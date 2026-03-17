"""
matrix_admin.py — Matrix homeserver admin API router (Phase 14A).

Endpoints:
  POST /matrix/rooms                  — Create a new Matrix room.
  GET  /matrix/rooms                  — List all bridged rooms.
  POST /matrix/bridge/{agent_id}      — Bridge an agent to a room.
  GET  /matrix/status                 — Matrix integration health.
  POST /matrix/notify/{agent_id}      — Send an ad-hoc notification from an agent.

The appservice webhook (/_matrix/app/v1/*) is sub-mounted from
backend.matrix.appservice.appservice_router so Dendrite's event delivery
lands at the correct path.

HITL:
  Room creation → requires HITL approval (ethical_impact=HIGH).
  Sending a message → ethical_impact=MEDIUM, no additional HITL.
  Reading room list / status → read-only, no HITL.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.matrix.appservice import appservice_router
from backend.matrix.bridge import AgentBridge
from backend.matrix.client import MatrixClient
from backend.schemas.matrix import BridgeConfig, MatrixRoomCreate, MatrixStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matrix", tags=["matrix"])

# Mount the Dendrite appservice webhook sub-router.
router.include_router(appservice_router, prefix="/_matrix/app/v1")


# ── POST /matrix/rooms ────────────────────────────────────────────────────────

@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_room(body: MatrixRoomCreate) -> dict[str, Any]:
    """
    Create a new Matrix room and bridge it to an agent.

    ethical_impact=HIGH — calls MatrixClient.create_room() which requires
    HITL approval in the calling context. For admin use only.
    """
    client = MatrixClient.get_instance()
    if not client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Matrix homeserver not connected. Check dendrite service.",
        )

    room_id, action = await client.create_room(
        name=body.name,
        alias=body.alias,
        topic=body.topic,
        invite=body.invite,
    )

    if not room_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Room creation failed. See server logs.",
        )

    bridge = AgentBridge.get_instance()
    if body.alias:
        bridge.register_room(body.alias, room_id)

    return {
        "room_id": room_id,
        "alias": body.alias,
        "agent_id": body.agent_id,
        "action": action.model_dump(),
    }


# ── GET /matrix/rooms ─────────────────────────────────────────────────────────

@router.get("/rooms", status_code=status.HTTP_200_OK)
async def list_rooms() -> dict[str, Any]:
    """List all rooms registered in the AgentBridge room cache."""
    bridge = AgentBridge.get_instance()
    rooms = [
        {"alias_localpart": k, "room_id": v}
        for k, v in bridge._room_ids.items()
    ]
    return {"rooms": rooms, "count": len(rooms)}


# ── POST /matrix/bridge/{agent_id} ────────────────────────────────────────────

@router.post("/bridge/{agent_id}", status_code=status.HTTP_200_OK)
async def bridge_agent(agent_id: str, body: BridgeConfig) -> dict[str, Any]:
    """
    Register an agent ↔ room bridge mapping.

    Allows dynamic bridging beyond the static routing table in bridge.py.
    Useful when a newly spawned AJD agent needs its own room.
    """
    bridge = AgentBridge.get_instance()
    # Derive room alias localpart from room_id or bot_user_id.
    alias_localpart = body.room_id.lstrip("!").split(":")[0] if body.room_id.startswith("!") else body.room_id
    bridge.register_room(alias_localpart, body.room_id)

    return {
        "agent_id": agent_id,
        "room_id": body.room_id,
        "bot_user_id": body.bot_user_id,
        "registered": True,
    }


# ── GET /matrix/status ────────────────────────────────────────────────────────

@router.get("/status", status_code=status.HTTP_200_OK)
async def matrix_status() -> MatrixStatus:
    """Return the Matrix integration health and configuration."""
    from backend.config import settings

    client = MatrixClient.get_instance()
    bridge = AgentBridge.get_instance()

    from backend.matrix.bridge import _AGENT_ROUTING
    registered_bots = list({bot for bot, _ in _AGENT_ROUTING.values()})

    return MatrixStatus(
        homeserver_url=settings.matrix_homeserver_url,
        domain=settings.matrix_domain,
        connected=client.is_connected,
        registered_bots=[f"@{b}:{settings.matrix_domain}" for b in registered_bots],
        bridged_rooms=[
            {"alias_localpart": k, "room_id": v}
            for k, v in bridge._room_ids.items()
        ],
    )


# ── POST /matrix/notify/{agent_id} ────────────────────────────────────────────

@router.post("/notify/{agent_id}", status_code=status.HTTP_200_OK)
async def send_notification(agent_id: str, message: str) -> dict[str, Any]:
    """
    Send an ad-hoc notification from an agent to its Matrix room.

    Useful for manual announcements or testing the bridge.
    """
    bridge = AgentBridge.get_instance()
    event_id, action = await bridge.send_to_room(agent_id=agent_id, body=message)
    return {"event_id": event_id, "action": action.model_dump()}
