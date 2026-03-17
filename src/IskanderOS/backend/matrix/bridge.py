"""
bridge.py — Agent ↔ Matrix Room bridge (Phase 14A).

Each Iskander agent type maps to:
  - A dedicated bot user: @iskander_<agent>:<domain>
  - A persistent Matrix room: #iskander_<agent>:<domain>

The bridge is a thin coordination layer: given an agent_id and a message,
it resolves the correct bot/room pair and delegates to MatrixClient.

BOT ROSTER:
  @iskander_secretary:<domain>   → #iskander_governance:<domain>
  @iskander_treasurer:<domain>   → #iskander_treasury:<domain>
  @iskander_steward:<domain>     → #iskander_steward:<domain>
  @iskander_bot:<domain>         → #iskander_general:<domain> (catch-all)
  @iskander_provisioner:<domain> → #iskander_appstore:<domain>

GLASS BOX:
  send_to_room() logs an AgentAction and returns it so callers can append
  it to the LangGraph state's action_log.

USAGE in LangGraph nodes:
    bridge = AgentBridge.get_instance()
    event_id, action = await bridge.send_to_room(
        agent_id="secretary-agent-v1",
        body="Meeting summary published.",
    )
    state["action_log"].append(action.model_dump())
"""
from __future__ import annotations

import logging
from typing import Any

from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

# ── Agent → Bot/Room Routing Table ────────────────────────────────────────────
# Maps agent_id prefixes to (bot_localpart, room_alias_localpart).
# Extend this table when new agents are spawned via the AJD system.

_AGENT_ROUTING: dict[str, tuple[str, str]] = {
    "secretary":   ("iskander_secretary",   "iskander_governance"),
    "treasurer":   ("iskander_treasurer",   "iskander_treasury"),
    "steward":     ("iskander_steward",     "iskander_steward"),
    "governance":  ("iskander_secretary",   "iskander_governance"),
    "provisioner": ("iskander_provisioner", "iskander_appstore"),
    "procurement": ("iskander_treasurer",   "iskander_treasury"),
    "inventory":   ("iskander_bot",         "iskander_general"),
    "default":     ("iskander_bot",         "iskander_general"),
}


def _resolve_routing(agent_id: str) -> tuple[str, str]:
    """
    Resolve (bot_localpart, room_localpart) for a given agent_id.

    Matching is done by substring — "steward-agent-v2" → "steward" key.
    Falls back to "default" if no match.
    """
    agent_lower = agent_id.lower()
    for key, routing in _AGENT_ROUTING.items():
        if key in agent_lower:
            return routing
    return _AGENT_ROUTING["default"]


