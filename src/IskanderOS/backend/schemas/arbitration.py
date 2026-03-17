"""
Pydantic schemas for Phase 15: Inter-Coop Arbitration (Solidarity Court).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DisputeCreate(BaseModel):
    """Request body to file a new arbitration dispute."""
    escrow_id: str = Field(..., description="On-chain escrow ID being disputed.")
    complainant_did: str = Field(..., description="DID of the complaining party.")
    respondent_did: str = Field(..., description="DID of the responding party.")
    description: str = Field(..., min_length=20, description="Plain-language dispute description.")
    evidence_cids: list[str] = Field(default=[], description="IPFS CIDs of supporting evidence.")


class DisputeStatus(BaseModel):
    """Current status of an arbitration case."""
    case_id: UUID
    escrow_id: str
    status: str   # filed | jury_selection | deliberation | verdict_rendered | remedy_executed | appealed
    complainant_did: str
    respondent_did: str
    jury_members: list[dict[str, Any]] = []
    verdict: dict[str, Any] | None = None


class EvidenceSubmission(BaseModel):
    """Additional evidence submitted during deliberation."""
    case_id: UUID
    submitted_by: str    # DID of submitting party.
    ipfs_cid: str        # IPFS CID of evidence document.
    description: str     # Brief description of what this evidence shows.


class JuryMember(BaseModel):
    """A member of the federated jury."""
    did: str
    source_coop_domain: str  # e.g. "sistercoop.local"
    nominated_at: str        # ISO datetime.
    confirmed: bool = False


class Verdict(BaseModel):
    """The human jury's verdict, submitted by the operator Safe."""
    case_id: UUID
    outcome: str = Field(
        ...,
        description="One of: BuyerFavored, SellerFavored, Split, Dismissed",
    )
    buyer_amount_wei: int = Field(..., ge=0)
    seller_amount_wei: int = Field(..., ge=0)
    buyer_slash: int = Field(default=0, ge=0, le=1000, description="Trust score penalty for buyer.")
    seller_slash: int = Field(default=0, ge=0, le=1000, description="Trust score penalty for seller.")
    jury_ipfs_cid: str = Field(..., description="IPFS CID of the jury deliberation record.")
    rationale_summary: str = Field(..., description="Plain-language summary of the verdict rationale.")


class EscrowCreate(BaseModel):
    """Request body to create a new inter-coop escrow."""
    seller_coop_address: str = Field(..., description="Seller's Safe wallet address (0x...).")
    token_address: str = Field(..., description="ERC-20 token contract address.")
    amount_wei: int = Field(..., gt=0)
    terms_ipfs_cid: str = Field(..., description="IPFS CID of the Ricardian trade contract.")
    expires_at: int = Field(default=0, description="Unix timestamp for expiry (0 = no expiry).")


class EscrowStatus(BaseModel):
    """Runtime status of an escrow contract."""
    escrow_id: str
    buyer_coop: str
    seller_coop: str
    token_address: str
    amount_wei: int
    status: str   # Active | Released | Disputed | Arbitrated | Expired
    terms_ipfs_cid: str
    has_active_case: bool = False
