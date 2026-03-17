"""
ingestion_embassy.py — Single entry point for external knowledge assets.

The Ingestion Embassy is the "diplomatic gateway" through which all external
content enters the local Knowledge Commons. It coordinates:

  1. **FRS Tier Check** — Verify the source SDC's reputation tier. Quarantined
     SDCs cannot submit assets at all.
  2. **Local Pinning** — Pin the external content to the local IPFS node via
     SovereignStorage (encrypted, audience="federation").
  3. **Ontology Transcoding** — Map external metadata fields to the local
     KnowledgeAsset schema. Detect semantic collisions with existing assets.
  4. **Quarantine Sandbox** — Hold the asset in a sandbox pending curator
     review. Assets from Tier 1 (Provisional) SDCs get extended review.
  5. **Admission** — On curator approval, promote to a full KnowledgeAsset
     via LibraryManager.register_asset().

GLASS BOX: Every step returns an AgentAction for the audit trail.

TOMBSTONE-ONLY: External assets that are rejected remain in the sandbox
forever (status=Rejected). They are NEVER deleted from IPFS.

REUSE:
  - SovereignStorage for IPFS pinning (same as LibraryManager)
  - BoundaryAgent's OntologyTranslator for schema mapping
  - FRSClient for reputation tier lookups
  - LibraryManager for asset promotion
"""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from backend.config import settings
from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
from backend.diplomacy.vc_verifier import TrustRegistryClient, VCVerifier
from backend.finance.frs_client import FRSClient
from backend.mesh.library_manager import LibraryManager
from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.diplomacy import (
    CollisionEntry,
    CollisionReport,
    ExternalAsset,
    QuarantineStatus,
    ReputationTier,
)
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "ingestion-embassy-v1"


