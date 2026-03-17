"""
ipd_audit.py — Phase 18: API Router for the IPD Auditing System.

Endpoints:
  POST /ipd-audit/predict          — Pre-trade cooperation prediction.
  POST /ipd-audit/record-outcome   — Post-trade outcome recording.
  GET  /ipd-audit/reputation/{did} — Reputation profile for a node.
  GET  /ipd-audit/pairwise         — Pairwise cooperation history.
  POST /ipd-audit/attest           — Submit a peer attestation.
  POST /ipd-audit/request-audit    — Request an inter-node audit.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import AuthenticatedUser, get_current_user
from backend.agents.library.ipd_auditor import (
    predict_cooperation_for_partner,
    post_trade_graph,
)
from backend.config import settings
from backend.schemas.ipd_audit import (
    AuditRequestCreate,
    OutcomeRecordRequest,
    OutcomeRecordResponse,
    PairwiseHistory,
    PeerAttestationRequest,
    PredictionRequest,
    PredictionResponse,
    ReputationProfile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ipd-audit", tags=["ipd-audit"])


# ── POST /ipd-audit/predict ─────────────────────────────────────────────────


@router.post("/predict", response_model=PredictionResponse)
async def predict_cooperation(req: PredictionRequest) -> dict[str, Any]:
    """Pre-trade cooperation probability prediction.

    Uses Generous Tit-for-Tat strategy with weighted signal aggregation.
    Returns cooperation probability, recommended strategy, payoff matrix,
    forgiveness rate, and whether HITL review is required.
    """
    result = predict_cooperation_for_partner(
        partner_did=req.partner_did,
        is_meatspace=req.is_meatspace,
    )

    p_coop = result.get("cooperation_probability", settings.ipd_prior_cooperation)
    matrix = result.get("payoff_matrix", {})

    return {
        "partner_did": req.partner_did,
        "cooperation_probability": p_coop,
        "recommended_strategy": result.get("recommended_strategy", "cooperate"),
        "strategy_rationale": result.get("strategy_rationale", ""),
        "payoff_matrix": {
            "R": matrix.get("R", settings.ipd_payoff_r),
            "S": matrix.get("S", settings.ipd_payoff_s),
            "T": matrix.get("T", settings.ipd_payoff_t),
            "P": matrix.get("P", settings.ipd_payoff_p),
        },
        "expected_values": {
            "EV_cooperate": matrix.get("EV_cooperate", 0.0),
            "EV_defect": matrix.get("EV_defect", 0.0),
        },
        "forgiveness_rate": result.get("forgiveness_rate", settings.ipd_forgiveness_rate),
        "signals_used": {},  # Populated when DB queries are implemented.
        "requires_human_review": result.get("requires_human_review", False),
        "is_meatspace": req.is_meatspace,
        "risk_assessment": {
            "cooperation_floor": settings.ipd_cooperation_floor,
            "below_floor": p_coop < settings.ipd_cooperation_floor,
        },
    }


# ── POST /ipd-audit/record-outcome ──────────────────────────────────────────


@router.post("/record-outcome", response_model=OutcomeRecordResponse)
async def record_outcome(req: OutcomeRecordRequest) -> dict[str, Any]:
    """Record post-trade escrow outcome in the reputation graph.

    Classifies the outcome into cooperate/defect per party and updates
    the off-chain reputation tables. Does NOT modify on-chain trust scores.
    """
    return await record_outcome_internal(
        escrow_id=req.escrow_id,
        buyer_did=req.buyer_did,
        seller_did=req.seller_did,
        escrow_outcome=req.escrow_outcome,
        arbitration_outcome=req.arbitration_outcome,
        is_meatspace=req.is_meatspace,
    )


async def record_outcome_internal(
    escrow_id: str,
    buyer_did: str,
    seller_did: str,
    escrow_outcome: str,
    arbitration_outcome: str | None = None,
    is_meatspace: bool = False,
) -> dict[str, Any]:
    """Internal helper invoked by both the API endpoint and post-trade hooks.

    Runs the post-trade LangGraph to classify outcome and update reputation.
    """
    from backend.agents.library.ipd_auditor import (
        classify_escrow_outcome,
        update_reputation_graph,
        compute_updated_probability,
        broadcast_audit_summary,
    )

    # Build minimal state for post-trade graph.
    state: dict[str, Any] = {
        "messages": [],
        "agent_id": "ipd-auditor-agent-v1",
        "action_log": [],
        "error": None,
        "partner_did": seller_did,
        "audit_mode": "post_trade",
        "interaction_history": [],
        "global_history": None,
        "trust_score_trajectory": [],
        "federation_behavior": None,
        "ica_scores": None,
        "cooperation_probability": None,
        "payoff_matrix": None,
        "recommended_strategy": None,
        "strategy_rationale": None,
        "risk_assessment": None,
        "escrow_outcome": {
            "escrow_id": escrow_id,
            "buyer_did": buyer_did,
            "seller_did": seller_did,
            "escrow_outcome": escrow_outcome,
            "arbitration_outcome": arbitration_outcome,
        },
        "outcome_classification": None,
        "reputation_update": None,
        "audit_request": None,
        "audit_response": None,
        "ipd_report": None,
        "requires_human_token": False,
        "is_meatspace": is_meatspace,
        "peer_attestations": [],
    }

    # Run post-trade pipeline synchronously (no LLM calls, fast).
    state = classify_escrow_outcome(state)
    state = update_reputation_graph(state)
    state = compute_updated_probability(state)
    state = broadcast_audit_summary(state)

    classification = state.get("outcome_classification") or {}

    return {
        "escrow_id": escrow_id,
        "buyer_action": classification.get("buyer_action", "cooperate"),
        "seller_action": classification.get("seller_action", "cooperate"),
        "buyer_updated_reputation": None,  # Populated with real DB in production.
        "seller_updated_reputation": None,
        "message": (
            f"Trade outcome recorded: buyer={classification.get('buyer_action')}, "
            f"seller={classification.get('seller_action')}. "
            "Off-chain reputation graph updated. On-chain trust scores unchanged."
        ),
    }


# ── GET /ipd-audit/reputation/{did} ─────────────────────────────────────────


@router.get("/reputation/{node_did}", response_model=ReputationProfile)
async def get_reputation(node_did: str) -> dict[str, Any]:
    """Query the aggregated reputation profile for a cooperative node.

    STUB: Returns default values. Production: query reputation_scores table.
    """
    # STUB: In production, query reputation_scores WHERE node_did=$1.
    logger.info("STUB: Reputation query for %s", node_did[:20])
    return {
        "node_did": node_did,
        "total_interactions": 0,
        "cooperate_count": 0,
        "defect_count": 0,
        "cooperation_ratio": 0.0,
        "jury_participation_rate": 0.0,
        "audit_compliance_rate": 1.0,
        "is_meatspace": False,
        "peer_attestation_avg": 0.0,
    }


# ── GET /ipd-audit/pairwise ─────────────────────────────────────────────────


@router.get("/pairwise", response_model=PairwiseHistory)
async def get_pairwise(node_a: str, node_b: str) -> dict[str, Any]:
    """Query pairwise cooperation statistics between two nodes.

    STUB: Returns default values. Production: query pairwise_cooperation table.
    """
    logger.info("STUB: Pairwise query for %s <-> %s", node_a[:15], node_b[:15])
    return {
        "node_a": node_a,
        "node_b": node_b,
        "total_interactions": 0,
        "mutual_cooperate": 0,
        "a_defect_b_cooperate": 0,
        "b_defect_a_cooperate": 0,
        "mutual_defect": 0,
    }


# ── POST /ipd-audit/attest ──────────────────────────────────────────────────


@router.post("/attest", status_code=status.HTTP_201_CREATED)
async def submit_attestation(
    req: PeerAttestationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit a meatspace peer attestation for a trading partner.

    Attestations provide soft reputation signals for partners without
    on-chain presence. A bakery with excellent peer attestations scores
    equally against a DAO with on-chain history.

    STUB: Logs the attestation. Production: INSERT into peer_attestations.
    """
    logger.info(
        "STUB: Attestation from %s for %s (type=%s, score=%d)",
        req.attester_did[:15], req.subject_did[:15],
        req.attestation_type, req.score,
    )
    return {
        "attester_did": req.attester_did,
        "subject_did": req.subject_did,
        "attestation_type": req.attestation_type,
        "score": req.score,
        "recorded": True,
        "message": (
            "Peer attestation recorded. This meatspace evidence will be "
            "incorporated into future cooperation probability predictions."
        ),
    }


# ── POST /ipd-audit/request-audit ───────────────────────────────────────────


@router.post("/request-audit", status_code=status.HTTP_202_ACCEPTED)
async def request_audit(
    req: AuditRequestCreate,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Request an inter-node audit of a trading partner's reputation.

    Sends an iskander:AuditRequest ActivityPub activity to the target node.
    Refusing an audit incurs a soft reputation penalty only — no on-chain slash.

    STUB: Logs the request. Production: deliver via ArbitrationProtocol.
    """
    request_id = str(uuid4())
    logger.info(
        "STUB: Audit request %s for target %s (type=%s)",
        request_id, req.target_node_did[:20], req.audit_type,
    )
    return {
        "request_id": request_id,
        "target_node_did": req.target_node_did,
        "audit_type": req.audit_type,
        "status": "pending",
        "message": (
            "Audit request created. The target node will be notified via "
            "ActivityPub federation. Refusing incurs a soft reputation penalty only."
        ),
    }
