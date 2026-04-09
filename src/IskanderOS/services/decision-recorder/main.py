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
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
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

LOOMIO_WEBHOOK_SECRET = os.environ.get("LOOMIO_WEBHOOK_SECRET", "")


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

@app.post("/webhook/loomio", status_code=status.HTTP_202_ACCEPTED)
async def loomio_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_loomio_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Receives a Loomio outcome_created webhook.
    Verifies HMAC, stores to PostgreSQL, pins payload to IPFS.
    Returns immediately (202) so Loomio doesn't time out; IPFS pin is best-effort.
    """
    body = await request.body()

    # Verify HMAC when secret is configured
    if LOOMIO_WEBHOOK_SECRET:
        if not x_loomio_signature:
            raise HTTPException(status_code=403, detail="Missing X-Loomio-Signature")
        expected = "sha256=" + hmac.new(
            LOOMIO_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(x_loomio_signature, expected):
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    poll = payload.get("poll", {})
    outcome = payload.get("outcome", {})

    if not poll.get("id"):
        logger.warning("Received webhook with no poll data — ignoring")
        return {"status": "ignored"}

    # Persist to PostgreSQL
    decision = Decision(
        loomio_poll_id=poll["id"],
        loomio_group_key=poll.get("group", {}).get("key"),
        title=poll.get("title", ""),
        outcome=outcome.get("statement"),
        status=poll.get("status", "unknown"),
        stance_counts=json.dumps(poll.get("stance_counts", {})),
        raw_payload=json.dumps(payload, sort_keys=True),
        loomio_url=f"{os.environ.get('LOOMIO_URL', '')}/p/{poll.get('key', '')}",
        decided_at=_parse_dt(poll.get("closed_at")),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    logger.info("Recorded decision #%d: %s", decision.id, decision.title)

    # Pin to IPFS — best effort (don't fail the webhook if IPFS is down)
    try:
        cid = ipfs.pin_json(payload)
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
    actor: str = Field(..., description="Mattermost user ID of the member")
    agent: str = Field("clerk", description="Agent name")
    action: str = Field(..., description="What the agent is about to do")
    target: str = Field(..., description="Resource being acted on")
    reasoning: str = Field(..., description="Why the agent is taking this action")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp from the agent")


@app.post("/log", status_code=status.HTTP_201_CREATED)
def glass_box_log(
    body: GlassBoxLogRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Record a Clerk agent action in the Glass Box audit trail.
    Called by the Clerk's glass_box_log tool before every write action.
    """
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
    actor: str | None = Query(None, description="Filter by member user ID"),
    agent: str | None = Query(None, description="Filter by agent name"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """
    Query the Glass Box audit trail. Readable by any cooperative member.
    Returns a paginated list of Clerk actions with reasoning.
    """
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
    group_key: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """List recorded decisions, newest first."""
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
def get_decision(decision_id: int, db: Session = Depends(get_db)) -> dict:
    """Get a specific decision including full payload and IPFS CID."""
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
