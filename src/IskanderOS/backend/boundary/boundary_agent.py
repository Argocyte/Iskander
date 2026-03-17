"""
Boundary Agent / Embassy --- orchestrator singleton (Fix 7).

Runs five layers in sequence on every inbound foreign activity:

  1. **Trust Quarantine** --- assess/update the foreign identity's trust profile.
  2. **Ontology Translation** --- map foreign schemas to Iskander canonical form.
  3. **Governance Verification** --- check governance guarantees for sensitive types.
  4. **Causal Ordering** --- buffer or release based on causal dependencies.
  5. **Glass Box Wrapping** --- produce an AgentAction chain for audit.

Usage::

    verdicts = await BoundaryAgent.get_instance().ingest(activity, local_handle)
    for v in verdicts:
        if v.proceed:
            await inbox_processor.process(v.translated_activity, local_handle)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import structlog

from backend.boundary.causal_buffer import CausalBuffer
from backend.boundary.governance_verifier import GovernanceCapabilities, GovernanceVerifier
from backend.boundary.ontology_translator import OntologyTranslator, TranslationResult
from backend.boundary.trust_quarantine import ForeignIdentityProfile, TrustQuarantine
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = structlog.get_logger(__name__)

AGENT_ID = "boundary-agent-v1"


# ── Verdict dataclass ────────────────────────────────────────────────────────

@dataclass
class BoundaryVerdict:
    """Result of processing a single activity through the Boundary Agent."""

    proceed: bool
    actor_iri: str
    trust_profile: ForeignIdentityProfile
    translation: TranslationResult
    governance_capabilities: GovernanceCapabilities
    governance_ok: bool = True
    governance_reason: str = ""
    requires_hitl: bool = False
    causal_buffered: bool = False
    agent_actions: List[AgentAction] = field(default_factory=list)
    original_activity: Dict[str, Any] = field(default_factory=dict)
    translated_activity: Dict[str, Any] = field(default_factory=dict)


# ── Boundary Agent ───────────────────────────────────────────────────────────

class BoundaryAgent:
    """Orchestrator singleton for the federation boundary.

    Obtain via ``BoundaryAgent.get_instance()``.
    """

    _instance: "BoundaryAgent | None" = None

    def __init__(self) -> None:
        self._quarantine = TrustQuarantine.get_instance()
        self._translator = OntologyTranslator.get_instance()
        self._governance = GovernanceVerifier.get_instance()
        self._causal = CausalBuffer.get_instance()

    @classmethod
    def get_instance(cls) -> "BoundaryAgent":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Primary entry point (ActivityPub inbox) ──────────────────────────────

    async def ingest(
        self,
        activity: Dict[str, Any],
        local_handle: str,
    ) -> List[BoundaryVerdict]:
        """Run the five-layer boundary pipeline on *activity*.

        Returns a list of :class:`BoundaryVerdict` objects --- typically one,
        but may include previously buffered activities released by this event.
        """
        actor_iri = activity.get("actor", "unknown")
        activity_type = activity.get("type", "Unknown")
        actions: List[AgentAction] = []

        # ── Layer 1: Trust Quarantine ────────────────────────────────────────
        trust_profile = self._quarantine.get_or_create_profile(actor_iri)
        actions.append(AgentAction(
            agent_id=AGENT_ID,
            action="trust_quarantine_assess",
            rationale=(
                f"Assessed foreign identity {actor_iri}: "
                f"trust_penalty={trust_profile.trust_penalty:.4f}, "
                f"interactions={trust_profile.interaction_count}."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={
                "actor_iri": actor_iri,
                "trust_penalty": trust_profile.trust_penalty,
                "interaction_count": trust_profile.interaction_count,
            },
        ))

        # ── Layer 2: Ontology Translation ────────────────────────────────────
        translation = self._translator.translate_activity(activity, actor_iri)
        translated = self._apply_translation(activity, translation)

        if translation.quarantined_fields or translation.suspicious_typos:
            actions.append(AgentAction(
                agent_id=AGENT_ID,
                action="ontology_translation_quarantine",
                rationale=(
                    f"Quarantined {len(translation.quarantined_fields)} unknown field(s) "
                    f"from {actor_iri} (framework: {translation.source_framework}). "
                    f"Typos flagged: {len(translation.suspicious_typos)}."
                ),
                ethical_impact=EthicalImpactLevel.MEDIUM,
                payload={
                    "quarantined_fields": list(translation.quarantined_fields.keys()),
                    "suspicious_typos": translation.suspicious_typos,
                    "source_framework": translation.source_framework,
                },
            ))

        # ── Layer 3: Governance Verification ─────────────────────────────────
        gov_ok = True
        gov_reason = "No governance verification required."
        gov_hitl = False
        capabilities = GovernanceCapabilities()

        if self._governance.requires_verification(activity_type):
            capabilities = self._governance.assess_capabilities(activity, actor_iri)
            gov_ok, gov_reason, gov_hitl = self._governance.evaluate(
                activity, capabilities
            )
            actions.append(AgentAction(
                agent_id=AGENT_ID,
                action="governance_verification",
                rationale=gov_reason,
                ethical_impact=EthicalImpactLevel.HIGH if not gov_ok else EthicalImpactLevel.MEDIUM,
                payload={
                    "activity_type": activity_type,
                    "governance_ok": gov_ok,
                    "requires_hitl": gov_hitl,
                    "capabilities": {
                        "human_jury": capabilities.human_jury,
                        "zk_voting": capabilities.zk_voting,
                        "sbt_identity": capabilities.sbt_identity,
                    },
                },
            ))

        if not gov_ok:
            # Governance rejection: update trust penalty and return immediately.
            self._quarantine.record_outcome(actor_iri, quarantined=True, activity_type=activity_type)
            return [BoundaryVerdict(
                proceed=False,
                actor_iri=actor_iri,
                trust_profile=trust_profile,
                translation=translation,
                governance_capabilities=capabilities,
                governance_ok=False,
                governance_reason=gov_reason,
                requires_hitl=False,
                causal_buffered=False,
                agent_actions=actions,
                original_activity=activity,
                translated_activity=translated,
            )]

        # ── Layer 4: Causal Ordering ─────────────────────────────────────────
        ready_pairs = self._causal.ingest(translated, local_handle)

        if not ready_pairs:
            # Activity was buffered --- nothing to release yet.
            actions.append(AgentAction(
                agent_id=AGENT_ID,
                action="causal_buffer_hold",
                rationale=(
                    f"Activity {activity_type} from {actor_iri} buffered: "
                    f"causal predecessor not yet received."
                ),
                ethical_impact=EthicalImpactLevel.LOW,
                payload={"activity_type": activity_type, "actor_iri": actor_iri},
            ))
            self._quarantine.record_outcome(actor_iri, quarantined=False, activity_type=activity_type)
            return [BoundaryVerdict(
                proceed=False,
                actor_iri=actor_iri,
                trust_profile=trust_profile,
                translation=translation,
                governance_capabilities=capabilities,
                governance_ok=True,
                governance_reason=gov_reason,
                requires_hitl=gov_hitl,
                causal_buffered=True,
                agent_actions=actions,
                original_activity=activity,
                translated_activity=translated,
            )]

        # ── Layer 5: Glass Box Wrapping & Verdict Assembly ───────────────────
        verdicts: List[BoundaryVerdict] = []
        for ready_activity, ready_handle in ready_pairs:
            ready_actor = ready_activity.get("actor", actor_iri)
            self._quarantine.record_outcome(
                ready_actor, quarantined=False,
                activity_type=ready_activity.get("type", ""),
            )

            verdict_actions = list(actions)  # Copy shared actions for first item.
            verdict_actions.append(AgentAction(
                agent_id=AGENT_ID,
                action="boundary_accept",
                rationale=(
                    f"Activity {ready_activity.get('type', 'Unknown')} from "
                    f"{ready_actor} passed all boundary checks. "
                    f"Forwarding to inbox processor."
                ),
                ethical_impact=EthicalImpactLevel.MEDIUM,
                payload={
                    "activity_type": ready_activity.get("type"),
                    "actor_iri": ready_actor,
                    "governance_hitl": gov_hitl,
                },
            ))

            verdicts.append(BoundaryVerdict(
                proceed=True,
                actor_iri=ready_actor,
                trust_profile=self._quarantine.get_or_create_profile(ready_actor),
                translation=translation,
                governance_capabilities=capabilities,
                governance_ok=True,
                governance_reason=gov_reason,
                requires_hitl=gov_hitl,
                causal_buffered=False,
                agent_actions=verdict_actions,
                original_activity=activity,
                translated_activity=ready_activity,
            ))

        logger.info(
            "boundary_agent_ingested",
            actor_iri=actor_iri,
            activity_type=activity_type,
            verdicts_produced=len(verdicts),
            any_hitl=any(v.requires_hitl for v in verdicts),
        )

        return verdicts

    # ── Delta-sync entry point ───────────────────────────────────────────────

    def ingest_sync(
        self,
        peer_did: str,
        cids: List[str],
    ) -> Tuple[List[str], List[str], List[AgentAction]]:
        """Boundary check for delta-sync CID ingestion.

        Returns ``(accepted_cids, denied_cids, agent_actions)``.

        Currently applies trust-quarantine discount: if the peer's penalty is
        above 0.5, all CIDs are denied.  Otherwise all are accepted.
        Future: per-CID content inspection.
        """
        profile = self._quarantine.get_or_create_profile(peer_did)
        actions: List[AgentAction] = []

        if profile.trust_penalty > 0.5:
            actions.append(AgentAction(
                agent_id=AGENT_ID,
                action="delta_sync_denied",
                rationale=(
                    f"Peer {peer_did} has trust_penalty={profile.trust_penalty:.4f} "
                    f"(> 0.5 threshold). All {len(cids)} CIDs denied."
                ),
                ethical_impact=EthicalImpactLevel.HIGH,
                payload={"peer_did": peer_did, "denied_cids": cids},
            ))
            self._quarantine.record_outcome(peer_did, quarantined=True, activity_type="delta_sync")
            return [], list(cids), actions

        actions.append(AgentAction(
            agent_id=AGENT_ID,
            action="delta_sync_accepted",
            rationale=(
                f"Peer {peer_did} has trust_penalty={profile.trust_penalty:.4f} "
                f"(within threshold). {len(cids)} CIDs accepted."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"peer_did": peer_did, "accepted_cids": cids},
        ))
        self._quarantine.record_outcome(peer_did, quarantined=False, activity_type="delta_sync")
        return list(cids), [], actions

    # ── Translation application ──────────────────────────────────────────────

    @staticmethod
    def _apply_translation(
        activity: Dict[str, Any],
        translation: TranslationResult,
    ) -> Dict[str, Any]:
        """Return a copy of *activity* with translation mappings applied."""
        translated = dict(activity)

        if translation.stream_mapped and translation.target_stream:
            # Update stream in top-level and nested object.
            if "iskander:stream" in translated:
                translated["iskander:stream"] = translation.target_stream
            if "stream" in translated:
                translated["stream"] = translation.target_stream
            obj = translated.get("object")
            if isinstance(obj, dict) and "stream" in obj:
                translated["object"] = dict(obj)
                translated["object"]["stream"] = translation.target_stream

        if translation.score_normalised and translation.normalised_score is not None:
            if "iskander:score" in translated:
                translated["iskander:score"] = translation.normalised_score
            if "score" in translated:
                translated["score"] = translation.normalised_score
            obj = translated.get("object")
            if isinstance(obj, dict) and "score" in obj:
                if not isinstance(translated.get("object"), dict) or translated["object"] is obj:
                    translated["object"] = dict(obj)
                translated["object"]["score"] = translation.normalised_score

        return translated
