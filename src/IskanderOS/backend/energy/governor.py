"""
governor.py — @energy_gated_execution decorator (Phase 2 Energy Gate).

Wraps any sync or async callable so that it is only executed when the
current energy level meets the minimum requirement.  If the gate rejects
the call, an ``EnergyGateRejected`` exception is raised with a diagnostic
message (including a mesh-offload suggestion when RED).

Usage::

    @energy_gated_execution(min_level=EnergyLevel.YELLOW, agent_id="treasurer")
    async def reconcile_ledger():
        ...
"""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable

from backend.energy.hearth_interface import EnergyLevel, HearthInterface
from backend.energy.resource_policy_engine import ResourcePolicyEngine

logger = logging.getLogger(__name__)

_policy_engine = ResourcePolicyEngine()


# ── Custom Exception ────────────────────────────────────────────────────────

class EnergyGateRejected(Exception):
    """Raised when an energy gate blocks execution."""

    def __init__(
        self,
        level: EnergyLevel,
        required_level: EnergyLevel,
        message: str,
    ) -> None:
        self.level = level
        self.required_level = required_level
        self.message = message
        super().__init__(message)


# ── Decorator ───────────────────────────────────────────────────────────────

def energy_gated_execution(
    min_level: EnergyLevel = EnergyLevel.YELLOW,
    agent_id: str = "",
) -> Callable[..., Any]:
    """
    Decorator that gates function execution on energy level.

    Parameters
    ----------
    min_level:
        The minimum ``EnergyLevel`` required to run the decorated function.
    agent_id:
        If provided, the decorator also checks whether this agent is allowed
        under the current execution policy.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:

        def _check_gate() -> None:
            """Shared pre-flight check for sync and async paths."""
            current = HearthInterface.get_instance().get_state()

            # Level comparison: RED(0) < YELLOW(1) < GREEN(2)
            if current < min_level:
                msg = (
                    f"Energy gate rejected: current level {current.name} is below "
                    f"required {min_level.name} for {fn.__qualname__}"
                )
                if current == EnergyLevel.RED:
                    msg += (
                        ". Node is in RED — consider offloading this task to a "
                        "mesh peer with available energy capacity."
                    )
                logger.warning(msg)
                raise EnergyGateRejected(
                    level=current,
                    required_level=min_level,
                    message=msg,
                )

            # Agent allow-list check at YELLOW / RED.
            if agent_id and current != EnergyLevel.GREEN:
                policy = _policy_engine.get_policy(current)
                if "*" not in policy.allowed_agents and agent_id not in policy.allowed_agents:
                    msg = (
                        f"Energy gate rejected: agent '{agent_id}' is not in the "
                        f"allowed list {policy.allowed_agents} at level {current.name}"
                    )
                    if current == EnergyLevel.RED:
                        msg += (
                            ". Node is in RED — consider offloading this task to a "
                            "mesh peer with available energy capacity."
                        )
                    logger.warning(msg)
                    raise EnergyGateRejected(
                        level=current,
                        required_level=min_level,
                        message=msg,
                    )

        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _check_gate()
                return await fn(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                _check_gate()
                return fn(*args, **kwargs)
            return sync_wrapper

    return decorator
