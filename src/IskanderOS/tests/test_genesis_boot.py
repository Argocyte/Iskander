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
