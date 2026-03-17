#!/usr/bin/env python3
"""
led_state_daemon.py — NeoPixel LED State Visualization Daemon

License: CERN-OHL-S v2 / MIT (software component)
Managed by: systemd unit hearth-leds.service
Runs as: hearth-ux (dedicated non-root service user)

Drives a 30-LED WS2812B strip (top panel diffuser) to visually express
the AI's current operational state per the Glass Box LED Protocol v1.
See: software/glass_box/led_protocol.md

STATE → PATTERN MAPPING:
    IDLE             → Blue breathe, 2s cycle
    INFERENCE        → White breathe, 0.5s cycle
    MULTISIG_PENDING → Solid amber
    SIGNING          → Green chase (rotating dot)
    VETOED           → Red flash ×3 (1s), then restore previous
    SETUP            → Rainbow sweep
    LOW_POWER        → Dim amber breathe, 3s cycle
    HARDWARE_FAULT   → Red/off alternating flash, 2 Hz
    OFF              → All LEDs off

State priority (high→low): HARDWARE_FAULT > VETOED > SIGNING > MULTISIG_PENDING >
                            LOW_POWER > INFERENCE > SETUP > IDLE > OFF

Transport: Unix domain socket server on /run/iskander/led_state.sock.
           Accepts JSON messages: {"state": "INFERENCE", "source": "...", "ts": ...}

Dependencies:
    pip install rpi-ws281x sdnotify
"""

from __future__ import annotations

import colorsys
import json
import logging
import math
import os
import select
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from pathlib import Path
from typing import Optional

try:
    import rpi_ws281x as ws281x
    WS281X_AVAILABLE = True
except ImportError:
    WS281X_AVAILABLE = False

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
log = logging.getLogger("hearth.leds")

# ── Configuration ─────────────────────────────────────────────────────────────

LED_COUNT        = int(os.environ.get("HEARTH_LED_COUNT",      "30"))
LED_GPIO_PIN     = int(os.environ.get("HEARTH_LED_GPIO_PIN",   "18"))   # Must be PWM-capable (BCM 18 = PCM CLK)
                                                                          # Matches GPIO26 via level-shifter routed to this header
LED_FREQ_HZ      = int(os.environ.get("HEARTH_LED_FREQ_HZ",   "800000"))
LED_DMA_CHANNEL  = int(os.environ.get("HEARTH_LED_DMA",       "10"))
LED_BRIGHTNESS   = int(os.environ.get("HEARTH_LED_BRIGHTNESS", "80"))   # 0–255
LED_INVERT       = os.environ.get("HEARTH_LED_INVERT", "0") == "1"

LED_STATE_SOCK   = os.environ.get("HEARTH_LED_STATE_SOCK", "/run/iskander/led_state.sock")
SOVEREIGNTY_LOCK = os.environ.get("HEARTH_SOVEREIGNTY_LOCK", "/run/iskander/sovereignty.lock")

FRAME_RATE_HZ    = float(os.environ.get("HEARTH_LED_FRAME_HZ", "60"))
FRAME_SEC        = 1.0 / FRAME_RATE_HZ


# ── State definitions ─────────────────────────────────────────────────────────

class LedState(str, Enum):
    IDLE             = "IDLE"
    INFERENCE        = "INFERENCE"
    MULTISIG_PENDING = "MULTISIG_PENDING"
    SIGNING          = "SIGNING"
    VETOED           = "VETOED"
    SETUP            = "SETUP"
    LOW_POWER        = "LOW_POWER"
    HARDWARE_FAULT   = "HARDWARE_FAULT"
    OFF              = "OFF"


# Priority: higher index = higher priority
_STATE_PRIORITY: dict[LedState, int] = {
    LedState.OFF:              0,
    LedState.IDLE:             1,
    LedState.SETUP:            2,
    LedState.INFERENCE:        3,
    LedState.LOW_POWER:        4,
    LedState.MULTISIG_PENDING: 5,
    LedState.SIGNING:          6,
    LedState.VETOED:           7,
    LedState.HARDWARE_FAULT:   8,
}

_VALID_STATES = {s.value for s in LedState}


# ── Color helpers ─────────────────────────────────────────────────────────────

def _rgb(r: int, g: int, b: int, brightness: float = 1.0) -> int:
    """Pack scaled RGB into a 24-bit WS2812B color int."""
    br = max(0, min(255, int(brightness * LED_BRIGHTNESS / 255)))
    r2 = int(r * br / 255)
    g2 = int(g * br / 255)
    b2 = int(b * br / 255)
    return (r2 << 16) | (g2 << 8) | b2


def _hsv(h: float, s: float, v: float) -> int:
    """HSV (0–1 each) to 24-bit WS2812B color int at global brightness."""
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return _rgb(int(r * 255), int(g * 255), int(b * 255))


def _breathe(period_sec: float, t: float) -> float:
    """Sinusoidal breathe function. Returns 0.0–1.0."""
    return math.sin(math.pi * (t % period_sec) / period_sec) ** 2


# ── Pattern generators ────────────────────────────────────────────────────────

