# Solidarity HAT v1 — Pinout & Netlist Definition

**License:** CERN-OHL-S v2
**Revision:** 1.0 | 2026-03-16
**Form factor:** 65×56mm, 2-layer FR4

> **Security rationale:** Software privacy is provably insufficient against state-level and corporate adversaries
> with kernel access. Hardware kill switches are the only mathematically sound countermeasure —
> they break the physical circuit, eliminating the possibility of firmware-level re-enablement.
> This document defines those circuit breaks with enough precision to eliminate ambiguity during layout.

---

## 1. Connector Reference Designators

| Ref | Type | Description |
|-----|------|-------------|
| J1 | 2×20 2.54mm male header | Main HAT ↔ host motherboard I2C/GPIO bus |
| J2 | 9-pin USB 2.0 internal header (2×5 -1 key) | Mic USB passthrough with SW1 inline on VCC |
| J3 | 4-pin dupont 2.54mm | Wi-Fi M.2 enable line + SW2 state read |
| J4 | 4-pin dupont 2.54mm | GPU PCIe AUX power enable + SW3 state read |
| J5 | 10-pin IDC 2.54mm | TPM 2.0 passthrough (optional: when ATECC608B not fitted) |
| J6 | 3-pin JST-XH | INA3221 CH1 shunt terminals (12V system rail) |
| J7 | 3-pin JST-XH | INA3221 CH2 shunt terminals (solar/battery rail) |
| J8 | 3-pin JST-XH | INA3221 CH3 shunt terminals (3.3V aux rail) |

---

## 2. J1 — Main HAT Header Pinout (2×20, 2.54mm pitch)

This is the primary electrical interface to the host system.
On desktop motherboards without a native GPIO header, use a USB-I2C bridge
(e.g., CH341A or CP2112) and connect only the I2C + power pins.

| Pin | Name | Direction | Net | Description |
|-----|------|-----------|-----|-------------|
| 1 | 3V3 | PWR IN | +3V3 | 3.3V supply from host |
| 2 | 5V | PWR IN | +5V | 5V supply (unused, reserved) |
| 3 | SDA | BIDIR | I2C_SDA | I2C data — shared bus (INA3221 + ATECC608B) |
| 4 | 5V | PWR IN | +5V | (unused) |
| 5 | SCL | OUTPUT host | I2C_SCL | I2C clock |
| 6 | GND | PWR | GND | Ground |
| 7 | GPIO4 | INPUT host | GPIO_MIC_KILL | Reads SW1 state (logic HIGH = mic killed) |
| 8 | GPIO14 | — | NC | Reserved Phase 6 |
| 9 | GND | PWR | GND | Ground |
| 10 | GPIO15 | — | NC | Reserved Phase 6 |
| 11 | GPIO17 | INPUT host | GPIO_WIFI_KILL | Reads SW2 state (logic HIGH = Wi-Fi killed) |
| 12 | GPIO18 | — | NC | Reserved Phase 6 |
| 13 | GPIO27 | INPUT host | GPIO_GPU_KILL | Reads SW3 state (logic HIGH = GPU killed) |
| 14 | GND | PWR | GND | Ground |
| 15 | GPIO22 | INPUT host | GPIO_ATECC_IRQ | ATECC608B alert interrupt (active LOW) |
| 16 | GPIO23 | OUTPUT host | GPIO_LED_I2C_ACT | I2C activity LED drive |
| 17 | 3V3 | PWR | +3V3 | 3.3V supply (redundant) |
| 18 | GPIO24 | — | NC | Reserved |
| 19 | GPIO10 | — | NC | Reserved |
| 20 | GND | PWR | GND | Ground |
| 21–40 | — | — | NC | Reserved for Phase 6 Glass Box UX |

**Pull resistors on HAT:**
- GPIO4 (MIC_KILL), GPIO17 (WIFI_KILL), GPIO27 (GPU_KILL): 10kΩ pull-down to GND (active HIGH from SW pole 2)

---

## 3. J2 — USB 2.0 Internal Header (Mic Kill Passthrough)

Standard Intel/AMD 9-pin internal USB 2.0 header pinout.
SW1 Pole 1 is wired **inline on the +5V VCC pin only**.
D+/D- and GND pass through uninterrupted to preserve device enumeration state.
When SW1 opens: VCC is cut → USB MEMS mic loses power → hardware air-gap.

