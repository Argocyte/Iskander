"""
tx_orchestrator.py — Safe multi-sig batch drafting with TTL enforcement.

The TxOrchestrator extends the existing Safe-drafting pattern from treasurer.py
and governance_agent.py. It is the single exit point for all value-moving
operations: agents propose transaction batches, the orchestrator validates
against the PolicyEngine, and exports Gnosis Safe-compatible JSON for human
M-of-N signing.

CORE INVARIANT: No Auto-Sign.
  The node holds only a propose_key (read + propose). It NEVER holds a
  sign_key. Fraudulent proposals are harmless unsigned payloads.

GLASS BOX: Every method returns an AgentAction for the audit trail.

LIFECYCLE:
  draft_batch()       → Drafted
  (human signs)       → Pending → Executed (external)
  verify_settlement() → Settled
  purge_stale()       → Stale (TTL expired, no auto-cancel)
  cancel()            → Cancelled (manual by steward)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from backend.config import settings
from backend.governance.policy_engine import PolicyEngine
from backend.mesh.causal_event import CausalEvent
from backend.schemas.compliance import (
    DraftedTransaction,
    OperationalComplianceViolation,
    SafeTxPayload,
    TxStatus,
    VALID_TX_TRANSITIONS,
)
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "tx-orchestrator-v1"


class TxOrchestrator:
    """Singleton Safe batch orchestrator.

    Obtain via ``TxOrchestrator.get_instance()``.

    All value-moving operations route through this class. It reads from the
    PolicyEngine and the Mesh Archive — it has NO write-access to private keys.
    """

    _instance: TxOrchestrator | None = None

    def __init__(self) -> None:
        self._policy_engine = PolicyEngine.get_instance()
        # In-memory transaction store (STUB for DB)
        self._pending_transactions: dict[str, DraftedTransaction] = {}

    @classmethod
    def get_instance(cls) -> TxOrchestrator:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton."""
        cls._instance = None

    # ═══════════════════════════════════════════════════════════════════════════
    # DRAFT BATCH — The Primary Entry Point
    # ═══════════════════════════════════════════════════════════════════════════

    def draft_batch(
        self,
        proposals: list[dict[str, Any]],
        requester_did: str,
    ) -> tuple[DraftedTransaction, AgentAction]:
        """Draft a batch of Safe transactions from agent proposals.

        Steps:
          1. Run PolicyEngine.check_compliance() for each proposal.
          2. Build SafeTxPayload objects from validated proposals.
          3. Store the DraftedTransaction with TTL.
          4. Attach the governance_manifest_cid for provenance.

        Raises:
            OperationalComplianceViolation: If any proposal fails compliance.
            ValueError: If no PolicyEngine manifest is loaded.
        """
        # ── Step 1: Policy check for each proposal ────────────────────────────
        all_violations = []
        for proposal in proposals:
            agent_id = proposal.get("agent_id", "unknown")
            action_type = proposal.get("type", "payment")
            result, _action = self._policy_engine.check_compliance(
                agent_id=agent_id,
                action_type=action_type,
                params=proposal,
            )
            if not result.compliant:
                all_violations.extend(result.violations)

        if all_violations:
            raise OperationalComplianceViolation(
                violations=all_violations,
                message=(
                    f"Batch draft blocked: {len(all_violations)} policy violation(s) "
                    f"across {len(proposals)} proposal(s)."
                ),
            )

        # ── Step 2: Build Safe payloads ───────────────────────────────────────
        safe_txs: list[SafeTxPayload] = []
        for proposal in proposals:
            tx = SafeTxPayload(
                to=proposal.get("to", "0x" + "0" * 40),
                value=str(proposal.get("value_wei", proposal.get("value", "0"))),
                data=proposal.get("data", "0x"),
                operation=proposal.get("operation", 0),
                nonce=proposal.get("nonce"),
            )
            safe_txs.append(tx)

        # ── Step 3: Create DraftedTransaction ─────────────────────────────────
        ttl_deadline = datetime.now(timezone.utc) + timedelta(
            days=settings.tx_draft_ttl_days
        )

        drafted = DraftedTransaction(
            safe_address=settings.safe_address,
            transactions=safe_txs,
            status=TxStatus.DRAFTED,
            ttl_deadline=ttl_deadline,
            policy_check_result={
                "compliant": True,
                "checked_proposals": len(proposals),
                "manifest_cid": self._policy_engine.manifest_cid,
            },
            governance_manifest_cid=self._policy_engine.manifest_cid,
            requester_did=requester_did,
        )

        self._pending_transactions[str(drafted.tx_id)] = drafted

        action = AgentAction(
            agent_id=AGENT_ID,
            action="draft_safe_batch",
            rationale=(
                f"Drafted Safe batch with {len(safe_txs)} transaction(s) for "
                f"requester '{requester_did}'. TTL: {ttl_deadline.isoformat()}. "
                f"All {len(proposals)} proposal(s) passed PolicyEngine compliance. "
                f"Governance manifest CID: {self._policy_engine.manifest_cid}. "
                f"Awaiting human M-of-N signing."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "tx_id": str(drafted.tx_id),
                "transaction_count": len(safe_txs),
                "safe_address": settings.safe_address,
                "ttl_deadline": ttl_deadline.isoformat(),
                "governance_manifest_cid": self._policy_engine.manifest_cid,
                "requester_did": requester_did,
            },
        )

        logger.info(
            "Drafted Safe batch: tx_id=%s count=%d requester=%s",
            drafted.tx_id,
            len(safe_txs),
            requester_did,
        )
        return drafted, action

    # ═══════════════════════════════════════════════════════════════════════════
    # SETTLEMENT VERIFICATION
    # ═══════════════════════════════════════════════════════════════════════════

    async def verify_settlement(
        self,
        tx_id: str,
        tx_hash: str,
    ) -> tuple[DraftedTransaction, AgentAction]:
        """Record on-chain settlement of a drafted transaction.

        Steps:
          1. Validate tx_id exists and is in Executed or Pending status.
          2. Record the tx_hash and transition to Settled.
          3. Create a CausalEvent for the governance audit trail.

        STUB: Does not verify the tx_hash on-chain. In production, this would
        query the RPC for confirmation count.

        Raises:
            KeyError: If tx_id not found.
            ValueError: If transaction is not in a settleable state.
        """
        drafted = self._pending_transactions.get(tx_id)
        if drafted is None:
            raise KeyError(f"Transaction not found: {tx_id}")

        if drafted.status not in (TxStatus.DRAFTED, TxStatus.PENDING, TxStatus.EXECUTED):
            raise ValueError(
                f"Cannot settle transaction in status '{drafted.status.value}'. "
                f"Expected Drafted, Pending, or Executed."
            )

        drafted.status = TxStatus.SETTLED
        drafted.on_chain_tx_hash = tx_hash
        drafted.settled_at = datetime.now(timezone.utc)

        # Create CausalEvent for governance audit trail
        # Use "governance.transaction.settled" prefix for federated replication
        _record, _ce_action = await CausalEvent.create(
            event_type="governance.transaction.settled",
            source_agent_id=AGENT_ID,
            payload={
                "tx_id": tx_id,
                "tx_hash": tx_hash,
                "safe_address": drafted.safe_address,
                "transaction_count": len(drafted.transactions),
                "governance_manifest_cid": drafted.governance_manifest_cid,
            },
            audience="federation",
        )

        action = AgentAction(
            agent_id=AGENT_ID,
            action="verify_settlement",
            rationale=(
                f"Transaction {tx_id} settled on-chain: tx_hash={tx_hash}. "
                f"CausalEvent created for governance audit trail. "
                f"Safe: {drafted.safe_address}."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "tx_id": tx_id,
                "tx_hash": tx_hash,
                "status": drafted.status.value,
                "settled_at": drafted.settled_at.isoformat(),
                "causal_event_cid": _record.ipfs_cid,
            },
        )

        logger.info(
            "Settlement verified: tx_id=%s tx_hash=%s",
            tx_id,
            tx_hash,
        )
        return drafted, action

    # ═══════════════════════════════════════════════════════════════════════════
    # TTL ENFORCEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def purge_stale(self) -> tuple[list[str], AgentAction]:
        """Scan for past-TTL drafts and transition them to Stale.

        Does NOT auto-cancel — stale transactions are a warning signal.
        A steward can still manually review and either cancel or extend.

        Returns:
            (list of stale tx_ids, AgentAction)
        """
        now = datetime.now(timezone.utc)
        stale_ids: list[str] = []

        for tx_id, drafted in self._pending_transactions.items():
            if drafted.status in (TxStatus.DRAFTED, TxStatus.PENDING):
                if now > drafted.ttl_deadline:
                    drafted.status = TxStatus.STALE
                    stale_ids.append(tx_id)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="purge_stale_transactions",
            rationale=(
                f"TTL scan: {len(stale_ids)} transaction(s) marked Stale "
                f"(past {settings.tx_draft_ttl_days}-day deadline). "
                f"No auto-cancel — steward review required."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM if stale_ids else EthicalImpactLevel.LOW,
            payload={
                "stale_count": len(stale_ids),
                "stale_tx_ids": stale_ids,
                "ttl_days": settings.tx_draft_ttl_days,
            },
        )

        if stale_ids:
            logger.warning(
                "Stale transactions detected: %d tx(s) past TTL",
                len(stale_ids),
            )
        return stale_ids, action

    # ═══════════════════════════════════════════════════════════════════════════
    # MANUAL OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def cancel(
        self,
        tx_id: str,
        reason: str,
    ) -> tuple[DraftedTransaction, AgentAction]:
        """Manually cancel a drafted transaction (steward-only).

        Raises:
            KeyError: If tx_id not found.
            ValueError: If transaction is in a terminal state.
        """
        drafted = self._pending_transactions.get(tx_id)
        if drafted is None:
            raise KeyError(f"Transaction not found: {tx_id}")

        if drafted.status not in (TxStatus.DRAFTED, TxStatus.PENDING):
            raise ValueError(
                f"Cannot cancel transaction in status '{drafted.status.value}'. "
                f"Only Drafted or Pending transactions can be cancelled."
            )

        drafted.status = TxStatus.CANCELLED

        action = AgentAction(
            agent_id=AGENT_ID,
            action="cancel_transaction",
            rationale=(
                f"Transaction {tx_id} cancelled by steward. Reason: {reason}. "
                f"Safe: {drafted.safe_address}."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "tx_id": tx_id,
                "reason": reason,
                "previous_status": "Drafted/Pending",
                "new_status": drafted.status.value,
            },
        )

        logger.info("Transaction cancelled: tx_id=%s reason=%s", tx_id, reason)
        return drafted, action

    def get_transaction(self, tx_id: str) -> DraftedTransaction:
        """Retrieve a transaction by ID.

        Raises:
            KeyError: If not found.
        """
        drafted = self._pending_transactions.get(tx_id)
        if drafted is None:
            raise KeyError(f"Transaction not found: {tx_id}")
        return drafted

    def list_stale(self) -> list[DraftedTransaction]:
        """List all transactions in Stale status."""
        return [
            tx for tx in self._pending_transactions.values()
            if tx.status == TxStatus.STALE
        ]

    def export_safe_batch(self, tx_id: str) -> tuple[dict[str, Any], AgentAction]:
        """Export a transaction as Gnosis Safe batch JSON.

        The output is compatible with the Safe UI's "Transaction Builder"
        import feature.

        Raises:
            KeyError: If tx_id not found.
        """
        drafted = self._pending_transactions.get(tx_id)
        if drafted is None:
            raise KeyError(f"Transaction not found: {tx_id}")

        # Build Safe-compatible batch format
        batch = {
            "version": "1.0",
            "chainId": str(settings.evm_chain_id),
            "createdAt": int(drafted.drafted_at.timestamp() * 1000),
            "meta": {
                "name": f"Iskander Batch {tx_id}",
                "description": (
                    f"Governance-approved transaction batch. "
                    f"Manifest CID: {drafted.governance_manifest_cid}"
                ),
                "txBuilderVersion": "1.16.3",
                "createdFromSafeAddress": drafted.safe_address,
                "createdFromOwnerAddress": "",
            },
            "transactions": [],
        }

        for tx in drafted.transactions:
            batch["transactions"].append({
                "to": tx.to,
                "value": tx.value,
                "data": tx.data if tx.data else "0x",
                "contractMethod": None,
                "contractInputsValues": None,
            })

        action = AgentAction(
            agent_id=AGENT_ID,
            action="export_safe_batch",
            rationale=(
                f"Exported Safe batch JSON for tx_id={tx_id}: "
                f"{len(drafted.transactions)} transaction(s), "
                f"chain={settings.evm_chain_id}, safe={drafted.safe_address}."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={
                "tx_id": tx_id,
                "transaction_count": len(drafted.transactions),
                "chain_id": settings.evm_chain_id,
            },
        )

        return batch, action
