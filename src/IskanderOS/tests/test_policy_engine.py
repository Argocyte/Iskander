"""
Tests for the PolicyEngine — governance-as-code with CCIN Constitutional Core.

Covers:
  - Manifest loading and CID anchoring
  - Rule evaluation (MaxValue, MinValue, RequireApproval, Deny)
  - Constitutional Core immutability (anti-extractive, democratic control,
    transparency, open membership)
  - Agent-scoped rules (applies_to filtering)
  - OperationalComplianceViolation exception
"""
from __future__ import annotations

import pytest

from backend.governance.policy_engine import CCIN_PRINCIPLES, PolicyEngine
from backend.schemas.compliance import (
    ConstraintType,
    GovernanceManifest,
    OperationalComplianceViolation,
    PolicyCheckResult,
    PolicyRule,
    PolicyViolation,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fresh_engine():
    """Reset singleton before and after each test."""
    PolicyEngine._reset_instance()
    yield
    PolicyEngine._reset_instance()


def _make_manifest(**overrides) -> dict:
    """Build a minimal governance manifest dict."""
    base = {
        "version": 1,
        "constitutional_core": [
            "anti_extractive",
            "democratic_control",
            "transparency",
            "open_membership",
        ],
        "policies": [
            {
                "rule_id": "max_pay_ratio",
                "description": "Mondragon pay-ratio cap: 6:1",
                "constraint_type": "MaxValue",
                "value": "6",
                "applies_to": ["treasurer-agent-v1"],
            },
            {
                "rule_id": "max_single_payment",
                "description": "Single payment cap: 100k",
                "constraint_type": "MaxValue",
                "value": "100000",
                "applies_to": ["treasurer-agent-v1"],
            },
            {
                "rule_id": "deny_auto_mint",
                "description": "Agents cannot autonomously mint",
                "constraint_type": "Deny",
                "value": "mint",
                "applies_to": [],
            },
        ],
    }
    base.update(overrides)
    return base


def _load_engine(manifest_dict=None) -> PolicyEngine:
    """Create and load a PolicyEngine with a manifest."""
    engine = PolicyEngine.get_instance()
    engine.load_manifest(manifest_dict=manifest_dict or _make_manifest())
    return engine


# ═════════════════════════════════════════════════════════════════════════════
# MANIFEST LOADING
# ═════════════════════════════════════════════════════════════════════════════


class TestManifestLoading:
    """Tests for manifest load, validation, and CID anchoring."""

    def test_load_manifest_returns_governance_manifest(self):
        engine = _load_engine()
        assert engine.manifest is not None
        assert isinstance(engine.manifest, GovernanceManifest)
        assert engine.manifest.version == 1

    def test_manifest_cid_computed(self):
        engine = _load_engine()
        assert engine.manifest_cid is not None
        assert engine.manifest_cid.startswith("Qm")
        assert len(engine.manifest_cid) == 46  # Qm + 44 hex chars

    def test_load_manifest_agent_action(self):
        engine = PolicyEngine.get_instance()
        _manifest, action = engine.load_manifest(manifest_dict=_make_manifest())
        assert action.agent_id == "policy-engine-v1"
        assert action.action == "load_governance_manifest"
        assert "3 rule(s)" in action.rationale

    def test_missing_manifest_raises(self):
        engine = PolicyEngine.get_instance()
        with pytest.raises(FileNotFoundError):
            engine.load_manifest(path="/nonexistent/governance_manifest.json")

    def test_no_manifest_check_compliance_raises(self):
        engine = PolicyEngine.get_instance()
        with pytest.raises(ValueError, match="No governance manifest loaded"):
            engine.check_compliance("agent", "payment", {})

    def test_manifest_reload_replaces_rules(self):
        engine = _load_engine()
        assert len(engine.manifest.policies) == 3

        new_manifest = _make_manifest(policies=[])
        engine.load_manifest(manifest_dict=new_manifest)
        assert len(engine.manifest.policies) == 0

    def test_different_manifests_produce_different_cids(self):
        engine = PolicyEngine.get_instance()
        _m1, _ = engine.load_manifest(manifest_dict=_make_manifest(version=1))
        cid1 = engine.manifest_cid
        _m2, _ = engine.load_manifest(manifest_dict=_make_manifest(version=2))
        cid2 = engine.manifest_cid
        assert cid1 != cid2


# ═════════════════════════════════════════════════════════════════════════════
# RULE EVALUATION
# ═════════════════════════════════════════════════════════════════════════════


class TestRuleEvaluation:
    """Tests for individual rule types."""

    def test_compliant_action_passes(self):
        engine = _load_engine()
        result, action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"pay_ratio": 4, "single_payment": 50000},
        )
        assert result.compliant is True
        assert len(result.violations) == 0
        assert "PASS" in action.rationale

    def test_max_value_violation_blocked(self):
        engine = _load_engine()
        result, action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"pay_ratio": 8},  # exceeds 6:1 cap
        )
        assert result.compliant is False
        violations = [v for v in result.violations if v.rule_id == "max_pay_ratio"]
        assert len(violations) == 1
        assert violations[0].actual_value == "8"
        assert violations[0].threshold == "6"

    def test_deny_rule_blocks_action(self):
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="any-agent",
            action_type="mint",
            params={},
        )
        assert result.compliant is False
        deny_violations = [
            v for v in result.violations if v.rule_id == "deny_auto_mint"
        ]
        assert len(deny_violations) == 1

    def test_max_single_payment_violation(self):
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"single_payment": 200000},
        )
        assert result.compliant is False
        violations = [v for v in result.violations if v.rule_id == "max_single_payment"]
        assert len(violations) == 1


