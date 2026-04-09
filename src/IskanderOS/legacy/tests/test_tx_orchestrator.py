"""
Tests for the TxOrchestrator — Safe multi-sig batch drafting with TTL.

Covers:
  - Batch drafting with PolicyEngine compliance gate
  - Settlement verification and CausalEvent creation
  - TTL enforcement (stale detection)
  - Manual cancellation
  - Safe batch JSON export format
  - OperationalComplianceViolation on policy failure
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.finance.tx_orchestrator import TxOrchestrator
from backend.governance.policy_engine import PolicyEngine
from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.compliance import (
    DraftedTransaction,
    OperationalComplianceViolation,
    TxStatus,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def run_async(coro):
    """Run an async coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_manifest() -> dict:
    """Minimal governance manifest for testing."""
    return {
        "version": 1,
        "constitutional_core": [
            "anti_extractive",
            "democratic_control",
            "transparency",
            "open_membership",
        ],
        "policies": [
            {
                "rule_id": "max_single_payment",
                "description": "No payment above 100k",
                "constraint_type": "MaxValue",
                "value": "100000",
                "applies_to": [],
            },
            {
                "rule_id": "deny_auto_mint",
                "description": "No agent minting",
                "constraint_type": "Deny",
                "value": "mint",
                "applies_to": [],
            },
        ],
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fresh_singletons(monkeypatch):
    """Reset all singletons before and after each test."""
    PolicyEngine._reset_instance()
    TxOrchestrator._reset_instance()
    SovereignStorage._instance = None

    # Patch _broadcast_and_collect to return fake receipts (stub returns 0
    # receipts which triggers InsufficientReplication for governance events).
    from backend.mesh.sovereign_storage import PinReceipt

    async def _mock_broadcast(self, cid, min_replicas):
        return [
            PinReceipt(peer_did=f"did:key:peer{i}", cid=cid, timestamp="now")
            for i in range(min_replicas)
        ]

    monkeypatch.setattr(SovereignStorage, "_broadcast_and_collect", _mock_broadcast)

    # Load manifest so PolicyEngine is ready
    engine = PolicyEngine.get_instance()
    engine.load_manifest(manifest_dict=_make_manifest())

    yield

    PolicyEngine._reset_instance()
    TxOrchestrator._reset_instance()
    SovereignStorage._instance = None


# ═════════════════════════════════════════════════════════════════════════════
# BATCH DRAFTING
# ═════════════════════════════════════════════════════════════════════════════


class TestDraftBatch:
    """Tests for draft_batch()."""

    def test_draft_batch_creates_transaction(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": "0x1234567890abcdef1234567890abcdef12345678",
                "value_wei": 1000,
            }
        ]
        drafted, action = orch.draft_batch(proposals, "did:key:requester")

        assert isinstance(drafted, DraftedTransaction)
        assert drafted.status == TxStatus.DRAFTED
        assert len(drafted.transactions) == 1
        assert drafted.governance_manifest_cid is not None
        assert drafted.requester_did == "did:key:requester"

    def test_draft_batch_stores_in_pending(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": "0x1111111111111111111111111111111111111111",
                "value_wei": 500,
            }
        ]
        drafted, _action = orch.draft_batch(proposals, "did:key:test")

        # Should be retrievable
        retrieved = orch.get_transaction(str(drafted.tx_id))
        assert retrieved.tx_id == drafted.tx_id

    def test_draft_batch_multiple_proposals(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'1' * 40}",
                "value_wei": 100,
            },
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'2' * 40}",
                "value_wei": 200,
            },
        ]
        drafted, _action = orch.draft_batch(proposals, "did:key:batch")
        assert len(drafted.transactions) == 2

    def test_draft_batch_glass_box_action(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'a' * 40}",
                "value_wei": 100,
            }
        ]
        _drafted, action = orch.draft_batch(proposals, "did:key:gb")
        assert action.agent_id == "tx-orchestrator-v1"
        assert action.action == "draft_safe_batch"
        assert "governance_manifest_cid" in action.payload

    def test_draft_batch_ttl_set(self):
        orch = TxOrchestrator.get_instance()
        before = datetime.now(timezone.utc)
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'b' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _action = orch.draft_batch(proposals, "did:key:ttl")
        assert drafted.ttl_deadline > before


# ═════════════════════════════════════════════════════════════════════════════
# POLICY CHECK BEFORE DRAFT
# ═════════════════════════════════════════════════════════════════════════════


class TestPolicyGate:
    """Tests proving PolicyEngine blocks non-compliant drafts."""

    def test_policy_violation_blocks_draft(self):
        orch = TxOrchestrator.get_instance()
        # Proposal that violates deny_auto_mint
        proposals = [
            {
                "agent_id": "any-agent",
                "type": "mint",  # denied by manifest
                "to": f"0x{'c' * 40}",
                "value_wei": 100,
            }
        ]
        with pytest.raises(OperationalComplianceViolation):
            orch.draft_batch(proposals, "did:key:bad")

    def test_max_value_violation_blocks_draft(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'d' * 40}",
                "single_payment": 200000,  # exceeds 100k cap
            }
        ]
        with pytest.raises(OperationalComplianceViolation):
            orch.draft_batch(proposals, "did:key:toobig")


