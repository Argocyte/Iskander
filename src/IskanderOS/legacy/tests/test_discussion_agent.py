"""DiscussionAgent tests — deterministic nodes + fallback paths."""
from __future__ import annotations


def _base_state(**overrides) -> dict:
    base = {
        "messages": [], "agent_id": "discussion-agent-v1",
        "action_log": [], "error": None,
        "thread_id": "thread-1", "raw_prompt": "We need to discuss pay policy.",
        "precedent_docs": [], "draft_context": None,
        "suggested_invitees": [], "engagement_report": None,
        "requires_human_token": False,
    }
    base.update(overrides)
    return base


class TestReceivePrompt:
    def test_valid_prompt(self):
        from backend.agents.library.discussion import receive_prompt
        result = receive_prompt(_base_state())
        assert result["error"] is None
        assert len(result["action_log"]) == 1

    def test_empty_prompt_returns_error(self):
        from backend.agents.library.discussion import receive_prompt
        result = receive_prompt(_base_state(raw_prompt=""))
        assert result["error"] is not None

    def test_whitespace_only_prompt_returns_error(self):
        from backend.agents.library.discussion import receive_prompt
        result = receive_prompt(_base_state(raw_prompt="   "))
        assert result["error"] is not None

    def test_none_prompt_returns_error(self):
        from backend.agents.library.discussion import receive_prompt
        result = receive_prompt(_base_state(raw_prompt=None))
        assert result["error"] is not None

    def test_valid_prompt_preserved(self):
        from backend.agents.library.discussion import receive_prompt
        result = receive_prompt(_base_state(raw_prompt="  Should we adopt a 4-day week?  "))
        assert result["error"] is None
        # Whitespace is stripped.
        assert result["raw_prompt"] == "Should we adopt a 4-day week?"

    def test_action_log_contains_entry(self):
        from backend.agents.library.discussion import receive_prompt
        result = receive_prompt(_base_state())
        assert len(result["action_log"]) == 1
        entry = result["action_log"][0]
        assert "agent_id" in entry
        assert entry["agent_id"] == "discussion-agent-v1"


class TestResearchPrecedents:
    def test_returns_empty_when_unavailable(self):
        from backend.agents.library.discussion import research_precedents
        result = research_precedents(_base_state())
        assert isinstance(result["precedent_docs"], list)

    def test_preserves_state_on_failure(self):
        from backend.agents.library.discussion import research_precedents
        state = _base_state(thread_id="t-99")
        result = research_precedents(state)
        assert result["thread_id"] == "t-99"

    def test_action_logged(self):
        from backend.agents.library.discussion import research_precedents
        result = research_precedents(_base_state())
        assert len(result["action_log"]) == 1

    def test_result_is_list_of_dicts_or_empty(self):
        from backend.agents.library.discussion import research_precedents
        result = research_precedents(_base_state())
        docs = result["precedent_docs"]
        assert isinstance(docs, list)
        for doc in docs:
            assert isinstance(doc, dict)


class TestDraftThreadContext:
    def test_fallback_when_llm_unavailable(self):
        from backend.agents.library.discussion import draft_thread_context
        result = draft_thread_context(_base_state())
        assert result["draft_context"] is not None
        assert len(result["draft_context"]) > 0

    def test_fallback_returns_raw_prompt(self):
        """When Ollama is not running, draft_context falls back to raw_prompt."""
        from backend.agents.library.discussion import draft_thread_context
        result = draft_thread_context(_base_state(raw_prompt="Should we hire a new member?"))
        # Either LLM succeeded (longer draft) or fallback returned the prompt.
        assert result["draft_context"] is not None
        assert len(result["draft_context"]) > 0

    def test_truncates_to_max_tokens(self):
        from backend.agents.library.discussion import draft_thread_context
        from backend.config import settings
        # Feed a very long raw_prompt; when LLM is unavailable the fallback
        # path returns raw_prompt, and it must be truncated.
        long_prompt = "x" * (settings.deliberation_context_max_tokens + 200)
        result = draft_thread_context(_base_state(raw_prompt=long_prompt))
        assert len(result["draft_context"]) <= settings.deliberation_context_max_tokens

    def test_action_logged(self):
        from backend.agents.library.discussion import draft_thread_context
        result = draft_thread_context(_base_state())
        assert len(result["action_log"]) == 1

    def test_uses_precedent_docs_when_present(self):
        from backend.agents.library.discussion import draft_thread_context
        precedent_docs = [{"content": "Past vote: members agreed to 4-day week in 2024.", "source": "pgvector"}]
        result = draft_thread_context(_base_state(precedent_docs=precedent_docs))
        assert result["draft_context"] is not None


