"""
test_library.py — Unit tests for Iskander Knowledge Commons (IKC).

Tests the LibraryManager (asset registration, dependency graph, status
transitions, break-glass) and the CuratorNetwork LangGraph (curator
votes, consensus logic, HITL escalation, tombstone-only invariant).
"""
from __future__ import annotations

import asyncio
import sys
import os

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.mesh.library_manager import LibraryManager
from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.knowledge import KnowledgeAssetStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

def run(coro):
    """Run an async coroutine synchronously for tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def fresh_singletons():
    """Reset singletons before each test."""
    LibraryManager._reset_instance()
    SovereignStorage._instance = None  # No _reset_instance method
    yield
    LibraryManager._reset_instance()
    SovereignStorage._instance = None


def _register(lib, data=b"test content", title="Test Asset", author="did:test:alice",
              deps=None, desc=None):
    """Shorthand to register an asset synchronously."""
    return run(lib.register_asset(
        data=data,
        title=title,
        author_did=author,
        description=desc,
        dependency_manifest=deps,
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# LibraryManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLibraryManagerRegistration:
    """Tests for asset registration and IPFS pinning."""

    def test_register_asset_returns_cid_and_action(self):
        """register_asset pins to IPFS and returns KnowledgeAsset + AgentAction."""
        lib = LibraryManager.get_instance()
        asset, action = _register(lib)

        assert asset.cid.startswith("Qm")
        assert asset.status == KnowledgeAssetStatus.ACTIVE
        assert asset.version == 1
        assert asset.title == "Test Asset"
        assert asset.author_did == "did:test:alice"
        assert action.agent_id == "library-manager-v1"
        assert action.action == "register_knowledge_asset"

    def test_register_asset_content_hash(self):
        """Content hash is SHA-256 of the raw data."""
        import hashlib
        data = b"unique content for hashing"
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib, data=data)

        expected = hashlib.sha256(data).hexdigest()
        assert asset.content_hash == expected

    def test_register_with_dependencies(self):
        """Dependencies are recorded in forward and reverse indexes."""
        lib = LibraryManager.get_instance()
        # Register two base assets
        base_a, _ = _register(lib, data=b"base A", title="Base A")
        base_b, _ = _register(lib, data=b"base B", title="Base B")

        # Register dependent asset
        dep, _ = _register(
            lib, data=b"dependent", title="Dependent",
            deps=[base_a.cid, base_b.cid],
        )

        # Check forward index
        assert base_a.cid in lib._dependencies[dep.cid]
        assert base_b.cid in lib._dependencies[dep.cid]

        # Check reverse index
        assert dep.cid in lib._dependents[base_a.cid]
        assert dep.cid in lib._dependents[base_b.cid]

    def test_missing_dependency_rejected(self):
        """dependency_manifest referencing unknown CID raises ValueError."""
        lib = LibraryManager.get_instance()
        with pytest.raises(ValueError, match="not found in registry"):
            _register(lib, deps=["QmNONEXISTENT"])

    def test_get_asset(self):
        """get_asset returns the registered asset."""
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib)
        retrieved, action = run(lib.get_asset(asset.cid))

        assert retrieved.cid == asset.cid
        assert retrieved.title == asset.title
        assert action.ethical_impact.value == "low"

    def test_get_asset_not_found(self):
        """get_asset raises KeyError for unknown CID."""
        lib = LibraryManager.get_instance()
        with pytest.raises(KeyError):
            run(lib.get_asset("QmNONEXISTENT"))


class TestLibraryManagerStatus:
    """Tests for status transitions (tombstone-only invariant)."""

    def test_update_status_tombstone_only(self):
        """After tombstoning, the original CID is still retrievable."""
        lib = LibraryManager.get_instance()
        storage = SovereignStorage.get_instance()

        asset, _ = _register(lib)
        original_cid = asset.cid

        # Tombstone the asset
        tag, action = run(lib.update_status(
            cid=original_cid,
            new_status=KnowledgeAssetStatus.TOMBSTONED,
            changed_by="did:test:steward",
            rationale="Outdated content",
        ))

        # Original CID is still in IPFS (tombstone-only!)
        plaintext, _ = run(storage.cat(original_cid))
        assert plaintext == b"test content"

        # Asset status is updated
        updated, _ = run(lib.get_asset(original_cid))
        assert updated.status == KnowledgeAssetStatus.TOMBSTONED
        assert updated.metadata_cid is not None

    def test_status_tag_pinned_to_ipfs(self):
        """StatusTag CID is stored in asset's metadata_cid."""
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib)

        tag, _ = run(lib.update_status(
            cid=asset.cid,
            new_status=KnowledgeAssetStatus.LEGACY,
            changed_by="did:test:steward",
            rationale="Superseded by v2",
        ))

        updated, _ = run(lib.get_asset(asset.cid))
        assert updated.metadata_cid is not None
        assert updated.metadata_cid.startswith("Qm")

    def test_invalid_transition_rejected(self):
        """Tombstoned → Active raises ValueError (terminal state)."""
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib)

        # First tombstone it
        run(lib.update_status(
            asset.cid, KnowledgeAssetStatus.TOMBSTONED,
            "did:test:steward", "done",
        ))

        # Try to revive — should fail
        with pytest.raises(ValueError, match="Invalid status transition"):
            run(lib.update_status(
                asset.cid, KnowledgeAssetStatus.ACTIVE,
                "did:test:steward", "try to revive",
            ))

    def test_valid_transitions(self):
        """Valid transitions succeed: Active → Legacy → Active."""
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib)

        # Active → Legacy
        run(lib.update_status(
            asset.cid, KnowledgeAssetStatus.LEGACY,
            "did:test:steward", "deprecating",
        ))
        updated, _ = run(lib.get_asset(asset.cid))
        assert updated.status == KnowledgeAssetStatus.LEGACY

        # Legacy → Active
        run(lib.update_status(
            asset.cid, KnowledgeAssetStatus.ACTIVE,
            "did:test:steward", "reviving",
        ))
        updated, _ = run(lib.get_asset(asset.cid))
        assert updated.status == KnowledgeAssetStatus.ACTIVE


