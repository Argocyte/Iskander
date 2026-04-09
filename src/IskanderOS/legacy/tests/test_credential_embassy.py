"""
test_credential_embassy.py — Unit tests for the Credential Embassy feature.

Tests cover:
  - TrustRegistryClient: registration, revocation, lookup, duplicate handling
  - VCVerifier: W3C structure validation, trust check, PII sanitisation,
    expiration, revocation list
  - IdentityAttestationAgent: VC→attestation pipeline, ZK-attestation,
    tombstone propagation
  - IngestionEmbassy.ingest_credential(): full pipeline integration
  - Schema validation: request/response models
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import unittest
from datetime import datetime, timezone

import pytest


# ── Helper: run async coroutines in sync test methods ─────────────────────────

def run_async(coro):
    """Run an async coroutine in a new event loop (for sync test methods)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_singletons():
    """Reset all singletons before each test."""
    from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
    from backend.diplomacy.vc_verifier import (
        RevocationCache,
        TrustRegistryClient,
        VCVerifier,
    )
    from backend.finance.frs_client import FRSClient
    from backend.mesh.ingestion_embassy import IngestionEmbassy
    from backend.mesh.library_manager import LibraryManager
    from backend.mesh.sovereign_storage import SovereignStorage

    TrustRegistryClient._reset_instance()
    VCVerifier._reset_instance()
    RevocationCache._reset_instance()
    IdentityAttestationAgent._reset_instance()
    FRSClient._reset_instance()
    IngestionEmbassy._reset_instance()
    LibraryManager._reset_instance()
    SovereignStorage._instance = None

    yield

    TrustRegistryClient._reset_instance()
    VCVerifier._reset_instance()
    RevocationCache._reset_instance()
    IdentityAttestationAgent._reset_instance()
    FRSClient._reset_instance()
    IngestionEmbassy._reset_instance()
    LibraryManager._reset_instance()
    SovereignStorage._instance = None


# ── Test Data ─────────────────────────────────────────────────────────────────

def _make_valid_vc(
    issuer_did: str = "did:web:university.mondragon.edu",
    role: str = "Researcher",
    institution: str = "University of Mondragon",
    verification_method: str = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK#z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
) -> dict:
    """Create a valid W3C VC JSON for testing."""
    return {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://www.w3.org/2018/credentials/examples/v1",
        ],
        "id": "urn:uuid:test-credential-001",
        "type": ["VerifiableCredential", "UniversityDegreeCredential"],
        "issuer": issuer_did,
        "issuanceDate": "2024-01-15T00:00:00Z",
        "credentialSubject": {
            "id": "did:key:holder-001",
            "role": role,
            "institution": institution,
            "name": "Alice Smith",  # PII — should be stripped
            "studentId": "STU-12345",  # PII — should be stripped
        },
        "proof": {
            "type": "Ed25519Signature2020",
            "verificationMethod": verification_method,
            "proofPurpose": "assertionMethod",
            "created": "2024-01-15T00:00:00Z",
            "proofValue": "z58DAdFfa9SkqZMVPxAQp...stub",
        },
    }


