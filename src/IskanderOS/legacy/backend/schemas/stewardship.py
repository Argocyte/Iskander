"""
Phase 23: Pydantic schemas for the Stewardship Council & Delegation Ledger.

Request/response models for:
  - Impact Score computation and retrieval
  - Liquid delegation and revocation
  - Emergency veto filing
  - Council rationale submission (Glass Box Protocol)
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Impact Score ──────────────────────────────────────────────────────────────


class ComputeScoresRequest(BaseModel):
    """Trigger Impact Score computation for specified nodes (or all if empty)."""

    target_node_dids: list[str] = Field(
        default_factory=list,
        description=(
            "DIDs of nodes to score. Empty list = score all members."
        ),
    )


class ImpactScoreResponse(BaseModel):
    """Impact Score result for a single node."""

    node_did: str
    historical_contribution_value: float = 0.0
    ecosystem_total_value: float = 0.0
    ethical_audit_score: float = 0.0
    impact_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Normalised Impact Score: (contribution / total) * ethical_audit.",
    )
    is_eligible_steward: bool
    warning_message: str | None = Field(
        None,
        description="Anticipatory warning if score is near the eligibility threshold.",
    )


class ComputeScoresResponse(BaseModel):
    """Response from the StewardshipScorer agent."""

    thread_id: str
    status: str
    scores: list[ImpactScoreResponse] = []
    current_threshold: float | None = None
    proposed_threshold: float | None = None
    threshold_rationale: str | None = None
    action_log: list[dict[str, Any]] = []
    error: str | None = None


# ── Delegation ────────────────────────────────────────────────────────────────


class DelegationRequest(BaseModel):
    """Submit a liquid delegation of gSBT weight to a steward."""

    steward_address: str = Field(
        ..., description="Ethereum address of the steward to delegate to.",
    )


class DelegationResponse(BaseModel):
    """Result of a delegation or revocation operation."""

    status: str = Field(
        ..., description="One of: delegated, revoked, failed.",
    )
    tx_hash: str | None = Field(
        None, description="On-chain transaction hash (None if stubbed).",
    )
    message: str = ""


class VotingWeightResponse(BaseModel):
    """On-chain voting weight for a node."""

    address: str
    self_weight: int
    received_delegations: int
    total_weight: int


# ── Emergency Veto ────────────────────────────────────────────────────────────


class VetoRequest(BaseModel):
    """File an emergency veto against a Council decision."""

    proposal_id: str = Field(
        ..., description="ID of the proposal being vetoed.",
    )
    rationale_ipfs_cid: str = Field(
        ..., description="IPFS CID of the Glass Box rationale document.",
    )
    cited_principles: list[str] = Field(
        default_factory=list,
        description="ICA Cooperative Principles cited as violated (e.g., ['P1', 'P5']).",
    )


class VetoResponse(BaseModel):
    """Result of an emergency veto filing."""

    veto_id: str
    status: str
    tx_hash: str | None = None
    message: str = ""


# ── Council Rationale (Glass Box Protocol) ────────────────────────────────────


class CouncilRationaleRequest(BaseModel):
    """Submit the rationale for a cross-node Council decision."""

    decision_type: str = Field(
        ..., description="Type of decision (e.g., 'resource_allocation', 'policy_change').",
    )
    description: str = Field(
        ..., min_length=1, description="Human-readable description of the decision.",
    )
    rationale_ipfs_cid: str = Field(
        ..., description="IPFS CID of the full rationale document.",
    )
    ica_principles: list[str] = Field(
        default_factory=list,
        description="ICA Cooperative Principles this decision supports.",
    )


class CouncilRationaleResponse(BaseModel):
    """Confirmation of a recorded Council rationale."""

    rationale_id: str
    status: str = "recorded"
    message: str = ""


# ── Stewardship Summary ──────────────────────────────────────────────────────


class EligibleSteward(BaseModel):
    """Summary of an eligible steward."""

    node_did: str
    impact_score: float
    received_delegations: int = 0


class StewardshipSummaryResponse(BaseModel):
    """Overview of the Stewardship Council state."""

    eligible_stewards: list[EligibleSteward] = []
    current_threshold: float
    ecosystem_total_value: float = 0.0


# ── Threshold Review (HITL) ──────────────────────────────────────────────────


class ThresholdReviewRequest(BaseModel):
    """Approve or reject a proposed threshold change."""

    thread_id: str
    approved: bool
    reason: str = ""
