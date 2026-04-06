"""ProposalAgent tests — process recommendation + drafting."""
from __future__ import annotations


def _base_state(**overrides) -> dict:
    base = {
        "messages": [], "agent_id": "proposal-agent-v1",
        "action_log": [], "error": None,
        "thread_id": "thread-1", "discussion_summary": None,
        "recommended_process": None, "draft_proposal": None,
        "draft_options": [], "closing_at": None,
        "requires_human_token": False,
    }
    base.update(overrides)
    return base


class TestSummariseDiscussion:
    def test_fallback_on_llm_failure(self):
        from backend.agents.library.proposal import summarise_discussion
        result = summarise_discussion(_base_state())
        assert result["discussion_summary"] is not None

    def test_summary_logged_in_action_log(self):
        from backend.agents.library.proposal import summarise_discussion
        result = summarise_discussion(_base_state())
        assert len(result["action_log"]) == 1
        assert "summarise" in result["action_log"][0]["action"].lower()

    def test_error_cleared_on_success(self):
        from backend.agents.library.proposal import summarise_discussion
        result = summarise_discussion(_base_state(error="old error"))
        assert result["error"] is None


class TestRecommendProcess:
    def test_fallback_returns_consent(self):
        from backend.agents.library.proposal import recommend_process
        result = recommend_process(_base_state(discussion_summary="Budget discussion"))
        assert result["recommended_process"] in [
            "sense_check", "advice", "consent", "consensus",
            "choose", "score", "allocate", "rank", "time_poll",
        ]

    def test_action_logged(self):
        from backend.agents.library.proposal import recommend_process
        result = recommend_process(_base_state(discussion_summary="Budget discussion"))
        assert len(result["action_log"]) == 1
        assert "process" in result["action_log"][0]["action"].lower()

    def test_no_summary_still_returns_valid_process(self):
        from backend.agents.library.proposal import recommend_process
        result = recommend_process(_base_state())
        assert result["recommended_process"] in [
            "sense_check", "advice", "consent", "consensus",
            "choose", "score", "allocate", "rank", "time_poll",
        ]


class TestDraftProposalText:
    def test_draft_body_set_on_fallback(self):
        from backend.agents.library.proposal import draft_proposal_text
        state = _base_state(
            discussion_summary="We discussed the new budget.",
            recommended_process="consent",
        )
        result = draft_proposal_text(state)
        assert result["draft_proposal"] is not None
        assert len(result["draft_proposal"]) > 0

    def test_draft_options_has_at_least_two(self):
        from backend.agents.library.proposal import draft_proposal_text
        state = _base_state(
            discussion_summary="We discussed the new budget.",
            recommended_process="consent",
        )
        result = draft_proposal_text(state)
        assert len(result["draft_options"]) >= 2

    def test_action_logged(self):
        from backend.agents.library.proposal import draft_proposal_text
        state = _base_state(
            discussion_summary="We discussed the new budget.",
            recommended_process="consent",
        )
        result = draft_proposal_text(state)
        assert len(result["action_log"]) == 1


class TestHumanEditProposal:
    def test_sets_requires_human_token(self):
        from backend.agents.library.proposal import human_edit_proposal
        result = human_edit_proposal(_base_state())
        assert result["requires_human_token"] is True

    def test_action_logged(self):
        from backend.agents.library.proposal import human_edit_proposal
        result = human_edit_proposal(_base_state())
        assert len(result["action_log"]) == 1
        assert "hitl" in result["action_log"][0]["action"].lower()


class TestOpenPoll:
    def test_sets_closing_at(self):
        from backend.agents.library.proposal import open_poll
        result = open_poll(_base_state())
        assert result["closing_at"] is not None
        # Should be a valid ISO datetime string
        from datetime import datetime
        datetime.fromisoformat(result["closing_at"])

    def test_closing_at_is_future(self):
        from backend.agents.library.proposal import open_poll
        from datetime import datetime, timezone
        result = open_poll(_base_state())
        closing = datetime.fromisoformat(result["closing_at"])
        now = datetime.now(timezone.utc)
        assert closing > now

    def test_closing_at_honours_config_days(self):
        from backend.agents.library.proposal import open_poll
        from backend.config import settings
        from datetime import datetime, timezone, timedelta
        result = open_poll(_base_state())
        closing = datetime.fromisoformat(result["closing_at"])
        expected_min = datetime.now(timezone.utc) + timedelta(
            days=settings.deliberation_proposal_default_days - 1
        )
        assert closing > expected_min


class TestNotifyParticipants:
    def test_action_logged_with_proposal_opened_event(self):
        from backend.agents.library.proposal import notify_participants
        state = _base_state(
            thread_id="thread-42",
            recommended_process="consent",
            closing_at="2026-04-13T12:00:00+00:00",
            draft_options=["Approve", "Reject"],
        )
        result = notify_participants(state)
        assert len(result["action_log"]) == 1
        payload = result["action_log"][0]["payload"]
        assert payload["event_type"] == "proposal_opened"
        assert payload["thread_id"] == "thread-42"
        assert payload["recommended_process"] == "consent"


class TestProposalGraph:
    def test_graph_compiles(self):
        from backend.agents.library.proposal import build_proposal_graph
        graph = build_proposal_graph()
        assert graph is not None

    def test_graph_interrupts_at_hitl(self):
        from backend.agents.library.proposal import build_proposal_graph
        graph = build_proposal_graph()
        config = {"configurable": {"thread_id": "test-proposal-hitl"}}
        state = _base_state()
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        assert snapshot.next  # Should have paused at HITL

    def test_graph_after_resume_reaches_end(self):
        from backend.agents.library.proposal import build_proposal_graph
        graph = build_proposal_graph()
        config = {"configurable": {"thread_id": "test-proposal-resume"}}
        state = _base_state()
        # First invoke: pauses at HITL
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        assert snapshot.next
        # Resume: no state update needed — just continue
        graph.invoke(None, config=config)
        snapshot2 = graph.get_state(config)
        # After resuming, graph should reach END (no next node)
        assert not snapshot2.next

    def test_graph_closing_at_set_after_resume(self):
        from backend.agents.library.proposal import build_proposal_graph
        from datetime import datetime
        graph = build_proposal_graph()
        config = {"configurable": {"thread_id": "test-proposal-closing"}}
        graph.invoke(_base_state(), config=config)
        graph.invoke(None, config=config)
        snapshot = graph.get_state(config)
        closing_at = snapshot.values.get("closing_at")
        assert closing_at is not None
        datetime.fromisoformat(closing_at)
