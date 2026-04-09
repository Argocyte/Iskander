"""
delta_sync.py — Peer-to-peer CID synchronisation protocol (Phase 25).

``DeltaSyncProtocol`` pushes and receives content-addressed CIDs between
federated Iskander nodes.  Before accepting incoming CIDs, the protocol
checks access via the ``requires_access`` middleware.

STUB NOTICE:
  All sync operations are logged but do not transfer real data.
  In production: use libp2p / IPFS Cluster / custom pubsub to replicate
  pinned CIDs across peer nodes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── Result ───────────────────────────────────────────────────────────────────


@dataclass
class SyncResult:
    """Outcome of a delta-sync operation with a peer."""

    peer_did: str
    direction: str  # "push" or "pull"
    cids_synced: list[str] = field(default_factory=list)
    cids_denied: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Protocol ─────────────────────────────────────────────────────────────────


class DeltaSyncProtocol:
    """
    Permission-aware CID synchronisation between federated peers.

    Singleton: obtain via ``DeltaSyncProtocol.get_instance()``.
    """

    _instance: "DeltaSyncProtocol | None" = None

    def __init__(self) -> None:
        # STUB: track sync history in memory.
        self._history: list[SyncResult] = []

    @classmethod
    def get_instance(cls) -> "DeltaSyncProtocol":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Outbound ────────────────────────────────────────────────────────────────

    async def sync_to_peer(
        self,
        peer_did: str,
        cids: list[str],
    ) -> SyncResult:
        """Push CIDs to a remote peer.

        STUB: logs the attempt and returns success for all CIDs.
        In production: establish a libp2p stream to the peer, negotiate which
        CIDs they need, and transfer the encrypted blocks.
        """
        logger.info(
            "STUB sync_to_peer: pushing %d CIDs to peer %s",
            len(cids),
            peer_did,
        )

        result = SyncResult(
            peer_did=peer_did,
            direction="push",
            cids_synced=list(cids),
            cids_denied=[],
        )
        self._history.append(result)
        return result

    # ── Inbound ─────────────────────────────────────────────────────────────────

    async def receive_from_peer(
        self,
        peer_did: str,
        cids: list[str],
    ) -> SyncResult:
        """Accept CIDs offered by a remote peer.

        Permission-aware: each CID is checked before acceptance.  In this stub
        all CIDs are accepted; in production the access middleware would verify
        that the peer holds the required gSBT and the CIDs are audience-scoped
        to a group this node belongs to.

        STUB: logs the attempt and returns success for all CIDs.
        """
        # Fix 7: Route through Boundary Agent for trust-based filtering.
        from backend.boundary.boundary_agent import BoundaryAgent

        boundary = BoundaryAgent.get_instance()
        synced, denied, boundary_actions = boundary.ingest_sync(peer_did, cids)

        for ba in boundary_actions:
            logger.info(
                "boundary_agent_sync_action: %s — %s",
                ba.action,
                ba.rationale,
            )

        result = SyncResult(
            peer_did=peer_did,
            direction="pull",
            cids_synced=synced,
            cids_denied=denied,
        )
        self._history.append(result)
        logger.info(
            "receive_from_peer: peer=%s synced=%d denied=%d",
            peer_did,
            len(synced),
            len(denied),
        )
        return result

    # ── Chain-Anchored Sync Resolution (Fix 4) ──────────────────────────────

    GOVERNANCE_PREFIXES = ("governance", "arbitration", "veto")

    async def validate_chain_anchor(self, cid: str, expected_anchor: str | None) -> bool:
        """Validate that a governance CID has a valid on-chain anchor.

        Returns True if the anchor is valid or if the CID is non-governance.
        Returns False if the CID requires an anchor but doesn't have one.

        STUB: In production, this would verify the anchor hash exists in
        the on-chain anchor contract via web3.
        """
        if expected_anchor is None:
            logger.warning("Governance CID %s has no on-chain anchor — rejecting", cid)
            return False
        # STUB: verify anchor on-chain
        logger.info("Chain anchor validated for CID %s: %s", cid, expected_anchor)
        return True

    def _is_governance_event(self, event_type: str) -> bool:
        """Return True if the event type requires on-chain anchoring."""
        return any(event_type.startswith(prefix) for prefix in self.GOVERNANCE_PREFIXES)

    async def receive_from_peer_with_anchor(
        self,
        peer_did: str,
        cids_with_metadata: list[dict],
    ) -> SyncResult:
        """Accept CIDs from a peer, enforcing chain-anchor validation for governance CIDs.

        Each entry in *cids_with_metadata* must be a dict with keys:
            - ``cid``: the IPFS CID string
            - ``event_type``: causal event type string
            - ``on_chain_anchor``: anchor hash or None

        Governance CIDs without a valid anchor are denied.
        """
        synced: list[str] = []
        denied: list[str] = []

        for entry in cids_with_metadata:
            cid = entry["cid"]
            event_type = entry.get("event_type", "")
            anchor = entry.get("on_chain_anchor")

            if self._is_governance_event(event_type):
                valid = await self.validate_chain_anchor(cid, anchor)
                if not valid:
                    denied.append(cid)
                    continue

            synced.append(cid)

        result = SyncResult(
            peer_did=peer_did,
            direction="pull",
            cids_synced=synced,
            cids_denied=denied,
        )
        self._history.append(result)
        logger.info(
            "receive_from_peer_with_anchor: peer=%s synced=%d denied=%d",
            peer_did,
            len(synced),
            len(denied),
        )
        return result
