"""
Glass Box Protocol — Pydantic schemas.

Every agent action MUST be wrapped in AgentAction, forcing explicit
rationale and ethical impact disclosure before any side-effect executes.
This creates an auditable trail in the `agent_actions` Postgres table.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EthicalImpactLevel(str, Enum):
    LOW    = "low"     # Informational / read-only
    MEDIUM = "medium"  # Writes to internal ledger only
    HIGH   = "high"    # Triggers Web3 tx draft or external federation message


class AgentAction(BaseModel):
    """
    Mandatory envelope for every agent-initiated action.
    Stored verbatim in agent_actions table; never truncated.
    """
    action_id:      UUID              = Field(default_factory=uuid4)
    agent_id:       str               = Field(..., description="Identifier of the emitting agent, e.g. 'steward-agent-v1'")
    action:         str               = Field(..., description="Short imperative description of the action being taken")
    rationale:      str               = Field(..., description="Why the agent chose this action given its current context")
    ethical_impact: EthicalImpactLevel = Field(..., description="Assessed risk level of this action")
    payload:        dict[str, Any] | None = Field(default=None, description="Action-specific structured data")
    payload_hash:   str | None = Field(default=None, description="SHA-256 of payload at rationale time. Binds rationale to specific data.")
    ica_verifier_version: str | None = Field(default=None, description="Version of ICA verifier that checked this action.")
    boundary_provenance: dict[str, Any] | None = Field(default=None, description="Metadata from boundary agent when action originated from foreign SDC data.")


class AgentActionRecord(AgentAction):
    """DB-persisted form — includes server-assigned timestamp."""
    timestamp: str = Field(
        default_factory=lambda: __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc
        ).isoformat(),
        description="ISO-8601 timestamp assigned on persistence",
    )


# ── Constitutional Dialogue ────────────────────────────────────────────────────

class CoopProfile(BaseModel):
    """Input gathered during First-Boot Constitutional Dialogue."""
    coop_name:          str = Field(..., description="Legal name of the cooperative")
    jurisdiction:       str = Field(..., description="e.g. 'Colorado, USA' or 'Catalunya, Spain'")
    legal_wrapper_type: str = Field(..., description="e.g. 'LCA', 'LLC Operating Agreement', 'Bylaws'")
    founding_members:   list[str] = Field(..., description="List of founding member DIDs or names")
    pay_ratio:          int = Field(default=6, ge=1, le=20, description="Mondragon pay ratio cap (highest:lowest)")
    mission_statement:  str = Field(..., description="Cooperative's purpose statement")
    ica_principles:    list[str] = Field(
        default_factory=list,
        description="Selected ICA Cooperative Principles the coop commits to"
    )


class ConstitutionResponse(BaseModel):
    """Returned after First-Boot Constitutional Dialogue completes."""
    constitution_markdown: str  = Field(..., description="Generated Ricardian constitution in Markdown")
    ipfs_cid:              str  = Field(..., description="IPFS CID (mocked in dev; real in prod)")
    ipfs_uri:              str  = Field(..., description="ipfs://<cid>")
    agent_action:          AgentAction


# ── Federation ─────────────────────────────────────────────────────────────────

class ActorType(str, Enum):
    COOP    = "Organization"
    MEMBER  = "Person"
    SERVICE = "Service"


class ActivityPubActor(BaseModel):
    """Minimal ActivityPub Actor object for inter-coop federation."""
    context:           str       = Field(default="https://www.w3.org/ns/activitystreams", alias="@context")
    id:                str       = Field(..., description="https://<domain>/federation/actors/<handle>")
    type:              ActorType
    preferred_username: str      = Field(..., alias="preferredUsername")
    name:              str
    inbox:             str
    outbox:            str
    public_key:        dict[str, str] = Field(..., alias="publicKey")

    model_config = {"populate_by_name": True}


class ActivityObject(BaseModel):
    """Generic ActivityPub Activity wrapper."""
    context:    str  = Field(default="https://www.w3.org/ns/activitystreams", alias="@context")
    id:         str
    type:       str  = Field(..., description="e.g. 'Create', 'Follow', 'Announce'")
    actor:      str  = Field(..., description="Actor IRI")
    object:     Any
    to:         list[str] = Field(default_factory=lambda: ["https://www.w3.org/ns/activitystreams#Public"])

    model_config = {"populate_by_name": True}
