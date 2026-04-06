# tests/test_deliberation_agents.py
"""Phase B: Deliberation facilitator agent tests."""
from __future__ import annotations

class TestDeliberationStateTypes:
    def test_discussion_state_has_required_fields(self):
        from backend.agents.state import DiscussionState
        fields = DiscussionState.__annotations__
        assert "thread_id" in fields
        assert "raw_prompt" in fields
        assert "draft_context" in fields
        assert "suggested_invitees" in fields
        assert "requires_human_token" in fields

    def test_voting_state_has_required_fields(self):
        from backend.agents.state import VotingState
        fields = VotingState.__annotations__
        assert "proposal_id" in fields
        assert "current_tally" in fields
        assert "closing_condition_met" in fields
        assert "existing_stances" in fields

    def test_proposal_state_has_required_fields(self):
        from backend.agents.state import ProposalState
        fields = ProposalState.__annotations__
        assert "thread_id" in fields
        assert "recommended_process" in fields
        assert "draft_proposal" in fields
        assert "draft_options" in fields
        assert "requires_human_token" in fields

    def test_outcome_state_has_required_fields(self):
        from backend.agents.state import OutcomeState
        fields = OutcomeState.__annotations__
        assert "decision_type" in fields
        assert "draft_outcome" in fields

    def test_task_extraction_state_has_required_fields(self):
        from backend.agents.state import TaskExtractionState
        fields = TaskExtractionState.__annotations__
        assert "extracted_tasks" in fields

class TestDeliberationConfig:
    def test_config_has_deliberation_settings(self):
        from backend.config import settings
        assert hasattr(settings, "deliberation_context_max_tokens")
        assert settings.deliberation_context_max_tokens == 800
        assert hasattr(settings, "deliberation_proposal_default_days")
        assert settings.deliberation_proposal_default_days == 7
        assert hasattr(settings, "deliberation_consent_auto_close_on_block")
        assert settings.deliberation_consent_auto_close_on_block is True

class TestNodeRegistry:
    def test_deliberation_nodes_registered(self):
        from backend.agents.spawner.node_registry import get_registry
        registry = get_registry()
        deliberation_nodes = [
            # Discussion (7)
            "receive_prompt", "research_precedents", "draft_thread_context",
            "human_edit_context", "publish_thread", "suggest_invitees", "notify_members",
            # Proposal (6)
            "summarise_discussion", "recommend_process", "draft_proposal_text",
            "human_edit_proposal", "open_poll", "notify_participants",
            # Voting (6)
            "validate_stance", "record_stance", "compute_tally",
            "evaluate_closing_condition", "notify_block", "trigger_outcome",
            # Outcome (8)
            "tally_final_results", "classify_decision", "draft_outcome_statement",
            "human_approve_outcome", "publish_outcome", "store_precedent_data",
            "broadcast_outcome", "invoke_task_agent",
            # Task Extractor (4)
            "extract_action_items", "confirm_assignments",
            "create_task_records", "schedule_reminders",
        ]
        for name in deliberation_nodes:
            assert name in registry, f"Node '{name}' not in registry"
