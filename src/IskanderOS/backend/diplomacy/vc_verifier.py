"""
vc_verifier.py — W3C Verifiable Credential Verifier (Credential Embassy).

Validates W3C VCs offline against the on-chain TrustRegistry. No live
connections to issuer servers are made during verification.

VERIFICATION FLOW:
    1. Parse the credential JSON and validate W3C VC structure.
    2. Extract the issuer DID and proof section.
    3. Compute the issuer's key fingerprint (keccak256 of the public key).
    4. Check the TrustRegistry: is this key trusted?
    5. Verify the cryptographic signature (Ed25519 or ES256).
    6. Check expiration (if ``expirationDate`` is present).
    7. Check revocation list (fetch once, cache locally).

OFFLINE-FIRST:
    The verifier NEVER pings the issuer's server for each verification.
    Issuer public keys are resolved from the TrustRegistry on-chain or
    from the local DID document cache. Revocation lists are fetched once
    and cached for ``vc_revocation_cache_ttl_seconds`` (default 24h).

PII SANITISATION:
    The ``sanitize_for_mesh()`` function strips all PII from a verified
    credential before it is stored in the Mesh Archive. Only the Verified
    Role, Verified Institution, and issuer DID are retained.

GLASS BOX:
    Every verification produces an AgentAction recording the outcome.

STUB NOTICE:
    Cryptographic signature verification is stubbed in development.
    In production, use ``cryptography`` library for Ed25519/ES256 verification.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "vc-verifier-v1"

# ── W3C VC Required Fields ───────────────────────────────────────────────────

REQUIRED_VC_FIELDS = {"@context", "type", "issuer", "credentialSubject"}
REQUIRED_PROOF_FIELDS = {"type", "verificationMethod"}
SUPPORTED_PROOF_TYPES = {"Ed25519Signature2020", "JsonWebSignature2020", "EcdsaSecp256k1Signature2019"}


# ── Verification Result ──────────────────────────────────────────────────────

@dataclass
class VCVerificationResult:
    """Outcome of a W3C VC verification attempt."""
    valid: bool
    issuer_did: str
    issuer_name: str = ""
    key_fingerprint: str = ""
    credential_type: str = ""
    subject_role: str = ""
    subject_institution: str = ""
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Trust Registry Client (Python-side) ──────────────────────────────────────

class TrustRegistryClient:
    """Python-side client for the on-chain TrustRegistry contract.

    STUB: In development, uses an in-memory registry. In production,
    reads from the TrustRegistry.sol contract via Web3.

    Obtain via ``TrustRegistryClient.get_instance()``.
    """

    _instance: TrustRegistryClient | None = None

    def __init__(self) -> None:
        # In-memory stub: fingerprint_hex → issuer record
        self._registry: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> TrustRegistryClient:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton."""
        cls._instance = None

    def register_issuer(
        self,
        key_fingerprint: str,
        issuer_did: str,
        issuer_name: str,
        key_type: str,
        public_key_bytes: bytes | None = None,
    ) -> AgentAction:
        """Register a trusted issuer key.

        Raises:
            ValueError: If already registered and active.
        """
        existing = self._registry.get(key_fingerprint)
        if existing and existing.get("active"):
            raise ValueError(f"Issuer already registered: {key_fingerprint}")

        self._registry[key_fingerprint] = {
            "issuer_did": issuer_did,
            "issuer_name": issuer_name,
            "key_type": key_type,
            "public_key_bytes": public_key_bytes,
            "registered_at": time.time(),
            "active": True,
        }

        return AgentAction(
            agent_id=AGENT_ID,
            action="register_trusted_issuer",
            rationale=(
                f"Registered trusted issuer '{issuer_name}' "
                f"(DID: {issuer_did}, key type: {key_type}, "
                f"fingerprint: {key_fingerprint[:16]}...)."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "key_fingerprint": key_fingerprint,
                "issuer_did": issuer_did,
                "issuer_name": issuer_name,
                "key_type": key_type,
            },
        )

    def revoke_issuer(self, key_fingerprint: str, rationale: str) -> AgentAction:
        """Revoke an issuer key. Emits action for tombstone propagation.

        Raises:
            KeyError: If not found.
            ValueError: If already revoked.
        """
        record = self._registry.get(key_fingerprint)
        if record is None:
            raise KeyError(f"Issuer not found: {key_fingerprint}")
        if not record["active"]:
            raise ValueError(f"Issuer already revoked: {key_fingerprint}")

        record["active"] = False
        record["revoked_at"] = time.time()

        return AgentAction(
            agent_id=AGENT_ID,
            action="revoke_trusted_issuer",
            rationale=(
                f"Revoked trusted issuer '{record['issuer_name']}' "
                f"(DID: {record['issuer_did']}). Reason: {rationale}. "
                f"All credentials derived from this key must be tombstoned."
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "key_fingerprint": key_fingerprint,
                "issuer_did": record["issuer_did"],
                "issuer_name": record["issuer_name"],
                "rationale": rationale,
            },
        )

    def is_trusted(self, key_fingerprint: str) -> bool:
        """Check if a key fingerprint is currently trusted."""
        record = self._registry.get(key_fingerprint)
        return record is not None and record.get("active", False)

    def get_issuer(self, key_fingerprint: str) -> dict[str, Any] | None:
        """Get issuer record by key fingerprint."""
        return self._registry.get(key_fingerprint)

    def get_revoked_fingerprints(self) -> list[str]:
        """Return all revoked key fingerprints (for tombstone processing)."""
        return [
            fp for fp, record in self._registry.items()
            if not record.get("active", False)
        ]


