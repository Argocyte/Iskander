"""Tests for the Genesis Boot Sequence."""
from __future__ import annotations

import pytest

from backend.schemas.compliance import PolicyRule, ConstraintType
from backend.schemas.genesis import (
    GenesisMode,
    GovernanceTier,
    RegulatoryUpdateSeverity,
    ExtractedRule,
    MappingConfirmation,
    RegulatoryLayer,
    RegulatoryUpdate,
    FounderRegistration,
)


class TestGenesisEnums:
    """Test enum definitions."""

    def test_genesis_mode_values(self):
        assert GenesisMode.SOLO_NODE == "solo_node"
        assert GenesisMode.LEGACY_IMPORT == "legacy_import"
        assert GenesisMode.NEW_FOUNDING == "new_founding"

    def test_governance_tier_values(self):
        assert GovernanceTier.CONSTITUTIONAL == "Constitutional"
        assert GovernanceTier.OPERATIONAL == "Operational"
        assert GovernanceTier.REGULATORY == "Regulatory"

    def test_regulatory_update_severity_values(self):
        assert RegulatoryUpdateSeverity.ADVISORY == "Advisory"
        assert RegulatoryUpdateSeverity.MANDATORY == "Mandatory"
        assert RegulatoryUpdateSeverity.URGENT == "Urgent"


class TestExtractedRule:
    """Test ExtractedRule model."""

    def test_ambiguity_threshold(self):
        """Rules with confidence < 0.6 must be marked ambiguous."""
        rule = ExtractedRule(
            rule_id="test_rule",
            source_text="Members shall meet quarterly",
            proposed_policy_rule={"rule_id": "test", "constraint_type": "MaxValue", "value": "4"},
            confidence=0.5,
            tier=GovernanceTier.OPERATIONAL,
        )
        assert rule.is_ambiguous is True

    def test_high_confidence_not_ambiguous(self):
        rule = ExtractedRule(
            rule_id="test_rule",
            source_text="Pay ratio capped at 6:1",
            proposed_policy_rule={"rule_id": "pay_ratio", "constraint_type": "MaxValue", "value": "6"},
            confidence=0.9,
            tier=GovernanceTier.CONSTITUTIONAL,
        )
        assert rule.is_ambiguous is False

    def test_novel_field_default_false(self):
        rule = ExtractedRule(
            rule_id="test",
            source_text="text",
            proposed_policy_rule={},
            confidence=0.8,
            tier=GovernanceTier.OPERATIONAL,
        )
        assert rule.is_novel_field is False


class TestRegulatoryLayer:
    """Test RegulatoryLayer model."""

    def test_non_overridable_always_true(self):
        layer = RegulatoryLayer(
            jurisdiction="GB",
            rules=[],
            source_documents=[],
        )
        assert layer.non_overridable is True

    def test_cannot_set_overridable(self):
        """non_overridable is forced True regardless of input."""
        layer = RegulatoryLayer(
            jurisdiction="GB",
            rules=[],
            source_documents=[],
            non_overridable=False,
        )
        assert layer.non_overridable is True


class TestPolicyRuleMetadata:
    def test_metadata_default_empty_dict(self):
        rule = PolicyRule(
            rule_id="test",
            description="test rule",
            constraint_type=ConstraintType.MAX_VALUE,
            value="10",
        )
        assert rule.metadata == {}

    def test_metadata_regulatory_marker(self):
        rule = PolicyRule(
            rule_id="reg_test",
            description="regulatory rule",
            constraint_type=ConstraintType.MAX_VALUE,
            value="100",
            metadata={"_regulatory": True, "non_overridable": True},
        )
        assert rule.metadata["_regulatory"] is True

    def test_metadata_ambiguous_marker(self):
        rule = PolicyRule(
            rule_id="ambig_test",
            description="ambiguous rule",
            constraint_type=ConstraintType.REQUIRE_APPROVAL,
            value="payment",
            metadata={"_ambiguous": True},
        )
        assert rule.metadata["_ambiguous"] is True


from backend.agents.state import BootState, AgentState


class TestBootState:
    def test_boot_state_extends_agent_state(self):
        agent_keys = set(AgentState.__annotations__.keys())
        boot_keys = set(BootState.__annotations__.keys())
        assert agent_keys.issubset(boot_keys)

    def test_boot_state_has_genesis_fields(self):
        required = {
            "mode", "node_type", "coop_profile", "owner_profile",
            "skeleton_template_cid", "extracted_rules", "mapping_confirmations",
            "founder_confirmations", "ambiguous_rules", "regulatory_layer",
            "genesis_manifest", "constitution_cid", "genesis_manifest_cid",
            "founding_tx_hash", "founder_sbt_ids", "safe_address",
            "boot_phase", "boot_complete", "requires_human_token",
        }
        boot_keys = set(BootState.__annotations__.keys())
        missing = required - boot_keys
        assert not missing, f"Missing fields in BootState: {missing}"