class AgentBridge:
    """
    Coordinates agent output → Matrix room delivery.

    Singleton: obtain via AgentBridge.get_instance().
    """

    _instance: "AgentBridge | None" = None

    def __init__(self) -> None:
        self._domain = settings.matrix_domain
        # room_id cache: alias_localpart → !room_id:domain
        self._room_ids: dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> "AgentBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Room ID resolution ────────────────────────────────────────────────────

    def register_room(self, alias_localpart: str, room_id: str) -> None:
        """
        Register a known room_id for an alias localpart.

        Called during startup after ensure_rooms() creates or resolves rooms.
        """
        self._room_ids[alias_localpart] = room_id
        logger.info("Bridge: registered room %s → %s", alias_localpart, room_id)

    def get_room_id(self, alias_localpart: str) -> str | None:
        """Return the room_id for an alias localpart, or None if unknown."""
        return self._room_ids.get(alias_localpart)

    def get_room_alias(self, alias_localpart: str) -> str:
        """Return the full room alias: #<localpart>:<domain>."""
        return f"#{alias_localpart}:{self._domain}"

    def get_bot_mxid(self, bot_localpart: str) -> str:
        """Return the full MXID: @<localpart>:<domain>."""
        return f"@{bot_localpart}:{self._domain}"

    # ── Message Routing ───────────────────────────────────────────────────────

    async def send_to_room(
        self,
        agent_id: str,
        body: str,
        formatted_body: str | None = None,
        room_override: str | None = None,
    ) -> tuple[str | None, AgentAction]:
        """
        Send an agent message to its designated Matrix room.

        Resolves the correct bot user and room for the agent_id, then
        delegates to MatrixClient.send_message().

        Args:
            agent_id:       The sending agent's ID (e.g. "steward-agent-v2").
            body:           Plain-text message body.
            formatted_body: Optional HTML body.
            room_override:  If set, override the routing table's room.

        Returns:
            (event_id: str | None, action: AgentAction)
        """
        from backend.matrix.client import MatrixClient

        bot_localpart, room_localpart = _resolve_routing(agent_id)
        target_room = room_override or self._room_ids.get(room_localpart)

        if not target_room:
            # Room not yet initialised — use alias as fallback.
            target_room = self.get_room_alias(room_localpart)
            logger.warning(
                "Bridge: room_id unknown for '%s', using alias %s",
                room_localpart, target_room,
            )

        client = MatrixClient.get_instance()
        event_id, action = await client.send_message(
            room_id=target_room,
            body=body,
            msgtype="m.notice",
            formatted_body=formatted_body,
            sender_localpart=bot_localpart,
        )
        return event_id, action

    # ── Startup: ensure all agent rooms exist ─────────────────────────────────

    async def ensure_rooms(self) -> list[AgentAction]:
        """
        Idempotently ensure all agent rooms exist in Dendrite.

        Called on FastAPI startup. For each (bot, room) pair in the routing
        table, attempts to create the room if it does not already exist.
        Rooms that already exist are resolved and cached.

        Returns:
            List of AgentAction records for the startup log.
        """
        from backend.matrix.client import MatrixClient

        client = MatrixClient.get_instance()
        actions: list[AgentAction] = []

        room_configs = [
            ("iskander_general",    "iskander_general",    "Iskander — General",       "general"),
            ("iskander_governance", "iskander_governance",  "Iskander — Governance",    "governance"),
            ("iskander_treasury",   "iskander_treasury",   "Iskander — Treasury",      "treasury"),
            ("iskander_steward",    "iskander_steward",    "Iskander — Steward",       "steward"),
            ("iskander_appstore",   "iskander_appstore",   "Iskander — App Store",     "general"),
        ]

        for bot_lp, room_lp, room_name, room_type in room_configs:
            room_id, action = await client.create_room(
                name=room_name,
                alias=room_lp,
                topic=f"Iskander cooperative agent room: {room_name}",
            )
            actions.append(action)
            if room_id:
                self.register_room(room_lp, room_id)

        return actions

    # ── Notification helpers ──────────────────────────────────────────────────

    async def notify_hitl_required(
        self,
        agent_id: str,
        proposal_summary: str,
        proposal_id: str,
    ) -> tuple[str | None, AgentAction]:
        """
        Send a HITL approval request to the governance room.

        Formats a clear call-to-action so members know they need to vote
        via !vote <proposal_id> yes|no or the Streamlit dashboard.
        """
        body = (
            f"**Action Required — Governance Vote**\n\n"
            f"Agent `{agent_id}` is awaiting democratic approval:\n\n"
            f"> {proposal_summary}\n\n"
            f"Vote via Matrix: `!vote {proposal_id} yes` or `!vote {proposal_id} no`\n"
            f"Or use the Iskander dashboard at http://iskander.local:8501"
        )
        return await self.send_to_room(
            agent_id=agent_id,
            body=body,
            room_override=self._room_ids.get("iskander_governance"),
        )

    async def notify_deployment_complete(
        self,
        app_name: str,
        access_url: str,
    ) -> tuple[str | None, AgentAction]:
        """Announce a successful app deployment to the app store room."""
        body = (
            f"**App Deployed** — `{app_name}`\n\n"
            f"Access at: {access_url}\n\n"
            f"The cooperative now self-hosts this application. "
            f"Data remains on this node."
        )
        return await self.send_to_room(
            agent_id="provisioner",
            body=body,
            room_override=self._room_ids.get("iskander_appstore"),
        )

    # ── Generic node function (for node_registry.py) ──────────────────────────

    async def send_matrix_notification_node(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generic LangGraph node: sends an agent state summary to its Matrix room.

        Registered in node_registry.py as "send_matrix_notification".
        Reads state["agent_id"] and state.get("matrix_notification_body") or
        falls back to the last action_log entry's action string.
        """
        agent_id = state.get("agent_id", "iskander_bot")
        body = state.get("matrix_notification_body") or (
            (state.get("action_log") or [{}])[-1].get("action", "Agent action completed.")
        )

        event_id, action = await self.send_to_room(
            agent_id=agent_id,
            body=str(body),
        )

        return {
            **state,
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }
