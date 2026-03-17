"""
Ontology Translator --- maps foreign SDC schemas to Iskander internals (Fix 7).

Foreign cooperatives may use different names for DisCO value streams, different
score ranges, or entirely different field names. This module:

  1. Detects the source scoring framework (iskander_v1, kleros_v1, colony_v1).
  2. Normalises stream names (German, Spanish, French variants).
  3. Normalises score values into the Iskander [0.0, 1.0] range.
  4. Quarantines unknown fields rather than dropping them.
  5. Flags suspicious near-matches (SequenceMatcher > 0.85) as SUSPICIOUS_TYPO.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# ── Stream name mappings ─────────────────────────────────────────────────────
# Foreign SDC networks may label the three DisCO value streams differently.
# All values are lowercased during lookup.

STREAM_MAPPINGS: Dict[str, str] = {
    # German
    "produktiv": "livelihood",
    "fuersorge": "care",
    "gemeinwohl": "commons",
    # Spanish
    "sustento": "livelihood",
    "cuidado": "care",
    "bien_comun": "commons",
    "biencomun": "commons",
    # French
    "subsistance": "livelihood",
    "soin": "care",
    "communs": "commons",
    # Pass-through (canonical Iskander names)
    "livelihood": "livelihood",
    "care": "care",
    "commons": "commons",
}

# ── Score framework detection heuristics ─────────────────────────────────────

KNOWN_FRAMEWORKS = {
    "iskander_v1": {"range": (0.0, 1.0), "divisor": 1.0},
    "kleros_v1": {"range": (0.0, 100.0), "divisor": 100.0},
    "colony_v1": {"range": (0.0, 10.0), "divisor": 10.0},
}

# Fields that Iskander recognises in an incoming activity object.
KNOWN_ACTIVITY_FIELDS = {
    "type", "actor", "object", "id", "@context", "to", "cc", "bto", "bcc",
    "published", "updated", "summary", "content", "name",
    "stream", "score", "hours", "care_score", "value_tokens",
    "member_did", "caseId", "auditRequestId", "governanceProof",
    "scoreFramework", "iskander:stream", "iskander:score",
}

# ── Fuzzy-match threshold ────────────────────────────────────────────────────
TYPO_THRESHOLD = 0.85


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class TranslationResult:
    """Outcome of translating a single foreign activity."""

    source_framework: str = "unknown"
    stream_mapped: bool = False
    original_stream: str | None = None
    target_stream: str | None = None
    score_normalised: bool = False
    original_score: float | None = None
    normalised_score: float | None = None
    quarantined_fields: Dict[str, Any] = field(default_factory=dict)
    suspicious_typos: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ── Translator ───────────────────────────────────────────────────────────────

class OntologyTranslator:
    """Stateless translator — one instance shared across the boundary agent."""

    _instance: "OntologyTranslator | None" = None

    @classmethod
    def get_instance(cls) -> "OntologyTranslator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ───────────────────────────────────────────────────────────

    def translate_activity(
        self,
        activity: dict[str, Any],
        actor_iri: str,
    ) -> TranslationResult:
        """Translate a foreign activity dict into Iskander-canonical form.

        Returns a :class:`TranslationResult` describing every mapping applied.
        The caller is responsible for merging the result into the activity dict.
        """
        result = TranslationResult()

        # 1. Detect scoring framework
        result.source_framework = self._detect_framework(activity)

        # 2. Translate stream name
        raw_stream = (
            activity.get("iskander:stream")
            or activity.get("stream")
            or (activity.get("object", {}) or {}).get("stream")
        )
        if raw_stream:
            mapped = STREAM_MAPPINGS.get(raw_stream.lower().strip())
            if mapped:
                result.stream_mapped = True
                result.original_stream = raw_stream
                result.target_stream = mapped
            else:
                result.quarantined_fields["stream"] = raw_stream
                result.warnings.append(
                    f"Unknown stream value '{raw_stream}' quarantined."
                )

        # 3. Normalise score
        raw_score = (
            activity.get("iskander:score")
            or activity.get("score")
            or (activity.get("object", {}) or {}).get("score")
        )
        if raw_score is not None:
            try:
                raw_score = float(raw_score)
            except (TypeError, ValueError):
                result.quarantined_fields["score"] = raw_score
                result.warnings.append(
                    f"Non-numeric score '{raw_score}' quarantined."
                )
                raw_score = None

        if raw_score is not None:
            fw = KNOWN_FRAMEWORKS.get(result.source_framework)
            if fw:
                normalised = raw_score / fw["divisor"]
                normalised = max(0.0, min(1.0, normalised))
                result.score_normalised = True
                result.original_score = raw_score
                result.normalised_score = normalised
            else:
                # Unknown framework: quarantine the score.
                result.quarantined_fields["score"] = raw_score
                result.warnings.append(
                    f"Score from unknown framework '{result.source_framework}' quarantined."
                )

        # 4. Quarantine unknown fields
        policy = settings.boundary_unknown_field_policy
        for key in activity:
            if key not in KNOWN_ACTIVITY_FIELDS:
                typo_match = self._check_suspicious_typos(key, KNOWN_ACTIVITY_FIELDS)
                if typo_match:
                    result.suspicious_typos.append(
                        f"'{key}' looks like '{typo_match}' (SUSPICIOUS_TYPO)"
                    )
                if policy == "quarantine":
                    result.quarantined_fields[key] = activity[key]

        if result.quarantined_fields:
            logger.info(
                "ontology_translation_quarantined_fields",
                actor_iri=actor_iri,
                fields=list(result.quarantined_fields.keys()),
                framework=result.source_framework,
            )

        return result

    # ── Framework detection ──────────────────────────────────────────────────

    def _detect_framework(self, activity: dict[str, Any]) -> str:
        """Heuristically detect the scoring framework of an activity.

        Checks for explicit ``scoreFramework`` field first, then infers from
        score range.
        """
        explicit = activity.get("scoreFramework")
        if explicit and explicit in KNOWN_FRAMEWORKS:
            return str(explicit)

        # Infer from score value range
        raw_score = (
            activity.get("iskander:score")
            or activity.get("score")
            or (activity.get("object", {}) or {}).get("score")
        )
        if raw_score is not None:
            try:
                val = float(raw_score)
            except (TypeError, ValueError):
                return "unknown"

            if 0.0 <= val <= 1.0:
                return "iskander_v1"
            elif 0.0 <= val <= 10.0:
                return "colony_v1"
            elif 0.0 <= val <= 100.0:
                return "kleros_v1"

        return "unknown"

    # ── Typo detection ───────────────────────────────────────────────────────

    @staticmethod
    def _check_suspicious_typos(
        field_name: str,
        known_fields: set[str],
    ) -> Optional[str]:
        """Return the best fuzzy match if ratio > TYPO_THRESHOLD, else None."""
        best_match: Optional[str] = None
        best_ratio = 0.0
        for known in known_fields:
            ratio = SequenceMatcher(None, field_name.lower(), known.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = known
        if best_ratio > TYPO_THRESHOLD and best_match != field_name:
            return best_match
        return None
