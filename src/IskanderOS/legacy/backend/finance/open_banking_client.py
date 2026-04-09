"""
open_banking_client.py — PSD2/Open Banking API wrapper (Phase 22).

Bridges the Iskander on-chain economy with traditional cooperative banking.
Provides read-only balance queries and draft-only transfer creation.

SECURITY INVARIANT:
  The AI NEVER possesses write-access API keys capable of moving fiat
  without a cryptographic Human-in-the-Loop signature. The draft_fiat_transfer()
  method creates a PENDING transfer only — a BrightID-verified cooperative
  treasurer must approve via the bank portal or OAuth to execute the actual
  funds movement.

ANTI-EXTRACTIVE:
  This architecture bypasses Visa, Mastercard, and Stripe. Inter-cooperative
  commerce settles directly via cooperative bank rails (PSD2/Open Banking),
  returning the 2-3% transaction fees to the workers and the cooperative
  ecosystem. No extractive payment processor sits between cooperatives.

REGULATORY REALISM:
  The cFIAT token supply must NEVER exceed the fiat reserve balance in
  the cooperative bank's regulated trust account. The Fiat Gateway Agent
  calls get_fiat_reserve_balance() before authorizing any mint operation.

STUB NOTICE:
  All API calls are mocked. In production, replace with authenticated
  calls to a PSD2-compliant provider (Plaid, TrueLayer, Yapily, etc.).
  The mock returns plausible balances for development and testing.

GLASS BOX:
  Every API operation produces an AgentAction for the audit ledger.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.config import settings
from backend.schemas.fiat_bridge import FiatReserveBalance, PendingTransfer
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "open-banking-client"


class OpenBankingClient:
    """
    Wraps a PSD2/Open Banking API for cooperative fiat reserve management.

    Singleton: obtain via OpenBankingClient.get_instance().

    The client has TWO capabilities:
      1. READ:  get_fiat_reserve_balance() — query the trust account balance.
      2. DRAFT: draft_fiat_transfer() — create a PENDING transfer for human approval.

    The client NEVER executes a transfer autonomously.
    """

    _instance: "OpenBankingClient | None" = None

    def __init__(self) -> None:
        self._api_url = settings.open_banking_api_url.rstrip("/")
        self._api_key = settings.open_banking_api_key
        self._currency = settings.cfiat_currency

        # STUB: mock pending transfers for development.
        self._pending_transfers: list[PendingTransfer] = []

    @classmethod
    def get_instance(cls) -> "OpenBankingClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Balance Query ──────────────────────────────────────────────────────────

    async def get_fiat_reserve_balance(self) -> tuple[FiatReserveBalance, AgentAction]:
        """
        Query the cooperative bank's trust account balance.

        Returns the available fiat balance that backs the cFIAT token supply.
        If the balance is less than total cFIAT supply, minting must halt.

        STUB: Returns a mock balance. Production: authenticated PSD2 API call.
        """
        # STUB: Mock response — replace with httpx call to Open Banking API.
        balance = FiatReserveBalance(
            balance=Decimal("50000.00"),
            currency=self._currency,
            account_id="****4821",
            institution="Cooperative Bank of Britain (STUB)",
        )

        action = AgentAction(
            agent_id=AGENT_ID,
            action="get_fiat_reserve_balance",
            rationale=(
                "Queried the cooperative bank's trust account balance via Open Banking API. "
                "This balance must always be >= total cFIAT supply to maintain 1:1 backing. "
                "The cooperative bank holds real, insured fiat — not algorithmic reserves."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "balance": str(balance.balance),
                "currency": balance.currency,
                "account_id": balance.account_id,
                "institution": balance.institution,
            },
        )

        logger.info(
            "Fiat reserve balance: %s %s (account: %s)",
            balance.balance, balance.currency, balance.account_id,
        )

        return balance, action

    # ── Transfer Drafting ──────────────────────────────────────────────────────

    async def draft_fiat_transfer(
        self,
        to_account: str,
        amount: Decimal,
        reference: str,
        currency: str | None = None,
    ) -> tuple[PendingTransfer, AgentAction]:
        """
        Draft a pending fiat bank transfer for human approval.

        This creates a transfer DRAFT only. The actual funds movement requires
        a BrightID-verified cooperative treasurer to:
          1. Review the draft in the Iskander dashboard
          2. Approve via the bank's OAuth flow or portal login
          3. Confirm execution back to the Fiat Gateway Agent

        The AI NEVER executes fiat transfers autonomously. This is a
        non-negotiable security invariant of the Iskander architecture.

        STUB: Stores the draft in-memory. Production: PSD2 Payment Initiation
        Service (PIS) API call that creates a consent request.
        """
        transfer = PendingTransfer(
            to_account=to_account,
            amount=amount,
            currency=currency or self._currency,
            reference=reference,
            status="pending_human_approval",
        )

        # STUB: store locally.
        self._pending_transfers.append(transfer)

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"draft_fiat_transfer({amount} {transfer.currency} → {to_account[:8]}...)",
            rationale=(
                f"Drafted a pending fiat bank transfer of {amount} {transfer.currency} "
                f"to account {to_account[:8]}... (ref: {reference}). "
                f"This is a DRAFT ONLY — a BrightID-verified treasurer must approve "
                f"via the bank portal before any real-world funds move. "
                f"The AI NEVER holds write-access to cooperative bank accounts."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "transfer_id": transfer.id,
                "to_account": to_account[:8] + "...",
                "amount": str(amount),
                "currency": transfer.currency,
                "reference": reference,
                "status": transfer.status,
            },
        )

        logger.info(
            "Fiat transfer drafted: %s %s → %s (ref: %s, status: %s)",
            amount, transfer.currency, to_account[:8], reference, transfer.status,
        )

        return transfer, action

    # ── Query Helpers ──────────────────────────────────────────────────────────

    def get_pending_transfers(self) -> list[PendingTransfer]:
        """Return all pending transfer drafts awaiting human approval."""
        return [t for t in self._pending_transfers if t.status == "pending_human_approval"]

    def mark_transfer_approved(self, transfer_id: str, approved_by: str) -> bool:
        """Mark a transfer as approved by a BrightID-verified treasurer."""
        for t in self._pending_transfers:
            if t.id == transfer_id:
                t.status = "approved"
                t.approved_by = approved_by
                return True
        return False
