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


class TestHITLExtensions:
    def test_new_proposal_types_accepted(self):
        from backend.schemas.hitl import HITLProposal
        p = HITLProposal(
            proposal_type="discussion_context",
            summary="AI drafted thread context for payroll discussion",
            agent_id="discussion-agent-v1",
            thread_id="thread-abc",
            callback_inbox="http://localhost:8000/hitl/callback",
        )
        assert p.proposal_type == "discussion_context"

    def test_loomio_route_accepted(self):
        from backend.schemas.hitl import HITLNotification, HITLProposal
        from datetime import datetime, timezone
        n = HITLNotification(
            member_did="did:example:alice",
            proposal=HITLProposal(
                proposal_type="proposal_draft",
                summary="Test",
                agent_id="proposal-agent",
                thread_id="t1",
                callback_inbox="http://cb",
            ),
            route="loomio",
        )
        assert n.route == "loomio"


from unittest.mock import AsyncMock

class TestSubGroupsRouter:
    async def test_list_subgroups_returns_empty_list(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        fake_user = AuthenticatedUser(address="0xTest", did="did:example:test", role="steward", member_token_id=1, chain_id=31337)
        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: mock_db
        mock_db.fetch = AsyncMock(return_value=[])

        resp = await async_client.get(
            "/subgroups",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
        app.dependency_overrides.clear()

    async def test_create_subgroup_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        import uuid
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(address="0xTest", did="did:example:test", role="steward", member_token_id=1, chain_id=31337)
        app.dependency_overrides[get_current_user] = lambda: fake_user

        fake_row = {
            "id": str(uuid.uuid4()),
            "slug": "tech-wg",
            "name": "Tech Working Group",
            "description": None,
            "created_by": "did:example:alice",
            "created_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(return_value=fake_row)
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            "/subgroups",
            json={"slug": "tech-wg", "name": "Tech Working Group", "created_by": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "tech-wg"
        app.dependency_overrides.clear()

    async def test_create_subgroup_invalid_slug_returns_422(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        fake_user = AuthenticatedUser(address="0xTest", did="did:example:test", role="steward", member_token_id=1, chain_id=31337)
        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: mock_db
        resp = await async_client.post(
            "/subgroups",
            json={"slug": "INVALID SLUG!", "name": "Bad", "created_by": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422
        app.dependency_overrides.clear()
