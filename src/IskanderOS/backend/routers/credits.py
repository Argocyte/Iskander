"""
credits.py — Phase 19: Custodial Treasury / Internal Credit Management API.

The cooperative acts as custodian for off-chain (meatspace) members.
Credits are internal accounting units denominated in the same unit as the
on-chain token (xDAI equivalent). Conversion to/from on-chain tokens is
gated by steward multi-sig approval (HITL).

Endpoints:
  POST /credits/deposit          — Record a fiat deposit and credit the member (steward).
  GET  /credits/balance/{did}    — Query credit balance.
  POST /credits/transfer         — Transfer credits between members (auth).
  POST /credits/convert-to-chain — Convert credits to on-chain tokens via Safe (HITL).
  POST /credits/convert-from-chain — Reverse: tokens → credits.
  GET  /credits/ledger/{did}     — Full transaction history for audit.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.dependencies import AuthenticatedUser, get_current_user, require_role
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["credits"])

# ── STUB: In-memory credit accounts (production: asyncpg queries) ────────────
_accounts: dict[str, dict[str, Any]] = {}
_transactions: list[dict[str, Any]] = []


def _get_or_create_account(member_did: str) -> dict[str, Any]:
    if member_did not in _accounts:
        _accounts[member_did] = {
            "member_did": member_did,
            "balance": 0.0,
            "is_on_chain": False,
            "linked_address": None,
        }
    return _accounts[member_did]


# ── Schemas ───────────────────────────────────────────────────────────────────


class DepositRequest(BaseModel):
    member_did: str = Field(..., description="DID of the member to credit")
    amount: float = Field(..., gt=0, description="Amount in credit units (xDAI equivalent)")
    currency: str = Field(default="USD", description="Fiat currency of the deposit")
    payment_method: str = Field(default="bank_transfer")
    fiat_reference: str | None = Field(default=None, description="External payment reference")
    note: str | None = None


class TransferRequest(BaseModel):
    to_did: str = Field(..., description="Recipient member DID")
    amount: float = Field(..., gt=0, description="Amount to transfer")
    note: str | None = None


class ConvertToChainRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Credit amount to convert to on-chain tokens")
    recipient_address: str = Field(..., description="Ethereum address to receive tokens")


class ConvertFromChainRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Token amount being deposited to treasury")
    tx_hash: str = Field(..., description="On-chain transaction hash as proof")


# ── POST /credits/deposit ────────────────────────────────────────────────────


@router.post("/deposit", status_code=status.HTTP_201_CREATED)
async def deposit_credits(
    req: DepositRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> dict[str, Any]:
    """Record a fiat deposit and credit the member's internal account.

    Only stewards can process deposits — this is the fiat-to-credit bridge.
    The steward confirms the fiat payment was received off-chain, then
    credits the member's internal account.
    """
    account = _get_or_create_account(req.member_did)
    account["balance"] += req.amount

    tx_id = str(uuid4())
    _transactions.append({
        "id": tx_id,
        "from_did": None,
        "to_did": req.member_did,
        "amount": req.amount,
        "tx_type": "deposit",
        "fiat_reference": req.fiat_reference,
        "note": req.note,
        "created_by": user.did or user.address,
    })

    logger.info(
        "Credit deposit: %s credited %.4f to %s (ref=%s)",
        user.address[:15],
        req.amount,
        req.member_did[:20],
        req.fiat_reference,
    )

    return {
        "transaction_id": tx_id,
        "member_did": req.member_did,
        "amount_credited": req.amount,
        "new_balance": account["balance"],
        "message": (
            f"Deposit of {req.amount} credits recorded for {req.member_did}. "
            "Fiat payment confirmed by steward."
        ),
    }


# ── GET /credits/balance/{did} ───────────────────────────────────────────────


@router.get("/balance/{member_did}")
async def get_balance(member_did: str) -> dict[str, Any]:
    """Query credit balance for a member. Public read endpoint."""
    account = _accounts.get(member_did)
    if not account:
        return {
            "member_did": member_did,
            "balance": 0.0,
            "is_on_chain": False,
            "linked_address": None,
        }
    return account


# ── POST /credits/transfer ───────────────────────────────────────────────────


@router.post("/transfer", status_code=status.HTTP_200_OK)
async def transfer_credits(
    req: TransferRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Transfer credits between members. Requires authentication."""
    from_did = user.did
    if not from_did:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account has no DID. Cannot transfer credits without a DID.",
        )

    from_account = _accounts.get(from_did)
    if not from_account or from_account["balance"] < req.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient credit balance.",
        )

    to_account = _get_or_create_account(req.to_did)

    from_account["balance"] -= req.amount
    to_account["balance"] += req.amount

    tx_id = str(uuid4())
    _transactions.append({
        "id": tx_id,
        "from_did": from_did,
        "to_did": req.to_did,
        "amount": req.amount,
        "tx_type": "transfer",
        "note": req.note,
        "created_by": user.did or user.address,
    })

    return {
        "transaction_id": tx_id,
        "from_did": from_did,
        "to_did": req.to_did,
        "amount": req.amount,
        "from_new_balance": from_account["balance"],
        "to_new_balance": to_account["balance"],
    }