class TestLibraryManagerDownstreamImpact:
    """Tests for check_downstream_impact (dependency traversal)."""

    def test_downstream_impact_finds_dependents(self):
        """A depends on B: check_downstream_impact(B) returns [A.cid]."""
        lib = LibraryManager.get_instance()
        base, _ = _register(lib, data=b"base", title="Base")
        dependent, _ = _register(
            lib, data=b"dep", title="Dependent", deps=[base.cid],
        )

        deps, action = run(lib.check_downstream_impact(base.cid))
        assert dependent.cid in deps

    def test_downstream_impact_empty_for_leaf(self):
        """Leaf asset with no dependents returns empty list."""
        lib = LibraryManager.get_instance()
        leaf, _ = _register(lib, data=b"leaf", title="Leaf")

        deps, _ = run(lib.check_downstream_impact(leaf.cid))
        assert deps == []

    def test_downstream_impact_only_active(self):
        """Only ACTIVE dependents are returned."""
        lib = LibraryManager.get_instance()
        base, _ = _register(lib, data=b"base", title="Base")
        dep1, _ = _register(lib, data=b"dep1", title="Dep1", deps=[base.cid])
        dep2, _ = _register(lib, data=b"dep2", title="Dep2", deps=[base.cid])

        # Tombstone dep1
        run(lib.update_status(
            dep1.cid, KnowledgeAssetStatus.TOMBSTONED,
            "did:test:steward", "old",
        ))

        deps, _ = run(lib.check_downstream_impact(base.cid))
        assert dep1.cid not in deps
        assert dep2.cid in deps


