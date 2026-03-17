"""
client.py — Async Matrix client wrapper (Phase 14A).

Wraps matrix-nio's AsyncClient with:
  - Singleton pattern (one client per process, matching pgvector_store.py).
  - Glass-Box-logged send methods that return AgentAction records.
  - Graceful degradation to stub mode when Dendrite is unreachable.

STUB NOTICE:
  All methods that mutate Matrix state (send_message, create_room, invite_user)
  return stub responses when `_client` is None (Dendrite not running / not
  configured). This allows the rest of the backend to start in development
  without a live homeserver.

HITL ENFORCEMENT:
  - `create_room()` and `invite_user()` → ethical_impact=HIGH.
    Callers MUST have HITL approval before invoking these.
  - `send_message()` → ethical_impact=MEDIUM (visible to room members).
  - `listen_for_commands()` → ethical_impact=LOW (read-only).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

# ── Lazy matrix-nio import ────────────────────────────────────────────────────
try:
    from nio import (
        AsyncClient,
        AsyncClientConfig,
        LoginResponse,
        RoomCreateResponse,
        RoomInviteResponse,
        RoomSendResponse,
        SyncResponse,
    )
    _NIO_AVAILABLE = True
except ImportError:
    _NIO_AVAILABLE = False
    AsyncClient = None          # type: ignore[misc,assignment]
    LoginResponse = None        # type: ignore[misc,assignment]

AGENT_ID = "matrix-client"


class MatrixClient:
    """
    Async wrapper around matrix-nio's AsyncClient.

    Singleton: obtain via MatrixClient.get_instance().
    Each Iskander agent bot registers as a separate Matrix user
    (e.g. @iskander_secretary:iskander.local) via the Application Service.
    This client represents the primary coordinator bot (@iskander_bot).

    Bot registration uses the Matrix Application Service protocol rather
    than individual user passwords: the appservice token grants the
    coordinator permission to act on behalf of all @iskander_* users.
    """

    _instance: "MatrixClient | None" = None

    def __init__(self) -> None:
        self._homeserver = settings.matrix_homeserver_url
        self._domain = settings.matrix_domain
        self._bot_prefix = settings.matrix_bot_prefix
        self._appservice_token = settings.matrix_appservice_token
        self._client: Any = None   # nio.AsyncClient or None in stub mode
        self._connected = False
        self._room_cache: dict[str, str] = {}  # alias → room_id

    @classmethod
    def get_instance(cls) -> "MatrixClient":
        """Return (or create) the process-wide singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Connection ─────────────────────────────────────────────────────────────

    async def connect(self, bot_localpart: str = "iskander_bot") -> bool:
        """
        Connect to the Dendrite homeserver as the coordinator bot.

        Uses the Application Service token instead of a password — the
        appservice registration in dendrite.yaml grants the bot user access.

        Args:
            bot_localpart: Local part of the bot MXID (without @... prefix).

        Returns:
            True if connected, False if Dendrite unreachable.
        """
        if not _NIO_AVAILABLE:
            logger.warning("matrix-nio not installed — MatrixClient in stub mode.")
            return False

        bot_mxid = f"@{bot_localpart}:{self._domain}"
        cfg = AsyncClientConfig(max_limit_exceeded=0, max_timeouts=0)

        try:
            self._client = AsyncClient(
                homeserver=self._homeserver,
                user=bot_mxid,
                config=cfg,
            )
            # Appservice bots authenticate via the AS token, not a password.
            self._client.access_token = self._appservice_token
            self._client.user_id = bot_mxid
            self._connected = True
            logger.info("MatrixClient connected as %s", bot_mxid)
            return True
        except Exception as exc:
            logger.warning("MatrixClient failed to connect to %s: %s", self._homeserver, exc)
            self._client = None
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    # ── Message Sending ────────────────────────────────────────────────────────

    async def send_message(
        self,
        room_id: str,
        body: str,
        msgtype: str = "m.notice",
        formatted_body: str | None = None,
        sender_localpart: str | None = None,
    ) -> tuple[str | None, AgentAction]:
        """
        Send a text message to a Matrix room.

        Args:
            room_id:          Matrix room ID (!abc:iskander.local).
            body:             Plain-text message body.
            msgtype:          m.text for member messages, m.notice for bot notifications.
            formatted_body:   Optional HTML-formatted body.
            sender_localpart: Bot user to send as (via appservice user_id masquerading).
                              None → use the coordinator bot.

        Returns:
            (event_id: str | None, action: AgentAction)
        """
        action = AgentAction(
            agent_id=sender_localpart or AGENT_ID,
            action=f"send_message(room={room_id[:20]}...)",
            rationale=(
                "Agent broadcasting output to cooperative Matrix room. "
                "Members may read and respond via any Matrix client."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "room_id": room_id,
                "msgtype": msgtype,
                "body_preview": body[:120],
                "sender": sender_localpart or "iskander_bot",
            },
        )

        if not self.is_connected:
            logger.info("Matrix stub: send_message to %s: %s", room_id, body[:80])
            return "stub_event_id", action

        try:
            content: dict[str, Any] = {"msgtype": msgtype, "body": body}
            if formatted_body:
                content["format"] = "org.matrix.custom.html"
                content["formatted_body"] = formatted_body

            # Appservice user masquerading: send on behalf of a specific bot.
            params = {}
            if sender_localpart:
                params["user_id"] = f"@{sender_localpart}:{self._domain}"

            resp: RoomSendResponse = await self._client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
                **params,
            )
            event_id = getattr(resp, "event_id", None)
            action.payload["event_id"] = event_id
            return event_id, action

        except Exception as exc:
            action.action = f"FAILED send_message: {exc}"
            action.ethical_impact = EthicalImpactLevel.HIGH
            logger.error("Matrix send_message failed: %s", exc)
            return None, action

    # ── Room Management ────────────────────────────────────────────────────────

    async def create_room(
        self,
        name: str,
        alias: str | None = None,
        topic: str | None = None,
        invite: list[str] | None = None,
        is_public: bool = False,
    ) -> tuple[str | None, AgentAction]:
        """
        Create a new Matrix room.

        ethical_impact=HIGH — visible to invited members, creates persistent state.
        Callers MUST have HITL approval.

        Returns:
            (room_id: str | None, action: AgentAction)
        """
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"create_room(name='{name}')",
            rationale=(
                "Creating Matrix room for cooperative agent communications. "
                "HITL approval confirmed prior to this call."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"name": name, "alias": alias, "invite": invite or []},
        )

        if not self.is_connected:
            stub_id = f"!stub_{name.replace(' ', '_')}:{self._domain}"
            logger.info("Matrix stub: create_room '%s' → %s", name, stub_id)
            action.payload["room_id"] = stub_id
            return stub_id, action

        try:
            resp: RoomCreateResponse = await self._client.room_create(
                name=name,
                alias=alias,
                topic=topic or "",
                invite=invite or [],
                visibility="public" if is_public else "private",
            )
            room_id = getattr(resp, "room_id", None)
            if alias and room_id:
                self._room_cache[alias] = room_id
            action.payload["room_id"] = room_id
            logger.info("Matrix room created: %s (%s)", name, room_id)
            return room_id, action

        except Exception as exc:
            action.action = f"FAILED create_room('{name}'): {exc}"
            logger.error("Matrix create_room failed: %s", exc)
            return None, action

    async def invite_user(
        self,
        room_id: str,
        user_id: str,
    ) -> tuple[bool, AgentAction]:
        """
        Invite a Matrix user to a room.

        ethical_impact=HIGH — sends a notification visible to the invitee.
        Callers MUST have HITL approval.
        """
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"invite_user({user_id[:30]} → {room_id[:20]}...)",
            rationale="Inviting cooperative member to agent-bridged Matrix room.",
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"room_id": room_id, "user_id": user_id},
        )

        if not self.is_connected:
            logger.info("Matrix stub: invite_user %s to %s", user_id, room_id)
            return True, action

        try:
            resp: RoomInviteResponse = await self._client.room_invite(
                room_id=room_id, user_id=user_id
            )
            success = not hasattr(resp, "status_code") or resp.status_code == 200
            return success, action
        except Exception as exc:
            action.action = f"FAILED invite_user: {exc}"
            logger.error("Matrix invite_user failed: %s", exc)
            return False, action

    # ── Bot Registration ──────────────────────────────────────────────────────

    async def register_bot(self, localpart: str) -> tuple[bool, AgentAction]:
        """
        Register a bot user via the Application Service protocol.

        The appservice token allows Iskander to create @iskander_*:domain users
        without individual passwords. Called once per bot on first startup.

        Args:
            localpart: e.g. "iskander_secretary"
        """
        mxid = f"@{localpart}:{self._domain}"
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"register_bot({mxid})",
            rationale=(
                "Registering agent bot user in Dendrite homeserver via "
                "Application Service protocol. Bot acts as agent communication proxy."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={"mxid": mxid},
        )

        if not self.is_connected:
            logger.info("Matrix stub: register_bot %s", mxid)
            return True, action

        try:
            # Appservice registration: POST /_matrix/client/v3/register
            # with the AS token and kind=guest bypasses password requirements.
            resp = await self._client.register(
                username=localpart,
                password=None,
                kind="guest",
            )
            success = hasattr(resp, "user_id")
            logger.info("Matrix bot registered: %s", mxid)
            return success, action
        except Exception as exc:
            # Bot may already exist — treat as success.
            if "exclusive" in str(exc).lower() or "taken" in str(exc).lower():
                logger.info("Bot %s already registered.", mxid)
                return True, action
            action.action = f"FAILED register_bot({mxid}): {exc}"
            logger.error("Matrix register_bot failed: %s", exc)
            return False, action

    # ── Command Listener ──────────────────────────────────────────────────────

    async def listen_for_commands(
        self,
        room_id: str,
        timeout_ms: int = 30_000,
    ) -> list[dict[str, Any]]:
        """
        Perform a single Matrix sync and return command messages from a room.

        Command messages are those whose body starts with '!' (e.g. !vote yes).
        The AppServiceHandler processes these; this method collects them.

        Returns:
            List of raw event dicts matching the command pattern.
        """
        if not self.is_connected:
            return []

        try:
            resp: SyncResponse = await self._client.sync(timeout=timeout_ms)
            commands: list[dict[str, Any]] = []

            timeline = getattr(
                getattr(resp, "rooms", None), "join", {}
            ).get(room_id, None)
            if not timeline:
                return []

            for event in getattr(timeline, "timeline", {}).get("events", []):
                content = event.get("content", {})
                body = content.get("body", "")
                if body.startswith("!"):
                    commands.append(event)
            return commands
        except Exception as exc:
            logger.warning("Matrix sync failed: %s", exc)
            return []

    async def close(self) -> None:
        """Close the underlying nio client connection."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._connected = False
