# backend/routers/deliberation.py
"""
deliberation.py — Iskander Native Deliberation System router.

Implements Loomio's deliberation model natively:
  Threads → Comments → Proposals → Stances → Outcomes → Tasks

All write operations go to PostgreSQL via asyncpg.
AI facilitation agents are wired as side-effects after DB writes:
  - DiscussionAgent (LLM, async) — enqueued after thread creation
  - ProposalAgent (LLM, async) — enqueued after proposal creation
  - VotingAgent (deterministic, sync) — invoked inline after stance cast
  - OutcomeAgent (LLM, async) — enqueued after proposal auto-close
  - TaskAgent (LLM, async) — enqueued after outcome with action keywords

Endpoints:
  Threads:   GET/POST /deliberation/threads
             GET/PATCH /deliberation/threads/{id}
  Comments:  POST /deliberation/threads/{id}/comments
             POST /deliberation/threads/{id}/comments/{cid}/react
             POST /deliberation/threads/{id}/seen
  Proposals: POST /deliberation/threads/{id}/proposals
             GET  /deliberation/threads/{id}/proposals/{pid}
  Stances:   POST /deliberation/threads/{id}/proposals/{pid}/stance
  Outcomes:  POST /deliberation/threads/{id}/proposals/{pid}/outcome
  Tasks:     POST /deliberation/threads/{id}/tasks
             PATCH /deliberation/tasks/{tid}
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.dependencies import AuthenticatedUser, get_current_user
from backend.db import get_db
from backend.schemas.deliberation import (
    CommentCreateRequest,
    CommentResponse,
    OutcomeCreateRequest,
    OutcomeResponse,
    ProposalCreateRequest,
    ProposalDetail,
    ProposalSummary,
    ProposalTally,
    ReactionToggleRequest,
    StanceCreateRequest,
    StanceResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    ThreadCreateRequest,
    ThreadDetail,
    ThreadSummary,
    ThreadUpdateRequest,
)

logger = logging.getLogger(__name__)

# ── Agent imports (Phase B) ───────────────────────────────────────────────
try:
    from backend.agents.library.voting import voting_graph
    from backend.agents.library.discussion import discussion_graph
    from backend.agents.library.proposal import proposal_graph
    from backend.agents.library.outcome import outcome_graph
    from backend.agents.library.task_extractor import task_graph
    from backend.core.llm_queue_manager import AsyncAgentQueue
    from backend.api.websocket_notifier import WebSocketNotifier
    _AGENTS_AVAILABLE = True
except ImportError:
    _AGENTS_AVAILABLE = False
    logger.warning("Deliberation agents not available — running in data-only mode")

router = APIRouter(prefix="/deliberation", tags=["deliberation"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(val)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid UUID: {val}")


async def _require_thread(conn: asyncpg.Connection, thread_id: str) -> dict[str, Any]:
    row = await conn.fetchrow(
        "SELECT id::text, title, context, author_did, sub_group_id::text, "
        "tags, status, ai_context_draft, agent_action_id::text, created_at, updated_at "
        "FROM deliberation_threads WHERE id = $1",
        _uuid(thread_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return dict(row)


async def _require_proposal(
    conn: asyncpg.Connection, proposal_id: str
) -> dict[str, Any]:
    row = await conn.fetchrow(
        "SELECT id::text, thread_id::text, title, body, process_type, options, "
        "quorum_pct, closing_at, status, ai_draft, author_did, "
        "agent_action_id::text, created_at, closed_at "
        "FROM deliberation_proposals WHERE id = $1",
        _uuid(proposal_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return dict(row)


# ── Threads ───────────────────────────────────────────────────────────────────

@router.get("/threads", response_model=list[ThreadSummary])
async def list_threads(
    status_filter: str | None = Query(default=None, alias="status"),
    tag: str | None = Query(default=None),
    sub_group_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[ThreadSummary]:
    """List threads, optionally filtered by status, tag, subgroup, or search."""
    clauses = []
    params: list[Any] = []

    if status_filter:
        params.append(status_filter)
        clauses.append(f"t.status = ${len(params)}")
    if tag:
        params.append(tag)
        clauses.append(f"${len(params)} = ANY(t.tags)")
    if sub_group_id:
        params.append(_uuid(sub_group_id))
        clauses.append(f"t.sub_group_id = ${len(params)}")
    if search:
        params.append(f"%{search}%")
        clauses.append(f"(t.title ILIKE ${len(params)} OR t.context ILIKE ${len(params)})")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = await conn.fetch(
        f"""
        SELECT
            t.id::text, t.title, t.author_did, t.status, t.tags, t.sub_group_id::text,
            COALESCE(MAX(c.created_at), t.created_at) AS last_activity,
            COUNT(DISTINCT c.id)::int                 AS comment_count,
            COUNT(DISTINCT p.id) FILTER (WHERE p.status = 'open')::int AS open_proposal_count
        FROM deliberation_threads t
        LEFT JOIN thread_comments      c ON c.thread_id = t.id
        LEFT JOIN deliberation_proposals p ON p.thread_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY last_activity DESC
        """,
        *params,
    )
    return [ThreadSummary(**dict(r)) for r in rows]


@router.post("/threads", response_model=ThreadDetail, status_code=status.HTTP_201_CREATED)
async def create_thread(
    req: ThreadCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    """Create a new deliberation thread. Phase B: DiscussionAgent triggered here."""
    row = await conn.fetchrow(
        """
        INSERT INTO deliberation_threads
            (title, context, author_did, sub_group_id, tags)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id::text, title, context, author_did, sub_group_id::text,
                  tags, status, ai_context_draft, agent_action_id::text,
                  created_at, updated_at
        """,
        req.title, req.context, req.author_did,
        _uuid(req.sub_group_id) if req.sub_group_id else None,
        req.tags,
    )
    result = ThreadDetail(**dict(row))

    # ── Phase B: Enqueue DiscussionAgent ──────────────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            queue = AsyncAgentQueue.get_instance()
            handle = await queue.enqueue(discussion_graph, {
                "messages": [], "agent_id": "discussion-agent-v1",
                "action_log": [], "error": None,
                "thread_id": str(row["id"]), "raw_prompt": req.context,
                "precedent_docs": [], "draft_context": None,
                "suggested_invitees": [], "engagement_report": None,
                "requires_human_token": False,
            }, {"configurable": {"thread_id": str(row["id"])}})
            logger.info("DiscussionAgent enqueued: task_id=%s", handle.task_id)
        except Exception as exc:
            logger.warning("DiscussionAgent enqueue failed: %s", exc)

    # ── Phase B: WebSocket broadcast ──────────────────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "event": "thread_created",
                "agent_id": "deliberation-router",
                "payload": {"thread_id": str(row["id"]), "title": req.title},
            })
        except Exception:
            pass  # WebSocket unavailable — degrade silently

    return result


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    """Return full thread with comments, proposals, and tasks."""
    thread = await _require_thread(conn, thread_id)

    comments_rows = await conn.fetch(
        "SELECT id::text, thread_id::text, author_did, parent_id::text, "
        "body, edited_at, created_at "
        "FROM thread_comments WHERE thread_id = $1 ORDER BY created_at",
        _uuid(thread_id),
    )
    proposal_rows = await conn.fetch(
        "SELECT p.id::text, p.title, p.process_type, p.status, p.closing_at, "
        "COUNT(s.id)::int AS stance_count "
        "FROM deliberation_proposals p "
        "LEFT JOIN proposal_stances s ON s.proposal_id = p.id "
        "WHERE p.thread_id = $1 GROUP BY p.id ORDER BY p.created_at",
        _uuid(thread_id),
    )
    task_rows = await conn.fetch(
        "SELECT id::text, thread_id::text, outcome_id::text, title, "
        "assignee_did, due_date::text, done, done_at, created_by, created_at "
        "FROM thread_tasks WHERE thread_id = $1 ORDER BY created_at",
        _uuid(thread_id),
    )

    thread["comments"]  = [CommentResponse(**{**dict(r), "reactions": {}}) for r in comments_rows]
    thread["proposals"] = [ProposalSummary(**dict(r)) for r in proposal_rows]
    thread["tasks"]     = [TaskResponse(**dict(r)) for r in task_rows]
    return ThreadDetail(**thread)


@router.patch("/threads/{thread_id}", response_model=ThreadDetail)
async def update_thread(
    thread_id: str,
    req: ThreadUpdateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    """Update thread title, context, status, or tags."""
    await _require_thread(conn, thread_id)

    updates: list[str] = ["updated_at = NOW()"]
    params: list[Any] = []

    if req.title is not None:
        params.append(req.title);    updates.append(f"title = ${len(params)}")
    if req.context is not None:
        params.append(req.context);  updates.append(f"context = ${len(params)}")
    if req.status is not None:
        params.append(req.status.value); updates.append(f"status = ${len(params)}")
    if req.tags is not None:
        params.append(req.tags);     updates.append(f"tags = ${len(params)}")

    params.append(_uuid(thread_id))
    row = await conn.fetchrow(
        f"UPDATE deliberation_threads SET {', '.join(updates)} "
        f"WHERE id = ${len(params)} "
        "RETURNING id::text, title, context, author_did, sub_group_id::text, "
        "tags, status, ai_context_draft, agent_action_id::text, created_at, updated_at",
        *params,
    )
    result = dict(row)
    result.update({"comments": [], "proposals": [], "tasks": []})
    return ThreadDetail(**result)


# ── Comments ──────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/comments",
             response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    thread_id: str,
    req: CommentCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> CommentResponse:
    """Post a comment to a thread."""
    await _require_thread(conn, thread_id)
    row = await conn.fetchrow(
        """
        INSERT INTO thread_comments (thread_id, author_did, parent_id, body)
        VALUES ($1, $2, $3, $4)
        RETURNING id::text, thread_id::text, author_did, parent_id::text,
                  body, edited_at, created_at
        """,
        _uuid(thread_id), req.author_did,
        _uuid(req.parent_id) if req.parent_id else None,
        req.body,
    )
    result = CommentResponse(**{**dict(row), "reactions": {}})

    # ── Phase B: WebSocket broadcast ──────────────────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "event": "comment_added",
                "agent_id": "deliberation-router",
                "payload": {
                    "thread_id": thread_id,
                    "comment_id": str(row["id"]),
                    "author_did": req.author_did,
                },
            })
        except Exception:
            pass  # WebSocket unavailable — degrade silently

    return result


@router.post("/threads/{thread_id}/comments/{comment_id}/react",
             status_code=status.HTTP_200_OK)
async def toggle_reaction(
    thread_id: str,
    comment_id: str,
    req: ReactionToggleRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Toggle an emoji reaction on a comment."""
    existing = await conn.fetchrow(
        "SELECT 1 FROM thread_reactions WHERE comment_id = $1 "
        "AND member_did = $2 AND emoji = $3",
        _uuid(comment_id), req.member_did, req.emoji,
    )
    if existing:
        await conn.execute(
            "DELETE FROM thread_reactions WHERE comment_id = $1 "
            "AND member_did = $2 AND emoji = $3",
            _uuid(comment_id), req.member_did, req.emoji,
        )
        return {"action": "removed", "emoji": req.emoji}
    await conn.execute(
        "INSERT INTO thread_reactions (comment_id, member_did, emoji) "
        "VALUES ($1, $2, $3)",
        _uuid(comment_id), req.member_did, req.emoji,
    )
    return {"action": "added", "emoji": req.emoji}


