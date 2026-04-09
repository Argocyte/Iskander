"""
frs_client.py — Python bridge to the ForeignReputation.sol contract.

Translates between the Python domain (DIDs, basis points, Pydantic models)
and the on-chain FRS contract (bytes32 sdcId, uint256 scores, events).

STUB NOTICE:
    In development, all Web3 calls are stubbed with deterministic in-memory
    state. In production, set ``frs_contract_address`` in config and provide
    the deployer private key.

GLASS BOX:
    Every public method returns an ``AgentAction`` recording what happened.

DESIGN:
    - Lazy decay is computed on-chain; this client reads getCurrentScore().
    - The Python side only calls recordTransaction() when the BoundaryAgent
      or IngestionEmbassy has a Valueflows event to anchor.
    - Tier checks (getCurrentTier) are used by AccessMiddleware to gate
      federation endpoints per SDC.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone

from backend.config import settings
from backend.schemas.diplomacy import (
    ReputationTier,
    SDCReputationProfile,
)
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "frs-client-v1"


class FRSClient:
    """Singleton Python bridge to the ForeignReputation.sol contract.

    Obtain via ``FRSClient.get_instance()``.

    STUB: In development, uses in-memory state mirroring the contract's
    logic (exponential decay, tier thresholds, delta caps). In production,
    replace ``_stub_*`` methods with Web3 contract calls.
    """

    _instance: FRSClient | None = None

    def __init__(self) -> None:
        # In-memory stub registry: sdc_did -> profile data
        self._profiles: dict[str, dict] = {}
        # Config mirrors contract constructor args
        self._quarantine_threshold = settings.frs_quarantine_threshold_bps
        self._provisional_threshold = settings.frs_provisional_threshold_bps
        self._trusted_threshold = settings.frs_trusted_threshold_bps
        self._half_life_seconds = settings.frs_decay_half_life_seconds
        self._max_delta = 500  # MAX_DELTA_PER_TX from contract

    @classmethod
    def get_instance(cls) -> FRSClient:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton."""
        cls._instance = None

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    def sdc_id_hash(self, sdc_did: str) -> str:
        """Compute keccak256 hash of a DID (mirrors contract's bytes32 sdcId)."""
        # STUB: Use SHA-256 in dev (keccak256 in production via web3)
        return "0x" + hashlib.sha256(sdc_did.encode()).hexdigest()

    def register_sdc(
        self, sdc_did: str, initial_score: int = 1000,
    ) -> tuple[SDCReputationProfile, AgentAction]:
        """Register a new foreign SDC with an initial reputation score.

        Raises:
            ValueError: If SDC already registered or score exceeds 10000.
        """
        if sdc_did in self._profiles:
            raise ValueError(f"SDC already registered: {sdc_did}")
        if initial_score > 10000:
            raise ValueError(f"Initial score exceeds maximum: {initial_score}")

        now = time.time()
        self._profiles[sdc_did] = {
            "raw_score": initial_score,
            "last_updated": now,
            "force_quarantined": False,
            "tx_count": 0,
        }

        profile = self._build_profile(sdc_did)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="register_foreign_sdc",
            rationale=(
                f"Registered foreign SDC '{sdc_did}' with initial score "
                f"{initial_score} bps (tier {profile.tier.name}). "
                f"sdcIdHash: {profile.sdc_id_hash}"
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "sdc_did": sdc_did,
                "sdc_id_hash": profile.sdc_id_hash,
                "initial_score": initial_score,
                "tier": profile.tier.value,
            },
        )

        logger.info("Registered foreign SDC: did=%s score=%d tier=%s",
                     sdc_did, initial_score, profile.tier.name)
        return profile, action

    def record_transaction(
        self,
        sdc_did: str,
        score_delta: int,
        tx_cid: str,
        rationale: str,
    ) -> tuple[SDCReputationProfile, AgentAction]:
        """Record a Valueflows transaction outcome and update the SDC's score.

        Raises:
            ValueError: If SDC not registered, or delta exceeds ±500.
        """
        if sdc_did not in self._profiles:
            raise ValueError(f"SDC not registered: {sdc_did}")
        if abs(score_delta) > self._max_delta:
            raise ValueError(
                f"Delta {score_delta} exceeds maximum ±{self._max_delta}"
            )

        data = self._profiles[sdc_did]
        now = time.time()

        # Apply decay first
        current_score = self._compute_decay(
            data["raw_score"], data["last_updated"], now,
        )
        previous_score = current_score
        previous_tier = self._score_tier(current_score, data["force_quarantined"])

        # Apply delta with clamping
        if score_delta >= 0:
            current_score = min(current_score + score_delta, 10000)
        else:
            current_score = max(current_score + score_delta, 0)

        # Update stored state (decay resets from now)
        data["raw_score"] = current_score
        data["last_updated"] = now
        data["tx_count"] += 1

        profile = self._build_profile(sdc_did)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="record_frs_transaction",
            rationale=(
                f"Recorded Valueflows transaction for SDC '{sdc_did}': "
                f"delta={score_delta:+d} bps, "
                f"score {previous_score}→{current_score}, "
                f"tier {previous_tier.name}→{profile.tier.name}. "
                f"txCid: {tx_cid}. Reason: {rationale}"
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "sdc_did": sdc_did,
                "score_delta": score_delta,
                "previous_score": previous_score,
                "new_score": current_score,
                "previous_tier": previous_tier.value,
                "new_tier": profile.tier.value,
                "tx_cid": tx_cid,
            },
        )

        logger.info(
            "FRS transaction: sdc=%s delta=%+d score=%d->%d tier=%s->%s",
            sdc_did, score_delta, previous_score, current_score,
            previous_tier.name, profile.tier.name,
        )
        return profile, action

    def get_profile(self, sdc_did: str) -> tuple[SDCReputationProfile, AgentAction]:
        """Get the current reputation profile for an SDC.

        Raises:
            KeyError: If SDC not registered.
        """
        if sdc_did not in self._profiles:
            raise KeyError(f"SDC not registered: {sdc_did}")

        profile = self._build_profile(sdc_did)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="get_frs_profile",
            rationale=f"Retrieved FRS profile for SDC '{sdc_did}': score={profile.decayed_score}, tier={profile.tier.name}.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"sdc_did": sdc_did, "tier": profile.tier.value, "score": profile.decayed_score},
        )
        return profile, action

    def get_tier(self, sdc_did: str) -> ReputationTier:
        """Quick tier lookup for AccessMiddleware gating."""
        if sdc_did not in self._profiles:
            return ReputationTier.QUARANTINE  # Unknown SDCs default to quarantine

        data = self._profiles[sdc_did]
        now = time.time()
        score = self._compute_decay(data["raw_score"], data["last_updated"], now)
        return self._score_tier(score, data["force_quarantined"])

    def force_quarantine(self, sdc_did: str, rationale_cid: str) -> AgentAction:
        """Force-quarantine an SDC (council override).

        Raises:
            KeyError: If SDC not registered.
        """
        if sdc_did not in self._profiles:
            raise KeyError(f"SDC not registered: {sdc_did}")

        self._profiles[sdc_did]["force_quarantined"] = True

        return AgentAction(
            agent_id=AGENT_ID,
            action="force_quarantine_sdc",
            rationale=f"Force-quarantined SDC '{sdc_did}'. Rationale CID: {rationale_cid}",
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"sdc_did": sdc_did, "rationale_cid": rationale_cid},
        )

    def lift_quarantine(self, sdc_did: str) -> AgentAction:
        """Lift a force-quarantine.

        Raises:
            KeyError: If SDC not registered.
        """
        if sdc_did not in self._profiles:
            raise KeyError(f"SDC not registered: {sdc_did}")

        self._profiles[sdc_did]["force_quarantined"] = False

        return AgentAction(
            agent_id=AGENT_ID,
            action="lift_quarantine_sdc",
            rationale=f"Lifted force-quarantine for SDC '{sdc_did}'. Score-based tier resumes.",
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={"sdc_did": sdc_did},
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # INTERNAL: Decay + Tier Logic (mirrors ForeignReputation.sol)
    # ═══════════════════════════════════════════════════════════════════════════

    def _compute_decay(
        self, raw_score: int, last_updated: float, now: float,
    ) -> int:
        """Exponential decay: score * 2^(-elapsed / halfLife).

        Mirrors _computeDecayedScore in ForeignReputation.sol.
        """
        if raw_score == 0:
            return 0
        if now <= last_updated:
            return raw_score

        elapsed = now - last_updated
        half_life = float(self._half_life_seconds)

        full_half_lives = int(elapsed / half_life)
        if full_half_lives >= 13:
            return 0

        # Bit-shift for full half-lives
        decayed = raw_score >> full_half_lives
        if decayed == 0:
            return 0

        # Linear interpolation for fractional half-life
        remainder = elapsed % half_life
        if remainder > 0:
            next_half = decayed >> 1
            fractional_decay = int(((decayed - next_half) * remainder) / half_life)
            decayed -= fractional_decay

        return decayed

    def _score_tier(self, score: int, force_quarantined: bool) -> ReputationTier:
        """Compute tier from score. Mirrors _scoreTier in contract."""
        if force_quarantined:
            return ReputationTier.QUARANTINE

        if score < self._quarantine_threshold:
            return ReputationTier.QUARANTINE
        if score < self._provisional_threshold:
            return ReputationTier.PROVISIONAL
        if score < self._trusted_threshold:
            return ReputationTier.TRUSTED
        return ReputationTier.ALLIED

    def _build_profile(self, sdc_did: str) -> SDCReputationProfile:
        """Build a SDCReputationProfile from in-memory state."""
        data = self._profiles[sdc_did]
        now = time.time()
        decayed = self._compute_decay(data["raw_score"], data["last_updated"], now)
        tier = self._score_tier(decayed, data["force_quarantined"])

        return SDCReputationProfile(
            sdc_did=sdc_did,
            sdc_id_hash=self.sdc_id_hash(sdc_did),
            raw_score=data["raw_score"],
            decayed_score=decayed,
            tier=tier,
            last_updated=datetime.fromtimestamp(data["last_updated"], tz=timezone.utc),
            force_quarantined=data["force_quarantined"],
            tx_count=data["tx_count"],
        )
