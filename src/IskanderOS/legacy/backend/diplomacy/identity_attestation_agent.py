"""
identity_attestation_agent.py — Converts verified external VCs to internal
SBT attestations and generates ZK-attestation placeholders.

FLOW:
    1. Receive a verified VCVerificationResult.
    2. Sanitise the credential (strip PII).
    3. Mint a local non-transferable attestation (internal SBT equivalent).
    4. Pin the attestation event to the Mesh Archive as a CausalEvent.
    5. Generate a ZK-Attestation placeholder (proving role without revealing
       identity details).

TOMBSTONE PROPAGATION:
    When a TrustRegistry issuer key is revoked, this agent scans all
    attestations derived from that key and flags them as Tombstoned.

GLASS BOX:
    Every attestation action produces an AgentAction.

STUB NOTICE:
    SBT minting is simulated in-memory. In production, this would call
    CoopIdentity.attest() via Web3. ZK proof generation is a placeholder
    returning a deterministic hash.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.diplomacy.vc_verifier import (
    TrustRegistryClient,
    VCVerificationResult,
    VCVerifier,
)
from backend.mesh.causal_event import CausalEvent
from backend.mesh.sovereign_storage import SovereignStorage
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "identity-attestation-v1"


class IdentityAttestationAgent:
    """Converts verified W3C VCs into internal Iskander attestations.

    Obtain via ``IdentityAttestationAgent.get_instance()``.

    TOMBSTONE-ONLY: Attestations are never deleted. Revoked attestations
    are flagged with status='Tombstoned' but remain in the registry.
    """

    _instance: IdentityAttestationAgent | None = None

    def __init__(self) -> None:
        self._verifier = VCVerifier.get_instance()
        self._trust_registry = TrustRegistryClient.get_instance()
        self._storage = SovereignStorage.get_instance()
        # In-memory attestation registry: attestation_id → record
        self._attestations: dict[str, dict[str, Any]] = {}
        # Index: key_fingerprint → list of attestation_ids (for tombstone propagation)
        self._by_issuer_key: dict[str, list[str]] = {}

    @classmethod
    def get_instance(cls) -> IdentityAttestationAgent:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    async def attest_from_vc(
        self,
        credential_json: dict[str, Any],
        holder_did: str,
    ) -> tuple[dict[str, Any], AgentAction]:
        """Full pipeline: verify VC → sanitise → mint attestation → pin to Mesh.

        Returns:
            (attestation_record, agent_action)

        Raises:
            ValueError: If VC verification fails.
        """
        # ── Step 1: Verify the credential ─────────────────────────────────────
        result, verify_action = self._verifier.verify_vc(credential_json)
        if not result.valid:
            raise ValueError(
                f"Credential verification failed: {result.error}"
            )

        # ── Step 2: Sanitise (strip PII) ──────────────────────────────────────
        sanitized = self._verifier.sanitize_for_mesh(credential_json, result)

        # ── Step 3: Mint internal attestation ─────────────────────────────────
        attestation_id = str(uuid4())
        now = datetime.now(timezone.utc)

        attestation = {
            "attestation_id": attestation_id,
            "holder_did": holder_did,
            "issuer_did": result.issuer_did,
            "issuer_name": result.issuer_name,
            "key_fingerprint": result.key_fingerprint,
            "credential_type": result.credential_type,
            "verified_role": result.subject_role,
            "verified_institution": result.subject_institution,
            "status": "Active",
            "created_at": now.isoformat(),
            "tombstoned_at": None,
        }

        # Store in registry
        self._attestations[attestation_id] = attestation

        # Index by issuer key (for tombstone propagation)
        if result.key_fingerprint not in self._by_issuer_key:
            self._by_issuer_key[result.key_fingerprint] = []
        self._by_issuer_key[result.key_fingerprint].append(attestation_id)

        # ── Step 4: Pin sanitised attestation to Mesh Archive ─────────────────
        attestation_blob = json.dumps({
            **sanitized,
            "attestation_id": attestation_id,
            "holder_did": holder_did,
        }).encode()

        cid, _replicas, _pin_action = await self._storage.pin(
            attestation_blob, audience="federation",
        )
        attestation["mesh_cid"] = cid

        # ── Step 5: Create CausalEvent for audit trail ────────────────────────
        event_record, _event_action = await CausalEvent.create(
            event_type="credential.attestation_minted",
            source_agent_id=AGENT_ID,
            payload={
                "attestation_id": attestation_id,
                "holder_did": holder_did,
                "issuer_did": result.issuer_did,
                "credential_type": result.credential_type,
                "verified_role": result.subject_role,
                "verified_institution": result.subject_institution,
                "mesh_cid": cid,
                # NO PII in the event payload
            },
            audience="federation",
        )
        attestation["causal_event_cid"] = event_record.ipfs_cid

        # ── Step 6: Generate ZK-Attestation placeholder ───────────────────────
        zk_attestation = self._generate_zk_attestation(attestation)
        attestation["zk_attestation"] = zk_attestation

        action = AgentAction(
            agent_id=AGENT_ID,
            action="mint_identity_attestation",
            rationale=(
                f"Minted internal attestation {attestation_id} for holder "
                f"'{holder_did}' from issuer '{result.issuer_name}' "
                f"(DID: {result.issuer_did}). Role: {result.subject_role}. "
                f"Institution: {result.subject_institution}. "
                f"PII stripped. Pinned to Mesh CID {cid}. "
                f"CausalEvent: {event_record.ipfs_cid}. "
                f"ZK-attestation generated."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "attestation_id": attestation_id,
                "holder_did": holder_did,
                "issuer_did": result.issuer_did,
                "credential_type": result.credential_type,
                "verified_role": result.subject_role,
                "mesh_cid": cid,
                "causal_event_cid": event_record.ipfs_cid,
                "zk_attestation_hash": zk_attestation["proof_hash"],
            },
        )

        logger.info(
            "Minted attestation: id=%s holder=%s role=%s institution=%s",
            attestation_id, holder_did, result.subject_role,
            result.subject_institution,
        )
        return attestation, action

    def get_attestation(self, attestation_id: str) -> dict[str, Any]:
        """Retrieve an attestation by ID.

        Raises:
            KeyError: If not found.
        """
        att = self._attestations.get(attestation_id)
        if att is None:
            raise KeyError(f"Attestation not found: {attestation_id}")
        return att

    def get_attestations_by_holder(self, holder_did: str) -> list[dict[str, Any]]:
        """Get all attestations for a given holder DID."""
        return [
            a for a in self._attestations.values()
            if a["holder_did"] == holder_did
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    # TOMBSTONE PROPAGATION
    # ═══════════════════════════════════════════════════════════════════════════

    def tombstone_by_issuer_key(
        self, key_fingerprint: str, rationale: str,
    ) -> tuple[list[str], AgentAction]:
        """Tombstone all attestations derived from a revoked issuer key.

        Called when an IssuerRevoked event is detected from the TrustRegistry.

        Returns:
            (list of tombstoned attestation_ids, agent_action)
        """
        attestation_ids = self._by_issuer_key.get(key_fingerprint, [])
        tombstoned: list[str] = []
        now = datetime.now(timezone.utc).isoformat()

        for att_id in attestation_ids:
            att = self._attestations.get(att_id)
            if att and att["status"] != "Tombstoned":
                att["status"] = "Tombstoned"
                att["tombstoned_at"] = now
                tombstoned.append(att_id)

        action = AgentAction(
            agent_id=AGENT_ID,
            action="tombstone_attestations_by_issuer",
            rationale=(
                f"Tombstoned {len(tombstoned)} attestation(s) derived from "
                f"revoked issuer key {key_fingerprint[:16]}... "
                f"Reason: {rationale}. "
                f"Attestation IDs: {tombstoned or 'none'}."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "key_fingerprint": key_fingerprint,
                "tombstoned_count": len(tombstoned),
                "tombstoned_ids": tombstoned,
                "rationale": rationale,
            },
        )

        if tombstoned:
            logger.warning(
                "Tombstoned %d attestations for revoked issuer key %s",
                len(tombstoned), key_fingerprint[:16],
            )
        return tombstoned, action

    # ═══════════════════════════════════════════════════════════════════════════
    # ZK-ATTESTATION PLACEHOLDER
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _generate_zk_attestation(attestation: dict[str, Any]) -> dict[str, Any]:
        """Generate a ZK-Attestation proving the holder has a verified role
        without revealing their name, ID, or other personal information.

        STUB: In production, this would use a ZK-SNARK circuit (e.g., Circom/
        SnarkJS) to generate a zero-knowledge proof. The proof attests:
          - "The holder has a valid credential of type X"
          - "The credential was issued by a trusted institution"
          - "The holder's role is Y"
        WITHOUT revealing:
          - The holder's name
          - The holder's student/employee ID
          - The specific institution (optionally — configurable)

        For now, returns a deterministic hash-based placeholder.
        """
        # Combine non-PII fields for the proof input
        proof_input = json.dumps({
            "credential_type": attestation.get("credential_type"),
            "verified_role": attestation.get("verified_role"),
            "issuer_did": attestation.get("issuer_did"),
            "attestation_id": attestation.get("attestation_id"),
        }, sort_keys=True).encode()

        proof_hash = hashlib.sha256(proof_input).hexdigest()

        return {
            "proof_hash": f"0x{proof_hash}",
            "proof_type": "zk-attestation-placeholder-v1",
            "public_signals": {
                "has_valid_credential": True,
                "credential_type": attestation.get("credential_type"),
                "verified_role": attestation.get("verified_role"),
                "issuer_trusted": True,
            },
            "private_inputs_hash": f"0x{hashlib.sha256(attestation.get('holder_did', '').encode()).hexdigest()[:32]}",
            "note": (
                "STUB: In production, this would be a real ZK-SNARK proof "
                "generated via Circom/SnarkJS. The public signals prove the "
                "holder's role without revealing their identity."
            ),
        }
