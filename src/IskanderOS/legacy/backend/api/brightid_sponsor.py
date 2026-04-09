"""
brightid_sponsor.py — Phase 17: BrightID Sponsorship Endpoint.

PURPOSE:
  Automatically sponsors new cooperative members' BrightID accounts using the
  cooperative's treasury wallet, ensuring onboarding is ENTIRELY FREE and
  frictionless for non-technical workers (bakers, drivers, care workers).

DESIGN RATIONALE (Anti-Wealth-Gating):
  BrightID requires a small sponsorship transaction to activate a new user's
  verification. Without this backend, members would need to acquire tokens
  and interact with smart contracts directly — creating a de facto wealth
  barrier that contradicts ICA Principle 1 (Voluntary & Open Membership).

  This endpoint absorbs the cost via the cooperative's shared treasury,
  ensuring that a baker who has never touched a blockchain wallet can join
  the cooperative with the same ease as a software engineer.

IDENTITY MODEL:
  Identity is derived 100% from the BrightID peer-to-peer social graph.
  NO Gitcoin Passport. NO wallet-balance-based voting weights. NO invasive KYC.
  The cooperative trusts the Web-of-Trust, not wealth signals or government IDs.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from web3 import Web3

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brightid", tags=["identity"])

# BrightID sponsorship contract ABI (minimal — only the sponsor function).
_SPONSOR_ABI = [
    {
        "inputs": [{"name": "contextId", "type": "bytes32"}],
        "name": "sponsor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


class SponsorRequest(BaseModel):
    """Request to sponsor a new member's BrightID account."""

    # The applicant's Ethereum address (will be linked to their BrightID).
    applicant_address: str = Field(
        ..., description="Ethereum address of the cooperative applicant."
    )
    # Optional: the applicant's BrightID contextId if already generated.
    # If omitted, derived from keccak256(applicant_address).
    context_id: str | None = Field(
        None, description="BrightID context ID (hex). Auto-derived if omitted."
    )


class SponsorResponse(BaseModel):
    """Response after sponsoring a BrightID account."""

    sponsored: bool
    tx_hash: str | None = None
    context_id: str
    message: str


@router.post("/sponsor", response_model=SponsorResponse)
async def sponsor_brightid_account(req: SponsorRequest) -> dict[str, Any]:
    """Sponsor a new cooperative member's BrightID account.

    The cooperative's treasury wallet pays the sponsorship fee so that
    non-technical workers (bakers, drivers, care workers) can join without
    needing to acquire tokens or understand blockchain mechanics.

    This endpoint is called by the First-Boot Constitutional Dialogue UI
    during the member onboarding flow.
    """
    # Derive contextId from applicant address if not provided.
    if req.context_id:
        context_id = req.context_id
    else:
        context_id = Web3.solidity_keccak(
            ["address"], [Web3.to_checksum_address(req.applicant_address)]
        ).hex()

    # Connect to the local EVM node.
    w3 = Web3(Web3.HTTPProvider(settings.evm_rpc_url))
    if not w3.is_connected():
        raise HTTPException(status_code=503, detail="EVM node unreachable.")

    # Load the cooperative's treasury wallet (sponsor account).
    # In production: use a hardware wallet signer or Safe multi-sig relay.
    treasury_key = getattr(settings, "treasury_private_key", None)
    if not treasury_key:
        raise HTTPException(
            status_code=500,
            detail="Treasury private key not configured. Set TREASURY_PRIVATE_KEY in .env.",
        )

    treasury_address = w3.eth.account.from_key(treasury_key).address

    # Load the BrightID sponsorship contract.
    sponsor_contract_addr = getattr(settings, "brightid_sponsor_contract", None)
    if not sponsor_contract_addr:
        raise HTTPException(
            status_code=500,
            detail="BrightID sponsor contract address not configured.",
        )

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(sponsor_contract_addr),
        abi=_SPONSOR_ABI,
    )

    try:
        # Build and sign the sponsorship transaction.
        nonce = w3.eth.get_transaction_count(treasury_address)
        tx = contract.functions.sponsor(bytes.fromhex(context_id[2:] if context_id.startswith("0x") else context_id)).build_transaction(
            {
                "from": treasury_address,
                "nonce": nonce,
                "gas": 100_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
        signed = w3.eth.account.sign_transaction(tx, treasury_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        logger.info(
            "BrightID sponsorship sent for applicant %s — tx: %s",
            req.applicant_address[:10],
            tx_hash.hex(),
        )

        return {
            "sponsored": True,
            "tx_hash": tx_hash.hex(),
            "context_id": context_id,
            "message": (
                "BrightID account sponsored. The applicant can now complete "
                "BrightID verification and join the cooperative. No tokens or "
                "blockchain knowledge required — the cooperative treasury covered "
                "the sponsorship cost."
            ),
        }

    except Exception as exc:
        logger.exception("BrightID sponsorship failed for %s", req.applicant_address[:10])
        raise HTTPException(
            status_code=500,
            detail=f"Sponsorship transaction failed: {exc}",
        ) from exc
