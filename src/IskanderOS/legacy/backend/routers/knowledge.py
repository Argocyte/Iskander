"""
knowledge.py — Iskander Knowledge Commons (IKC) API Router.

Endpoints for registering knowledge assets, submitting curation proposals
(invokes the CuratorDebate LangGraph), HITL review for escalated debates,
Break-Glass activation/deactivation, and dependency queries.

All content is pinned to the Mesh Archive (IPFS) via SovereignStorage and
referenced by CID. The tombstone-only invariant is enforced at the
LibraryManager level — this router never deletes CIDs.
"""
from __future__ import annotations

import base64
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from backend.agents.library.curator_network import curator_network_graph
from backend.auth.dependencies import AuthenticatedUser, require_role
from backend.mesh.library_manager import LibraryManager
from backend.schemas.knowledge import (
    CurationProposalRequest,
    CurationProposalResponse,
    CurationReviewRequest,
    DependentsResponse,
    RegisterAssetRequest,
    RegisterAssetResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge-commons"])


# ── POST /knowledge/register ─────────────────────────────────────────────────

@router.post("/register", response_model=RegisterAssetResponse)
async def register_asset(
    req: RegisterAssetRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> RegisterAssetResponse:
    """Register a new knowledge asset — pin content to IPFS, record dependencies."""
    try:
        raw = base64.b64decode(req.data_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 data")

    lib = LibraryManager.get_instance()
    try:
        asset, action = await lib.register_asset(
            data=raw,
            title=req.title,
            author_did=req.author_did,
            description=req.description,
            dependency_manifest=req.dependency_manifest,
            audience=req.audience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return RegisterAssetResponse(
        asset_id=str(asset.asset_id),
        cid=asset.cid,
        version=asset.version,
        status=asset.status.value,
    )


# ── GET /knowledge/asset/{cid} ───────────────────────────────────────────────

@router.get("/asset/{cid}")
async def get_asset(
    cid: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> dict:
    """Retrieve asset metadata by CID."""
    lib = LibraryManager.get_instance()
    try:
        asset, _action = await lib.get_asset(cid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Asset not found: {cid}")

    return asset.model_dump(mode="json")


# ── POST /knowledge/curate ───────────────────────────────────────────────────

@router.post("/curate", response_model=CurationProposalResponse)
async def submit_curation_proposal(
    req: CurationProposalRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> CurationProposalResponse:
    """Submit a curation proposal — invokes the CuratorDebate LangGraph.

    If curators reach unanimous consensus, the status change is applied
    immediately. If not, the debate is escalated to the StewardshipCouncil
    via HITL and returns ``status='escalated_to_council'``.
    """
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "curator-network-v1",
        "action_log": [],
        "error": None,
        "asset_cid": req.asset_cid,
        "proposed_status": req.proposed_status.value,
        "proposer_rationale": req.rationale,
        "asset_metadata": None,
        "downstream_deps": [],
        "dependency_check_passed": True,
        "votes": [],
        "consensus_status": "in_progress",
        "rationale_log": [],
        "escalation_signal": False,
        "break_glass_active": False,
        "requires_human_token": False,
    }

    try:
        curator_network_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Curator graph error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Curator graph error: {exc}")

    snapshot = curator_network_graph.get_state(config)
    state = snapshot.values

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    consensus = state.get("consensus_status", "in_progress")

    # Map consensus to response status
    if consensus == "unanimous_approve":
        status = "consensus_reached"
    elif consensus == "unanimous_reject":
        status = "consensus_reached"
    elif consensus == "escalated":
        status = "escalated_to_council"
    elif consensus == "rejected_downstream_deps":
        status = "rejected_downstream_deps"
    elif consensus == "paused":
        status = "paused"
    else:
        status = consensus

    return CurationProposalResponse(
        thread_id=thread_id,
        status=status,
        votes=state.get("votes", []),
        consensus_status=consensus,
        rationale_log=state.get("rationale_log", []),
        action_log=state.get("action_log", []),
    )


# ── POST /knowledge/curate/review ────────────────────────────────────────────

@router.post("/curate/review", response_model=CurationProposalResponse)
async def review_curation(
    req: CurationReviewRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> CurationProposalResponse:
    """HITL resume endpoint for escalated curator debates.

    The StewardshipCouncil approves or rejects the proposed status change.
    If approved, the graph resumes and applies the change. If rejected,
    the debate ends with the original status preserved.
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        snapshot = curator_network_graph.get_state(config)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"No active debate found for thread_id: {req.thread_id}",
        )

    state = snapshot.values
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"No active debate found for thread_id: {req.thread_id}",
        )

    if not req.approved:
        # Council rejected — do not apply status change
        return CurationProposalResponse(
            thread_id=req.thread_id,
            status="council_rejected",
            votes=state.get("votes", []),
            consensus_status="council_rejected",
            rationale_log=state.get("rationale_log", []) + [
                f"StewardshipCouncil rejected: {req.reason or 'no reason given'}"
            ],
            action_log=state.get("action_log", []),
        )

    # Resume the graph past the HITL breakpoint
    curator_network_graph.update_state(
        config,
        {"requires_human_token": False},
        as_node="human_review_curation",
    )
    curator_network_graph.invoke(None, config=config)

    updated = curator_network_graph.get_state(config).values

    return CurationProposalResponse(
        thread_id=req.thread_id,
        status="consensus_reached",
        votes=updated.get("votes", []),
        consensus_status=updated.get("consensus_status", ""),
        rationale_log=updated.get("rationale_log", []) + [
            f"StewardshipCouncil approved: {req.reason or 'approved'}"
        ],
        action_log=updated.get("action_log", []),
    )


# ── POST /knowledge/break-glass ──────────────────────────────────────────────

@router.post("/break-glass")
async def activate_break_glass(
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Activate Break-Glass — halt all curation activity."""
    lib = LibraryManager.get_instance()
    try:
        action = lib.activate_break_glass()
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    return {
        "status": "break_glass_activated",
        "action": action.model_dump(),
    }


# ── DELETE /knowledge/break-glass ─────────────────────────────────────────────

@router.delete("/break-glass")
async def deactivate_break_glass(
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict:
    """Deactivate Break-Glass — resume curation activity."""
    lib = LibraryManager.get_instance()
    action = lib.deactivate_break_glass()

    return {
        "status": "break_glass_deactivated",
        "action": action.model_dump(),
    }


# ── GET /knowledge/dependents/{cid} ──────────────────────────────────────────

@router.get("/dependents/{cid}", response_model=DependentsResponse)
async def get_dependents(
    cid: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> DependentsResponse:
    """List active assets that depend on this CID."""
    lib = LibraryManager.get_instance()
    deps, _action = await lib.check_downstream_impact(cid)

    return DependentsResponse(
        cid=cid,
        dependents=deps,
        count=len(deps),
    )
