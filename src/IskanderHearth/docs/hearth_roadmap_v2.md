# Iskander Hearth — Strategic Roadmap v2

**Phases 5–8: Custom Electronics, Physical UX, Thermal Validation, Distributed Manufacturing**

| Field | Value |
|-------|-------|
| Status | Draft |
| License | CERN-OHL-S v2 |
| Depends on | Phases 1–4 (existing repository) |
| Component ID Range | P5-001 → P8-006 |

---

## Phase Dependency Graph

```
Phase 5 ── Solidarity HAT PCB (KiCad)
  ├──► Phase 6 ── Glass Box Physical UX (depends on HAT GPIO pinout)
  │       └──► Phase 7 ── Thermal & Acoustic Validation (depends on chassis v2 geometry)
  └──────────► Phase 8 ── Distributed Manufacturing (depends on all phases at v1 release)
```

Phases 5 and 7 can partially overlap: CFD simulation begins on chassis v1 geometry while HAT/UX hardware stabilizes, then re-runs on v2.

---

## Phase 5: "Solidarity HAT" — Custom Open PCB

### Objective

Consolidate three discrete modules — hardware kill switches, INA3221 power sensor, and ATECC608B secure element — onto a single open-source PCB. HAT form-factor (65×56mm), designed in KiCad 8.x. Eliminates loose wiring. Adds air-gapped privacy controls absent from any off-the-shelf motherboard.

### Engineering Tasks

| Task | Output File | Tool |
|------|-------------|------|
| Schematic capture | `pcb/solidarity_hat/solidarity_hat_v1.kicad_sch` | KiCad 8.x |
| PCB layout (2-layer, 1.6mm FR4) | `pcb/solidarity_hat/solidarity_hat_v1.kicad_pcb` | KiCad 8.x |
| Gerber + drill export | `pcb/solidarity_hat/gerbers/` | KiCad Fabrication Output |
| Component footprint library | `pcb/solidarity_hat/libs/iskander_hearth.pretty/` | KiCad Footprint Editor |
| Schematic symbol library | `pcb/solidarity_hat/libs/iskander_hearth.kicad_sym` | KiCad Symbol Editor |
| Interactive HTML BOM | `pcb/solidarity_hat/bom/ibom.html` | InteractiveHtmlBom plugin |
| BOM CSV addendum | `boms/solidarity_hat_bom.csv` | KiCad BOM export + manual |
| Kill switch handler firmware | `firmware/solidarity_hat/kill_switch_handler.c` | gcc-arm / avr-gcc |
| INA3221 polling daemon | `firmware/solidarity_hat/ina3221_poller.py` | Python 3 + smbus2 (MIT) |
| ATECC608B provisioning script | `firmware/solidarity_hat/atecc_provision.py` | Python 3 + cryptoauthlib (MIT) |
| Assembly guide addendum | `assembly_guides/installing_solidarity_hat.md` | Markdown |
| Material Passport entries | `supply_chain/passports/solidarity_hat_passport.csv` | CSV |

### BOM Additions

| ID | Component | Specs | Est. Cost | Notes |
|----|-----------|-------|-----------|-------|
| P5-001 | SPDT toggle switch ×3 | 6A 250VAC, panel-mount, M12 | $9 (3× $3) | Mic, Wi-Fi antenna, GPU power. Physical air-gap — breaks circuit trace, not software mute. |
| P5-002 | INA3221 IC | TI INA3221AIDR, SOIC-14 | $4 | Replaces breakout board. Integrated on HAT for solar/battery graceful degradation. |
| P5-003 | ATECC608B | Microchip ATECC608B-MAHDA-S, SOIC-8 | $1.50 | Secure element. ECC-P256 key storage for Web3 Safe multi-sig. Alternative to discrete TPM for Tier 1/2. |
| P5-004 | 2×20 pin header | 2.54mm pitch, vertical | $0.50 | Connects HAT to motherboard I2C/GPIO or USB-I2C bridge. |
| P5-005 | PCB fabrication | 2-layer, HASL, 65×56mm | $15 (5 units, JLCPCB) | Minimum order 5. Target OSHWA certification. |
| P5-006 | Status LEDs ×4 | 0805 SMD, green/red/amber/blue | $0.40 | Power, I2C activity, kill-switch state, secure enclave heartbeat. |
| P5-007 | Decoupling capacitors | 100nF + 10µF ceramic, 0805 | $0.30 | Standard I2C bus decoupling. |
| P5-008 | 10-pin IDC connector | 2.54mm, TPM passthrough | $0.60 | Optional: passes TPM signal to motherboard header if ATECC608B not used. |

