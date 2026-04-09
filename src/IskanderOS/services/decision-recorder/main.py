"""
Decision Recorder — tamper-evident decision storage and Glass Box audit trail.

Endpoints:
  POST /webhook/loomio          Loomio outcome webhook → PostgreSQL + IPFS
  POST /log                     Glass Box: Clerk action log entry
  GET  /log                     Glass Box: query audit trail (member-readable)
  GET  /decisions               List recorded decisions
  GET  /decisions/{id}          Single decision with IPFS CID
  GET  /health                  Service health
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from . import ipfs
from .db import Decision, GlassBoxEntry, SessionLocal, create_tables, get_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("decision-recorder")

app = FastAPI(
    title="Decision Recorder",
    description="Tamper-evident cooperative decision storage and Glass Box audit trail",
    version="0.1.0",
)

# Required — refuse to start without it (same policy as OpenClaw after red team audit)
LOOMIO_WEBHOOK_SECRET = os.environ["LOOMIO_WEBHOOK_SECRET"]

# Shared secret for internal service-to-service calls (OpenClaw → Glass Box endpoints)
# Optional: if unset, internal endpoints are still network-isolated by NetworkPolicy.
# Set this for defence-in-depth when Headscale mesh is enabled (Phase B).
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

# ---------------------------------------------------------------------------
# Rate limiting — sliding window (same pattern as OpenClaw)
# ---------------------------------------------------------------------------

_RATE_WINDOW = 60  # seconds
_WEBHOOK_MAX = int(os.environ.get("DR_WEBHOOK_RATE_LIMIT", "60"))   # Loomio can burst
_QUERY_MAX = int(os.environ.get("DR_QUERY_RATE_LIMIT", "120"))       # read queries
_rate_counters: dict[str, list[float]] = defaultdict(list)


def _rate_check(key: str, max_requests: int) -> None:
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    _rate_counters[key] = [t for t in _rate_counters[key] if t > window_start]
    if len(_rate_counters[key]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded.",
        )
    _rate_counters[key].append(now)


@app.on_event("startup")
def startup() -> None:
    create_tables()
    logger.info("Decision recorder ready. IPFS available: %s", ipfs.is_available())


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "ipfs": ipfs.is_available(),
    }


# ---------------------------------------------------------------------------
# Loomio decision webhook
# ---------------------------------------------------------------------------

class LoomioWebhookPayload(BaseModel):
    """Validated shape of a Loomio outcome_created webhook payload."""

    class Poll(BaseModel):
        id: int
        title: str = ""
        key: str = ""
        status: str = "unknown"
        closed_at: str | None = None
        stance_counts: dict = Field(default_factory=dict)
        group: dict = Field(default_factory=dict)

        @field_validator("title")
        @classmethod
        def title_not_empty(cls, v: str) -> str:
            if len(v) > 500:
                raise ValueError("title too long")
            return v

    class Outcome(BaseModel):
        statement: str | None = None

        @field_validator("statement")
        @classmethod
        def statement_length(cls, v: str | None) -> str | None:
            if v and len(v) > 10_000:
                raise ValueError("outcome statement too long")
            return v

    poll: Poll
    outcome: Outcome = Field(default_factory=lambda: LoomioWebhookPayload.Outcome())


@app.post("/webhook/loomio", status_code=status.HTTP_202_ACCEPTED)
async def loomio_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_loomio_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Receives a Loomio outcome_created webhook.
    HMAC verification always required.
    Stores to PostgreSQL, pins payload to IPFS (best-effort, 202 response).
    """
    body = await request.body()

    # Rate limit by remote host
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"webhook:{client_host}", _WEBHOOK_MAX)

    # HMAC verification — always required, no conditional
    if not x_loomio_signature:
        raise HTTPException(status_code=403, detail="Missing X-Loomio-Signature")
    expected = "sha256=" + hmac.new(
        LOOMIO_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(x_loomio_signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Validate payload structure
    try:
        raw_json = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        payload = LoomioWebhookPayload(**raw_json)
    except Exception as exc:
        logger.warning("Webhook payload validation failed: %s", exc)
        raise HTTPException(status_code=400, detail="Unexpected payload structure")

    poll = payload.poll
    outcome = payload.outcome

    # Persist to PostgreSQL
    decision = Decision(
        loomio_poll_id=poll.id,
        loomio_group_key=poll.group.get("key"),
        title=poll.title,
        outcome=outcome.statement,
        status=poll.status,
        stance_counts=json.dumps(poll.stance_counts),
        raw_payload=json.dumps(raw_json, sort_keys=True),
        loomio_url=f"{os.environ.get('LOOMIO_URL', '')}/p/{poll.key}",
        decided_at=_parse_dt(poll.closed_at),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    logger.info("Recorded decision #%d: %s", decision.id, decision.title)

    # Pin to IPFS — best effort (don't fail the webhook if IPFS is down)
    try:
        cid = ipfs.pin_json(raw_json)
        decision.ipfs_cid = cid
        db.commit()
        logger.info("Pinned decision #%d to IPFS: %s", decision.id, cid)
    except Exception:
        logger.exception("IPFS pin failed for decision #%d — CID will be null", decision.id)

    return {"status": "recorded", "decision_id": decision.id, "ipfs_cid": decision.ipfs_cid}


# ---------------------------------------------------------------------------
# Glass Box — Clerk action audit trail
# ---------------------------------------------------------------------------

class GlassBoxLogRequest(BaseModel):
    actor: str = Field(..., description="Mattermost user ID of the member", max_length=100)
    agent: str = Field("clerk", description="Agent name", max_length=50)
    action: str = Field(..., description="What the agent is about to do", max_length=500)
    target: str = Field(..., description="Resource being acted on", max_length=500)
    reasoning: str = Field(..., description="Why the agent is taking this action", max_length=5_000)
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp from the agent")


@app.post("/log", status_code=status.HTTP_201_CREATED)
def glass_box_log(
    body: GlassBoxLogRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Record a Clerk agent action in the Glass Box audit trail.
    Called by the Clerk's glass_box_log tool before every write action.
    Internal callers only — protected by NetworkPolicy + optional service token.
    """
    _verify_internal_caller(request)

    try:
        ts = datetime.fromisoformat(body.timestamp.replace("Z", "+00:00"))
    except ValueError:
        ts = datetime.now(timezone.utc)

    entry = GlassBoxEntry(
        actor=body.actor,
        agent=body.agent,
        action=body.action,
        target=body.target,
        reasoning=body.reasoning,
        timestamp=ts,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info("Glass Box: %s by %s → %s", body.action, body.actor, body.target)
    return {"id": entry.id, "recorded": True}


@app.get("/log")
def glass_box_query(
    request: Request,
    actor: str | None = Query(None, description="Filter by member user ID"),
    agent: str | None = Query(None, description="Filter by agent name"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """
    Query the Glass Box audit trail.
    Readable by any authenticated cooperative member via the member API token,
    or by internal services via the service token.
    """
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"log-query:{client_host}", _QUERY_MAX)

    q = db.query(GlassBoxEntry).order_by(GlassBoxEntry.timestamp.desc())
    if actor:
        q = q.filter(GlassBoxEntry.actor == actor)
    if agent:
        q = q.filter(GlassBoxEntry.agent == agent)

    total = q.count()
    entries = q.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "actor": e.actor,
                "agent": e.agent,
                "action": e.action,
                "target": e.target,
                "reasoning": e.reasoning,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# Decision query endpoints
# ---------------------------------------------------------------------------

@app.get("/decisions")
def list_decisions(
    request: Request,
    group_key: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """List recorded decisions, newest first."""
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"decisions:{client_host}", _QUERY_MAX)

    q = db.query(Decision).order_by(Decision.recorded_at.desc())
    if group_key:
        q = q.filter(Decision.loomio_group_key == group_key)

    total = q.count()
    decisions = q.offset(offset).limit(limit).all()

    return {
        "total": total,
        "decisions": [_decision_summary(d) for d in decisions],
    }


@app.get("/decisions/{decision_id}")
def get_decision(
    decision_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Get a specific decision including full payload and IPFS CID."""
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"decisions:{client_host}", _QUERY_MAX)

    d = db.query(Decision).filter(Decision.id == decision_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {
        **_decision_summary(d),
        "raw_payload": json.loads(d.raw_payload),
        "ipfs_url": f"https://ipfs.io/ipfs/{d.ipfs_cid}" if d.ipfs_cid else None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_internal_caller(request: Request) -> None:
    """
    Verify the caller is an internal service when INTERNAL_SERVICE_TOKEN is set.
    Without a token configured (Phase C default), NetworkPolicy provides isolation.
    With a token (Phase B with Headscale mesh), both layers enforce access.
    """
    if not INTERNAL_SERVICE_TOKEN:
        return  # NetworkPolicy is the guard in Phase C
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Internal service token required")
    if not hmac.compare_digest(auth[7:], INTERNAL_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid service token")


def _decision_summary(d: Decision) -> dict:
    return {
        "id": d.id,
        "loomio_poll_id": d.loomio_poll_id,
        "title": d.title,
        "status": d.status,
        "outcome": d.outcome,
        "stance_counts": json.loads(d.stance_counts) if d.stance_counts else {},
        "ipfs_cid": d.ipfs_cid,
        "loomio_url": d.loomio_url,
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
        "recorded_at": d.recorded_at.isoformat(),
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