# ═════════════════════════════════════════════════════════════════════════════
# SETTLEMENT
# ═════════════════════════════════════════════════════════════════════════════


class TestSettlement:
    """Tests for verify_settlement()."""

    def test_verify_settlement_updates_status(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'e' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _action = orch.draft_batch(proposals, "did:key:settle")
        tx_id = str(drafted.tx_id)
        tx_hash = "0xabcdef1234567890"

        settled, action = run_async(
            orch.verify_settlement(tx_id, tx_hash)
        )
        assert settled.status == TxStatus.SETTLED
        assert settled.on_chain_tx_hash == tx_hash
        assert settled.settled_at is not None
        assert "causal_event_cid" in action.payload

    def test_settle_nonexistent_raises(self):
        orch = TxOrchestrator.get_instance()
        with pytest.raises(KeyError):
            run_async(orch.verify_settlement("nonexistent-id", "0xabc"))

    def test_settle_already_settled_raises(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'f' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:double")
        tx_id = str(drafted.tx_id)

        run_async(orch.verify_settlement(tx_id, "0xhash1"))

        with pytest.raises(ValueError, match="Cannot settle"):
            run_async(orch.verify_settlement(tx_id, "0xhash2"))


# ═════════════════════════════════════════════════════════════════════════════
# TTL ENFORCEMENT
# ═════════════════════════════════════════════════════════════════════════════


class TestTTLEnforcement:
    """Tests for stale detection."""

    def test_stale_detection(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'1' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:stale")

        # Force TTL to be in the past
        drafted.ttl_deadline = datetime.now(timezone.utc) - timedelta(days=1)

        stale_ids, action = orch.purge_stale()
        assert str(drafted.tx_id) in stale_ids
        assert drafted.status == TxStatus.STALE

    def test_non_expired_not_stale(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'2' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:fresh")
        # TTL is in the future — should NOT be stale

        stale_ids, _action = orch.purge_stale()
        assert str(drafted.tx_id) not in stale_ids
        assert drafted.status == TxStatus.DRAFTED


# ═════════════════════════════════════════════════════════════════════════════
# CANCELLATION
# ═════════════════════════════════════════════════════════════════════════════


class TestCancellation:
    """Tests for manual cancel()."""

    def test_cancel_transitions_to_cancelled(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'3' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:cancel")
        tx_id = str(drafted.tx_id)

        cancelled, action = orch.cancel(tx_id, "Changed plans")
        assert cancelled.status == TxStatus.CANCELLED
        assert "Changed plans" in action.rationale

    def test_cancel_settled_raises(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'4' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:settled")
        tx_id = str(drafted.tx_id)
        run_async(orch.verify_settlement(tx_id, "0xhash"))

        with pytest.raises(ValueError, match="Cannot cancel"):
            orch.cancel(tx_id, "too late")

    def test_cancel_nonexistent_raises(self):
        orch = TxOrchestrator.get_instance()
        with pytest.raises(KeyError):
            orch.cancel("nonexistent", "no such tx")


# ═════════════════════════════════════════════════════════════════════════════
# SAFE BATCH EXPORT
# ═════════════════════════════════════════════════════════════════════════════


class TestSafeBatchExport:
    """Tests for export_safe_batch()."""

    def test_export_safe_batch_format(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": "0x1234567890abcdef1234567890abcdef12345678",
                "value_wei": 1000,
            },
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "value_wei": 2000,
            },
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:export")
        tx_id = str(drafted.tx_id)

        batch, action = orch.export_safe_batch(tx_id)

        # Validate Safe batch structure
        assert batch["version"] == "1.0"
        assert "chainId" in batch
        assert "meta" in batch
        assert "transactions" in batch
        assert len(batch["transactions"]) == 2

        # Each tx should have Safe-compatible fields
        for tx in batch["transactions"]:
            assert "to" in tx
            assert "value" in tx
            assert "data" in tx

    def test_export_nonexistent_raises(self):
        orch = TxOrchestrator.get_instance()
        with pytest.raises(KeyError):
            orch.export_safe_batch("nonexistent")

    def test_export_includes_manifest_cid_in_meta(self):
        orch = TxOrchestrator.get_instance()
        proposals = [
            {
                "agent_id": "treasurer-agent-v1",
                "type": "payment",
                "to": f"0x{'5' * 40}",
                "value_wei": 100,
            }
        ]
        drafted, _ = orch.draft_batch(proposals, "did:key:meta")
        batch, _ = orch.export_safe_batch(str(drafted.tx_id))
        assert "Manifest CID" in batch["meta"]["description"]
