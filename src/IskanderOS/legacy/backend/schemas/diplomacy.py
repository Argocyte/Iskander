"""
Iskander Diplomatic Embassy — Pydantic Schemas.

Models for the Foreign Reputation System (FRS), Ingestion Embassy,
Quarantine Sandbox, and Researcher-in-the-Loop (RITL) protocols.

DESIGN:
  - FRS models mirror the on-chain ForeignReputation.sol contract.
  - ExternalAsset extends KnowledgeAsset with quarantine metadata.
  - PeerReview models support the Socratic Cross-Examination dialectic.
  - All models participate in the Glass Box Protocol via AgentAction payloads.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Foreign Reputation System ────────────────────────────────────────────────

class ReputationTier(int, Enum):
    """Access tiers derived from the FRS on-chain score."""
    QUARANTINE   = 0  # Sandbox only — no federation access
    PROVISIONAL  = 1  # Read + limited write
    TRUSTED      = 2  # Full federation
    ALLIED       = 3  # Deep integration (curriculum sharing, joint research)


class SDCReputationProfile(BaseModel):
    """Python mirror of the ForeignReputation.sol SDCProfile struct."""
    sdc_did:           str = Field(..., description="W3C DID of the foreign SDC")
    sdc_id_hash:       str = Field(..., description="keccak256(sdc_did) as hex string")
    raw_score:         int = Field(ge=0, le=10000, description="Score in basis points before decay")
    decayed_score:     int = Field(ge=0, le=10000, description="Score after exponential decay")
    tier:              ReputationTier
    last_updated:      datetime
    force_quarantined: bool = False
    tx_count:          int = Field(ge=0, default=0)


class TransactionRecord(BaseModel):
    """A Valueflows EconomicEvent that anchors a reputation score change."""
    sdc_did:     str = Field(..., description="DID of the foreign SDC")
    score_delta: int = Field(ge=-500, le=500, description="Signed delta in basis points")
    tx_cid:      str = Field(..., description="IPFS CID of the Valueflows EconomicEvent")
    rationale:   str = Field(..., min_length=1)


# ── Quarantine Sandbox ───────────────────────────────────────────────────────

class QuarantineStatus(str, Enum):
    """Lifecycle states for external assets in the quarantine sandbox."""
    PENDING_REVIEW  = "PendingReview"    # Awaiting curator evaluation
    UNDER_REVIEW    = "UnderReview"      # Curator debate in progress
    ADMITTED        = "Admitted"          # Promoted to KnowledgeAsset (Active)
    REJECTED        = "Rejected"         # Not admitted — remains sandboxed
    EXPIRED         = "Expired"          # TTL exceeded without resolution


class ExternalAsset(BaseModel):
    """An ingested external knowledge asset held in the quarantine sandbox.

    External assets enter through the IngestionEmbassy and must pass
    curator review before being promoted to full KnowledgeAsset status.
    """
    quarantine_id:     UUID = Field(default_factory=uuid4)
    source_sdc_did:    str = Field(..., description="DID of the originating SDC")
    source_sdc_tier:   ReputationTier
    original_cid:      str = Field(..., description="CID from the source SDC")
    local_cid:         str | None = Field(default=None, description="CID after local pinning")
    title:             str = Field(..., min_length=1)
    description:       str | None = None
    status:            QuarantineStatus = QuarantineStatus.PENDING_REVIEW
    collision_report:  CollisionReport | None = None
    ingested_at:       datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at:       datetime | None = None
    promoted_asset_cid: str | None = Field(
        default=None,
        description="CID of the KnowledgeAsset created on admission",
    )


class CollisionReport(BaseModel):
    """Semantic collision detection report from the OntologyTranscoder.

    Identifies potential duplicates or conflicts with existing knowledge
    assets in the local commons.
    """
    collisions:       list[CollisionEntry] = Field(default_factory=list)
    collision_count:  int = 0
    checked_at:       datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CollisionEntry(BaseModel):
    """A single collision between an external asset and a local asset."""
    local_cid:        str = Field(..., description="CID of the existing local asset")
    local_title:      str
    similarity_score: float = Field(ge=0.0, le=1.0, description="Cosine similarity or Jaccard index")
    collision_type:   Literal["duplicate", "supersedes", "contradicts", "overlaps"]
    rationale:        str


# ── Researcher-in-the-Loop (RITL) ───────────────────────────────────────────

class ReviewVerdict(str, Enum):
    """Outcomes of a peer review round."""
    ACCEPT           = "accept"
    MINOR_REVISIONS  = "minor_revisions"
    MAJOR_REVISIONS  = "major_revisions"
    REJECT           = "reject"


class PeerReview(BaseModel):
    """A single peer review in the RITL dialectic.

    Each review is a structured assessment that feeds the Socratic
    Cross-Examination process. The agent_action field links to the
    Glass Box audit trail.
    """
    review_id:        UUID = Field(default_factory=uuid4)
    reviewer_id:      str = Field(..., description="Agent ID or DID of the reviewer")
    dimension:        Literal["Rigor", "Novelty", "Ethics", "Reproducibility"]
    verdict:          ReviewVerdict
    score:            int = Field(ge=0, le=100, description="0-100 quality score")
    strengths:        list[str] = Field(default_factory=list)
    weaknesses:       list[str] = Field(default_factory=list)
    questions:        list[str] = Field(
        default_factory=list,
        description="Socratic questions for cross-examination",
    )
    rationale:        str = Field(..., min_length=1)
    blind_mode:       bool = Field(default=False, description="True if reviewer identity is masked")
    agent_action:     dict[str, Any] = Field(default_factory=dict)


class SocraticExchange(BaseModel):
    """A question-response pair in the Socratic Cross-Examination."""
    question:         str = Field(..., min_length=1)
    asked_by:         str = Field(..., description="Agent ID of the questioner")
    response:         str | None = None
    responded_by:     str | None = None
    round_number:     int = Field(ge=1)


class ResearchSubmission(BaseModel):
    """A knowledge contribution submitted for RITL peer review."""
    submission_id:    UUID = Field(default_factory=uuid4)
    asset_cid:        str = Field(..., description="CID of the submitted knowledge asset")
    author_did:       str = Field(..., description="DID of the submitting author/agent")
    title:            str = Field(..., min_length=1)
    abstract:         str | None = None
    field_tags:       list[str] = Field(default_factory=list)
    submitted_at:     datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PeerReviewRound(BaseModel):
    """A complete round of peer reviews for a submission."""
    round_id:         UUID = Field(default_factory=uuid4)
    submission_id:    UUID
    round_number:     int = Field(ge=1)
    reviews:          list[PeerReview] = Field(default_factory=list)
    socratic_exchanges: list[SocraticExchange] = Field(default_factory=list)
    consensus:        ReviewVerdict | None = None
    blind_mode:       bool = False
    started_at:       datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at:     datetime | None = None


# ── API Request / Response Models ────────────────────────────────────────────

class RegisterSDCRequest(BaseModel):
    """Request body for POST /diplomacy/sdc/register."""
    sdc_did:       str = Field(..., min_length=1)
    initial_score: int = Field(ge=0, le=10000, default=1000)


class RegisterSDCResponse(BaseModel):
    """Response body for POST /diplomacy/sdc/register."""
    sdc_did:    str
    sdc_id_hash: str
    tier:       int
    score:      int


class RecordTransactionRequest(BaseModel):
    """Request body for POST /diplomacy/sdc/transaction."""
    sdc_did:     str = Field(..., min_length=1)
    score_delta: int = Field(ge=-500, le=500)
    tx_cid:      str = Field(..., min_length=1)
    rationale:   str = Field(..., min_length=1)


class IngestExternalAssetRequest(BaseModel):
    """Request body for POST /diplomacy/ingest."""
    source_sdc_did: str = Field(..., min_length=1)
    original_cid:   str = Field(..., min_length=1)
    title:          str = Field(..., min_length=1)
    description:    str | None = None
    data_base64:    str = Field(..., description="Base64-encoded content to pin locally")


class IngestExternalAssetResponse(BaseModel):
    """Response body for POST /diplomacy/ingest."""
    quarantine_id: str
    local_cid:     str
    source_tier:   int
    status:        str
    collision_count: int


class SubmitForReviewRequest(BaseModel):
    """Request body for POST /diplomacy/research/submit."""
    asset_cid:   str = Field(..., min_length=1)
    author_did:  str = Field(..., min_length=1)
    title:       str = Field(..., min_length=1)
    abstract:    str | None = None
    field_tags:  list[str] = Field(default_factory=list)
    blind_mode:  bool = Field(default=False, description="Enable ZK blind review")


class PeerReviewResponse(BaseModel):
    """Response body for peer review operations."""
    thread_id:     str
    submission_id: str
    round_number:  int
    status:        str
    reviews:       list[dict[str, Any]] = Field(default_factory=list)
    socratic_log:  list[dict[str, Any]] = Field(default_factory=list)
    consensus:     str | None = None
    action_log:    list[dict[str, Any]] = Field(default_factory=list)


# ── Credential Embassy (W3C VC → Internal Attestation) ────────────────────────

class VerifyCredentialRequest(BaseModel):
    """Request body for POST /diplomacy/credentials/verify."""
    credential_json: dict[str, Any] = Field(
        ..., description="Full W3C VC JSON document including proof section",
    )


class VerifyCredentialResponse(BaseModel):
    """Response body for POST /diplomacy/credentials/verify."""
    valid:                bool
    issuer_did:           str
    issuer_name:          str = ""
    key_fingerprint:      str = ""
    credential_type:      str = ""
    subject_role:         str = ""
    subject_institution:  str = ""
    error:                str | None = None
    warnings:             list[str] = Field(default_factory=list)


class IngestCredentialRequest(BaseModel):
    """Request body for POST /diplomacy/credentials/ingest.

    Full pipeline: verify VC → mint attestation → pin to Mesh Archive.
    """
    credential_json: dict[str, Any] = Field(
        ..., description="Full W3C VC JSON document including proof section",
    )
    holder_did: str = Field(
        ..., min_length=1, description="DID of the credential holder",
    )


class IngestCredentialResponse(BaseModel):
    """Response body for POST /diplomacy/credentials/ingest."""
    attestation_id:       str
    holder_did:           str
    issuer_did:           str
    credential_type:      str
    verified_role:        str
    verified_institution: str
    mesh_cid:             str
    causal_event_cid:     str
    zk_attestation_hash:  str
    status:               str = "Active"


class AttestationResponse(BaseModel):
    """Response body for GET /diplomacy/attestations/{attestation_id}."""
    attestation_id:       str
    holder_did:           str
    issuer_did:           str
    issuer_name:          str
    credential_type:      str
    verified_role:        str
    verified_institution: str
    status:               str
    created_at:           str
    tombstoned_at:        str | None = None
    mesh_cid:             str | None = None
    causal_event_cid:     str | None = None
    zk_attestation:       dict[str, Any] | None = None


class RevokeIssuerRequest(BaseModel):
    """Request body for POST /diplomacy/credentials/revoke-issuer."""
    key_fingerprint: str = Field(
        ..., min_length=1, description="Key fingerprint of the issuer to revoke",
    )
    rationale: str = Field(
        ..., min_length=1, description="Reason for revocation (pinned to audit log)",
    )


class RevokeIssuerResponse(BaseModel):
    """Response body for POST /diplomacy/credentials/revoke-issuer."""
    key_fingerprint:   str
    tombstoned_count:  int
    tombstoned_ids:    list[str] = Field(default_factory=list)
    rationale:         str


# Forward reference resolution
ExternalAsset.model_rebuild()
