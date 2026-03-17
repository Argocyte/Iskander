# Solidarity HAT — KiCad 8.x Project

**License:** CERN-OHL-S v2
**Board:** `solidarity_hat_v1` | 2-layer | 1.6mm FR4 | HASL | 65×56mm
**Target fab:** JLCPCB (5-unit minimum, ~$15/run)

## Project Files

| File | Description |
|------|-------------|
| `solidarity_hat_v1.kicad_sch` | Schematic — captured from `pinout_and_nets.md` netlist |
| `solidarity_hat_v1.kicad_pcb` | PCB layout — 2-layer, routed per netlist constraints below |
| `solidarity_hat_v1.kicad_pro` | Project file — KiCad 8.x |
| `fp-lib-table` | Footprint library table (points to `../libs/iskander_hearth.pretty/`) |
| `sym-lib-table` | Symbol library table (points to `../libs/iskander_hearth.kicad_sym`) |

## Design Rules (DRC constraints)

| Parameter | Value | Reason |
|-----------|-------|--------|
| Min trace width | 0.2mm | Standard HASL 2-layer capability |
| Min clearance | 0.2mm | Same |
| Kill switch power traces | 0.8mm min | Rated for 500mA USB/signal currents |
| I2C traces | 0.2mm | Low-current signal |
| Via drill | 0.4mm min | JLCPCB standard |
| Via annular ring | 0.2mm | JLCPCB standard |
| Board edge clearance | 0.5mm | Standard keepout |

## Layer Stack

| Layer | Purpose |
|-------|---------|
| F.Cu | Signal + power routing |
| B.Cu | Ground plane (poured) |
| F.SilkS | Component labels, orientation markers |
| B.SilkS | Board ID, license notice, OSHWA UID |
| F.Mask / B.Mask | Solder mask |
| Edge.Cuts | 65×56mm board outline |

## Human Engineer Routing Notes

1. Route I2C traces (SDA/SCL) together. Keep under 10cm. Add 4.7kΩ pull-ups to 3.3V near J1.
2. Kill switch traces must be **fully broken** (no copper bridge) when switch is open. Confirm with DRC net-tie check.
3. INA3221 IN±pins must be Kelvin-connected to shunt resistors (R_SHUNT1–3, 0.1Ω 1%).
4. ATECC608B decoupling: 100nF cap within 2mm of VCC pin.
5. All kill-switch state GPIO lines need 10kΩ pull-down to GND on HAT side.
6. Pour B.Cu ground plane. Connect via stitching vias every 10mm along board perimeter.

## Gerber Export Settings (KiCad → Fabrication Outputs)

- Format: Gerber RS-274X
- Include board edge in all layers: YES
- Drill file: Excellon, metric, suppress trailing zeros
- Map file: YES
- Export to: `../gerbers/`

## Pre-fabrication checklist

- [ ] KiCad ERC: 0 errors
- [ ] KiCad DRC: 0 errors
- [ ] Gerbers reviewed in JLCPCB online viewer
- [ ] Kill switch continuity verified in schematic net inspector
- [ ] InteractiveHtmlBom generated → `../bom/ibom.html`
- [ ] OSHWA certification UID affixed to B.SilkS layer
