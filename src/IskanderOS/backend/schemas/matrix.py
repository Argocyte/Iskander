"""
Pydantic schemas for Phase 14: Matrix & ActivityPub Federation.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MatrixRoom(BaseModel):
    """A Matrix room managed by Iskander."""
    room_id: str
    room_alias: str | None = None
    agent_id: str | None = None
    room_type: str = Field(
        ...,
        description="One of: general, governance, treasury, steward, secretary",
    )
    topic: str | None = None


class MatrixMessage(BaseModel):
    """A message to send into a Matrix room."""
    room_id: str
    body: str
    msgtype: str = "m.text"   # m.text | m.notice | m.emote
    formatted_body: str | None = None  # HTML-formatted body (m.text + format=m.html)


class BridgeConfig(BaseModel):
    """Configuration for bridging an agent to a Matrix room."""
    agent_id: str
    room_id: str
    bot_user_id: str  # e.g. @iskander_secretary:iskander.local


class MatrixRoomCreate(BaseModel):
    """Request body for POST /matrix/rooms."""
    name: str
    alias: str | None = None
    room_type: str
    agent_id: str | None = None
    invite: list[str] = Field(default=[], description="Matrix user IDs to invite on creation.")
    topic: str | None = None


class MatrixStatus(BaseModel):
    """Runtime status of the Matrix integration."""
    homeserver_url: str
    domain: str
    connected: bool
    registered_bots: list[str]
    bridged_rooms: list[dict[str, Any]]


class AppServiceEvent(BaseModel):
    """Inbound event from Dendrite → Iskander appservice webhook."""
    type: str           # m.room.message, m.room.member, etc.
    event_id: str
    room_id: str
    sender: str
    origin_server_ts: int
    content: dict[str, Any] = {}
    unsigned: dict[str, Any] = {}
