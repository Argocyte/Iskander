"""
Phase 25: Pydantic schemas for the Mesh Archive / Sovereign Data Fabric.

Request/response models for:
  - IPFS pin and retrieval
  - Causal event creation and listing
  - Delta-sync between federated peers
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── IPFS Pin ─────────────────────────────────────────────────────────────────


class PinRequest(BaseModel):
    """Request to pin data to the local IPFS node."""

    data: str = Field(
        ...,
        description="Base64-encoded payload to pin.",
    )
    audience: Literal["federation", "council", "node"] = Field(
        default="federation",
        description="Encryption audience scope.",
    )


class PinResponse(BaseModel):
    """Response after pinning data to IPFS."""

    cid: str = Field(..., description="Content identifier returned by IPFS.")
    audience: str = Field(..., description="Audience the data was encrypted for.")
    encrypted: bool = Field(
        default=True,
        description="Whether the pinned data is encrypted.",
    )
    replica_count: int = Field(
        default=1,
        description="Number of mesh peers that confirmed pinning this CID.",
    )


# ── Causal Events ────────────────────────────────────────────────────────────


class CausalEventCreate(BaseModel):
    """Request to create and pin a new causal event."""

    event_type: str = Field(..., description="Dot-separated event type identifier.")
    source_agent_id: str = Field(..., description="Agent that originated the event.")
    payload: dict = Field(default_factory=dict, description="Event payload.")
    audience: Literal["federation", "council", "node"] = Field(
        default="federation",
        description="Encryption audience scope.",
    )


class CausalEventResponse(BaseModel):
    """Response containing a persisted causal event."""

    id: str
    event_type: str
    source_agent_id: str
    ipfs_cid: str
    audience: str
    created_at: datetime


# ── Delta Sync ───────────────────────────────────────────────────────────────


class SyncRequest(BaseModel):
    """Request to trigger a delta-sync with a peer node."""

    peer_did: str = Field(..., description="W3C DID of the target peer node.")
    cids: list[str] = Field(
        default_factory=list,
        description="CIDs to sync to the peer.",
    )


class SyncStatusResponse(BaseModel):
    """Outcome of a delta-sync operation."""

    peer_did: str
    direction: str
    cids_synced: int
    cids_denied: int
    timestamp: datetime
