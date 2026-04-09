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


# ── Router ↔ Agent Integration Tests (Phase B, Task 9) ──────────────────────

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def agent_test_app():
    """Create test app with mocked dependencies for agent integration tests."""
    from backend.main import app
    from backend.db import get_db
    from backend.auth.dependencies import get_current_user, AuthenticatedUser

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
    mock_conn.fetchval = AsyncMock(return_value=None)
    test_user = AuthenticatedUser(
        address="0x1234", did="did:test:alice", role="steward",
        member_token_id=1, chain_id=31337,
    )
    app.dependency_overrides[get_db] = lambda: mock_conn
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield app, mock_conn
    app.dependency_overrides.clear()


class TestRouterAgentIntegration:
    """Verify that CRUD endpoints correctly wire to deliberation agents."""

    async def test_create_thread_enqueues_discussion_agent(self, agent_test_app):
        """POST /deliberation/threads should enqueue DiscussionAgent."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "title": "Test Thread", "context": "Test context",
            "author_did": "did:test:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None, "created_at": now, "updated_at": now,
        })

        with patch("backend.routers.deliberation.AsyncAgentQueue") as mock_queue_cls, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_queue = AsyncMock()
            mock_queue.enqueue = AsyncMock(return_value=MagicMock(task_id="task-1"))
            mock_queue_cls.get_instance.return_value = mock_queue
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/deliberation/threads", json={
                    "title": "Test Thread", "context": "Test context",
                    "author_did": "did:test:alice",
                })

            assert resp.status_code == 201
            mock_queue.enqueue.assert_called_once()
            # Verify the enqueued state has correct agent_id and thread_id
            call_args = mock_queue.enqueue.call_args
            state_arg = call_args[0][1]  # second positional arg is state
            assert state_arg["agent_id"] == "discussion-agent-v1"
            assert state_arg["thread_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            assert state_arg["raw_prompt"] == "Test context"

    async def test_create_thread_broadcasts_thread_created(self, agent_test_app):
        """POST /deliberation/threads should broadcast thread_created event."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "title": "Test Thread", "context": "Test context",
            "author_did": "did:test:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None, "created_at": now, "updated_at": now,
        })

        with patch("backend.routers.deliberation.AsyncAgentQueue") as mock_queue_cls, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_queue = AsyncMock()
            mock_queue.enqueue = AsyncMock(return_value=MagicMock(task_id="task-1"))
            mock_queue_cls.get_instance.return_value = mock_queue
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/deliberation/threads", json={
                    "title": "Test Thread", "context": "Test context",
                    "author_did": "did:test:alice",
                })

            assert resp.status_code == 201
            # Verify WebSocket broadcast with correct event type
            mock_ws.broadcast.assert_called()
            broadcast_arg = mock_ws.broadcast.call_args[0][0]
            assert broadcast_arg["event"] == "thread_created"
            assert broadcast_arg["payload"]["title"] == "Test Thread"

    async def test_add_comment_broadcasts_comment_added(self, agent_test_app):
        """POST /deliberation/threads/{id}/comments should broadcast comment_added."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:test:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None, "created_at": now, "updated_at": now,
        }
        fake_comment = {
            "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "thread_id": thread_id, "author_did": "did:test:bob",
            "parent_id": None, "body": "Great idea!", "edited_at": None,
            "created_at": now,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_thread, fake_comment])

        with patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/comments",
                    json={"thread_id": thread_id, "author_did": "did:test:bob",
                          "body": "Great idea!"},
                )

            assert resp.status_code == 201
            mock_ws.broadcast.assert_called()
            broadcast_arg = mock_ws.broadcast.call_args[0][0]
            assert broadcast_arg["event"] == "comment_added"
            assert broadcast_arg["payload"]["thread_id"] == thread_id

    async def test_create_proposal_enqueues_proposal_agent(self, agent_test_app):
        """POST /deliberation/threads/{id}/proposals should enqueue ProposalAgent."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:test:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None, "created_at": now, "updated_at": now,
        }
        fake_proposal = {
            "id": "22222222-2222-2222-2222-222222222222",
            "thread_id": thread_id, "title": "Test Proposal",
            "body": "We propose...", "process_type": "consent",
            "options": None, "quorum_pct": 0, "closing_at": None,
            "status": "open", "ai_draft": None,
            "author_did": "did:test:alice", "agent_action_id": None,
            "created_at": now, "closed_at": None,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_thread, fake_proposal])
        mock_conn.fetch = AsyncMock(return_value=[{"body": "I think we should..."}])

        with patch("backend.routers.deliberation.AsyncAgentQueue") as mock_queue_cls, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_queue = AsyncMock()
            mock_queue.enqueue = AsyncMock(return_value=MagicMock(task_id="task-2"))
            mock_queue_cls.get_instance.return_value = mock_queue
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/proposals",
                    json={
                        "thread_id": thread_id, "title": "Test Proposal",
                        "body": "We propose...", "process_type": "consent",
                        "author_did": "did:test:alice",
                    },
                )

            assert resp.status_code == 201
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            state_arg = call_args[0][1]
            assert state_arg["agent_id"] == "proposal-agent-v1"
            assert state_arg["discussion_summary"] == "I think we should..."
            # Verify proposal_opened WebSocket broadcast
            mock_ws.broadcast.assert_called()
            broadcast_arg = mock_ws.broadcast.call_args[0][0]
            assert broadcast_arg["event"] == "proposal_opened"

    async def test_cast_stance_invokes_voting_agent(self, agent_test_app):
        """POST /stance should invoke VotingAgent synchronously."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "11111111-1111-1111-1111-111111111111"
        proposal_id = "22222222-2222-2222-2222-222222222222"

        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id,
            "title": "Test", "body": "Body", "process_type": "consent",
            "options": None, "quorum_pct": 0, "closing_at": None,
            "status": "open", "ai_draft": None, "author_did": "did:test:bob",
            "agent_action_id": None, "created_at": now, "closed_at": None,
        }
        fake_stance = {
            "id": "33333333-3333-3333-3333-333333333333",
            "proposal_id": proposal_id, "member_did": "did:test:alice",
            "stance": "agree", "reason": "Looks good", "score": None,
            "rank_order": None, "created_at": now, "updated_at": now,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_stance])
        mock_conn.fetch = AsyncMock(return_value=[
            {"stance": "agree"}, {"stance": "agree"},
        ])

        with patch("backend.routers.deliberation.voting_graph") as mock_vg, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            # VotingAgent returns non-closing state
            mock_snapshot = MagicMock()
            mock_snapshot.values = {
                "closing_condition_met": False,
                "close_reason": None,
                "error": None,
                "current_tally": {"agree": 2, "total": 2},
            }
            mock_vg.invoke = MagicMock()
            mock_vg.get_state = MagicMock(return_value=mock_snapshot)
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/stance",
                    json={"member_did": "did:test:alice", "stance": "agree",
                          "reason": "Looks good"},
                )

            assert resp.status_code == 200
            mock_vg.invoke.assert_called_once()
            # Verify stance_cast WebSocket broadcast
            mock_ws.broadcast.assert_called()
            events = [c[0][0]["event"] for c in mock_ws.broadcast.call_args_list]
            assert "stance_cast" in events

    async def test_cast_block_closes_consent_proposal(self, agent_test_app):
        """Block on consent proposal triggers auto-close + OutcomeAgent enqueue."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "11111111-1111-1111-1111-111111111111"
        proposal_id = "22222222-2222-2222-2222-222222222222"

        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id,
            "title": "Test", "body": "Body", "process_type": "consent",
            "options": None, "quorum_pct": 0, "closing_at": None,
            "status": "open", "ai_draft": None, "author_did": "did:test:bob",
            "agent_action_id": None, "created_at": now, "closed_at": None,
        }
        fake_stance = {
            "id": "33333333-3333-3333-3333-333333333333",
            "proposal_id": proposal_id, "member_did": "did:test:alice",
            "stance": "block", "reason": "No", "score": None,
            "rank_order": None, "created_at": now, "updated_at": now,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_stance])
        mock_conn.fetch = AsyncMock(return_value=[{"stance": "block"}])
        mock_conn.execute = AsyncMock()

        with patch("backend.routers.deliberation.voting_graph") as mock_vg, \
             patch("backend.routers.deliberation.AsyncAgentQueue") as mock_queue_cls, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_snapshot = MagicMock()
            mock_snapshot.values = {
                "closing_condition_met": True,
                "close_reason": "block",
                "error": None,
                "current_tally": {"agree": 0, "block": 1, "total": 1},
            }
            mock_vg.invoke = MagicMock()
            mock_vg.get_state = MagicMock(return_value=mock_snapshot)
            mock_queue = AsyncMock()
            mock_queue.enqueue = AsyncMock(return_value=MagicMock(task_id="t2"))
            mock_queue_cls.get_instance.return_value = mock_queue
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/stance",
                    json={"member_did": "did:test:alice", "stance": "block",
                          "reason": "No"},
                )

            assert resp.status_code == 200
            # Proposal should be closed via DB UPDATE
            mock_conn.execute.assert_called()
            # OutcomeAgent should be enqueued
            mock_queue.enqueue.assert_called_once()
            outcome_state = mock_queue.enqueue.call_args[0][1]
            assert outcome_state["agent_id"] == "outcome-agent-v1"
            assert outcome_state["proposal_id"] == proposal_id
            # Both proposal_closed and stance_cast events should be broadcast
            events = [c[0][0]["event"] for c in mock_ws.broadcast.call_args_list]
            assert "proposal_closed" in events
            assert "stance_cast" in events

    async def test_state_outcome_broadcasts_and_enqueues_task_agent(self, agent_test_app):
        """POST /outcome with action keywords should enqueue TaskAgent."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "11111111-1111-1111-1111-111111111111"
        proposal_id = "22222222-2222-2222-2222-222222222222"
        outcome_id = "44444444-4444-4444-4444-444444444444"

        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id,
            "title": "Test", "body": "Body", "process_type": "consent",
            "options": None, "quorum_pct": 0, "closing_at": None,
            "status": "open", "ai_draft": None, "author_did": "did:test:bob",
            "agent_action_id": None, "created_at": now, "closed_at": None,
        }
        fake_outcome = {
            "id": outcome_id, "proposal_id": proposal_id,
            "statement": "The proposal passed. Members must update the handbook.",
            "decision_type": "passed", "precedent_id": None,
            "ai_draft": None, "stated_by": "did:test:alice",
            "agent_action_id": None, "created_at": now,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_outcome])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.routers.deliberation.AsyncAgentQueue") as mock_queue_cls, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_queue = AsyncMock()
            mock_queue.enqueue = AsyncMock(return_value=MagicMock(task_id="t3"))
            mock_queue_cls.get_instance.return_value = mock_queue
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/outcome",
                    json={
                        "statement": "The proposal passed. Members must update the handbook.",
                        "decision_type": "passed",
                        "stated_by": "did:test:alice",
                    },
                )

            assert resp.status_code == 201
            # TaskAgent should be enqueued (statement contains "must")
            mock_queue.enqueue.assert_called_once()
            task_state = mock_queue.enqueue.call_args[0][1]
            assert task_state["agent_id"] == "task-agent-v1"
            assert "must" in task_state["source_text"].lower()
            # outcome_stated WebSocket event
            mock_ws.broadcast.assert_called()
            broadcast_arg = mock_ws.broadcast.call_args_list[0][0][0]
            assert broadcast_arg["event"] == "outcome_stated"

    async def test_state_outcome_no_task_agent_without_keywords(self, agent_test_app):
        """POST /outcome without action keywords should NOT enqueue TaskAgent."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "11111111-1111-1111-1111-111111111111"
        proposal_id = "22222222-2222-2222-2222-222222222222"
        outcome_id = "44444444-4444-4444-4444-444444444444"

        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id,
            "title": "Test", "body": "Body", "process_type": "consent",
            "options": None, "quorum_pct": 0, "closing_at": None,
            "status": "open", "ai_draft": None, "author_did": "did:test:bob",
            "agent_action_id": None, "created_at": now, "closed_at": None,
        }
        fake_outcome = {
            "id": outcome_id, "proposal_id": proposal_id,
            "statement": "The proposal did not reach quorum.",
            "decision_type": "rejected", "precedent_id": None,
            "ai_draft": None, "stated_by": "did:test:alice",
            "agent_action_id": None, "created_at": now,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_outcome])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.routers.deliberation.AsyncAgentQueue") as mock_queue_cls, \
             patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_queue = AsyncMock()
            mock_queue_cls.get_instance.return_value = mock_queue
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/outcome",
                    json={
                        "statement": "The proposal did not reach quorum.",
                        "decision_type": "rejected",
                        "stated_by": "did:test:alice",
                    },
                )

            assert resp.status_code == 201
            # TaskAgent should NOT be enqueued (no action keywords)
            mock_queue.enqueue.assert_not_called()

    async def test_create_task_broadcasts_task_created(self, agent_test_app):
        """POST /deliberation/threads/{id}/tasks should broadcast task_created."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        thread_id = "11111111-1111-1111-1111-111111111111"

        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:test:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None, "created_at": now, "updated_at": now,
        }
        fake_task = {
            "id": "55555555-5555-5555-5555-555555555555",
            "thread_id": thread_id, "outcome_id": None,
            "title": "Draft handbook update", "assignee_did": "did:test:charlie",
            "due_date": "2026-05-01", "done": False, "done_at": None,
            "created_by": "did:test:alice", "created_at": now,
        }
        mock_conn.fetchrow = AsyncMock(side_effect=[fake_thread, fake_task])

        with patch("backend.routers.deliberation.WebSocketNotifier") as mock_ws_cls, \
             patch("backend.routers.deliberation._AGENTS_AVAILABLE", True):
            mock_ws = AsyncMock()
            mock_ws_cls.get_instance.return_value = mock_ws

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/deliberation/threads/{thread_id}/tasks",
                    json={
                        "thread_id": thread_id,
                        "title": "Draft handbook update",
                        "created_by": "did:test:alice",
                        "assignee_did": "did:test:charlie",
                        "due_date": "2026-05-01",
                    },
                )

            assert resp.status_code == 201
            mock_ws.broadcast.assert_called()
            broadcast_arg = mock_ws.broadcast.call_args[0][0]
            assert broadcast_arg["event"] == "task_created"
            assert broadcast_arg["payload"]["title"] == "Draft handbook update"

    async def test_agents_degrade_gracefully_when_unavailable(self, agent_test_app):
        """When _AGENTS_AVAILABLE is False, endpoints still return data normally."""
        app, mock_conn = agent_test_app
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "title": "Test Thread", "context": "Test context",
            "author_did": "did:test:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None, "created_at": now, "updated_at": now,
        })

        with patch("backend.routers.deliberation._AGENTS_AVAILABLE", False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/deliberation/threads", json={
                    "title": "Test Thread", "context": "Test context",
                    "author_did": "did:test:alice",
                })

            assert resp.status_code == 201
            assert resp.json()["title"] == "Test Thread"