**Estimated per-unit cost:** ~$31

### Kill Switch Architecture

Each switch physically interrupts a power trace on the HAT PCB:
- **Mic kill:** Cuts 3.3V supply to USB audio MEMS microphone.
- **Wi-Fi kill:** Cuts 3.3V supply to M.2 Wi-Fi module via relay trace.
- **GPU kill:** Cuts PCIe AUX power enable signal (GPU enters safe power-down, does not hard-cut 12V rail).

All three switches accessible on the rear I/O bracket without opening the chassis.

### Secure Enclave Specification

- ATECC608B stores up to 16 ECC-P256 key slots.
- Slot 0: Web3 Safe multi-sig signing key (never leaves hardware).
- Slot 1: Node identity key (mutual TLS between federation nodes).
- Provisioning via `atecc_provision.py` during first-boot setup flow.
- I2C address: 0x60 (default). Shared bus with INA3221 at 0x40.

### Acceptance Criteria

1. KiCad DRC passes with zero errors.
2. KiCad ERC passes with zero errors.
3. Gerbers verified via JLCPCB online viewer before fabrication order.
4. Kill switches verified with continuity tester — open circuit when toggled.
5. INA3221 responds on I2C bus at 0x40; reads voltage/current/power on 3 channels.
6. ATECC608B responds to cryptoauthlib `info` command.
7. OSHWA open hardware certification checklist completed.

---

## Phase 6: Tangible AI — "Glass Box" Physical UX

### Objective

If Iskander OS enforces a Glass Box protocol for AI transparency, the physical chassis must embody it. Add two arcade-style HITL buttons (Veto / Sign) to the front panel and a NeoPixel LED status matrix to the top panel. All controlled via the Solidarity HAT GPIO lines.

### Engineering Tasks

| Task | Output File | Tool |
|------|-------------|------|
| Front panel button bracket | `enclosures/hitl_button_bracket_v1.scad` | OpenSCAD |
| LED matrix top panel mount | `enclosures/led_matrix_mount_v1.scad` | OpenSCAD |
| Chassis v2 (integrates HAT + UX) | `enclosures/hearth_chassis_v2.scad` | OpenSCAD |
| Sensor HAT mounting bracket | `enclosures/sensor_hat_bracket.scad` | OpenSCAD |
| Button handler daemon | `software/glass_box/button_handler.py` | Python 3 + libgpiod |
| LED state daemon | `software/glass_box/led_state_daemon.py` | Python 3 + rpi_ws281x |
| LED state protocol spec | `software/glass_box/led_protocol.md` | Markdown |
| systemd service: buttons | `software/glass_box/systemd/hearth-buttons.service` | systemd |
| systemd service: LEDs | `software/glass_box/systemd/hearth-leds.service` | systemd |
| Wiring schematic | `pcb/glass_box_wiring/glass_box_wiring.kicad_sch` | KiCad 8.x |
| Assembly guide addendum | `assembly_guides/installing_glass_box_ux.md` | Markdown |

### BOM Additions

| ID | Component | Specs | Est. Cost | Notes |
|----|-----------|-------|-----------|-------|
| P6-001 | Arcade button ×2 | 30mm, LED-illuminated, momentary, Sanwa OBSA-30 | $8 (2× $4) | Veto = red illumination. Sign = green illumination. NO + NC contacts. |
| P6-002 | NeoPixel strip (WS2812B) | 60 LEDs/m, 5V, IP30, 0.5m | $6 | Cut to fit top panel diffuser window. Data pin from HAT GPIO. |
| P6-003 | Diffuser panel | 3mm frosted acrylic, laser-cut to top panel dims | $5 | Softens individual LED dots into ambient glow. |
| P6-004 | 5V 2A buck regulator | Pololu D24V22F5 or Mini-360 | $3 | Powers NeoPixels from 12V PSU rail. |
| P6-005 | JST-XH connectors ×4 | 2.54mm, 3-pin + 4-pin | $2 | Tool-free disconnect for maintenance. |

