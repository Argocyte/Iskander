# tests/test_deliberation_data_layer.py
"""Phase A: Deliberation data layer tests."""
from __future__ import annotations
import pytest

class TestDBPool:
    async def test_get_db_yields_connection(self, async_client):
        """Health endpoint proves app boots with DB pool initialised."""
        resp = await async_client.get("/health")
        assert resp.status_code == 200


class TestDeliberationSchemas:
    def test_process_type_enum_has_nine_values(self):
        from backend.schemas.deliberation import ProcessType
        assert len(ProcessType) == 9
        assert ProcessType.CONSENT.value == "consent"
        assert ProcessType.TIME_POLL.value == "time_poll"

    def test_thread_create_request_requires_title_and_author(self):
        from backend.schemas.deliberation import ThreadCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ThreadCreateRequest()  # missing required fields

    def test_thread_create_request_valid(self):
        from backend.schemas.deliberation import ThreadCreateRequest
        t = ThreadCreateRequest(
            title="New payroll policy",
            context="We need to revise how stewards are compensated.",
            author_did="did:example:alice",
        )
        assert t.title == "New payroll policy"
        assert t.sub_group_id is None

    def test_stance_option_enum(self):
        from backend.schemas.deliberation import StanceOption
        assert StanceOption.BLOCK.value == "block"
        assert StanceOption.AGREE.value == "agree"

    def test_proposal_tally_total(self):
        from backend.schemas.deliberation import ProposalTally
        tally = ProposalTally(agree=5, abstain=2, disagree=1, block=0, total=8)
        assert tally.total == 8

    def test_thread_summary_response(self):
        from backend.schemas.deliberation import ThreadSummary
        import uuid
        from datetime import datetime, timezone
        s = ThreadSummary(
            id=str(uuid.uuid4()),
            title="Test",
            author_did="did:example:bob",
            status="open",
            tags=[],
            open_proposal_count=1,
            comment_count=3,
            last_activity=datetime.now(timezone.utc),
        )
        assert s.open_proposal_count == 1
