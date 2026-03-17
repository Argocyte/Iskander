"""
Power State Router — receives webhooks from the power_monitor daemon.

POST /power/state
  Called by the power_monitor.py daemon on level transitions.
  Sets a process-global flag that LangGraph agents poll before
  accepting new heavy tasks (inventory fetches, LLM inference).

GET /power/state
  Returns the current power state so agents and the frontend can query it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/power", tags=["power"])

# ── In-process power state (single-node; replace with Redis for multi-node) ───
_current_state: dict = {
    "level":         "normal",
    "battery_pct":   None,
    "on_ac":         True,
    "source":        "unknown",
    "agents_paused": False,
    "keep_alive":    [],
    "updated_at":    None,
}


class PowerStatePayload(BaseModel):
    level:         Literal["normal", "low", "critical"]
    battery_pct:   int | None = Field(default=None)
    on_ac:         bool
    source:        str
    agents_paused: bool
    keep_alive:    list[str] = Field(default_factory=list)


@router.post("/state", summary="Receive power level transition from daemon")
async def receive_power_state(payload: PowerStatePayload) -> dict:
    global _current_state
    _current_state = {
        **payload.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(
        "power_state_updated",
        level=payload.level,
        battery_pct=payload.battery_pct,
        agents_paused=payload.agents_paused,
    )
    return {"ok": True, "state": _current_state}


@router.get("/state", summary="Query current power state")
async def get_power_state() -> dict:
    return _current_state


@router.get("/policy", summary="Query current energy execution policy")
async def get_energy_policy() -> dict:
    """Return the active execution policy based on real-time battery telemetry.

    Uses the HearthInterface (Phase 24) to read hardware state and the
    ResourcePolicyEngine to map it to agent/model/network constraints.
    """
    from backend.energy.hearth_interface import HearthInterface
    from backend.energy.resource_policy_engine import ResourcePolicyEngine

    hearth = HearthInterface.get_instance()
    engine = ResourcePolicyEngine()

    telemetry = hearth.get_telemetry()
    level = hearth.get_state()
    policy = engine.get_policy(level)

    return {
        "telemetry": telemetry,
        "policy": {
            "level": level.name,
            "allowed_agents": policy.allowed_agents,
            "model_id": policy.model_id,
            "network_replication": policy.network_replication,
            "batch_non_urgent": policy.batch_non_urgent,
            "inference_allowed": policy.inference_allowed,
        },
    }


def agents_are_paused() -> bool:
    """
    Helper for agents to check before starting heavy work.

    Usage in any agent node:
        from backend.routers.power import agents_are_paused
        if agents_are_paused():
            return {**state, "error": "paused: low power mode"}
    """
    return bool(_current_state.get("agents_paused", False))