**Estimated per-unit cost:** ~$24

### LED State Protocol

| Pattern | State | Color | Trigger |
|---------|-------|-------|---------|
| Slow pulse (2s period) | Idle / healthy | Blue | Default when no tasks active |
| Fast pulse (0.5s period) | LLM inference active | White | Inference engine processing |
| Solid | Multi-sig transaction pending | Amber | Transaction awaiting HITL approval |
| Chase animation (rotating) | Signing in progress | Green | After Sign button confirmed |
| Flash (3 Hz, 3 cycles) | Transaction vetoed | Red | After Veto button pressed |
| Rainbow sweep | First-boot / setup mode | Rainbow | Initial provisioning flow |
| Off | Node powered down | — | No power or critical fault |

LED state updates must propagate within 500ms of OS state change.

### Button Handler Logic

- **Debounce:** 50ms hardware (RC filter on HAT) + 50ms software.
- **Veto button:** Single press sends `VETO` signal to Iskander OS multi-sig daemon via Unix domain socket.
- **Sign button:** Requires 3-second sustained hold to confirm. Prevents accidental signing.
- **Emergency shutdown:** Both buttons held 10 seconds triggers graceful poweroff.
- **Daemons run as non-root systemd services** under a dedicated `hearth-ux` user.

### OpenSCAD Integration

`hearth_chassis_v2.scad` imports v1 and overrides:
- `front_panel()` — adds 2× 30mm arcade button cutouts alongside existing 16mm power button.
- `top_panel()` — adds recessed NeoPixel channel with diffuser clip rails.
- Inherits all v1 parameters: `wall_thickness`, `fit_tolerance`, `ext_w`, `ext_h`, `fan_size`.

### Acceptance Criteria

1. Veto button physically prevents multi-sig transaction completion.
2. Sign button + 3s hold triggers transaction signature.
3. LED state reflects AI agent state within 500ms.
4. Chassis v2 renders in OpenSCAD without errors; all panels export to STL.
5. Button + LED wiring uses tool-free JST-XH connectors.
6. Daemons run as non-root systemd services.

---

## Phase 7: Thermal & Acoustic Validation

### Objective

Running local Llama 3 on refurbished GPUs (RTX 3060 at 140W TDP) generates significant heat and noise. Unacceptable for a living room or shared office. Validate airflow via CFD simulation, optimize fan selection and ducting, and implement thermal throttling scripts that bridge OS and hardware.

**Targets:**
- GPU junction temperature: <83°C under sustained inference.
- System noise: <35 dBA at 1m (shared office), <30 dBA at 2m (living room).

### Engineering Tasks

| Task | Output File | Tool |
|------|-------------|------|
| OpenFOAM case directory | `thermal/openfoam/hearth_t2_thermal/` | OpenFOAM v2312+ |
| Chassis interior STL mesh | `thermal/openfoam/hearth_t2_thermal/constant/triSurface/chassis_interior.stl` | OpenSCAD export → snappyHexMesh |
| Fan duct module | `enclosures/fan_duct_v1.scad` | OpenSCAD |
| 140mm fan mount adapter | `enclosures/fan_140mm_adapter_v1.scad` | OpenSCAD |
| Chassis v2 fan mount updates | `enclosures/hearth_chassis_v2.scad` (rear/top panel mods) | OpenSCAD |
| GPU thermal throttle script | `software/thermal/gpu_thermal_manager.sh` | Bash + nvidia-smi |
| CPU thermal tuning service | `software/thermal/cpu_thermal_manager.service` | systemd + tuned |
| Acoustic test protocol | `thermal/acoustic_test_protocol.md` | Markdown |
| Thermal test results template | `thermal/thermal_test_results_template.csv` | CSV |
| ParaView visualization state | `thermal/openfoam/hearth_t2_thermal/paraview_state.pvsm` | ParaView 5.12+ |

### BOM Additions