@router.post("/threads/{thread_id}/seen", status_code=status.HTTP_200_OK)
async def mark_seen(
    thread_id: str,
    member_did: str = Query(...),
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, str]:
    """Mark a thread as seen by a member (upsert)."""
    await conn.execute(
        """
        INSERT INTO thread_seen (thread_id, member_did, last_seen_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (thread_id, member_did) DO UPDATE SET last_seen_at = NOW()
        """,
        _uuid(thread_id), member_did,
    )
    return {"status": "seen"}


# ── Proposals ─────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/proposals",
             response_model=ProposalDetail, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    thread_id: str,
    req: ProposalCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalDetail:
    """Attach a proposal to a thread. Phase B: ProposalAgent drafts body here."""
    await _require_thread(conn, thread_id)
    row = await conn.fetchrow(
        """
        INSERT INTO deliberation_proposals
            (thread_id, title, body, process_type, options, quorum_pct,
             closing_at, author_did)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        RETURNING id::text, thread_id::text, title, body, process_type, options,
                  quorum_pct, closing_at, status, ai_draft, author_did,
                  agent_action_id::text, created_at, closed_at
        """,
        _uuid(thread_id), req.title, req.body, req.process_type.value,
        json.dumps(req.options) if req.options else None,
        req.quorum_pct, req.closing_at, req.author_did,
    )
    result = dict(row)
    result.update({"stances": [], "tally": ProposalTally(), "outcome": None})

    # ── Phase B: Enqueue ProposalAgent ────────────────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            queue = AsyncAgentQueue.get_instance()
            comment_rows = await conn.fetch(
                "SELECT body FROM thread_comments WHERE thread_id = $1 ORDER BY created_at",
                _uuid(thread_id),
            )
            discussion_text = "\n".join(r["body"] for r in comment_rows)
            handle = await queue.enqueue(proposal_graph, {
                "messages": [], "agent_id": "proposal-agent-v1",
                "action_log": [], "error": None,
                "thread_id": thread_id, "discussion_summary": discussion_text,
                "recommended_process": None, "draft_proposal": None,
                "draft_options": [], "closing_at": None,
                "requires_human_token": False,
            }, {"configurable": {"thread_id": f"proposal-{row['id']}"}})
            logger.info("ProposalAgent enqueued: task_id=%s", handle.task_id)
        except Exception as exc:
            logger.warning("ProposalAgent enqueue failed: %s", exc)

    # ── Phase B: WebSocket broadcast ──────────────────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "event": "proposal_opened",
                "agent_id": "deliberation-router",
                "payload": {
                    "thread_id": thread_id,
                    "proposal_id": str(row["id"]),
                    "title": req.title,
                    "process_type": req.process_type.value,
                },
            })
        except Exception:
            pass  # WebSocket unavailable — degrade silently

    return ProposalDetail(**result)


