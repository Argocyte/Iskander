"""
did_resolver.py — Decentralized Identifier (DID) resolution for sovereign routing (Phase 20).

Resolves member DIDs to determine their preferred communication endpoint.
If a member's DID document declares an ActivityPub inbox service, the
HITL routing manager pushes proposals there instead of the coop's local UI.

RESOLUTION STRATEGY:
  1. Check in-memory TTL cache (avoids repeat HTTP lookups).
  2. Check local registry (stub for known members during dev/testing).
  3. For did:web — HTTP GET https://<domain>/<path>/did.json
  4. Cache the result (even None, to avoid thundering herd on unknown DIDs).

DID METHODS SUPPORTED:
  - did:web  — HTTP resolution per W3C DID Web method spec.
  - Others   — Stub: returns None. Extend for did:ethr, did:pkh, etc.

STUB NOTICE:
  Production should use asyncpg for the did_document_cache table instead
  of the in-memory dict. The local registry is intentionally ephemeral —
  it is a convenience for tests and first-boot, not a persistent store.

GLASS BOX:
  Every resolve_did() call returns an AgentAction with LOW ethical impact.
  DID resolution is a read-only, non-coercive operation — the cooperative
  is looking up where a member *wants* to be contacted. It asserts no
  authority over the member's identity.

SOVEREIGNTY NOTE:
  The member publishes their DID document on infrastructure they control.
  The cooperative merely reads it. If the member updates their DID document
  to remove the ActivityPub inbox, the next resolution (after cache TTL)
  will fall back to local DB routing. The member's preference is always
  respected — the cooperative does not override, cache indefinitely, or
  assume consent.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel
from backend.schemas.hitl import DIDDocument, DIDServiceEndpoint

logger = logging.getLogger(__name__)

AGENT_ID = "did-resolver"

# ActivityPub inbox service type — members declare this in their DID document
# to signal "I run my own Iskander node; send proposals here."
AP_INBOX_SERVICE_TYPE = "ActivityPubInbox"


class DIDResolver:
    """
    Resolves Decentralized Identifiers to DID Documents for service discovery.

    Singleton: obtain via DIDResolver.get_instance().

    The resolver does NOT verify DID document signatures in Phase 20.
    Cryptographic authenticity is delegated to the ActivityPub HTTP Signature
    layer during actual message delivery. This resolver's job is service
    endpoint discovery only.
    """

    _instance: "DIDResolver | None" = None

    def __init__(self) -> None:
        # TTL cache: did -> (document | None, timestamp)
        self._cache: dict[str, tuple[DIDDocument | None, float]] = {}
        self._cache_ttl: int = settings.did_resolver_cache_ttl

        # Local registry: stub for dev/testing. Register known member DIDs
        # here during first-boot or test setup. NOT a production store.
        self._local_registry: dict[str, DIDDocument] = {}

    @classmethod
    def get_instance(cls) -> "DIDResolver":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ─────────────────────────────────────────────────────────────

    async def resolve_did(self, did: str) -> tuple[DIDDocument | None, AgentAction]:
        """
        Resolve a DID to its DID Document.

        Resolution order: cache → local registry → HTTP (did:web).
        Results are cached (including None) for cache_ttl seconds.

        Args:
            did: The Decentralized Identifier to resolve (e.g. "did:web:alice.example").

        Returns:
            (DIDDocument | None, AgentAction) — the resolved document and a
            Glass Box audit record. None means "no resolvable document found."
        """
        # 1. Check cache.
        cached = self._cache_lookup(did)
        if cached is not None:
            doc = cached
            source = "cache"
        else:
            # 2. Check local registry.
            if did in self._local_registry:
                doc = self._local_registry[did]
                source = "local_registry"
            # 3. HTTP resolution for did:web.
            elif did.startswith("did:web:"):
                doc = await self._resolve_did_web(did)
                source = "did:web_http"
            else:
                doc = None
                source = "unsupported_method"

            # Cache result (even None).
            self._cache[did] = (doc, time.monotonic())

        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"resolve_did({did[:40]})",
            rationale=(
                f"Resolved member DID via {source} to determine sovereign notification "
                f"preference. The member publishes their DID document on infrastructure "
                f"they control — the cooperative merely reads it. "
                f"{'Document found with ' + str(len(doc.service)) + ' service(s).' if doc else 'No document found — fallback to local routing.'}"
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={
                "did": did,
                "resolved": doc is not None,
                "source": source,
                "service_count": len(doc.service) if doc else 0,
            },
        )

        logger.info(
            "DID resolution: %s → %s (source: %s, services: %d)",
            did[:40],
            "found" if doc else "not_found",
            source,
            len(doc.service) if doc else 0,
        )

        return doc, action

    @staticmethod
    def get_activitypub_inbox(doc: DIDDocument) -> str | None:
        """
        Extract the ActivityPub inbox URL from a DID Document.

        Scans the document's service entries for one with
        type == "ActivityPubInbox". Returns the service_endpoint URL
        or None if no such service is declared.

        A member who does NOT want sovereign routing simply omits this
        service entry from their DID document. No inbox → local fallback.
        """
        for svc in doc.service:
            if svc.type == AP_INBOX_SERVICE_TYPE:
                return svc.service_endpoint
        return None

    def register_local(self, did: str, doc: DIDDocument) -> None:
        """
        Register a DID Document in the local stub registry.

        Used by tests and during first-boot when the cooperative knows
        its own members' DIDs. This is NOT a production persistence layer —
        production reads from the did_document_cache Postgres table.

        Args:
            did: The DID to register.
            doc: The DID Document to associate with it.
        """
        self._local_registry[did] = doc
        # Invalidate cache so next resolve picks up the registry entry.
        self._cache.pop(did, None)
        logger.info("DID registered locally: %s", did[:40])

    def clear_cache(self) -> None:
        """Flush the entire resolution cache. Used in tests."""
        self._cache.clear()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _cache_lookup(self, did: str) -> DIDDocument | None | type[None]:
        """
        Check the TTL cache for a previously resolved DID.

        Returns:
            DIDDocument — if cached and within TTL.
            None        — if cached as "not found" and within TTL.
            type[None]  — sentinel (returns the *class* None, not the value)
                          if the cache has no entry or the entry expired.
                          Callers check `if cached is not None` to distinguish.

        Implementation note: We use the class `type[None]` as a sentinel
        distinct from the value `None` (which means "DID resolved but no
        document found"). This avoids a separate "cache miss" exception.
        """
        entry = self._cache.get(did)
        if entry is None:
            return type(None)  # Cache miss sentinel.
        doc, ts = entry
        if (time.monotonic() - ts) > self._cache_ttl:
            del self._cache[did]
            return type(None)  # Expired.
        return doc  # Hit (may be None = "DID not found, cached negative").

    async def _resolve_did_web(self, did: str) -> DIDDocument | None:
        """
        Resolve a did:web identifier via HTTPS.

        did:web:example.com        → GET https://example.com/.well-known/did.json
        did:web:example.com:path   → GET https://example.com/path/did.json

        Colons in the method-specific-id are path separators.
        Percent-encoded characters are decoded per the did:web spec.

        Returns DIDDocument on success, None on any error.
        """
        try:
            # Strip "did:web:" prefix.
            method_specific_id = did[len("did:web:"):]
            # Split on colons → URL path segments.
            parts = method_specific_id.split(":")
            domain = parts[0]
            path_segments = parts[1:] if len(parts) > 1 else []

            if path_segments:
                url = f"https://{domain}/{'/'.join(path_segments)}/did.json"
            else:
                url = f"https://{domain}/.well-known/did.json"

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers={"Accept": "application/did+json"})

            if resp.status_code != 200:
                logger.warning("did:web resolution failed for %s: HTTP %d", did, resp.status_code)
                return None

            raw: dict[str, Any] = resp.json()
            return self._parse_did_document(raw)

        except Exception as exc:
            logger.error("did:web resolution error for %s: %s", did, exc)
            return None

    @staticmethod
    def _parse_did_document(raw: dict[str, Any]) -> DIDDocument | None:
        """Parse a raw JSON DID Document into the Pydantic model."""
        try:
            services = []
            for svc in raw.get("service", []):
                services.append(DIDServiceEndpoint(
                    id=svc.get("id", ""),
                    type=svc.get("type", ""),
                    service_endpoint=svc.get("serviceEndpoint", ""),
                ))

            return DIDDocument(
                id=raw.get("id", ""),
                service=services,
                verification_method=raw.get("verificationMethod"),
            )
        except Exception as exc:
            logger.error("Failed to parse DID document: %s", exc)
            return None