| ID | Component | Specs | Est. Cost | Notes |
|----|-----------|-------|-----------|-------|
| P7-001 | Noctua NF-A12x25 PWM | 120mm, 450–2000 RPM, 22.6 dBA max, 102.1 m³/h | $30 | Reference intake fan. Replaces generic chassis fan for acoustic target. |
| P7-002 | Noctua NF-A14 PWM | 140mm, 300–1500 RPM, 24.6 dBA max, 140.2 m³/h | $30 | Alternative if top panel supports 140mm mount (requires adapter). |
| P7-003 | Thermal pads (GPU VRM) | Thermalright Odyssey, 12.8 W/mK, 1.5mm, 120×120mm | $8 | Replaces stock pads on refurbished GPUs. Critical for sustained inference. |
| P7-004 | Fan splitter cable (PWM) | 1-to-2, 4-pin PWM | $3 | Both chassis fans on single motherboard header, shared PWM curve. |

**Estimated per-unit cost:** ~$71

### OpenFOAM CFD Specification

| Parameter | Value |
|-----------|-------|
| Solver | `buoyantSimpleFoam` (steady-state, buoyancy + forced convection) |
| Mesh | snappyHexMesh from chassis + component ghost STLs |
| GPU heat source | 85W surface flux (RTX 3060 at 140W PL, ~60% radiated from heatsink) |
| CPU heat source | 25W surface flux |
| Fan boundary | Velocity inlet computed from fan curve at operating point |
| Turbulence model | k-ω SST |
| Convergence target | Residuals < 1×10⁻⁴ |
| Post-processing | ParaView state file for reproducible temperature field + streamline visualization |

### GPU Thermal Throttle Logic (`gpu_thermal_manager.sh`)

```
Poll nvidia-smi every 5s:
  GPU > 80°C  → reduce power limit by 10W
  GPU > 85°C  → clamp power limit to 100W minimum
  GPU < 70°C for 60s → restore configured maximum PL
  LLM queue empty > 5 min → lock GPU to lowest P-state (nvidia-smi -lgc 210,210)
Log all transitions to systemd journal.
```

### Acoustic Budget

| Deployment | Target | Distance | Measurement Tool |
|------------|--------|----------|------------------|
| Living room | < 30 dBA | 2m | NIOSH SLM app or calibrated SPL meter |
| Shared office | < 35 dBA | 1m | Same |
| Server closet | < 45 dBA | 0.5m | Same |

### Acceptance Criteria

1. OpenFOAM simulation converges (residuals < 1×10⁻⁴).
2. Simulated GPU junction < 83°C at sustained 140W PL.
3. Physical prototype: GPU < 83°C during 30-minute `gpu-burn` at configured PL.
4. Acoustic measurement: < 35 dBA at 1m with Noctua fans during inference.
5. Thermal throttle script prevents GPU from exceeding 85°C under any load.
6. Fan duct STL prints without supports and clips into chassis v2.

---

## Phase 8: Distributed Cooperative Manufacturing

### Objective

Define the complete replication package for any Maker-Coop, FabLab, or informal workshop to manufacture, assemble, test, and ship Iskander Hearth nodes. No franchise agreements. No centralized production. No permission required. CERN-OHL-S compliance throughout.

### Engineering Tasks

| Task | Output File | Tool |
|------|-------------|------|
| Hearth Builder Network guide | `manufacturing/hearth_builder_network_guide.md` | Markdown |
| CERN-OHL-S manufacturing checklist | `manufacturing/cern_ohls_manufacturing_checklist.md` | Markdown |
| QA/QC test checklist (per-node) | `manufacturing/qa_qc_checklist.csv` | CSV |
| Automated QA test script | `manufacturing/qa_automated_test.sh` | Bash |
| Flash-and-ship procedure | `manufacturing/flash_and_ship.md` | Markdown |
| DisCO value-tracking spec | `manufacturing/disco_labor_accounting.md` | Markdown |
| Packaging and labeling spec | `manufacturing/packaging_spec.md` | Markdown |
| Micro-factory equipment BOM | `manufacturing/microfactory_equipment_bom.csv` | CSV |
| Builder self-assessment | `manufacturing/builder_self_assessment.md` | Markdown |
| Tier 1 Seed enclosure | `enclosures/tier1_seed_case_v1.scad` | OpenSCAD |
| Tier 3 Federation rack panel | `enclosures/tier3_federation_panel_v1.scad` | OpenSCAD |

### Micro-factory Equipment BOM (One-time Setup)