class PatternEngine:
    """
    Stateless pattern functions. Each returns a list[int] of LED colors
    given the current wall-clock time and LED count.
    """

    @staticmethod
    def idle(t: float) -> list[int]:
        br = _breathe(2.0, t)
        c  = _rgb(0, 64, 255, br)
        return [c] * LED_COUNT

    @staticmethod
    def inference(t: float) -> list[int]:
        br = _breathe(0.5, t)
        c  = _rgb(255, 255, 255, br)
        return [c] * LED_COUNT

    @staticmethod
    def multisig_pending(_t: float) -> list[int]:
        c = _rgb(255, 140, 0)
        return [c] * LED_COUNT

    @staticmethod
    def signing(t: float) -> list[int]:
        step  = int((t % (LED_COUNT * 0.08)) / 0.08) % LED_COUNT
        leds  = [0] * LED_COUNT
        leds[step] = _rgb(0, 255, 64)
        # Fading tail (3 LEDs behind)
        for tail in range(1, 4):
            idx  = (step - tail) % LED_COUNT
            fade = 1.0 - tail * 0.25
            leds[idx] = _rgb(0, int(255 * fade), int(64 * fade))
        return leds

    @staticmethod
    def vetoed(phase_t: float) -> list[int]:
        """phase_t: time since VETOED started (0–1.0s)."""
        # 3 Hz flash for 1 second = 3 cycles
        c = _rgb(255, 0, 0) if int(phase_t * 6) % 2 == 0 else 0
        return [c] * LED_COUNT

    @staticmethod
    def setup(t: float) -> list[int]:
        leds = []
        for i in range(LED_COUNT):
            h = (i / LED_COUNT + t / 3.0) % 1.0
            leds.append(_hsv(h, 1.0, 1.0))
        return leds

    @staticmethod
    def low_power(t: float) -> list[int]:
        br = _breathe(3.0, t) * 0.30  # max 30% brightness
        c  = _rgb(255, 68, 0, br)
        return [c] * LED_COUNT

    @staticmethod
    def hardware_fault(t: float) -> list[int]:
        c = _rgb(255, 0, 0) if int(t * 4) % 2 == 0 else 0
        return [c] * LED_COUNT

    @staticmethod
    def off(_t: float) -> list[int]:
        return [0] * LED_COUNT


# ── Shared state ──────────────────────────────────────────────────────────────

@dataclass
class SharedState:
    current: LedState = LedState.IDLE
    previous: LedState = LedState.IDLE   # restored after VETOED clears
    veto_start: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, new_state: LedState) -> None:
        with self.lock:
            new_pri = _STATE_PRIORITY.get(new_state, 0)
            cur_pri = _STATE_PRIORITY.get(self.current, 0)
            if new_pri >= cur_pri or new_state == LedState.IDLE:
                if new_state == LedState.VETOED:
                    self.previous   = self.current
                    self.veto_start = time.monotonic()
                self.current = new_state
                log.info("LED state → %s", new_state.value)

    def tick(self) -> LedState:
        """Auto-clear VETOED after 1s."""
        with self.lock:
            if self.current == LedState.VETOED:
                if time.monotonic() - self.veto_start >= 1.0:
                    log.info("VETOED cleared → restoring %s", self.previous.value)
                    self.current = self.previous
            return self.current


# ── LED hardware wrapper ──────────────────────────────────────────────────────

class LedStrip:
    """Wraps rpi_ws281x.PixelStrip with a clean interface."""

    def __init__(self) -> None:
        if not WS281X_AVAILABLE:
            log.warning(
                "rpi_ws281x not installed. Running in simulation mode (no physical output). "
                "Install with: pip install rpi-ws281x"
            )
            self._strip = None
            return
        self._strip = ws281x.PixelStrip(
            LED_COUNT, LED_GPIO_PIN, LED_FREQ_HZ,
            LED_DMA_CHANNEL, LED_INVERT, LED_BRIGHTNESS,
        )
        self._strip.begin()
        log.info(
            "WS2812B strip initialized: %d LEDs on BCM%d, brightness=%d",
            LED_COUNT, LED_GPIO_PIN, LED_BRIGHTNESS,
        )

    def show(self, colors: list[int]) -> None:
        if self._strip is None:
            return
        for i, c in enumerate(colors[:LED_COUNT]):
            self._strip.setPixelColor(i, c)
        self._strip.show()

    def clear(self) -> None:
        self.show([0] * LED_COUNT)


# ── Socket server (receives state updates) ────────────────────────────────────