@router.get("/threads/{thread_id}/proposals/{proposal_id}",
            response_model=ProposalDetail)
async def get_proposal(
    thread_id: str,
    proposal_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalDetail:
    """Return proposal with all stances and live tally."""
    proposal = await _require_proposal(conn, proposal_id)

    stance_rows = await conn.fetch(
        "SELECT id::text, proposal_id::text, member_did, stance, reason, "
        "score, rank_order, created_at, updated_at "
        "FROM proposal_stances WHERE proposal_id = $1 ORDER BY created_at",
        _uuid(proposal_id),
    )
    stances = [StanceResponse(**dict(r)) for r in stance_rows]

    tally = ProposalTally(total=len(stances))
    for s in stances:
        if s.stance in ("agree", "abstain", "disagree", "block"):
            setattr(tally, s.stance, getattr(tally, s.stance, 0) + 1)
        else:
            tally.options[s.stance] = tally.options.get(s.stance, 0) + 1

    outcome_row = await conn.fetchrow(
        "SELECT id::text, proposal_id::text, statement, decision_type, "
        "precedent_id::text, ai_draft, stated_by, agent_action_id::text, created_at "
        "FROM decision_outcomes WHERE proposal_id = $1",
        _uuid(proposal_id),
    )
    outcome = OutcomeResponse(**dict(outcome_row)) if outcome_row else None

    proposal.update({"stances": stances, "tally": tally, "outcome": outcome})
    return ProposalDetail(**proposal)


# ── Stances ───────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/proposals/{proposal_id}/stance",
             response_model=StanceResponse)