| ID | Equipment | Specs | Est. Cost | Purpose |
|----|-----------|-------|-----------|---------|
| P8-001 | FDM 3D printer | Bambu Lab A1 or Prusa MK4, 256³mm build vol, PETG-capable | $400–600 | Chassis panels, brackets, QR tiles |
| P8-002 | Soldering station | Hakko FX-888D or Pinecil V2, temp-controlled | $70–100 | HAT assembly, sensor wiring |
| P8-003 | USB flash duplicator | 1-to-7, standalone | $80 | Bulk Iskander OS flashing |
| P8-004 | Digital multimeter | Fluke 101 or UNI-T UT61E | $30–50 | Kill switch continuity, voltage verification |
| P8-005 | Anti-static mat + wrist strap | 600×500mm, grounded | $25 | ESD protection during assembly |
| P8-006 | Label printer | Brother QL-820NWB, 62mm labels | $100 | QR codes, node ID, packaging labels |

**Estimated micro-factory setup:** ~$705–955 (one-time, amortized across all builds)

### QA/QC Checklist Fields (Per Node)

```
node_serial, builder_coop_id, build_date, tier,
cpu_stress_pass, ram_memtest_pass, gpu_burn_pass, nvme_smart_ok,
tpm_detected, ina3221_detected, kill_switches_continuity,
ups_nut_detected, graceful_degrade_test_pass,
os_version_flashed, os_checksum_verified,
qr_codes_affixed, chassis_closed_clean,
acoustic_test_dba, thermal_test_gpu_max_c,
material_passport_completed, shipped_date, shipped_to_coop
```

### Flash-and-Ship Procedure

1. Flash Iskander OS to NVMe via USB duplicator station.
2. First boot in test jig (monitor + keyboard + Ethernet).
3. Run `manufacturing/qa_automated_test.sh` — automated hardware verification.
4. Seal chassis, affix QR repair codes.
5. Print Material Passport, include in packaging.
6. Print CERN-OHL-S license summary card.
7. Ship with: node, power cable, Ethernet cable, UPS, antenna rods, USB installer backup, printed setup card.

**Target:** Under 2 hours per node (excluding 3D print time).

### CERN-OHL-S Manufacturing Compliance

- Source Location notice maintained on all distributed hardware.
- License text accompanies every shipped node (printed or digital).
- All modifications shared under the same license.
- No trademark restriction on "Iskander" when describing compatible builds.
- Derivative works must clearly state modifications.

### DisCO Value-Tracking Integration

DisCO (Distributed Cooperative Organization) tracks three value types:
- **Productive:** Direct build labor (assembly, testing, shipping).
- **Reproductive:** Maintenance labor (documentation updates, supply chain management).
- **Care:** Community labor (training new builders, support).

Each build step logged with labor hours and contributor handle. Integration point: Iskander OS cooperative ledger stores build labor records. Schema and API contract defined in `disco_labor_accounting.md`.

### Franchise-Free Replication Model

- No permission required to build or sell Iskander Hearth nodes.
- No royalties, fees, or franchise agreements.
- "Hearth Builder" is self-declared, not centrally granted.
- Builder self-assessment checklist replaces certification.
- Disputes resolved via cooperative federation governance, not legal enforcement.

### Acceptance Criteria

1. An external FabLab with no prior Iskander knowledge builds a Tier 2 node from documentation alone.
2. CERN-OHL-S compliance checklist passes legal review.
3. QA/QC checklist covers all functional requirements from Phases 1–7.
4. Flash-and-ship completes in under 2 hours per node.
5. DisCO labor accounting schema validated against DisCO.coop reference implementation.
6. Tier 1 and Tier 3 enclosure OpenSCAD files render and export to STL.

---

## Phase Sequencing

| Phase | Can Start | Blocked Until | Est. Duration |
|-------|-----------|---------------|---------------|
| 5 — Solidarity HAT | Immediately | — | 8–12 weeks |
| 6 — Glass Box UX | After Phase 5 schematic freeze | GPIO pinout locked | 4–6 weeks |
| 7 — Thermal Validation | After Phase 6 chassis v2 stable | Enclosure geometry locked | 6–8 weeks |
| 8 — Distributed Mfg | After Phase 7 complete | All phases at v1 | 4–6 weeks |