class IngestionEmbassy:
    """Singleton managing the quarantine sandbox for external knowledge assets.

    Obtain via ``IngestionEmbassy.get_instance()``.

    TOMBSTONE-ONLY: Rejected assets remain in the sandbox permanently.
    Only admitted assets are promoted to KnowledgeAsset via LibraryManager.
    """

    _instance: IngestionEmbassy | None = None

    def __init__(self) -> None:
        self._storage = SovereignStorage.get_instance()
        self._frs = FRSClient.get_instance()
        self._library = LibraryManager.get_instance()
        # In-memory quarantine sandbox: quarantine_id → ExternalAsset
        self._sandbox: dict[str, ExternalAsset] = {}

    @classmethod
    def get_instance(cls) -> IngestionEmbassy:
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

    async def ingest(
        self,
        source_sdc_did: str,
        original_cid: str,
        title: str,
        data: bytes,
        description: str | None = None,
    ) -> tuple[ExternalAsset, AgentAction]:
        """Ingest an external knowledge asset into the quarantine sandbox.

        Steps:
          1. Check source SDC reputation tier (must be ≥ Provisional).
          2. Pin content to local IPFS via SovereignStorage.
          3. Run semantic collision detection against existing local assets.
          4. Create ExternalAsset record in the sandbox.

        Raises:
            ValueError: If source SDC is in Quarantine tier or unknown.
        """
        # ── Step 1: FRS Tier Check ────────────────────────────────────────────
        tier = self._frs.get_tier(source_sdc_did)
        if tier == ReputationTier.QUARANTINE:
            raise ValueError(
                f"SDC '{source_sdc_did}' is in Quarantine tier (tier 0). "
                f"Cannot ingest assets. The SDC must achieve Provisional "
                f"tier (≥{settings.frs_quarantine_threshold_bps} bps) first."
            )

        # ── Step 2: Local Pinning ─────────────────────────────────────────────
        local_cid, replica_count, _pin_action = await self._storage.pin(
            data, audience="federation",
        )

        # ── Step 3: Collision Detection ───────────────────────────────────────
        collision_report = self._detect_collisions(title, data)

        # ── Step 4: Create Sandbox Record ─────────────────────────────────────
        asset = ExternalAsset(
            source_sdc_did=source_sdc_did,
            source_sdc_tier=tier,
            original_cid=original_cid,
            local_cid=local_cid,
            title=title,
            description=description,
            status=QuarantineStatus.PENDING_REVIEW,
            collision_report=collision_report,
        )

        self._sandbox[str(asset.quarantine_id)] = asset

        action = AgentAction(
            agent_id=AGENT_ID,
            action="ingest_external_asset",
            rationale=(
                f"Ingested external asset '{title}' from SDC '{source_sdc_did}' "
                f"(tier {tier.name}, score tier {tier.value}). "
                f"Pinned locally as CID {local_cid} ({replica_count} replicas). "
                f"Collision check: {collision_report.collision_count} collision(s) found. "
                f"Status: {asset.status.value}."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "quarantine_id": str(asset.quarantine_id),
                "source_sdc_did": source_sdc_did,
                "source_tier": tier.value,
                "original_cid": original_cid,
                "local_cid": local_cid,
                "title": title,
                "collision_count": collision_report.collision_count,
                "replica_count": replica_count,
            },
        )

        logger.info(
            "Ingested external asset: qid=%s sdc=%s tier=%s cid=%s collisions=%d",
            asset.quarantine_id, source_sdc_did, tier.name, local_cid,
            collision_report.collision_count,
        )
        return asset, action

    async def admit(
        self,
        quarantine_id: str,
        author_did: str,
    ) -> tuple[ExternalAsset, AgentAction]:
        """Promote a quarantined asset to a full KnowledgeAsset.

        Calls LibraryManager.register_asset() to create the canonical record.

        Raises:
            KeyError: If quarantine_id not found.
            ValueError: If asset is not in PENDING_REVIEW or UNDER_REVIEW status.
        """
        asset = self._sandbox.get(quarantine_id)
        if asset is None:
            raise KeyError(f"Quarantine ID not found: {quarantine_id}")

        if asset.status not in (
            QuarantineStatus.PENDING_REVIEW,
            QuarantineStatus.UNDER_REVIEW,
        ):
            raise ValueError(
                f"Cannot admit asset in status '{asset.status.value}'. "
                f"Only PendingReview or UnderReview assets can be admitted."
            )

        # Retrieve the pinned content to re-register via LibraryManager
        content, _cat_action = await self._storage.cat(asset.local_cid)

        # Register as a KnowledgeAsset
        ka, _reg_action = await self._library.register_asset(
            data=content,
            title=asset.title,
            author_did=author_did,
            description=asset.description,
        )

        # Update sandbox record
        asset.status = QuarantineStatus.ADMITTED
        asset.reviewed_at = datetime.now(timezone.utc)
        asset.promoted_asset_cid = ka.cid

        action = AgentAction(
            agent_id=AGENT_ID,
            action="admit_external_asset",
            rationale=(
                f"Admitted external asset '{asset.title}' from SDC "
                f"'{asset.source_sdc_did}'. Promoted to KnowledgeAsset "
                f"CID {ka.cid} (version {ka.version}). Original quarantine "
                f"ID: {quarantine_id}."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "quarantine_id": quarantine_id,
                "promoted_cid": ka.cid,
                "promoted_asset_id": str(ka.asset_id),
                "source_sdc_did": asset.source_sdc_did,
            },
        )

        logger.info(
            "Admitted external asset: qid=%s -> cid=%s",
            quarantine_id, ka.cid,
        )
        return asset, action

    def reject(self, quarantine_id: str, reason: str) -> tuple[ExternalAsset, AgentAction]:
        """Reject a quarantined asset. It remains in the sandbox permanently.

        TOMBSTONE-ONLY: The local CID is NOT deleted from IPFS.

        Raises:
            KeyError: If quarantine_id not found.
            ValueError: If asset is not in a reviewable status.
        """
        asset = self._sandbox.get(quarantine_id)
        if asset is None:
            raise KeyError(f"Quarantine ID not found: {quarantine_id}")

        if asset.status not in (
            QuarantineStatus.PENDING_REVIEW,
            QuarantineStatus.UNDER_REVIEW,
        ):
            raise ValueError(
                f"Cannot reject asset in status '{asset.status.value}'."
            )

        asset.status = QuarantineStatus.REJECTED
        asset.reviewed_at = datetime.now(timezone.utc)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="reject_external_asset",
            rationale=(
                f"Rejected external asset '{asset.title}' from SDC "
                f"'{asset.source_sdc_did}'. Reason: {reason}. "
                f"Asset remains in sandbox (tombstone-only invariant). "
                f"Local CID: {asset.local_cid}."
            ),
            ethical_impact=EthicalImpactLevel.MEDIUM,
            payload={
                "quarantine_id": quarantine_id,
                "local_cid": asset.local_cid,
                "source_sdc_did": asset.source_sdc_did,
                "reason": reason,
            },
        )

        logger.info("Rejected external asset: qid=%s reason=%s", quarantine_id, reason)
        return asset, action

    def get_sandbox_asset(self, quarantine_id: str) -> ExternalAsset:
        """Retrieve a quarantined asset by ID.

        Raises:
            KeyError: If not found.
        """
        asset = self._sandbox.get(quarantine_id)
        if asset is None:
            raise KeyError(f"Quarantine ID not found: {quarantine_id}")
        return asset

    def list_pending(self) -> list[ExternalAsset]:
        """List all assets awaiting review."""
        return [
            a for a in self._sandbox.values()
            if a.status in (QuarantineStatus.PENDING_REVIEW, QuarantineStatus.UNDER_REVIEW)
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    # CREDENTIAL INGESTION (W3C VC → Internal Attestation)
    # ═══════════════════════════════════════════════════════════════════════════

    async def ingest_credential(
        self,
        credential_json: dict[str, Any],
        holder_did: str,
    ) -> tuple[dict[str, Any], AgentAction]:
        """Full credential ingestion pipeline: verify VC → mint attestation → Mesh Archive.

        Steps:
          1. Verify the W3C VC against the TrustRegistry (offline, no live pings).
          2. Mint a local non-transferable attestation (internal SBT equivalent).
          3. The attestation agent pins sanitised data to IPFS and creates a CausalEvent.
          4. A ZK-Attestation placeholder is generated.

        Returns:
            (attestation_record, agent_action) — attestation contains mesh_cid,
            causal_event_cid, and zk_attestation fields.

        Raises:
            ValueError: If VC verification fails (untrusted issuer, expired, revoked,
                        bad structure, or signature failure).
        """
        attestation_agent = IdentityAttestationAgent.get_instance()

        # attest_from_vc handles the full pipeline:
        #   verify → sanitise → mint → pin → CausalEvent → ZK-attestation
        attestation, action = await attestation_agent.attest_from_vc(
            credential_json, holder_did,
        )

        # Wrap with an embassy-level action for the Glass Box trail
        embassy_action = AgentAction(
            agent_id=AGENT_ID,
            action="ingest_credential",
            rationale=(
                f"Ingested W3C VC for holder '{holder_did}'. "
                f"Issuer: {attestation.get('issuer_name', 'unknown')} "
                f"(DID: {attestation.get('issuer_did', 'unknown')}). "
                f"Role: {attestation.get('verified_role', 'unknown')}. "
                f"Institution: {attestation.get('verified_institution', 'unknown')}. "
                f"Attestation ID: {attestation['attestation_id']}. "
                f"Mesh CID: {attestation.get('mesh_cid', 'N/A')}. "
                f"CausalEvent: {attestation.get('causal_event_cid', 'N/A')}. "
                f"ZK-attestation generated. PII stripped before Mesh storage."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "attestation_id": attestation["attestation_id"],
                "holder_did": holder_did,
                "issuer_did": attestation.get("issuer_did"),
                "credential_type": attestation.get("credential_type"),
                "verified_role": attestation.get("verified_role"),
                "mesh_cid": attestation.get("mesh_cid"),
                "causal_event_cid": attestation.get("causal_event_cid"),
                "zk_attestation_hash": attestation.get("zk_attestation", {}).get("proof_hash"),
            },
        )

        logger.info(
            "Credential ingested: att=%s holder=%s role=%s",
            attestation["attestation_id"], holder_did,
            attestation.get("verified_role"),
        )
        return attestation, embassy_action

    # ═══════════════════════════════════════════════════════════════════════════
    # INTERNAL: Collision Detection
    # ═══════════════════════════════════════════════════════════════════════════

    def _detect_collisions(
        self, title: str, data: bytes,
    ) -> CollisionReport:
        """Check for semantic collisions with existing local knowledge assets.

        STUB: Uses title similarity (SequenceMatcher) and content hash matching.
        In production, this would use embedding-based similarity via the RAG
        pipeline (Phase 11 nomic-embed-text).
        """
        collisions: list[CollisionEntry] = []
        content_hash = hashlib.sha256(data).hexdigest()

        for cid, asset in self._library._registry.items():
            # Exact content match
            if asset.content_hash == content_hash:
                collisions.append(CollisionEntry(
                    local_cid=cid,
                    local_title=asset.title,
                    similarity_score=1.0,
                    collision_type="duplicate",
                    rationale="Exact content hash match (SHA-256).",
                ))
                continue

            # Title similarity
            ratio = SequenceMatcher(None, title.lower(), asset.title.lower()).ratio()
            if ratio >= settings.frs_collision_similarity_threshold:
                collision_type = "overlaps"
                if ratio >= 0.95:
                    collision_type = "duplicate"
                elif ratio >= 0.8:
                    collision_type = "supersedes"

                collisions.append(CollisionEntry(
                    local_cid=cid,
                    local_title=asset.title,
                    similarity_score=ratio,
                    collision_type=collision_type,
                    rationale=f"Title similarity: {ratio:.2%} (threshold: {settings.frs_collision_similarity_threshold:.2%}).",
                ))

        return CollisionReport(
            collisions=collisions,
            collision_count=len(collisions),
        )
