"""
HITL Governance API — FastAPI router

POST /governance/propose   — Submit a governance proposal; starts the agent graph
GET  /governance/proposals/{thread_id} — Fetch current graph state (pending tx draft)
POST /governance/vote      — Cast a human approve/reject vote; resumes the graph
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.agents.governance_agent import governance_graph
from backend.auth.dependencies import AuthenticatedUser, get_current_user, require_role

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/governance", tags=["governance"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class ProposalRequest(BaseModel):
    description:  str           = Field(..., description="Natural language description of the proposal")
    to:           str | None    = Field(default=None, description="EVM recipient address (optional if described)")
    value_wei:    int           = Field(default=0, description="ETH value in wei")
    data:         str           = Field(default="0x", description="Calldata hex string")
    nonce:        int           = Field(default=0, description="Safe nonce")
    proposed_by:  str           = Field(..., description="Member DID or address of proposer")


class VoteRequest(BaseModel):
    thread_id:        str  = Field(..., description="Graph thread ID from POST /propose response")
    approved:         bool = Field(..., description="True = approve, False = reject")
    rejection_reason: str  = Field(default="", description="Required if approved=false")
    voter_did:        str  = Field(..., description="DID or address of the voting steward")


class ProposalResponse(BaseModel):
    thread_id:     str
    status:        str
    safe_tx_draft: dict[str, Any] | None
    action_log:    list[dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/propose",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a governance proposal — starts the HITL agent graph",
)
async def submit_proposal(
    req: ProposalRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> ProposalResponse:
    """
    Starts the Governance Agent graph. The graph runs `draft_safe_tx`
    then suspends at the `human_review` HITL breakpoint.

    Returns the thread_id for subsequent status polling and voting.
    """
    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages":         [],
        "agent_id":         "governance-agent-v1",
        "action_log":       [],
        "error":            None,
        "proposal": {
            "id":           thread_id,
            "description":  req.description,
            "to":           req.to,
            "value_wei":    req.value_wei,
            "data":         req.data,
            "nonce":        req.nonce,
            "proposed_by":  req.proposed_by,
        },
        "safe_tx_draft":    None,
        "hitl_approved":    None,
        "rejection_reason": None,
    }

    try:
        # Run until HITL breakpoint (interrupt_before=["human_review"])
        governance_graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("governance_graph_error", error=str(exc), thread_id=thread_id)
        raise HTTPException(status_code=500, detail=f"Agent graph error: {exc}")

    # Retrieve checkpointed state
    snapshot = governance_graph.get_state(config)
    state    = snapshot.values

    logger.info("proposal_submitted", thread_id=thread_id, proposed_by=req.proposed_by)

    return ProposalResponse(
        thread_id=thread_id,
        status="pending_human_review",
        safe_tx_draft=state.get("safe_tx_draft"),
        action_log=state.get("action_log", []),
    )


@router.get(
    "/proposals/{thread_id}",
    response_model=ProposalResponse,
    summary="Fetch current state of a governance proposal",
)
async def get_proposal(thread_id: str) -> ProposalResponse:
    """Poll the checkpointed graph state for a given proposal thread."""
    config = {"configurable": {"thread_id": thread_id}}

    try:
        snapshot = governance_graph.get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Thread not found: {exc}")

    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Proposal not found")

    state  = snapshot.values
    approved = state.get("hitl_approved")
    if approved is None:
        tx_status = "pending_human_review"
    elif approved:
        tx_status = "approved"
    else:
        tx_status = "rejected"

    return ProposalResponse(
        thread_id=thread_id,
        status=tx_status,
        safe_tx_draft=state.get("safe_tx_draft"),
        action_log=state.get("action_log", []),
    )


@router.post(
    "/vote",
    response_model=ProposalResponse,
    summary="Cast a human approve/reject vote — resumes the HITL graph",
)
async def cast_vote(
    req: VoteRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
) -> ProposalResponse:
    """
    Resumes the governance graph after human review.

    Updates `hitl_approved` in the checkpointed state, then resumes
    execution from `human_review` → `execute_or_reject` → END.

    No on-chain transaction is submitted here. Approval only queues
    the unsigned tx in `pending_transactions` for steward signatures.
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    # Fetch current state to verify it's awaiting review
    try:
        snapshot = governance_graph.get_state(config)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Thread not found: {exc}")

    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if snapshot.values.get("hitl_approved") is not None:
        raise HTTPException(status_code=409, detail="Vote already cast for this proposal")

    if not req.approved and not req.rejection_reason:
        raise HTTPException(status_code=422, detail="rejection_reason required when approved=false")

    # Inject human decision into checkpointed state
    governance_graph.update_state(
        config,
        {
            "hitl_approved":    req.approved,
            "rejection_reason": req.rejection_reason,
        },
        as_node="human_review",
    )

    # Resume graph from human_review → execute_or_reject → END
    try:
        governance_graph.invoke(None, config=config)
    except Exception as exc:
        logger.error("governance_resume_error", error=str(exc), thread_id=req.thread_id)
        raise HTTPException(status_code=500, detail=f"Graph resume error: {exc}")

    snapshot = governance_graph.get_state(config)
    state    = snapshot.values

    # ── Phase 11: Embed decision as democratic precedent ─────────────────
    try:
        from backend.memory.pgvector_store import store_precedent

        proposal_desc = (state.get("proposal") or {}).get("description", "")
        store_precedent(
            source_agent="governance-agent-v1",
            decision_type="governance_vote",
            original_text=proposal_desc,
            vote_result="approved" if req.approved else "rejected",
            metadata={
                "thread_id": req.thread_id,
                "voter_did": req.voter_did,
            },
        )
    except Exception as prec_exc:
        logger.warning("precedent_store_failed", error=str(prec_exc))

    logger.info(
        "governance_vote_cast",
        thread_id=req.thread_id,
        voter=req.voter_did,
        approved=req.approved,
    )

    return ProposalResponse(
        thread_id=req.thread_id,
        status="approved" if req.approved else "rejected",
        safe_tx_draft=state.get("safe_tx_draft"),
        action_log=state.get("action_log", []),
    )