class TestDependencyGraph:
    """Tests for cycle detection in the dependency graph."""

    def test_simple_cycle_detected(self):
        """B depends on A. Adding A→B would create cycle: detected."""
        lib = LibraryManager.get_instance()
        a, _ = _register(lib, data=b"a", title="A")
        b, _ = _register(lib, data=b"b", title="B", deps=[a.cid])

        # Would adding A → B create a cycle?
        # DFS from B following forward deps: B → A. A == from_cid. Cycle!
        assert lib._detect_cycle(a.cid, b.cid) is True
        # Converse: B → A already exists, adding B → A is redundant, not a new cycle
        # (but _detect_cycle checks reachability of from_cid from to_cid)

    def test_transitive_cycle_detected(self):
        """A→B→C, then C→A is detected."""
        lib = LibraryManager.get_instance()
        a, _ = _register(lib, data=b"a", title="A")
        b, _ = _register(lib, data=b"b", title="B", deps=[a.cid])
        c, _ = _register(lib, data=b"c", title="C", deps=[b.cid])

        # Try to make a new asset that depends on c AND that c depends on
        # The cycle detection is: does adding new_cid → dep_cid create a cycle?
        # For a new asset, it can't create a cycle since it has no dependents.
        # True cycle: we'd need to add c → a, but c is already registered.
        # Test _detect_cycle directly:
        assert lib._detect_cycle(a.cid, c.cid) is True  # c → b → a: a is reachable
        assert lib._detect_cycle(a.cid, b.cid) is True   # b → a: a is reachable

    def test_diamond_not_false_positive(self):
        """A→B, A→C, B→D, C→D is a valid diamond — not a cycle."""
        lib = LibraryManager.get_instance()
        d, _ = _register(lib, data=b"d", title="D")
        b, _ = _register(lib, data=b"b", title="B", deps=[d.cid])
        c, _ = _register(lib, data=b"c", title="C", deps=[d.cid])
        a, _ = _register(lib, data=b"a", title="A", deps=[b.cid, c.cid])

        # No cycle — should succeed
        assert a.cid in lib._registry

    def test_self_reference_rejected(self):
        """Self-reference is detected by _detect_cycle."""
        lib = LibraryManager.get_instance()
        # Can't self-reference at registration because CID doesn't exist yet.
        # Test the internal method directly:
        assert lib._detect_cycle("QmSELF", "QmSELF") is True


class TestBreakGlass:
    """Tests for the Break-Glass mechanism."""

    def test_break_glass_blocks_updates(self):
        """update_status raises ValueError while break-glass is active."""
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib)

        lib.activate_break_glass()

        with pytest.raises(ValueError, match="Break-Glass is active"):
            run(lib.update_status(
                asset.cid, KnowledgeAssetStatus.LEGACY,
                "did:test:steward", "test",
            ))

    def test_break_glass_activate_deactivate(self):
        """activate/deactivate toggle works correctly."""
        lib = LibraryManager.get_instance()

        assert lib.break_glass_active is False

        action = lib.activate_break_glass()
        assert lib.break_glass_active is True
        assert action.ethical_impact.value == "high"

        action = lib.deactivate_break_glass()
        assert lib.break_glass_active is False

    def test_break_glass_resumes_after_deactivation(self):
        """After deactivation, updates work again."""
        lib = LibraryManager.get_instance()
        asset, _ = _register(lib)

        lib.activate_break_glass()
        lib.deactivate_break_glass()
        # Bypass cooldown for test
        lib._break_glass_last_deactivated = 0

        # Should succeed now
        tag, _ = run(lib.update_status(
            asset.cid, KnowledgeAssetStatus.LEGACY,
            "did:test:steward", "test after resume",
        ))
        assert tag.new_status == KnowledgeAssetStatus.LEGACY


