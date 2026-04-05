"""
/stewardship — Stewardship Council & Delegation Ledger (Phase 23).

Endpoints for Impact Score computation, liquid delegation, emergency veto,
and Council rationale submission (Glass Box Protocol compliance).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.agents.library.stewardship_scorer import stewardship_scorer_graph
from backend.api.hitl_rate_limiter import HITLRateLimiter
from backend.auth.dependencies import AuthenticatedUser, require_role
from backend.config import settings
from backend.schemas.stewardship import (
    ComputeScoresRequest,
    ComputeScoresResponse,
    CouncilRationaleRequest,
    CouncilRationaleResponse,
    DelegationRequest,
    DelegationResponse,
    EligibleSteward,
    ImpactScoreResponse,
    StewardshipSummaryResponse,
    ThresholdReviewRequest,
    VetoRequest,
    VetoResponse,
    VotingWeightResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stewardship", tags=["stewardship"])


# ── Score Computation ────────────────────────────────────────────────────────


@router.post("/compute-scores", response_model=ComputeScoresResponse)
async def compute_scores(
    req: ComputeScoresRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Trigger the StewardshipScorer agent to compute Impact Scores.

    If a threshold change is proposed, the response status will be
    ``pending_threshold_review`` and the scores are held until approved.
    """
    await HITLRateLimiter.get_instance().check(user.address, "/stewardship/compute-scores")
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "stewardship-scorer-v1",
        "action_log": [],
        "error": None,
        "target_nodes": req.target_node_dids,
        "contribution_aggregates": [],
        "ecosystem_total_value": None,
        "ethical_audit_results": [],
        "impact_scores": [],
        "current_threshold": settings.steward_threshold_default,
        "proposed_threshold": None,
        "threshold_rationale": None,
        "chain_update_result": None,
        "anticipatory_warnings": [],
        "requires_human_token": False,
    }

    try:
        stewardship_scorer_graph.invoke(initial_state, config=config)
        snapshot = stewardship_scorer_graph.get_state(config)
        state = snapshot.values
    except Exception as exc:
        logger.exception("StewardshipScorer agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    # Build response scores.
    scores = [
        ImpactScoreResponse(
            node_did=s.get("node_did", ""),
            historical_contribution_value=s.get("historical_contribution_value", 0.0),
            ecosystem_total_value=state.get("ecosystem_total_value", 0.0),
            ethical_audit_score=s.get("ethical_audit_score", 0.0),
            impact_score=s.get("impact_score", 0.0),
            is_eligible_steward=s.get("is_eligible_steward", False),
            warning_message=s.get("warning_message"),
        )
        for s in state.get("impact_scores", [])
    ]

    # Determine status based on HITL state.
    if state.get("requires_human_token"):
        status = "pending_threshold_review"
    else:
        status = "completed"

    return ComputeScoresResponse(
        thread_id=thread_id,
        status=status,
        scores=scores,
        current_threshold=state.get("current_threshold"),
        proposed_threshold=state.get("proposed_threshold"),
        threshold_rationale=state.get("threshold_rationale"),
        action_log=state.get("action_log", []),
    )


@router.get("/scores", response_model=list[ImpactScoreResponse])
async def list_scores(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Retrieve current Impact Scores from the database.

    STUB: In production, queries the impact_scores table via asyncpg.
    """
    # STUB: Return empty list pending DB integration.
    # SELECT * FROM impact_scores ORDER BY impact_score DESC
    return []


@router.get("/scores/{node_did}", response_model=ImpactScoreResponse)
async def get_score(
    node_did: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Retrieve the Impact Score for a single node.

    STUB: In production, queries impact_scores WHERE node_did = $1.
    """
    # STUB: Return 404 pending DB integration.
    raise HTTPException(status_code=404, detail=f"Score for {node_did} not found.")


# ── Delegation ───────────────────────────────────────────────────────────────


@router.post("/delegate", response_model=DelegationResponse)
async def delegate(
    req: DelegationRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Submit a liquid delegation of gSBT weight to a steward.

    STUB: In production, builds and submits an on-chain delegate() transaction
    via web3.py to the StewardshipLedger contract.
    """
    # STUB: Validate steward eligibility off-chain before submitting.
    # In production:
    #   w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
    #   contract = w3.eth.contract(address=settings.stewardship_ledger_address, abi=ABI)
    #   tx = contract.functions.delegate(req.steward_address).build_transaction({...})
    return DelegationResponse(
        status="delegated",
        tx_hash=None,
        message=(
            f"STUB: Delegation to {req.steward_address} drafted. "
            "Pending oracle integration for on-chain submission."
        ),
    )


@router.post("/revoke", response_model=DelegationResponse)
async def revoke(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Revoke delegation, returning gSBT weight to self.

    STUB: In production, calls StewardshipLedger.revoke() on-chain.
    """
    return DelegationResponse(
        status="revoked",
        tx_hash=None,
        message="STUB: Revocation drafted. Pending on-chain submission.",
    )


@router.get("/voting-weight/{address}", response_model=VotingWeightResponse)
async def get_voting_weight(
    address: str,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Read on-chain voting weight for a node.

    STUB: In production, calls StewardshipLedger.getVotingWeight(address) via web3.py.
    """
    return VotingWeightResponse(
        address=address,
        self_weight=1,
        received_delegations=0,
        total_weight=1,
    )


# ── Emergency Veto ───────────────────────────────────────────────────────────


@router.post("/veto", response_model=VetoResponse)
async def file_veto(
    req: VetoRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """File an emergency veto against a Council decision.

    Any member can veto by providing a Glass Box rationale citing ICA
    Principle violations. The veto is recorded on-chain and routed to the
    cooperative for review.

    STUB: In production, calls StewardshipLedger.emergencyVeto() on-chain
    and inserts into the veto_records table.
    """
    veto_id = str(uuid4())

    # STUB: Insert into veto_records table.
    # INSERT INTO veto_records (proposal_id, vetoer_did, vetoer_address,
    #     rationale_ipfs_cid, cited_principles, status)
    # VALUES ($1, $2, $3, $4, $5, 'filed')

    return VetoResponse(
        veto_id=veto_id,
        status="filed",
        tx_hash=None,
        message=(
            f"STUB: Emergency veto filed for proposal {req.proposal_id}. "
            f"Rationale: {req.rationale_ipfs_cid}. "
            f"Cited principles: {req.cited_principles}. "
            "Pending on-chain submission."
        ),
    )


# ── Council Rationale (Glass Box Protocol) ───────────────────────────────────


@router.post("/rationale", response_model=CouncilRationaleResponse)
async def submit_rationale(
    req: CouncilRationaleRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Submit the rationale for a cross-node Council decision.

    Required for Glass Box Protocol compliance — every Council decision
    must have an auditable rationale document stored on IPFS.

    STUB: In production, inserts into council_rationale table.
    """
    rationale_id = str(uuid4())

    # STUB: Insert into council_rationale table.
    # INSERT INTO council_rationale (decision_type, description,
    #     rationale_ipfs_cid, submitted_by, ica_principles)
    # VALUES ($1, $2, $3, $4, $5)

    return CouncilRationaleResponse(
        rationale_id=rationale_id,
        status="recorded",
        message=(
            f"Council rationale recorded for {req.decision_type}: "
            f"{req.rationale_ipfs_cid}."
        ),
    )


# ── Eligible Stewards ───────────────────────────────────────────────────────


@router.get("/eligible-stewards", response_model=StewardshipSummaryResponse)
async def list_eligible_stewards(
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """List all nodes currently above the steward threshold.

    STUB: In production, queries impact_scores WHERE is_eligible_steward = TRUE.
    """
    # STUB: Return empty summary pending DB integration.
    return StewardshipSummaryResponse(
        eligible_stewards=[],
        current_threshold=settings.steward_threshold_default,
        ecosystem_total_value=0.0,
    )


# ── Threshold Review (HITL) ─────────────────────────────────────────────────


@router.post("/threshold/review", response_model=ComputeScoresResponse)
async def review_threshold(
    req: ThresholdReviewRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Approve or reject a proposed steward threshold change.

    Resumes the StewardshipScorer graph past the HITL breakpoint.
    """
    await HITLRateLimiter.get_instance().check(user.address, "/stewardship/threshold/review")
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        snapshot = stewardship_scorer_graph.get_state(config)
    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Thread {req.thread_id} not found."
        )

    if not req.approved:
        state = snapshot.values
        return ComputeScoresResponse(
            thread_id=req.thread_id,
            status="threshold_rejected",
            scores=[
                ImpactScoreResponse(
                    node_did=s.get("node_did", ""),
                    historical_contribution_value=s.get("historical_contribution_value", 0.0),
                    ecosystem_total_value=state.get("ecosystem_total_value", 0.0),
                    ethical_audit_score=s.get("ethical_audit_score", 0.0),
                    impact_score=s.get("impact_score", 0.0),
                    is_eligible_steward=s.get("is_eligible_steward", False),
                    warning_message=s.get("warning_message"),
                )
                for s in state.get("impact_scores", [])
            ],
            current_threshold=state.get("current_threshold"),
            proposed_threshold=state.get("proposed_threshold"),
            threshold_rationale=f"Rejected: {req.reason}",
            action_log=state.get("action_log", []),
        )

    # Resume graph past HITL → push_scores_to_chain.
    stewardship_scorer_graph.update_state(
        config,
        {"requires_human_token": False},
        as_node="human_review_threshold",
    )
    stewardship_scorer_graph.invoke(None, config=config)

    updated = stewardship_scorer_graph.get_state(config).values
    return ComputeScoresResponse(
        thread_id=req.thread_id,
        status="completed",
        scores=[
            ImpactScoreResponse(
                node_did=s.get("node_did", ""),
                historical_contribution_value=s.get("historical_contribution_value", 0.0),
                ecosystem_total_value=updated.get("ecosystem_total_value", 0.0),
                ethical_audit_score=s.get("ethical_audit_score", 0.0),
                impact_score=s.get("impact_score", 0.0),
                is_eligible_steward=s.get("is_eligible_steward", False),
                warning_message=s.get("warning_message"),
            )
            for s in updated.get("impact_scores", [])
        ],
        current_threshold=updated.get("current_threshold"),
        proposed_threshold=updated.get("proposed_threshold"),
        threshold_rationale=updated.get("threshold_rationale"),
        action_log=updated.get("action_log", []),
    )
