# tests/test_voting_agent.py
"""VotingAgent tests — all deterministic, no LLM."""
from __future__ import annotations

def _base_state(**overrides) -> dict:
    base = {
        "messages": [], "agent_id": "voting-agent-v1",
        "action_log": [], "error": None,
        "proposal_id": "proposal-1", "process_type": "consent",
        "member_did": "did:test:alice", "stance": "agree",
        "reason": "Looks good", "existing_stances": [],
        "current_tally": {}, "quorum_pct": 0, "quorum_met": False,
        "closing_at": None, "closing_condition_met": False,
        "close_reason": None, "requires_human_token": False,
    }
    base.update(overrides)
    return base

class TestValidateStance:
    def test_valid_agree_stance(self):
        from backend.agents.library.voting import validate_stance
        state = _base_state(stance="agree", process_type="consent")
        result = validate_stance(state)
        assert result["error"] is None

    def test_block_only_valid_on_consent(self):
        from backend.agents.library.voting import validate_stance
        state = _base_state(stance="block", process_type="score")
        result = validate_stance(state)
        assert result["error"] is not None
        assert "block" in result["error"].lower()

    def test_block_valid_on_consent(self):
        from backend.agents.library.voting import validate_stance
        state = _base_state(stance="block", process_type="consent")
        result = validate_stance(state)
        assert result["error"] is None

class TestComputeTally:
    def test_tally_from_existing_stances(self):
        from backend.agents.library.voting import compute_tally
        stances = [
            {"stance": "agree"}, {"stance": "agree"},
            {"stance": "disagree"}, {"stance": "abstain"},
        ]
        state = _base_state(existing_stances=stances)
        result = compute_tally(state)
        assert result["current_tally"]["agree"] == 2
        assert result["current_tally"]["disagree"] == 1
        assert result["current_tally"]["total"] == 4

class TestEvaluateClosingCondition:
    def test_consent_closes_on_block(self):
        from backend.agents.library.voting import evaluate_closing_condition
        tally = {"agree": 3, "abstain": 0, "disagree": 0, "block": 1, "total": 4}
        state = _base_state(process_type="consent", current_tally=tally)
        result = evaluate_closing_condition(state)
        assert result["closing_condition_met"] is True
        assert result["close_reason"] == "block"

    def test_consensus_unanimous_closes(self):
        from backend.agents.library.voting import evaluate_closing_condition
        tally = {"agree": 5, "abstain": 0, "disagree": 0, "block": 0, "total": 5}
        state = _base_state(process_type="consensus", current_tally=tally)
        result = evaluate_closing_condition(state)
        assert result["closing_condition_met"] is True
        assert result["close_reason"] == "unanimous"

    def test_quorum_not_met(self):
        from backend.agents.library.voting import evaluate_closing_condition
        tally = {"agree": 1, "abstain": 0, "disagree": 0, "block": 0, "total": 1}
        state = _base_state(process_type="advice", quorum_pct=50, current_tally=tally)
        result = evaluate_closing_condition(state)
        assert result["quorum_met"] is False

class TestVotingGraph:
    def test_graph_compiles(self):
        from backend.agents.library.voting import build_voting_graph
        graph = build_voting_graph()
        assert graph is not None

    def test_agree_vote_end_to_end(self):
        from backend.agents.library.voting import build_voting_graph
        graph = build_voting_graph()
        state = _base_state(
            stance="agree", process_type="advice",
            existing_stances=[{"stance": "agree"}],
        )
        config = {"configurable": {"thread_id": "test-vote-e2e"}}
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        result = snapshot.values
        assert result["closing_condition_met"] is False
        assert len(result["action_log"]) >= 4  # 4 nodes
