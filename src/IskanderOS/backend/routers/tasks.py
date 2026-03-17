"""
tasks.py — Phase 16: Async Task Status Polling Router.

Endpoints:
  GET /tasks/{task_id}   — Poll status and result for a queued agent invocation.
  GET /tasks             — List all known task IDs (most recent first).

Used by:
  - Streamlit dashboard (polls every 2 s while task is running).
  - Matrix bot (`!status <task_id>` command).
  - External integrations that call any router with `?async=true`.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.core.llm_queue_manager import AsyncAgentQueue, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── GET /tasks/{task_id} ──────────────────────────────────────────────────────

@router.get("/{task_id}", status_code=status.HTTP_200_OK)
async def get_task(task_id: str) -> dict[str, Any]:
    """
    Poll the status and (when complete) result of a queued agent invocation.

    Returns:
      - status: queued | running | complete | error
      - result: the final LangGraph state dict (only when status=complete)
      - error: error message string (only when status=error)
      - queue_depth: current queue depth (informational)
    """
    queue = AsyncAgentQueue.get_instance()
    task_status = queue.get_status(task_id)

    if task_status is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    response: dict[str, Any] = {
        "task_id":     task_id,
        "status":      task_status.value,
        "queue_depth": queue.queue_depth(),
    }

    if task_status == TaskStatus.COMPLETE:
        response["result"] = queue.get_result(task_id)

    elif task_status == TaskStatus.ERROR:
        response["error"] = queue.get_error(task_id)

    return response


# ── GET /tasks ────────────────────────────────────────────────────────────────

@router.get("", status_code=status.HTTP_200_OK)
async def list_tasks() -> dict[str, Any]:
    """
    Return all known task IDs and their current statuses.
    Intended for operator dashboards — not paginated in stub mode.
    """
    queue = AsyncAgentQueue.get_instance()
    # Access internal state directly (operator endpoint — auth added in prod).
    tasks = [
        {"task_id": tid, "status": st.value}
        for tid, st in queue._statuses.items()
    ]
    return {
        "tasks":       tasks,
        "queue_depth": queue.queue_depth(),
        "total":       len(tasks),
    }