import json
from pathlib import Path


class TestRegulatoryTemplates:
    TEMPLATES_DIR = Path("backend/governance/regulatory")

    def test_universal_template_exists(self):
        assert (self.TEMPLATES_DIR / "UNIVERSAL.json").exists()

    def test_gb_template_exists(self):
        assert (self.TEMPLATES_DIR / "GB.json").exists()

    def test_es_template_exists(self):
        assert (self.TEMPLATES_DIR / "ES.json").exists()

    def test_templates_valid_json(self):
        for name in ("UNIVERSAL.json", "GB.json", "ES.json"):
            with open(self.TEMPLATES_DIR / name) as f:
                data = json.load(f)
            assert "jurisdiction" in data
            assert "rules" in data
            assert isinstance(data["rules"], list)

    def test_universal_has_no_jurisdiction_rules(self):
        with open(self.TEMPLATES_DIR / "UNIVERSAL.json") as f:
            data = json.load(f)
        assert data["jurisdiction"] == "UNIVERSAL"
        for rule in data["rules"]:
            assert rule.get("metadata", {}).get("_regulatory") is True

    def test_gb_template_jurisdiction(self):
        with open(self.TEMPLATES_DIR / "GB.json") as f:
            data = json.load(f)
        assert data["jurisdiction"] == "GB"


# ── Task 9: Solo Path Nodes ──────────────────────────────────────────────────

from backend.agents.genesis.initializer_agent import (
    select_mode,
    collect_owner_profile,
    inject_regulatory_layer,
    configure_solo_manifest,
)
from backend.schemas.genesis import GenesisMode


def _solo_initial_state() -> dict:
    return {
        "messages": [],
        "agent_id": "initializer-agent-v1",
        "action_log": [],
        "error": None,
        "mode": GenesisMode.SOLO_NODE.value,
        "node_type": None,
        "coop_profile": None,
        "owner_profile": None,
        "skeleton_template_cid": None,
        "extracted_rules": [],
        "mapping_confirmations": {},
        "founder_confirmations": {},
        "ambiguous_rules": [],
        "regulatory_layer": None,
        "genesis_manifest": None,
        "constitution_cid": None,
        "genesis_manifest_cid": None,
        "founding_tx_hash": None,
        "founder_sbt_ids": [],
        "safe_address": None,
        "boot_phase": "pre-genesis",
        "boot_complete": False,
        "requires_human_token": False,
    }


class TestSoloPathNodes:
    def test_select_mode_sets_node_type_solo(self):
        state = _solo_initial_state()
        result = select_mode(state)
        assert result["node_type"] == "solo"
        assert len(result["action_log"]) == 1

    def test_collect_owner_profile(self):
        state = _solo_initial_state()
        state["owner_profile"] = {
            "did": "did:key:owner123",
            "address": "0x" + "a" * 40,
            "name": "Alice",
            "jurisdiction": "GB",
        }
        result = collect_owner_profile(state)
        assert result["owner_profile"]["did"] == "did:key:owner123"
        assert result["boot_phase"] == "owner-profile-collected"

    def test_inject_regulatory_layer_loads_jurisdiction(self):
        state = _solo_initial_state()
        state["owner_profile"] = {"jurisdiction": "GB"}
        result = inject_regulatory_layer(state)
        assert result["regulatory_layer"] is not None
        assert result["regulatory_layer"]["jurisdiction"] == "GB"
        assert result["regulatory_layer"]["non_overridable"] is True

    def test_inject_regulatory_layer_fallback_universal(self):
        state = _solo_initial_state()
        state["owner_profile"] = {"jurisdiction": "XX"}
        result = inject_regulatory_layer(state)
        assert result["regulatory_layer"]["jurisdiction"] == "UNIVERSAL"

    def test_configure_solo_manifest(self):
        state = _solo_initial_state()
        state["regulatory_layer"] = {
            "jurisdiction": "GB",
            "rules": [{"rule_id": "reg_test", "metadata": {"_regulatory": True}}],
            "non_overridable": True,
        }
        result = configure_solo_manifest(state)
        assert result["genesis_manifest"] is not None
        assert result["genesis_manifest"]["version"] == 1
        assert len(result["genesis_manifest"]["policies"]) >= 1


# ── Task 10: Cooperative Path Nodes ──────────────────────────────────────────

from backend.agents.genesis.initializer_agent import (
    register_founders,
    compile_genesis_manifest,
    validate_genesis_manifest,
)


def _coop_initial_state() -> dict:
    state = _solo_initial_state()
    state["mode"] = GenesisMode.LEGACY_IMPORT.value
    state["node_type"] = "cooperative"
    return state


