"""
resource_policy_engine.py — Energy-aware execution policy engine (Phase 2).

Maps each EnergyLevel to an ExecutionPolicy that governs which agents may run,
which LLM model to use, whether network replication is allowed, and whether
non-urgent tasks should be batched.

The ResourcePolicyEngine is a pure state machine with no side effects — it
simply answers "what is permitted at this energy level?"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.energy.hearth_interface import EnergyLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionPolicy:
    """Immutable execution policy for a given energy level."""
    allowed_agents: list[str] = field(default_factory=list)
    model_id: str = "claude-haiku-4-5-20251001"
    network_replication: bool = False
    batch_non_urgent: bool = True
    inference_allowed: bool = False


# ── Pre-built policies ──────────────────────────────────────────────────────

_GREEN_POLICY = ExecutionPolicy(
    allowed_agents=["*"],  # all agents
    model_id="claude-opus-4-6",
    network_replication=True,
    batch_non_urgent=False,
    inference_allowed=True,
)

_YELLOW_POLICY = ExecutionPolicy(
    allowed_agents=["secretary", "treasurer", "steward"],
    model_id="claude-sonnet-4-6",
    network_replication=True,
    batch_non_urgent=True,
    inference_allowed=True,
)

_RED_POLICY = ExecutionPolicy(
    allowed_agents=["heartbeat"],
    model_id="claude-haiku-4-5-20251001",
    network_replication=False,  # SOS broadcast only
    batch_non_urgent=True,
    inference_allowed=False,
)


class ResourcePolicyEngine:
    """
    Pure state-machine that returns the execution policy for a given energy level.

    Usage::

        engine = ResourcePolicyEngine()
        policy = engine.get_policy(EnergyLevel.YELLOW)
        if agent_id in policy.allowed_agents or "*" in policy.allowed_agents:
            ...
    """

    _POLICIES: dict[EnergyLevel, ExecutionPolicy] = {
        EnergyLevel.GREEN: _GREEN_POLICY,
        EnergyLevel.YELLOW: _YELLOW_POLICY,
        EnergyLevel.RED: _RED_POLICY,
    }

    def get_policy(self, level: EnergyLevel) -> ExecutionPolicy:
        """Return the execution policy for *level*."""
        policy = self._POLICIES.get(level)
        if policy is None:
            logger.warning("Unknown energy level %s — defaulting to RED policy", level)
            return _RED_POLICY
        return policy