# ═════════════════════════════════════════════════════════════════════════════
# AGENT-SCOPED RULES
# ═════════════════════════════════════════════════════════════════════════════


class TestAgentScopedRules:
    """Tests for applies_to filtering."""

    def test_rule_applies_to_correct_agent(self):
        engine = _load_engine()
        # treasurer-agent-v1 should be checked against max_pay_ratio
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"pay_ratio": 8},
        )
        assert not result.compliant

    def test_rule_skips_wrong_agent(self):
        engine = _load_engine()
        # secretary-agent-v1 is NOT in applies_to for max_pay_ratio
        result, _action = engine.check_compliance(
            agent_id="secretary-agent-v1",
            action_type="payment",
            params={"pay_ratio": 8},  # would violate if checked
        )
        # Only the deny_auto_mint rule applies (empty applies_to = all agents),
        # but action_type is "payment" not "mint", so it passes
        pay_ratio_violations = [
            v for v in result.violations if v.rule_id == "max_pay_ratio"
        ]
        assert len(pay_ratio_violations) == 0

    def test_empty_applies_to_matches_all_agents(self):
        engine = _load_engine()
        # deny_auto_mint has applies_to=[] → applies to all agents
        result, _action = engine.check_compliance(
            agent_id="random-agent",
            action_type="mint",
            params={},
        )
        deny_violations = [
            v for v in result.violations if v.rule_id == "deny_auto_mint"
        ]
        assert len(deny_violations) == 1


# ═════════════════════════════════════════════════════════════════════════════
# CONSTITUTIONAL CORE (CCIN) — IMMUTABLE CHECKS
# ═════════════════════════════════════════════════════════════════════════════


