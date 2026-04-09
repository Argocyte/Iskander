"""TaskAgent tests — action item extraction + HITL confirmation."""
from __future__ import annotations


def _base_state(**overrides) -> dict:
    base = {
        "messages": [], "agent_id": "task-agent-v1",
        "action_log": [], "error": None,
        "source_text": "Alice should review the budget by Friday. Bob will update the website.",
        "thread_id": "thread-1", "outcome_id": "outcome-1",
        "extracted_tasks": [], "confirmed_tasks": [],
        "requires_human_token": False,
    }
    base.update(overrides)
    return base


class TestExtractActionItems:
    def test_fallback_returns_empty_list(self):
        from backend.agents.library.task_extractor import extract_action_items
        result = extract_action_items(_base_state())
        # No Ollama running — falls back to empty list
        assert isinstance(result["extracted_tasks"], list)

    def test_empty_source_returns_empty(self):
        from backend.agents.library.task_extractor import extract_action_items
        result = extract_action_items(_base_state(source_text=""))
        assert result["extracted_tasks"] == []


class TestCreateTaskRecords:
    def test_uses_confirmed_tasks_if_available(self):
        from backend.agents.library.task_extractor import create_task_records
        confirmed = [{"title": "Review budget", "suggested_assignee": "alice", "due_date": "2026-04-10"}]
        result = create_task_records(_base_state(confirmed_tasks=confirmed))
        # Should use confirmed_tasks, not extracted_tasks
        assert len(result["confirmed_tasks"]) == 1

    def test_falls_back_to_extracted(self):
        from backend.agents.library.task_extractor import create_task_records
        extracted = [{"title": "Update website", "suggested_assignee": "bob"}]
        result = create_task_records(_base_state(extracted_tasks=extracted, confirmed_tasks=[]))
        assert len(result["confirmed_tasks"]) == 1


class TestScheduleReminders:
    def test_logs_reminder_data(self):
        from backend.agents.library.task_extractor import schedule_reminders
        tasks = [{"title": "T1", "due_date": "2026-04-10"}]
        result = schedule_reminders(_base_state(confirmed_tasks=tasks))
        assert len(result["action_log"]) == 1


class TestTaskGraph:
    def test_graph_compiles(self):
        from backend.agents.library.task_extractor import build_task_graph
        graph = build_task_graph()
        assert graph is not None

    def test_graph_interrupts_at_hitl(self):
        from backend.agents.library.task_extractor import build_task_graph
        graph = build_task_graph()
        config = {"configurable": {"thread_id": "test-task-hitl"}}
        state = _base_state()
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        assert snapshot.next  # Should pause at confirm_assignments