# ── POST /credits/convert-to-chain ──────────────────────────────────────────


@router.post("/convert-to-chain", status_code=status.HTTP_202_ACCEPTED)
async def convert_to_chain(
    req: ConvertToChainRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Convert credits to on-chain tokens via co-op treasury Safe.

    The flow:
      1. Debit credits from member's internal account.
      2. Submit Safe transaction to transfer equivalent tokens from treasury.
      3. HITL gate: steward multi-sig signs the transaction.

    STUB: Records the intent. Production: creates a pending Safe transaction.
    """
    from_did = user.did
    if not from_did:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DID required for credit-to-chain conversion.",
        )

    account = _accounts.get(from_did)
    if not account or account["balance"] < req.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient credit balance.",
        )

    # Debit credits.
    account["balance"] -= req.amount

    tx_id = str(uuid4())
    _transactions.append({
        "id": tx_id,
        "from_did": from_did,
        "to_did": None,
        "amount": req.amount,
        "tx_type": "conversion_to_chain",
        "note": f"Convert to {req.recipient_address}",
        "created_by": user.did or user.address,
    })

    logger.info(
        "STUB: Credit-to-chain conversion: %s converting %.4f to %s",
        from_did[:20],
        req.amount,
        req.recipient_address[:15],
    )

    return {
        "transaction_id": tx_id,
        "amount": req.amount,
        "recipient_address": req.recipient_address,
        "status": "pending_safe_signature",
        "message": (
            "Credits debited. Awaiting steward Safe multi-sig signature "
            "to transfer equivalent tokens on-chain."
        ),
    }


# ── POST /credits/convert-from-chain ────────────────────────────────────────


@router.post("/convert-from-chain", status_code=status.HTTP_200_OK)
async def convert_from_chain(
    req: ConvertFromChainRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Reverse: member sends tokens to treasury, credits their account.

    STUB: Records the conversion. Production: verify on-chain transfer to
    treasury Safe address, then credit the member's account.
    """
    member_did = user.did
    if not member_did:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DID required for chain-to-credit conversion.",
        )

    account = _get_or_create_account(member_did)
    account["balance"] += req.amount
    account["is_on_chain"] = True
    account["linked_address"] = user.address

    tx_id = str(uuid4())
    _transactions.append({
        "id": tx_id,
        "from_did": None,
        "to_did": member_did,
        "amount": req.amount,
        "tx_type": "conversion_from_chain",
        "on_chain_tx_hash": req.tx_hash,
        "created_by": user.did or user.address,
    })

    logger.info(
        "STUB: Chain-to-credit conversion: %s deposited %.4f (tx=%s)",
        member_did[:20],
        req.amount,
        req.tx_hash[:15],
    )

    return {
        "transaction_id": tx_id,
        "amount_credited": req.amount,
        "new_balance": account["balance"],
        "on_chain_tx_hash": req.tx_hash,
        "message": "On-chain tokens received. Credits added to internal account.",
    }


# ── GET /credits/ledger/{did} ────────────────────────────────────────────────


@router.get("/ledger/{member_did}")
async def get_ledger(member_did: str) -> dict[str, Any]:
    """Full transaction history for a member. Public read for transparency."""
    member_txs = [
        tx
        for tx in _transactions
        if tx.get("from_did") == member_did or tx.get("to_did") == member_did
    ]
    return {
        "member_did": member_did,
        "transaction_count": len(member_txs),
        "transactions": member_txs,
    }
