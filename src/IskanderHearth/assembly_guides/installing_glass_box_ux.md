# Installing the Glass Box UX (Phase 6)

**License:** CERN-OHL-S v2
**Prerequisite:** Solidarity HAT installed and verified (Phase 5)
**Applies to:** Iskander Hearth Tier 2 (Commons) and above

---

## Overview

The Glass Box UX makes the AI's internal state physically observable and overridable.

| Component | Function |
|-----------|----------|
| Veto button (red, left) | Single press — rejects any pending multi-sig transaction |
| Sign button (green, right) | 3-second hold — confirms and signs a pending transaction |
| NeoPixel strip (top panel) | Displays AI inference state in real-time (≤500ms latency) |

> **Why this matters:** A cooperative node processes transactions on behalf of its members.
> The Veto button is not a feature. It is the minimum viable expression of human agency
> over a machine. It must work even if the AI is mid-inference.

---

## 1. Hardware Assembly

### 1.1 Print or cut chassis v2

```bash
# Open hearth_chassis_v2.scad in OpenSCAD
# Verify renders without errors (F5)
# Export panels individually for printing:
#   - front_panel_v2()  → front_panel_v2.stl
#   - top_panel_v2()    → top_panel_v2.stl
# (other panels unchanged from v1)
```

Print settings: PETG, 3 perimeters, 40% gyroid infill, 0.2mm layer height.

### 1.2 Print brackets

```bash
# hitl_button_bracket_v1.scad → hitl_button_bracket.stl
# led_matrix_mount_v1.scad    → led_matrix_mount.stl  (prints as channel insert)
# sensor_hat_bracket.scad     → sensor_hat_bracket.stl (if not already mounted)
```

### 1.3 Install HITL button bracket

1. Press `hitl_button_bracket.stl` into the v2 front panel button slot from inside.
2. Secure with 2× M3×10 screws through mounting ears.
3. Install Sanwa OBSA-30 buttons from outside, thread M12 retention nuts from inside.
   - Left position: **red cap** → Veto
   - Right position: **green cap** → Sign

### 1.4 Install NeoPixel LED channel

1. Press `led_matrix_mount.stl` into the v2 top panel slot. It should clip in without adhesive.
2. Feed WS2812B strip (P6-002, 0.5m, 30 LEDs) into the channel from one end.
   - Adhesive backing holds strip in channel; clean channel interior before placing.
3. Slide 3mm frosted acrylic diffuser (P6-003, laser-cut to channel width × length) into clip rails.
   The diffuser softens individual LED dots into smooth ambient glow.
4. Route data and power leads through wire exit notch at rear of channel.

### 1.5 Wiring

Follow `pcb/glass_box_wiring/glass_box_wiring_netlist.md` for full circuit.
Summary:

| Wire | From | To |
|------|------|----|
| Veto button NO | HAT J1.21 (GPIO5) via RC debounce | SW_VETO NO contact |
| Sign button NO | HAT J1.22 (GPIO6) via RC debounce | SW_SIGN NO contact |
| Veto LED+ | Q1 collector | Veto button LED anode |
| Veto LED− | Veto button LED cathode | GND |
| Sign LED+ | Q2 collector | Sign button LED anode |
| Sign LED− | Sign button LED cathode | GND |
| NeoPixel DIN | HAT J1.26 (GPIO26) via level shifter | WS2812B DIN |
| NeoPixel VCC | P6-004 buck output (+5V) | WS2812B VCC |
| NeoPixel GND | GND | WS2812B GND |

All JST-XH 2.5mm connectors — tool-free disconnect.

### 1.6 5V Buck regulator (P6-004)

1. Mount Pololu D24V22F5 (or Mini-360) inside chassis on a small standoff.
2. Input: 12V from PSU auxiliary rail.
3. Output: +5V_NEO → NeoPixel strip VCC + button LED anodes (via Q1/Q2 transistors).
4. Add 1000µF 10V bulk cap at output terminal (see netlist section 4a).

---

## 2. Software Setup

### 2.1 Install Python dependencies

```bash
source /opt/iskander/venv/bin/activate
pip install rpi-ws281x gpiozero sdnotify
```

### 2.2 Create hearth-ux user (if not already created)

```bash
sudo useradd --system --no-create-home \
    --groups gpio \
    --shell /sbin/nologin \
    hearth-ux
```

### 2.3 Install systemd services

```bash
sudo cp /opt/iskander/software/glass_box/systemd/hearth-buttons.service \
        /etc/systemd/system/

sudo cp /opt/iskander/software/glass_box/systemd/hearth-leds.service \
        /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now hearth-buttons.service
sudo systemctl enable --now hearth-leds.service
```

