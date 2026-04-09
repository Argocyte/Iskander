"""
backend.energy — Energy-aware agent scheduling (Phase 2 Energy Gate).

Public API
----------
- ``EnergyLevel``              — Tri-state enum: GREEN, YELLOW, RED.
- ``HearthInterface``          — Singleton hardware battery sensor.
- ``ResourcePolicyEngine``     — Maps energy levels to execution policies.
- ``energy_gated_execution``   — Decorator that blocks calls below a minimum level.
- ``TaskQueuer``               — Priority queue for deferred non-critical tasks.
"""
from __future__ import annotations

from backend.energy.governor import EnergyGateRejected, energy_gated_execution
from backend.energy.hearth_interface import EnergyLevel, HearthInterface
from backend.energy.resource_policy_engine import ExecutionPolicy, ResourcePolicyEngine
from backend.energy.task_queuer import TaskQueuer

__all__ = [
    "EnergyLevel",
    "HearthInterface",
    "ResourcePolicyEngine",
    "ExecutionPolicy",
    "EnergyGateRejected",
    "energy_gated_execution",
    "TaskQueuer",
]
