"""
Governance Orchestrator — Pydantic schemas.

Covers:
  - ComplianceFactory (manifests, drafts, notarization)
  - PolicyEngine (governance manifest, rules, check results)
  - TxOrchestrator (Safe batch drafting, settlement, TTL)

DESIGN INVARIANT: Agents draft, humans sign.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# ComplianceFactory Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class FieldDefinition(BaseModel):
    """A single variable field within a ComplianceManifest template."""

    field_id: str = Field(..., description="Unique within manifest, e.g. 'company_name'")
    label: str = Field(..., description="Human-readable label, e.g. 'Registered Company Name'")
    data_source_path: str = Field(
        ...,
        description="Dot-path into Iskander state, e.g. 'treasury.pay_ratio'",
    )
    validation_regex: str | None = Field(
        default=None,
        description="Optional regex to validate the resolved value",
    )
    required: bool = Field(default=True)


class ComplianceManifest(BaseModel):
    """Jurisdiction-agnostic compliance template with diff-lock anchor."""

    template_id: str = Field(..., description="Unique ID, e.g. 'uk-hmrc-ct600'")
    version: int = Field(..., ge=1, description="Monotonically increasing version")
    jurisdiction: str = Field(..., description="ISO country code or '*' for universal")
    sector: str = Field(..., description="e.g. 'tax', 'planning', 'corporate'")
    title: str = Field(..., description="Human-readable name")
    boilerplate_hash: str = Field(
        default="",
        description="SHA-256 of static template text (diff-lock anchor)",
    )
    boilerplate_text: str = Field(
        default="",
        description="The static legal template text",
    )
    fields: list[FieldDefinition] = Field(default_factory=list)
    content_cid: str | None = Field(
        default=None,
        description="CID anchor after SovereignStorage registration",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Draft Document
# ═══════════════════════════════════════════════════════════════════════════════


class DraftStatus(str, Enum):
    """Lifecycle of a compliance draft document.

    Draft -> PendingReview -> Approved -> Notarized
                            \\-> Rejected (terminal, tombstone-only)
    """

    DRAFT = "Draft"
    PENDING_REVIEW = "PendingReview"
    APPROVED = "Approved"
    NOTARIZED = "Notarized"
    REJECTED = "Rejected"


# Valid transitions map (from -> set of valid targets)
VALID_DRAFT_TRANSITIONS: dict[DraftStatus, set[DraftStatus]] = {
    DraftStatus.DRAFT: {DraftStatus.PENDING_REVIEW},
    DraftStatus.PENDING_REVIEW: {DraftStatus.APPROVED, DraftStatus.REJECTED},
    DraftStatus.APPROVED: {DraftStatus.NOTARIZED},
    DraftStatus.NOTARIZED: set(),  # terminal
    DraftStatus.REJECTED: set(),  # terminal, tombstone-only
}


class DraftDocument(BaseModel):
    """A filled compliance document produced by the RegulatoryScribe."""

    draft_id: UUID = Field(default_factory=uuid4)
    manifest_id: str = Field(...)
    manifest_version: int = Field(..., ge=1)
    manifest_content_cid: str = Field(
        ..., description="Exact manifest version CID (provenance chain)"
    )
    filled_fields: dict[str, str] = Field(default_factory=dict)
    boilerplate_text: str = Field(default="", description="Static text copied from template")
    rendered_text: str = Field(default="", description="Final output with fields interpolated")
    status: DraftStatus = Field(default=DraftStatus.DRAFT)
    diff_lock_valid: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: datetime | None = Field(default=None)
    notarized_at: datetime | None = Field(default=None)
    document_hash: str | None = Field(
        default=None, description="SHA-256 of rendered_text (set at notarization)"
    )
    signature: str | None = Field(
        default=None, description="Node signature over document_hash"
    )
    mesh_cid: str | None = Field(
        default=None, description="CID after Mesh Archive pinning"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PolicyEngine Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class ConstraintType(str, Enum):
    """Types of policy constraints."""

    MAX_VALUE = "MaxValue"
    MIN_VALUE = "MinValue"
    REQUIRE_APPROVAL = "RequireApproval"
    DENY = "Deny"


class PolicyRule(BaseModel):
    """A single rule within the governance manifest."""

    rule_id: str = Field(..., description="e.g. 'max_pay_ratio'")
    description: str = Field(...)
    constraint_type: ConstraintType = Field(...)
    value: str = Field(..., description="Threshold or parameter value")
    applies_to: list[str] = Field(
        default_factory=list,
        description="Agent IDs this rule constrains. Empty = all agents.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extension metadata. Keys: _regulatory, _ambiguous, non_overridable")


class PolicyViolation(BaseModel):
    """A single policy violation detected by PolicyEngine."""

    rule_id: str
    description: str
    constraint_type: ConstraintType
    threshold: str
    actual_value: str | None = None
    message: str


class PolicyCheckResult(BaseModel):
    """Result of a PolicyEngine compliance check."""

    compliant: bool = Field(...)
    violations: list[PolicyViolation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_rules: int = Field(default=0)
    constitutional_checks_passed: bool = Field(default=True)


class GovernanceManifest(BaseModel):
    """The cooperative's governance-as-code manifest."""

    version: int = Field(..., ge=1)
    content_cid: str | None = Field(default=None)
    policies: list[PolicyRule] = Field(default_factory=list)
    constitutional_core: list[str] = Field(
        default_factory=list,
        description="ICA principle IDs (cannot be overridden by manifest updates)",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TxOrchestrator Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class TxStatus(str, Enum):
    """Lifecycle of a drafted transaction.

    Drafted -> Pending -> Executed -> Settled
    Drafted -> Stale (TTL expired)
    Drafted/Pending -> Cancelled (manual by steward)
    """

    DRAFTED = "Drafted"
    PENDING = "Pending"
    EXECUTED = "Executed"
    SETTLED = "Settled"
    STALE = "Stale"
    CANCELLED = "Cancelled"


# Valid transitions map
VALID_TX_TRANSITIONS: dict[TxStatus, set[TxStatus]] = {
    TxStatus.DRAFTED: {TxStatus.PENDING, TxStatus.STALE, TxStatus.CANCELLED},
    TxStatus.PENDING: {TxStatus.EXECUTED, TxStatus.STALE, TxStatus.CANCELLED},
    TxStatus.EXECUTED: {TxStatus.SETTLED},
    TxStatus.SETTLED: set(),  # terminal
    TxStatus.STALE: set(),  # terminal
    TxStatus.CANCELLED: set(),  # terminal
}


class SafeTxPayload(BaseModel):
    """Gnosis Safe transaction payload — compatible with Safe Transaction Service API.

    Mirrors the existing _build_safe_tx_draft() pattern from treasurer.py and
    governance_agent.py, including all fields required by the Safe UI.
    """

    to: str = Field(...)
    value: str = Field(default="0")
    data: str = Field(default="0x")
    operation: int = Field(default=0, description="0=CALL, 1=DELEGATECALL")
    safeTxGas: int = Field(default=0)
    baseGas: int = Field(default=0)
    gasPrice: str = Field(default="0")
    gasToken: str = Field(default="0x0000000000000000000000000000000000000000")
    refundReceiver: str = Field(default="0x0000000000000000000000000000000000000000")
    nonce: int | None = Field(default=None)
    # Iskander metadata extensions (prefixed with _ to avoid Safe API conflicts)
    _iskander_note: str = ""
    _iskander_payment_type: str = ""
    _iskander_mondragon_ratio: float | None = None


class DraftedTransaction(BaseModel):
    """A batch of Safe transactions drafted by the TxOrchestrator."""

    tx_id: UUID = Field(default_factory=uuid4)
    safe_address: str = Field(...)
    transactions: list[SafeTxPayload] = Field(default_factory=list)
    status: TxStatus = Field(default=TxStatus.DRAFTED)
    drafted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: datetime | None = Field(default=None)
    settled_at: datetime | None = Field(default=None)
    ttl_deadline: datetime = Field(...)
    on_chain_tx_hash: str | None = Field(default=None)
    rea_event_id: str | None = Field(default=None)
    policy_check_result: dict[str, Any] = Field(default_factory=dict)
    manifest_diff: str | None = Field(
        default=None,
        description="Human-readable diff of the governance rules that authorized this batch",
    )
    governance_manifest_cid: str | None = Field(
        default=None,
        description="CID of the GovernanceManifest that authorized this transaction",
    )
    requester_did: str | None = Field(default=None)


# ═══════════════════════════════════════════════════════════════════════════════
# API Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class PolicyCheckRequest(BaseModel):
    """Request to check an action against the PolicyEngine."""

    agent_id: str = Field(...)
    action_type: str = Field(..., description="e.g. 'payment', 'draft', 'mint'")
    params: dict[str, Any] = Field(default_factory=dict)


class PolicyCheckResponse(BaseModel):
    """Response from a PolicyEngine compliance check."""

    compliant: bool
    violations: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_rules: int = 0
    constitutional_checks_passed: bool = True


class DraftBatchRequest(BaseModel):
    """Request to draft a Safe batch transaction."""

    proposals: list[dict[str, Any]] = Field(
        ..., description="List of payment/action proposals"
    )
    requester_did: str = Field(...)


class DraftBatchResponse(BaseModel):
    """Response after drafting a Safe batch."""

    tx_id: str
    safe_address: str
    status: str
    transaction_count: int
    ttl_deadline: str
    policy_check: dict[str, Any]
    governance_manifest_cid: str | None = None


class SettleTransactionRequest(BaseModel):
    """Request to record on-chain settlement of a transaction."""

    tx_hash: str = Field(..., min_length=1)


class SettleTransactionResponse(BaseModel):
    """Response after recording settlement."""

    tx_id: str
    status: str
    tx_hash: str
    settled_at: str
    causal_event_cid: str | None = None


class OperationalComplianceViolation(Exception):
    """Raised when an agent action violates the current governance manifest.

    This is the core enforcement mechanism: if an agent tries to draft a payment
    that violates pay-ratio or spending-limit rules, this exception halts the
    pipeline with full violation details for the Glass Box trail.
    """

    def __init__(self, violations: list[PolicyViolation], message: str = ""):
        self.violations = violations
        self.message = message or f"Compliance violation: {len(violations)} rule(s) failed"
        super().__init__(self.message)
