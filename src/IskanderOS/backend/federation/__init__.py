"""
backend.federation
~~~~~~~~~~~~~~~~~~
Phase 14B: ActivityPub federation package.

Provides:
  HTTPSignatureSigner   — signs outbound HTTP requests (RFC 9421 / draft-cavage).
  HTTPSignatureVerifier — verifies inbound HTTP Signatures.
  InboxProcessor        — routes inbound ActivityPub activities by type.
  OutboxStore           — persists outbound activities to Postgres.
"""
from backend.federation.http_signatures import HTTPSignatureSigner, HTTPSignatureVerifier
from backend.federation.inbox_processor import InboxProcessor
from backend.federation.outbox_store import OutboxStore

__all__ = [
    "HTTPSignatureSigner",
    "HTTPSignatureVerifier",
    "InboxProcessor",
    "OutboxStore",
]
