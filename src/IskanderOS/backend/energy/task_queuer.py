"""
task_queuer.py — Priority queue for deferred tasks (Phase 2 Energy Gate).

When energy drops to YELLOW or RED, non-critical tasks are enqueued rather
than executed.  When the node transitions back to GREEN, ``process_queue()``
drains the queue in priority order.

Singleton: obtain via ``TaskQueuer.get_instance()``.
"""
from __future__ import annotations

import heapq
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.energy.hearth_interface import EnergyLevel, HearthInterface

logger = logging.getLogger(__name__)


@dataclass(order=True)
class _QueueEntry:
    """Internal heap entry.  Lower ``priority`` value = higher urgency."""
    priority: int
    # Fields below are excluded from ordering.
    task_id: str = field(compare=False)
    callback: Callable[..., Any] = field(compare=False)
    is_critical: bool = field(compare=False)


class TaskQueuer:
    """
    Energy-aware priority queue for deferred task execution.

    Singleton: obtain via ``TaskQueuer.get_instance()``.
    """

    _instance: TaskQueuer | None = None

    def __init__(self) -> None:
        self._heap: list[_QueueEntry] = []

    @classmethod
    def get_instance(cls) -> TaskQueuer:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton so tests start fresh."""
        cls._instance = None

    # ── Public API ──────────────────────────────────────────────────────────────

    def enqueue(
        self,
        task_id: str,
        callback: Callable[..., Any],
        priority: int = 10,
        is_critical: bool = False,
    ) -> str:
        """
        Add a task to the deferred queue.

        Parameters
        ----------
        task_id:
            Human-readable identifier for the task.
        callback:
            Zero-argument callable to invoke when the task is processed.
        priority:
            Lower value = higher urgency (``heapq`` is a min-heap).
        is_critical:
            If ``True`` the task will be processed even at YELLOW level.

        Returns
        -------
        str
            A unique queue entry ID (``task_id`` may not be unique across
            multiple enqueue calls, but the returned ID always is).
        """
        entry_id = f"{task_id}:{uuid.uuid4().hex[:8]}"
        entry = _QueueEntry(
            priority=priority,
            task_id=entry_id,
            callback=callback,
            is_critical=is_critical,
        )
        heapq.heappush(self._heap, entry)
        logger.info(
            "Task enqueued: %s (priority=%d, critical=%s)",
            entry_id, priority, is_critical,
        )
        return entry_id

    def process_queue(self) -> int:
        """
        Process pending tasks if energy level allows.

        Called on GREEN transitions (or manually).  Critical tasks are also
        processed at YELLOW.

        Returns
        -------
        int
            Number of tasks successfully processed.
        """
        level = HearthInterface.get_instance().get_state()
        processed = 0
        remaining: list[_QueueEntry] = []

        while self._heap:
            entry = heapq.heappop(self._heap)

            # Decide whether this entry can run at the current level.
            can_run = False
            if level == EnergyLevel.GREEN:
                can_run = True
            elif level == EnergyLevel.YELLOW and entry.is_critical:
                can_run = True
            # RED: nothing runs via the queue.

            if can_run:
                try:
                    entry.callback()
                    processed += 1
                    logger.info("Task processed: %s", entry.task_id)
                except Exception:
                    logger.exception("Task failed: %s", entry.task_id)
            else:
                remaining.append(entry)

        # Re-heapify the entries we couldn't run.
        self._heap = remaining
        heapq.heapify(self._heap)

        logger.info(
            "Queue drain complete: processed=%d, remaining=%d",
            processed, len(self._heap),
        )
        return processed

    def get_pending(self) -> list[dict[str, Any]]:
        """Return a snapshot of all pending deferred tasks."""
        return [
            {
                "task_id": entry.task_id,
                "priority": entry.priority,
                "is_critical": entry.is_critical,
            }
            for entry in sorted(self._heap)
        ]

    def flush(self) -> int:
        """
        Discard all pending tasks (emergency cleanup).

        Returns
        -------
        int
            Number of tasks discarded.
        """
        count = len(self._heap)
        self._heap.clear()
        logger.warning("Task queue flushed: %d tasks discarded", count)
        return count
