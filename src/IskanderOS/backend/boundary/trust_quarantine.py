"""
Trust Quarantine --- foreign identity risk scoring (Fix 7).

New foreign identities start with a trust penalty that decays through
successful interactions and grows when activities are quarantined.

Design:
  - trust_penalty starts at 0.3 (configurable via settings).
  - Successful (non-quarantined) interactions reduce penalty by 0.02,
    weighted by the interaction's risk class.
  - Quarantined interactions increase penalty by 0.1.
  - Penalty is clamped to [0.0, 1.0].
  - Applied as a discount: effective_score = raw_score * (1.0 - trust_penalty).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# ── Interaction risk weights ─────────────────────────────────────────────────
# Low-risk social actions earn only 25 % of the recovery rate per success.
# Governance-sensitive actions earn the full 100 %.

INTERACTION_RISK_WEIGHTS: Dict[str, float] = {
    # Standard ActivityPub
    "Follow": 0.25,
    "Accept": 0.25,
    "Announce": 0.25,
    "Create": 0.5,
    "Undo": 0.25,
    # Iskander governance extensions
    "iskander:AuditRequest": 1.0,
    "iskander:AuditResponse": 1.0,
    "iskander:ArbitrationRequest": 1.0,
    "iskander:Verdict": 1.0,
    "iskander:JuryNomination": 1.0,
    "iskander:HITLProposalVote": 1.0,
    "iskander:HITLProposal": 1.0,
    "iskander:AuditSummary": 1.0,
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ForeignIdentityProfile:
    """Mutable trust profile for a single foreign actor IRI."""

    actor_iri: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0
    cooperation_count: int = 0
    quarantine_count: int = 0
    trust_penalty: float = field(default_factory=lambda: settings.boundary_initial_trust_penalty)
    declared_capabilities: dict = field(default_factory=dict)


# ── Quarantine engine ─────────────────────────────────────────────────────────

class TrustQuarantine:
    """In-memory trust quarantine engine.

    Singleton: obtain via ``TrustQuarantine.get_instance()``.
    Production deployments should persist profiles to the
    ``foreign_identity_trust`` Postgres table on every mutation.
    """

    _instance: "TrustQuarantine | None" = None

    def __init__(self) -> None:
        self._profiles: Dict[str, ForeignIdentityProfile] = {}

    @classmethod
    def get_instance(cls) -> "TrustQuarantine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Profile access ───────────────────────────────────────────────────────

    def get_or_create_profile(self, actor_iri: str) -> ForeignIdentityProfile:
        """Return the existing profile or create a fresh quarantined one."""
        if actor_iri not in self._profiles:
            profile = ForeignIdentityProfile(actor_iri=actor_iri)
            self._profiles[actor_iri] = profile
            logger.info(
                "trust_quarantine_new_identity",
                actor_iri=actor_iri,
                initial_penalty=profile.trust_penalty,
            )
        return self._profiles[actor_iri]

    # ── Outcome recording ────────────────────────────────────────────────────

    def record_outcome(
        self,
        actor_iri: str,
        quarantined: bool,
        activity_type: str = "",
    ) -> ForeignIdentityProfile:
        """Record the outcome of processing an activity from *actor_iri*.

        Parameters
        ----------
        actor_iri:
            The foreign actor's IRI.
        quarantined:
            ``True`` if the activity was quarantined / rejected.
        activity_type:
            The ActivityPub ``type`` field, used for risk-weight lookup.

        Returns
        -------
        The updated :class:`ForeignIdentityProfile`.
        """
        profile = self.get_or_create_profile(actor_iri)
        profile.interaction_count += 1
        profile.last_seen = time.time()

        if quarantined:
            profile.quarantine_count += 1
            profile.trust_penalty = min(
                1.0,
                profile.trust_penalty + settings.boundary_trust_decay_rate,
            )
            logger.warning(
                "trust_quarantine_penalty_increased",
                actor_iri=actor_iri,
                new_penalty=round(profile.trust_penalty, 4),
                activity_type=activity_type,
            )
        else:
            profile.cooperation_count += 1
            weight = INTERACTION_RISK_WEIGHTS.get(activity_type, 0.5)
            recovery = settings.boundary_trust_recovery_rate * weight
            profile.trust_penalty = max(0.0, profile.trust_penalty - recovery)
            logger.debug(
                "trust_quarantine_penalty_reduced",
                actor_iri=actor_iri,
                new_penalty=round(profile.trust_penalty, 4),
                activity_type=activity_type,
                weight=weight,
            )

        return profile

    # ── Discount application ─────────────────────────────────────────────────

    def apply_discount(self, raw_score: float, actor_iri: str) -> float:
        """Return *raw_score* discounted by the actor's current trust penalty.

        ``effective_score = raw_score * (1.0 - trust_penalty)``
        """
        profile = self.get_or_create_profile(actor_iri)
        return raw_score * (1.0 - profile.trust_penalty)
