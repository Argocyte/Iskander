"""
Decision Recorder — tamper-evident decision storage and Glass Box audit trail.

Endpoints:
  POST /webhook/loomio          Loomio outcome webhook → PostgreSQL + IPFS
  POST /log                     Glass Box: Clerk action log entry
  GET  /log                     Glass Box: query audit trail (member-readable)
  GET  /decisions               List recorded decisions
  GET  /decisions/{id}          Single decision with IPFS CID
  PATCH /decisions/{id}/review         Set review date on an agreement (S3: Evolve Agreements)
  GET  /decisions/reviews/due          Agreements due for review
  PATCH /decisions/{id}/accountability Update implementation status (Decidim accountability)
  GET  /decisions/accountability/overdue Decisions needing accountability follow-up
  POST /tensions                       Log an organisational tension (S3: Navigate Via Tension)
  GET  /tensions                List tensions
  PATCH /tensions/{id}          Update tension status / driver statement
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
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

import ipfs
from db import Decision, GlassBoxEntry, SessionLocal, Tension, create_tables, get_db

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
# Agreement review scheduling (S3: Evaluate and Evolve Agreements)
# ---------------------------------------------------------------------------

class ReviewUpdateRequest(BaseModel):
    review_date: str = Field(..., description="ISO 8601 date YYYY-MM-DD")
    review_circle: str | None = Field(None, description="Loomio group key responsible")

    @field_validator("review_date")
    @classmethod
    def parse_date(cls, v: str) -> str:
        try:
            parsed = date.fromisoformat(v)
        except ValueError:
            raise ValueError("review_date must be YYYY-MM-DD")
        if parsed <= date.today():
            raise ValueError("review_date must be a future date")
        return v


@app.patch("/decisions/{decision_id}/review")
def set_review_date(
    decision_id: int,
    body: ReviewUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Set or update the review date on a recorded agreement."""
    _verify_internal_caller(request)
    d = db.query(Decision).filter(Decision.id == decision_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")
    d.review_date = date.fromisoformat(body.review_date)
    if body.review_circle:
        d.review_circle = body.review_circle
    d.review_status = "pending"
    db.commit()
    return {"id": d.id, "review_date": str(d.review_date), "review_circle": d.review_circle}


@app.get("/decisions/reviews/due")
def list_due_reviews(
    request: Request,
    days_ahead: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """List agreements whose review date falls within the next N days."""
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"decisions:{client_host}", _QUERY_MAX)

    cutoff = date.today()
    from datetime import timedelta
    future = cutoff + timedelta(days=days_ahead)

    due = (
        db.query(Decision)
        .filter(
            Decision.review_date.isnot(None),
            Decision.review_date <= future,
            Decision.review_status != "complete",
        )
        .order_by(Decision.review_date)
        .all()
    )
    return {
        "count": len(due),
        "days_ahead": days_ahead,
        "reviews": [
            {
                "id": d.id,
                "title": d.title,
                "review_date": str(d.review_date),
                "review_circle": d.review_circle,
                "review_status": d.review_status,
                "loomio_url": d.loomio_url,
            }
            for d in due
        ],
    }


# ---------------------------------------------------------------------------
# Accountability tracking (Decidim-inspired: was the decision implemented?)
# ---------------------------------------------------------------------------

_ACCOUNTABILITY_STATUSES = frozenset({
    "not_applicable",
    "not_started",
    "in_progress",
    "implemented",
    "not_implemented",
    "deferred",
})


class AccountabilityUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description=(
            "not_applicable | not_started | in_progress | "
            "implemented | not_implemented | deferred"
        ),
    )
    notes: str | None = Field(None, description="Free-text implementation notes", max_length=4_000)
    review_date: str | None = Field(None, description="ISO 8601 YYYY-MM-DD for next accountability check")
    updated_by: str = Field(..., description="Mattermost user ID of the member updating", max_length=128)

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in _ACCOUNTABILITY_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_ACCOUNTABILITY_STATUSES))}")
        return v

    @field_validator("review_date")
    @classmethod
    def future_review_date(cls, v: str | None) -> str | None:
        if not v:
            return v
        try:
            parsed = date.fromisoformat(v)
        except ValueError:
            raise ValueError("review_date must be YYYY-MM-DD")
        if parsed <= date.today():
            raise ValueError("review_date must be a future date")
        return v