### 2.4 Verify

```bash
sudo systemctl status hearth-buttons.service
sudo systemctl status hearth-leds.service

# Watch live
sudo journalctl -u hearth-buttons -f
sudo journalctl -u hearth-leds -f
```

Expected output:
```
hearth-buttons: Button handler active. Waiting for input.
hearth-leds: WS2812B strip initialized: 30 LEDs on BCM18, brightness=80
```

---

## 3. Functional Verification

### 3.1 LED startup sequence

On daemon start, the strip runs a rainbow sweep for 3 seconds (SETUP state), then transitions to slow blue breathe (IDLE). This confirms both hardware and firmware are functional.

### 3.2 Push state manually

```bash
echo '{"state":"INFERENCE","source":"test","ts":0}' | \
    socat - UNIX-CONNECT:/run/iskander/led_state.sock
# Strip should switch to fast white breathe
```

### 3.3 Test Veto button

```bash
# Press Veto (red) button
# Expected:
sudo journalctl -u hearth-buttons --since "10 sec ago"
# → "VETO pressed — rejecting pending transaction."
# Strip should flash red 3× then return to IDLE
```

### 3.4 Test Sign hold

```bash
# Hold Sign (green) button for 3 seconds
# Expected log:
# → "Sign button pressed — hold for 3s to confirm."
# → "Sign 3s hold confirmed — initiating signing."
# Strip should switch to green chase animation
```

### 3.5 Test emergency shutdown (non-destructive check)

```bash
# DO NOT test on a live node without saving all work first.
# To verify wiring without triggering shutdown:
gpioget gpiochip0 5   # Veto: 1 = released, 0 = pressed
gpioget gpiochip0 6   # Sign: 1 = released, 0 = pressed
# Hold both and confirm both lines read 0 simultaneously.
```

---

## 4. LED Protocol Summary

| Behavior | State | Trigger |
|----------|-------|---------|
| Slow blue breathe (2s) | IDLE | Default |
| Fast white breathe (0.5s) | INFERENCE | LLM processing |
| Solid amber | MULTISIG_PENDING | TX awaiting human approval |
| Green rotating dot | SIGNING | After 3s Sign hold |
| Red flash ×3 (1s) | VETOED | After Veto press |
| Rainbow sweep | SETUP | First boot / provisioning |
| Dim amber breathe (3s) | LOW_POWER | Battery low |
| Red/off alternating | HARDWARE_FAULT | Sovereignty lock |
| Off | OFF | Powered down |

See `software/glass_box/led_protocol.md` for full specification.

---

## 5. Acceptance Criteria Checklist

- [ ] Chassis v2 renders without errors in OpenSCAD; front and top panels export to STL
- [ ] Veto and Sign buttons physically installed, correct colors (red left / green right)
- [ ] NeoPixel strip: all 30 LEDs visible through diffuser on startup rainbow
- [ ] LED state updates within 500ms of OS event (manual test with socat)
- [ ] Veto button: single press sends VETO to multi-sig daemon
- [ ] Sign button: 3-second hold required (release at 2s = no action)
- [ ] Emergency: both held 10s triggers `shutdown` (test on non-production node only)
- [ ] Button illumination LEDs operate: red for Veto, green for Sign
- [ ] `hearth-buttons.service` and `hearth-leds.service` both active/running
- [ ] Both daemons run as non-root `hearth-ux` user (confirm with `ps aux | grep hearth`)
- [ ] JST-XH connectors: all wiring disconnects tool-free without tools

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Strip shows nothing on startup | rpi_ws281x not installed or wrong GPIO pin | `pip install rpi-ws281x`; check `HEARTH_LED_GPIO_PIN=18` |
| LED stuck on HARDWARE_FAULT | Sovereignty lock exists | Check `/run/iskander/sovereignty.lock`; resolve hardware issue |
| Veto press not logged | GPIO5 wrong or gpiozero not installed | `gpioget gpiochip0 5`; check wiring and pull-up |
| Sign fires immediately | bounce_time too low or RC filter missing | Increase `HEARTH_BTN_DEBOUNCE_SEC`; check C_DEBOUNCE cap |
| Button LED doesn't light | Q1/Q2 transistor circuit | Check base resistor (1kΩ), collector-emitter polarity |
| NeoPixel colors wrong | LED_INVERT or GRB vs RGB order | Set `HEARTH_LED_INVERT=1` or adjust `_rgb()` byte order |