def socket_server(state: SharedState, sock_path: str) -> None:
    """
    Listens on Unix domain socket. Each connected client may send
    newline-delimited JSON state update messages.
    Runs in a background thread.
    """
    if Path(sock_path).exists():
        os.remove(sock_path)

    sock_dir = str(Path(sock_path).parent)
    os.makedirs(sock_dir, exist_ok=True)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    os.chmod(sock_path, 0o660)
    server.listen(8)
    server.setblocking(False)
    log.info("LED state socket listening: %s", sock_path)

    clients: list[socket.socket] = []
    buf: dict[socket.socket, bytes] = {}

    while True:
        readable, _, errored = select.select([server, *clients], [], [*clients], 1.0)

        for s in errored:
            clients.remove(s)
            buf.pop(s, None)
            s.close()

        for s in readable:
            if s is server:
                conn, _ = server.accept()
                conn.setblocking(False)
                clients.append(conn)
                buf[conn] = b""
            else:
                try:
                    chunk = s.recv(1024)
                    if not chunk:
                        clients.remove(s)
                        buf.pop(s, None)
                        s.close()
                        continue
                    buf[s] += chunk
                    while b"\n" in buf[s]:
                        line, buf[s] = buf[s].split(b"\n", 1)
                        _process_message(state, line.decode(errors="replace"))
                except OSError:
                    clients.remove(s)
                    buf.pop(s, None)
                    s.close()


def _process_message(state: SharedState, raw: str) -> None:
    try:
        msg = json.loads(raw.strip())
        raw_state = msg.get("state", "").upper()
        if raw_state not in _VALID_STATES:
            log.warning("Unknown LED state received: %r", raw_state)
            return
        state.update(LedState(raw_state))
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("Malformed LED state message: %r (%s)", raw, exc)


# ── Render loop ───────────────────────────────────────────────────────────────

def render_loop(strip: LedStrip, state: SharedState) -> None:
    """Main render loop. Runs at FRAME_RATE_HZ."""
    engine = PatternEngine()
    t_start = time.monotonic()

    while True:
        t       = time.monotonic() - t_start
        current = state.tick()

        if current == LedState.IDLE:
            colors = engine.idle(t)
        elif current == LedState.INFERENCE:
            colors = engine.inference(t)
        elif current == LedState.MULTISIG_PENDING:
            colors = engine.multisig_pending(t)
        elif current == LedState.SIGNING:
            colors = engine.signing(t)
        elif current == LedState.VETOED:
            phase_t = time.monotonic() - state.veto_start
            colors  = engine.vetoed(phase_t)
        elif current == LedState.SETUP:
            colors = engine.setup(t)
        elif current == LedState.LOW_POWER:
            colors = engine.low_power(t)
        elif current == LedState.HARDWARE_FAULT:
            colors = engine.hardware_fault(t)
        else:  # OFF
            colors = engine.off(t)

        strip.show(colors)
        time.sleep(FRAME_SEC)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if SDNOTIFY_AVAILABLE:
        notifier = sdnotify.SystemdNotifier()
    else:
        notifier = None

    log.info(
        "Glass Box LED State Daemon starting — %d LEDs, BCM%d, brightness=%d",
        LED_COUNT, LED_GPIO_PIN, LED_BRIGHTNESS,
    )

    strip = LedStrip()
    state = SharedState()

    # Check for sovereignty lock at startup → HARDWARE_FAULT immediately
    if Path(SOVEREIGNTY_LOCK).exists():
        log.critical(
            "Sovereignty lock present at startup: %s — LED HARDWARE_FAULT state active.",
            SOVEREIGNTY_LOCK,
        )
        state.update(LedState.HARDWARE_FAULT)
    else:
        # Startup SETUP rainbow for 3s
        state.update(LedState.SETUP)
        threading.Timer(3.0, lambda: state.update(LedState.IDLE)).start()

    # Start socket server in background thread
    sock_thread = threading.Thread(
        target=socket_server, args=(state, LED_STATE_SOCK), daemon=True
    )
    sock_thread.start()

    if notifier:
        notifier.notify("READY=1")
        notifier.notify(f"STATUS=Active: {LED_COUNT} LEDs on BCM{LED_GPIO_PIN}.")

    try:
        render_loop(strip, state)
    except KeyboardInterrupt:
        pass
    finally:
        strip.clear()
        log.info("LED strip cleared.")


# ── CLI test mode ─────────────────────────────────────────────────────────────

def _cli_test() -> None:
    """Quick visual test: cycle through all states for 2s each."""
    logging.basicConfig(level=logging.DEBUG)
    strip = LedStrip()
    state = SharedState()
    test_states = [
        LedState.SETUP, LedState.IDLE, LedState.INFERENCE,
        LedState.MULTISIG_PENDING, LedState.SIGNING, LedState.VETOED,
        LedState.LOW_POWER, LedState.HARDWARE_FAULT, LedState.OFF,
    ]
    t_start = time.monotonic()
    engine  = PatternEngine()
    idx     = 0
    state_start = time.monotonic()

    while True:
        t = time.monotonic() - t_start
        if time.monotonic() - state_start > 2.0:
            idx = (idx + 1) % len(test_states)
            state.update(test_states[idx])
            state_start = time.monotonic()
            print(f"→ {test_states[idx].value}")
            if test_states[idx] == LedState.VETOED:
                state.veto_start = time.monotonic()

        current = state.tick()
        # render one frame
        colors = getattr(engine, current.value.lower(), engine.off)(t)
        strip.show(colors)
        time.sleep(FRAME_SEC)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _cli_test()
    else:
        main()