# ═══════════════════════════════════════════════════════════════════════════════
# CuratorNetwork Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCuratorNetwork:
    """Tests for the CuratorDebate LangGraph."""

    def test_graph_compiles(self):
        """curator_network_graph is a valid compiled StateGraph."""
        from backend.agents.library.curator_network import curator_network_graph
        assert curator_network_graph is not None

    def test_downstream_deps_block_tombstone(self):
        """Asset with active dependents → rejected_downstream_deps."""
        from backend.agents.library.curator_network import curator_network_graph
        from uuid import uuid4

        lib = LibraryManager.get_instance()
        base, _ = _register(lib, data=b"base", title="Base")
        dep, _ = _register(lib, data=b"dep", title="Dep", deps=[base.cid])

        thread_id = str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "curator-network-v1",
            "action_log": [],
            "error": None,
            "asset_cid": base.cid,
            "proposed_status": "Tombstoned",
            "proposer_rationale": "Outdated",
            "asset_metadata": None,
            "downstream_deps": [],
            "dependency_check_passed": True,
            "votes": [],
            "consensus_status": "in_progress",
            "rationale_log": [],
            "escalation_signal": False,
            "break_glass_active": False,
            "requires_human_token": False,
        }

        curator_network_graph.invoke(initial_state, config=config)
        state = curator_network_graph.get_state(config).values

        assert state["consensus_status"] == "rejected_downstream_deps"
        assert state["dependency_check_passed"] is False

    def test_break_glass_pauses_debate(self):
        """When break_glass_active, debate enters 'paused' state."""
        from backend.agents.library.curator_network import curator_network_graph
        from uuid import uuid4

        lib = LibraryManager.get_instance()
        asset, _ = _register(lib, data=b"content", title="Test")
        lib.activate_break_glass()

        thread_id = str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "curator-network-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "proposed_status": "Legacy",
            "proposer_rationale": "Test break glass",
            "asset_metadata": None,
            "downstream_deps": [],
            "dependency_check_passed": True,
            "votes": [],
            "consensus_status": "in_progress",
            "rationale_log": [],
            "escalation_signal": False,
            "break_glass_active": False,
            "requires_human_token": False,
        }

        curator_network_graph.invoke(initial_state, config=config)
        state = curator_network_graph.get_state(config).values

        assert state["consensus_status"] == "paused"
        assert state["break_glass_active"] is True

    def test_votes_wrapped_in_agent_action(self):
        """All 3 votes contain valid AgentAction payloads."""
        from backend.agents.library.curator_network import curator_network_graph
        from uuid import uuid4

        lib = LibraryManager.get_instance()
        asset, _ = _register(lib, data=b"content", title="Vote Test")

        thread_id = str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "curator-network-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "proposed_status": "Legacy",
            "proposer_rationale": "Testing votes with detailed rationale for ethics check",
            "asset_metadata": None,
            "downstream_deps": [],
            "dependency_check_passed": True,
            "votes": [],
            "consensus_status": "in_progress",
            "rationale_log": [],
            "escalation_signal": False,
            "break_glass_active": False,
            "requires_human_token": False,
        }

        curator_network_graph.invoke(initial_state, config=config)
        state = curator_network_graph.get_state(config).values

        votes = state.get("votes", [])
        assert len(votes) == 3

        dimensions = {v["dimension"] for v in votes}
        assert dimensions == {"Efficiency", "Ethics", "Resilience"}

        for vote in votes:
            assert "agent_action" in vote
            assert "agent_id" in vote["agent_action"]
            assert "rationale" in vote["agent_action"]
            assert 0 <= vote["score"] <= 100

    def test_tombstone_preserves_cid(self):
        """After tombstoning via curator graph, original CID is still accessible."""
        from backend.agents.library.curator_network import curator_network_graph
        from uuid import uuid4

        lib = LibraryManager.get_instance()
        storage = SovereignStorage.get_instance()
        content = b"precious knowledge that must survive"
        asset, _ = _register(lib, data=content, title="Preserve Me")

        thread_id = str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages": [],
            "agent_id": "curator-network-v1",
            "action_log": [],
            "error": None,
            "asset_cid": asset.cid,
            "proposed_status": "Tombstoned",
            "proposer_rationale": "No longer needed but content must survive tombstone-only invariant check",
            "asset_metadata": None,
            "downstream_deps": [],
            "dependency_check_passed": True,
            "votes": [],
            "consensus_status": "in_progress",
            "rationale_log": [],
            "escalation_signal": False,
            "break_glass_active": False,
            "requires_human_token": False,
        }

        curator_network_graph.invoke(initial_state, config=config)
        state = curator_network_graph.get_state(config).values

        # Regardless of consensus outcome, original CID must survive
        plaintext, _ = run(storage.cat(asset.cid))
        assert plaintext == content
