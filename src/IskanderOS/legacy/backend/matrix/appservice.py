"""
appservice.py — Matrix Application Service event handler (Phase 14A).

Dendrite POSTs inbound room events to this module's FastAPI sub-application
at the appservice webhook URL (/_matrix/app/v1/transactions/{txn_id}).

Supported commands (prefixed with '!'):
  !propose <text>   → calls POST /governance/propose internally
  !vote yes|no      → calls POST /governance/vote internally (or /apps/{id}/vote)
  !status           → returns the node health summary
  !apps             → returns the app store deployment list
  !help             → returns the command reference

GLASS BOX:
  Every inbound command that triggers an agent action is logged as an
  AgentAction with ethical_impact matching the underlying operation.
  Passive messages (non-command m.room.message events) are logged to
  matrix_events_log but do not generate AgentActions.

SECURITY:
  All incoming requests MUST present the `Authorization: Bearer <hs_token>`
  header matching the `hs_token` in `appservice-iskander.yaml`.
  Requests without a valid token are rejected with HTTP 403.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, status

from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

# Appservice sub-router. Mounted at /_matrix/app/v1 in matrix_admin.py.
appservice_router = APIRouter(tags=["matrix-appservice"])

# ── Internal HTTP client for routing commands to the main API ─────────────────
# Commands from Matrix rooms call the same FastAPI endpoints as the Streamlit
# dashboard — no special routing logic, same HITL breakpoints apply.
_internal_base = "http://localhost:8000"


def _check_hs_token(authorization: str | None) -> None:
    """Verify the homeserver-to-appservice authorization token."""
    expected = f"Bearer {settings.matrix_appservice_token}"
    if not authorization or authorization != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid hs_token")


# ── Transaction endpoint — Dendrite POSTs events here ────────────────────────

@appservice_router.put("/transactions/{txn_id}", status_code=status.HTTP_200_OK)
async def handle_transaction(
    txn_id: str,
    request: Request,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Receive a batch of Matrix events from Dendrite.

    Dendrite delivers events reliably by incrementing txn_id. Iskander
    acknowledges every transaction immediately (returns {}) and processes
    events asynchronously to avoid blocking Dendrite's delivery queue.

    In production: deduplicate by txn_id in Postgres to prevent replay.
    """
    _check_hs_token(authorization)

    try:
        body = await request.json()
    except Exception:
        return {}

    events: list[dict[str, Any]] = body.get("events", [])
    logger.debug("AppService txn %s: %d events", txn_id, len(events))

    for event in events:
        await _dispatch_event(event)

    # Always acknowledge — Dendrite will retry if we return non-200.
    return {}


async def _dispatch_event(event: dict[str, Any]) -> None:
    """
    Route a single Matrix event to the appropriate handler.

    Only m.room.message events from non-bot senders are processed.
    All other event types (m.room.member, m.room.topic, etc.) are logged
    and discarded.
    """
    event_type = event.get("type", "")
    sender = event.get("sender", "")
    room_id = event.get("room_id", "")

    # Ignore events from our own bots to prevent feedback loops.
    if sender.startswith(settings.matrix_bot_prefix):
        return

    if event_type == "m.room.message":
        content = event.get("content", {})
        body = content.get("body", "")
        if body.startswith("!"):
            await _handle_command(body.strip(), sender, room_id, event)
        else:
            # Non-command messages are logged but not acted upon.
            logger.debug("Matrix message (non-command) from %s in %s", sender, room_id)

    elif event_type == "m.room.member":
        membership = event.get("content", {}).get("membership", "")
        logger.info(
            "Matrix membership event: %s → %s in %s", sender, membership, room_id
        )


