"""
/steward — DisCO Contributory Accounting v2 (Care Work + Circuit Breaker).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.library.steward import steward_v2_graph
from backend.auth.dependencies import AuthenticatedUser, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/steward", tags=["steward"])


# ── Request / Response schemas ────────────────────────────────────────────────


class ContributionRequest(BaseModel):
    member_did: str = Field(..., description="Member's DID or Ethereum address.")
    description: str = Field(..., min_length=1, description="Description of the contribution.")
    hours: float = Field(..., ge=0, description="Base hours worked.")
    value_tokens: float = Field(0, ge=0, description="Optional token value.")
    ipfs_cid: str | None = None


class ContributionResponse(BaseModel):
    thread_id: str
    status: str
    classified_stream: str | None = None
    care_score: float | None = None
    ledger_entry: dict[str, Any] | None = None
    conflict_resolution: dict[str, Any] | None = None
    action_log: list[dict[str, Any]] = []
    error: str | None = None


class ReviewRequest(BaseModel):
    thread_id: str
    approved: bool
    reason: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/contribute", response_model=ContributionResponse)
async def log_contribution(
    req: ContributionRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Log a member contribution through the Steward v2 pipeline.

    If the circuit breaker fires, the response status will be
    ``pending_human_review`` and the contribution is held until approved.
    """
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "steward-agent-v2",
        "action_log": [],
        "error": None,
        "raw_contribution": req.model_dump(),
        "classified_stream": None,
        "care_score": None,
        "conflict_resolution": None,
        "ledger_entry": None,
        "requires_human_token": False,
    }

    try:
        steward_v2_graph.invoke(initial_state, config=config)
        snapshot = steward_v2_graph.get_state(config)
        state = snapshot.values
    except Exception as exc:
        logger.exception("Steward v2 agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    # If circuit breaker fired, graph is paused at human_review.
    if state.get("conflict_resolution"):
        return ContributionResponse(
            thread_id=thread_id,
            status="pending_human_review",
            classified_stream=state.get("classified_stream"),
            care_score=state.get("care_score"),
            conflict_resolution=state.get("conflict_resolution"),
            action_log=state.get("action_log", []),
        )

    return ContributionResponse(
        thread_id=thread_id,
        status="recorded",
        classified_stream=state.get("classified_stream"),
        care_score=state.get("care_score"),
        ledger_entry=state.get("ledger_entry"),
        action_log=state.get("action_log", []),
    )


@router.post("/contribute/review", response_model=ContributionResponse)
async def review_contribution(
    req: ReviewRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Approve/reject a circuit-breaker-held contribution."""
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        snapshot = steward_v2_graph.get_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Thread {req.thread_id} not found.")

    if not req.approved:
        return ContributionResponse(
            thread_id=req.thread_id,
            status="rejected",
            conflict_resolution=snapshot.values.get("conflict_resolution"),
            action_log=snapshot.values.get("action_log", []),
        )

    # Resume graph past human_review → write_ledger_entry.
    steward_v2_graph.update_state(
        config,
        {"requires_human_token": False},
        as_node="human_review",
    )
    steward_v2_graph.invoke(None, config=config)

    updated = steward_v2_graph.get_state(config).values
    return ContributionResponse(
        thread_id=req.thread_id,
        status="recorded",
        classified_stream=updated.get("classified_stream"),
        care_score=updated.get("care_score"),
        ledger_entry=updated.get("ledger_entry"),
        action_log=updated.get("action_log", []),
    )