class TestCooperativePathNodes:
    def test_register_founders_minimum_3(self):
        state = _coop_initial_state()
        state["founder_confirmations"] = {
            "did:key:alice": False,
            "did:key:bob": False,
        }
        result = register_founders(state)
        assert result["error"] is not None
        assert "minimum 3" in result["error"].lower()

    def test_register_founders_success(self):
        state = _coop_initial_state()
        state["founder_confirmations"] = {
            "did:key:alice": False,
            "did:key:bob": False,
            "did:key:carol": False,
        }
        result = register_founders(state)
        assert result["error"] is None
        assert result["boot_phase"] == "founders-registered"

    def test_compile_genesis_manifest_merges_tiers(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {
                "rule_id": "pay_ratio",
                "tier": "Constitutional",
                "proposed_policy_rule": {"rule_id": "pay_ratio", "description": "6:1 cap", "constraint_type": "MaxValue", "value": "6", "applies_to": []},
                "confirmed": True,
            },
            {
                "rule_id": "spend_limit",
                "tier": "Operational",
                "proposed_policy_rule": {"rule_id": "spend_limit", "description": "100k cap", "constraint_type": "MaxValue", "value": "100000", "applies_to": []},
                "confirmed": True,
            },
        ]
        state["regulatory_layer"] = {
            "jurisdiction": "GB",
            "rules": [{"rule_id": "reg_test", "metadata": {"_regulatory": True}}],
            "non_overridable": True,
        }
        result = compile_genesis_manifest(state)
        manifest = result["genesis_manifest"]
        assert manifest["version"] == 1
        assert len(manifest["policies"]) == 3

    def test_compile_genesis_manifest_skips_unconfirmed(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {"rule_id": "confirmed_rule", "tier": "Operational", "proposed_policy_rule": {"rule_id": "confirmed_rule"}, "confirmed": True},
            {"rule_id": "unconfirmed_rule", "tier": "Operational", "proposed_policy_rule": {"rule_id": "unconfirmed_rule"}, "confirmed": False},
        ]
        state["regulatory_layer"] = {"rules": [], "non_overridable": True}
        result = compile_genesis_manifest(state)
        rule_ids = [r.get("rule_id") for r in result["genesis_manifest"]["policies"]]
        assert "confirmed_rule" in rule_ids
        assert "unconfirmed_rule" not in rule_ids

    def test_validate_genesis_manifest_passes(self):
        state = _coop_initial_state()
        state["genesis_manifest"] = {
            "version": 1,
            "constitutional_core": ["anti_extractive", "democratic_control", "transparency", "open_membership"],
            "policies": [{"rule_id": "test"}],
        }
        state["regulatory_layer"] = {"rules": [], "non_overridable": True}
        result = validate_genesis_manifest(state)
        assert result["error"] is None
        assert result["boot_phase"] == "manifest-validated"

    def test_validate_genesis_manifest_missing_ccin(self):
        state = _coop_initial_state()
        state["genesis_manifest"] = {"version": 1, "constitutional_core": [], "policies": []}
        state["regulatory_layer"] = {"rules": [], "non_overridable": True}
        result = validate_genesis_manifest(state)
        assert result["error"] is not None
        assert "CCIN" in result["error"]


# ── Task 11: Rule Extractor ──────────────────────────────────────────────────

from backend.agents.genesis.rule_extractor import (
    extract_rules_from_bylaws,
    tag_ambiguous_rules,
)


class TestRuleExtractor:
    def test_extract_rules_returns_list(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {"rule_id": "pay_ratio", "source_text": "Pay ratio 6:1", "proposed_policy_rule": {"rule_id": "pay_ratio", "constraint_type": "MaxValue", "value": "6"}, "confidence": 0.95, "is_ambiguous": False, "is_novel_field": False, "tier": "Operational", "confirmed": False}
        ]
        result = extract_rules_from_bylaws(state)
        assert isinstance(result["extracted_rules"], list)
        assert len(result["extracted_rules"]) >= 1

    def test_tag_ambiguous_marks_low_confidence(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {"rule_id": "clear_rule", "confidence": 0.9, "is_ambiguous": False},
            {"rule_id": "vague_rule", "confidence": 0.4, "is_ambiguous": False},
        ]
        result = tag_ambiguous_rules(state)
        rules = {r["rule_id"]: r for r in result["extracted_rules"]}
        assert rules["clear_rule"]["is_ambiguous"] is False
        assert rules["vague_rule"]["is_ambiguous"] is True
        assert "vague_rule" in result["ambiguous_rules"]

    def test_tag_ambiguous_empty_list(self):
        state = _coop_initial_state()
        state["extracted_rules"] = []
        result = tag_ambiguous_rules(state)
        assert result["ambiguous_rules"] == []
