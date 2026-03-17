"""
AJD Spawner Graph — Democratic workflow for creating new cooperative agents.

Graph: propose_ajd → [HITL: human_vote] → compile_agent_limits → deploy_agent → END

When a cooperative wants to "hire" a new AI agent, they submit an Agent Job
Description (AJD).  The spawner validates it, pauses for democratic vote,
then compiles a bounded LangGraph from the node registry and deploys it.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from backend.agents.spawner.ajd_schema import AJDSpec
from backend.agents.spawner.node_registry import resolve_nodes
from backend.agents.spawner.runtime_registry import register_agent
from backend.agents.state import AgentState
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "spawner-engine-v1"


# ── Spawner state ─────────────────────────────────────────────────────────────


class SpawnerState(AgentState):
    """State for the AJD spawning workflow."""

    ajd_spec: dict[str, Any] | None
    votes: list[dict[str, Any]]
    quorum_required: int
    quorum_reached: bool
    deployment_result: dict[str, Any] | None


# ── Node 1: Validate the proposed AJD ─────────────────────────────────────────


def propose_ajd(state: SpawnerState) -> dict[str, Any]:
    """Validate the AJD spec: check all node names exist in the registry."""
    raw = state.get("ajd_spec")
    if not raw:
        return {**state, "error": "No AJD specification provided."}

    try:
        ajd = AJDSpec(**raw)
    except Exception as exc:
        return {**state, "error": f"Invalid AJD spec: {exc}"}

    # Validate all node names resolve.
    try:
        resolve_nodes(ajd.node_sequence)
    except ValueError as exc:
        return {**state, "error": str(exc)}

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"AJD proposed: '{ajd.name}' ({ajd.agent_id})",
        rationale=(
            "New agent proposal submitted for democratic review.  "
            f"Node sequence: {ajd.node_sequence}.  "
            f"Permissions: {[p.value for p in ajd.permissions]}."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload=ajd.model_dump(mode="json"),
    )

    return {
        **state,
        "ajd_spec": ajd.model_dump(mode="json"),
        "votes": [],
        "quorum_reached": False,
        "action_log": state.get("action_log", []) + [action.model_dump()],
        "error": None,
    }


# ── Node 2: HITL breakpoint for democratic vote ──────────────────────────────


def human_vote(state: SpawnerState) -> dict[str, Any]:
    """No-op HITL breakpoint.  Graph suspends here for member voting.

    Votes are accumulated externally via the spawner router's
    ``POST /agents/vote`` endpoint.  The graph resumes after quorum.
    """
    return state


# ── Node 3: Compile agent from AJD ───────────────────────────────────────────


def compile_agent_limits(state: SpawnerState) -> dict[str, Any]:
    """Build a bounded LangGraph from the approved AJD node sequence.

    The compiled graph enforces:
    - Only registered node functions (no arbitrary code).
    - HITL breakpoints at any ``hitl_breakpoint`` node.
    - Ethical ceiling from the AJD (enforced at prompt level, not graph level).
    """
    raw_ajd = state.get("ajd_spec", {}) or {}

    try:
        ajd = AJDSpec(**raw_ajd)
        nodes = resolve_nodes(ajd.node_sequence)
    except Exception as exc:
        return {**state, "error": f"Compilation failed: {exc}"}

    # Build the StateGraph dynamically.
    g = StateGraph(AgentState)
    for name, func in nodes:
        g.add_node(name, func)

    # Wire edges sequentially.
    g.set_entry_point(nodes[0][0])
    for i in range(len(nodes) - 1):
        g.add_edge(nodes[i][0], nodes[i + 1][0])
    g.add_edge(nodes[-1][0], END)

    # HITL breakpoints at any node named *hitl_breakpoint* or *human_*.
    interrupt_nodes = [
        name for name, _ in nodes
        if name == "hitl_breakpoint" or name.startswith("human_")
    ]

    compiled = g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=interrupt_nodes or None,
    )

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Compiled agent '{ajd.agent_id}' from {len(nodes)} nodes",
        rationale=(
            f"AJD approved by quorum.  Graph compiled with nodes: "
            f"{[n for n, _ in nodes]}.  HITL breakpoints: {interrupt_nodes}."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={
            "agent_id": ajd.agent_id,
            "node_count": len(nodes),
            "hitl_breakpoints": interrupt_nodes,
        },
    )

    return {
        **state,
        "deployment_result": {
            "agent_id": ajd.agent_id,
            "compiled": True,
            "_graph": compiled,  # Transient — not serializable.
        },
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Node 4: Deploy agent to runtime registry ─────────────────────────────────


def deploy_agent(state: SpawnerState) -> dict[str, Any]:
    """Register the compiled graph in the runtime registry."""
    result = state.get("deployment_result", {}) or {}
    graph = result.get("_graph")
    ajd_raw = state.get("ajd_spec", {}) or {}
    agent_id = ajd_raw.get("agent_id", "unknown")

    if graph is None:
        return {**state, "error": "No compiled graph to deploy."}

    register_agent(agent_id, graph, ajd_raw)

    action = AgentAction(
        agent_id=AGENT_ID,
        action=f"Deployed agent '{agent_id}' to runtime registry",
        rationale=(
            "Agent is now active and invokable via POST /agents/{agent_id}/invoke.  "
            "Deployment logged per Glass Box Protocol."
        ),
        ethical_impact=EthicalImpactLevel.HIGH,
        payload={"agent_id": agent_id, "status": "active"},
    )

    # Clean transient graph ref from serializable state.
    clean_result = {k: v for k, v in result.items() if k != "_graph"}
    clean_result["status"] = "active"

    return {
        **state,
        "deployment_result": clean_result,
        "action_log": state.get("action_log", []) + [action.model_dump()],
    }


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_spawner_graph():
    """Compile the AJD Spawner LangGraph with HITL voting breakpoint."""
    g = StateGraph(SpawnerState)
    g.add_node("propose_ajd", propose_ajd)
    g.add_node("human_vote", human_vote)
    g.add_node("compile_agent_limits", compile_agent_limits)
    g.add_node("deploy_agent", deploy_agent)

    g.set_entry_point("propose_ajd")
    g.add_edge("propose_ajd", "human_vote")
    g.add_edge("human_vote", "compile_agent_limits")
    g.add_edge("compile_agent_limits", "deploy_agent")
    g.add_edge("deploy_agent", END)

    return g.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_vote"],
    )


spawner_graph = build_spawner_graph()
