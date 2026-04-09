"""
Iskander Knowledge Commons (IKC) — Pydantic Schemas.

Defines KnowledgeAsset, StatusTag, CuratorVote, and API request/response
models for the Decentralized University feature. All knowledge content is
pinned to the Mesh Archive (IPFS via SovereignStorage) and referenced by CID.

TOMBSTONE-ONLY INVARIANT: CIDs are never deleted. Status changes are
metadata-only writes (StatusTag) pinned alongside the original content.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Status Lifecycle ─────────────────────────────────────────────────────────

class KnowledgeAssetStatus(str, Enum):
    """Lifecycle states for a knowledge asset.

    Transitions:
        Active     → Legacy, Tombstoned, DeepFreeze
        Legacy     → Active, Tombstoned
        Tombstoned → (terminal — no transitions out)
        DeepFreeze → Active (only via StewardshipCouncil HITL)
    """
    ACTIVE      = "Active"
    LEGACY      = "Legacy"
    TOMBSTONED  = "Tombstoned"
    DEEP_FREEZE = "DeepFreeze"


# ── Core Models ──────────────────────────────────────────────────────────────

class KnowledgeAsset(BaseModel):
    """A content-addressed knowledge asset in the Iskander Knowledge Commons.

    Every asset is pinned to IPFS via SovereignStorage and referenced by its
    CID. The dependency_manifest lists CIDs this asset depends on (e.g., an
    agent strategy that imports a policy document).
    """
    asset_id:            UUID = Field(default_factory=uuid4)
    cid:                 str = Field(..., description="IPFS CID of the pinned content")
    author_did:          str = Field(..., description="W3C DID of the contributing author/agent")
    version:             int = Field(default=1, ge=1, description="Monotonically increasing version number")
    status:              KnowledgeAssetStatus = Field(
        default=KnowledgeAssetStatus.ACTIVE,
        description="Current lifecycle status",
    )
    dependency_manifest: list[str] = Field(
        default_factory=list,
        description="List of CIDs this asset depends on",
    )
    title:               str = Field(..., min_length=1, description="Human-readable title")
    description:         str | None = Field(default=None, description="Optional description")
    content_hash:        str | None = Field(
        default=None,
        description="SHA-256 of unencrypted content — integrity check independent of CID",
    )
    metadata_cid:        str | None = Field(
        default=None,
        description="CID of the latest StatusTag metadata blob",
    )
    created_at:          datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:          datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusTag(BaseModel):
    """Metadata-only record of a status change. Pinned to IPFS as JSON.

    TOMBSTONE-ONLY: This is the mechanism for 'changing' an asset's status.
    The original content CID is NEVER deleted — only this metadata tag is
    appended alongside it.
    """
    asset_cid:       str = Field(..., description="CID of the asset whose status changed")
    new_status:      KnowledgeAssetStatus
    previous_status: KnowledgeAssetStatus
    changed_by:      str = Field(..., description="DID of the actor who triggered the change")
    rationale:       str = Field(..., min_length=1, description="Why this status change was made")
    timestamp:       datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CuratorVote(BaseModel):
    """A single curator's assessment of a curation proposal.

    Each vote is wrapped in an AgentAction for Glass Box audit trail.
    """
    curator_id:   str = Field(..., description="Agent ID, e.g. 'efficiency-curator-v1'")
    dimension:    Literal["Efficiency", "Ethics", "Resilience"]
    vote:         Literal["approve", "reject", "abstain"]
    score:        int = Field(ge=0, le=100, description="0-100 confidence/quality score")
    rationale:    str = Field(..., min_length=1, description="Why the curator voted this way")
    agent_action: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized AgentAction envelope for Glass Box audit",
    )


# ── API Request / Response Models ────────────────────────────────────────────

class RegisterAssetRequest(BaseModel):
    """Request body for POST /knowledge/register."""
    data_base64:         str = Field(..., description="Base64-encoded content to pin")
    title:               str = Field(..., min_length=1)
    author_did:          str = Field(..., min_length=1)
    description:         str | None = None
    dependency_manifest: list[str] = Field(
        default_factory=list,
        description="CIDs this asset depends on (must all exist in registry)",
    )
    audience:            Literal["federation", "council", "node"] = "federation"


class RegisterAssetResponse(BaseModel):
    """Response body for POST /knowledge/register."""
    asset_id: str
    cid:      str
    version:  int
    status:   str


class CurationProposalRequest(BaseModel):
    """Request body for POST /knowledge/curate."""
    asset_cid:       str = Field(..., description="CID of the asset to curate")
    proposed_status: KnowledgeAssetStatus = Field(
        ..., description="Target status for the asset"
    )
    rationale:       str = Field(..., min_length=1, description="Why this change is proposed")


class CurationProposalResponse(BaseModel):
    """Response body for POST /knowledge/curate."""
    thread_id:        str
    status:           str = Field(..., description="Overall result: consensus_reached | escalated_to_council | rejected_downstream_deps | paused")
    votes:            list[dict[str, Any]] = Field(default_factory=list)
    consensus_status: str
    rationale_log:    list[str] = Field(default_factory=list)
    action_log:       list[dict[str, Any]] = Field(default_factory=list)


class CurationReviewRequest(BaseModel):
    """Request body for POST /knowledge/curate/review (HITL resume)."""
    thread_id: str = Field(..., description="Thread ID of the paused curator debate")
    approved:  bool = Field(..., description="Whether the StewardshipCouncil approves the change")
    reason:    str = Field(default="", description="Optional reason for approval/rejection")


class DependentsResponse(BaseModel):
    """Response body for GET /knowledge/dependents/{cid}."""
    cid:        str
    dependents: list[str] = Field(default_factory=list, description="CIDs of active assets depending on this CID")
    count:      int = 0
