"""
DiscussionAgent — Precedent-aware thread context drafting with HITL.

Drafts rich discussion thread context by searching democratic precedents
and using an LLM.  A HITL gate lets a human edit the AI's draft before
it is published to the deliberation platform (Loomio / ActivityPub).

Graph:
  receive_prompt → research_precedents → draft_thread_context
    → [HITL: human_edit_context]
    → publish_thread → suggest_invitees → notify_members → END

Compiled with interrupt_before=["human_edit_context"] so the graph halts
for human review of the AI draft before any publishing side-effect occurs.
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import DiscussionState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "discussion-agent-v1"

# Load prompt once at import time (cached by load_prompt).
_role_prompt = load_prompt("prompt_discussion.txt")


# ── Node 1: Receive & validate the raw discussion prompt ─────────────────────


def receive_prompt(state: DiscussionState) -> dict[str, Any]:
    """Validate that raw_prompt is non-empty before proceeding."""
    raw = (state.get("raw_prompt") or "").strip()

    if not raw:
        action = AgentAction(
            agent_id=AGENT_ID,
            action="REJECT — empty discussion prompt",
            rationale=(
                "A discussion thread cannot be created without a topic. "
                "The raw_prompt field is empty or whitespace-only."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"raw_prompt": state.get("raw_prompt")},
        )
        return {
            **state,
            "error": "raw_prompt must be a non-empty string.",
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Receive discussion prompt ({len(raw)} chars)",
        rationale=(
            "ICA Principle 2 (Democratic Member Control): every member has the "
            "right to raise topics for cooperative deliberation. "
            "Prompt validated and accepted for processing."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"prompt_length": len(raw)},
    )
    return {
        **state,
        "raw_prompt": raw,
        "error": None,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2: Search democratic precedents ─────────────────────────────────────


def research_precedents(state: DiscussionState) -> dict[str, Any]:
    """Query the vector store for relevant past democratic decisions.

    Returns an empty list on any failure so the graph can continue with
    the fallback 'no precedents' message.
    """
    raw = state.get("raw_prompt") or ""
    docs: list[dict[str, Any]] = []

    try:
        from backend.memory.precedent_retriever import format_precedent_block  # noqa: PLC0415
        block = format_precedent_block(raw)
        # Store the formatted block as a single doc entry for prompt injection.
        docs = [{"content": block, "source": "pgvector"}]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Precedent retrieval unavailable: %s", exc)
        docs = []

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Research precedents for prompt (found {len(docs)} block(s))",
        rationale=(
            "ICA Principle 2 (Democratic Member Control): past democratic "
            "decisions are binding precedent. Searching for relevant prior votes "
            "to ground the discussion draft in cooperative history."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"precedent_blocks": len(docs)},
    )
    return {
        **state,
        "precedent_docs": docs,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 3: LLM-powered discussion draft ─────────────────────────────────────


def draft_thread_context(state: DiscussionState) -> dict[str, Any]:
    """Call the LLM to produce a facilitative discussion context draft.

    Falls back to returning raw_prompt unchanged if Ollama is unavailable.
    Truncates to settings.deliberation_context_max_tokens characters.
    """
    raw = state.get("raw_prompt") or ""
    precedent_docs = state.get("precedent_docs") or []

    # Build precedent block string for prompt substitution.
    if precedent_docs:
        precedent_block = precedent_docs[0].get("content", "")
    else:
        precedent_block = (
            "No democratic precedents available yet. The cooperative has not "
            "recorded any binding human votes."
        )

    # Substitute placeholders in the role prompt.
    system_prompt = _role_prompt.replace("{PERSONA_BLOCK}", "(development mode — no profile loaded)")
    system_prompt = system_prompt.replace("{PRECEDENT_BLOCK}", precedent_block)
    system_prompt = system_prompt.replace(
        "{MAX_TOKENS}", str(settings.deliberation_context_max_tokens)
    )

    draft: str | None = None

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Please draft a discussion thread for this topic:\n\n{raw}"),
        ])
        raw_text = response.content or ""

        # Try to extract discussion_draft from Glass Box JSON response.
        import json  # noqa: PLC0415
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                parsed = json.loads(cleaned[start:end + 1])
                draft = parsed.get("discussion_draft") or cleaned
            except json.JSONDecodeError:
                draft = cleaned
        else:
            draft = cleaned

    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM unavailable for discussion draft, using fallback: %s", exc)
        draft = raw  # Fallback: return raw_prompt unchanged.

    # Truncate to configured max tokens (treated as max chars).
    max_chars = settings.deliberation_context_max_tokens
    if draft and len(draft) > max_chars:
        draft = draft[:max_chars]

    action = AgentAction(
        agent_id=AGENT_ID,
        action="Draft discussion thread context",
        rationale=(
            "ICA Principle 5 (Education, Training & Information): the AI "
            "produces a neutral, facilitative draft to help members deliberate "
            "with full context. A human will review and edit before publishing."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={"draft_length": len(draft) if draft else 0, "used_fallback": draft == raw},
    )
    return {
        **state,
        "draft_context": draft,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: HITL breakpoint — human edits the draft ─────────────────────────


def human_edit_context(state: DiscussionState) -> dict[str, Any]:
    """No-op HITL breakpoint.

    The graph halts here (interrupt_before=["human_edit_context"]).
    The calling router resumes the graph by invoking graph.invoke() with
    the human-edited draft_context in the updated state.
    """
    return state


# ── Node 5: Publish thread ────────────────────────────────────────────────────


def publish_thread(state: DiscussionState) -> dict[str, Any]:
    """Package the approved draft for router to publish.

    Agent does NOT write to the Loomio API — the calling router handles
    all external side-effects to keep agents stateless and testable.
    """
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Package discussion thread for publication",
        rationale=(
            "Human has reviewed and approved the draft context. "
            "Packaging for router to publish via Loomio / ActivityPub."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "thread_id": state.get("thread_id"),
            "draft_length": len(state.get("draft_context") or ""),
        },
    )
    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 6: Suggest invitees ──────────────────────────────────────────────────


def suggest_invitees(state: DiscussionState) -> dict[str, Any]:
    """Return empty invitee list.

    Member resolution requires a live DB query, which is handled by the
    calling router after the graph completes.
    """
    return {**state, "suggested_invitees": []}


# ── Node 7: Notify members ────────────────────────────────────────────────────


def notify_members(state: DiscussionState) -> dict[str, Any]:
    """Format WebSocket event data for the router to broadcast."""
    event_data = {
        "event": "discussion.thread.published",
        "thread_id": state.get("thread_id"),
        "invitees": state.get("suggested_invitees", []),
    }
    action = AgentAction(
        agent_id=AGENT_ID,
        action="Prepare member notification payload",
        rationale=(
            "ICA Principle 2 (Democratic Member Control): all members must be "
            "notified of new discussion threads so they can participate equally."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload=event_data,
    )
    return {
        **state,
        "engagement_report": event_data,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_discussion_graph():
    """Compile the DiscussionAgent LangGraph with HITL interrupt.

    Graph flow:
      receive_prompt → research_precedents → draft_thread_context
        → [HITL: human_edit_context]
        → publish_thread → suggest_invitees → notify_members → END

    The graph halts at human_edit_context so a human can review and edit
    the AI's draft before it is published to the deliberation platform.
    """
    g = StateGraph(DiscussionState)

    g.add_node("receive_prompt", receive_prompt)
    g.add_node("research_precedents", research_precedents)
    g.add_node("draft_thread_context", draft_thread_context)
    g.add_node("human_edit_context", human_edit_context)
    g.add_node("publish_thread", publish_thread)
    g.add_node("suggest_invitees", suggest_invitees)
    g.add_node("notify_members", notify_members)

    g.set_entry_point("receive_prompt")
    g.add_edge("receive_prompt", "research_precedents")
    g.add_edge("research_precedents", "draft_thread_context")
    g.add_edge("draft_thread_context", "human_edit_context")
    g.add_edge("human_edit_context", "publish_thread")
    g.add_edge("publish_thread", "suggest_invitees")
    g.add_edge("suggest_invitees", "notify_members")
    g.add_edge("notify_members", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_edit_context"],
    )


discussion_graph = build_discussion_graph()
