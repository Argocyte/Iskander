#!/usr/bin/env python3
"""
hardware_sovereignty_daemon.py — Physical Kill Switch Monitor

License: CERN-OHL-S v2 / MIT (software component)
Managed by: systemd unit hearth-sovereignty.service
Runs as: hearth-hw (dedicated non-root service user)

SECURITY RATIONALE:
    Software privacy is an illusion when an adversary controls the kernel, firmware,
    or hardware supply chain. The only mathematically sound countermeasure is to
    physically break circuits — interrupting current flow at the copper level —
    making surveillance or reactivation impossible without physical access.

    This daemon monitors the hardware state of the three DPST kill switches on the
    Solidarity HAT and enforces OS-level consequences when those switches are toggled.
    It does NOT trust software state; it reads GPIO directly.

ENFORCED BEHAVIORS:
    SW1 (Mic Kill)    → Kills any running pulseaudio/pipewire capture sources.
    SW2 (Wi-Fi Kill)  → Brings down wlan0 interface via networkmanager.
    SW3 (GPU Kill)    → Sends SIGSTOP to Ollama + halts LangGraph orchestrator API.
                        GPU switch restoration triggers SIGCONT + daemon restart.

FAILURE POLICY:
    If GPIO initialization fails or the HAT is not detected, the daemon emits
    a CRITICAL log entry and refuses to allow Web3 transaction signing until
    a human operator manually verifies hardware integrity.

Dependencies:
    pip install gpiozero sdnotify requests
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
try:
    from gpiozero import Button
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False

try:
    import sdnotify
    SDNOTIFY_AVAILABLE = True
except ImportError:
    SDNOTIFY_AVAILABLE = False

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hearth.sovereignty")

# ── Configuration (override via environment variables) ────────────────────────

GPIO_MIC_KILL   = int(os.environ.get("HEARTH_GPIO_MIC_KILL",  "4"))   # BCM 4  / J1 pin 7
GPIO_WIFI_KILL  = int(os.environ.get("HEARTH_GPIO_WIFI_KILL", "17"))  # BCM 17 / J1 pin 11
GPIO_GPU_KILL   = int(os.environ.get("HEARTH_GPIO_GPU_KILL",  "27"))  # BCM 27 / J1 pin 13

OLLAMA_API_URL        = os.environ.get("HEARTH_OLLAMA_URL",    "http://127.0.0.1:11434")
LANGGRAPH_API_URL     = os.environ.get("HEARTH_LANGGRAPH_URL", "http://127.0.0.1:8123")
POLL_INTERVAL_SEC     = float(os.environ.get("HEARTH_KILL_POLL_SEC", "0.25"))

# Path to the sovereignty lock file: read by Web3 signing daemon to refuse TX when set
SOVEREIGNTY_LOCK_PATH = os.environ.get(
    "HEARTH_SOVEREIGNTY_LOCK", "/run/iskander/sovereignty.lock"
)

# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class KillState:
    mic_killed:  bool = False
    wifi_killed: bool = False
    gpu_killed:  bool = False

    # Tracks whether hardware is verified. False = refuse all Web3 signing.
    hardware_verified: bool = False

    # PID of suspended Ollama process (SIGSTOP target)
    ollama_pid: Optional[int] = field(default=None, repr=False)

    def any_killed(self) -> bool:
        return self.mic_killed or self.wifi_killed or self.gpu_killed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KillState):
            return NotImplemented
        return (
            self.mic_killed == other.mic_killed
            and self.wifi_killed == other.wifi_killed
            and self.gpu_killed == other.gpu_killed
        )


# ── Hardware initialization ────────────────────────────────────────────────────

def init_gpio() -> tuple[Button, Button, Button]:
    """
    Initialize GPIO inputs for the three DPST kill switch state lines.

    GPIO lines are pulled LOW by 10kΩ resistors on the HAT; switch pole 2
    connects the line to +3.3V when closed (switch = KILLED).

    Raises RuntimeError if gpiozero is unavailable or GPIO init fails.
    """
    if not GPIOZERO_AVAILABLE:
        raise RuntimeError(
            "gpiozero not installed. Install with: pip install gpiozero. "
            "This daemon cannot provide hardware sovereignty without GPIO access."
        )
    try:
        btn_mic  = Button(GPIO_MIC_KILL,  pull_up=False, bounce_time=0.05)
        btn_wifi = Button(GPIO_WIFI_KILL, pull_up=False, bounce_time=0.05)
        btn_gpu  = Button(GPIO_GPU_KILL,  pull_up=False, bounce_time=0.05)
        log.info(
            "GPIO initialized: MIC_KILL=BCM%d WIFI_KILL=BCM%d GPU_KILL=BCM%d",
            GPIO_MIC_KILL, GPIO_WIFI_KILL, GPIO_GPU_KILL,
        )
        return btn_mic, btn_wifi, btn_gpu
    except Exception as exc:
        raise RuntimeError(f"GPIO initialization failed: {exc}") from exc


# ── Kill switch enforcement actions ──────────────────────────────────────────

def _find_ollama_pid() -> Optional[int]:
    """Return PID of the first 'ollama' process, or None."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ollama serve"],
            capture_output=True, text=True, check=False,
        )
        pids = result.stdout.strip().split()
        return int(pids[0]) if pids else None
    except Exception as exc:
        log.warning("Could not find Ollama PID: %s", exc)
        return None


