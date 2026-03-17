"""
fiat.py — Pydantic schemas for Phase 26: Fiat-Crypto Bridge API.

Request/response models for the /fiat router: mint/burn proposals,
reserve balance queries, and solvency status.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MintRequest(BaseModel):
    """Request body for POST /fiat/mint."""
    amount: int = Field(..., gt=0, description="Amount to mint in smallest token unit (wei).")
    rationale: str = Field(..., min_length=1, description="Human-readable justification for the mint.")
    escrow_id: str | None = Field(default=None, description="Related escrow ID, if triggered by settlement.")


class BurnRequest(BaseModel):
    """Request body for POST /fiat/burn."""
    amount: int = Field(..., gt=0, description="Amount to burn in smallest token unit (wei).")
    rationale: str = Field(..., min_length=1, description="Human-readable justification for the burn.")
    destination_account: str | None = Field(
        default=None,
        description="Off-ramp destination bank account (IBAN or sort-code/account).",
    )


class FiatOperationResponse(BaseModel):
    """Response for mint/burn operations."""
    thread_id: str = Field(..., description="LangGraph thread ID for resuming HITL flows.")
    status: str = Field(..., description="One of: proposed, pending_approval, executed.")
    operation_type: str = Field(..., description="One of: mint, burn.")
    amount: int = Field(..., description="Token amount in smallest unit (wei).")
    solvency_ratio: float | None = Field(default=None, description="Current reserve/supply ratio.")
    tx_hash: str | None = Field(default=None, description="On-chain transaction hash, if executed.")
    message: str = Field(..., description="Human-readable status message.")


class ReserveResponse(BaseModel):
    """Response for GET /fiat/reserve."""
    balance: str = Field(..., description="Decimal string of the fiat reserve balance.")
    currency: str = Field(..., description="ISO 4217 currency code.")
    account_id: str = Field(..., description="Masked bank account identifier.")
    institution: str = Field(..., description="Name of the cooperative bank.")
    as_of: str = Field(..., description="ISO 8601 datetime of the balance query.")


class SolvencyResponse(BaseModel):
    """Response for GET /fiat/solvency."""
    fiat_reserve: str = Field(..., description="Decimal string of fiat reserve balance.")
    total_escrow_wei: int = Field(..., description="Total on-chain escrow value in wei.")
    cfiat_supply_wei: int = Field(..., description="Total cFIAT token supply in wei.")
    solvency_ratio: float = Field(..., description="Reserve / supply ratio (>= 1.0 is healthy).")
    circuit_breaker_active: bool = Field(..., description="True if solvency ratio breached safety threshold.")
    checked_at: str = Field(..., description="ISO 8601 datetime of the solvency check.")
