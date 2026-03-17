#!/usr/bin/env python3
"""
permacomputing_monitor.py — Off-Grid Power State Monitor & Graceful Degradation Daemon

License: CERN-OHL-S v2 / MIT (software component)
Managed by: systemd unit hearth-permacomputing.service
Runs as: hearth-hw (dedicated non-root service user)

PHILOSOPHY:
    A cooperative Hearth node may operate on solar, battery, or grid power.
    When renewable energy is scarce, the node must de-prioritize heavy computation
    and signal federated sister nodes so they can redistribute work — not crash.
    This is permacomputing: operating within ecological and energetic constraints
    with dignity rather than fighting against them.

ENFORCED BEHAVIORS (voltage thresholds configurable via environment):
    BATTERY_WARN_V  (default 11.5V, 12V lead-acid ~50% SoC)
        → Emit "Low Power Mode" warning to ActivityPub Router webhook.
        → Pause the COGS cost calculator agent.
        → Log to systemd journal.

    BATTERY_CRITICAL_V  (default 10.8V, 12V lead-acid ~20% SoC)
        → Pause all background agents except presence daemon.
        → Broadcast emergency status to federated nodes.
        → Reduce CPU performance state via cpupower.

    BATTERY_SHUTDOWN_V  (default 10.2V, 12V lead-acid ~5% SoC — prevent deep discharge)
        → Initiate graceful OS shutdown sequence.
        → Final ActivityPub broadcast: node going offline.

FAILURE POLICY:
    If INA3221 fails to initialize (hardware absent or I2C error), daemon writes
    a sovereignty lock and refuses all new background agent launches until a human
    verifies the hardware. The node continues serving existing requests but will not
    start new heavy tasks that could drain an unmeasured battery.

Dependencies:
    pip install smbus2 requests sdnotify
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from enum import Enum, auto
from typing import Optional

import requests

try:
    import sdnotify
    SDNOTIFY_AVAILABLE = True
except ImportError:
    SDNOTIFY_AVAILABLE = False

from ina3221_poller import INA3221, PowerSnapshot

log = logging.getLogger("hearth.permacomputing")

# ── Configuration ─────────────────────────────────────────────────────────────

I2C_BUS              = int(os.environ.get("HEARTH_I2C_BUS",    "1"))
POLL_INTERVAL_SEC    = float(os.environ.get("HEARTH_POWER_POLL_SEC", "30"))

# Voltage thresholds (CH2 bus voltage = solar/battery rail)
BATTERY_WARN_V      = float(os.environ.get("HEARTH_BATT_WARN_V",     "11.5"))
BATTERY_CRITICAL_V  = float(os.environ.get("HEARTH_BATT_CRITICAL_V", "10.8"))
BATTERY_SHUTDOWN_V  = float(os.environ.get("HEARTH_BATT_SHUTDOWN_V", "10.2"))

# ActivityPub Router webhook (Iskander OS internal service)
ACTIVITYPUB_WEBHOOK = os.environ.get(
    "HEARTH_ACTIVITYPUB_WEBHOOK", "http://127.0.0.1:8080/internal/power-status"
)

# COGS agent control endpoint
COGS_AGENT_URL = os.environ.get(
    "HEARTH_COGS_URL", "http://127.0.0.1:8124/agents/cogs"
)

# Background agent orchestrator endpoint (LangGraph)
LANGGRAPH_API_URL = os.environ.get(
    "HEARTH_LANGGRAPH_URL", "http://127.0.0.1:8123"
)

# Sovereignty lock path (shared with hardware_sovereignty_daemon)
SOVEREIGNTY_LOCK_PATH = os.environ.get(
    "HEARTH_SOVEREIGNTY_LOCK", "/run/iskander/sovereignty.lock"
)


# ── Power state machine ───────────────────────────────────────────────────────

class PowerLevel(Enum):
    NORMAL   = auto()   # Above BATTERY_WARN_V
    WARNING  = auto()   # Below BATTERY_WARN_V
    CRITICAL = auto()   # Below BATTERY_CRITICAL_V
    SHUTDOWN = auto()   # Below BATTERY_SHUTDOWN_V


def _classify_voltage(volts: float) -> PowerLevel:
    if volts <= BATTERY_SHUTDOWN_V:
        return PowerLevel.SHUTDOWN
    elif volts <= BATTERY_CRITICAL_V:
        return PowerLevel.CRITICAL
    elif volts <= BATTERY_WARN_V:
        return PowerLevel.WARNING
    else:
        return PowerLevel.NORMAL


# ── ActivityPub broadcast ─────────────────────────────────────────────────────

def broadcast_power_status(level: PowerLevel, volts: float, current_ma: float) -> None:
    """
    Send a power status update to the Iskander OS ActivityPub Router.
    The router federates this status to all registered sister nodes.
    """
    payload = {
        "type": "PowerStatus",
        "level": level.name,
        "battery_voltage_v": round(volts, 3),
        "current_ma": round(current_ma, 1),
        "timestamp": time.time(),
    }
    try:
        resp = requests.post(ACTIVITYPUB_WEBHOOK, json=payload, timeout=5)
        resp.raise_for_status()
        log.info(
            "ActivityPub broadcast: %s | %.3fV | %.1fmA", level.name, volts, current_ma
        )
    except requests.RequestException as exc:
        log.warning("ActivityPub broadcast failed (router offline?): %s", exc)


# ── Agent control ─────────────────────────────────────────────────────────────

def _post_agent_control(url: str, action: str, reason: str) -> None:
    try:
        requests.post(url, json={"action": action, "reason": reason}, timeout=3)
        log.info("Agent control: %s → %s (%s)", url, action, reason)
    except requests.RequestException as exc:
        log.warning("Agent control request failed: %s", exc)


def pause_cogs_agent(reason: str) -> None:
    """Pause the COGS (cost-of-goods-sold) calculator background agent."""
    _post_agent_control(f"{COGS_AGENT_URL}/pause", "pause", reason)


def resume_cogs_agent(reason: str) -> None:
    _post_agent_control(f"{COGS_AGENT_URL}/resume", "resume", reason)


def pause_all_background_agents(reason: str) -> None:
    """
    Send a pause signal to all non-critical LangGraph background agents.
    The orchestrator is responsible for determining which agents are 'critical'
    (presence daemon, health monitor) vs. 'background' (COGS, summarizers, etc.)
    """
    _post_agent_control(
        f"{LANGGRAPH_API_URL}/admin/pause-background", "pause_background", reason
    )


def resume_all_background_agents(reason: str) -> None:
    _post_agent_control(
        f"{LANGGRAPH_API_URL}/admin/resume-background", "resume_background", reason
    )


def reduce_cpu_performance() -> None:
    """Set CPU governor to powersave mode to reduce power draw."""
    try:
        subprocess.run(
            ["cpupower", "frequency-set", "--governor", "powersave"],
            check=False, capture_output=True,
        )
        log.warning("CPU governor set to powersave.")
    except FileNotFoundError:
        log.warning("cpupower not found — skipping CPU performance reduction.")


def restore_cpu_performance() -> None:
    """Restore CPU governor to ondemand mode."""
    try:
        subprocess.run(
            ["cpupower", "frequency-set", "--governor", "ondemand"],
            check=False, capture_output=True,
        )
        log.info("CPU governor restored to ondemand.")
    except FileNotFoundError:
        pass


def initiate_graceful_shutdown() -> None:
    """Schedule OS shutdown in 60 seconds to allow final broadcasts."""
    log.critical(
        "BATTERY CRITICALLY LOW (%.2f V threshold). "
        "Initiating graceful shutdown in 60 seconds.",
        BATTERY_SHUTDOWN_V,
    )
    subprocess.run(
        ["shutdown", "--poweroff", "+1", "Iskander Hearth: battery depleted"],
        check=False,
    )


# ── Sovereignty lock ──────────────────────────────────────────────────────────

def _write_sovereignty_lock(reason: str) -> None:
    lock_dir = os.path.dirname(SOVEREIGNTY_LOCK_PATH)
    os.makedirs(lock_dir, exist_ok=True)
    with open(SOVEREIGNTY_LOCK_PATH, "w") as f:
        f.write(f"LOCKED: {reason}\nTimestamp: {time.time()}\n")
    log.critical(
        "SOVEREIGNTY LOCK WRITTEN: %s — hardware unverified, new agents suspended.",
        SOVEREIGNTY_LOCK_PATH,
    )


# ── State transition logic ────────────────────────────────────────────────────

def _handle_transition(
    prev: PowerLevel,
    curr: PowerLevel,
    snap: PowerSnapshot,
) -> None:
    """Apply OS-level actions when power level changes."""
    volts    = snap.solar_battery_voltage()
    curr_ma  = snap.ch2.current_ma

    # Always broadcast on any level change
    broadcast_power_status(curr, volts, curr_ma)

    if curr == PowerLevel.NORMAL and prev != PowerLevel.NORMAL:
        log.info("Power restored to NORMAL (%.3fV). Resuming agents.", volts)
        resume_cogs_agent("battery_restored_normal")
        resume_all_background_agents("battery_restored_normal")
        restore_cpu_performance()

    elif curr == PowerLevel.WARNING and prev == PowerLevel.NORMAL:
        log.warning("Power entered WARNING state (%.3fV). Pausing COGS agent.", volts)
        pause_cogs_agent("battery_low_warning")

    elif curr == PowerLevel.CRITICAL and prev in (PowerLevel.NORMAL, PowerLevel.WARNING):
        log.warning(
            "Power entered CRITICAL state (%.3fV). Pausing background agents + reducing CPU.",
            volts,
        )
        pause_cogs_agent("battery_critical")
        pause_all_background_agents("battery_critical")
        reduce_cpu_performance()

    elif curr == PowerLevel.SHUTDOWN:
        log.critical("Power entered SHUTDOWN state (%.3fV).", volts)
        pause_all_background_agents("battery_pre_shutdown")
        # Final broadcast happens in broadcast_power_status() above
        initiate_graceful_shutdown()


# ── Main daemon loop ──────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    log.info("Permacomputing Monitor starting.")
    log.info(
        "Thresholds — WARN: %.1fV  CRITICAL: %.1fV  SHUTDOWN: %.1fV  Poll: %.0fs",
        BATTERY_WARN_V, BATTERY_CRITICAL_V, BATTERY_SHUTDOWN_V, POLL_INTERVAL_SEC,
    )

    if SDNOTIFY_AVAILABLE:
        notifier = sdnotify.SystemdNotifier()
    else:
        notifier = None

    sensor: Optional[INA3221] = None
    try:
        sensor = INA3221(i2c_bus=I2C_BUS)
    except RuntimeError as exc:
        log.critical(
            "INA3221 initialization FAILED: %s\n"
            "The power monitoring subsystem cannot protect against battery deep-discharge.\n"
            "Writing sovereignty lock — new background agents suspended until hardware verified.",
            exc,
        )
        _write_sovereignty_lock(reason="ina3221_init_failure")
        if notifier:
            notifier.notify("READY=1")
            notifier.notify("STATUS=DEGRADED: INA3221 unavailable. Sovereignty lock active.")
        while True:
            time.sleep(60)

    if notifier:
        notifier.notify("READY=1")
        notifier.notify("STATUS=Active: monitoring battery/solar rail.")

    prev_level = PowerLevel.NORMAL

    try:
        while True:
            try:
                snap = sensor.read_all()
                volts = snap.solar_battery_voltage()
                curr_level = _classify_voltage(volts)

                log.debug(
                    "CH2 solar/batt: %.4fV %.1fmA | level=%s",
                    volts, snap.ch2.current_ma, curr_level.name,
                )

                if curr_level != prev_level:
                    _handle_transition(prev_level, curr_level, snap)
                    prev_level = curr_level

                    if notifier:
                        notifier.notify(
                            f"STATUS={curr_level.name}: {volts:.3f}V {snap.ch2.current_ma:.1f}mA"
                        )

            except Exception as exc:
                log.error("INA3221 read error: %s — will retry.", exc)

            time.sleep(POLL_INTERVAL_SEC)

    finally:
        if sensor:
            sensor.close()


if __name__ == "__main__":
    main()