**Total estimated timeline:** 22–32 weeks (sequential). Partial overlap between 5/7 reduces to ~18–26 weeks.

---

## Cumulative Per-Node Cost Impact

| Phase | Added Cost | Running Total (Tier 2 base: ~$960–1150) |
|-------|------------|------------------------------------------|
| 5 — Solidarity HAT | ~$31 | ~$991–1181 |
| 6 — Glass Box UX | ~$24 | ~$1015–1205 |
| 7 — Thermal Upgrade | ~$71 | ~$1086–1276 |
| **Total added** | **~$126** | **~$1086–1276** |

Phase 8 adds no per-node cost — only micro-factory setup ($705–955 one-time).

---

## New Repository Structure (Additions)

```
IskanderHearth/
├── docs/
│   └── hearth_roadmap_v2.md              ← this document
├── pcb/
│   ├── solidarity_hat/
│   │   ├── solidarity_hat_v1.kicad_sch
│   │   ├── solidarity_hat_v1.kicad_pcb
│   │   ├── gerbers/
│   │   ├── libs/
│   │   │   ├── iskander_hearth.pretty/
│   │   │   └── iskander_hearth.kicad_sym
│   │   └── bom/
│   │       └── ibom.html
│   └── glass_box_wiring/
│       └── glass_box_wiring.kicad_sch
├── firmware/
│   └── solidarity_hat/
│       ├── kill_switch_handler.c
│       ├── ina3221_poller.py
│       └── atecc_provision.py
├── software/
│   ├── glass_box/
│   │   ├── button_handler.py
│   │   ├── led_state_daemon.py
│   │   ├── led_protocol.md
│   │   └── systemd/
│   │       ├── hearth-buttons.service
│   │       └── hearth-leds.service
│   └── thermal/
│       ├── gpu_thermal_manager.sh
│       └── cpu_thermal_manager.service
├── thermal/
│   ├── openfoam/
│   │   └── hearth_t2_thermal/
│   │       ├── 0/
│   │       ├── constant/triSurface/chassis_interior.stl
│   │       ├── system/
│   │       └── paraview_state.pvsm
│   ├── acoustic_test_protocol.md
│   └── thermal_test_results_template.csv
├── manufacturing/
│   ├── hearth_builder_network_guide.md
│   ├── cern_ohls_manufacturing_checklist.md
│   ├── qa_qc_checklist.csv
│   ├── qa_automated_test.sh
│   ├── flash_and_ship.md
│   ├── disco_labor_accounting.md
│   ├── packaging_spec.md
│   ├── microfactory_equipment_bom.csv
│   └── builder_self_assessment.md
├── enclosures/
│   ├── (existing v1 files)
│   ├── hearth_chassis_v2.scad
│   ├── hitl_button_bracket_v1.scad
│   ├── led_matrix_mount_v1.scad
│   ├── fan_duct_v1.scad
│   ├── fan_140mm_adapter_v1.scad
│   ├── sensor_hat_bracket.scad
│   ├── tier1_seed_case_v1.scad
│   └── tier3_federation_panel_v1.scad
├── boms/
│   ├── (existing tier CSVs)
│   └── solidarity_hat_bom.csv
└── assembly_guides/
    ├── (existing guides)
    ├── installing_solidarity_hat.md
    └── installing_glass_box_ux.md
```

---

## Open-Source Toolchain Summary

| Domain | Tool | License | Phase |
|--------|------|---------|-------|
| PCB design | KiCad 8.x | GPL-3.0 | 5, 6 |
| Interactive BOM | InteractiveHtmlBom | MIT | 5 |
| Secure element SDK | cryptoauthlib | MIT | 5 |
| I2C communication | smbus2 (Python) | MIT | 5 |
| Parametric CAD | OpenSCAD | GPL-2.0 | 6, 7, 8 |
| CFD simulation | OpenFOAM v2312+ | GPL-3.0 | 7 |
| CFD post-processing | ParaView 5.12+ | BSD-3 | 7 |
| GPU management | nvidia-smi | Proprietary (driver) | 7 |
| LED control | rpi_ws281x | BSD-2 | 6 |
| GPIO control | libgpiod | LGPL-2.1 | 6 |