async def cast_stance(
    thread_id: str,
    proposal_id: str,
    req: StanceCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> StanceResponse:
    """Cast or update a stance. Phase B: VotingAgent validates closing conditions."""
    proposal = await _require_proposal(conn, proposal_id)
    if proposal["status"] != "open":
        raise HTTPException(status_code=409, detail="Proposal is not open for voting")

    row = await conn.fetchrow(
        """
        INSERT INTO proposal_stances
            (proposal_id, member_did, stance, reason, score, rank_order)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (proposal_id, member_did) DO UPDATE
            SET stance     = EXCLUDED.stance,
                reason     = EXCLUDED.reason,
                score      = EXCLUDED.score,
                rank_order = EXCLUDED.rank_order,
                updated_at = NOW()
        RETURNING id::text, proposal_id::text, member_did, stance, reason,
                  score, rank_order, created_at, updated_at
        """,
        _uuid(proposal_id), req.member_did, req.stance,
        req.reason, req.score,
        json.dumps(req.rank_order) if req.rank_order else None,
    )
    result = StanceResponse(**dict(row))

    # ── Phase B: Invoke VotingAgent synchronously ─────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            stance_rows = await conn.fetch(
                "SELECT stance FROM proposal_stances WHERE proposal_id = $1",
                _uuid(proposal_id),
            )
            voting_state = {
                "messages": [], "agent_id": "voting-agent-v1",
                "action_log": [], "error": None,
                "proposal_id": proposal_id, "process_type": proposal["process_type"],
                "member_did": req.member_did, "stance": req.stance,
                "reason": req.reason,
                "existing_stances": [dict(s) for s in stance_rows],
                "current_tally": {}, "quorum_pct": proposal.get("quorum_pct", 0),
                "quorum_met": False,
                "closing_at": str(proposal["closing_at"]) if proposal.get("closing_at") else None,
                "closing_condition_met": False, "close_reason": None,
                "requires_human_token": False,
            }
            config = {"configurable": {"thread_id": f"vote-{proposal_id}-{req.member_did}"}}

            await asyncio.to_thread(voting_graph.invoke, voting_state, config)
            snapshot = await asyncio.to_thread(voting_graph.get_state, config)
            result_values = snapshot.values

            if result_values.get("error"):
                logger.warning(
                    "VotingAgent validation warning for proposal %s: %s",
                    proposal_id, result_values["error"],
                )

            if result_values.get("closing_condition_met"):
                await conn.execute(
                    "UPDATE deliberation_proposals SET status = 'closed', closed_at = NOW() "
                    "WHERE id = $1", _uuid(proposal_id),
                )
                logger.info(
                    "Proposal %s auto-closed: %s",
                    proposal_id, result_values.get("close_reason"),
                )
                # Enqueue OutcomeAgent for auto-closed proposal
                try:
                    queue = AsyncAgentQueue.get_instance()
                    tally = result_values.get("current_tally", {})
                    await queue.enqueue(outcome_graph, {
                        "messages": [], "agent_id": "outcome-agent-v1",
                        "action_log": [], "error": None,
                        "proposal_id": proposal_id, "thread_id": thread_id,
                        "final_tally": tally, "process_type": proposal["process_type"],
                        "draft_outcome": None, "decision_type": None,
                        "precedent_data": None, "should_extract_tasks": False,
                        "requires_human_token": False,
                    }, {"configurable": {"thread_id": f"outcome-{proposal_id}"}})
                except Exception as exc:
                    logger.warning("OutcomeAgent enqueue failed: %s", exc)

                # Broadcast proposal_closed
                try:
                    notifier = WebSocketNotifier.get_instance()
                    await notifier.broadcast({
                        "event": "proposal_closed",
                        "agent_id": "deliberation-router",
                        "payload": {
                            "thread_id": thread_id,
                            "proposal_id": proposal_id,
                            "close_reason": result_values.get("close_reason"),
                        },
                    })
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("VotingAgent invocation failed: %s", exc)

    # ── Phase B: WebSocket broadcast — stance_cast ────────────────────────
    if _AGENTS_AVAILABLE:
        try:
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "event": "stance_cast",
                "agent_id": "deliberation-router",
                "payload": {
                    "thread_id": thread_id,
                    "proposal_id": proposal_id,
                    "member_did": req.member_did,
                    "stance": req.stance,
                },
            })
        except Exception:
            pass  # WebSocket unavailable — degrade silently

    return result