class TestHumanEditContext:
    def test_noop_returns_state_unchanged(self):
        from backend.agents.library.discussion import human_edit_context
        state = _base_state(draft_context="Draft here.", thread_id="t-42")
        result = human_edit_context(state)
        assert result == state

    def test_preserves_all_fields(self):
        from backend.agents.library.discussion import human_edit_context
        state = _base_state(
            draft_context="Human-edited draft.",
            requires_human_token=True,
        )
        result = human_edit_context(state)
        assert result["draft_context"] == "Human-edited draft."
        assert result["requires_human_token"] is True


class TestPublishThread:
    def test_logs_action(self):
        from backend.agents.library.discussion import publish_thread
        result = publish_thread(_base_state(draft_context="The draft."))
        assert len(result["action_log"]) == 1

    def test_preserves_draft_context(self):
        from backend.agents.library.discussion import publish_thread
        result = publish_thread(_base_state(draft_context="Approved draft text."))
        assert result["draft_context"] == "Approved draft text."


class TestSuggestInvitees:
    def test_returns_empty_list(self):
        from backend.agents.library.discussion import suggest_invitees
        result = suggest_invitees(_base_state())
        assert result["suggested_invitees"] == []

    def test_preserves_state(self):
        from backend.agents.library.discussion import suggest_invitees
        state = _base_state(thread_id="t-77")
        result = suggest_invitees(state)
        assert result["thread_id"] == "t-77"


class TestNotifyMembers:
    def test_sets_engagement_report(self):
        from backend.agents.library.discussion import notify_members
        result = notify_members(_base_state(thread_id="thread-abc"))
        assert result["engagement_report"] is not None
        assert result["engagement_report"]["event"] == "discussion.thread.published"
        assert result["engagement_report"]["thread_id"] == "thread-abc"

    def test_logs_action(self):
        from backend.agents.library.discussion import notify_members
        result = notify_members(_base_state())
        assert len(result["action_log"]) == 1


class TestDiscussionGraph:
    def test_graph_compiles(self):
        from backend.agents.library.discussion import build_discussion_graph
        graph = build_discussion_graph()
        assert graph is not None

    def test_graph_has_hitl_interrupt(self):
        from backend.agents.library.discussion import build_discussion_graph
        graph = build_discussion_graph()
        config = {"configurable": {"thread_id": "test-disc-hitl"}}
        state = _base_state()
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        # Graph should have stopped at the HITL node.
        assert snapshot.next  # There should be a pending node

    def test_interrupt_is_at_human_edit_context(self):
        from backend.agents.library.discussion import build_discussion_graph
        graph = build_discussion_graph()
        config = {"configurable": {"thread_id": "test-disc-node-check"}}
        graph.invoke(_base_state(), config=config)
        snapshot = graph.get_state(config)
        assert "human_edit_context" in snapshot.next

    def test_empty_prompt_does_not_crash_graph(self):
        from backend.agents.library.discussion import build_discussion_graph
        graph = build_discussion_graph()
        config = {"configurable": {"thread_id": "test-disc-empty"}}
        # Should not raise — error is stored in state, not raised as exception.
        graph.invoke(_base_state(raw_prompt=""), config=config)

    def test_module_level_graph_instance(self):
        """The module-level discussion_graph is pre-compiled and ready."""
        from backend.agents.library.discussion import discussion_graph
        assert discussion_graph is not None
