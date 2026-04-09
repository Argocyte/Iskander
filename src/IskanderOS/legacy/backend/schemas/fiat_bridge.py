"""
fiat_bridge.py — Pydantic schemas for Phase 22: Fiat-Backed Solidarity Economy.

Defines the data models for cooperative fiat token operations, open banking
integration, and the off-ramp/on-ramp bridge between on-chain escrow
settlements and physical cooperative bank accounts.

ANTI-EXTRACTIVE:
  This architecture exists to bypass Visa, Mastercard, and Stripe, returning
  the 2-3% transaction fees back to the workers and the cooperative ecosystem.
  Inter-cooperative commerce is settled directly via cooperative bank rails,
  not extractive payment processors.

REGULATORY REALISM:
  The minting of cFIAT relies on the physical cooperative bank holding the
  equivalent 1:1 fiat in a regulated trust account. This is NOT fractional
  reserve — every on-chain token is backed by an insured, auditable deposit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class FiatReserveBalance(BaseModel):
    """Current fiat reserve balance from the cooperative bank.

    Retrieved via Open Banking API (PSD2/Plaid/TrueLayer). The balance
    must always be >= total cFIAT supply to maintain 1:1 backing.
    """
    balance: Decimal = Field(..., description="Available balance in the trust account.")
    currency: str = Field(default="GBP", description="ISO 4217 currency code.")
    account_id: str = Field(..., description="Bank account identifier (masked for logs).")
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the balance query.",
    )
    institution: str = Field(default="", description="Name of the cooperative bank.")


class PendingTransfer(BaseModel):
    """A drafted fiat bank transfer awaiting human approval.

    The AI NEVER executes fiat transfers autonomously. This draft creates
    a pending real-world bank transfer that requires a BrightID-verified
    cooperative treasurer to log into the bank portal (or approve via OAuth)
    to authorize the actual funds movement.

    SECURITY: The AI must NEVER possess write-access API keys capable of
    moving fiat without a cryptographic Human-in-the-Loop signature.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    to_account: str = Field(..., description="Destination bank account (IBAN or sort-code/account).")
    amount: Decimal = Field(..., gt=0, description="Transfer amount in fiat currency.")
    currency: str = Field(default="GBP", description="ISO 4217 currency code.")
    reference: str = Field(..., description="Payment reference (e.g. escrow ID, coop trade ref).")
    status: Literal["drafted", "pending_human_approval", "approved", "executed", "failed"] = Field(
        default="drafted",
    )
    drafted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: str | None = Field(
        default=None,
        description="DID of the BrightID-verified treasurer who approved.",
    )


class OfframpProposal(BaseModel):
    """HITL proposal for burning cFIAT to off-ramp to physical bank account.

    When a cooperative receives cFIAT from an escrow trade, the Fiat Gateway
    Agent generates this proposal: "Keep on-chain for future trades, or burn
    to off-ramp and credit our physical cooperative bank account?"
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    escrow_id: str = Field(..., description="The escrow that generated this settlement.")
    cfiat_amount: Decimal = Field(..., description="Amount of cFIAT received.")
    currency_symbol: str = Field(default="cGBP", description="Cooperative fiat token symbol.")
    source_coop: str = Field(..., description="Address/DID of the trading partner cooperative.")
    proposal_type: Literal["offramp", "hold"] = Field(
        ..., description="Whether to burn (off-ramp) or hold on-chain.",
    )
    justification: str = Field(default="", description="Reason for the proposed action.")
    fiat_transfer_draft: PendingTransfer | None = Field(
        default=None,
        description="If offramp: the drafted bank transfer awaiting approval.",
    )
    status: Literal["proposed", "approved", "rejected", "executed"] = Field(default="proposed")


class CoopFiatTokenEvent(BaseModel):
    """On-chain event from the CoopFiatToken contract.

    Captures FiatMinted, FiatBurned, and FiatSettlementReady events
    for the off-chain Fiat Gateway Agent to process.
    """
    event_type: Literal["FiatMinted", "FiatBurned", "FiatSettlementReady"] = Field(
        ..., description="Contract event type.",
    )
    escrow_id: str | None = Field(default=None, description="Related escrow ID (if settlement).")
    address: str = Field(..., description="Address involved (minter, burner, or seller).")
    amount_wei: int = Field(..., description="Token amount in smallest unit.")
    tx_hash: str | None = Field(default=None, description="Transaction hash.")
    block_number: int | None = Field(default=None, description="Block number.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FiatSettlement(BaseModel):
    """Complete settlement record linking on-chain escrow to off-chain fiat.

    The end-to-end audit trail: escrow release → cFIAT transfer → burn
    decision → bank transfer → fiat credited. Every step is logged in
    the Glass Box audit ledger.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    escrow_id: str
    on_chain_amount_wei: int
    cfiat_symbol: str = "cGBP"
    settlement_action: Literal["held_on_chain", "offramped"] = Field(
        ..., description="What was done with the received cFIAT.",
    )
    fiat_transfer_id: str | None = Field(
        default=None, description="PendingTransfer.id if offramped.",
    )
    bank_confirmation: str | None = Field(
        default=None, description="Bank transaction reference if fiat was moved.",
    )
    settled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
