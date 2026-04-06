# backend/schemas/deliberation.py
"""
deliberation.py — Pydantic schemas for the Iskander Native Deliberation System.

Mirrors Loomio's data model: SubGroups → Threads → Comments → Proposals
→ Stances → Outcomes → Tasks.

All IDs are string UUIDs (matching asyncpg row UUID columns).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProcessType(str, Enum):
    """Nine Loomio-compatible decision processes and poll types."""
    SENSE_CHECK = "sense_check"
    ADVICE      = "advice"
    CONSENT     = "consent"
    CONSENSUS   = "consensus"
    CHOOSE      = "choose"
    SCORE       = "score"
    ALLOCATE    = "allocate"
    RANK        = "rank"
    TIME_POLL   = "time_poll"


class StanceOption(str, Enum):
    """Options for proposal-type polls (Consent, Consensus, Sense Check, Advice)."""
    AGREE    = "agree"
    ABSTAIN  = "abstain"
    DISAGREE = "disagree"
    BLOCK    = "block"   # only valid on consent proposals


class ThreadStatus(str, Enum):
    OPEN   = "open"
    CLOSED = "closed"
    PINNED = "pinned"


class ProposalStatus(str, Enum):
    OPEN      = "open"
    CLOSED    = "closed"
    WITHDRAWN = "withdrawn"


class DecisionType(str, Enum):
    PASSED    = "passed"
    REJECTED  = "rejected"
    WITHDRAWN = "withdrawn"
    NO_QUORUM = "no_quorum"


class MemberRole(str, Enum):
    MEMBER      = "member"
    COORDINATOR = "coordinator"


# ── SubGroup schemas ──────────────────────────────────────────────────────────

class SubGroupCreate(BaseModel):
    slug:        str  = Field(..., min_length=2, max_length=80, pattern=r'^[a-z0-9\-]+$')
    name:        str  = Field(..., min_length=1, max_length=120)
    description: str | None = None
    created_by:  str  = Field(..., description="Creator member DID")


class SubGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          str
    slug:        str
    name:        str
    description: str | None
    created_by:  str
    created_at:  datetime


class SubGroupMemberAdd(BaseModel):
    member_did: str
    role:       MemberRole = MemberRole.MEMBER


class SubGroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sub_group_id: str
    member_did:   str
    role:         str
    joined_at:    datetime


# ── Thread schemas ─────────────────────────────────────────────────────────────

class ThreadCreateRequest(BaseModel):
    title:        str       = Field(..., min_length=1, max_length=200)
    context:      str       = Field(default="", description="Rich-text thread body")
    author_did:   str       = Field(..., description="Creator member DID")
    sub_group_id: str | None = Field(default=None, description="Scope to working group (None = whole coop)")
    tags:         list[str] = Field(default_factory=list)


class ThreadUpdateRequest(BaseModel):
    title:   str | None = Field(default=None, max_length=200)
    context: str | None = None
    status:  ThreadStatus | None = None
    tags:    list[str] | None = None


class ThreadSummary(BaseModel):
    """Lightweight model for thread list view."""
    model_config = ConfigDict(from_attributes=True)
    id:                  str
    title:               str
    author_did:          str
    status:              str
    tags:                list[str]
    open_proposal_count: int
    comment_count:       int
    last_activity:       datetime
    sub_group_id:        str | None = None


class ThreadDetail(BaseModel):
    """Full thread view including nested data."""
    model_config = ConfigDict(from_attributes=True)
    id:               str
    title:            str
    context:          str
    author_did:       str
    sub_group_id:     str | None
    tags:             list[str]
    status:           str
    ai_context_draft: str | None
    created_at:       datetime
    updated_at:       datetime
    comments:         list[CommentResponse]         = Field(default_factory=list)
    proposals:        list[ProposalSummary]         = Field(default_factory=list)
    tasks:            list[TaskResponse]            = Field(default_factory=list)


# ── Comment schemas ───────────────────────────────────────────────────────────

class CommentCreateRequest(BaseModel):
    thread_id:  str
    author_did: str
    body:       str = Field(..., min_length=1)
    parent_id:  str | None = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:         str
    thread_id:  str
    author_did: str
    parent_id:  str | None
    body:       str
    edited_at:  datetime | None
    created_at: datetime
    reactions:  dict[str, int] = Field(default_factory=dict)  # emoji → count


class ReactionToggleRequest(BaseModel):
    member_did: str
    emoji:      str = Field(..., min_length=1, max_length=8)


# ── Proposal schemas ──────────────────────────────────────────────────────────

class ProposalCreateRequest(BaseModel):
    thread_id:    str
    title:        str       = Field(..., min_length=1, max_length=200)
    body:         str       = Field(..., min_length=1)
    process_type: ProcessType
    author_did:   str
    options:      list[str] | None = Field(
        default=None,
        description="Options for choose/score/allocate/rank/time_poll types"
    )
    quorum_pct:  int = Field(default=0, ge=0, le=100)
    closing_at:  datetime | None = None


class ProposalSummary(BaseModel):
    """Lightweight model for embedding proposals in thread list."""
    model_config = ConfigDict(from_attributes=True)
    id:           str
    title:        str
    process_type: str
    status:       str
    closing_at:   datetime | None
    stance_count: int = 0


class ProposalTally(BaseModel):
    """Live vote count — computed, not stored."""
    agree:    int = 0
    abstain:  int = 0
    disagree: int = 0
    block:    int = 0
    total:    int = 0
    options:  dict[str, int] = Field(default_factory=dict)  # for poll types


class ProposalDetail(BaseModel):
    """Full proposal view including stances and live tally."""
    model_config = ConfigDict(from_attributes=True)
    id:           str
    thread_id:    str
    title:        str
    body:         str
    process_type: str
    options:      list[str] | None
    quorum_pct:   int
    closing_at:   datetime | None
    status:       str
    ai_draft:     str | None
    author_did:   str
    created_at:   datetime
    closed_at:    datetime | None
    stances:      list[StanceResponse]  = Field(default_factory=list)
    tally:        ProposalTally | None  = None
    outcome:      OutcomeResponse | None = None


# ── Stance schemas ─────────────────────────────────────────────────────────────

class StanceCreateRequest(BaseModel):
    member_did:  str
    stance:      str  = Field(..., description="agree|abstain|disagree|block or option key")
    reason:      str | None = None
    score:       int | None = Field(default=None, ge=0, le=100)
    rank_order:  list[dict[str, Any]] | None = None


class StanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          str
    proposal_id: str
    member_did:  str
    stance:      str
    reason:      str | None
    score:       int | None
    rank_order:  list[dict[str, Any]] | None
    created_at:  datetime
    updated_at:  datetime


# ── Outcome schemas ────────────────────────────────────────────────────────────

class OutcomeCreateRequest(BaseModel):
    statement:     str = Field(..., min_length=1)
    decision_type: DecisionType
    stated_by:     str  = Field(..., description="Member DID confirming the outcome")


class OutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:            str
    proposal_id:   str
    statement:     str
    decision_type: str
    precedent_id:  str | None
    ai_draft:      str | None
    stated_by:     str
    created_at:    datetime


# ── Task schemas ──────────────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    thread_id:    str
    title:        str = Field(..., min_length=1, max_length=200)
    created_by:   str
    assignee_did: str | None = None
    due_date:     str | None = Field(default=None, description="ISO date string YYYY-MM-DD")
    outcome_id:   str | None = None


class TaskUpdateRequest(BaseModel):
    done:         bool | None = None
    assignee_did: str | None = None
    due_date:     str | None = None
    title:        str | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:           str
    thread_id:    str
    outcome_id:   str | None
    title:        str
    assignee_did: str | None
    due_date:     str | None
    done:         bool
    done_at:      datetime | None
    created_by:   str
    created_at:   datetime