@app.patch("/decisions/{decision_id}/accountability")
def update_accountability(
    decision_id: int,
    body: AccountabilityUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Update the accountability status on a recorded decision.

    Tracks whether the decision was actually implemented — closing the loop
    between governance outcome and real-world action (Decidim pattern, issue #94).
    Glass Box logs all changes so any member can audit the accountability trail.
    """
    _verify_internal_caller(request)
    actor_user_id = request.headers.get("X-Actor-User-Id", "")
    if actor_user_id and body.updated_by != actor_user_id:
        raise HTTPException(
            status_code=403,
            detail="updated_by must match the authenticated actor (X-Actor-User-Id)",
        )

    d = db.query(Decision).filter(Decision.id == decision_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")

    old_status = d.accountability_status
    d.accountability_status = body.status
    d.accountability_updated_at = datetime.now(timezone.utc)
    if body.notes is not None:
        d.accountability_notes = body.notes
    if body.review_date is not None:
        d.accountability_review_date = date.fromisoformat(body.review_date)

    db.commit()
    logger.info(
        "Accountability updated by %s: decision=%s %s→%s",
        body.updated_by, decision_id, old_status, body.status,
    )
    return _decision_accountability_summary(d)


@app.get("/decisions/accountability/overdue")
def list_overdue_accountability(
    request: Request,
    days_ahead: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    """
    List decisions whose accountability_review_date falls within the next N days
    and are still in an open status (not implemented or not_applicable).

    Used by the Clerk agent for weekly accountability reminders.
    """
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"decisions:{client_host}", _QUERY_MAX)

    from datetime import timedelta
    future = date.today() + timedelta(days=days_ahead)

    open_statuses = ("not_started", "in_progress", "deferred")
    due = (
        db.query(Decision)
        .filter(
            Decision.accountability_review_date.isnot(None),
            Decision.accountability_review_date <= future,
            Decision.accountability_status.in_(open_statuses),
        )
        .order_by(Decision.accountability_review_date)
        .all()
    )
    return {
        "count": len(due),
        "days_ahead": days_ahead,
        "decisions": [_decision_accountability_summary(d) for d in due],
    }


def _decision_accountability_summary(d: Decision) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "accountability_status": d.accountability_status,
        "accountability_notes": d.accountability_notes,
        "accountability_review_date": str(d.accountability_review_date) if d.accountability_review_date else None,
        "accountability_updated_at": d.accountability_updated_at.isoformat() if d.accountability_updated_at else None,
        "loomio_url": d.loomio_url,
    }


# ---------------------------------------------------------------------------
# Tension tracking (S3: Navigate Via Tension)
# ---------------------------------------------------------------------------

class TensionCreateRequest(BaseModel):
    description: str = Field(..., description="What the member noticed", max_length=5_000)
    domain: str | None = Field(None, description="Circle or group this relates to", max_length=128)
    driver_statement: str | None = Field(None, description="Optional S3 driver statement", max_length=2_000)
    logged_by: str = Field(..., description="Mattermost user ID", max_length=128)


class TensionUpdateRequest(BaseModel):
    updated_by: str = Field(..., description="Mattermost user ID of the member making the update", max_length=128)
    status: str | None = Field(None, description="open | in_progress | resolved")
    driver_statement: str | None = Field(None, max_length=2_000)
    loomio_discussion_id: int | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v and v not in ("open", "in_progress", "resolved"):
            raise ValueError("status must be open, in_progress, or resolved")
        return v


@app.post("/tensions", status_code=status.HTTP_201_CREATED)
def log_tension(
    body: TensionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Log an organisational tension for structured processing."""
    _verify_internal_caller(request)
    actor_user_id = request.headers.get("X-Actor-User-Id", "")
    if actor_user_id and body.logged_by != actor_user_id:
        raise HTTPException(
            status_code=403,
            detail="logged_by must match the authenticated actor (X-Actor-User-Id)",
        )
    tension = Tension(
        logged_by=body.logged_by,
        description=body.description,
        domain=body.domain,
        driver_statement=body.driver_statement,
    )
    db.add(tension)
    db.commit()
    db.refresh(tension)
    logger.info("Tension logged by %s: %.60s", body.logged_by, body.description)
    return _tension_summary(tension)


@app.get("/tensions")
def list_tensions(
    request: Request,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """
    List logged tensions.

    The logged_by filter has been removed (#64): it allowed any caller to
    enumerate tensions by any user ID without an ownership check. All tensions
    in a cooperative are visible to all members via the Clerk; per-user
    filtering with RBAC is planned for Phase B.
    """
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"decisions:{client_host}", _QUERY_MAX)

    q = db.query(Tension).order_by(Tension.logged_at.desc())
    if status_filter:
        q = q.filter(Tension.status == status_filter)
    actor_user_id = request.headers.get("X-Actor-User-Id", "")
    if actor_user_id:
        q = q.filter(Tension.logged_by == actor_user_id)
    total = q.count()
    tensions = q.offset(offset).limit(limit).all()
    return {"total": total, "tensions": [_tension_summary(t) for t in tensions]}


@app.patch("/tensions/{tension_id}")
def update_tension(
    tension_id: int,
    body: TensionUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Update tension status, driver statement, or linked discussion.

    Ownership enforced (#63): only the member who logged the tension may update it.
    Phase B will add a facilitator-override path when circle roles are implemented.
    """
    _verify_internal_caller(request)
    actor_user_id = request.headers.get("X-Actor-User-Id", "")
    if actor_user_id and body.updated_by != actor_user_id:
        raise HTTPException(
            status_code=403,
            detail="updated_by must match the authenticated actor (X-Actor-User-Id)",
        )
    t = db.query(Tension).filter(Tension.id == tension_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tension not found")
    if t.logged_by != body.updated_by:
        raise HTTPException(
            status_code=403,
            detail="Only the member who logged this tension may update it.",
        )
    if body.status:
        t.status = body.status
        if body.status == "resolved" and not t.resolved_at:
            t.resolved_at = datetime.now(timezone.utc)
    if body.driver_statement is not None:
        t.driver_statement = body.driver_statement
    if body.loomio_discussion_id is not None:
        t.loomio_discussion_id = body.loomio_discussion_id
    db.commit()
    return _tension_summary(t)


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


def _tension_summary(t: Tension) -> dict:
    return {
        "id": t.id,
        "logged_by": t.logged_by,
        "description": t.description,
        "domain": t.domain,
        "driver_statement": t.driver_statement,
        "status": t.status,
        "loomio_discussion_id": t.loomio_discussion_id,
        "logged_at": t.logged_at.isoformat(),
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
    }


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
        "accountability_status": d.accountability_status,
        "accountability_review_date": str(d.accountability_review_date) if d.accountability_review_date else None,
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
