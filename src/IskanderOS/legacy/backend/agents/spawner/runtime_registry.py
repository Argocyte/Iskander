"""
Runtime Registry — In-memory store of active dynamically-spawned agents.

Holds compiled LangGraph instances keyed by agent_id.  This is a process-
local singleton; for multi-node deployments, replace with a Redis-backed
registry.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# agent_id -> {"graph": compiled_graph, "ajd": dict, "deployed_at": datetime}
_ACTIVE_AGENTS: dict[str, dict[str, Any]] = {}


def register_agent(agent_id: str, graph: Any, ajd: dict[str, Any]) -> None:
    """Register a newly spawned agent in the runtime registry."""
    _ACTIVE_AGENTS[agent_id] = {
        "graph": graph,
        "ajd": ajd,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Agent registered: %s", agent_id)


def get_agent(agent_id: str) -> Any | None:
    """Return the compiled graph for *agent_id*, or None."""
    entry = _ACTIVE_AGENTS.get(agent_id)
    return entry["graph"] if entry else None


def get_agent_info(agent_id: str) -> dict[str, Any] | None:
    """Return full registry entry (graph + AJD + metadata) for *agent_id*."""
    return _ACTIVE_AGENTS.get(agent_id)


def list_agents() -> list[dict[str, Any]]:
    """Return metadata for all active agents (excludes graph objects)."""
    return [
        {
            "agent_id": aid,
            "name": entry["ajd"].get("name", aid),
            "deployed_at": entry["deployed_at"],
            "node_sequence": entry["ajd"].get("node_sequence", []),
            "permissions": entry["ajd"].get("permissions", []),
        }
        for aid, entry in _ACTIVE_AGENTS.items()
    ]


def deactivate_agent(agent_id: str) -> bool:
    """Remove an agent from the runtime registry.  Returns True if found."""
    if agent_id in _ACTIVE_AGENTS:
        del _ACTIVE_AGENTS[agent_id]
        logger.info("Agent deactivated: %s", agent_id)
        return True
    return False
