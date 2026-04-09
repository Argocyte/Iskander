"""
ProposalAgent — Process recommendation and proposal drafting.

Summarises thread discussion, recommends a democratic process type from the
cooperative's nine supported processes, and drafts a proposal body + options
for human editing before opening the poll.

Graph:
  summarise_discussion → recommend_process → draft_proposal_text
    → [HITL: human_edit_proposal]
    → open_poll → notify_participants → END

Compiled with interrupt_before=["human_edit_proposal"].

Every node follows the Glass Box Protocol: state mutations are accompanied by
an AgentAction record logged to the action_log.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import ProposalState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "proposal-agent-v1"

VALID_PROCESS_TYPES = {
    "sense_check", "advice", "consent", "consensus",
    "choose", "score", "allocate", "rank", "time_poll",
}

_role_prompt = load_prompt("prompt_proposal.txt")


# ── Node 1: Summarise discussion ──────────────────────────────────────────────


def summarise_discussion(state: ProposalState) -> dict[str, Any]:
    """LLM-powered discussion thread → structured summary.

    Falls back to 'Discussion pending summary.' if the LLM is unavailable.
    """
    thread_id = state.get("thread_id") or "unknown"
    messages = state.get("messages") or []

    # Build a plain-text representation of any existing messages in state.
    thread_text = "\n".join(
        str(m.content) if hasattr(m, "content") else str(m)
        for m in messages
    ) if messages else ""

    summary: str
    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        user_msg = (
            "Summarise the following cooperative discussion thread into a "
            "clear, neutral paragraph that captures the key themes, concerns, "
            "and areas of agreement or disagreement. Be concise (max 200 words).\n\n"
            f"THREAD ID: {thread_id}\n"
            f"DISCUSSION:\n{thread_text[:6000] or '(no messages recorded yet)'}"
        )
        response = llm.invoke(
            [
                {"role": "system", "content": _role_prompt},
                {"role": "user", "content": user_msg},
            ]
        )
        raw = response.content.strip()
        summary = raw if raw else "Discussion pending summary."
    except Exception as exc:
        logger.warning("Ollama unavailable for summarise_discussion: %s", exc)
        summary = "Discussion pending summary."

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Summarise discussion thread",
        rationale=(
            "Members need a neutral summary to evaluate the proposal fairly "
            "(ICA Principle 5 — Education & Information)."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"thread_id": thread_id, "message_count": len(messages)},
    )
    return {
        **state,
        "discussion_summary": summary,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: Recommend process type ───────────────────────────────────────────


def recommend_process(state: ProposalState) -> dict[str, Any]:
    """LLM recommends the most appropriate process type.

    Falls back to 'consent' if the LLM is unavailable or returns an invalid
    process type.  'consent' is the cooperative governance default.
    """
    summary = state.get("discussion_summary") or "No summary available."

    process: str
    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        user_msg = (
            "Based on the discussion summary below, recommend exactly one of "
            "the nine supported process types:\n"
            "sense_check, advice, consent, consensus, choose, score, allocate, "
            "rank, time_poll\n\n"
            "Respond with a single JSON object — no markdown fences — in the "
            'exact format: {"process_type": "<value>", "rationale": "<why>"}\n\n'
            f"DISCUSSION SUMMARY:\n{summary[:3000]}"
        )
        response = llm.invoke(
            [
                {"role": "system", "content": _role_prompt},
                {"role": "user", "content": user_msg},
            ]
        )
        raw = response.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
            raw = "\n".join(lines).strip()
        parsed = json.loads(raw)
        candidate = str(parsed.get("process_type", "")).strip().lower()
        process = candidate if candidate in VALID_PROCESS_TYPES else "consent"
    except Exception as exc:
        logger.warning("Ollama unavailable for recommend_process: %s", exc)
        process = "consent"

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Recommend process type: {process}",
        rationale=(
            "Matching the process type to the decision's nature ensures "
            "democratic legitimacy (ICA Principle 2 — Democratic Member Control)."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"recommended_process": process, "summary_length": len(summary)},
    )
    return {
        **state,
        "recommended_process": process,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: Draft proposal text ───────────────────────────────────────────────


def draft_proposal_text(state: ProposalState) -> dict[str, Any]:
    """LLM drafts the proposal body and options list.

    Falls back to a template built from the discussion summary when the LLM is
    unavailable.
    """
    summary = state.get("discussion_summary") or "No summary available."
    process = state.get("recommended_process") or "consent"

    draft_body: str
    options: list[str]
    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        user_msg = (
            "Draft a cooperative proposal for member review. Use the Glass Box "
            "output format specified in your system prompt.\n\n"
            f"PROCESS TYPE: {process}\n"
            f"DISCUSSION SUMMARY:\n{summary[:4000]}\n\n"
            "Return a single JSON object with fields:\n"
            '  "draft_body": "<full proposal text>",\n'
            '  "options": ["<option A>", "<option B>", ...]'
        )
        response = llm.invoke(
            [
                {"role": "system", "content": _role_prompt},
                {"role": "user", "content": user_msg},
            ]
        )
        raw = response.content.strip()
        if raw.startswith("```"):
            lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # Try to extract JSON from the response
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(raw[start: end + 1])
            draft_body = str(parsed.get("draft_body") or "").strip()
            raw_opts = parsed.get("options")
            options = (
                [str(o) for o in raw_opts]
                if isinstance(raw_opts, list) and raw_opts
                else ["Approve", "Reject"]
            )
        else:
            raise ValueError("No JSON object found in LLM response")

        if not draft_body:
            raise ValueError("Empty draft_body from LLM")

    except Exception as exc:
        logger.warning("Ollama unavailable for draft_proposal_text: %s", exc)
        draft_body = (
            f"## Proposal\n\n"
            f"**Context**\n\n{summary}\n\n"
            f"**The Proposal**\n\n"
            f"Based on the discussion above, members are invited to deliberate "
            f"using the *{process}* process.\n\n"
            f"**How to Participate**\n\n"
            f"Review the discussion summary and cast your response before the "
            f"closing date. All members are encouraged to participate."
        )
        options = ["Approve", "Reject"]

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Draft proposal body and options",
        rationale=(
            "A clear, well-structured draft lowers participation barriers and "
            "ensures all members can make an informed decision "
            "(ICA Principle 5 — Education & Information)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"process": process, "options_count": len(options)},
    )
    return {
        **state,
        "draft_proposal": draft_body,
        "draft_options": options,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: HITL breakpoint — human edits draft ───────────────────────────────


def human_edit_proposal(state: ProposalState) -> dict[str, Any]:
    """No-op HITL breakpoint.

    The graph suspends here via interrupt_before=["human_edit_proposal"].
    A cooperative member calls POST /proposals/{id}/edit to supply their edits,
    then resumes the graph.  This node does nothing itself — the resume payload
    carries the updated draft fields.
    """
    action = AgentAction(
        agent_id=AGENT_ID,
        action="HITL breakpoint: awaiting human edit of proposal draft",
        rationale=(
            "Human review and editing of AI-drafted proposals is mandatory "
            "to preserve democratic member control "
            "(ICA Principle 2 — Democratic Member Control)."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={"thread_id": state.get("thread_id")},
    )
    return {
        **state,
        "requires_human_token": True,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 5: Open poll ─────────────────────────────────────────────────────────


def open_poll(state: ProposalState) -> dict[str, Any]:
    """Set closing_at to now + deliberation_proposal_default_days."""
    deadline = datetime.now(timezone.utc) + timedelta(
        days=settings.deliberation_proposal_default_days
    )
    closing_at = deadline.isoformat()

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Open poll: closes at {closing_at}",
        rationale=(
            f"Setting a {settings.deliberation_proposal_default_days}-day "
            "closing window gives all members a fair opportunity to participate "
            "(ICA Principle 2 — Democratic Member Control)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "closing_at": closing_at,
            "days": settings.deliberation_proposal_default_days,
        },
    )
    return {
        **state,
        "closing_at": closing_at,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 6: Notify participants ───────────────────────────────────────────────


def notify_participants(state: ProposalState) -> dict[str, Any]:
    """Format WebSocket event data for the router to broadcast.

    This node does NOT send the notification — it prepares the event payload
    and logs it.  The calling router is responsible for broadcasting via
    the WebSocket notifier after this node completes.
    """
    event = {
        "event_type": "proposal_opened",
        "thread_id": state.get("thread_id"),
        "recommended_process": state.get("recommended_process"),
        "closing_at": state.get("closing_at"),
        "draft_options": state.get("draft_options", []),
    }

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Prepare proposal_opened notification event",
        rationale=(
            "Notifying participants promotes transparency and ensures all "
            "eligible members can exercise their democratic rights before the "
            "closing deadline (ICA Principles 2 & 5)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload=event,
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_proposal_graph():
    """Compile the ProposalAgent LangGraph with HITL breakpoint."""
    g = StateGraph(ProposalState)

    g.add_node("summarise_discussion", summarise_discussion)
    g.add_node("recommend_process", recommend_process)
    g.add_node("draft_proposal_text", draft_proposal_text)
    g.add_node("human_edit_proposal", human_edit_proposal)
    g.add_node("open_poll", open_poll)
    g.add_node("notify_participants", notify_participants)

    g.set_entry_point("summarise_discussion")
    g.add_edge("summarise_discussion", "recommend_process")
    g.add_edge("recommend_process", "draft_proposal_text")
    g.add_edge("draft_proposal_text", "human_edit_proposal")
    g.add_edge("human_edit_proposal", "open_poll")
    g.add_edge("open_poll", "notify_participants")
    g.add_edge("notify_participants", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_edit_proposal"],
    )


proposal_graph = build_proposal_graph()
