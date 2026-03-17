"""
ActivityPub Federation Router — /federation

Implements the minimal ActivityPub server-to-server (S2S) protocol
so Iskander nodes can federate with each other and the broader Fediverse.

Endpoints:
  GET  /federation/actors/{handle}         — Actor profile (WebFinger target)
  GET  /federation/actors/{handle}/inbox   — Stub inbox (read)
  POST /federation/actors/{handle}/inbox   — Receive federated activities
  GET  /federation/actors/{handle}/outbox  — Cooperative's public activity stream
  GET  /federation/.well-known/webfinger   — WebFinger discovery

HTTP Signatures for incoming requests are verified using the sender's
public key fetched from their Actor object. The `cryptography` library
handles RSA-SHA256 signing/verification.

NOTE: This router is a scaffold. Full inbox processing (Follow, Announce,
Create) and HTTP Signature verification are marked with TODO stubs for
Phase 4 agent integration.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from backend.boundary.boundary_agent import BoundaryAgent
from backend.config import settings
from backend.federation.http_signatures import HTTPSignatureVerifier
from backend.federation.inbox_processor import InboxProcessor
from backend.federation.outbox_store import OutboxStore
from backend.schemas.glass_box import ActivityObject, ActivityPubActor, ActorType

_verifier = HTTPSignatureVerifier()
_inbox_processor = InboxProcessor()
_outbox_store = OutboxStore.get_instance()

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/federation", tags=["federation"])

ACTIVITY_STREAMS_CONTEXT = "https://www.w3.org/ns/activitystreams"
CONTENT_TYPE = 'application/activity+json; charset=utf-8'


# ── In-memory actor registry (replace with Postgres in Phase 4) ──────────────

def _base_url() -> str:
    return settings.activitypub_base_url.rstrip("/")


def _build_actor(handle: str, name: str, public_key_pem: str = "") -> dict[str, Any]:
    base = _base_url()
    actor_id = f"{base}/federation/actors/{handle}"
    return {
        "@context": [
            ACTIVITY_STREAMS_CONTEXT,
            "https://w3id.org/security/v1",
        ],
        "id":                actor_id,
        "type":              ActorType.COOP.value,
        "preferredUsername": handle,
        "name":              name,
        "summary":           f"Iskander cooperative node: {name}",
        "inbox":             f"{actor_id}/inbox",
        "outbox":            f"{actor_id}/outbox",
        "followers":         f"{actor_id}/followers",
        "following":         f"{actor_id}/following",
        "publicKey": {
            "id":           f"{actor_id}#main-key",
            "owner":        actor_id,
            "publicKeyPem": public_key_pem or "# TODO: generate RSA key pair on first boot",
        },
        "endpoints": {
            "sharedInbox": f"{base}/federation/inbox",
        },
    }


# ── WebFinger ─────────────────────────────────────────────────────────────────

@router.get(
    "/.well-known/webfinger",
    summary="WebFinger discovery (RFC 7033)",
    include_in_schema=True,
)
async def webfinger(resource: str) -> JSONResponse:
    """
    Standard WebFinger endpoint. Clients query:
      /.well-known/webfinger?resource=acct:coop@iskander.local

    Returns a JRD pointing to the Actor profile.
    """
    if not resource.startswith("acct:"):
        raise HTTPException(status_code=400, detail="Only acct: URIs supported")

    account = resource.removeprefix("acct:")
    if "@" not in account:
        raise HTTPException(status_code=400, detail="Invalid acct URI format")

    handle, domain = account.split("@", 1)
    actor_url = f"{_base_url()}/federation/actors/{handle}"

    jrd = {
        "subject": resource,
        "links": [
            {
                "rel":  "self",
                "type": "application/activity+json",
                "href": actor_url,
            }
        ],
    }
    return JSONResponse(content=jrd, media_type="application/jrd+json")


# ── Actor ─────────────────────────────────────────────────────────────────────

@router.get(
    "/actors/{handle}",
    summary="Fetch ActivityPub Actor profile",
)
async def get_actor(handle: str) -> JSONResponse:
    """
    Returns the cooperative's ActivityPub Actor object.
    In production, handles map to CoopIdentity member DIDs in Postgres.
    """
    # TODO Phase 4: look up handle in Postgres member registry
    actor = _build_actor(handle=handle, name=f"{handle} @ {settings.activitypub_domain}")
    return JSONResponse(content=actor, media_type=CONTENT_TYPE)


# ── Inbox ─────────────────────────────────────────────────────────────────────

@router.get("/actors/{handle}/inbox", summary="Inbox stub (auth required in prod)")
async def get_inbox(handle: str) -> JSONResponse:
    """Stub: returns empty ordered collection. Full impl in Phase 4."""
    base = _base_url()
    return JSONResponse(
        content={
            "@context":    ACTIVITY_STREAMS_CONTEXT,
            "id":          f"{base}/federation/actors/{handle}/inbox",
            "type":        "OrderedCollection",
            "totalItems":  0,
            "orderedItems": [],
        },
        media_type=CONTENT_TYPE,
    )


@router.post(
    "/actors/{handle}/inbox",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive a federated Activity",
)
async def post_inbox(handle: str, request: Request) -> Response:
    """
    Receive inbound ActivityPub activities from federated nodes.

    Security: HTTP Signature verification is TODO for Phase 4.
    Until then, this endpoint MUST NOT be exposed to the public internet.
    It is safe on a LAN-only iskander.local deployment.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    activity_type = body.get("type", "Unknown")
    actor_iri     = body.get("actor", "unknown")

    logger.info(
        "activitypub_inbox_received",
        handle=handle,
        activity_type=activity_type,
        actor=actor_iri,
    )

    # Phase 14B: HTTP Signature verification.
    raw_body = await request.body()
    is_valid, reason = await _verifier.verify(
        headers=dict(request.headers),
        method="POST",
        path=request.url.path,
        body=raw_body,
    )
    if not is_valid:
        logger.warning("HTTP Signature verification failed for inbox POST: %s", reason)
        # Accept in stub/dev mode; reject in production.
        if not reason.startswith("STUB"):
            raise HTTPException(status_code=401, detail=f"Invalid HTTP Signature: {reason}")

    # Fix 7: Route through Boundary Agent before InboxProcessor.
    boundary = BoundaryAgent.get_instance()
    verdicts = await boundary.ingest(body, local_handle=handle)

    for verdict in verdicts:
        if verdict.proceed:
            action = await _inbox_processor.process(
                verdict.translated_activity, local_handle=handle,
            )
            logger.info(
                "Inbox processed via boundary: %s (hitl=%s)",
                action.action,
                verdict.requires_hitl,
            )
        else:
            logger.warning(
                "Boundary agent rejected activity",
                actor=verdict.actor_iri,
                reason=verdict.governance_reason,
                causal_buffered=verdict.causal_buffered,
            )

    return Response(status_code=status.HTTP_202_ACCEPTED)


