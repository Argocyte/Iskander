"""
causal_event.py — Immutable causal event creation & pinning (Phase 25).

A ``CausalEvent`` encrypts its payload for a target audience, pins the
ciphertext to IPFS via ``SovereignStorage``, and returns a typed record
with the resulting CID and metadata.

GLASS BOX:
  create() → AgentAction with EthicalImpactLevel.MEDIUM
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import hashlib

from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "causal-event"


# ── Record ───────────────────────────────────────────────────────────────────


@dataclass
class CausalEventRecord:
    """Immutable record returned after a causal event is created and pinned."""

    id: str
    event_type: str
    source_agent_id: str
    ipfs_cid: str
    audience: str
    timestamp: datetime
    on_chain_anchor: str | None = None


# ── Creator ──────────────────────────────────────────────────────────────────


class CausalEvent:
    """Factory for creating and pinning causal events.

    Usage::

        record, action = await CausalEvent.create(
            event_type="proposal.submitted",
            source_agent_id="steward-agent-v1",
            payload={"proposal_id": "abc123"},
            audience="council",
        )
    """

    @staticmethod
    async def create(
        event_type: str,
        source_agent_id: str,
        payload: dict[str, Any],
        audience: str = "federation",
    ) -> tuple[CausalEventRecord, AgentAction]:
        """Create a causal event, encrypt its payload, and pin to IPFS.

        Returns ``(record, agent_action)``.
        """
        event_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Serialise payload to JSON bytes.
        blob = json.dumps(
            {
                "id": event_id,
                "event_type": event_type,
                "source_agent_id": source_agent_id,
                "payload": payload,
                "timestamp": now.isoformat(),
            },
            separators=(",", ":"),
        ).encode()

        # Encrypt & pin.
        # Fix 3: governance events require federated replication (min 3 replicas).
        _governance_pin_prefixes = ("governance.", "proposal.", "council.", "veto.")
        min_replicas = 3 if event_type.startswith(_governance_pin_prefixes) else 0

        storage = SovereignStorage.get_instance()
        cid, _replica_count, _pin_action = await storage.pin(
            blob, audience=audience, min_replicas=min_replicas,
        )

        # ── Chain anchor for governance events (Fix 4) ────────────────────
        on_chain_anchor: str | None = None
        if CausalEvent._is_governance_event(event_type):
            on_chain_anchor = await CausalEvent.anchor_to_chain(cid)
            logger.info(
                "Governance event anchored on-chain: cid=%s anchor=%s",
                cid,
                on_chain_anchor,
            )

        record = CausalEventRecord(
            id=event_id,
            event_type=event_type,
            source_agent_id=source_agent_id,
            ipfs_cid=cid,
            audience=audience,
            timestamp=now,
            on_chain_anchor=on_chain_anchor,
        )

        action = AgentAction(
            agent_id=AGENT_ID,
            action="create_causal_event",
            rationale=(
                f"Created causal event '{event_type}' from agent "
                f"'{source_agent_id}', encrypted for audience '{audience}', "
                f"pinned as CID {cid}."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "event_id": event_id,
                "event_type": event_type,
                "cid": cid,
                "audience": audience,
                "on_chain_anchor": on_chain_anchor,
            },
        )

        logger.info(
            "Causal event created: id=%s type=%s cid=%s audience=%s anchor=%s",
            event_id,
            event_type,
            cid,
            audience,
            on_chain_anchor,
        )
        return record, action

    # ── Chain-Anchored Governance (Fix 4) ────────────────────────────────

    GOVERNANCE_PREFIXES = ("governance", "arbitration", "veto")

    @staticmethod
    def _is_governance_event(event_type: str) -> bool:
        """Return True if the event type requires on-chain anchoring."""
        return any(
            event_type.startswith(prefix)
            for prefix in CausalEvent.GOVERNANCE_PREFIXES
        )

    @staticmethod
    async def anchor_to_chain(cid: str) -> str:
        """Anchor a CID hash on-chain via the batch anchoring service.

        STUB: In production, this submits the CID to the AnchorBatcher which
        computes a Merkle root and writes a single transaction per batch window.
        Returns a deterministic pseudo-tx-hash for now.
        """
        # Import lazily to avoid circular dependency at module load time.
        from backend.mesh.anchor_batcher import AnchorBatcher

        batcher = AnchorBatcher.get_instance()
        batch_id = await batcher.submit(cid, source_node_did="local")

        # Generate a deterministic stub anchor hash from the CID.
        anchor = f"0x{hashlib.sha256(cid.encode()).hexdigest()}"
        logger.info("anchor_to_chain stub: cid=%s batch=%s anchor=%s", cid, batch_id, anchor)
        return anchor
