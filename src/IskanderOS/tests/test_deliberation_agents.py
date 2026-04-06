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
