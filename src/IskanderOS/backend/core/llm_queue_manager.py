"""
llm_queue_manager.py — Phase 16: LLM Concurrency Queue.

Wraps LangGraph graph.invoke() calls in an asyncio queue so that
CPU-bound Ollama inference on a single-GPU / CPU-only node never
blocks the FastAPI event loop. A single background worker serialises
all LLM calls; callers receive a task_id immediately (HTTP 202).

Design:
  ┌──────────────┐   enqueue()   ┌──────────────┐   invoke()   ┌──────────────┐
  │ FastAPI route │ ────────────► │ AsyncAgentQueue │ ──────────► │ LangGraph /  │
  │ (async)      │ ◄─ task_id ── │  asyncio.Queue  │ ◄── result ─ │ Ollama       │
  └──────────────┘               └──────────────┘               └──────────────┘
                                        │
                                        ▼ status events
                                  WebSocketNotifier

Queue overflow policy:
  depth >= max_depth → HTTP 503, {"error": "queue_full", "queue_length": N}
  Callers check via get_status(task_id) or GET /tasks/{task_id}.

Thread safety:
  LangGraph checkpoints are synchronous (MemorySaver uses threading locks).
  Each invoke() runs in asyncio.to_thread() to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    QUEUED   = "queued"
    RUNNING  = "running"
    COMPLETE = "complete"
    ERROR    = "error"


@dataclass
class TaskHandle:
    task_id:        str
    queue_position: int
    status_url:     str


@dataclass
class _QueueItem:
    task_id: str
    graph:   Any           # compiled LangGraph StateGraph
    state:   dict[str, Any]
    config:  dict[str, Any]


class AsyncAgentQueue:
    """
    Singleton LLM concurrency queue.

    Usage:
        queue = AsyncAgentQueue.get_instance()
        handle = await queue.enqueue(graph, state, config)
        # Later:
        status = queue.get_status(handle.task_id)
        result = queue.get_result(handle.task_id)
    """

    _instance: AsyncAgentQueue | None = None

    def __init__(self, max_depth: int = 50):
        self._max_depth  = max_depth
        self._queue:     asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._statuses:  dict[str, TaskStatus]     = {}
        self._results:   dict[str, Any]            = {}
        self._errors:    dict[str, str]            = {}
        self._worker_task: asyncio.Task | None     = None
        # Lazy import to avoid circular dependency at module load time.
        self._notifier = None

    @classmethod
    def get_instance(cls) -> AsyncAgentQueue:
        if cls._instance is None:
            from backend.config import settings
            cls._instance = cls(max_depth=settings.agent_queue_max_depth)
        return cls._instance

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background worker. Call from FastAPI startup event."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("AsyncAgentQueue worker started (max_depth=%d)", self._max_depth)

    def stop(self) -> None:
        """Cancel the background worker. Call from FastAPI shutdown event."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            logger.info("AsyncAgentQueue worker stopped.")

    # ── Public API ────────────────────────────────────────────────────────────

    async def enqueue(
        self,
        graph:  Any,
        state:  dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> TaskHandle:
        """
        Enqueue a graph invocation. Returns immediately with a TaskHandle.

        Raises:
            QueueFullError if the queue is at max_depth.
        """
        current_depth = self._queue.qsize()
        if current_depth >= self._max_depth:
            await self._notify({
                "event":        "queue_rejected",
                "queue_length": current_depth,
                "max_depth":    self._max_depth,
            })
            raise QueueFullError(current_depth, self._max_depth)

        task_id  = str(uuid.uuid4())
        position = current_depth + 1
        item     = _QueueItem(
            task_id=task_id,
            graph=graph,
            state=state,
            config=config or {},
        )

        self._statuses[task_id] = TaskStatus.QUEUED
        await self._queue.put(item)

        logger.debug("Task %s queued at position %d", task_id, position)
        await self._notify({
            "task_id":        task_id,
            "event":          "queued",
            "queue_position": position,
        })

        return TaskHandle(
            task_id=task_id,
            queue_position=position,
            status_url=f"/tasks/{task_id}",
        )

    def get_status(self, task_id: str) -> TaskStatus | None:
        return self._statuses.get(task_id)

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        return self._results.get(task_id)

    def get_error(self, task_id: str) -> str | None:
        return self._errors.get(task_id)

    def queue_depth(self) -> int:
        return self._queue.qsize()

    # ── Background Worker ─────────────────────────────────────────────────────

    async def _worker(self) -> None:
        """
        Single-worker coroutine. Runs for the lifetime of the process.
        Serialises all LangGraph/Ollama calls so CPU-only inference is not
        over-subscribed. Each invoke() is dispatched to a thread pool so
        that synchronous LangGraph checkpoints do not block the event loop.
        """
        logger.info("AsyncAgentQueue._worker() running")
        while True:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                break

            task_id = item.task_id
            self._statuses[task_id] = TaskStatus.RUNNING
            await self._notify({
                "task_id": task_id,
                "event":   "running",
            })

            try:
                result = await asyncio.to_thread(
                    item.graph.invoke, item.state, item.config
                )
                self._results[task_id]  = result
                self._statuses[task_id] = TaskStatus.COMPLETE
                await self._notify({
                    "task_id": task_id,
                    "event":   "task_complete",
                    "agent_id": item.state.get("agent_id", "unknown"),
                })
                logger.debug("Task %s complete", task_id)

            except Exception as exc:
                self._errors[task_id]   = str(exc)
                self._statuses[task_id] = TaskStatus.ERROR
                await self._notify({
                    "task_id": task_id,
                    "event":   "error",
                    "detail":  str(exc),
                })
                logger.exception("Task %s failed: %s", task_id, exc)

            finally:
                self._queue.task_done()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _notify(self, event: dict[str, Any]) -> None:
        """Forward event to WebSocketNotifier if available."""
        try:
            if self._notifier is None:
                from backend.api.websocket_notifier import WebSocketNotifier
                self._notifier = WebSocketNotifier.get_instance()
            await self._notifier.broadcast(event)
        except Exception:
            pass  # Notifier unavailable — degrade silently.


class QueueFullError(Exception):
    """Raised when the queue has reached max_depth."""

    def __init__(self, current: int, max_depth: int):
        self.current   = current
        self.max_depth = max_depth
        super().__init__(f"Agent queue full ({current}/{max_depth})")