| Pin | Name | Net (HAT side) | Net (device side) | Notes |
|-----|------|----------------|-------------------|-------|
| 1 | VCC | USB_VCC1_IN | USB_VCC1_SWITCHED | **Interrupted by SW1 Pole 1** |
| 2 | D− | USB_D_NEG1 | USB_D_NEG1 | Straight passthrough |
| 3 | D+ | USB_D_POS1 | USB_D_POS1 | Straight passthrough |
| 4 | GND | GND | GND | Common ground |
| 5 | VCC | USB_VCC2_IN | USB_VCC2_IN | Port 2 VCC — passthrough (unused port) |
| 6 | D− | USB_D_NEG2 | USB_D_NEG2 | Passthrough |
| 7 | D+ | USB_D_POS2 | USB_D_POS2 | Passthrough |
| 8 | GND | GND | GND | Common ground |
| 9 | KEY | — | — | No pin (keyed position) |

---

## 4. J3 — Wi-Fi Enable Header

Connects between motherboard M.2 slot power enable GPIO and M.2 Wi-Fi module.
SW2 Pole 1 breaks the enable line, putting the Wi-Fi module into hardware power-down.

| Pin | Name | Net | Description |
|-----|------|-----|-------------|
| 1 | WIFI_EN_IN | WIFI_EN_IN | From motherboard GPIO / M.2 CLKREQ# |
| 2 | WIFI_EN_OUT | WIFI_EN_SWITCHED | **Interrupted by SW2 Pole 1** → to M.2 enable pin |
| 3 | GND | GND | Ground reference |
| 4 | 3V3_M2 | +3V3 | 3.3V rail reference (sense only, not switched here) |

---

## 5. J4 — GPU PCIe AUX Enable Header

Connects between PCIe slot AUX power enable signal and GPU.
SW3 Pole 1 cuts the AUX enable → GPU enters safe power-down (does NOT hard-cut 12V).
This is the correct approach: hard-cutting 12V under load can damage the GPU.

| Pin | Name | Net | Description |
|-----|------|-----|-------------|
| 1 | GPU_EN_IN | GPU_PCIE_EN_IN | From PCIe slot AUX_PWR_EN signal |
| 2 | GPU_EN_OUT | GPU_PCIE_EN_SWITCHED | **Interrupted by SW3 Pole 1** → to GPU AUX_PWR_EN |
| 3 | GND | GND | Ground reference |
| 4 | 3V3_PCIE | +3V3 | 3.3V reference for enable logic |

---

## 6. Kill Switch Wiring (DPST Toggle Switches)

Each switch is **Double Pole Single Throw (DPST)**:
- **Pole 1:** Interrupts power/enable signal (true hardware air-gap)
- **Pole 2:** Connects GPIO_KILL_STATE line to +3.3V (HIGH = killed; pulled LOW by 10kΩ to GND when switch open)

| Switch | Ref | Pole 1 Circuit Break | Pole 2 GPIO Signal | Panel Label |
|--------|-----|---------------------|--------------------|-------------|
| SW1 | SW_MIC | USB_VCC1_IN → USB_VCC1_SWITCHED | GPIO_MIC_KILL → +3V3 | MIC KILL |
| SW2 | SW_WIFI | WIFI_EN_IN → WIFI_EN_SWITCHED | GPIO_WIFI_KILL → +3V3 | WIFI KILL |
| SW3 | SW_GPU | GPU_PCIE_EN_IN → GPU_PCIE_EN_SWITCHED | GPIO_GPU_KILL → +3V3 | GPU KILL |

**Switch specs (P5-001):** DPST, 6A 250VAC rated, panel-mount M12 thread, positive tactile detent.

---

## 7. U1 — INA3221AIDR (TI) Power Monitor

**I2C address:** 0x40 (A0=GND, A1=GND)
**Package:** SOIC-14
**Bus:** Shared I2C_SDA / I2C_SCL

