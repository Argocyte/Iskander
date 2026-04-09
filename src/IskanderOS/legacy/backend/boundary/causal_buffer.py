"""
Causal Buffer --- buffers out-of-order ActivityPub activities (Fix 7).

Some Iskander governance activities have causal predecessors: a Verdict
requires a prior ArbitrationRequest with the same ``caseId``, an
AuditResponse requires a prior AuditRequest with the same ``auditRequestId``.

This module holds activities whose causal predecessors have not yet arrived.
When a predecessor arrives, all buffered dependants are released together.

Design constraints:
  - max_age: 300 s (configurable). Expired activities are released with a
    warning --- never silently dropped.
  - max_size: 1000 buffered activities total.
  - per-actor limit: 50 buffered activities. Excess activities from the same
    actor are released with a warning.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# ── Causal dependency map ────────────────────────────────────────────────────
# key: activity type that REQUIRES a predecessor
# value: (required predecessor type, linking field name)

CAUSAL_PREDECESSORS: Dict[str, Tuple[str, str]] = {
    "iskander:Verdict": ("iskander:ArbitrationRequest", "caseId"),
    "iskander:AuditResponse": ("iskander:AuditRequest", "auditRequestId"),
}


# ── Buffered entry ───────────────────────────────────────────────────────────

@dataclass
class _BufferedActivity:
    """An activity waiting for its causal predecessor."""

    activity: Dict[str, Any]
    local_handle: str
    activity_type: str
    actor_iri: str
    causal_key: str
    required_type: str
    buffered_at: float = field(default_factory=time.time)


# ── Causal buffer ────────────────────────────────────────────────────────────

class CausalBuffer:
    """In-memory causal ordering buffer.

    Singleton: obtain via ``CausalBuffer.get_instance()``.
    """

    _instance: "CausalBuffer | None" = None

    def __init__(self) -> None:
        # Keyed by (required_type, causal_key_value) -> list of buffered items.
        self._buffer: Dict[Tuple[str, str], List[_BufferedActivity]] = {}
        # Track per-actor counts.
        self._actor_counts: Dict[str, int] = {}
        # Set of (activity_type, causal_key_value) that have been seen.
        self._seen: set[Tuple[str, str]] = set()

    @classmethod
    def get_instance(cls) -> "CausalBuffer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ───────────────────────────────────────────────────────────

    def ingest(
        self,
        activity: Dict[str, Any],
        local_handle: str,
    ) -> List[Tuple[Dict[str, Any], str]]:
        """Process an activity through the causal buffer.

        Returns a list of ``(activity, local_handle)`` tuples that are ready
        to proceed --- either the input itself (if no buffering needed) or
        previously buffered activities that are now unblocked, plus the input.
        """
        released: List[Tuple[Dict[str, Any], str]] = []

        # Flush expired entries first.
        released.extend(self._flush_expired())

        activity_type = activity.get("type", "")
        actor_iri = activity.get("actor", "")

        # Record this activity type + key as "seen" so future dependants
        # can be released immediately.
        for dep_type, (_, link_field) in CAUSAL_PREDECESSORS.items():
            key_value = activity.get(link_field) or (activity.get("object", {}) or {}).get(link_field)
            if key_value:
                self._seen.add((activity_type, str(key_value)))

        # Check if this activity itself needs a predecessor.
        dep = CAUSAL_PREDECESSORS.get(activity_type)
        if dep:
            required_type, link_field = dep
            key_value = activity.get(link_field) or (activity.get("object", {}) or {}).get(link_field)

            if key_value and (required_type, str(key_value)) not in self._seen:
                # Predecessor not yet seen: buffer this activity.
                if self._should_buffer(actor_iri):
                    entry = _BufferedActivity(
                        activity=activity,
                        local_handle=local_handle,
                        activity_type=activity_type,
                        actor_iri=actor_iri,
                        causal_key=str(key_value),
                        required_type=required_type,
                    )
                    buf_key = (required_type, str(key_value))
                    self._buffer.setdefault(buf_key, []).append(entry)
                    self._actor_counts[actor_iri] = self._actor_counts.get(actor_iri, 0) + 1
                    logger.info(
                        "causal_buffer_activity_held",
                        activity_type=activity_type,
                        waiting_for=required_type,
                        causal_key=str(key_value),
                        actor_iri=actor_iri,
                        buffer_size=self.buffer_size(),
                    )
                    return released  # Do not include the current activity.
                else:
                    # Buffer limits exceeded: release with warning.
                    logger.warning(
                        "causal_buffer_limit_exceeded_releasing",
                        activity_type=activity_type,
                        actor_iri=actor_iri,
                    )

        # Release the current activity.
        released.append((activity, local_handle))

        # Check if this activity satisfies any buffered dependants.
        released.extend(self._release_dependants(activity))

        return released

    def buffer_size(self) -> int:
        """Total number of buffered activities."""
        return sum(len(v) for v in self._buffer.values())

    # ── Internal ─────────────────────────────────────────────────────────────

    def _should_buffer(self, actor_iri: str) -> bool:
        """Check global and per-actor buffer limits."""
        if self.buffer_size() >= settings.boundary_causal_buffer_max_size:
            return False
        if self._actor_counts.get(actor_iri, 0) >= 50:
            return False
        return True

    def _release_dependants(
        self,
        activity: Dict[str, Any],
    ) -> List[Tuple[Dict[str, Any], str]]:
        """Release buffered activities whose predecessor just arrived."""
        released: List[Tuple[Dict[str, Any], str]] = []
        activity_type = activity.get("type", "")

        keys_to_remove: List[Tuple[str, str]] = []
        for buf_key, entries in self._buffer.items():
            req_type, key_value = buf_key
            if req_type != activity_type:
                continue
            # Check that the arriving activity carries the matching key value.
            for dep_type, (pred_type, link_field) in CAUSAL_PREDECESSORS.items():
                if pred_type != activity_type:
                    continue
                arriving_key = activity.get(link_field) or (activity.get("object", {}) or {}).get(link_field)
                if arriving_key and str(arriving_key) == key_value:
                    for entry in entries:
                        released.append((entry.activity, entry.local_handle))
                        self._actor_counts[entry.actor_iri] = max(
                            0, self._actor_counts.get(entry.actor_iri, 1) - 1
                        )
                        logger.info(
                            "causal_buffer_activity_released",
                            activity_type=entry.activity_type,
                            causal_key=key_value,
                        )
                    keys_to_remove.append(buf_key)

        for key in keys_to_remove:
            self._buffer.pop(key, None)

        return released

    def _flush_expired(self) -> List[Tuple[Dict[str, Any], str]]:
        """Release all entries older than ``max_age`` with a warning."""
        released: List[Tuple[Dict[str, Any], str]] = []
        now = time.time()
        max_age = settings.boundary_causal_buffer_max_age_seconds

        keys_to_clean: List[Tuple[str, str]] = []
        for buf_key, entries in self._buffer.items():
            remaining: List[_BufferedActivity] = []
            for entry in entries:
                if now - entry.buffered_at > max_age:
                    logger.warning(
                        "causal_buffer_expired_releasing",
                        activity_type=entry.activity_type,
                        actor_iri=entry.actor_iri,
                        causal_key=entry.causal_key,
                        age_seconds=round(now - entry.buffered_at, 1),
                    )
                    released.append((entry.activity, entry.local_handle))
                    self._actor_counts[entry.actor_iri] = max(
                        0, self._actor_counts.get(entry.actor_iri, 1) - 1
                    )
                else:
                    remaining.append(entry)
            if not remaining:
                keys_to_clean.append(buf_key)
            else:
                self._buffer[buf_key] = remaining

        for key in keys_to_clean:
            self._buffer.pop(key, None)

        return released
