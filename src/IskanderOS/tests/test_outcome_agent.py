# tests/test_outcome_agent.py
"""OutcomeAgent tests — classify_decision exhaustive + LLM fallback."""
from __future__ import annotations
import pytest

def _base_state(**overrides) -> dict:
    base = {
        "messages": [], "agent_id": "outcome-agent-v1",
        "action_log": [], "error": None,
        "proposal_id": "p1", "thread_id": "t1",
        "final_tally": {"agree": 3, "disagree": 0, "block": 0, "abstain": 0, "total": 3},
        "process_type": "consent", "draft_outcome": None,
        "decision_type": None, "precedent_data": None,
        "should_extract_tasks": False, "requires_human_token": False,
    }
    base.update(overrides)
    return base

class TestClassifyDecision:
    def test_consent_passes_without_block(self):
        from backend.agents.library.outcome import classify_decision
        result = classify_decision(_base_state(process_type="consent"))
        assert result["decision_type"] == "passed"

    def test_consent_rejects_on_block(self):
        from backend.agents.library.outcome import classify_decision
        tally = {"agree": 2, "disagree": 0, "block": 1, "abstain": 0, "total": 3}
        result = classify_decision(_base_state(process_type="consent", final_tally=tally))
        assert result["decision_type"] == "rejected"

    def test_consensus_passes_on_unanimous(self):
        from backend.agents.library.outcome import classify_decision
        tally = {"agree": 5, "disagree": 0, "block": 0, "abstain": 0, "total": 5}
        result = classify_decision(_base_state(process_type="consensus", final_tally=tally))
        assert result["decision_type"] == "passed"

    def test_consensus_rejects_on_disagree(self):
        from backend.agents.library.outcome import classify_decision
        tally = {"agree": 3, "disagree": 1, "block": 0, "abstain": 0, "total": 4}
        result = classify_decision(_base_state(process_type="consensus", final_tally=tally))
        assert result["decision_type"] == "rejected"

    def test_sense_check_always_passes(self):
        from backend.agents.library.outcome import classify_decision
        tally = {"agree": 1, "disagree": 5, "block": 0, "abstain": 0, "total": 6}
        result = classify_decision(_base_state(process_type="sense_check", final_tally=tally))
        assert result["decision_type"] == "passed"

    def test_advice_always_passes(self):
        from backend.agents.library.outcome import classify_decision
        result = classify_decision(_base_state(process_type="advice"))
        assert result["decision_type"] == "passed"

    @pytest.mark.parametrize("process", ["choose", "score", "allocate", "rank", "time_poll"])
    def test_poll_types_pass(self, process):
        from backend.agents.library.outcome import classify_decision
        result = classify_decision(_base_state(process_type=process))
        assert result["decision_type"] == "passed"

    def test_empty_tally_is_no_quorum(self):
        from backend.agents.library.outcome import classify_decision
        tally = {"agree": 0, "disagree": 0, "block": 0, "abstain": 0, "total": 0}
        result = classify_decision(_base_state(final_tally=tally))
        assert result["decision_type"] == "no_quorum"

class TestDraftOutcomeStatement:
    def test_fallback_produces_template(self):
        from backend.agents.library.outcome import draft_outcome_statement
        state = _base_state(decision_type="passed")
        result = draft_outcome_statement(state)
        assert result["draft_outcome"] is not None
        assert "passed" in result["draft_outcome"].lower()

class TestInvokeTaskAgent:
    def test_detects_action_keywords(self):
        from backend.agents.library.outcome import invoke_task_agent
        state = _base_state(draft_outcome="Alice should review the budget by Friday.")
        result = invoke_task_agent(state)
        assert result["should_extract_tasks"] is True

    def test_no_keywords_skips(self):
        from backend.agents.library.outcome import invoke_task_agent
        state = _base_state(draft_outcome="The proposal was approved.")
        result = invoke_task_agent(state)
        assert result["should_extract_tasks"] is False

class TestOutcomeGraph:
    def test_graph_compiles(self):
        from backend.agents.library.outcome import build_outcome_graph
        graph = build_outcome_graph()
        assert graph is not None