| Pin | Name | Net | Description |
|-----|------|-----|-------------|
| 1 | VS | +3V3 | Supply (3.3V, 100nF + 10µF decoupling to GND) |
| 2 | GND | GND | Ground |
| 3 | IN1+ | INA_IN1P | CH1 positive input — connect to J6 pin 1 |
| 4 | IN1- | INA_IN1N | CH1 negative input — connect to J6 pin 2 |
| 5 | IN2+ | INA_IN2P | CH2 positive input — connect to J7 pin 1 |
| 6 | IN2- | INA_IN2N | CH2 negative input — connect to J7 pin 2 |
| 7 | IN3+ | INA_IN3P | CH3 positive input — connect to J8 pin 1 |
| 8 | IN3- | INA_IN3N | CH3 negative input — connect to J8 pin 2 |
| 9 | A0 | GND | Address bit 0 = 0 |
| 10 | A1 | GND | Address bit 1 = 0 → address 0x40 |
| 11 | SDA | I2C_SDA | I2C data |
| 12 | SCL | I2C_SCL | I2C clock |
| 13 | /PV | NC | Power-valid open-drain (leave unconnected or pull to +3V3) |
| 14 | /WRN | NC | Warning alert (NC — software polls registers) |

**Shunt resistors:** R_SHUNT1, R_SHUNT2, R_SHUNT3 = 0.1Ω, 1%, 1W, 2512 package.
Place inline between INx+ and INx- Kelvin connections.

**Channel assignments:**

| Channel | Net | Measurement | Full-scale voltage |
|---------|-----|-------------|-------------------|
| CH1 | J6 | 12V system rail (via 10:1 resistor divider) | 26V input range |
| CH2 | J7 | Solar/battery rail (direct if ≤26V) | 26V input range |
| CH3 | J8 | 3.3V auxiliary rail (HAT internal) | 26V input range |

---

## 8. U2 — ATECC608B-MAHDA-S (Microchip) Secure Element

**I2C address:** 0x60 (default, SA0=GND)
**Package:** SOIC-8
**Bus:** Shared I2C_SDA / I2C_SCL
**Key slots:** 16 × ECC-P256

| Pin | Name | Net | Description |
|-----|------|-----|-------------|
| 1 | NC | NC | No connect |
| 2 | NC | NC | No connect |
| 3 | NC | NC | No connect |
| 4 | GND | GND | Ground |
| 5 | SDA | I2C_SDA | I2C data (single-wire capable; use I2C mode) |
| 6 | SCL | I2C_SCL | I2C clock |
| 7 | /RST | +3V3 | Active-LOW reset — tie HIGH (100nF filter cap to GND) |
| 8 | VCC | +3V3 | Supply (100nF decoupling within 2mm of pin) |

**Key provisioning (first-boot, `atecc_provision.py`):**
- Slot 0: Web3 Safe multi-sig signing key (ECC-P256, never leaves hardware)
- Slot 1: Node identity key (mutual TLS between federated Hearth nodes)
- Slots 2–15: Reserved for future cooperative key ceremonies

**I2C pull-ups:** R_PULL_SDA = R_PULL_SCL = 4.7kΩ to +3V3. Mount near J1 pins 3 and 5.

---

## 9. Status LEDs

| Ref | Color | Net | Description |
|-----|-------|-----|-------------|
| LED1 | Green (0805) | LED_PWR | HAT powered (3.3V present). Series R = 100Ω. |
| LED2 | Blue (0805) | LED_I2C_ACT | I2C bus activity (driven by GPIO_LED_I2C_ACT from J1 pin 16). Series R = 100Ω. |
| LED3 | Amber (0805) | LED_KILL_STATE | Any kill switch active (OR of GPIO_MIC_KILL, WIFI_KILL, GPU_KILL). Driven by small logic OR via 3× diode-OR network. Series R = 100Ω. |
| LED4 | Red (0805) | LED_ENCLAVE_BEAT | ATECC608B heartbeat (toggled by daemon every 5s via GPIO_ATECC_IRQ). Series R = 100Ω. |

---

## 10. Net Summary (Complete Netlist)

