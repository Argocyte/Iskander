# Glass Box LED State Protocol v1

**License:** CERN-OHL-S v2 / MIT (software)
**Revision:** 1.0 | 2026-03-16
**Implementation:** `led_state_daemon.py`
**Transport:** Unix domain socket `/run/iskander/led_state.sock` (server) ← Iskander OS components push state updates

---

## Overview

The NeoPixel strip (30× WS2812B, top panel) is the external expression of what the AI is doing
at any moment. It is not decorative. It is the Glass Box protocol made visible — a machine that
cannot hide its internal state from the people in the room with it.

State updates must render within **500ms** of the triggering OS event.

---

## 1. LED State Table

| State ID | Pattern | Color | Period / Duration | Trigger condition |
|----------|---------|-------|-------------------|-------------------|
| `IDLE` | Slow pulse (breathe) | Blue `#0040FF` | 2000ms full cycle | Default: no tasks active, node healthy |
| `INFERENCE` | Fast pulse (breathe) | White `#FFFFFF` | 500ms full cycle | LLM inference engine processing tokens |
| `MULTISIG_PENDING` | Solid on | Amber `#FF8C00` | Steady until cleared | Multi-sig transaction awaiting HITL approval |
| `SIGNING` | Chase animation (rotating dot) | Green `#00FF40` | 80ms per LED step | Signing in progress after Sign button confirm |
| `VETOED` | Flash | Red `#FF0000` | 3 Hz for 3 cycles (1s total), then → IDLE | Veto button pressed; transaction rejected |
| `SETUP` | Rainbow sweep | Full spectrum HSV | 50ms per step | First-boot / provisioning mode |
| `LOW_POWER` | Slow pulse | Dim amber `#FF4400` at 30% brightness | 3000ms cycle | Permacomputing monitor: WARNING or CRITICAL |
| `HARDWARE_FAULT` | Alternating flash | Red/Off | 2 Hz, indefinite | Sovereignty lock active; hardware unverified |
| `OFF` | All LEDs off | — | Indefinite | Node powered down or fault |

---

## 2. State Priority

Higher priority states override lower ones. Priority descending:

```
1. HARDWARE_FAULT   (highest — overrides everything)
2. VETOED           (clears after 1s, then restores previous)
3. SIGNING
4. MULTISIG_PENDING
5. LOW_POWER
6. INFERENCE
7. SETUP
8. IDLE             (lowest — default)
9. OFF
```

---

## 3. Transport Protocol

### 3a. State update message (JSON, newline-delimited)

```json
{"state": "INFERENCE", "source": "ollama-daemon", "ts": 1710000000.123}
```

```json
{"state": "MULTISIG_PENDING", "source": "web3-signer", "ts": 1710000001.456, "tx_hash": "0xabc..."}
```

```json
{"state": "IDLE", "source": "orchestrator", "ts": 1710000002.789}
```

Fields:
- `state` (required): one of the State IDs above
- `source` (required): identifying string of the sending daemon
- `ts` (required): Unix timestamp (float)
- Additional fields: optional metadata, ignored by LED daemon

### 3b. Socket path

- Server: `led_state_daemon.py` listens on `/run/iskander/led_state.sock` (SOCK_STREAM, UNIX)
- Any Iskander OS component may connect and send newline-delimited JSON messages
- Multiple concurrent clients supported; each sends updates independently
- Daemon applies priority resolution: new state only overrides if higher priority

### 3c. Brightness

Global brightness: configurable via `HEARTH_LED_BRIGHTNESS` env var (0–255, default 80).
All patterns scale to this global brightness. `LOW_POWER` state forces maximum 30% of global value.

---

## 4. Pattern Definitions

### `IDLE` — Breathe slow (2s)
```
brightness = global_brightness × sin²(π × t / 2.0)   where t = [0, 2.0] seconds
color = #0040FF at current brightness
All 30 LEDs same value simultaneously.
```

### `INFERENCE` — Breathe fast (0.5s)
```
brightness = global_brightness × sin²(π × t / 0.5)   where t = [0, 0.5] seconds
color = #FFFFFF at current brightness
All 30 LEDs same value simultaneously.
```

### `MULTISIG_PENDING` — Solid amber
```
All 30 LEDs = #FF8C00 at global_brightness
No animation. Holds until SIGNING or VETOED state.
```

### `SIGNING` — Chase (rotating single dot)
```
One LED at full brightness (#00FF40), all others off.
LED index advances by 1 every 80ms.
Direction: left-to-right (index 0 → 29 → 0).
Chase speed: 80ms × 30 LEDs = 2.4s per full rotation.
Continues until IDLE or VETOED.
```

### `VETOED` — Flash red (1 second, then restore)
```
0–166ms:  All LEDs = #FF0000 at global_brightness
166–333ms: All LEDs off
333–500ms: All LEDs = #FF0000
500–666ms: All LEDs off
666–833ms: All LEDs = #FF0000
833–1000ms: All LEDs off
After 1000ms: restore previous state (before VETOED).
```

### `SETUP` — Rainbow sweep
```
Each LED offset by hue: hue_i = (i / 30 + t / 3.0) mod 1.0
Color: HSV(hue_i, 1.0, 1.0) converted to RGB
Step every 50ms (continuous sweep).
```

### `LOW_POWER` — Breathe slow dim amber
```
Same breathe function as IDLE but:
  - color = #FF4400
  - max_brightness = 0.3 × global_brightness
  - period = 3000ms
```

### `HARDWARE_FAULT` — Alternating flash red
```
0–250ms: All LEDs = #FF0000 at global_brightness
250–500ms: All LEDs off
Repeat indefinitely at 2 Hz.
```

---

## 5. Startup Sequence

On daemon start (before first external state message):
1. Run SETUP (rainbow sweep) for 3 seconds — signals "I am alive."
2. Transition to IDLE.

If `/run/iskander/sovereignty.lock` exists at startup:
- Skip SETUP, go directly to HARDWARE_FAULT.

---

## 6. Implementing Daemon Integration

Other Iskander OS daemons push state changes with:

```python
import socket, json, time

def push_led_state(state: str, source: str, **extra):
    msg = json.dumps({"state": state, "source": source, "ts": time.time(), **extra})
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect("/run/iskander/led_state.sock")
        s.sendall((msg + "\n").encode())
```

Recommended integration points:

| Iskander OS daemon | State to push | When |
|--------------------|--------------|------|
| Ollama monitor | `INFERENCE` | On inference start |
| Ollama monitor | `IDLE` | On inference complete |
| Web3 signer | `MULTISIG_PENDING` | On TX presented for signing |
| Web3 signer | `SIGNING` | On Sign button 3s hold confirmed |
| Web3 signer | `IDLE` | On TX complete |
| Button handler | `VETOED` | On Veto button press |
| Permacomputing monitor | `LOW_POWER` | On WARNING/CRITICAL power |
| Permacomputing monitor | `IDLE` | On power restored |
| Sovereignty daemon | `HARDWARE_FAULT` | On hardware lock |
| First-boot setup | `SETUP` | On provisioning start |
