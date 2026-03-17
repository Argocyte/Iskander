"""
http_signatures.py — HTTP Signature signing and verification (Phase 14B).

Implements the draft-cavage-http-signatures scheme used by ActivityPub
implementations (Mastodon, Pleroma, Misskey, etc.) — not RFC 9421, which
is a newer standard not yet widely adopted by the Fediverse.

Reference: https://datatracker.ietf.org/doc/html/draft-cavage-http-signatures-12

SIGNING (outbound requests):
  - Compute a signature over: (request-target) host date digest
  - Sign with the node's RSA-SHA256 private key
  - Add Authorization: Signature keyId=...,headers=...,signature=... header

VERIFICATION (inbound requests):
  - Extract keyId from the Signature header
  - Fetch the sender's Actor object to retrieve their publicKeyPem
  - Verify the RSA-SHA256 signature over the reconstructed signing string

KEY MANAGEMENT:
  - The node's RSA keypair is generated on first boot and stored in Postgres
    (or in a local .pem file in development — see config.activitypub_key_path).
  - The public key is published in the Actor object at /federation/actors/{handle}.

STUB NOTICE:
  Key loading from Postgres / disk is stubbed. The verify() and sign() methods
  perform the cryptographic operations correctly if real keys are provided.
  Replace _load_private_key() and _fetch_remote_public_key() for production.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# ── cryptography library (already a FastAPI/httpx dependency) ─────────────────
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not available — HTTP Signatures in stub mode.")


class HTTPSignatureSigner:
    """
    Signs outbound HTTP requests with the node's RSA private key.

    Usage:
        signer = HTTPSignatureSigner(private_key_pem, key_id)
        headers = signer.sign(method="POST", url="https://...", body=b"...")
        # Add headers to the outbound httpx request.
    """

    def __init__(self, private_key_pem: str, key_id: str) -> None:
        """
        Args:
            private_key_pem: PEM-encoded RSA private key string.
            key_id:          Key ID URI — typically <actor_url>#main-key
        """
        self._key_id = key_id
        self._private_key = None

        if _CRYPTO_AVAILABLE and private_key_pem and "PRIVATE KEY" in private_key_pem:
            try:
                self._private_key = serialization.load_pem_private_key(
                    private_key_pem.encode(),
                    password=None,
                    backend=default_backend(),
                )
            except Exception as exc:
                logger.error("Failed to load private key: %s", exc)

    def sign(
        self,
        method: str,
        url: str,
        body: bytes = b"",
        date: str | None = None,
    ) -> dict[str, str]:
        """
        Produce HTTP headers for a signed request.

        Headers returned: Date, Digest, Signature.
        The caller merges these into the outbound request headers.

        Args:
            method: HTTP method (e.g. "POST").
            url:    Full URL of the target endpoint.
            body:   Request body bytes (used to compute the Digest header).
            date:   RFC 7231 date string (generated if not provided).

        Returns:
            Dict of header name → value to add to the request.
        """
        parsed = urlparse(url)
        host = parsed.netloc
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        date_str = date or datetime.now(timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

        # Digest header: SHA-256 of request body.
        digest = "SHA-256=" + base64.b64encode(
            hashlib.sha256(body).digest()
        ).decode()

        # Signing string: newline-separated header values.
        headers_to_sign = ["(request-target)", "host", "date", "digest"]
        signing_string = "\n".join([
            f"(request-target): {method.lower()} {path}",
            f"host: {host}",
            f"date: {date_str}",
            f"digest: {digest}",
        ])

        if self._private_key is None or not _CRYPTO_AVAILABLE:
            logger.warning("HTTPSignatureSigner: stub mode — unsigned request.")
            return {
                "Date": date_str,
                "Digest": digest,
                "Signature": (
                    f'keyId="{self._key_id}",headers="{" ".join(headers_to_sign)}",'
                    f'signature="STUB_UNSIGNED"'
                ),
            }

        raw_sig = self._private_key.sign(
            signing_string.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        sig_b64 = base64.b64encode(raw_sig).decode()

        signature_header = (
            f'keyId="{self._key_id}",'
            f'algorithm="rsa-sha256",'
            f'headers="{" ".join(headers_to_sign)}",'
            f'signature="{sig_b64}"'
        )

        return {
            "Date": date_str,
            "Digest": digest,
            "Signature": signature_header,
        }


class HTTPSignatureVerifier:
    """
    Verifies inbound HTTP Signatures against the sender's published public key.

    Usage:
        verifier = HTTPSignatureVerifier()
        valid = await verifier.verify(request_headers, method, path, body)
    """

    def __init__(self) -> None:
        self._key_cache: dict[str, Any] = {}  # key_id → public key object

    async def verify(
        self,
        headers: dict[str, str],
        method: str,
        path: str,
        body: bytes = b"",
    ) -> tuple[bool, str]:
        """
        Verify an HTTP Signature on an inbound request.

        Args:
            headers: Request headers (case-insensitive dict).
            method:  HTTP method.
            path:    Request path (with query string if present).
            body:    Request body bytes.

        Returns:
            (is_valid: bool, reason: str)
        """
        # Normalise header keys to lowercase.
        h = {k.lower(): v for k, v in headers.items()}

        sig_header = h.get("signature") or h.get("authorization", "").removeprefix("Signature ")
        if not sig_header:
            return False, "MISSING_SIGNATURE_HEADER"

        # Parse the Signature header into a dict.
        sig_params: dict[str, str] = {}
        for part in sig_header.split(","):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                sig_params[k.strip()] = v.strip('"')

        key_id = sig_params.get("keyId")
        headers_param = sig_params.get("headers", "date").split()
        sig_b64 = sig_params.get("signature")

        if not key_id or not sig_b64:
            return False, "MISSING_KEY_ID_OR_SIGNATURE"

        # Verify Digest header if present.
        digest_header = h.get("digest", "")
        if digest_header:
            expected_digest = "SHA-256=" + base64.b64encode(
                hashlib.sha256(body).digest()
            ).decode()
            if digest_header != expected_digest:
                return False, "DIGEST_MISMATCH"

        # Reconstruct the signing string.
        signing_parts: list[str] = []
        for header_name in headers_param:
            if header_name == "(request-target)":
                signing_parts.append(f"(request-target): {method.lower()} {path}")
            else:
                val = h.get(header_name, "")
                signing_parts.append(f"{header_name}: {val}")
        signing_string = "\n".join(signing_parts)

        # Fetch the sender's public key.
        public_key = await self._fetch_remote_public_key(key_id)
        if public_key is None:
            return False, f"CANNOT_FETCH_PUBLIC_KEY: {key_id}"

        if not _CRYPTO_AVAILABLE:
            logger.warning("HTTPSignatureVerifier: stub mode — skipping cryptographic check.")
            return True, "STUB_ACCEPTED"

        try:
            raw_sig = base64.b64decode(sig_b64)
            public_key.verify(
                raw_sig,
                signing_string.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True, "VALID"
        except Exception as exc:
            return False, f"INVALID_SIGNATURE: {exc}"

    async def _fetch_remote_public_key(self, key_id: str) -> Any:
        """
        Fetch and cache the RSA public key from a remote Actor's publicKeyPem.

        key_id is typically: https://example.coop/federation/actors/coop#main-key
        We fetch the Actor document at the URL prefix (before '#') and extract
        the publicKey.publicKeyPem field.
        """
        if key_id in self._key_cache:
            return self._key_cache[key_id]

        actor_url = key_id.split("#")[0]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    actor_url,
                    headers={"Accept": "application/activity+json"},
                )
                resp.raise_for_status()
                actor = resp.json()

            pem = actor.get("publicKey", {}).get("publicKeyPem", "")
            if not pem or not _CRYPTO_AVAILABLE:
                return None

            pub_key = serialization.load_pem_public_key(
                pem.encode(), backend=default_backend()
            )
            self._key_cache[key_id] = pub_key
            return pub_key

        except Exception as exc:
            logger.warning("Failed to fetch public key for %s: %s", key_id, exc)
            return None
