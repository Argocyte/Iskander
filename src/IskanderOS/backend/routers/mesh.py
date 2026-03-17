"""
/mesh — Mesh Archive / Sovereign Data Fabric endpoints (Phase 25).

Content-addressed, permission-aware distributed storage. All data is
encrypted per-audience before pinning to IPFS.  Access is gated by
gSBT identity tokens and cooperative role-based auth.
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.auth.dependencies import AuthenticatedUser, require_role
from backend.mesh.causal_event import CausalEvent
from backend.mesh.delta_sync import DeltaSyncProtocol
from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.mesh import (
    CausalEventCreate,
    CausalEventResponse,
    PinRequest,
    PinResponse,
    SyncRequest,
    SyncStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mesh", tags=["mesh"])


# ── Pin ──────────────────────────────────────────────────────────────────────


@router.post("/pin", response_model=PinResponse)
async def pin_data(
    req: PinRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Pin data to the local IPFS node.

    The payload is base64-decoded, encrypted for the specified audience,
    and pinned.  Returns the resulting CID.
    """
    try:
        raw = base64.b64decode(req.data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 data: {exc}") from exc

    storage = SovereignStorage.get_instance()
    cid, _action = await storage.pin(raw, audience=req.audience)

    return PinResponse(cid=cid, audience=req.audience, encrypted=True)


# ── Cat ──────────────────────────────────────────────────────────────────────


@router.get("/cat/{cid}")
async def cat_data(
    cid: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Retrieve content by CID from the local IPFS node.

    Returns the decrypted content as base64-encoded JSON (to avoid binary
    transport issues).
    """
    storage = SovereignStorage.get_instance()
    try:
        plaintext, _action = await storage.cat(cid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"CID not found: {cid}")

    encoded = base64.b64encode(plaintext).decode()
    return {"cid": cid, "data": encoded}


# ── Causal Events ────────────────────────────────────────────────────────────


@router.post("/events", response_model=CausalEventResponse)
async def create_event(
    req: CausalEventCreate,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Create a new causal event, encrypt it, and pin to IPFS."""
    record, _action = await CausalEvent.create(
        event_type=req.event_type,
        source_agent_id=req.source_agent_id,
        payload=req.payload,
        audience=req.audience,
    )

    return CausalEventResponse(
        id=record.id,
        event_type=record.event_type,
        source_agent_id=record.source_agent_id,
        ipfs_cid=record.ipfs_cid,
        audience=record.audience,
        created_at=record.timestamp,
    )


@router.get("/events", response_model=list[CausalEventResponse])
async def list_events(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """List recent causal events.

    STUB: returns an empty list.  In production this would query the
    local event store / database.
    """
    return []


# ── Delta Sync ───────────────────────────────────────────────────────────────


@router.post("/sync", response_model=SyncStatusResponse)
async def trigger_sync(
    req: SyncRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Trigger a delta-sync of CIDs to a peer node."""
    protocol = DeltaSyncProtocol.get_instance()
    result = await protocol.sync_to_peer(peer_did=req.peer_did, cids=req.cids)

    return SyncStatusResponse(
        peer_did=result.peer_did,
        direction=result.direction,
        cids_synced=len(result.cids_synced),
        cids_denied=len(result.cids_denied),
        timestamp=result.timestamp,
    )