# ── Outbox ────────────────────────────────────────────────────────────────────

@router.get(
    "/actors/{handle}/outbox",
    summary="Cooperative's public activity stream",
)
async def get_outbox(handle: str) -> JSONResponse:
    """
    Returns the cooperative's public outbox as an OrderedCollection.
    TODO Phase 4: paginate from Postgres federation_outbox table.
    """
    base = _base_url()
    # Phase 14B: return activities from OutboxStore.
    recent = _outbox_store.get_recent(limit=20)
    return JSONResponse(
        content={
            "@context":    ACTIVITY_STREAMS_CONTEXT,
            "id":          f"{base}/federation/actors/{handle}/outbox",
            "type":        "OrderedCollection",
            "totalItems":  _outbox_store.total_count(),
            "orderedItems": [r["raw_activity"] for r in recent],
        },
        media_type=CONTENT_TYPE,
    )


# ── Shared inbox (server-wide) ────────────────────────────────────────────────

@router.post(
    "/inbox",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Shared inbox — receives activities for all local actors",
)
async def shared_inbox(request: Request) -> Response:
    """Shared inbox for efficient federation delivery. Stub for Phase 4."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logger.info("activitypub_shared_inbox", activity_type=body.get("type"))
    # TODO Phase 4: fan-out to per-actor inboxes
    return Response(status_code=status.HTTP_202_ACCEPTED)
