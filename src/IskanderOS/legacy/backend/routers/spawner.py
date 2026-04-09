"""
/agents — AJD spawning, voting, invocation, and deactivation.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.spawner.ajd_schema import AJDSpec, AJDVote
from backend.agents.spawner.runtime_registry import (
    deactivate_agent,
    get_agent,
    get_agent_info,
    list_agents,
)
from backend.agents.spawner.spawner_graph import spawner_graph
from backend.auth.dependencies import AuthenticatedUser, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ── Request / Response schemas ────────────────────────────────────────────────


class ProposeRequest(BaseModel):
    ajd: AJDSpec


class ProposeResponse(BaseModel):
    thread_id: str
    status: str
    agent_id: str
    action_log: list[dict[str, Any]] = []
    error: str | None = None


class VoteRequest(BaseModel):
    thread_id: str
    voter_did: str
    approved: bool
    reason: str = ""


class InvokeRequest(BaseModel):
    input_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial state dict to pass to the spawned agent graph.",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/propose", response_model=ProposeResponse)
async def propose_agent(
    req: ProposeRequest,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Submit an AJD for democratic approval.  Graph pauses at human_vote."""
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "agent_id": "spawner-engine-v1",
        "action_log": [],
        "error": None,
        "ajd_spec": req.ajd.model_dump(mode="json"),
        "votes": [],
        "quorum_required": 1,  # TODO: derive from cooperative bylaws.
        "quorum_reached": False,
        "deployment_result": None,
    }

    try:
        spawner_graph.invoke(initial_state, config=config)
        snapshot = spawner_graph.get_state(config)
        state = snapshot.values
    except Exception as exc:
        logger.exception("Spawner proposal failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if state.get("error"):
        raise HTTPException(status_code=422, detail=state["error"])

    return ProposeResponse(
        thread_id=thread_id,
        status="pending_vote",
        agent_id=req.ajd.agent_id,
        action_log=state.get("action_log", []),
    )


@router.post("/vote", response_model=ProposeResponse)
async def vote_on_agent(
    req: VoteRequest,
    user: AuthenticatedUser = Depends(require_role("worker-owner", "steward")),
):
    """Cast a vote on an AJD proposal.  Resumes graph on approval."""
    config = {"configurable": {"thread_id": req.thread_id}}

    try:
        snapshot = spawner_graph.get_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Thread {req.thread_id} not found.")

    state = snapshot.values
    votes = state.get("votes", [])
    votes.append({
        "voter_did": req.voter_did,
        "approved": req.approved,
        "reason": req.reason,
    })

    quorum = state.get("quorum_required", 1)
    votes_for = sum(1 for v in votes if v["approved"])

    if votes_for < quorum:
        # Update votes but don't resume graph yet.
        spawner_graph.update_state(
            config,
            {"votes": votes, "quorum_reached": False},
            as_node="human_vote",
        )
        return ProposeResponse(
            thread_id=req.thread_id,
            status=f"pending_vote ({votes_for}/{quorum})",
            agent_id=state.get("ajd_spec", {}).get("agent_id", "unknown"),
            action_log=state.get("action_log", []),
        )

    # Quorum reached — resume graph.
    spawner_graph.update_state(
        config,
        {"votes": votes, "quorum_reached": True},
        as_node="human_vote",
    )
    spawner_graph.invoke(None, config=config)
    updated = spawner_graph.get_state(config).values

    return ProposeResponse(
        thread_id=req.thread_id,
        status="deployed" if not updated.get("error") else "failed",
        agent_id=state.get("ajd_spec", {}).get("agent_id", "unknown"),
        action_log=updated.get("action_log", []),
        error=updated.get("error"),
    )


@router.get("/")
async def list_active_agents():
    """List all active dynamically-spawned agents."""
    return {"agents": list_agents()}


@router.post("/{agent_id}/invoke")
async def invoke_agent(agent_id: str, req: InvokeRequest):
    """Invoke a dynamically spawned agent with an input state."""
    graph = get_agent(agent_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found in registry.")

    initial_state = {
        "messages": [],
        "agent_id": agent_id,
        "action_log": [],
        "error": None,
        **req.input_state,
    }

    try:
        result = graph.invoke(initial_state)
    except Exception as exc:
        logger.exception("Spawned agent '%s' failed: %s", agent_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "agent_id": agent_id,
        "result": {k: v for k, v in result.items() if k != "messages"},
        "action_log": result.get("action_log", []),
    }


@router.delete("/{agent_id}")
async def revoke_agent(
    agent_id: str,
    user: AuthenticatedUser = Depends(require_role("steward")),
):
    """Deactivate (revoke) a spawned agent."""
    removed = deactivate_agent(agent_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return {"agent_id": agent_id, "status": "revoked"}