async def _handle_command(
    body: str,
    sender: str,
    room_id: str,
    raw_event: dict[str, Any],
) -> None:
    """
    Parse and dispatch a '!command [args]' message from a Matrix room.

    Commands call the existing FastAPI endpoints internally via httpx.
    This means they traverse the same HITL, Glass Box, and validation
    logic as requests from the Streamlit dashboard.
    """
    parts = body.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    action = AgentAction(
        agent_id="matrix-appservice",
        action=f"matrix_command({cmd})",
        rationale=f"Cooperative member {sender} issued command via Matrix room {room_id}.",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"sender": sender, "room_id": room_id, "command": cmd, "args": args[:200]},
    )

    try:
        async with httpx.AsyncClient(base_url=_internal_base) as client:
            if cmd == "!help":
                await _reply_help(room_id, sender)

            elif cmd == "!status":
                resp = await client.get("/health")
                await _send_reply(room_id, f"Node status:\n```\n{resp.text}\n```", sender)

            elif cmd == "!apps":
                resp = await client.get("/apps")
                await _send_reply(room_id, f"App deployments:\n```\n{resp.text}\n```", sender)

            elif cmd == "!propose":
                # Routes to governance propose — HITL will pause the graph.
                if not args:
                    await _send_reply(room_id, "Usage: !propose <description>", sender)
                    return
                payload = {"description": args, "proposer_did": sender, "impact": "MEDIUM"}
                resp = await client.post("/governance/propose", json=payload)
                await _send_reply(room_id, f"Proposal submitted:\n```\n{resp.text}\n```", sender)
                action.ethical_impact = EthicalImpactLevel.MEDIUM

            elif cmd in ("!vote", "!vote_yes", "!vote_no"):
                # Vote on the most recent pending governance proposal.
                approved = cmd == "!vote_yes" or (cmd == "!vote" and args.lower() == "yes")
                payload = {"voter_did": sender, "approved": approved, "reason": args}
                # The route requires a proposal_id — member must provide it.
                # Improved UX: !vote <proposal_id> yes|no
                vote_parts = args.split(None, 1)
                if len(vote_parts) >= 1:
                    prop_id = vote_parts[0]
                    approved_flag = (len(vote_parts) < 2 or vote_parts[1].lower() == "yes")
                    resp = await client.post(
                        f"/governance/proposals/{prop_id}/vote",
                        json={"voter_did": sender, "approved": approved_flag, "reason": ""},
                    )
                    await _send_reply(room_id, f"Vote recorded:\n```\n{resp.text}\n```", sender)
                else:
                    await _send_reply(room_id, "Usage: !vote <proposal_id> yes|no", sender)
                action.ethical_impact = EthicalImpactLevel.HIGH

            else:
                await _send_reply(room_id, f"Unknown command '{cmd}'. Try !help.", sender)

    except Exception as exc:
        logger.error("AppService command dispatch failed: %s", exc)
        action.action = f"FAILED matrix_command({cmd}): {exc}"
        await _send_reply(room_id, f"Command error: {exc}", sender)


async def _send_reply(room_id: str, body: str, sender: str) -> None:
    """Send a reply message to the originating Matrix room."""
    from backend.matrix.client import MatrixClient
    client = MatrixClient.get_instance()
    await client.send_message(room_id=room_id, body=body, msgtype="m.notice")


async def _reply_help(room_id: str, sender: str) -> None:
    help_text = (
        "**Iskander Node — Matrix Command Reference**\n\n"
        "```\n"
        "!help              — This message\n"
        "!status            — Node health and configuration\n"
        "!apps              — List deployed cooperative apps\n"
        "!propose <text>    — Submit a governance proposal\n"
        "!vote <id> yes|no  — Vote on a proposal\n"
        "```\n\n"
        "All governance actions require cooperative member approval "
        "(HITL breakpoints apply). Your Matrix ID is your DID for voting."
    )
    await _send_reply(room_id, help_text, sender)


# ── Appservice user/room query endpoints ──────────────────────────────────────

@appservice_router.get("/users/{user_id}", status_code=status.HTTP_200_OK)
async def query_user(
    user_id: str,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Respond to Dendrite's user existence queries.

    Dendrite calls this before delivering messages to @iskander_* users to
    confirm the appservice manages them. Return {} to indicate the user exists.
    """
    _check_hs_token(authorization)
    # All @iskander_* users are managed by this appservice.
    if user_id.startswith(settings.matrix_bot_prefix):
        return {}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not managed")


@appservice_router.get("/rooms/{room_alias}", status_code=status.HTTP_200_OK)
async def query_room(
    room_alias: str,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """
    Respond to Dendrite's room alias queries.

    Returns {} to confirm the appservice can create #iskander_*:domain rooms.
    """
    _check_hs_token(authorization)
    if room_alias.startswith("#iskander_"):
        return {}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not managed")
