# Glass Box UX — Wiring Netlist & Schematic Definition

**License:** CERN-OHL-S v2
**Revision:** 1.0 | 2026-03-16
**File:** `pcb/glass_box_wiring/glass_box_wiring.kicad_sch` (graphical capture from this document)
**Depends on:** Solidarity HAT v1 (`pcb/solidarity_hat/pinout_and_nets.md`) — uses J1 reserved pins 21–26

> **Design intent:** If AI inference is happening inside this machine, the human must be
> able to see it and veto it. These are not decorative LEDs and novelty buttons — they are
> the physical expression of the Glass Box protocol. The LED strip shows what the AI is
> doing *right now*. The Veto button is a constitutional right rendered in copper.

---

## 1. Signal Definitions

| Net Name | Source | Destination | Level | Description |
|----------|--------|-------------|-------|-------------|
| GPIO_BTN_VETO | HAT J1 pin 21 (GPIO5) | R_DEBOUNCE_V → SW_VETO | 3.3V logic, active LOW | Veto button sense line |
| GPIO_BTN_SIGN | HAT J1 pin 22 (GPIO6) | R_DEBOUNCE_S → SW_SIGN | 3.3V logic, active LOW | Sign button sense line |
| GPIO_LED_VETO_ILLUM | HAT J1 pin 24 (GPIO13) | Q1 base | 3.3V output | Veto button red LED drive |
| GPIO_LED_SIGN_ILLUM | HAT J1 pin 25 (GPIO19) | Q2 base | 3.3V output | Sign button green LED drive |
| GPIO_NEOPIXEL_DATA | HAT J1 pin 26 (GPIO26) | U_LS → WS2812B DIN | 3.3V→5V shifted | NeoPixel strip data |
| +3V3 | HAT J1 pin 27 | Pull-ups, level-shifter VCCA | 3.3V | Logic supply |
| +5V_NEO | P6-004 buck output | WS2812B VCC, button LED anodes | 5V 2A | NeoPixel + button LED power |
| GND | HAT J1 pin 29 | All ground returns | 0V | Common ground |

---

## 2. Solidarity HAT J1 — Phase 6 Pin Assignments (pins 21–30)

These were reserved in Phase 5. Now defined.

| J1 Pin | GPIO (BCM) | Net | Direction | Description |
|--------|------------|-----|-----------|-------------|
| 21 | GPIO5  | GPIO_BTN_VETO | INPUT | Veto button, active LOW (10kΩ pull-up to +3V3) |
| 22 | GPIO6  | GPIO_BTN_SIGN | INPUT | Sign button, active LOW (10kΩ pull-up to +3V3) |
| 23 | GND    | GND | PWR | Ground |
| 24 | GPIO13 | GPIO_LED_VETO_ILLUM | OUTPUT | Veto red LED drive (HIGH = lit) |
| 25 | GPIO19 | GPIO_LED_SIGN_ILLUM | OUTPUT | Sign green LED drive (HIGH = lit) |
| 26 | GPIO26 | GPIO_NEOPIXEL_DATA | OUTPUT | WS2812B data (via 3.3→5V level shifter) |
| 27 | +3V3   | +3V3 | PWR | 3.3V reference for level shifter VCCA |
| 28 | GPIO20 | NC | — | Reserved Phase 7 |
| 29 | GND    | GND | PWR | Ground |
| 30 | — | NC | — | Reserved |

---

## 3. HITL Button Circuit (×2 — Veto and Sign)

**Component:** Sanwa OBSA-30 (30mm LED-illuminated momentary, NO + NC contacts)

Each button has:
- **SW contact (NO):** Normally open, closes on press
- **LED terminals:** 5V LED (internal to button body), ~20mA

### 3a. Button sense circuit

```
+3V3 ──── R_PULL (10kΩ) ──┬──── GPIO_BTN_VETO (J1 pin 21)
                            │
                          SW_VETO (NO contact)
                            │
                           GND

Hardware RC debounce: R_DEBOUNCE = 1kΩ, C_DEBOUNCE = 47nF inline on GPIO line.
Time constant: τ = RC = 1kΩ × 47nF = 47µs.
Combined with gpiozero 50ms software debounce: total ~50ms.
```

Same circuit for SW_SIGN on GPIO_BTN_SIGN (J1 pin 22).

### 3b. Button LED drive circuit

Sanwa OBSA-30 LED is a 5V device. Drive via NPN transistor (2N3904 or BC337):

```
GPIO_LED_VETO_ILLUM (3.3V) ──── R_BASE (1kΩ) ──── Q1 Base
                                                     Q1 Emitter ──── GND
                                                     Q1 Collector ──── LED Cathode (Veto button)
+5V_NEO ──── R_LED (100Ω) ──── LED Anode (Veto button)
```

- Q1, Q2: NPN BJT (2N3904, SOT-23)
- R_BASE: 1kΩ (limits base current, ensures saturation at 3.3V Vhigh)
- R_LED: 100Ω series current limiter → ~20mA through 5V LED

