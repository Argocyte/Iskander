"""
/secretary — Meeting summaries & governance broadcasts.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.library.secretary import secretary_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/secretary", tags=["secretary"])


# ── Request / Response schemas ────────────────────────────────────────────────


class SummarizeRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Raw meeting transcript text.")


class SummarizeResponse(BaseModel):
    summary: str
    consensus_items: list[dict[str, Any]]
    activitypub_broadcast: dict[str, Any] | None = None
    action_log: list[dict[str, Any]] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_meeting(req: SummarizeRequest):
    """Summarize a meeting transcript, extract consensus, prepare AP broadcast."""
    initial_state = {
        "messages": [],
        "agent_id": "secretary-agent-v1",
        "action_log": [],
        "error": None,
        "meeting_transcript": req.transcript,
        "summary": None,
        "consensus_items": [],
        "activitypub_broadcast": None,
    }

    try:
        result = secretary_graph.invoke(initial_state)
    except Exception as exc:
        logger.exception("Secretary agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])

    return SummarizeResponse(
        summary=result.get("summary", ""),
        consensus_items=result.get("consensus_items", []),
        activitypub_broadcast=result.get("activitypub_broadcast"),
        action_log=result.get("action_log", []),
    )
