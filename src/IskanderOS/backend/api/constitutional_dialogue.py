"""
constitutional_dialogue.py — Phase 17: Ricardian Contract Generator with
New York Convention Arbitration Clause.

PURPOSE:
  Generates the IPFS JSON payload for Ricardian legal wrappers that bind
  smart contracts (IskanderEscrow.sol, CoopIdentity.sol) to real-world
  legal enforcement mechanisms.

DESIGN RATIONALE (Meatspace Execution Gap):
  Smart contract slashing does NOT recover stolen physical goods. On-chain
  dispute resolution is meaningless if a seller cooperative ships defective
  flour and the buyer cooperative has no legal recourse beyond a trust score
  deduction. The code must bridge to the courts.

  Every generated `legalWrapperCID` payload now includes a binding arbitration
  clause under the United Nations Convention on the Recognition and Enforcement
  of Foreign Arbitral Awards (1958 New York Convention). If the IskanderEscrow
  smart contract fails, deadlocks, or cannot resolve a dispute on-chain, the
  legal document designates a real-world cooperative arbitrator to enforce the
  debt in any signatory jurisdiction.

  This is not optional legal boilerplate — it is the bridge between code and
  the physical world where cooperatives actually operate.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/legal", tags=["legal"])

# ── New York Convention Arbitration Clause Template ──────────────────────────
# This clause is automatically injected into every Ricardian contract payload.
# It designates a cooperative-aligned arbitration body and ensures enforceability
# in all 172 signatory nations of the 1958 New York Convention.
_NY_CONVENTION_ARBITRATION_CLAUSE = {
    "clause_type": "binding_arbitration",
    "legal_framework": "United Nations Convention on the Recognition and Enforcement of Foreign Arbitral Awards (New York, 1958)",
    "arbitration_body": {
        "name": "International Co-operative Alliance (ICA) Dispute Resolution Service",
        "fallback": "International Centre for Dispute Resolution (ICDR) — Cooperative Sector Panel",
        "selection_procedure": (
            "If the parties cannot agree on an arbitrator within 30 days of the "
            "on-chain dispute event, the ICA Dispute Resolution Service shall appoint "
            "a sole arbitrator with expertise in cooperative law and solidarity economics."
        ),
    },
    "governing_law": "The law of the jurisdiction where the respondent cooperative is legally incorporated.",
    "seat_of_arbitration": "To be determined by the arbitration body based on party locations.",
    "language": "English, unless both parties agree to an alternative.",
    "enforcement": (
        "The arbitral award shall be final and binding. Either party may enforce "
        "the award in any court of competent jurisdiction under the New York Convention. "
        "The on-chain escrow verdict (ArbitrationRegistry.sol) shall be admissible as "
        "evidence of the parties' prior attempt at decentralised resolution."
    ),
    "scope": (
        "This clause covers all disputes arising from or in connection with the "
        "inter-cooperative trade agreement, including but not limited to: delivery "
        "failures, quality disputes, payment disputes, and any matter that the "
        "IskanderEscrow smart contract cannot resolve on-chain (e.g., deadlock, "
        "contract bug, force majeure, or physical goods recovery)."
    ),
    "cost_allocation": (
        "Arbitration costs shall be borne equally by both parties unless the "
        "arbitrator orders otherwise. The cooperative's mutual aid fund may "
        "subsidize costs for member cooperatives facing financial hardship."
    ),
}


class RicardianPayload(BaseModel):
    """Input for generating a Ricardian legal wrapper."""

    coop_name: str = Field(..., description="Name of the issuing cooperative.")
    counterparty_name: str = Field(..., description="Name of the counterparty cooperative.")
    trade_description: str = Field(..., description="Human-readable description of the trade.")
    escrow_contract_address: str | None = Field(
        None, description="On-chain IskanderEscrow contract address (if deployed)."
    )
    total_value: str = Field(..., description="Total trade value (e.g., '5000 USDC').")
    delivery_deadline: str = Field(..., description="ISO-8601 delivery deadline.")
    additional_terms: list[str] = Field(
        default_factory=list, description="Any additional terms agreed by both parties."
    )


class RicardianResponse(BaseModel):
    """Generated Ricardian contract ready for IPFS pinning."""

    legal_wrapper_json: dict[str, Any]
    ipfs_pin_ready: bool = True
    message: str


@router.post("/generate-ricardian", response_model=RicardianResponse)
async def generate_ricardian_contract(payload: RicardianPayload) -> dict[str, Any]:
    """Generate a Ricardian legal wrapper JSON payload for IPFS storage.

    Phase 17: Every generated payload automatically includes a binding
    New York Convention arbitration clause. If the IskanderEscrow smart contract
    fails or deadlocks, the off-chain legal document designates a real-world
    cooperative arbitrator to legally enforce the debt. Smart contracts are
    enforcement tools, not legal substitutes.
    """
    now = datetime.now(timezone.utc).isoformat()

    legal_wrapper = {
        "schema_version": "1.0.0",
        "document_type": "ricardian_trade_agreement",
        "generated_at": now,
        "generator": "iskander-os/constitutional-dialogue/v17",

        # ── Parties ──────────────────────────────────────────────────────
        "parties": {
            "issuer": {
                "name": payload.coop_name,
                "type": "cooperative",
            },
            "counterparty": {
                "name": payload.counterparty_name,
                "type": "cooperative",
            },
        },

        # ── Trade Terms ──────────────────────────────────────────────────
        "trade": {
            "description": payload.trade_description,
            "total_value": payload.total_value,
            "delivery_deadline": payload.delivery_deadline,
            "escrow_contract": payload.escrow_contract_address,
            "additional_terms": payload.additional_terms,
        },

        # ── On-Chain Dispute Resolution (First Resort) ───────────────────
        "on_chain_dispute_resolution": {
            "mechanism": "IskanderEscrow.sol + ArbitrationRegistry.sol",
            "description": (
                "Disputes are first routed through the federated solidarity court "
                "(Phase 15). A jury of peer cooperatives deliberates via Matrix rooms "
                "and ActivityPub. The ArbitrationRegistry records the verdict on-chain "
                "and the IskanderEscrow distributes funds per the jury's ruling."
            ),
            "limitation": (
                "On-chain resolution CANNOT recover stolen physical goods, enforce "
                "specific performance, or compel action in the physical world. "
                "It is limited to token redistribution and trust score adjustment."
            ),
        },

        # ── Phase 17: New York Convention Arbitration (Last Resort) ──────
        # This clause bridges the gap between code and the physical world.
        # When the smart contract fails, the law steps in.
        "binding_arbitration": _NY_CONVENTION_ARBITRATION_CLAUSE,

        # ── Cooperative Principles Affirmation ───────────────────────────
        "principles_affirmation": (
            "Both parties affirm their commitment to the ICA Cooperative Principles "
            "and the CCIN 10 Principles as encoded in the Iskander base_prompt.txt. "
            "This trade agreement is entered into in a spirit of mutual aid, not "
            "extractive competition."
        ),

        # ── Signature Placeholder ────────────────────────────────────────
        "signatures": {
            "issuer_signature": None,   # Filled by Safe multi-sig tx hash.
            "counterparty_signature": None,
            "signature_type": "EIP-712 typed data or Safe multi-sig transaction hash",
        },
    }

    logger.info(
        "Generated Ricardian legal wrapper for trade: %s <-> %s (value: %s)",
        payload.coop_name, payload.counterparty_name, payload.total_value,
    )

    return {
        "legal_wrapper_json": legal_wrapper,
        "ipfs_pin_ready": True,
        "message": (
            "Ricardian contract generated with Phase 17 New York Convention arbitration "
            "clause. Pin this JSON to IPFS and use the resulting CID as the "
            "termsIpfsCid parameter when calling IskanderEscrow.createEscrow()."
        ),
    }
