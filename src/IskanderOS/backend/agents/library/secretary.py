"""
Secretary Agent — Meeting summaries, consensus extraction, ActivityPub broadcast.

Graph: parse_transcript → extract_consensus → prepare_broadcast → END
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.core.glass_box_parser import GlassBoxParser
from backend.agents.core.persona_generator import build_agent_prompt
from backend.agents.state import SecretaryState
from backend.config import settings
from backend.routers.power import agents_are_paused
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "secretary-agent-v1"

_role_prompt = load_prompt("prompt_secretary.txt")
_parser = GlassBoxParser()


# ── Node 1: Parse transcript into structured summary ─────────────────────────


def parse_transcript(state: SecretaryState) -> dict[str, Any]:
    """LLM-powered meeting transcript → structured summary."""
    if agents_are_paused():
        return {
            **state,
            "error": "Agents paused (low power mode). Retry when power restored.",
        }

    transcript = state.get("meeting_transcript") or ""
    if not transcript.strip():
        return {**state, "summary": "(empty transcript)", "error": None}

    system_prompt = build_agent_prompt(agent_specific_suffix=_role_prompt)
    user_msg = (
        f"Summarize the following cooperative meeting transcript into "
        f"clear, structured minutes.  Capture all motions, votes, action "
        f"items, and dissenting opinions.\n\n"
        f"TRANSCRIPT:\n{transcript[:8000]}"
    )

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        response = llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ]
        )
        # Parse through Glass Box — but summary is the raw content here.
        summary = response.content
    except Exception as exc:
        logger.warning("Ollama unavailable for summary: %s", exc)
        summary = f"[AUTO-FALLBACK] Raw transcript excerpt:\n{transcript[:2000]}"

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Summarize meeting transcript",
        rationale="Members who were absent need accurate minutes per CCIN Principle 5 (Education & Information).",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"transcript_length": len(transcript)},
    )

    return {
        **state,
        "summary": summary,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Extract consensus items ──────────────────────────────────────────

_CONSENSUS_SYSTEM = (
    "You are a consensus extraction engine.  From the meeting summary below, "
    "extract every decision point as a JSON array.  Each element must have:\n"
    '  {"motion": "...", "result": "passed"|"failed"|"tabled", '
    '"vote_count": {"for": N, "against": N, "abstain": N}, '
    '"assignee": "name"|null, "deadline": "YYYY-MM-DD"|null}\n'
    "Return ONLY the JSON array — no markdown fences, no commentary."
)


def extract_consensus(state: SecretaryState) -> dict[str, Any]:
    """Extract structured consensus items from the meeting summary."""
    summary = state.get("summary") or ""
    if not summary.strip():
        return {**state, "consensus_items": []}

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        response = llm.invoke(
            [
                {"role": "system", "content": _CONSENSUS_SYSTEM},
                {"role": "user", "content": summary[:6000]},
            ]
        )
        items = _parse_json_array(response.content)
    except Exception as exc:
        logger.warning("Consensus extraction LLM failed: %s", exc)
        items = []

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Extract consensus items from summary",
        rationale="Structured consensus enables democratic accountability (CCIN Principle 2).",
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"items_found": len(items)},
    )

    return {
        **state,
        "consensus_items": items,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Prepare ActivityPub broadcast ─────────────────────────────────────


def prepare_broadcast(state: SecretaryState) -> dict[str, Any]:
    """Format summary + consensus as an ActivityPub Create/Note activity.

    Phase 14A addition: also queues a Matrix room notification to
    #iskander_governance so members receive the summary on their phones
    without waiting for ActivityPub federation delivery.

    NOTE: This node prepares the payload but does NOT dispatch it.
    The calling router is responsible for actual federation delivery after
    human approval (requires_human_token = true for all external comms).
    The Matrix notification is similarly queued — the router sends it
    after HITL approval.
    """
    summary = state.get("summary") or ""
    items = state.get("consensus_items", [])
    domain = settings.activitypub_domain

    activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"https://{domain}/activities/{uuid4()}",
        "type": "Create",
        "actor": f"https://{domain}/federation/actors/secretary",
        "published": datetime.now(timezone.utc).isoformat(),
        "to": ["https://www.w3.org/ns/activitystreams#Public"],
        "object": {
            "type": "Note",
            "content": summary[:4000],
            "attachment": [
                {
                    "type": "Document",
                    "mediaType": "application/json",
                    "name": "consensus_items",
                    "content": json.dumps(items, default=str),
                }
            ],
        },
    }

    # Phase 14A: Matrix notification body (plain text for room delivery).
    consensus_lines = ""
    for item in items[:5]:  # First 5 items; truncate for brevity.
        motion = item.get("motion", "?")
        result = item.get("result", "?")
        consensus_lines += f"\n• {motion} → **{result}**"

    matrix_body = (
        f"**Meeting Summary**\n\n"
        f"{summary[:800]}"
        + (f"\n\n**Decisions:{consensus_lines}" if consensus_lines else "")
        + f"\n\n_Full minutes published to the cooperative's activity stream._"
    )

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Prepare ActivityPub + Matrix governance broadcast",
        rationale=(
            "Federation broadcast promotes Cooperation Among Cooperatives "
            "(CCIN Principle 6). Matrix notification enables real-time "
            "member engagement. Both require human approval before dispatch."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "activity_id": activity["id"],
            "matrix_body_length": len(matrix_body),
            "consensus_items": len(items),
        },
    )

    return {
        **state,
        "activitypub_broadcast": activity,
        # Phase 14A: carry the Matrix notification body for the router to send.
        "matrix_notification_body": matrix_body,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_secretary_graph():
    """Compile the Secretary Agent LangGraph."""
    g = StateGraph(SecretaryState)
    g.add_node("parse_transcript", parse_transcript)
    g.add_node("extract_consensus", extract_consensus)
    g.add_node("prepare_broadcast", prepare_broadcast)
    g.set_entry_point("parse_transcript")
    g.add_edge("parse_transcript", "extract_consensus")
    g.add_edge("extract_consensus", "prepare_broadcast")
    g.add_edge("prepare_broadcast", END)
    return g.compile()


secretary_graph = build_secretary_graph()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    """Best-effort JSON array extraction from LLM output."""
    cleaned = text.strip()
    # Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        result = json.loads(cleaned[start : end + 1])
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []
