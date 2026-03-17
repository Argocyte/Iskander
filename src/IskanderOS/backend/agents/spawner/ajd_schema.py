"""
Agent Job Description (AJD) — the "Policy Card" that governs a custom agent.

When a cooperative wants to hire a new AI agent, they fill out this
machine-readable job description specifying the agent's permissions,
budget limits, and Web3 multi-sig constraints.  The AJD must be
democratically approved before the agent is deployed.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from backend.schemas.glass_box import EthicalImpactLevel


class AJDPermission(str, Enum):
    """Granular permission flags for spawned agents.

    Each permission maps to a category of side-effects the agent may
    produce.  The spawner enforces these at compile time.
    """

    READ_ONLY = "read_only"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    WEB3_DRAFT = "web3_draft"
    FEDERATION_BROADCAST = "federation_broadcast"
    CONTAINER_DEPLOY = "container_deploy"  # Phase 13: Docker create/start/stop/remove.


class AJDSpec(BaseModel):
    """Machine-readable job description for a cooperatively-hired AI agent.

    This is the "Policy Card" that bounds the agent's behavior.  It is
    stored in the ``agent_job_descriptions`` Postgres table after democratic
    approval.

    Legal note: An AJD is an operational policy instrument, not a legal
    contract.  The cooperative's legal wrapper governs liability.
    """

    id: UUID = Field(default_factory=uuid4)
    agent_id: str = Field(
        ...,
        min_length=3,
        description="Unique identifier for the agent (e.g., 'logistics-agent-v1').",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human-friendly name for the agent.",
    )
    description: str = Field(
        ...,
        min_length=10,
        description="What this agent does and why the cooperative needs it.",
    )
    created_by: str = Field(
        ...,
        description="DID or identifier of the member who proposed this agent.",
    )

    # ── Permissions & constraints ─────────────────────────────────────────
    permissions: list[AJDPermission] = Field(
        default=[AJDPermission.READ_ONLY],
        description="Allowed action categories.",
    )
    budget_limit_wei: int = Field(
        default=0,
        ge=0,
        description="Max wei the agent may propose per transaction (0 = no treasury access).",
    )
    budget_period: Literal["daily", "weekly", "monthly"] = Field(
        default="monthly",
        description="Budget limit reset period.",
    )
    multisig_threshold: int = Field(
        default=1,
        ge=1,
        description="M-of-N human signatures required for this agent's Web3 actions.",
    )
    ethical_ceiling: EthicalImpactLevel = Field(
        default=EthicalImpactLevel.MEDIUM,
        description=(
            "Maximum ethical_impact_score tier this agent may self-authorize.  "
            "Actions above this ceiling auto-set requires_human_token=true."
        ),
    )

    # ── Model targeting (Phase 21) ─────────────────────────────────────────
    target_model: str | None = Field(
        default=None,
        description=(
            "Override the global ollama_model for this agent (e.g., 'llama3.2:3b', "
            "'qwen2.5:7b'). If None, the agent uses the cooperative's global default. "
            "The hardware profiler validates compatibility before deployment."
        ),
    )

    # ── Graph definition ──────────────────────────────────────────────────
    node_sequence: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered list of node-type strings from the node registry.  "
            "The spawner compiles these into a LangGraph at deploy time."
        ),
    )
    prompt_file: str | None = Field(
        default=None,
        description="Path to a custom prompt .txt file (relative to agents/library/).",
    )


class AJDVote(BaseModel):
    """A single member's vote on an AJD proposal."""

    ajd_id: UUID
    voter_did: str
    approved: bool
    reason: str = ""


class AJDStatus(BaseModel):
    """Current status of an AJD in the approval pipeline."""

    ajd_id: UUID
    agent_id: str
    name: str
    status: str  # proposed | approved | active | suspended | revoked
    votes_for: int = 0
    votes_against: int = 0
    quorum_required: int = 1
