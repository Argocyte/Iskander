#!/usr/bin/env python3
"""
button_handler.py — HITL Veto / Sign Button Daemon

License: CERN-OHL-S v2 / MIT (software component)
Managed by: systemd unit hearth-buttons.service
Runs as: hearth-ux (dedicated non-root service user)

HITL = Human-in-the-Loop. These are not convenience buttons.
They are the physical instantiation of cooperative AI governance:
a human can always overrule the machine with a single press.

BUTTON BEHAVIORS:
    Veto (GPIO5, red):
        Single press → sends VETO to multi-sig daemon via Unix socket.
        Pushes VETOED state to LED daemon.
        Lights button red LED for 1 second.

    Sign (GPIO6, green):
        3-second sustained hold → sends SIGN to multi-sig daemon.
        Visual feedback: green LED pulses during hold, solid on confirmation.
        If released before 3s: no action. Prevents accidental signing.

    Emergency shutdown (both held 10s):
        Initiates graceful OS poweroff.
        Final ActivityPub broadcast handled by permacomputing_monitor.

DEBOUNCE:
    Hardware: RC filter on wiring board (τ ≈ 47µs, see glass_box_wiring_netlist.md).
    Software: gpiozero bounce_time=0.05s (50ms). Total: ~50ms.

SOCKET PROTOCOL:
    Sends newline-delimited JSON to /run/iskander/multisig.sock (TX governance).
    Sends LED state updates to /run/iskander/led_state.sock (LED daemon).

Dependencies:
    pip install gpiozero sdnotify
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time

try:
    from gpiozero import Button, LED
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False

try:
    import sdnotify
    SDNOTIFY_AVAILABLE = True
except ImportError:
    SDNOTIFY_AVAILABLE = False

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hearth.buttons")

# ── Configuration ─────────────────────────────────────────────────────────────

GPIO_BTN_VETO        = int(os.environ.get("HEARTH_GPIO_BTN_VETO",       "5"))    # BCM5 / J1.21
GPIO_BTN_SIGN        = int(os.environ.get("HEARTH_GPIO_BTN_SIGN",       "6"))    # BCM6 / J1.22
GPIO_LED_VETO_ILLUM  = int(os.environ.get("HEARTH_GPIO_LED_VETO",       "13"))   # BCM13 / J1.24
GPIO_LED_SIGN_ILLUM  = int(os.environ.get("HEARTH_GPIO_LED_SIGN",       "19"))   # BCM19 / J1.25

SIGN_HOLD_SEC        = float(os.environ.get("HEARTH_SIGN_HOLD_SEC",     "3.0"))
EMERGENCY_HOLD_SEC   = float(os.environ.get("HEARTH_EMERGENCY_HOLD_SEC", "10.0"))
DEBOUNCE_SEC         = float(os.environ.get("HEARTH_BTN_DEBOUNCE_SEC",  "0.05"))

MULTISIG_SOCK        = os.environ.get("HEARTH_MULTISIG_SOCK", "/run/iskander/multisig.sock")
LED_STATE_SOCK       = os.environ.get("HEARTH_LED_STATE_SOCK", "/run/iskander/led_state.sock")


# ── Unix socket helpers ───────────────────────────────────────────────────────

def _send_unix_json(sock_path: str, payload: dict) -> None:
    """Send a JSON message to a Unix domain socket. Fire-and-forget."""
    msg = json.dumps(payload) + "\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(sock_path)
            s.sendall(msg.encode())
    except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
        log.warning("Could not reach %s: %s", sock_path, exc)


def send_multisig(action: str, **extra) -> None:
    """Send a governance action to the multi-sig daemon."""
    _send_unix_json(
        MULTISIG_SOCK,
        {"action": action, "source": "button_handler", "ts": time.time(), **extra},
    )
    log.info("Multi-sig: %s", action)


def push_led_state(state: str) -> None:
    """Push a LED state update to the LED state daemon."""
    _send_unix_json(
        LED_STATE_SOCK,
        {"state": state, "source": "button_handler", "ts": time.time()},
    )


# ── Button LED control ────────────────────────────────────────────────────────

class ButtonLED:
    """
    Controls the illuminated ring of an arcade button.
    Wraps gpiozero LED with blink and pulse helpers.
    """

    def __init__(self, gpio_pin: int) -> None:
        if GPIOZERO_AVAILABLE:
            self._led = LED(gpio_pin, active_high=True, initial_value=False)
        else:
            self._led = None

    def on(self) -> None:
        if self._led:
            self._led.on()

    def off(self) -> None:
        if self._led:
            self._led.off()

    def blink(self, on_time: float = 0.1, off_time: float = 0.1, n: int = 3) -> None:
        if self._led:
            self._led.blink(on_time=on_time, off_time=off_time, n=n, background=True)

    def pulse(self) -> None:
        """Continuous slow pulse (using blink as approximation)."""
        if self._led:
            self._led.blink(on_time=0.5, off_time=0.5, background=True)

    def stop(self) -> None:
        if self._led:
            self._led.off()


# ── Sign hold tracker ─────────────────────────────────────────────────────────

class SignHoldTracker:
    """
    Tracks the Sign button hold duration.
    On 3s threshold: triggers sign action.
    On 10s threshold (with Veto also held): triggers emergency shutdown.
    """

    def __init__(
        self,
        sign_led: ButtonLED,
        veto_btn: "Button",
    ) -> None:
        self._sign_led  = sign_led
        self._veto_btn  = veto_btn
        self._press_ts: float = 0.0
        self._armed     = False
        self._fired     = False
        self._timer: threading.Timer | None = None
        self._emerg_timer: threading.Timer | None = None

    def pressed(self) -> None:
        """Called when Sign button is pressed."""
        self._press_ts = time.time()
        self._fired    = False
        self._armed    = True
        log.info("Sign button pressed — hold for %.0fs to confirm.", SIGN_HOLD_SEC)

        # Pulse LED during hold
        self._sign_led.pulse()

        # Schedule sign confirmation at SIGN_HOLD_SEC
        self._timer = threading.Timer(SIGN_HOLD_SEC, self._sign_confirmed)
        self._timer.start()

        # Schedule emergency at EMERGENCY_HOLD_SEC
        self._emerg_timer = threading.Timer(EMERGENCY_HOLD_SEC, self._check_emergency)
        self._emerg_timer.start()

    def released(self) -> None:
        """Called when Sign button is released."""
        self._armed = False
        self._sign_led.stop()
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
            log.info("Sign hold cancelled (released before %.0fs).", SIGN_HOLD_SEC)
        if self._emerg_timer and self._emerg_timer.is_alive():
            self._emerg_timer.cancel()

    def _sign_confirmed(self) -> None:
        """Called after 3s hold."""
        if not self._armed:
            return
        self._fired = True
        log.info("Sign 3s hold confirmed — initiating signing.")
        self._sign_led.on()  # Solid green = signing in progress
        push_led_state("SIGNING")
        send_multisig("SIGN")

    def _check_emergency(self) -> None:
        """Called after 10s. If Veto is also held, trigger emergency shutdown."""
        if not self._armed:
            return
        if GPIOZERO_AVAILABLE and self._veto_btn and self._veto_btn.is_pressed:
            log.critical("EMERGENCY: Both buttons held 10s — initiating graceful poweroff.")
            push_led_state("OFF")
            subprocess.run(
                ["shutdown", "--poweroff", "+0",
                 "Iskander Hearth: emergency shutdown via HITL buttons"],
                check=False,
            )
        else:
            log.debug("10s elapsed with only Sign held — not an emergency.")


# ── Veto handler ──────────────────────────────────────────────────────────────

def handle_veto_press(veto_led: ButtonLED) -> None:
    """Single press action for Veto button."""
    log.warning("VETO pressed — rejecting pending transaction.")
    veto_led.blink(on_time=0.15, off_time=0.1, n=6)  # ~1.5s red flash
    push_led_state("VETOED")
    send_multisig("VETO")


# ── Main daemon ───────────────────────────────────────────────────────────────

def main() -> None:
    if not GPIOZERO_AVAILABLE:
        log.critical(
            "gpiozero not installed. Run: pip install gpiozero\n"
            "HITL button daemon cannot start without GPIO access."
        )
        sys.exit(1)

    if SDNOTIFY_AVAILABLE:
        notifier = sdnotify.SystemdNotifier()
    else:
        notifier = None

    log.info(
        "Glass Box Button Handler starting — "
        "VETO=BCM%d SIGN=BCM%d "
        "sign_hold=%.1fs emergency=%.1fs",
        GPIO_BTN_VETO, GPIO_BTN_SIGN, SIGN_HOLD_SEC, EMERGENCY_HOLD_SEC,
    )

    # Initialize GPIO
    veto_btn = Button(GPIO_BTN_VETO, pull_up=True,  bounce_time=DEBOUNCE_SEC)
    sign_btn = Button(GPIO_BTN_SIGN, pull_up=True,  bounce_time=DEBOUNCE_SEC)

    veto_led = ButtonLED(GPIO_LED_VETO_ILLUM)
    sign_led = ButtonLED(GPIO_LED_SIGN_ILLUM)

    tracker = SignHoldTracker(sign_led=sign_led, veto_btn=veto_btn)

    # Wire button events
    veto_btn.when_pressed  = lambda: handle_veto_press(veto_led)
    sign_btn.when_pressed  = tracker.pressed
    sign_btn.when_released = tracker.released

    # Startup LED flash: brief white blink on both buttons = "I am alive"
    veto_led.blink(on_time=0.2, off_time=0.1, n=2)
    sign_led.blink(on_time=0.2, off_time=0.1, n=2)

    if notifier:
        notifier.notify("READY=1")
        notifier.notify("STATUS=Active: monitoring HITL buttons.")

    log.info("Button handler active. Waiting for input.")

    # Block main thread — gpiozero runs callbacks in background threads
    signal.pause()


if __name__ == "__main__":
    main()