class TestConstitutionalCore:
    """Tests proving CCIN checks cannot be overridden by manifest changes."""

    def test_anti_extractive_blocks_external_payment(self):
        """External payments without HITL approval are blocked by CCIN."""
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={
                "amount": 50000,
                "to": "0xDeaDBeef",
                "is_external": True,
                "hitl_approved": False,
            },
        )
        assert result.constitutional_checks_passed is False
        ccin_violations = [
            v for v in result.violations if v.rule_id == "ccin_anti_extractive"
        ]
        assert len(ccin_violations) == 1

    def test_anti_extractive_passes_with_hitl(self):
        """External payments WITH HITL approval pass the CCIN check."""
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={
                "amount": 50000,
                "to": "0xDeaDBeef",
                "is_external": True,
                "hitl_approved": True,
            },
        )
        ccin_violations = [
            v for v in result.violations if v.rule_id == "ccin_anti_extractive"
        ]
        assert len(ccin_violations) == 0

    def test_democratic_control_blocks_hitl_bypass(self):
        """Attempting to bypass HITL is blocked by CCIN."""
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"bypass_hitl": True},
        )
        assert result.constitutional_checks_passed is False
        ccin_violations = [
            v for v in result.violations if v.rule_id == "ccin_democratic_control"
        ]
        assert len(ccin_violations) == 1

    def test_transparency_blocks_anonymous_agent(self):
        """Empty agent_id is blocked by CCIN transparency check."""
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="",  # anonymous
            action_type="payment",
            params={},
        )
        assert result.constitutional_checks_passed is False
        ccin_violations = [
            v for v in result.violations if v.rule_id == "ccin_transparency"
        ]
        assert len(ccin_violations) == 1

    def test_open_membership_blocks_discriminatory_params(self):
        """Params with discriminatory fields are blocked by CCIN."""
        engine = _load_engine()
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"gender": "male", "amount": 100},
        )
        assert result.constitutional_checks_passed is False
        ccin_violations = [
            v for v in result.violations if v.rule_id == "ccin_open_membership"
        ]
        assert len(ccin_violations) == 1

    def test_constitutional_core_cannot_be_overridden(self):
        """Even a manifest with NO rules cannot disable CCIN checks.

        This is the key test: removing all manifest policies does NOT
        disable the constitutional core. CCIN checks are hardcoded.
        """
        # Load a manifest with zero policies
        engine = _load_engine(manifest_dict={
            "version": 1,
            "constitutional_core": [],  # even empty constitutional_core list
            "policies": [],             # no manifest rules at all
        })
        result, _action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={
                "amount": 50000,
                "to": "0xDeaDBeef",
                "is_external": True,
                "hitl_approved": False,
                "bypass_hitl": True,
            },
        )
        # CCIN still fires even with empty manifest
        assert result.constitutional_checks_passed is False
        assert len(result.violations) >= 2  # at least anti-extractive + democratic_control

    def test_ccin_principles_exist(self):
        """All four CCIN principles are defined."""
        assert "anti_extractive" in CCIN_PRINCIPLES
        assert "democratic_control" in CCIN_PRINCIPLES
        assert "transparency" in CCIN_PRINCIPLES
        assert "open_membership" in CCIN_PRINCIPLES


# ═════════════════════════════════════════════════════════════════════════════
# GLASS BOX INTEGRATION
# ═════════════════════════════════════════════════════════════════════════════


class TestGlassBox:
    """Tests for Glass Box AgentAction compliance."""

    def test_check_compliance_returns_agent_action(self):
        engine = _load_engine()
        _result, action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"pay_ratio": 4},
        )
        assert action.agent_id == "policy-engine-v1"
        assert action.action == "check_compliance"
        assert action.payload is not None
        assert "manifest_cid" in action.payload

    def test_violation_action_includes_count(self):
        engine = _load_engine()
        _result, action = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"pay_ratio": 8},
        )
        assert "FAIL" in action.rationale
        assert action.payload["violation_count"] >= 1


# ═════════════════════════════════════════════════════════════════════════════
# EXCEPTION
# ═════════════════════════════════════════════════════════════════════════════


class TestOperationalComplianceViolation:
    """Tests for the custom exception."""

    def test_exception_carries_violations(self):
        violations = [
            PolicyViolation(
                rule_id="test",
                description="test rule",
                constraint_type=ConstraintType.MAX_VALUE,
                threshold="10",
                actual_value="20",
                message="Value 20 exceeds max 10",
            )
        ]
        exc = OperationalComplianceViolation(violations)
        assert len(exc.violations) == 1
        assert "1 rule(s) failed" in exc.message

    def test_exception_is_raisable(self):
        with pytest.raises(OperationalComplianceViolation):
            raise OperationalComplianceViolation([], "test error")
