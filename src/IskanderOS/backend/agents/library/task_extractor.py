"""
TaskAgent — Action item extraction with HITL confirmation.

Graph:
  extract_action_items → [HITL: confirm_assignments]
    → create_task_records → schedule_reminders → END

Compiled with interrupt_before=["confirm_assignments"] so the graph halts
after LLM extraction and resumes only after a human operator reviews and
confirms (or edits) the extracted tasks via the router.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.agents.core import load_prompt
from backend.agents.state import TaskExtractionState
from backend.config import settings
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "task-agent-v1"

_role_prompt = load_prompt("prompt_task_extract.txt")

_EXTRACT_SYSTEM = (
    "You are the Iskander OS Task Agent. "
    "Extract structured action items from the text. "
    "Return ONLY a valid JSON object with a 'tasks' array. "
    "Each task must have: title (string, starts with verb), "
    "suggested_assignee (string), due_date (YYYY-MM-DD or 'ongoing'). "
    "If no clear commitments are found, return {\"tasks\": []}. "
    "No markdown fences, no preamble."
)


# ── Node 1: Extract action items via LLM ──────────────────────────────────────


def extract_action_items(state: TaskExtractionState) -> dict[str, Any]:
    """LLM parses source_text for action item commitments.

    Fallback on LLM failure or empty source: returns empty extracted_tasks list.
    """
    source_text = state.get("source_text") or ""

    if not source_text.strip():
        action = AgentAction(
            agent_id=AGENT_ID,
            action="Skip extraction — source text is empty",
            rationale="No text provided; no tasks can be extracted.",
            ethical_impact=EthicalImpactLevel.LOW,
            payload={"source_length": 0},
        )
        return {
            **state,
            "extracted_tasks": [],
            "action_log": state.get("action_log", []) + [action.model_dump()],
        }

    tasks: list[dict[str, Any]] = []

    try:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        response = llm.invoke(
            [
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Extract action items from this text:\n\n{source_text[:6000]}"
                    ),
                },
            ]
        )
        tasks = _parse_tasks(response.content)
    except Exception as exc:
        logger.warning("Ollama unavailable for task extraction: %s", exc)
        tasks = []

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Extract action items: found {len(tasks)} task(s)",
        rationale=(
            "Scanning source text for explicit member commitments per "
            "ICA Principle 2 (Democratic Member Control). "
            "Only confirmed commitments are extracted."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={
            "thread_id": state.get("thread_id"),
            "outcome_id": state.get("outcome_id"),
            "source_length": len(source_text),
            "tasks_found": len(tasks),
        },
    )

    return {
        **state,
        "extracted_tasks": tasks,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 2: HITL breakpoint — human reviews extracted tasks ──────────────────


def confirm_assignments(state: TaskExtractionState) -> dict[str, Any]:
    """No-op HITL breakpoint.

    The graph halts here (interrupt_before=["confirm_assignments"]).
    The calling router resumes the graph after a human operator has reviewed,
    edited, or approved the extracted_tasks. The router sets confirmed_tasks
    in the resumed state before calling graph.invoke() again.
    """
    return state


# ── Node 3: Create task records ───────────────────────────────────────────────


def create_task_records(state: TaskExtractionState) -> dict[str, Any]:
    """Package confirmed (or fallback: extracted) tasks for router to INSERT.

    The agent does NOT write to the database directly. The router is responsible
    for persisting the task records after this node runs.

    Uses confirmed_tasks if non-empty (human reviewed), otherwise falls back to
    extracted_tasks (LLM output passed through without human edit).
    """
    confirmed = state.get("confirmed_tasks") or []
    extracted = state.get("extracted_tasks") or []

    final_tasks = confirmed if confirmed else extracted

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Create task records: {len(final_tasks)} task(s) packaged",
        rationale=(
            "Human-confirmed tasks (or LLM-extracted tasks if none confirmed) "
            "packaged for router to persist as accountability records. "
            "Supports democratic member control (ICA Principle 2)."
        ),
        ethical_impact=EthicalImpactLevel.MEDIUM,
        payload={
            "source": "confirmed" if confirmed else "extracted_fallback",
            "task_count": len(final_tasks),
            "task_titles": [t.get("title", "") for t in final_tasks],
        },
    )

    return {
        **state,
        "confirmed_tasks": final_tasks,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Schedule reminders (stub) ────────────────────────────────────────


def schedule_reminders(state: TaskExtractionState) -> dict[str, Any]:
    """Stub: log due dates for future notification integration.

    Formats reminder data into the action_log so the router can wire up
    notification delivery (email, Matrix, ActivityPub) in a future phase.
    Does NOT dispatch notifications — the router handles all side-effects.
    """
    tasks = state.get("confirmed_tasks") or []

    reminder_data = []
    for task in tasks:
        due = task.get("due_date")
        if due:
            reminder_data.append(
                {
                    "task_title": task.get("title", "Untitled"),
                    "assignee": task.get("suggested_assignee", "Unassigned"),
                    "due_date": due,
                    "reminder_queued": True,
                }
            )
            logger.info(
                "Reminder queued for '%s' → %s (due %s)",
                task.get("title"),
                task.get("suggested_assignee"),
                due,
            )

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Schedule reminders: {len(reminder_data)} reminder(s) queued",
        rationale=(
            "Logging due dates for future notification delivery. "
            "Members need timely reminders to fulfil their commitments "
            "(ICA Principle 5 — Education, Training & Information)."
        ),
        ethical_impact=EthicalImpactLevel.LOW,
        payload={"reminders": reminder_data},
    )

    return {
        **state,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_task_graph():
    """Compile the TaskAgent LangGraph with HITL interrupt at confirm_assignments."""
    g = StateGraph(TaskExtractionState)

    g.add_node("extract_action_items", extract_action_items)
    g.add_node("confirm_assignments", confirm_assignments)
    g.add_node("create_task_records", create_task_records)
    g.add_node("schedule_reminders", schedule_reminders)

    g.set_entry_point("extract_action_items")
    g.add_edge("extract_action_items", "confirm_assignments")
    g.add_edge("confirm_assignments", "create_task_records")
    g.add_edge("create_task_records", "schedule_reminders")
    g.add_edge("schedule_reminders", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["confirm_assignments"],
    )


task_graph = build_task_graph()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_tasks(text: str) -> list[dict[str, Any]]:
    """Best-effort JSON task array extraction from LLM output."""
    cleaned = text.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Try to parse the whole response as JSON object with 'tasks' key
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "tasks" in obj:
            tasks = obj["tasks"]
            return tasks if isinstance(tasks, list) else []
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass

    # Fall back to extracting a JSON array
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start : end + 1])
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            pass

    return []
