"""
OpenClaw — AI agent orchestrator for Iskander cooperatives.

Exposes a FastAPI server that:
  - Receives Mattermost outgoing webhook events
  - Routes them to the appropriate agent (currently: Clerk)
  - Returns the agent's response as a Mattermost bot reply

All agent actions that touch cooperative systems are logged to the
Glass Box audit trail before execution.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict
from typing import Annotated

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .agents.clerk import agent as clerk_agent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("openclaw")

app = FastAPI(
    title="OpenClaw",
    description="Iskander cooperative AI agent orchestrator",
    version="0.1.0",
)

MATTERMOST_TOKEN = os.environ["MATTERMOST_OUTGOING_WEBHOOK_TOKEN"]
BOT_USER_ID = os.environ["MATTERMOST_BOT_USER_ID"]  # Required — prevents response loops

# ---------------------------------------------------------------------------
# Rate limiting — simple in-memory sliding window
# Resets on restart; good enough for single-node cooperative deployments.
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = int(os.environ.get("CLERK_RATE_LIMIT_PER_MINUTE", "20"))
# user_id → list of timestamps within the window
_rate_counters: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: str) -> None:
    """Raise HTTP 429 if the user has exceeded the per-minute request limit."""
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW
    timestamps = _rate_counters[user_id]
    # Drop timestamps outside the window
    _rate_counters[user_id] = [t for t in timestamps if t > window_start]
    if len(_rate_counters[user_id]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before sending another message.",
        )
    _rate_counters[user_id].append(now)


# ---------------------------------------------------------------------------
# Mattermost outgoing webhook payload
# ---------------------------------------------------------------------------

class MattermostEvent(BaseModel):
    token: str
    team_id: str
    team_domain: str
    channel_id: str
    channel_name: str
    timestamp: int
    user_id: str
    user_name: str
    post_id: str
    text: str
    trigger_word: str = ""
    file_ids: str = ""


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent": "clerk"}


# ---------------------------------------------------------------------------
# Mattermost outgoing webhook receiver
# ---------------------------------------------------------------------------

@app.post("/webhook/mattermost")
async def mattermost_webhook(event: MattermostEvent) -> JSONResponse:
    """
    Receives Mattermost outgoing webhook events when a member mentions @clerk.
    Authenticates via token, strips the trigger word, dispatches to the Clerk agent.
    """
    # Authenticate — Mattermost sends the token in the body
    if not hmac.compare_digest(event.token, MATTERMOST_TOKEN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    # Ignore messages from the bot itself (prevents response loops)
    if event.user_id == BOT_USER_ID:
        return JSONResponse(content={})

    # Rate limit — checked after bot-loop guard so bot responses don't count
    _check_rate_limit(event.user_id)

    # Strip trigger word from message
    message = event.text
    if event.trigger_word and message.startswith(event.trigger_word):
        message = message[len(event.trigger_word):].strip()

    if not message:
        return JSONResponse(content={"text": "Yes? How can I help?"})

    logger.info("Clerk request | user=%s | channel=%s | message=%.80s",
                event.user_name, event.channel_name, message)

    try:
        response_text = clerk_agent.run(
            user_id=event.user_id,
            username=event.user_name,
            message=message,
            channel_id=event.channel_id,
        )
    except Exception:
        logger.exception("Clerk agent error")
        response_text = (
            "Something went wrong on my end. Please try again, "
            "or contact a fellow member if the problem persists."
        )

    # Mattermost outgoing webhooks expect {"text": "..."} in the response body
    return JSONResponse(content={"text": response_text})


# ---------------------------------------------------------------------------
# Loomio decision webhook receiver (from decision-recorder or Loomio directly)
# ---------------------------------------------------------------------------

# Required — do not accept unauthenticated Loomio webhooks
LOOMIO_WEBHOOK_SECRET = os.environ["LOOMIO_WEBHOOK_SECRET"]
MATTERMOST_GOVERNANCE_CHANNEL = os.environ.get("MATTERMOST_GOVERNANCE_CHANNEL_ID", "")
MATTERMOST_BOT_TOKEN = os.environ.get("MATTERMOST_BOT_TOKEN", "")


@app.post("/webhook/loomio-decision")
async def loomio_decision_webhook(
    request: Request,
    x_loomio_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """
    Receives a Loomio outcome webhook and posts a summary to #governance.
    Verifies HMAC-SHA256 signature — always required.
    """
    body = await request.body()

    if not x_loomio_signature:
        raise HTTPException(status_code=403, detail="Missing signature")
    expected = "sha256=" + hmac.new(
        LOOMIO_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(x_loomio_signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    outcome = payload.get("outcome", {})
    poll = payload.get("poll", {})

    if not poll:
        return {"status": "ignored", "reason": "no poll data"}

    summary = _format_decision_summary(poll, outcome)
    logger.info("Loomio decision received: %s", poll.get("title"))

    if MATTERMOST_GOVERNANCE_CHANNEL and MATTERMOST_BOT_TOKEN:
        _post_to_mattermost(MATTERMOST_GOVERNANCE_CHANNEL, summary)

    return {"status": "ok"}


def _format_decision_summary(poll: dict, outcome: dict) -> str:
    title = poll.get("title", "Unnamed proposal")
    status = poll.get("status", "unknown")
    stances = poll.get("stance_counts", {})
    outcome_text = outcome.get("statement", "")

    lines = [f"**Decision recorded: {title}**"]
    if stances:
        counts = ", ".join(f"{k}: {v}" for k, v in stances.items() if v)
        lines.append(f"Result: {counts}")
    if outcome_text:
        lines.append(f"Outcome: {outcome_text}")
    if poll.get("key"):
        lines.append(f"Full record: {os.environ.get('LOOMIO_URL', '')}/p/{poll['key']}")
    return "\n".join(lines)


def _post_to_mattermost(channel_id: str, message: str) -> None:
    try:
        httpx.post(
            f"{os.environ.get('MATTERMOST_URL', '')}/api/v4/posts",
            json={"channel_id": channel_id, "message": message},
            headers={"Authorization": f"Bearer {MATTERMOST_BOT_TOKEN}"},
            timeout=10,
        ).raise_for_status()
    except Exception:
        logger.exception("Failed to post decision summary to Mattermost")