# ── Revocation List Cache ────────────────────────────────────────────────────

class RevocationCache:
    """In-memory cache for issuer revocation lists.

    Fetches the revocation list URL once and caches for the configured TTL.
    If the issuer did not provide a revocation URL, the credential is
    considered non-revoked.

    STUB: In development, always returns "not revoked". In production,
    fetches the revocation list via HTTP and parses it.
    """

    _instance: RevocationCache | None = None

    def __init__(self) -> None:
        # Cache: revocation_url → (credential_ids, fetch_timestamp)
        self._cache: dict[str, tuple[set[str], float]] = {}

    @classmethod
    def get_instance(cls) -> RevocationCache:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    def is_revoked(self, credential_id: str, revocation_url: str | None) -> bool:
        """Check if a credential has been revoked.

        Returns False if no revocation URL is provided (optimistic).
        """
        if not revocation_url:
            return False

        # Check cache freshness
        cached = self._cache.get(revocation_url)
        ttl = settings.vc_revocation_cache_ttl_seconds
        now = time.time()

        if cached is not None:
            revoked_ids, fetch_time = cached
            if now - fetch_time < ttl:
                return credential_id in revoked_ids

        # STUB: In production, fetch the revocation list
        # For now, always return False (not revoked)
        self._cache[revocation_url] = (set(), now)
        return False


# ── Core Verifier ─────────────────────────────────────────────────────────────

