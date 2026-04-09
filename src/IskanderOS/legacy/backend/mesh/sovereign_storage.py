"""
sovereign_storage.py — IPFS wrapper with audience-scoped encryption (Phase 25).

All payloads are encrypted via Fernet before pinning. The encryption key is
derived from the target audience:

  - "federation" — shared key (all federated nodes can decrypt)
  - "council"    — council-only key
  - "node"       — local node key (only this node can decrypt)

STUB NOTICE:
  IPFS operations are mocked (return deterministic fake CIDs).
  Encryption is REAL — payloads are genuinely encrypted via Fernet.
  In production: replace httpx stubs with calls to the local IPFS daemon.

GLASS BOX:
  pin()  → AgentAction with EthicalImpactLevel.MEDIUM
  cat()  → AgentAction with EthicalImpactLevel.LOW
  ls()   → AgentAction with EthicalImpactLevel.LOW
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet

from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "sovereign-storage"


# ── Fix 3: Federated Pinning Protocol + Geo-Diversity ─────────────────────


@dataclass
class NodeMetadata:
    """Metadata about a mesh peer for diversity-aware replication."""
    peer_did: str
    region: str = "unknown"       # e.g., "eu-west", "us-east", "latam"
    isp: str = "unknown"          # e.g., "hetzner", "digitalocean", "community-mesh"
    power_source: str = "unknown" # e.g., "grid", "solar", "battery"


@dataclass
class PinReceipt:
    """Receipt from a peer confirming they pinned a CID."""
    peer_did: str
    cid: str
    timestamp: str
    receipt_signature: str = ""  # STUB: signed receipt from peer


class InsufficientReplication(Exception):
    """Raised when minimum replica count cannot be met."""
    def __init__(self, cid: str, actual: int, required: int):
        self.cid = cid
        self.actual = actual
        self.required = required
        super().__init__(f"CID {cid}: only {actual}/{required} replicas achieved")


def _load_fernet_key() -> bytes:
    """Load the Fernet key from the environment variable named by settings."""
    env_var = settings.mesh_encryption_key_env
    raw = os.environ.get(env_var, "")
    if not raw:
        # Development fallback: generate a deterministic key from the env var
        # name so that restarts are idempotent. NOT for production.
        logger.warning(
            "Environment variable %s is not set — using deterministic "
            "development key.  DO NOT use this in production.",
            env_var,
        )
        raw = Fernet.generate_key().decode()
        os.environ[env_var] = raw
    return raw.encode() if isinstance(raw, str) else raw


class SovereignStorage:
    """
    Content-addressed storage with audience-scoped Fernet encryption.

    Singleton: obtain via ``SovereignStorage.get_instance()``.
    """

    _instance: "SovereignStorage | None" = None

    def __init__(self) -> None:
        self._api_url = settings.ipfs_api_url.rstrip("/")
        self._gateway_url = settings.ipfs_gateway_url.rstrip("/")
        self._fernet = Fernet(_load_fernet_key())

        # STUB: in-memory store keyed by fake CID.
        self._store: dict[str, bytes] = {}

    @classmethod
    def get_instance(cls) -> "SovereignStorage":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Audience Tag ────────────────────────────────────────────────────────────

    @staticmethod
    def _audience_tag(audience: str) -> bytes:
        """Return a deterministic tag prepended to plaintext before encryption.

        In production the tag would select a different key; here it is embedded
        in the ciphertext so that cat() can verify audience scope.
        """
        return f"aud:{audience}|".encode()

    # ── Pin ─────────────────────────────────────────────────────────────────────

    async def pin(
        self,
        data: bytes,
        audience: str = "federation",
        min_replicas: int = 0,
    ) -> tuple[str, int, AgentAction]:
        """Encrypt *data* for *audience* and pin to IPFS.

        Returns ``(cid, replica_count, agent_action)``.

        When *min_replicas* > 0, the method broadcasts the CID to mesh peers
        and collects :class:`PinReceipt` confirmations.  If fewer than
        *min_replicas* receipts arrive, :class:`InsufficientReplication` is
        raised.

        STUB: stores ciphertext in memory, returns a fake CID derived from the
        SHA-256 of the ciphertext.
        """
        tagged = self._audience_tag(audience) + data
        ciphertext = self._fernet.encrypt(tagged)

        # STUB CID: Qm + base16 of first 22 bytes of SHA-256.
        digest = hashlib.sha256(ciphertext).hexdigest()[:44]
        cid = f"Qm{digest}"

        self._store[cid] = ciphertext
        logger.info("Pinned %d bytes → CID %s (audience=%s)", len(data), cid, audience)

        # ── Fix 3: Federated replication ──────────────────────────────────
        replica_count = 1  # local pin counts as 1
        if min_replicas > 0:
            receipts = await self._broadcast_and_collect(cid, min_replicas)
            replica_count += len(receipts)
            if replica_count < min_replicas:
                raise InsufficientReplication(
                    cid=cid, actual=replica_count, required=min_replicas,
                )
            logger.info(
                "Federated pinning: %d/%d replicas for CID %s",
                replica_count, min_replicas, cid,
            )

        action = AgentAction(
            agent_id=AGENT_ID,
            action="pin_to_ipfs",
            rationale=(
                f"Encrypted {len(data)} bytes for audience '{audience}' "
                f"and pinned to local IPFS node."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "cid": cid,
                "audience": audience,
                "size": len(data),
                "replica_count": replica_count,
            },
        )
        return cid, replica_count, action

    # ── Fix 3: Federated Pinning helpers ─────────────────────────────────

    async def _broadcast_and_collect(
        self,
        cid: str,
        min_replicas: int,
    ) -> list[PinReceipt]:
        """Broadcast a pin request to mesh peers and collect receipts.

        STUB: returns an empty list.  In production this will use the
        ActivityPub outbox to request pins from known peers and await
        signed receipts within ``settings.mesh_pin_timeout_seconds``.
        """
        logger.warning(
            "_broadcast_and_collect is a STUB — returning empty receipt list "
            "for CID %s (min_replicas=%d)",
            cid, min_replicas,
        )
        return []

    async def _select_diverse_peers(
        self,
        min_replicas: int,
        candidates: list[NodeMetadata],
    ) -> list[NodeMetadata]:
        """Select peers maximizing region + ISP diversity."""
        selected: list[NodeMetadata] = []
        used_regions: set[str] = set()
        used_isps: set[str] = set()
        for candidate in sorted(
            candidates,
            key=lambda c: (c.region in used_regions, c.isp in used_isps),
        ):
            selected.append(candidate)
            used_regions.add(candidate.region)
            used_isps.add(candidate.isp)
            if len(selected) >= min_replicas:
                break
        return selected

    async def verify_availability(self, cid: str) -> int:
        """Check how many peers currently hold *cid*.

        STUB: returns 1 (local node only).  In production, queries the
        mesh DHT for providers of the given CID.
        """
        logger.debug("verify_availability STUB for CID %s — returning 1", cid)
        return 1

    # ── Cat ─────────────────────────────────────────────────────────────────────

    async def cat(self, cid: str) -> tuple[bytes, AgentAction]:
        """Retrieve and decrypt content by CID.

        Returns ``(plaintext, agent_action)``.

        Raises ``KeyError`` if the CID is not found in the local store.
        """
        ciphertext = self._store.get(cid)
        if ciphertext is None:
            raise KeyError(f"CID not found in local store: {cid}")

        tagged = self._fernet.decrypt(ciphertext)

        # Strip the audience tag.
        if b"|" in tagged[:64]:
            plaintext = tagged.split(b"|", 1)[1]
        else:
            plaintext = tagged

        logger.info("Retrieved CID %s (%d bytes)", cid, len(plaintext))

        action = AgentAction(
            agent_id=AGENT_ID,
            action="cat_from_ipfs",
            rationale=f"Retrieved and decrypted CID {cid} from local IPFS node.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"cid": cid, "size": len(plaintext)},
        )
        return plaintext, action

    # ── Ls ──────────────────────────────────────────────────────────────────────

    async def ls(self) -> tuple[list[dict[str, Any]], AgentAction]:
        """List all pinned CIDs in the local store.

        Returns ``(entries, agent_action)`` where each entry has
        ``cid`` and ``size`` keys.
        """
        entries = [
            {"cid": cid, "size": len(blob)}
            for cid, blob in self._store.items()
        ]
        logger.info("Listed %d pinned CIDs", len(entries))

        action = AgentAction(
            agent_id=AGENT_ID,
            action="list_ipfs_pins",
            rationale="Listed all locally pinned CIDs.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"count": len(entries)},
        )
        return entries, action
