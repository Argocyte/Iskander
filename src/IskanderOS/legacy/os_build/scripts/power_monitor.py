#!/usr/bin/env python3
"""
power_monitor.py — Power-Aware Graceful Degradation Daemon

Monitors system power/battery state and sends webhooks to the
Iskander backend to pause or resume heavy LLM agents.

Designed for off-grid solar cooperatives where compute resources
are constrained by available renewable energy.

Thresholds:
  CRITICAL (<= 10%) : Pause ALL agents. Keep only ActivityPub federation alive.
  LOW      (<= 25%) : Pause inventory + steward background agents. Keep governance.
  NORMAL   (>  25%) : Resume all agents.

The webhook hits POST /power/state on the FastAPI backend, which
LangGraph agents poll to decide whether to accept new tasks.

Runs as: iskander-power-monitor.service
Reads battery from: /sys/class/power_supply/BAT*/
AC status from:     /sys/class/power_supply/AC*/online
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [power-monitor] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration (override via environment) ──────────────────────────────────
API_BASE         = os.environ.get("ISKANDER_API_URL",   "http://localhost:8000")
POLL_INTERVAL    = int(os.environ.get("POWER_POLL_SECS", "30"))
THRESHOLD_LOW    = int(os.environ.get("POWER_LOW_PCT",   "25"))
THRESHOLD_CRIT   = int(os.environ.get("POWER_CRIT_PCT",  "10"))


class PowerLevel(str, Enum):
    NORMAL   = "normal"
    LOW      = "low"
    CRITICAL = "critical"


@dataclass
class PowerState:
    level:          PowerLevel
    battery_pct:    int | None   # None if no battery (AC-only server)
    on_ac:          bool
    source:         str          # "battery" | "ac" | "unknown"


# ── Battery reading ────────────────────────────────────────────────────────────

def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def read_power_state() -> PowerState:
    """
    Read power state from Linux sysfs power_supply subsystem.
    Works for laptops, SBCs with UPS hats (Raspberry Pi), and
    systems with ACPI battery reporting.
    """
    ps_root = Path("/sys/class/power_supply")

    # ── AC adapter ────────────────────────────────────────────────────────────
    on_ac = True  # default: assume AC if no battery info
    for ac_path in ps_root.glob("AC*"):
        online = _read_int(ac_path / "online")
        if online is not None:
            on_ac = bool(online)
            break

    # ── Battery ───────────────────────────────────────────────────────────────
    battery_pct: int | None = None
    for bat_path in ps_root.glob("BAT*"):
        cap = _read_int(bat_path / "capacity")
        if cap is not None:
            battery_pct = cap
            break

    # ── Determine level ───────────────────────────────────────────────────────
    if battery_pct is None or on_ac:
        # AC-only or reading unavailable — treat as normal
        level = PowerLevel.NORMAL
        source = "ac" if on_ac else "unknown"
    else:
        source = "battery"
        if battery_pct <= THRESHOLD_CRIT:
            level = PowerLevel.CRITICAL
        elif battery_pct <= THRESHOLD_LOW:
            level = PowerLevel.LOW
        else:
            level = PowerLevel.NORMAL

    return PowerState(level=level, battery_pct=battery_pct, on_ac=on_ac, source=source)


# ── Webhook ────────────────────────────────────────────────────────────────────

def _post_webhook(endpoint: str, payload: dict) -> bool:
    url  = f"{API_BASE}{endpoint}"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except urllib.error.URLError as exc:
        log.warning("webhook_failed url=%s error=%s", url, exc)
        return False


def send_power_event(state: PowerState) -> None:
    payload = {
        "level":       state.level.value,
        "battery_pct": state.battery_pct,
        "on_ac":       state.on_ac,
        "source":      state.source,
        "agents_paused": state.level in (PowerLevel.LOW, PowerLevel.CRITICAL),
        "keep_alive":  ["federation", "governance"] if state.level == PowerLevel.LOW
                       else (["federation"] if state.level == PowerLevel.CRITICAL else []),
    }
    ok = _post_webhook("/power/state", payload)
    if ok:
        log.info("power_event_sent level=%s battery=%s%%", state.level.value, state.battery_pct)
    else:
        log.warning("power_event_delivery_failed — backend may be starting up")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    log.info(
        "power_monitor_starting poll_interval=%ds low=%d%% critical=%d%%",
        POLL_INTERVAL, THRESHOLD_LOW, THRESHOLD_CRIT,
    )

    last_level: PowerLevel | None = None

    while True:
        state = read_power_state()

        # Only emit webhook on level transitions to avoid flooding the API
        if state.level != last_level:
            log.info(
                "power_level_changed %s -> %s battery=%s%% ac=%s",
                last_level, state.level.value, state.battery_pct, state.on_ac,
            )
            send_power_event(state)
            last_level = state.level

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
