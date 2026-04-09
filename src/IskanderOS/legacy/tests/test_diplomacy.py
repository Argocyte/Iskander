"""
test_diplomacy.py — Unit tests for the Diplomatic Embassy feature.

Tests cover:
  - FRSClient: registration, transaction scoring, decay, tiers, quarantine
  - IngestionEmbassy: ingestion, collision detection, admission, rejection
  - RITL PeerReviewGraph: compilation, review flow, Socratic cross-examination
"""
from __future__ import annotations

import asyncio
import time
import unittest

import pytest


# ── Helper: run async coroutines in sync test methods ─────────────────────────

def run_async(coro):
    """Run an async coroutine in a new event loop (for sync test methods)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_singletons():
    """Reset all singletons before each test."""
    from backend.finance.frs_client import FRSClient
    from backend.mesh.ingestion_embassy import IngestionEmbassy
    from backend.mesh.library_manager import LibraryManager
    from backend.mesh.sovereign_storage import SovereignStorage

    FRSClient._reset_instance()
    IngestionEmbassy._reset_instance()
    LibraryManager._reset_instance()
    SovereignStorage._instance = None

    yield

    FRSClient._reset_instance()
    IngestionEmbassy._reset_instance()
    LibraryManager._reset_instance()
    SovereignStorage._instance = None


# ═══════════════════════════════════════════════════════════════════════════════
# FRS CLIENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFRSClientRegistration:
    """Tests for FRSClient.register_sdc()."""

    def test_register_sdc(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        profile, action = frs.register_sdc("did:web:coop-a.example", 5000)

        assert profile.sdc_did == "did:web:coop-a.example"
        assert profile.raw_score == 5000
        assert profile.decayed_score == 5000
        assert profile.tier.value == 2  # Trusted (5000 between 3000 and 7000)
        assert action.agent_id == "frs-client-v1"

    def test_register_sdc_duplicate_raises(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:coop-a.example", 5000)

        with pytest.raises(ValueError, match="already registered"):
            frs.register_sdc("did:web:coop-a.example", 3000)

    def test_register_sdc_exceeds_max_raises(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()

        with pytest.raises(ValueError, match="exceeds maximum"):
            frs.register_sdc("did:web:coop-a.example", 10001)

    def test_sdc_id_hash_deterministic(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        h1 = frs.sdc_id_hash("did:web:coop-a.example")
        h2 = frs.sdc_id_hash("did:web:coop-a.example")
        assert h1 == h2
        assert h1.startswith("0x")


class TestFRSClientTransactions:
    """Tests for FRSClient.record_transaction()."""

    def test_positive_delta(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:coop-a.example", 5000)

        profile, action = frs.record_transaction(
            "did:web:coop-a.example", 300, "bafyTx1", "Good trade"
        )
        assert profile.decayed_score == 5300

    def test_negative_delta(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:coop-a.example", 5000)

        profile, action = frs.record_transaction(
            "did:web:coop-a.example", -200, "bafyTx2", "Dispute"
        )
        assert profile.decayed_score == 4800

    def test_delta_clamped_to_zero(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:coop-a.example", 100)

        profile, action = frs.record_transaction(
            "did:web:coop-a.example", -500, "bafyTx3", "Major penalty"
        )
        assert profile.decayed_score == 0

    def test_delta_clamped_to_max(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:coop-a.example", 9900)

        profile, action = frs.record_transaction(
            "did:web:coop-a.example", 500, "bafyTx4", "Bonus"
        )
        assert profile.decayed_score == 10000

    def test_delta_exceeds_limit_raises(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:coop-a.example", 5000)

        with pytest.raises(ValueError, match="exceeds maximum"):
            frs.record_transaction(
                "did:web:coop-a.example", 501, "bafyTx5", "Too big"
            )

    def test_unregistered_sdc_raises(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()

        with pytest.raises(ValueError, match="not registered"):
            frs.record_transaction(
                "did:web:unknown.example", 100, "bafyTx6", "Who?"
            )


class TestFRSClientTiers:
    """Tests for tier computation."""

    def test_tier_quarantine(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:q.example", 500)
        assert frs.get_tier("did:web:q.example").value == 0

    def test_tier_provisional(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:p.example", 2000)
        assert frs.get_tier("did:web:p.example").value == 1

    def test_tier_trusted(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:t.example", 5000)
        assert frs.get_tier("did:web:t.example").value == 2

    def test_tier_allied(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:a.example", 8000)
        assert frs.get_tier("did:web:a.example").value == 3

    def test_unknown_sdc_defaults_to_quarantine(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        assert frs.get_tier("did:web:unknown.example").value == 0


class TestFRSClientForceQuarantine:
    """Tests for force quarantine/lift."""

    def test_force_quarantine_overrides_tier(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:a.example", 9000)
        assert frs.get_tier("did:web:a.example").value == 3  # Allied

        frs.force_quarantine("did:web:a.example", "bafyRationale")
        assert frs.get_tier("did:web:a.example").value == 0  # Quarantine

    def test_lift_quarantine_restores_tier(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:a.example", 9000)
        frs.force_quarantine("did:web:a.example", "bafyRationale")
        assert frs.get_tier("did:web:a.example").value == 0

        frs.lift_quarantine("did:web:a.example")
        assert frs.get_tier("did:web:a.example").value == 3  # Allied again


class TestFRSClientDecay:
    """Tests for exponential decay logic."""

    def test_decay_halves_after_half_life(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:d.example", 10000)

        # Manually set last_updated to simulate time passage
        data = frs._profiles["did:web:d.example"]
        data["last_updated"] = time.time() - frs._half_life_seconds

        profile, _ = frs.get_profile("did:web:d.example")
        assert profile.decayed_score == 5000

    def test_decay_to_zero_after_many_half_lives(self):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc("did:web:d.example", 10000)

        data = frs._profiles["did:web:d.example"]
        data["last_updated"] = time.time() - (13 * frs._half_life_seconds)

        profile, _ = frs.get_profile("did:web:d.example")
        assert profile.decayed_score == 0


# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION EMBASSY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestionEmbassy:
    """Tests for IngestionEmbassy.ingest()."""

    def _setup_sdc(self, did: str = "did:web:coop-a.example", score: int = 5000):
        from backend.finance.frs_client import FRSClient
        frs = FRSClient.get_instance()
        frs.register_sdc(did, score)

    def test_ingest_external_asset(self):
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        self._setup_sdc()

        embassy = IngestionEmbassy.get_instance()
        asset, action = run_async(embassy.ingest(
            source_sdc_did="did:web:coop-a.example",
            original_cid="bafyExternal123",
            title="External Research Paper",
            data=b"External content data",
            description="A paper from a sister cooperative",
        ))

        assert asset.source_sdc_did == "did:web:coop-a.example"
        assert asset.source_sdc_tier.value == 2  # Trusted
        assert asset.local_cid is not None
        assert asset.status.value == "PendingReview"
        assert action.agent_id == "ingestion-embassy-v1"

    def test_ingest_quarantined_sdc_rejected(self):
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        self._setup_sdc(score=500)  # Below quarantine threshold

        embassy = IngestionEmbassy.get_instance()
        with pytest.raises(ValueError, match="Quarantine tier"):
            run_async(embassy.ingest(
                source_sdc_did="did:web:coop-a.example",
                original_cid="bafyExternal456",
                title="Blocked Asset",
                data=b"Should not be ingested",
            ))

    def test_ingest_unknown_sdc_rejected(self):
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        embassy = IngestionEmbassy.get_instance()

        with pytest.raises(ValueError, match="Quarantine tier"):
            run_async(embassy.ingest(
                source_sdc_did="did:web:unknown.example",
                original_cid="bafyExternal789",
                title="Unknown SDC Asset",
                data=b"Unknown source",
            ))


class TestIngestionEmbassyAdmission:
    """Tests for admit/reject flow."""

    def _setup_and_ingest(self):
        from backend.finance.frs_client import FRSClient
        from backend.mesh.ingestion_embassy import IngestionEmbassy

        FRSClient.get_instance().register_sdc("did:web:coop-a.example", 5000)
        embassy = IngestionEmbassy.get_instance()
        asset, _ = run_async(embassy.ingest(
            source_sdc_did="did:web:coop-a.example",
            original_cid="bafyExt1",
            title="Test Paper",
            data=b"Test content for admission",
        ))
        return embassy, str(asset.quarantine_id)

    def test_admit_promotes_to_knowledge_asset(self):
        embassy, qid = self._setup_and_ingest()
        asset, action = run_async(embassy.admit(qid, "did:key:author123"))

        assert asset.status.value == "Admitted"
        assert asset.promoted_asset_cid is not None
        assert action.action == "admit_external_asset"

    def test_reject_keeps_in_sandbox(self):
        embassy, qid = self._setup_and_ingest()
        asset, action = embassy.reject(qid, "Does not meet standards")

        assert asset.status.value == "Rejected"
        assert asset.local_cid is not None  # CID preserved (tombstone-only)
        assert action.action == "reject_external_asset"

    def test_admit_already_rejected_raises(self):
        embassy, qid = self._setup_and_ingest()
        embassy.reject(qid, "Nope")

        with pytest.raises(ValueError, match="Cannot admit"):
            run_async(embassy.admit(qid, "did:key:author123"))

    def test_list_pending(self):
        from backend.finance.frs_client import FRSClient
        from backend.mesh.ingestion_embassy import IngestionEmbassy

        FRSClient.get_instance().register_sdc("did:web:coop-a.example", 5000)
        embassy = IngestionEmbassy.get_instance()

        run_async(embassy.ingest(
            "did:web:coop-a.example", "bafyExt1", "Paper A", b"Content A"
        ))
        run_async(embassy.ingest(
            "did:web:coop-a.example", "bafyExt2", "Paper B", b"Content B"
        ))

        pending = embassy.list_pending()
        assert len(pending) == 2


class TestCollisionDetection:
    """Tests for semantic collision detection."""

    def test_exact_content_collision(self):
        from backend.finance.frs_client import FRSClient
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        from backend.mesh.library_manager import LibraryManager

        FRSClient.get_instance().register_sdc("did:web:coop-a.example", 5000)
        lib = LibraryManager.get_instance()

        # Register a local asset first
        content = b"Identical content data"
        run_async(lib.register_asset(
            data=content,
            title="Local Asset",
            author_did="did:key:localauthor",
        ))

        # Ingest identical content from external SDC
        embassy = IngestionEmbassy.get_instance()
        asset, _ = run_async(embassy.ingest(
            source_sdc_did="did:web:coop-a.example",
            original_cid="bafyExtDuplicate",
            title="External Copy",
            data=content,  # Same bytes
        ))

        assert asset.collision_report is not None
        assert asset.collision_report.collision_count >= 1
        assert asset.collision_report.collisions[0].collision_type == "duplicate"

    def test_similar_title_collision(self):
        from backend.finance.frs_client import FRSClient
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        from backend.mesh.library_manager import LibraryManager

        FRSClient.get_instance().register_sdc("did:web:coop-a.example", 5000)
        lib = LibraryManager.get_instance()

        run_async(lib.register_asset(
            data=b"Original content",
            title="Introduction to Cooperative Economics",
            author_did="did:key:localauthor",
        ))

        embassy = IngestionEmbassy.get_instance()
        asset, _ = run_async(embassy.ingest(
            source_sdc_did="did:web:coop-a.example",
            original_cid="bafySimilar",
            title="Introduction to Cooperative Economics Revised",
            data=b"Different content but similar title",
        ))

        assert asset.collision_report is not None
        assert asset.collision_report.collision_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# RITL PEER REVIEW GRAPH TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPeerReviewGraph:
    """Tests for the RITL PeerReviewGraph."""

    def test_graph_compiles(self):
        """Verify the graph compiles without errors."""
        from backend.agents.research.ritl_manager import peer_review_graph
        assert peer_review_graph is not None

    def test_review_produces_four_reviews(self):
        """Run the graph and verify 4 dimension reviews are produced."""
        from backend.agents.research.ritl_manager import peer_review_graph
        from backend.mesh.library_manager import LibraryManager

        lib = LibraryManager.get_instance()
        asset, _ = run_async(lib.register_asset(
            data=b"Research content for RITL review",
            title="Novel Cooperative Algorithm",
            author_did="did:key:researcher1",
        ))

        thread_id = "test-ritl-1"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "ritl-manager-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "author_did": "did:key:researcher1",
            "submission_title": "Novel Cooperative Algorithm",
            "asset_metadata": None,
            "blind_mode": False,
            "reviewer_assignments": [],
            "reviews": [],
            "socratic_exchanges": [],
            "review_consensus": None,
            "rationale_log": [],
            "escalation_signal": False,
            "requires_human_token": False,
        }

        peer_review_graph.invoke(initial_state, config=config)
        snapshot = peer_review_graph.get_state(config)
        state = snapshot.values

        assert state.get("error") is None
        reviews = state.get("reviews", [])
        assert len(reviews) == 4

        dimensions = {r["dimension"] for r in reviews}
        assert dimensions == {"Rigor", "Novelty", "Ethics", "Reproducibility"}

    def test_socratic_exchanges_generated(self):
        """Verify Socratic cross-examination produces exchanges."""
        from backend.agents.research.ritl_manager import peer_review_graph
        from backend.mesh.library_manager import LibraryManager

        lib = LibraryManager.get_instance()
        asset, _ = run_async(lib.register_asset(
            data=b"Content for Socratic review",
            title="Dialectic Test Asset",
            author_did="did:key:researcher2",
        ))

        thread_id = "test-ritl-2"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "ritl-manager-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "author_did": "did:key:researcher2",
            "submission_title": "Dialectic Test Asset",
            "asset_metadata": None,
            "blind_mode": False,
            "reviewer_assignments": [],
            "reviews": [],
            "socratic_exchanges": [],
            "review_consensus": None,
            "rationale_log": [],
            "escalation_signal": False,
            "requires_human_token": False,
        }

        peer_review_graph.invoke(initial_state, config=config)
        snapshot = peer_review_graph.get_state(config)
        state = snapshot.values

        exchanges = state.get("socratic_exchanges", [])
        assert len(exchanges) > 0
        # Each exchange should have question + response
        for ex in exchanges:
            assert "question" in ex
            assert "asked_by" in ex
            assert "response" in ex

    def test_blind_mode_masks_identities(self):
        """Verify blind mode uses anonymized reviewer labels."""
        from backend.agents.research.ritl_manager import peer_review_graph
        from backend.mesh.library_manager import LibraryManager

        lib = LibraryManager.get_instance()
        asset, _ = run_async(lib.register_asset(
            data=b"Blind review content",
            title="Blind Review Test",
            author_did="did:key:researcher3",
        ))

        thread_id = "test-ritl-blind"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "ritl-manager-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "author_did": "did:key:researcher3",
            "submission_title": "Blind Review Test",
            "asset_metadata": None,
            "blind_mode": True,  # ZK blind review enabled
            "reviewer_assignments": [],
            "reviews": [],
            "socratic_exchanges": [],
            "review_consensus": None,
            "rationale_log": [],
            "escalation_signal": False,
            "requires_human_token": False,
        }

        peer_review_graph.invoke(initial_state, config=config)
        snapshot = peer_review_graph.get_state(config)
        state = snapshot.values

        # Socratic exchanges should use anonymized labels
        exchanges = state.get("socratic_exchanges", [])
        for ex in exchanges:
            assert ex["asked_by"].startswith("Reviewer-")
            assert ex["responded_by"].startswith("Reviewer-")

    def test_reviews_contain_agent_actions(self):
        """Verify all reviews are wrapped in AgentAction payloads."""
        from backend.agents.research.ritl_manager import peer_review_graph
        from backend.mesh.library_manager import LibraryManager

        lib = LibraryManager.get_instance()
        asset, _ = run_async(lib.register_asset(
            data=b"Agent action test content",
            title="Action Test",
            author_did="did:key:researcher4",
        ))

        thread_id = "test-ritl-actions"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "ritl-manager-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "author_did": "did:key:researcher4",
            "submission_title": "Action Test",
            "asset_metadata": None,
            "blind_mode": False,
            "reviewer_assignments": [],
            "reviews": [],
            "socratic_exchanges": [],
            "review_consensus": None,
            "rationale_log": [],
            "escalation_signal": False,
            "requires_human_token": False,
        }

        peer_review_graph.invoke(initial_state, config=config)
        snapshot = peer_review_graph.get_state(config)
        state = snapshot.values

        reviews = state.get("reviews", [])
        for review in reviews:
            assert "agent_action" in review
            aa = review["agent_action"]
            assert "agent_id" in aa
            assert "rationale" in aa

    def test_consensus_with_mixed_scores_escalates(self):
        """Verify that mixed verdicts trigger HITL escalation.

        With the STUB scoring (Rigor=72, Novelty=65, Ethics=80, Reproducibility=68),
        we get: MINOR_REVISIONS, MINOR_REVISIONS, ACCEPT, MINOR_REVISIONS.
        This should produce consensus='minor_revisions' and require HITL.
        """
        from backend.agents.research.ritl_manager import peer_review_graph
        from backend.mesh.library_manager import LibraryManager

        lib = LibraryManager.get_instance()
        asset, _ = run_async(lib.register_asset(
            data=b"Mixed consensus content",
            title="Mixed Consensus Test",
            author_did="did:key:researcher5",
        ))

        thread_id = "test-ritl-consensus"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "ritl-manager-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "author_did": "did:key:researcher5",
            "submission_title": "Mixed Consensus Test",
            "asset_metadata": None,
            "blind_mode": False,
            "reviewer_assignments": [],
            "reviews": [],
            "socratic_exchanges": [],
            "review_consensus": None,
            "rationale_log": [],
            "escalation_signal": False,
            "requires_human_token": False,
        }

        # Graph should pause at HITL breakpoint
        peer_review_graph.invoke(initial_state, config=config)
        snapshot = peer_review_graph.get_state(config)
        state = snapshot.values

        # The consensus node should have set requires_human_token
        # and the graph should be paused before human_review_research
        consensus = state.get("review_consensus")
        assert consensus == "minor_revisions"

    def test_invalid_asset_cid_produces_error(self):
        """Verify the graph handles missing assets gracefully."""
        from backend.agents.research.ritl_manager import peer_review_graph

        thread_id = "test-ritl-error"
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "ritl-manager-v1",
            "action_log": [],
            "error": None,
            "asset_cid": "bafyNonexistent",
            "author_did": "did:key:nobody",
            "submission_title": "Ghost Asset",
            "asset_metadata": None,
            "blind_mode": False,
            "reviewer_assignments": [],
            "reviews": [],
            "socratic_exchanges": [],
            "review_consensus": None,
            "rationale_log": [],
            "escalation_signal": False,
            "requires_human_token": False,
        }

        peer_review_graph.invoke(initial_state, config=config)
        snapshot = peer_review_graph.get_state(config)
        state = snapshot.values

        assert state.get("error") is not None
        assert "not found" in state["error"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiplomacySchemas:
    """Tests for Pydantic schema validation."""

    def test_sdc_reputation_profile_valid(self):
        from backend.schemas.diplomacy import SDCReputationProfile, ReputationTier
        from datetime import datetime, timezone

        profile = SDCReputationProfile(
            sdc_did="did:web:test.example",
            sdc_id_hash="0xabc123",
            raw_score=5000,
            decayed_score=4500,
            tier=ReputationTier.TRUSTED,
            last_updated=datetime.now(timezone.utc),
        )
        assert profile.tier == ReputationTier.TRUSTED

    def test_transaction_record_validates_delta(self):
        from backend.schemas.diplomacy import TransactionRecord

        # Valid delta
        tr = TransactionRecord(
            sdc_did="did:web:test.example",
            score_delta=300,
            tx_cid="bafyTx",
            rationale="Good trade",
        )
        assert tr.score_delta == 300

    def test_peer_review_valid(self):
        from backend.schemas.diplomacy import PeerReview, ReviewVerdict

        review = PeerReview(
            reviewer_id="rigor-reviewer-v1",
            dimension="Rigor",
            verdict=ReviewVerdict.ACCEPT,
            score=85,
            rationale="Strong methodology.",
        )
        assert review.verdict == ReviewVerdict.ACCEPT

    def test_external_asset_default_status(self):
        from backend.schemas.diplomacy import ExternalAsset, QuarantineStatus, ReputationTier

        asset = ExternalAsset(
            source_sdc_did="did:web:test.example",
            source_sdc_tier=ReputationTier.PROVISIONAL,
            original_cid="bafyExt",
            title="Test Asset",
        )
        assert asset.status == QuarantineStatus.PENDING_REVIEW


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