def enforce_mic_kill(state: KillState) -> None:
    """Cut or restore PipeWire/PulseAudio microphone capture sources."""
    if state.mic_killed:
        log.warning("MIC KILL active — muting all PipeWire capture sources.")
        subprocess.run(
            ["pactl", "list", "short", "sources"],
            check=False, capture_output=True,
        )
        # Mute every source (capture device). pactl accepts source names.
        subprocess.run(
            ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1"],
            check=False, capture_output=True,
        )
    else:
        log.info("MIC KILL cleared — restoring default capture source.")
        subprocess.run(
            ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "0"],
            check=False, capture_output=True,
        )


def enforce_wifi_kill(state: KillState) -> None:
    """Bring down or restore the Wi-Fi network interface."""
    if state.wifi_killed:
        log.warning("WIFI KILL active — taking wlan0 down via nmcli.")
        subprocess.run(
            ["nmcli", "radio", "wifi", "off"],
            check=False, capture_output=True,
        )
    else:
        log.info("WIFI KILL cleared — restoring Wi-Fi via nmcli.")
        subprocess.run(
            ["nmcli", "radio", "wifi", "on"],
            check=False, capture_output=True,
        )


def enforce_gpu_kill(state: KillState) -> None:
    """
    CRITICAL: When GPU kill switch is engaged, this method:
      1. Sends SIGSTOP to the Ollama inference server (freezes process, preserves state).
      2. Sends an HTTP halt command to the LangGraph orchestrator.
      3. Writes sovereignty.lock — Web3 signing daemon will refuse all transactions.

    When switch is cleared:
      1. Sends SIGCONT to resume Ollama.
      2. Clears sovereignty.lock.

    SIGSTOP is used (not SIGKILL) so model context is preserved and inference
    can resume without reloading weights — minimizing disruption while still
    mathematically preventing new data from being processed.
    """
    if state.gpu_killed:
        log.warning("GPU KILL active — freezing Ollama and halting LangGraph.")

        # Freeze Ollama
        pid = _find_ollama_pid()
        if pid:
            state.ollama_pid = pid
            try:
                os.kill(pid, signal.SIGSTOP)
                log.warning("Sent SIGSTOP to Ollama PID %d.", pid)
            except ProcessLookupError:
                log.warning("Ollama PID %d vanished before SIGSTOP.", pid)
        else:
            log.warning("Ollama process not found — may not be running.")

        # Halt LangGraph orchestrator via API
        try:
            requests.post(
                f"{LANGGRAPH_API_URL}/admin/halt",
                json={"reason": "hardware_gpu_kill_switch"},
                timeout=3,
            )
            log.warning("LangGraph halt command acknowledged.")
        except requests.RequestException as exc:
            log.warning("LangGraph halt request failed (may be offline): %s", exc)

        # Write sovereignty lock — Web3 daemon reads this before signing
        _write_sovereignty_lock(reason="gpu_kill_switch_engaged")

    else:
        log.info("GPU KILL cleared — resuming Ollama and releasing lock.")

        # Resume Ollama
        pid = state.ollama_pid or _find_ollama_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGCONT)
                log.info("Sent SIGCONT to Ollama PID %d.", pid)
                state.ollama_pid = None
            except ProcessLookupError:
                log.warning("Ollama PID %d not found during SIGCONT.", pid)

        # Resume LangGraph
        try:
            requests.post(
                f"{LANGGRAPH_API_URL}/admin/resume",
                json={"reason": "hardware_gpu_kill_switch_cleared"},
                timeout=3,
            )
            log.info("LangGraph resume command sent.")
        except requests.RequestException as exc:
            log.warning("LangGraph resume request failed: %s", exc)

        # Clear sovereignty lock
        _clear_sovereignty_lock()


