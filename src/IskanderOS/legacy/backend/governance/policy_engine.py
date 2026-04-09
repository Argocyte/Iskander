"""
policy_engine.py — Governance-as-code with immutable ICA Constitutional Core.

The PolicyEngine reads a ``governance_manifest.json`` and exposes a single
``check_compliance(agent_id, action_type, params)`` gate that every agent
MUST call before drafting any proposal, payment, or governance action.

CONSTITUTIONAL CORE:
  Four hardcoded ICA checks run AFTER manifest checks and CANNOT be
  overridden by manifest updates:
    1. Anti-extractive — no tx benefits one member at collective expense
    2. Democratic control — no single agent bypasses M-of-N approval
    3. Transparency — every proposal produces a Glass Box AgentAction
    4. Open membership — proposals cannot discriminate by identity attributes

GLASS BOX: check_compliance() → AgentAction with EthicalImpactLevel.MEDIUM
           load_manifest()     → AgentAction with EthicalImpactLevel.LOW

DESIGN: In-memory, no I/O per check. Manifest loaded at startup; reloaded
only on explicit call to load_manifest().
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.schemas.compliance import (
    ConstraintType,
    GovernanceManifest,
    OperationalComplianceViolation,
    PolicyCheckResult,
    PolicyRule,
    PolicyViolation,
)
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "policy-engine-v1"

# ── Constitutional Core (ICA) ─────────────────────────────────────────────────
# These are CODE-LEVEL invariants. The governance manifest can add rules on top
# but can NEVER weaken or remove these. Updating them requires a code release —
# deliberate, auditable friction per SYS-3.

ICA_PRINCIPLES = {
    "anti_extractive": (
        "No transaction can benefit a single member at the expense of the collective. "
        "Transfers to non-cooperative addresses require M-of-N approval."
    ),
    "democratic_control": (
        "No single agent can bypass M-of-N approval for value-moving operations. "
        "All financial proposals must route through HITL."
    ),
    "transparency": (
        "Every proposal must produce a Glass Box AgentAction with rationale and "
        "ethical impact assessment before any side-effect executes."
    ),
    "open_membership": (
        "Agent proposals cannot discriminate by identity attributes. "
        "Membership eligibility is determined by cooperative bylaws, not agent logic."
    ),
}


class PolicyEngine:
    """Singleton governance-as-code engine.

    Obtain via ``PolicyEngine.get_instance()``.

    Usage::

        engine = PolicyEngine.get_instance()
        result = engine.check_compliance(
            agent_id="treasurer-agent-v1",
            action_type="payment",
            params={"amount": 50000, "to": "0x..."},
        )
        if not result.compliant:
            raise OperationalComplianceViolation(result.violations)
    """

    _instance: PolicyEngine | None = None

    def __init__(self) -> None:
        self._manifest: GovernanceManifest | None = None
        self._manifest_cid: str | None = None
        self._rules_by_id: dict[str, PolicyRule] = {}

    @classmethod
    def get_instance(cls) -> PolicyEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton."""
        cls._instance = None

    # ═══════════════════════════════════════════════════════════════════════════
    # MANIFEST LOADING
    # ═══════════════════════════════════════════════════════════════════════════

    def load_manifest(
        self,
        path: str | Path | None = None,
        manifest_dict: dict[str, Any] | None = None,
    ) -> tuple[GovernanceManifest, AgentAction]:
        """Load (or reload) the governance manifest.

        Accepts either a filesystem path or a pre-parsed dict (for testing).
        Computes a content CID (SHA-256 hash) for provenance tracking.

        Raises:
            FileNotFoundError: If path does not exist.
            ValueError: If manifest JSON is invalid.
        """
        if manifest_dict is not None:
            raw = manifest_dict
        else:
            p = Path(path or settings.governance_manifest_path)
            if not p.exists():
                raise FileNotFoundError(
                    f"Governance manifest not found: {p}. "
                    f"Create it or set 'governance_manifest_path' in config."
                )
            raw = json.loads(p.read_text(encoding="utf-8"))

        manifest = GovernanceManifest(**raw)

        # Compute content CID for provenance (deterministic JSON serialisation)
        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        content_hash = hashlib.sha256(canonical).hexdigest()
        self._manifest_cid = f"Qm{content_hash[:44]}"
        manifest.content_cid = self._manifest_cid

        # Index rules by ID for fast lookup
        self._rules_by_id = {rule.rule_id: rule for rule in manifest.policies}
        self._manifest = manifest

        action = AgentAction(
            agent_id=AGENT_ID,
            action="load_governance_manifest",
            rationale=(
                f"Loaded governance manifest v{manifest.version} with "
                f"{len(manifest.policies)} rule(s) and "
                f"{len(manifest.constitutional_core)} constitutional principle(s). "
                f"Content CID: {self._manifest_cid}."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={
                "version": manifest.version,
                "rule_count": len(manifest.policies),
                "constitutional_core": manifest.constitutional_core,
                "content_cid": self._manifest_cid,
            },
        )

        logger.info(
            "Governance manifest loaded: v%d, %d rules, cid=%s",
            manifest.version,
            len(manifest.policies),
            self._manifest_cid,
        )
        return manifest, action

    @property
    def manifest(self) -> GovernanceManifest | None:
        return self._manifest

    @property
    def manifest_cid(self) -> str | None:
        return self._manifest_cid

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPLIANCE CHECK — THE GLOBAL GATE
    # ═══════════════════════════════════════════════════════════════════════════

    def check_compliance(
        self,
        agent_id: str,
        action_type: str,
        params: dict[str, Any],
    ) -> tuple[PolicyCheckResult, AgentAction]:
        """Check an agent action against the governance manifest + ICA core.

        This is the Compliance_Gate that all agents must pass through.

        Args:
            agent_id: The calling agent's identifier.
            action_type: Category of action (e.g. "payment", "draft", "mint").
            params: Action-specific parameters to check against rules.

        Returns:
            (PolicyCheckResult, AgentAction) — result includes violations and warnings.

        Raises:
            ValueError: If no manifest has been loaded.
        """
        if self._manifest is None:
            raise ValueError(
                "No governance manifest loaded. Call load_manifest() first."
            )

        violations: list[PolicyViolation] = []
        warnings: list[str] = []
        checked = 0

        # ── Phase 1: Manifest Rules ───────────────────────────────────────────
        for rule in self._manifest.policies:
            # Skip rules that don't apply to this agent
            if rule.applies_to and agent_id not in rule.applies_to:
                continue

            checked += 1
            violation = self._evaluate_rule(rule, action_type, params)
            if violation is not None:
                violations.append(violation)

        # ── Phase 2: Constitutional Core (ICA) ───────────────────────────────
        # These run AFTER manifest rules and CANNOT be overridden.
        constitutional_passed = self._check_constitutional_core(
            agent_id, action_type, params, violations
        )

        compliant = len(violations) == 0
        result = PolicyCheckResult(
            compliant=compliant,
            violations=violations,
            warnings=warnings,
            checked_rules=checked,
            constitutional_checks_passed=constitutional_passed,
        )

        # Glass Box trail
        action = AgentAction(
            agent_id=AGENT_ID,
            action="check_compliance",
            rationale=(
                f"Compliance check for agent '{agent_id}' action '{action_type}': "
                f"{'PASS' if compliant else 'FAIL'} — "
                f"{checked} manifest rules checked, {len(violations)} violation(s). "
                f"Constitutional core: {'PASS' if constitutional_passed else 'FAIL'}. "
                f"Manifest CID: {self._manifest_cid}."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "agent_id": agent_id,
                "action_type": action_type,
                "compliant": compliant,
                "violation_count": len(violations),
                "checked_rules": checked,
                "constitutional_passed": constitutional_passed,
                "manifest_cid": self._manifest_cid,
            },
        )

        if not compliant:
            logger.warning(
                "Compliance FAIL: agent=%s action=%s violations=%d",
                agent_id,
                action_type,
                len(violations),
            )
        else:
            logger.info(
                "Compliance PASS: agent=%s action=%s rules=%d",
                agent_id,
                action_type,
                checked,
            )

        return result, action

    # ═══════════════════════════════════════════════════════════════════════════
    # INTERNAL: Rule Evaluation
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _evaluate_rule(
        rule: PolicyRule,
        action_type: str,
        params: dict[str, Any],
    ) -> PolicyViolation | None:
        """Evaluate a single PolicyRule against the given params.

        Returns a PolicyViolation if the rule is violated, None otherwise.
        """
        # Extract the param value that this rule constrains
        # Convention: rule_id maps to a param key (e.g. "max_pay_ratio" -> "pay_ratio")
        param_key = rule.rule_id.replace("max_", "").replace("min_", "")
        actual_value = params.get(param_key) or params.get(rule.rule_id)

        if rule.constraint_type == ConstraintType.DENY:
            # Deny rules block specific action types entirely
            denied_actions = [v.strip() for v in rule.value.split(",")]
            if action_type in denied_actions:
                return PolicyViolation(
                    rule_id=rule.rule_id,
                    description=rule.description,
                    constraint_type=rule.constraint_type,
                    threshold=rule.value,
                    actual_value=action_type,
                    message=f"Action '{action_type}' is denied by rule '{rule.rule_id}': {rule.description}",
                )

        elif rule.constraint_type == ConstraintType.REQUIRE_APPROVAL:
            # RequireApproval rules flag that HITL is required
            # This is informational — the agent pipeline must honour it
            required_actions = [v.strip() for v in rule.value.split(",")]
            if action_type in required_actions:
                if not params.get("hitl_approved", False):
                    return PolicyViolation(
                        rule_id=rule.rule_id,
                        description=rule.description,
                        constraint_type=rule.constraint_type,
                        threshold=rule.value,
                        actual_value=str(params.get("hitl_approved", False)),
                        message=(
                            f"Action '{action_type}' requires human approval per rule "
                            f"'{rule.rule_id}': {rule.description}"
                        ),
                    )

        elif rule.constraint_type == ConstraintType.MAX_VALUE:
            if actual_value is not None:
                try:
                    if float(actual_value) > float(rule.value):
                        return PolicyViolation(
                            rule_id=rule.rule_id,
                            description=rule.description,
                            constraint_type=rule.constraint_type,
                            threshold=rule.value,
                            actual_value=str(actual_value),
                            message=(
                                f"Value {actual_value} exceeds maximum {rule.value} "
                                f"for rule '{rule.rule_id}': {rule.description}"
                            ),
                        )
                except (ValueError, TypeError):
                    pass  # Non-numeric values skip MaxValue checks

        elif rule.constraint_type == ConstraintType.MIN_VALUE:
            if actual_value is not None:
                try:
                    if float(actual_value) < float(rule.value):
                        return PolicyViolation(
                            rule_id=rule.rule_id,
                            description=rule.description,
                            constraint_type=rule.constraint_type,
                            threshold=rule.value,
                            actual_value=str(actual_value),
                            message=(
                                f"Value {actual_value} below minimum {rule.value} "
                                f"for rule '{rule.rule_id}': {rule.description}"
                            ),
                        )
                except (ValueError, TypeError):
                    pass

        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # CONSTITUTIONAL CORE (ICA) — HARDCODED, IMMUTABLE
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _check_constitutional_core(
        agent_id: str,
        action_type: str,
        params: dict[str, Any],
        violations: list[PolicyViolation],
    ) -> bool:
        """Run hardcoded ICA constitutional checks.

        These CANNOT be overridden or weakened by governance manifest updates.
        The manifest can only ADD constraints on top of these.

        Returns True if all constitutional checks pass.
        """
        passed = True

        # ── ICA-1: Anti-extractive ───────────────────────────────────────────
        # No single-beneficiary extraction without collective approval
        if action_type in ("payment", "transfer", "mint"):
            amount = params.get("amount") or params.get("value_wei") or 0
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                amount = 0

            beneficiary = params.get("to") or params.get("beneficiary")
            is_external = params.get("is_external", False)

            # External payments above zero require HITL (anti-extractive gate)
            if is_external and amount > 0 and not params.get("hitl_approved", False):
                violations.append(PolicyViolation(
                    rule_id="ica_anti_extractive",
                    description=ICA_PRINCIPLES["anti_extractive"],
                    constraint_type=ConstraintType.REQUIRE_APPROVAL,
                    threshold="0",
                    actual_value=str(amount),
                    message=(
                        f"ICA Anti-Extractive: External {action_type} of {amount} "
                        f"to '{beneficiary}' requires M-of-N human approval. "
                        f"This constitutional check cannot be overridden."
                    ),
                ))
                passed = False

        # ── ICA-2: Democratic control ────────────────────────────────────────
        # Value-moving operations must declare HITL routing
        if action_type in ("payment", "transfer", "mint", "burn"):
            if params.get("bypass_hitl", False):
                violations.append(PolicyViolation(
                    rule_id="ica_democratic_control",
                    description=ICA_PRINCIPLES["democratic_control"],
                    constraint_type=ConstraintType.DENY,
                    threshold="bypass_hitl=False",
                    actual_value="bypass_hitl=True",
                    message=(
                        "ICA Democratic Control: Cannot bypass HITL for "
                        f"'{action_type}' operations. This constitutional check "
                        "cannot be overridden."
                    ),
                ))
                passed = False

        # ── ICA-3: Transparency ──────────────────────────────────────────────
        # Every proposal must include an agent_id (Glass Box requirement)
        if not agent_id:
            violations.append(PolicyViolation(
                rule_id="ica_transparency",
                description=ICA_PRINCIPLES["transparency"],
                constraint_type=ConstraintType.REQUIRE_APPROVAL,
                threshold="agent_id required",
                actual_value="<empty>",
                message=(
                    "ICA Transparency: All actions must identify the proposing "
                    "agent. Anonymous proposals are blocked."
                ),
            ))
            passed = False

        # ── ICA-4: Open membership ───────────────────────────────────────────
        # Proposals cannot filter by protected identity attributes
        discriminatory_fields = {"ethnicity", "gender", "age", "religion", "nationality"}
        used_discriminatory = discriminatory_fields & set(params.keys())
        if used_discriminatory:
            violations.append(PolicyViolation(
                rule_id="ica_open_membership",
                description=ICA_PRINCIPLES["open_membership"],
                constraint_type=ConstraintType.DENY,
                threshold="no identity discrimination",
                actual_value=str(used_discriminatory),
                message=(
                    f"ICA Open Membership: Proposal contains discriminatory "
                    f"fields: {used_discriminatory}. Agent proposals cannot "
                    f"filter by protected identity attributes."
                ),
            ))
            passed = False

        return passed
