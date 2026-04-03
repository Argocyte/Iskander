"""
Genesis Boot Sequence — Pydantic schemas.

Covers:
  - GenesisMode, GovernanceTier, RegulatoryUpdateSeverity enums
  - ExtractedRule (template-guided bylaw extraction output)
  - MappingConfirmation (founder HITL sign-off per rule)
  - RegulatoryLayer (permanent jurisdictional floor)
  - RegulatoryUpdate (federation-pushed legislation changes)
  - FounderRegistration (pre-genesis member registration)
  - API request/response models
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class GenesisMode(str, Enum):
    SOLO_NODE = "solo_node"
    LEGACY_IMPORT = "legacy_import"
    NEW_FOUNDING = "new_founding"


class GovernanceTier(str, Enum):
    CONSTITUTIONAL = "Constitutional"
    OPERATIONAL = "Operational"
    REGULATORY = "Regulatory"


class RegulatoryUpdateSeverity(str, Enum):
    ADVISORY = "Advisory"
    MANDATORY = "Mandatory"
    URGENT = "Urgent"


class ExtractedRule(BaseModel):
    rule_id: str = Field(..., description="Unique rule identifier")
    source_text: str = Field(..., description="Original bylaw clause text")
    proposed_policy_rule: dict[str, Any] = Field(..., description="Serialised PolicyRule dict")
    confidence: float = Field(..., ge=0.0, le=1.0, description="LLM extraction confidence")
    is_ambiguous: bool = Field(default=False, description="True if confidence < 0.6")
    is_novel_field: bool = Field(default=False, description="True if rule doesn't match any skeleton slot")
    tier: GovernanceTier = Field(..., description="Governance tier assignment")
    confirmed: bool = Field(default=False, description="Human sign-off received")

    @model_validator(mode="after")
    def _set_ambiguous_from_confidence(self) -> ExtractedRule:
        if self.confidence < 0.6:
            self.is_ambiguous = True
        return self


class MappingConfirmation(BaseModel):
    rule_id: str
    confirmed_by_did: str
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    original_text: str = Field(..., description="Bylaw source text")
    code_representation: str = Field(..., description='e.g. "governance_manifest.json → voting.quorum = 0.5"')
    approved: bool
    tier_assignment: GovernanceTier


class RegulatoryLayer(BaseModel):
    jurisdiction: str = Field(..., description="ISO country code, e.g. 'GB', 'ES'")
    rules: list[dict[str, Any]] = Field(default_factory=list)
    source_documents: list[dict[str, Any]] = Field(default_factory=list)
    non_overridable: bool = Field(default=True)
    update_history: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _force_non_overridable(self) -> RegulatoryLayer:
        self.non_overridable = True
        return self


class RegulatoryUpdate(BaseModel):
    source_federation_did: str
    legislation_reference: str
    affected_rule_ids: list[str] = Field(default_factory=list)
    proposed_rules: list[dict[str, Any]] = Field(default_factory=list)
    severity: RegulatoryUpdateSeverity
    effective_date: datetime
    ingested_via: str = Field(..., description="CID of the ActivityPub message")


class FounderRegistration(BaseModel):
    did: str
    address: str = Field(..., description="EVM address for SBT + Safe")
    name: str = Field(..., description="Human-readable name")
    founder_token_hash: str = Field(..., description="bcrypt hash of the temporary founder token")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BootRequest(BaseModel):
    mode: GenesisMode


class FounderRegisterRequest(BaseModel):
    did: str
    address: str
    name: str


class FounderRegisterResponse(BaseModel):
    did: str
    address: str
    founder_token: str = Field(..., description="One-time secret — store securely, shown once")


class ModeSelectRequest(BaseModel):
    mode: GenesisMode


class BylawsUploadRequest(BaseModel):
    text: str
    skeleton_template_cid: str | None = Field(default=None)


class TemplateSelectRequest(BaseModel):
    template_cid: str


class RuleConfirmRequest(BaseModel):
    approved: bool


class TierAssignRequest(BaseModel):
    tier: GovernanceTier


class RatifyRequest(BaseModel):
    ratified: bool


class GenesisStatusResponse(BaseModel):
    status: str = Field(..., description="pre-genesis | in-progress | complete | recovery")
    mode: GenesisMode | None = None
    boot_phase: str | None = None
    founder_count: int = 0
    boot_complete: bool = False