def _key_fingerprint(verification_method: str) -> str:
    """Compute the key fingerprint the same way VCVerifier does."""
    return "0x" + hashlib.sha256(verification_method.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# TrustRegistryClient Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTrustRegistryClient:
    """Tests for the Python-side TrustRegistry client."""

    def test_register_issuer(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        action = client.register_issuer(
            "0xabc123", "did:web:uni.edu", "University", "Ed25519",
        )
        assert client.is_trusted("0xabc123")
        assert action.agent_id == "vc-verifier-v1"
        assert action.action == "register_trusted_issuer"

    def test_register_duplicate_raises(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        client.register_issuer("0xabc123", "did:web:uni.edu", "Uni", "Ed25519")
        with pytest.raises(ValueError, match="already registered"):
            client.register_issuer("0xabc123", "did:web:uni.edu", "Uni", "Ed25519")

    def test_revoke_issuer(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        client.register_issuer("0xabc123", "did:web:uni.edu", "Uni", "Ed25519")
        action = client.revoke_issuer("0xabc123", "Key compromised")
        assert not client.is_trusted("0xabc123")
        assert action.action == "revoke_trusted_issuer"

    def test_revoke_not_found_raises(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        with pytest.raises(KeyError, match="not found"):
            client.revoke_issuer("0xnonexistent", "test")

    def test_revoke_already_revoked_raises(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        client.register_issuer("0xabc123", "did:web:uni.edu", "Uni", "Ed25519")
        client.revoke_issuer("0xabc123", "test")
        with pytest.raises(ValueError, match="already revoked"):
            client.revoke_issuer("0xabc123", "test again")

    def test_get_revoked_fingerprints(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        client.register_issuer("0xaaa", "did:web:a.edu", "A", "Ed25519")
        client.register_issuer("0xbbb", "did:web:b.edu", "B", "Ed25519")
        client.revoke_issuer("0xaaa", "compromised")
        revoked = client.get_revoked_fingerprints()
        assert "0xaaa" in revoked
        assert "0xbbb" not in revoked

    def test_untrusted_key_returns_false(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        client = TrustRegistryClient.get_instance()
        assert not client.is_trusted("0xnonexistent")


# ══════════════════════════════════════════════════════════════════════════════
# VCVerifier Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestVCVerifier:
    """Tests for W3C VC verification."""

    def _register_test_issuer(self):
        """Register the test issuer so verification succeeds."""
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        vc = _make_valid_vc()
        vm = vc["proof"]["verificationMethod"]
        fp = _key_fingerprint(vm)
        client = TrustRegistryClient.get_instance()
        client.register_issuer(
            fp, "did:web:university.mondragon.edu",
            "University of Mondragon", "Ed25519",
        )
        return fp

    def test_verify_valid_vc(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        self._register_test_issuer()
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        result, action = verifier.verify_vc(vc)
        assert result.valid is True
        assert result.issuer_did == "did:web:university.mondragon.edu"
        assert result.subject_role == "Researcher"
        assert result.subject_institution == "University of Mondragon"
        assert action.action == "verify_credential"

    def test_verify_missing_context_fails(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        vc["@context"] = ["https://example.com"]
        result, _ = verifier.verify_vc(vc)
        assert result.valid is False
        assert "context" in result.error.lower()

    def test_verify_missing_type_fails(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        vc["type"] = ["CustomCredential"]  # missing VerifiableCredential
        result, _ = verifier.verify_vc(vc)
        assert result.valid is False

    def test_verify_missing_proof_fails(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        del vc["proof"]
        result, _ = verifier.verify_vc(vc)
        assert result.valid is False
        assert "proof" in result.error.lower()

    def test_verify_untrusted_issuer_fails(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        # Don't register the issuer
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        result, action = verifier.verify_vc(vc)
        assert result.valid is False
        assert "TrustRegistry" in result.error
        assert action.action == "reject_credential"

    def test_verify_expired_credential_fails(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        self._register_test_issuer()
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        vc["expirationDate"] = "2020-01-01T00:00:00Z"  # Already expired
        result, _ = verifier.verify_vc(vc)
        assert result.valid is False
        assert "expired" in result.error.lower()

    def test_sanitize_strips_pii(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        self._register_test_issuer()
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        result, _ = verifier.verify_vc(vc)
        sanitized = verifier.sanitize_for_mesh(vc, result)

        # Retained fields
        assert sanitized["verified_role"] == "Researcher"
        assert sanitized["verified_institution"] == "University of Mondragon"
        assert sanitized["issuer_did"] == "did:web:university.mondragon.edu"
        assert sanitized["pii_stripped"] is True

        # PII must NOT be present
        sanitized_str = str(sanitized)
        assert "Alice Smith" not in sanitized_str
        assert "STU-12345" not in sanitized_str

    def test_verify_missing_required_fields(self):
        from backend.diplomacy.vc_verifier import VCVerifier
        verifier = VCVerifier.get_instance()
        vc = {"type": ["VerifiableCredential"]}  # Missing most fields
        result, _ = verifier.verify_vc(vc)
        assert result.valid is False
        assert "Missing required" in result.error

    def test_verify_issuer_as_dict(self):
        """Test that issuer can be a dict with 'id' field (W3C spec)."""
        from backend.diplomacy.vc_verifier import VCVerifier
        self._register_test_issuer()
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        vc["issuer"] = {
            "id": "did:web:university.mondragon.edu",
            "name": "University of Mondragon",
        }
        result, _ = verifier.verify_vc(vc)
        assert result.valid is True
        assert result.issuer_did == "did:web:university.mondragon.edu"


# ══════════════════════════════════════════════════════════════════════════════
# IdentityAttestationAgent Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestIdentityAttestationAgent:
    """Tests for VC→attestation conversion and tombstone propagation."""

    def _setup_trusted_issuer(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        vc = _make_valid_vc()
        vm = vc["proof"]["verificationMethod"]
        fp = _key_fingerprint(vm)
        client = TrustRegistryClient.get_instance()
        client.register_issuer(
            fp, "did:web:university.mondragon.edu",
            "University of Mondragon", "Ed25519",
        )
        return fp

    def test_attest_from_vc_full_pipeline(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        self._setup_trusted_issuer()
        agent = IdentityAttestationAgent.get_instance()
        vc = _make_valid_vc()
        attestation, action = run_async(
            agent.attest_from_vc(vc, "did:key:holder-001")
        )

        assert attestation["status"] == "Active"
        assert attestation["holder_did"] == "did:key:holder-001"
        assert attestation["verified_role"] == "Researcher"
        assert attestation["verified_institution"] == "University of Mondragon"
        assert attestation["mesh_cid"] is not None
        assert attestation["causal_event_cid"] is not None
        assert attestation["zk_attestation"] is not None
        assert action.agent_id == "identity-attestation-v1"
        assert action.action == "mint_identity_attestation"

    def test_attest_untrusted_issuer_raises(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        # Don't register issuer
        agent = IdentityAttestationAgent.get_instance()
        vc = _make_valid_vc()
        with pytest.raises(ValueError, match="verification failed"):
            run_async(agent.attest_from_vc(vc, "did:key:holder-001"))

    def test_get_attestation(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        self._setup_trusted_issuer()
        agent = IdentityAttestationAgent.get_instance()
        vc = _make_valid_vc()
        attestation, _ = run_async(agent.attest_from_vc(vc, "did:key:holder-001"))

        retrieved = agent.get_attestation(attestation["attestation_id"])
        assert retrieved["attestation_id"] == attestation["attestation_id"]

    def test_get_attestation_not_found(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        agent = IdentityAttestationAgent.get_instance()
        with pytest.raises(KeyError, match="not found"):
            agent.get_attestation("nonexistent-id")

    def test_get_attestations_by_holder(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        self._setup_trusted_issuer()
        agent = IdentityAttestationAgent.get_instance()

        # Mint two attestations for the same holder
        vc1 = _make_valid_vc()
        vc2 = _make_valid_vc(role="Professor")
        run_async(agent.attest_from_vc(vc1, "did:key:holder-001"))
        run_async(agent.attest_from_vc(vc2, "did:key:holder-001"))

        attestations = agent.get_attestations_by_holder("did:key:holder-001")
        assert len(attestations) == 2

    def test_zk_attestation_structure(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        self._setup_trusted_issuer()
        agent = IdentityAttestationAgent.get_instance()
        vc = _make_valid_vc()
        attestation, _ = run_async(agent.attest_from_vc(vc, "did:key:holder-001"))

        zk = attestation["zk_attestation"]
        assert zk["proof_type"] == "zk-attestation-placeholder-v1"
        assert zk["proof_hash"].startswith("0x")
        assert zk["public_signals"]["has_valid_credential"] is True
        assert zk["public_signals"]["verified_role"] == "Researcher"
        assert zk["public_signals"]["issuer_trusted"] is True
        assert "private_inputs_hash" in zk

    def test_zk_attestation_deterministic(self):
        """Same inputs → same ZK proof hash."""
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        att = {
            "attestation_id": "test-id",
            "credential_type": "UniversityDegreeCredential",
            "verified_role": "Researcher",
            "issuer_did": "did:web:university.mondragon.edu",
            "holder_did": "did:key:holder-001",
        }
        zk1 = IdentityAttestationAgent._generate_zk_attestation(att)
        zk2 = IdentityAttestationAgent._generate_zk_attestation(att)
        assert zk1["proof_hash"] == zk2["proof_hash"]


# ══════════════════════════════════════════════════════════════════════════════
# Tombstone Propagation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTombstonePropagation:
    """Tests for tombstone propagation when issuer keys are revoked."""

    def _setup_and_mint(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        from backend.diplomacy.vc_verifier import TrustRegistryClient

        vc = _make_valid_vc()
        vm = vc["proof"]["verificationMethod"]
        fp = _key_fingerprint(vm)

        client = TrustRegistryClient.get_instance()
        client.register_issuer(
            fp, "did:web:university.mondragon.edu",
            "University of Mondragon", "Ed25519",
        )

        agent = IdentityAttestationAgent.get_instance()
        att1, _ = run_async(agent.attest_from_vc(vc, "did:key:holder-001"))
        att2, _ = run_async(agent.attest_from_vc(vc, "did:key:holder-002"))

        return fp, agent, client, att1, att2

    def test_tombstone_by_issuer_key(self):
        fp, agent, client, att1, att2 = self._setup_and_mint()

        tombstoned, action = agent.tombstone_by_issuer_key(fp, "Key compromised")

        assert len(tombstoned) == 2
        assert att1["attestation_id"] in tombstoned
        assert att2["attestation_id"] in tombstoned
        assert action.action == "tombstone_attestations_by_issuer"

        # Verify attestation records are updated
        assert agent.get_attestation(att1["attestation_id"])["status"] == "Tombstoned"
        assert agent.get_attestation(att2["attestation_id"])["status"] == "Tombstoned"

    def test_tombstone_idempotent(self):
        """Tombstoning the same key twice does not double-tombstone."""
        fp, agent, client, att1, att2 = self._setup_and_mint()

        tombstoned1, _ = agent.tombstone_by_issuer_key(fp, "First revocation")
        tombstoned2, _ = agent.tombstone_by_issuer_key(fp, "Second attempt")

        assert len(tombstoned1) == 2
        assert len(tombstoned2) == 0  # Already tombstoned

    def test_tombstone_unknown_key_returns_empty(self):
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        agent = IdentityAttestationAgent.get_instance()
        tombstoned, action = agent.tombstone_by_issuer_key("0xnonexistent", "test")
        assert len(tombstoned) == 0

    def test_full_revocation_flow(self):
        """End-to-end: register → mint → revoke → tombstone."""
        from backend.diplomacy.identity_attestation_agent import IdentityAttestationAgent
        from backend.diplomacy.vc_verifier import TrustRegistryClient

        fp, agent, client, att1, att2 = self._setup_and_mint()

        # Revoke the issuer
        client.revoke_issuer(fp, "Key compromised")
        assert not client.is_trusted(fp)

        # Tombstone all derived attestations
        tombstoned, _ = agent.tombstone_by_issuer_key(fp, "Key compromised")
        assert len(tombstoned) == 2

        # New VCs from this issuer should now fail verification
        from backend.diplomacy.vc_verifier import VCVerifier
        verifier = VCVerifier.get_instance()
        vc = _make_valid_vc()
        result, _ = verifier.verify_vc(vc)
        assert result.valid is False
        assert "TrustRegistry" in result.error


# ══════════════════════════════════════════════════════════════════════════════
# IngestionEmbassy.ingest_credential() Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestIngestionEmbassyCredential:
    """Tests for the credential ingestion pipeline via IngestionEmbassy."""

    def _setup_trusted_issuer(self):
        from backend.diplomacy.vc_verifier import TrustRegistryClient
        vc = _make_valid_vc()
        vm = vc["proof"]["verificationMethod"]
        fp = _key_fingerprint(vm)
        client = TrustRegistryClient.get_instance()
        client.register_issuer(
            fp, "did:web:university.mondragon.edu",
            "University of Mondragon", "Ed25519",
        )
        return fp

    def test_ingest_credential_full_pipeline(self):
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        self._setup_trusted_issuer()
        embassy = IngestionEmbassy.get_instance()
        vc = _make_valid_vc()

        attestation, action = run_async(
            embassy.ingest_credential(vc, "did:key:holder-001")
        )

        assert attestation["status"] == "Active"
        assert attestation["holder_did"] == "did:key:holder-001"
        assert attestation["verified_role"] == "Researcher"
        assert attestation["mesh_cid"] is not None
        assert action.agent_id == "ingestion-embassy-v1"
        assert action.action == "ingest_credential"

    def test_ingest_credential_untrusted_raises(self):
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        # Don't register the issuer
        embassy = IngestionEmbassy.get_instance()
        vc = _make_valid_vc()

        with pytest.raises(ValueError, match="verification failed"):
            run_async(embassy.ingest_credential(vc, "did:key:holder-001"))

    def test_ingest_credential_pii_not_in_mesh(self):
        """PII must not appear in the attestation record stored to Mesh."""
        from backend.mesh.ingestion_embassy import IngestionEmbassy
        self._setup_trusted_issuer()
        embassy = IngestionEmbassy.get_instance()
        vc = _make_valid_vc()

        attestation, _ = run_async(
            embassy.ingest_credential(vc, "did:key:holder-001")
        )

        # The attestation record should not contain PII
        att_str = str(attestation)
        assert "Alice Smith" not in att_str
        assert "STU-12345" not in att_str


# ══════════════════════════════════════════════════════════════════════════════
# Schema Validation Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCredentialSchemas:
    """Tests for Credential Embassy Pydantic schemas."""

    def test_verify_credential_request(self):
        from backend.schemas.diplomacy import VerifyCredentialRequest
        req = VerifyCredentialRequest(credential_json=_make_valid_vc())
        assert req.credential_json["type"][0] == "VerifiableCredential"

    def test_ingest_credential_request(self):
        from backend.schemas.diplomacy import IngestCredentialRequest
        req = IngestCredentialRequest(
            credential_json=_make_valid_vc(),
            holder_did="did:key:holder-001",
        )
        assert req.holder_did == "did:key:holder-001"

    def test_ingest_credential_request_empty_holder_fails(self):
        from backend.schemas.diplomacy import IngestCredentialRequest
        with pytest.raises(Exception):
            IngestCredentialRequest(
                credential_json=_make_valid_vc(),
                holder_did="",
            )

    def test_attestation_response(self):
        from backend.schemas.diplomacy import AttestationResponse
        resp = AttestationResponse(
            attestation_id="test-id",
            holder_did="did:key:holder-001",
            issuer_did="did:web:uni.edu",
            issuer_name="University",
            credential_type="UniversityDegreeCredential",
            verified_role="Researcher",
            verified_institution="University",
            status="Active",
            created_at="2024-01-15T00:00:00Z",
        )
        assert resp.status == "Active"
        assert resp.tombstoned_at is None

    def test_revoke_issuer_request(self):
        from backend.schemas.diplomacy import RevokeIssuerRequest
        req = RevokeIssuerRequest(
            key_fingerprint="0xabc123",
            rationale="Key compromised",
        )
        assert req.key_fingerprint == "0xabc123"

    def test_revoke_issuer_request_empty_rationale_fails(self):
        from backend.schemas.diplomacy import RevokeIssuerRequest
        with pytest.raises(Exception):
            RevokeIssuerRequest(
                key_fingerprint="0xabc123",
                rationale="",
            )

    def test_revoke_issuer_response(self):
        from backend.schemas.diplomacy import RevokeIssuerResponse
        resp = RevokeIssuerResponse(
            key_fingerprint="0xabc123",
            tombstoned_count=3,
            tombstoned_ids=["a", "b", "c"],
            rationale="Key compromised",
        )
        assert resp.tombstoned_count == 3


# ══════════════════════════════════════════════════════════════════════════════
# RevocationCache Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRevocationCache:
    """Tests for the offline revocation list cache."""

    def test_no_url_returns_not_revoked(self):
        from backend.diplomacy.vc_verifier import RevocationCache
        cache = RevocationCache.get_instance()
        assert cache.is_revoked("cred-001", None) is False

    def test_stub_returns_not_revoked(self):
        from backend.diplomacy.vc_verifier import RevocationCache
        cache = RevocationCache.get_instance()
        assert cache.is_revoked("cred-001", "https://example.com/revocations") is False

    def test_cache_respects_ttl(self):
        """Cache entries should be served within TTL."""
        from backend.diplomacy.vc_verifier import RevocationCache
        cache = RevocationCache.get_instance()
        # First call caches
        cache.is_revoked("cred-001", "https://example.com/revocations")
        # Second call should use cache
        assert cache.is_revoked("cred-001", "https://example.com/revocations") is False
