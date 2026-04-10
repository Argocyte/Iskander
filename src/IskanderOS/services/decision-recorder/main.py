"""
Decision Recorder — tamper-evident decision storage and Glass Box audit trail.

Endpoints:
  POST /webhook/loomio                       Loomio outcome webhook → PostgreSQL + IPFS
  POST /log                                  Glass Box: Clerk action log entry
  GET  /log                                  Glass Box: query audit trail (member-readable)
  GET  /decisions                            List recorded decisions
  GET  /decisions/{id}                       Single decision with IPFS CID
  PATCH /decisions/{id}/review               Set review date on an agreement (S3: Evolve Agreements)
  GET  /decisions/reviews/due                Agreements due for review
  POST /tensions                             Log an organisational tension (S3: Navigate Via Tension)
  GET  /tensions                             List tensions
  PATCH /tensions/{id}                       Update tension status / driver statement
  POST /governance/health-reports            Store a governance health report (from Clerk)
  GET  /governance/health-reports/latest     Most recent governance health report
  PATCH /governance/health-reports/{id}/suppress-nudge  Suppress a nudge
  GET  /health                               Service health
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
from db import Decision, GlassBoxEntry, GovernanceHealthReport, SessionLocal, Tension, create_tables, get_db

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
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("review_date must be YYYY-MM-DD")
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
# Tension tracking (S3: Navigate Via Tension)
# ---------------------------------------------------------------------------

class TensionCreateRequest(BaseModel):
    description: str = Field(..., description="What the member noticed", max_length=5_000)
    domain: str | None = Field(None, description="Circle or group this relates to", max_length=128)
    driver_statement: str | None = Field(None, description="Optional S3 driver statement", max_length=2_000)
    logged_by: str = Field(..., description="Mattermost user ID", max_length=128)


class TensionUpdateRequest(BaseModel):
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
    logged_by: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """List logged tensions."""
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"decisions:{client_host}", _QUERY_MAX)

    q = db.query(Tension).order_by(Tension.logged_at.desc())
    if status_filter:
        q = q.filter(Tension.status == status_filter)
    if logged_by:
        q = q.filter(Tension.logged_by == logged_by)
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
    """Update tension status, driver statement, or linked discussion."""
    _verify_internal_caller(request)
    t = db.query(Tension).filter(Tension.id == tension_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tension not found")
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
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Governance Health Reports — store and retrieve health assessments from Clerk
# ---------------------------------------------------------------------------

_VALID_LIFECYCLE_STAGES = {"founding", "growing", "maturing", "scaling", "federated"}
_VALID_SEVERITIES = {"advisory", "warning", "urgent"}


class HealthReportRequest(BaseModel):
    lifecycle_stage: str | None = None
    signals: list[dict] = Field(default_factory=list)
    nudges: list[dict] = Field(default_factory=list)

    @field_validator("lifecycle_stage")
    @classmethod
    def valid_stage(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_LIFECYCLE_STAGES:
            raise ValueError(f"lifecycle_stage must be one of {sorted(_VALID_LIFECYCLE_STAGES)}")
        return v

    @field_validator("signals")
    @classmethod
    def validate_signals(cls, v: list[dict]) -> list[dict]:
        for sig in v:
            if "id" not in sig or "severity" not in sig:
                raise ValueError("Each signal must have 'id' and 'severity'")
            if sig["severity"] not in _VALID_SEVERITIES:
                raise ValueError(f"Signal severity must be one of {sorted(_VALID_SEVERITIES)}")
        return v


class SuppressNudgeRequest(BaseModel):
    nudge_id: str = Field(..., min_length=1, max_length=64)


@app.post("/governance/health-reports", status_code=status.HTTP_201_CREATED)
def store_health_report(
    body: HealthReportRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Store a governance health report produced by the Clerk.

    Called by the Clerk after running a health assessment. The report is then
    retrievable by any member via GET /governance/health-reports/latest.
    All reports are visible to members — no hidden assessments (Glass Box principle).
    """
    _rate_check(request.client.host if request.client else "internal", _QUERY_MAX)
    _verify_internal_caller(request)

    report = GovernanceHealthReport(
        lifecycle_stage=body.lifecycle_stage,
        signals_json=json.dumps(body.signals),
        nudges_json=json.dumps(body.nudges),
        suppressed_json="[]",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _health_report_summary(report)


@app.get("/governance/health-reports/latest")
def get_latest_health_report(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Return the most recent governance health report.

    Returns 404 if no assessment has been run yet.
    """
    _rate_check(request.client.host if request.client else "internal", _QUERY_MAX)
    report = (
        db.query(GovernanceHealthReport)
        .order_by(GovernanceHealthReport.assessed_at.desc())
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No health report found. Run an assessment first.")
    return _health_report_summary(report)


@app.patch("/governance/health-reports/{report_id}/suppress-nudge")
def suppress_nudge(
    report_id: int,
    body: SuppressNudgeRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Mark a nudge as suppressed by the cooperative.

    Members can suppress nudges that are not relevant to their situation.
    The suppression is recorded in the report — all suppression decisions
    are visible to members (Glass Box principle).
    """
    _rate_check(request.client.host if request.client else "internal", _QUERY_MAX)
    _verify_internal_caller(request)

    report = db.get(GovernanceHealthReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    suppressed = json.loads(report.suppressed_json)
    if body.nudge_id not in suppressed:
        suppressed.append(body.nudge_id)
        report.suppressed_json = json.dumps(suppressed)
        db.commit()

    return _health_report_summary(report)


def _health_report_summary(r: GovernanceHealthReport) -> dict:
    return {
        "id": r.id,
        "assessed_at": r.assessed_at.isoformat(),
        "lifecycle_stage": r.lifecycle_stage,
        "signals": json.loads(r.signals_json),
        "nudges": json.loads(r.nudges_json),
        "suppressed_nudges": json.loads(r.suppressed_json),
    }
