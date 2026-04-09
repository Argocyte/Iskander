"""
Governance Verifier --- checks foreign SDC governance guarantees (Fix 7).

Certain Iskander activity types (Verdict, HITLProposalVote, JuryNomination,
ArbitrationRequest) carry governance implications.  Before accepting them, the
boundary agent must verify that the sending node offers equivalent guarantees
(human jury, ZK voting, SBT identity).

Decision matrix:
  - Verdict without ``human_jury``   -> REJECT (non-negotiable).
  - Vote without ``zk_voting``       -> ACCEPT with HITL flag.
  - JuryNomination without ``sbt_identity`` -> ACCEPT with HITL flag.
  - ArbitrationRequest               -> always ACCEPT (filing is low risk).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# ── Governance-sensitive activity types ──────────────────────────────────────

GOVERNANCE_SENSITIVE_TYPES = {
    "iskander:HITLProposalVote",
    "iskander:Verdict",
    "iskander:JuryNomination",
    "iskander:ArbitrationRequest",
}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class GovernanceCapabilities:
    """Declared governance capabilities extracted from a foreign activity."""

    human_jury: bool = False
    zk_voting: bool = False
    sbt_identity: bool = False
    raw_proof: Dict[str, Any] = field(default_factory=dict)


# ── Verifier ─────────────────────────────────────────────────────────────────

class GovernanceVerifier:
    """Stateless governance verifier.

    Singleton: obtain via ``GovernanceVerifier.get_instance()``.
    """

    _instance: "GovernanceVerifier | None" = None

    @classmethod
    def get_instance(cls) -> "GovernanceVerifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ───────────────────────────────────────────────────────────

    @staticmethod
    def requires_verification(activity_type: str) -> bool:
        """Return ``True`` if *activity_type* needs governance verification."""
        return activity_type in GOVERNANCE_SENSITIVE_TYPES

    def assess_capabilities(
        self,
        activity: Dict[str, Any],
        actor_iri: str,
    ) -> GovernanceCapabilities:
        """Extract governance capabilities from the activity's ``governanceProof``.

        If the field is missing, all capabilities default to ``False``.
        """
        proof = activity.get("governanceProof", {}) or {}
        caps = GovernanceCapabilities(
            human_jury=bool(proof.get("human_jury", False)),
            zk_voting=bool(proof.get("zk_voting", False)),
            sbt_identity=bool(proof.get("sbt_identity", False)),
            raw_proof=dict(proof),
        )
        logger.debug(
            "governance_capabilities_assessed",
            actor_iri=actor_iri,
            human_jury=caps.human_jury,
            zk_voting=caps.zk_voting,
            sbt_identity=caps.sbt_identity,
        )
        return caps

    def evaluate(
        self,
        activity: Dict[str, Any],
        capabilities: GovernanceCapabilities,
    ) -> Tuple[bool, str, bool]:
        """Evaluate whether a governance-sensitive activity should proceed.

        Returns
        -------
        tuple of (proceed, reason, requires_hitl)
            - proceed: ``True`` if the activity may continue.
            - reason: human-readable explanation.
            - requires_hitl: ``True`` if a human must review before final acceptance.
        """
        activity_type = activity.get("type", "")

        # ── Verdict without human jury -> REJECT ─────────────────────────────
        if activity_type == "iskander:Verdict":
            if not capabilities.human_jury:
                reason = (
                    "Verdict rejected: foreign node does not declare human_jury "
                    "governance capability. Iskander requires human juries for "
                    "all arbitration verdicts."
                )
                logger.warning("governance_verdict_rejected", reason=reason)
                return False, reason, False

        # ── Vote without ZK voting -> ACCEPT + HITL ─────────────────────────
        if activity_type == "iskander:HITLProposalVote":
            if not capabilities.zk_voting:
                reason = (
                    "Vote accepted provisionally: foreign node does not declare "
                    "zk_voting. Requires HITL review to confirm vote integrity."
                )
                logger.info("governance_vote_hitl_required", reason=reason)
                return True, reason, True

        # ── JuryNomination without SBT identity -> ACCEPT + HITL ────────────
        if activity_type == "iskander:JuryNomination":
            if not capabilities.sbt_identity:
                reason = (
                    "JuryNomination accepted provisionally: foreign node does not "
                    "declare sbt_identity. Requires HITL review to verify juror "
                    "eligibility."
                )
                logger.info("governance_jury_hitl_required", reason=reason)
                return True, reason, True

        # ── ArbitrationRequest -> always ACCEPT (low risk) ───────────────────
        if activity_type == "iskander:ArbitrationRequest":
            return True, "ArbitrationRequest accepted (filing is low-risk).", False

        # ── Default for any other governance-sensitive type ──────────────────
        if not settings.boundary_require_governance_proof:
            return True, "Governance proof not required by config.", False

        return True, "Governance verification passed.", False
