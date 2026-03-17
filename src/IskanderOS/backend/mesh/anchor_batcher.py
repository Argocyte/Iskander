"""
anchor_batcher.py — Merkle-Root-as-a-Service (Fix 4 Amendment).

Batches CID hashes from multiple nodes into a single on-chain Merkle root
transaction, reducing gas costs. Instead of N transactions (one per CID),
produces 1 transaction per batch window. Nodes split gas proportionally.
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)
AGENT_ID = "anchor-batcher-v1"


@dataclass
class BatchEntry:
    cid: str
    source_node_did: str
    submitted_at: float = field(default_factory=time.time)


class AnchorBatcher:
    """Collects CID hashes into batched Merkle roots for on-chain anchoring.

    Singleton: obtain via ``AnchorBatcher.get_instance()``.
    """

    _instance: AnchorBatcher | None = None

    def __init__(self, batch_window: int = 60) -> None:
        self._pending: list[BatchEntry] = []
        self._batch_window = batch_window
        self._batch_counter = 0
        self._last_flush: float = time.time()

    @classmethod
    def get_instance(cls) -> AnchorBatcher:
        if cls._instance is None:
            from backend.config import settings
            window = getattr(settings, 'mesh_anchor_batch_window_seconds', 60)
            cls._instance = cls(batch_window=window)
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    async def submit(self, cid: str, source_node_did: str) -> str:
        """Add CID to the current batch. Returns batch_id."""
        self._pending.append(BatchEntry(cid=cid, source_node_did=source_node_did))
        batch_id = f"batch-{self._batch_counter}"
        logger.info("CID %s added to %s (pending: %d)", cid, batch_id, len(self._pending))

        # Auto-flush if batch window exceeded
        if time.time() - self._last_flush >= self._batch_window:
            await self.flush()

        return batch_id

    async def flush(self) -> str | None:
        """Compute Merkle root and anchor to chain as single tx.

        Returns tx_hash or None if no pending entries.
        """
        if not self._pending:
            return None

        # Compute Merkle root
        leaves = [
            hashlib.sha256(entry.cid.encode()).hexdigest()
            for entry in self._pending
        ]
        root = self._compute_merkle_root(leaves)

        # STUB: anchor root to chain
        tx_hash = f"0x{hashlib.sha256(root.encode()).hexdigest()}"

        logger.info(
            "Batch %d flushed: %d CIDs, root=%s, tx=%s",
            self._batch_counter, len(self._pending), root[:16], tx_hash[:16],
        )

        self._pending.clear()
        self._batch_counter += 1
        self._last_flush = time.time()

        return tx_hash

    @staticmethod
    def _compute_merkle_root(leaves: list[str]) -> str:
        """Compute a simple binary Merkle root from leaf hashes."""
        if not leaves:
            return hashlib.sha256(b"empty").hexdigest()

        current = leaves[:]
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else left
                combined = hashlib.sha256((left + right).encode()).hexdigest()
                next_level.append(combined)
            current = next_level

        return current[0]

    def pending_count(self) -> int:
        return len(self._pending)