class VCVerifier:
    """W3C Verifiable Credential verifier.

    Obtain via ``VCVerifier.get_instance()``.
    """

    _instance: VCVerifier | None = None

    def __init__(self) -> None:
        self._trust_registry = TrustRegistryClient.get_instance()
        self._revocation_cache = RevocationCache.get_instance()

    @classmethod
    def get_instance(cls) -> VCVerifier:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    def verify_vc(
        self, credential_json: dict[str, Any],
    ) -> tuple[VCVerificationResult, AgentAction]:
        """Verify a W3C Verifiable Credential.

        Steps:
          1. Validate W3C VC structure.
          2. Extract issuer DID and proof.
          3. Compute key fingerprint from proof.verificationMethod.
          4. Check TrustRegistry for the key.
          5. Verify cryptographic signature (STUB).
          6. Check expiration.
          7. Check revocation list.

        Returns:
            (result, agent_action) — result.valid indicates success.
        """
        # ── Step 1: Validate W3C structure ────────────────────────────────────
        structure_error = self._validate_structure(credential_json)
        if structure_error:
            result = VCVerificationResult(
                valid=False,
                issuer_did="",
                error=structure_error,
            )
            return result, self._make_action(result, credential_json)

        # ── Step 2: Extract issuer ────────────────────────────────────────────
        issuer = credential_json.get("issuer", "")
        if isinstance(issuer, dict):
            issuer_did = issuer.get("id", "")
        else:
            issuer_did = str(issuer)

        # ── Step 3: Extract proof and compute fingerprint ─────────────────────
        proof = credential_json.get("proof", {})
        verification_method = proof.get("verificationMethod", "")

        # Compute key fingerprint from the verification method
        # In production: resolve DID document, extract public key, hash it
        # STUB: hash the verificationMethod string as a deterministic fingerprint
        key_fingerprint = "0x" + hashlib.sha256(
            verification_method.encode()
        ).hexdigest()

        # ── Step 4: Check TrustRegistry ───────────────────────────────────────
        if not self._trust_registry.is_trusted(key_fingerprint):
            result = VCVerificationResult(
                valid=False,
                issuer_did=issuer_did,
                key_fingerprint=key_fingerprint,
                error=(
                    f"Issuer key not found in TrustRegistry: "
                    f"{key_fingerprint[:16]}... "
                    f"(DID: {issuer_did}). Register the issuer's public key "
                    f"via the StewardshipCouncil before verifying credentials."
                ),
            )
            return result, self._make_action(result, credential_json)

        issuer_record = self._trust_registry.get_issuer(key_fingerprint) or {}
        issuer_name = issuer_record.get("issuer_name", "")

        # ── Step 5: Verify cryptographic signature ────────────────────────────
        # STUB: In production, verify Ed25519/ES256 signature using the
        # issuer's public key from the TrustRegistry.
        sig_valid = self._verify_signature_stub(credential_json, proof)
        if not sig_valid:
            result = VCVerificationResult(
                valid=False,
                issuer_did=issuer_did,
                issuer_name=issuer_name,
                key_fingerprint=key_fingerprint,
                error="Cryptographic signature verification failed.",
            )
            return result, self._make_action(result, credential_json)

        # ── Step 6: Check expiration ──────────────────────────────────────────
        expiration = credential_json.get("expirationDate")
        warnings: list[str] = []
        if expiration:
            try:
                exp_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                if exp_dt < datetime.now(timezone.utc):
                    result = VCVerificationResult(
                        valid=False,
                        issuer_did=issuer_did,
                        issuer_name=issuer_name,
                        key_fingerprint=key_fingerprint,
                        error=f"Credential expired at {expiration}.",
                    )
                    return result, self._make_action(result, credential_json)
            except (ValueError, TypeError):
                warnings.append(f"Could not parse expirationDate: {expiration}")

        # ── Step 7: Check revocation list ─────────────────────────────────────
        credential_id = credential_json.get("id", "")
        credential_status = credential_json.get("credentialStatus", {})
        revocation_url = credential_status.get("id") if isinstance(credential_status, dict) else None

        if self._revocation_cache.is_revoked(credential_id, revocation_url):
            result = VCVerificationResult(
                valid=False,
                issuer_did=issuer_did,
                issuer_name=issuer_name,
                key_fingerprint=key_fingerprint,
                error=f"Credential {credential_id} has been revoked by the issuer.",
            )
            return result, self._make_action(result, credential_json)

        # ── Extract subject fields ────────────────────────────────────────────
        subject = credential_json.get("credentialSubject", {})
        vc_types = credential_json.get("type", [])
        credential_type = next(
            (t for t in vc_types if t != "VerifiableCredential"), "Unknown"
        )

        result = VCVerificationResult(
            valid=True,
            issuer_did=issuer_did,
            issuer_name=issuer_name,
            key_fingerprint=key_fingerprint,
            credential_type=credential_type,
            subject_role=subject.get("role", subject.get("degree", "")),
            subject_institution=subject.get("institution", issuer_name),
            warnings=warnings,
        )
        return result, self._make_action(result, credential_json)

    def sanitize_for_mesh(
        self, credential_json: dict[str, Any], result: VCVerificationResult,
    ) -> dict[str, Any]:
        """Strip PII from a verified credential before Mesh Archive storage.

        Only retains:
          - Verified Role (e.g., "Researcher", "Professor")
          - Verified Institution (e.g., "University of Mondragon")
          - Issuer DID
          - Credential type
          - Issuance/expiration dates
          - Proof type (not the actual signature bytes)

        ALL personal identifiers are removed:
          - Name, email, date of birth, student ID, etc.
        """
        sanitized = {
            "verified_role": result.subject_role,
            "verified_institution": result.subject_institution,
            "issuer_did": result.issuer_did,
            "issuer_name": result.issuer_name,
            "credential_type": result.credential_type,
            "key_fingerprint": result.key_fingerprint,
            "issuance_date": credential_json.get("issuanceDate"),
            "expiration_date": credential_json.get("expirationDate"),
            "proof_type": credential_json.get("proof", {}).get("type"),
            "verified_at": result.verified_at.isoformat(),
            "pii_stripped": True,
        }
        return sanitized

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_structure(cred: dict[str, Any]) -> str | None:
        """Validate W3C VC structure. Returns error string or None."""
        missing = REQUIRED_VC_FIELDS - set(cred.keys())
        if missing:
            return f"Missing required W3C VC fields: {missing}"

        vc_types = cred.get("type", [])
        if not isinstance(vc_types, list) or "VerifiableCredential" not in vc_types:
            return "type must be a list containing 'VerifiableCredential'"

        contexts = cred.get("@context", [])
        if not isinstance(contexts, list) or "https://www.w3.org/2018/credentials/v1" not in contexts:
            return "@context must include 'https://www.w3.org/2018/credentials/v1'"

        proof = cred.get("proof")
        if not proof or not isinstance(proof, dict):
            return "Missing 'proof' section (required for signature verification)"

        proof_missing = REQUIRED_PROOF_FIELDS - set(proof.keys())
        if proof_missing:
            return f"Missing required proof fields: {proof_missing}"

        return None

    @staticmethod
    def _verify_signature_stub(
        credential: dict[str, Any], proof: dict[str, Any],
    ) -> bool:
        """STUB: Always returns True in development.

        In production, this would:
          1. Canonicalize the credential (JSON-LD canonicalization).
          2. Compute the hash of the canonical form.
          3. Verify the signature using the issuer's public key.
          4. Support Ed25519Signature2020, JsonWebSignature2020.
        """
        proof_type = proof.get("type", "")
        if proof_type in SUPPORTED_PROOF_TYPES or proof_type:
            return True
        return False

    @staticmethod
    def _make_action(
        result: VCVerificationResult, credential: dict[str, Any],
    ) -> AgentAction:
        """Create a Glass Box AgentAction for the verification outcome."""
        return AgentAction(
            agent_id=AGENT_ID,
            action="verify_credential" if result.valid else "reject_credential",
            rationale=(
                f"{'Verified' if result.valid else 'Rejected'} W3C VC from "
                f"issuer {result.issuer_did or 'unknown'}. "
                f"{'Type: ' + result.credential_type + '. ' if result.credential_type else ''}"
                f"{'Role: ' + result.subject_role + '. ' if result.subject_role else ''}"
                f"{'Error: ' + result.error if result.error else 'Signature valid.'}"
            ),
            ethical_impact=EthicalImpactLevel.HIGH,
            payload={
                "valid": result.valid,
                "issuer_did": result.issuer_did,
                "key_fingerprint": result.key_fingerprint,
                "credential_type": result.credential_type,
                "error": result.error,
                "pii_present": False,  # PII is never included in Glass Box
            },
        )