Same circuit for Q2 → Sign button green LED (GPIO_LED_SIGN_ILLUM).

**LED color mapping:**
- Veto button: **Red** internal LED (Sanwa OBSA-30 red cap)
- Sign button: **Green** internal LED (Sanwa OBSA-30 green cap)

---

## 4. NeoPixel Strip Circuit

**Component:** WS2812B 60 LED/m, 5V, IP30, 0.5m (P6-002) → 30 LEDs total on 0.5m

### 4a. Power supply

```
12V PSU rail ──── P6-004 Buck Regulator (5V 2A output) ──── +5V_NEO
+5V_NEO ──── 1000µF electrolytic cap (bulk capacitor, near strip input) ──── GND
+5V_NEO ──── WS2812B strip VCC
GND ──── WS2812B strip GND
```

**Bulk capacitor:** 1000µF 10V electrolytic, placed at power injection point to absorb switching
current spikes from WS2812B LEDs (each LED draws up to 60mA at full white).
Max theoretical draw: 30 LEDs × 60mA = 1.8A. P6-004 rated 2A — within spec.

### 4b. Data line level shift (3.3V → 5V)

WS2812B data line requires logic HIGH > 0.7 × VCC = 3.5V. 3.3V GPIO is marginally below spec.
**Level shift is required.**

```
GPIO_NEOPIXEL_DATA (3.3V) ──── U_LS.A1 (74AHCT125 or SN74LVC1T45)
U_LS.Y1 ──── R_DATA (300Ω) ──── WS2812B DIN
U_LS.VCCA = +3V3
U_LS.VCCB = +5V_NEO
```

- Level shifter: 74AHCT125 single-gate buffer, SOIC-14 (one gate used; tie unused OE pins LOW)
  OR: SN74LVC1T45DBVR SOT-23-6 (single-channel, cleaner BOM)
- R_DATA: 300Ω series resistor on data line. Limits ringing on long cable runs.

### 4c. Strip termination

```
WS2812B strip DOUT ──── R_TERM (50Ω) ──── NC (or next strip if chained)
```

End-of-strip termination resistor to suppress reflections.

---

## 5. Physical Connectors

| Ref | Type | Function | Connected to |
|-----|------|----------|-------------|
| J_HAT | 2×20 dupont female | HAT J1 mating connector | Solidarity HAT J1 (pins 21–29 used) |
| J_VETO | JST-XH 4-pin | Veto button | SW_VETO.NO+COM, LED+, LED- |
| J_SIGN | JST-XH 4-pin | Sign button | SW_SIGN.NO+COM, LED+, LED- |
| J_NEO_IN | JST-XH 3-pin | NeoPixel input | +5V_NEO, DIN (post level-shift), GND |
| J_12V | JST-XH 2-pin | 12V input from PSU | P6-004 input |
| J_NEO_POWER | JST-XH 2-pin | NeoPixel 5V power | +5V_NEO, GND (direct to strip) |

All connectors: JST-XH 2.5mm pitch, tool-free disconnect for maintenance (per roadmap).

---

## 6. Passive Component Summary

| Ref | Value | Package | Qty | Function |
|-----|-------|---------|-----|----------|
| R_PULL_VETO, R_PULL_SIGN | 10kΩ | 0805 | 2 | Button pull-ups |
| R_DEBOUNCE_V, R_DEBOUNCE_S | 1kΩ | 0805 | 2 | RC debounce series resistor |
| C_DEBOUNCE_V, C_DEBOUNCE_S | 47nF | 0805 | 2 | RC debounce capacitor |
| R_BASE1, R_BASE2 | 1kΩ | 0805 | 2 | BJT base resistors |
| R_LED1, R_LED2 | 100Ω | 0805 | 2 | Button LED current limit |
| Q1, Q2 | 2N3904 / BC337 | SOT-23 | 2 | NPN BJT LED drivers |
| U_LS | SN74LVC1T45DBVR | SOT-23-6 | 1 | 3.3→5V level shifter |
| R_DATA | 300Ω | 0805 | 1 | NeoPixel data line series |
| R_TERM | 50Ω | 0805 | 1 | NeoPixel end termination |
| C_BULK | 1000µF 10V | Radial through-hole | 1 | NeoPixel power bulk cap |

---

## 7. Acceptance Checks

| Check | Method | Pass |
|-------|--------|------|
| Veto button GPIO | `gpioget gpiochip0 5` (released) = 1; (pressed) = 0 | Correct logic levels |
| Sign button GPIO | Same on GPIO6 | Correct logic levels |
| Veto LED | `gpioset gpiochip0 13=1` | Red LED illuminates in button |
| Sign LED | `gpioset gpiochip0 19=1` | Green LED illuminates in button |
| NeoPixel strip | Run `led_state_daemon.py --test` | All 30 LEDs cycle colors |
| Power at strip | Multimeter at J_NEO_IN pin 1 | 4.9–5.1V under load |
| Data line high level | Oscilloscope at WS2812B DIN | Logic HIGH > 3.5V |
