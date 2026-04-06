"""
hitl.py — Pydantic schemas for Phase 20: Sovereign Personal Node HITL Routing.

Defines the data models for DID-based HITL notification routing. When a
multi-sig transaction or governance action requires a member's signature,
the system resolves the member's Decentralized Identifier (DID) document
to determine *where* they want to receive the proposal:

  - Their own personal Iskander node (ActivityPub inbox)  → sovereign path
  - The cooperative's local Streamlit dashboard            → fallback path

The individual member is sovereign. The cooperative routes notifications —
it does not gatekeep. A member who runs their own single-member Iskander
node at home should never be forced to log into a central cooperative
server to participate in governance.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.schemas.glass_box import AgentAction


# ── DID Document Types ─────────────────────────────────────────────────────────
# Minimal W3C DID Core v1.0 subset. Only the fields needed for service
# endpoint discovery. Full DID resolution is out of scope for Phase 20.


class DIDServiceEndpoint(BaseModel):
    """A single service entry within a DID Document.

    For HITL routing, the critical type is "ActivityPubInbox" — its
    service_endpoint URL is the member's personal node inbox.
    """
    id: str = Field(..., description="Service entry identifier (e.g. did:web:alice.example#ap-inbox)")
    type: str = Field(..., description="Service type. 'ActivityPubInbox' triggers sovereign routing.")
    service_endpoint: str = Field(..., description="URL of the service (e.g. https://alice.example/inbox)")


class DIDDocument(BaseModel):
    """Minimal W3C DID Document for service endpoint discovery.

    The cooperative does not need to fully verify the DID document for
    notification routing — it only needs to find the member's preferred
    inbox. Cryptographic verification of the DID document is deferred
    to the ActivityPub HTTP Signature layer.
    """
    id: str = Field(..., description="The DID itself (e.g. did:web:alice.example)")
    service: list[DIDServiceEndpoint] = Field(
        default_factory=list,
        description="Service endpoints declared by the DID subject.",
    )
    verification_method: list[dict[str, Any]] | None = Field(
        default=None,
        description="Public keys for verification. Not used in Phase 20 stub.",
    )


# ── HITL Proposal Types ───────────────────────────────────────────────────────


class HITLProposal(BaseModel):
    """A HITL approval request routed to a member.

    Encapsulates everything a member's personal AI needs to summarise
    the vote: what type of decision, the unsigned Safe transaction (if
    applicable), the voting deadline, and where to POST the vote back.
    """
    proposal_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique proposal identifier.",
    )
    proposal_type: Literal[
        "governance", "treasury", "steward", "arbitration", "ipd",
        "discussion_context",
        "proposal_draft",
        "outcome_approval",
        "task_assignment",
    ] = Field(
        ..., description="Which agent domain originated this HITL request.",
    )
    summary: str = Field(
        ..., description="Human-readable description of the action requiring approval.",
    )
    safe_transaction_draft: dict[str, Any] | None = Field(
        default=None,
        description="Unsigned Safe multi-sig transaction, if applicable.",
    )
    voting_deadline: datetime | None = Field(
        default=None,
        description="UTC deadline after which the proposal expires.",
    )
    callback_inbox: str = Field(
        ..., description="ActivityPub inbox URL of the originating cooperative node for vote delivery.",
    )
    agent_id: str = Field(
        ..., description="ID of the agent that triggered this HITL breakpoint.",
    )
    thread_id: str = Field(
        ..., description="LangGraph checkpoint thread_id for graph resumption after vote.",
    )
    ethical_impact: str = Field(
        default="MEDIUM",
        description="EthicalImpactLevel from Glass Box protocol.",
    )


class HITLNotification(BaseModel):
    """Local database row for HITL proposals delivered via the fallback path.

    When a member's DID does not resolve to a personal ActivityPub inbox,
    the notification is stored locally for Streamlit UI pickup. Even
    ActivityPub-routed proposals get a row here for audit trail completeness.

    The cooperative keeps records — but the member keeps sovereignty.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Notification row UUID.",
    )
    member_did: str = Field(..., description="DID of the member who must vote.")
    proposal: HITLProposal = Field(..., description="The full proposal payload.")
    route: Literal["activitypub", "local_db", "loomio"] = Field(
        ..., description="How this notification was delivered.",
    )
    status: Literal["pending", "approved", "rejected", "expired"] = Field(
        default="pending",
        description="Current lifecycle state.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the notification was created.",
    )
    responded_at: datetime | None = Field(
        default=None,
        description="When the member responded (None if still pending).",
    )


class HITLRoutingResult(BaseModel):
    """Return value from HITLRoutingManager.route_hitl_proposal().

    Tells the caller which path was taken and whether delivery succeeded.
    Always includes a Glass Box AgentAction for the audit log.
    """
    route: Literal["activitypub", "local_db", "loomio"] = Field(
        ..., description="Delivery channel used.",
    )
    proposal_id: str = Field(..., description="The routed proposal's ID.")
    member_did: str = Field(..., description="Target member's DID.")
    delivery_success: bool = Field(
        ..., description="True if the notification was delivered (AP POST succeeded or DB write succeeded).",
    )
    agent_action: AgentAction = Field(
        ..., description="Glass Box audit record for this routing decision.",
    )


class HITLProposalVote(BaseModel):
    """Inbound vote from a member's personal Iskander node.

    Delivered as an iskander:HITLProposalVote ActivityPub activity to
    the cooperative's federation inbox. The cooperative's inbox processor
    uses the thread_id to resume the paused LangGraph checkpoint.

    This is the sovereign counterpart to the Streamlit /governance/vote
    endpoint: same effect, different delivery channel. The member's
    personal AI summarised the proposal and the member voted from home.
    """
    proposal_id: str = Field(..., description="Which proposal this vote is for.")
    voter_did: str = Field(..., description="DID of the voting member.")
    approved: bool = Field(..., description="True = approve, False = reject.")
    rejection_reason: str | None = Field(
        default=None,
        description="Required if approved=False.",
    )
    thread_id: str = Field(
        ..., description="LangGraph thread_id for checkpoint resumption.",
    )