# ── Outcomes ──────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/proposals/{proposal_id}/outcome",
             response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
async def state_outcome(
    thread_id: str,
    proposal_id: str,
    req: OutcomeCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> OutcomeResponse:
    """State the outcome of a proposal. Phase B: OutcomeAgent drafts statement."""
    await _require_proposal(conn, proposal_id)

    await conn.execute(
        "UPDATE deliberation_proposals SET status = 'closed', closed_at = NOW() "
        "WHERE id = $1",
        _uuid(proposal_id),
    )

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO decision_outcomes
                (proposal_id, statement, decision_type, stated_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id::text, proposal_id::text, statement, decision_type,
                      precedent_id::text, ai_draft, stated_by,
                      agent_action_id::text, created_at
            """,
            _uuid(proposal_id), req.statement, req.decision_type.value, req.stated_by,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=409, detail="Outcome already stated for this proposal"
        )
    result = OutcomeResponse(**dict(row))

    # ── Phase B: WebSocket broadcast — outcome_stated ─────────────────────
    if _AGENTS_AVAILABLE:
        try:
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "event": "outcome_stated",
                "agent_id": "deliberation-router",
                "payload": {
                    "thread_id": thread_id,
                    "proposal_id": proposal_id,
                    "outcome_id": str(row["id"]),
                    "decision_type": req.decision_type.value,
                },
            })
        except Exception:
            pass  # WebSocket unavailable — degrade silently

    # ── Phase B: Conditionally enqueue TaskAgent for action items ─────────
    if _AGENTS_AVAILABLE:
        try:
            action_keywords = ["should", "must", "will", "assign", "needs to", "action", "task"]
            if any(kw in req.statement.lower() for kw in action_keywords):
                queue = AsyncAgentQueue.get_instance()
                await queue.enqueue(task_graph, {
                    "messages": [], "agent_id": "task-agent-v1",
                    "action_log": [], "error": None,
                    "source_text": req.statement, "thread_id": thread_id,
                    "outcome_id": str(row["id"]),
                    "extracted_tasks": [], "confirmed_tasks": [],
                    "requires_human_token": False,
                }, {"configurable": {"thread_id": f"tasks-{row['id']}"}})
                logger.info("TaskAgent enqueued for outcome %s", row["id"])
        except Exception as exc:
            logger.warning("TaskAgent enqueue failed: %s", exc)

    return result


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/tasks",
             response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    thread_id: str,
    req: TaskCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> TaskResponse:
    """Create a task within a thread."""
    await _require_thread(conn, thread_id)
    row = await conn.fetchrow(
        """
        INSERT INTO thread_tasks
            (thread_id, outcome_id, title, assignee_did, due_date, created_by)
        VALUES ($1, $2, $3, $4, $5::date, $6)
        RETURNING id::text, thread_id::text, outcome_id::text, title,
                  assignee_did, due_date::text, done, done_at, created_by, created_at
        """,
        _uuid(thread_id),
        _uuid(req.outcome_id) if req.outcome_id else None,
        req.title, req.assignee_did, req.due_date, req.created_by,
    )
    result = TaskResponse(**dict(row))

    # ── Phase B: WebSocket broadcast — task_created ───────────────────────
    if _AGENTS_AVAILABLE:
        try:
            notifier = WebSocketNotifier.get_instance()
            await notifier.broadcast({
                "event": "task_created",
                "agent_id": "deliberation-router",
                "payload": {
                    "thread_id": thread_id,
                    "task_id": str(row["id"]),
                    "title": req.title,
                },
            })
        except Exception:
            pass  # WebSocket unavailable — degrade silently

    return result


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    req: TaskUpdateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> TaskResponse:
    """Update a task — mark done, reassign, or update due date."""
    updates = []
    params: list[Any] = []

    if req.done is not None:
        params.append(req.done);        updates.append(f"done = ${len(params)}")
        if req.done:
            updates.append("done_at = NOW()")
        else:
            updates.append("done_at = NULL")
    if req.assignee_did is not None:
        params.append(req.assignee_did); updates.append(f"assignee_did = ${len(params)}")
    if req.due_date is not None:
        params.append(req.due_date);    updates.append(f"due_date = ${len(params)}::date")
    if req.title is not None:
        params.append(req.title);       updates.append(f"title = ${len(params)}")

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    params.append(_uuid(task_id))
    row = await conn.fetchrow(
        f"UPDATE thread_tasks SET {', '.join(updates)} WHERE id = ${len(params)} "
        "RETURNING id::text, thread_id::text, outcome_id::text, title, "
        "assignee_did, due_date::text, done, done_at, created_by, created_at",
        *params,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**dict(row))
