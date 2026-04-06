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


import uuid as _uuid_mod

class TestThreadEndpoints:
    async def test_create_thread_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(address="0xTest", did="did:example:alice", role="steward", member_token_id=1, chain_id=31337)
        fake = {
            "id": str(_uuid_mod.uuid4()), "title": "New payroll policy",
            "context": "We need to revise...", "author_did": "did:example:alice",
            "sub_group_id": None, "tags": [], "status": "open",
            "ai_context_draft": None, "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(return_value=fake)
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            "/deliberation/threads",
            json={"title": "New payroll policy", "context": "We need to revise...",
                  "author_did": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "New payroll policy"
        app.dependency_overrides.clear()

    async def test_list_threads_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        fake_user = AuthenticatedUser(address="0xTest", did=None, role="worker-owner", member_token_id=1, chain_id=31337)
        mock_db.fetch = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.get(
            "/deliberation/threads",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        app.dependency_overrides.clear()

    async def test_get_thread_detail_404_when_missing(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        fake_user = AuthenticatedUser(address="0xTest", did=None, role="worker-owner", member_token_id=1, chain_id=31337)
        mock_db.fetchrow = AsyncMock(return_value=None)
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.get(
            f"/deliberation/threads/{_uuid_mod.uuid4()}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 404
        app.dependency_overrides.clear()

    async def test_add_comment_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(address="0xTest", did=None, role="worker-owner", member_token_id=1, chain_id=31337)
        thread_id = str(_uuid_mod.uuid4())
        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:example:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        fake_comment = {
            "id": str(_uuid_mod.uuid4()), "thread_id": thread_id,
            "author_did": "did:example:bob", "parent_id": None,
            "body": "I agree with the direction.", "edited_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(side_effect=[fake_thread, fake_comment])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/comments",
            json={"thread_id": thread_id, "author_did": "did:example:bob",
                  "body": "I agree with the direction."},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["body"] == "I agree with the direction."
        app.dependency_overrides.clear()


class TestProposalEndpoints:
    async def test_create_proposal_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(address="0xTest", did=None, role="worker-owner", member_token_id=1, chain_id=31337)
        thread_id = str(_uuid_mod.uuid4())
        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:example:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        fake_proposal = {
            "id": str(_uuid_mod.uuid4()), "thread_id": thread_id,
            "title": "Adopt new pay policy", "body": "We propose...",
            "process_type": "consent", "options": None, "quorum_pct": 0,
            "closing_at": None, "status": "open", "ai_draft": None,
            "author_did": "did:example:alice", "agent_action_id": None,
            "created_at": datetime.now(timezone.utc), "closed_at": None,
        }
        mock_db.fetchrow = AsyncMock(side_effect=[fake_thread, fake_proposal])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/proposals",
            json={
                "thread_id": thread_id, "title": "Adopt new pay policy",
                "body": "We propose...", "process_type": "consent",
                "author_did": "did:example:alice",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["process_type"] == "consent"
        app.dependency_overrides.clear()

    async def test_cast_stance_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(address="0xTest", did=None, role="worker-owner", member_token_id=1, chain_id=31337)
        thread_id  = str(_uuid_mod.uuid4())
        proposal_id = str(_uuid_mod.uuid4())
        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id, "title": "t",
            "body": "b", "process_type": "consent", "options": None,
            "quorum_pct": 0, "closing_at": None, "status": "open",
            "ai_draft": None, "author_did": "did:example:alice",
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc), "closed_at": None,
        }
        fake_stance = {
            "id": str(_uuid_mod.uuid4()), "proposal_id": proposal_id,
            "member_did": "did:example:bob", "stance": "agree",
            "reason": "Good idea", "score": None, "rank_order": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_stance])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/stance",
            json={"member_did": "did:example:bob", "stance": "agree", "reason": "Good idea"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["stance"] == "agree"
        app.dependency_overrides.clear()

    async def test_create_task_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(address="0xTest", did=None, role="worker-owner", member_token_id=1, chain_id=31337)
        thread_id = str(_uuid_mod.uuid4())
        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:example:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        fake_task = {
            "id": str(_uuid_mod.uuid4()), "thread_id": thread_id,
            "outcome_id": None, "title": "Draft new contract",
            "assignee_did": "did:example:charlie", "due_date": "2026-05-01",
            "done": False, "done_at": None, "created_by": "did:example:alice",
            "created_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(side_effect=[fake_thread, fake_task])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/tasks",
            json={
                "thread_id": thread_id, "title": "Draft new contract",
                "created_by": "did:example:alice",
                "assignee_did": "did:example:charlie", "due_date": "2026-05-01",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Draft new contract"
        app.dependency_overrides.clear()


class TestUpdateThread:
    async def test_update_thread_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        thread_id = str(_uuid_mod.uuid4())
        fake_thread = {
            "id": thread_id, "title": "Updated title", "context": "Updated context",
            "author_did": "did:example:alice", "sub_group_id": None,
            "tags": ["updated"], "status": "open", "ai_context_draft": None,
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        # _require_thread → fetchrow returns thread; UPDATE ... RETURNING → fetchrow returns updated
        mock_db.fetchrow = AsyncMock(side_effect=[fake_thread, fake_thread])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.patch(
            f"/deliberation/threads/{thread_id}",
            json={"title": "Updated title", "context": "Updated context"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated title"
        app.dependency_overrides.clear()


class TestToggleReaction:
    async def test_toggle_reaction_adds_when_absent(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        thread_id  = str(_uuid_mod.uuid4())
        comment_id = str(_uuid_mod.uuid4())
        # fetchrow returns None → no existing reaction → INSERT path
        mock_db.fetchrow = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value="INSERT 0 1")
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/comments/{comment_id}/react",
            json={"member_did": "did:example:alice", "emoji": "👍"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "added"
        assert resp.json()["emoji"] == "👍"
        app.dependency_overrides.clear()


class TestMarkSeen:
    async def test_mark_seen_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        thread_id = str(_uuid_mod.uuid4())
        mock_db.execute = AsyncMock(return_value="INSERT 0 1")
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/seen",
            params={"member_did": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "seen"
        app.dependency_overrides.clear()


class TestGetProposal:
    async def test_get_proposal_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        thread_id   = str(_uuid_mod.uuid4())
        proposal_id = str(_uuid_mod.uuid4())
        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id,
            "title": "Adopt new pay policy", "body": "We propose...",
            "process_type": "consent", "options": None, "quorum_pct": 0,
            "closing_at": None, "status": "open", "ai_draft": None,
            "author_did": "did:example:alice", "agent_action_id": None,
            "created_at": datetime.now(timezone.utc), "closed_at": None,
        }
        # _require_proposal calls fetchrow; outcome lookup calls fetchrow again (returns None)
        mock_db.fetchrow = AsyncMock(side_effect=[fake_proposal, None])
        # stance fetch returns empty list
        mock_db.fetch = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.get(
            f"/deliberation/threads/{thread_id}/proposals/{proposal_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == proposal_id
        assert resp.json()["process_type"] == "consent"
        app.dependency_overrides.clear()


class TestStateOutcome:
    async def test_state_outcome_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        thread_id   = str(_uuid_mod.uuid4())
        proposal_id = str(_uuid_mod.uuid4())
        outcome_id  = str(_uuid_mod.uuid4())
        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id,
            "title": "Adopt new pay policy", "body": "We propose...",
            "process_type": "consent", "options": None, "quorum_pct": 0,
            "closing_at": None, "status": "open", "ai_draft": None,
            "author_did": "did:example:alice", "agent_action_id": None,
            "created_at": datetime.now(timezone.utc), "closed_at": None,
        }
        fake_outcome = {
            "id": outcome_id, "proposal_id": proposal_id,
            "statement": "The proposal passed by consent.",
            "decision_type": "passed", "precedent_id": None,
            "ai_draft": None, "stated_by": "did:example:alice",
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
        }
        # _require_proposal → fetchrow; INSERT outcome → fetchrow
        mock_db.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_outcome])
        mock_db.execute = AsyncMock(return_value="UPDATE 1")
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/outcome",
            json={
                "statement": "The proposal passed by consent.",
                "decision_type": "passed",
                "stated_by": "did:example:alice",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["decision_type"] == "passed"
        assert resp.json()["statement"] == "The proposal passed by consent."
        app.dependency_overrides.clear()


class TestUpdateTask:
    async def test_update_task_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        task_id    = str(_uuid_mod.uuid4())
        thread_id  = str(_uuid_mod.uuid4())
        fake_task = {
            "id": task_id, "thread_id": thread_id, "outcome_id": None,
            "title": "Draft new contract", "assignee_did": "did:example:charlie",
            "due_date": "2026-05-01", "done": True, "done_at": datetime.now(timezone.utc),
            "created_by": "did:example:alice", "created_at": datetime.now(timezone.utc),
        }
        # UPDATE ... RETURNING → fetchrow returns updated task
        mock_db.fetchrow = AsyncMock(return_value=fake_task)
        mock_db.execute = AsyncMock(return_value="UPDATE 1")
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.patch(
            f"/deliberation/tasks/{task_id}",
            json={"done": True},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["done"] is True
        app.dependency_overrides.clear()


class TestSubGroupMembers:
    async def test_list_members_returns_empty_list(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        subgroup_id = str(_uuid_mod.uuid4())
        mock_db.fetch = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.get(
            f"/subgroups/{subgroup_id}/members",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
        app.dependency_overrides.clear()

    async def test_add_member_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app
        from datetime import datetime, timezone

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        subgroup_id = str(_uuid_mod.uuid4())
        fake_member = {
            "sub_group_id": subgroup_id,
            "member_did": "did:example:bob",
            "role": "member",
            "joined_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(return_value=fake_member)
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.post(
            f"/subgroups/{subgroup_id}/members",
            json={"member_did": "did:example:bob", "role": "member"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["member_did"] == "did:example:bob"
        app.dependency_overrides.clear()

    async def test_remove_member_returns_204(self, async_client, mock_db):
        from backend.db import get_db
        from backend.auth.dependencies import get_current_user, AuthenticatedUser
        from backend.main import app

        fake_user = AuthenticatedUser(
            address="0xTest", did="did:test:alice", role="steward",
            member_token_id=1, chain_id=31337,
        )
        subgroup_id = str(_uuid_mod.uuid4())
        member_did  = "did:example:bob"
        mock_db.execute = AsyncMock(return_value="DELETE 1")
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await async_client.delete(
            f"/subgroups/{subgroup_id}/members/{member_did}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 204
        app.dependency_overrides.clear()