| Net Name | Connects |
|----------|---------|
| +3V3 | J1.1, J1.17, U1.1, U2.8, U2.7(via 100nF), LED1(anode via R), R_PULL_SDA, R_PULL_SCL, SW1.Pole2.common, SW2.Pole2.common, SW3.Pole2.common |
| GND | J1.6, J1.9, J1.14, J1.20, J2.4, J2.8, J3.3, J4.3, U1.2, U1.9, U1.10, U2.4, R_SHUNT1.sense−, R_SHUNT2.sense−, R_SHUNT3.sense−, Pull-downs for GPIO kill lines |
| I2C_SDA | J1.3, U1.11, U2.5, R_PULL_SDA.end |
| I2C_SCL | J1.5, U1.12, U2.6, R_PULL_SCL.end |
| GPIO_MIC_KILL | J1.7, SW1.Pole2.NO, pull-down 10kΩ to GND |
| GPIO_WIFI_KILL | J1.11, SW2.Pole2.NO, pull-down 10kΩ to GND |
| GPIO_GPU_KILL | J1.13, SW3.Pole2.NO, pull-down 10kΩ to GND |
| GPIO_ATECC_IRQ | J1.15, U2.8(IRQ, via firmware polling only — no physical IRQ pin on ATECC608B) |
| GPIO_LED_I2C_ACT | J1.16, LED2(anode via R) |
| USB_VCC1_IN | J2.1(host side) → SW1.Pole1.COM |
| USB_VCC1_SWITCHED | SW1.Pole1.NO → J2.1(device side) |
| USB_D_NEG1 | J2.2 (straight through) |
| USB_D_POS1 | J2.3 (straight through) |
| WIFI_EN_IN | J3.1 → SW2.Pole1.COM |
| WIFI_EN_SWITCHED | SW2.Pole1.NO → J3.2 |
| GPU_PCIE_EN_IN | J4.1 → SW3.Pole1.COM |
| GPU_PCIE_EN_SWITCHED | SW3.Pole1.NO → J4.2 |
| INA_IN1P | U1.3 → R_SHUNT1.1 → J6.1 |
| INA_IN1N | U1.4 → R_SHUNT1.2 → J6.2 |
| INA_IN2P | U1.5 → R_SHUNT2.1 → J7.1 |
| INA_IN2N | U1.6 → R_SHUNT2.2 → J7.2 |
| INA_IN3P | U1.7 → R_SHUNT3.1 → J8.1 |
| INA_IN3N | U1.8 → R_SHUNT3.2 → J8.2 |
| LED_PWR | LED1 anode (via 100Ω to +3V3), cathode to GND |
| LED_I2C_ACT | LED2 anode (via 100Ω from J1.16), cathode to GND |
| LED_KILL_STATE | LED3 anode (via 100Ω from diode-OR), cathode to GND |
| LED_ENCLAVE_BEAT | LED4 anode (via 100Ω from daemon-driven GPIO), cathode to GND |

---

## 11. Component Placement Notes (for KiCad layout)

```
+--65mm------------------------------------------+
|  [J1 2x20]                                     |  ← Left edge, top
|                                                 |
|  [U1 INA3221]  [U2 ATECC608B]                  |  ← Center
|  [LED1][LED2][LED3][LED4]                       |  ← Front edge row
|                                                 |
|  [J2 USB9]  [J3 4pin]  [J4 4pin]               |  ← Right edge
|  [J5 IDC10]                                     |  ← Bottom edge
|  [J6][J7][J8] JST-XH                           |  ← Bottom row
|  [SW1][SW2][SW3] panel-mount                   |  ← Panel cutout refs only;
+------------------------------------------------+     actual switches on I/O bracket
```

Panel-mount switches (SW1–3) are wired via flying leads to the I/O bracket.
PCB provides screw terminal or dupont pads for each switch lead.

---

## 12. Acceptance Checks

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| SW1 Mic kill | Continuity tester across USB_VCC1_IN ↔ USB_VCC1_SWITCHED | Open when SW1 OFF, closed when ON |
| SW2 Wi-Fi kill | Same across WIFI_EN_IN ↔ WIFI_EN_SWITCHED | Open when SW2 OFF |
| SW3 GPU kill | Same across GPU_PCIE_EN_IN ↔ GPU_PCIE_EN_SWITCHED | Open when SW3 OFF |
| INA3221 I2C | `i2cdetect -y 1` on host | Shows device at 0x40 |
| ATECC608B I2C | `i2cdetect -y 1` | Shows device at 0x60 |
| ATECC608B provisioning | `python3 atecc_provision.py --verify` | Returns slot 0 public key |
