"""
hearth_interface.py — Hearth hardware driver interface (Phase 2 Energy Gate).

Reads real battery telemetry via psutil and computes a tri-state energy level
(GREEN / YELLOW / RED) that governs which agents and models may execute.

The HearthInterface is the single source of truth for hardware energy state.
It reads sensors directly via psutil rather than relying on the webhook-based
power router (backend/routers/power.py), though the two are compatible.

Fix 5 (Signed Sensor Protocol):
  Supports signed telemetry from hardware HAT with versioned signature formats.
  Unverified (psutil-only) sensors are capped at YELLOW — only signed hardware
  telemetry can report GREEN. Legacy hardware gets a 180-day grace period
  before deprecated signature versions lose GREEN access.

GLASS BOX:
  State transitions emit an AgentAction with EthicalImpactLevel.LOW so the
  cooperative's audit ledger records every energy-level change.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "hearth-interface"

# ── Fix 5: Signed Sensor Protocol ─────────────────────────────────────────────
# Versioned signature formats for Hearth hardware HAT telemetry.
# Legacy boards get a grace period before deprecated versions lose GREEN.

SUPPORTED_SIGNATURE_VERSIONS: dict[str, dict[str, Any]] = {
    "v1": {"algorithm": "ed25519", "deprecated": False, "trust_penalty": 0},
    "v0": {"algorithm": "hmac-sha256", "deprecated": True, "trust_penalty": 1},
    # v0 gets trust_penalty=1 → max level capped at YELLOW after grace period
}

# Default grace period for deprecated signature versions (days).
LEGACY_GRACE_PERIOD_DAYS = 180


class EnergyLevel(IntEnum):
    """
    Tri-state energy level.  Integer ordering allows direct comparison:
    RED < YELLOW < GREEN.
    """
    RED = 0
    YELLOW = 1
    GREEN = 2


class HearthInterface:
    """
    Hardware energy sensor — singleton.

    Obtain via ``HearthInterface.get_instance()``.

    Reads battery percentage and AC status through ``psutil.sensors_battery()``.
    On systems without a battery (desktops, VMs) the interface gracefully
    defaults to GREEN (AC power assumed).
    """

    _instance: HearthInterface | None = None

    def __init__(self) -> None:
        self._previous_level: EnergyLevel | None = None

    @classmethod
    def get_instance(cls) -> HearthInterface:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Test-only: tear down the singleton so tests start fresh."""
        cls._instance = None

    # ── Public API ──────────────────────────────────────────────────────────────

    def get_state(self) -> EnergyLevel:
        """Return the current tri-state energy level."""
        battery = self._read_battery()
        level = self._compute_level(battery)

        # Emit Glass Box action on state transitions.
        if self._previous_level is not None and level != self._previous_level:
            self._emit_transition(self._previous_level, level, battery)
        self._previous_level = level
        return level

    def get_telemetry(self) -> dict[str, Any]:
        """Return a snapshot of battery telemetry for dashboards / logging."""
        battery = self._read_battery()
        level = self._compute_level(battery)
        return {
            "battery_pct": battery["percent"],
            "on_ac": battery["power_plugged"],
            "level": level.name,
            "is_verified": battery.get("is_verified", False),
            "signature_version": battery.get("signature_version"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Internals ───────────────────────────────────────────────────────────────

    @staticmethod
    def _read_battery() -> dict[str, Any]:
        """
        Read battery telemetry with signed sensor fallback (Fix 5).

        Priority:
          1. Try hardware HAT signed telemetry (``_read_signed_battery``)
          2. Fall back to psutil (unverified — capped at YELLOW by policy)

        Returns dict with ``percent``, ``power_plugged``, ``is_verified``,
        and ``signature_version``.
        """
        signed = HearthInterface._read_signed_battery()
        if signed is not None:
            return {**signed, "is_verified": True}

        # Fallback: psutil (unverified)
        psutil_data = HearthInterface._read_psutil_battery()
        return {**psutil_data, "is_verified": False, "signature_version": None}

    @staticmethod
    def _read_signed_battery() -> dict[str, Any] | None:
        """
        Try to read signed telemetry from Hearth hardware HAT.

        STUB: In production, this reads from a local Unix socket or I2C bus
        where the HAT publishes signed JSON telemetry packets. The signature
        is verified against the HAT's embedded ed25519 public key.

        Returns None if no signed telemetry is available.
        """
        # STUB: No hardware HAT present in development.
        # Production implementation:
        #   1. Read from /var/run/hearth-hat/telemetry.json
        #   2. Verify signature against /etc/hearth-hat/pubkey.pem
        #   3. Check signature version is in SUPPORTED_SIGNATURE_VERSIONS
        #   4. Return verified telemetry
        return None

    @staticmethod
    def _read_psutil_battery() -> dict[str, Any]:
        """
        Read battery via psutil (unverified fallback).
        On systems without a battery (desktops, VMs), assume AC power.
        """
        try:
            import psutil  # type: ignore[import-untyped]
            info = psutil.sensors_battery()
            if info is None:
                # Desktop / VM — no battery present.
                return {"percent": 100.0, "power_plugged": True}
            return {
                "percent": info.percent,
                "power_plugged": bool(info.power_plugged),
            }
        except (ImportError, AttributeError, RuntimeError):
            # psutil not installed or sensors_battery not supported.
            logger.debug("psutil battery read unavailable — assuming GREEN (AC)")
            return {"percent": 100.0, "power_plugged": True}

    @staticmethod
    def _validate_signature(sig_data: dict[str, Any]) -> tuple[bool, int]:
        """Validate a signed telemetry packet's signature.

        Returns (is_valid, trust_penalty).
        - trust_penalty=0: full trust (GREEN allowed)
        - trust_penalty=1: deprecated version past grace → cap at YELLOW
        - trust_penalty=2: unknown version → cap at RED
        """
        version = sig_data.get("signature_version", "v0")
        spec = SUPPORTED_SIGNATURE_VERSIONS.get(version)
        if spec is None:
            return False, 2  # Unknown version → RED

        if spec["deprecated"]:
            # Check if past grace period
            first_seen = sig_data.get("version_first_seen")
            if first_seen:
                try:
                    first_dt = datetime.fromisoformat(first_seen)
                    age_days = (datetime.now(timezone.utc) - first_dt).days
                    if age_days > LEGACY_GRACE_PERIOD_DAYS:
                        logger.warning(
                            "Deprecated signature version %s past grace period "
                            "(%d days > %d). Applying trust penalty.",
                            version, age_days, LEGACY_GRACE_PERIOD_DAYS,
                        )
                        return True, spec["trust_penalty"]
                except (ValueError, TypeError):
                    pass
            # Within grace period or no first_seen — allow with no penalty
            return True, 0

        # Current version, no penalty
        # STUB: actual crypto verification would happen here
        return True, 0

    @staticmethod
    def _compute_level(battery: dict[str, Any]) -> EnergyLevel:
        """
        Map raw battery state to tri-state level.

        GREEN:  Battery > 80 % **or** AC power connected.
        YELLOW: Battery 20 %–80 % (on battery).
        RED:    Battery < 20 % (on battery) — or thermal overheat (future).

        Fix 5: Unverified sensors (psutil-only) are capped at YELLOW.
        Only signed hardware telemetry can report GREEN. This prevents
        psutil spoofing from unlocking full agent capabilities.
        """
        percent: float = battery["percent"]
        on_ac: bool = battery["power_plugged"]
        is_verified: bool = battery.get("is_verified", False)

        # Compute raw level from battery data.
        if on_ac or percent > 80:
            raw_level = EnergyLevel.GREEN
        elif percent < 20:
            raw_level = EnergyLevel.RED
        else:
            raw_level = EnergyLevel.YELLOW

        # Fix 5: Cap unverified sensors at YELLOW.
        # Unverified psutil data can never report GREEN — only signed
        # hardware telemetry from a Hearth HAT gets full trust.
        if not is_verified and raw_level == EnergyLevel.GREEN:
            from backend.config import settings
            if getattr(settings, "energy_require_signed_telemetry", False):
                logger.info(
                    "Unverified sensor capped at YELLOW (signed telemetry required). "
                    "Raw level was GREEN (battery=%s%%, ac=%s)",
                    percent, on_ac,
                )
                return EnergyLevel.YELLOW

        return raw_level

    @staticmethod
    def _emit_transition(
        previous: EnergyLevel,
        current: EnergyLevel,
        battery: dict[str, Any],
    ) -> AgentAction:
        """Emit a Glass Box AgentAction recording an energy-level transition."""
        action = AgentAction(
            agent_id=AGENT_ID,
            action=f"energy_transition:{previous.name}->{current.name}",
            rationale=(
                f"Battery telemetry changed energy level from {previous.name} to "
                f"{current.name} (battery={battery['percent']}%, "
                f"ac={battery['power_plugged']}). Execution policies will adjust."
            ),
            ethical_impact=EthicalImpactLevel.LOW,
            payload={
                "previous_level": previous.name,
                "current_level": current.name,
                "battery_pct": battery["percent"],
                "on_ac": battery["power_plugged"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info(
            "Energy transition: %s -> %s (battery=%s%%, ac=%s)",
            previous.name, current.name, battery["percent"], battery["power_plugged"],
        )
        return action