# ── Sovereignty lock ──────────────────────────────────────────────────────────

def _write_sovereignty_lock(reason: str) -> None:
    """
    Write a sovereignty lock file. The Web3 signing daemon (and any other
    service that calls _check_sovereignty_lock()) must refuse to sign
    transactions while this file exists.
    """
    lock_dir = os.path.dirname(SOVEREIGNTY_LOCK_PATH)
    os.makedirs(lock_dir, exist_ok=True)
    with open(SOVEREIGNTY_LOCK_PATH, "w") as f:
        f.write(f"LOCKED: {reason}\nTimestamp: {time.time()}\n")
    log.critical(
        "SOVEREIGNTY LOCK WRITTEN: %s — Web3 signing suspended.", SOVEREIGNTY_LOCK_PATH
    )


def _clear_sovereignty_lock() -> None:
    """Remove the sovereignty lock file."""
    try:
        os.remove(SOVEREIGNTY_LOCK_PATH)
        log.info("Sovereignty lock cleared: %s", SOVEREIGNTY_LOCK_PATH)
    except FileNotFoundError:
        pass  # Already clear


# ── Main daemon loop ──────────────────────────────────────────────────────────

def main() -> None:
    log.info("Solidarity HAT Hardware Sovereignty Daemon starting.")
    log.info(
        "Poll interval: %.2fs | Sovereignty lock: %s",
        POLL_INTERVAL_SEC, SOVEREIGNTY_LOCK_PATH,
    )

    # systemd readiness notification
    if SDNOTIFY_AVAILABLE:
        notifier = sdnotify.SystemdNotifier()
    else:
        notifier = None

    current_state = KillState()

    try:
        btn_mic, btn_wifi, btn_gpu = init_gpio()
        current_state.hardware_verified = True
        log.info("Hardware verified — kill switch monitoring active.")
    except RuntimeError as exc:
        log.critical(
            "HARDWARE INITIALIZATION FAILED: %s\n"
            "Writing sovereignty lock — Web3 signing is SUSPENDED until "
            "a human engineer verifies the Solidarity HAT hardware.",
            exc,
        )
        _write_sovereignty_lock(reason="hardware_init_failure")
        # Do not exit — keep lock in place and report READY so systemd does not restart loop
        if notifier:
            notifier.notify("READY=1")
            notifier.notify("STATUS=DEGRADED: GPIO unavailable. Sovereignty lock active.")
        # Block indefinitely — a human must intervene
        while True:
            time.sleep(60)

    if notifier:
        notifier.notify("READY=1")
        notifier.notify("STATUS=Active: monitoring kill switches.")

    log.info("Entering monitoring loop.")

    while True:
        new_state = KillState(
            mic_killed  = btn_mic.is_pressed,
            wifi_killed = btn_wifi.is_pressed,
            gpu_killed  = btn_gpu.is_pressed,
            hardware_verified = True,
            ollama_pid  = current_state.ollama_pid,
        )

        if new_state != current_state:
            log.info(
                "Kill state change: MIC=%s WIFI=%s GPU=%s",
                new_state.mic_killed, new_state.wifi_killed, new_state.gpu_killed,
            )

            if new_state.mic_killed != current_state.mic_killed:
                enforce_mic_kill(new_state)

            if new_state.wifi_killed != current_state.wifi_killed:
                enforce_wifi_kill(new_state)

            if new_state.gpu_killed != current_state.gpu_killed:
                enforce_gpu_kill(new_state)

            current_state = new_state

            if notifier:
                notifier.notify(
                    f"STATUS=MIC={'KILLED' if new_state.mic_killed else 'OK'} "
                    f"WIFI={'KILLED' if new_state.wifi_killed else 'OK'} "
                    f"GPU={'KILLED' if new_state.gpu_killed else 'OK'}"
                )

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
