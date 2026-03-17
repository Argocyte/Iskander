# Installing the Solidarity HAT

**License:** CERN-OHL-S v2
**Applies to:** Iskander Hearth Tier 1 (Seed) and Tier 2 (Commons) nodes
**Prerequisites:** Soldering station, multimeter, i2c-tools, Python 3.10+

---

## Overview

The Solidarity HAT is a 65×56mm open-source interface board that provides:
- **3× DPST hardware kill switches** (Mic, Wi-Fi, GPU) — physically break circuits
- **INA3221** 3-channel I2C power monitor for off-grid graceful degradation
- **ATECC608B** secure element for air-gapped Web3 multi-sig key storage

> **Why hardware matters:** Software kill switches can be bypassed by kernel exploits,
> firmware backdoors, or supply chain compromise. A DPST switch physically interrupts
> the copper trace. There is no software pathway to circumvent an open circuit.
> This is the only mathematically sound approach to cooperative privacy.

---

## 1. Pre-Installation Checks

### 1.1 Verify HAT functionality before mounting

Connect the bare HAT to a USB-I2C bridge (CH341A or CP2112):

```bash
# Scan I2C bus — expect 0x40 (INA3221) and 0x60 (ATECC608B)
i2cdetect -y 1

# Expected output includes:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 60
```

If either address is missing, check I2C pull-up resistors (R_PULL_SDA, R_PULL_SCL = 4.7kΩ).

### 1.2 Verify kill switch continuity

Use a multimeter in continuity mode:

| Switch | Test points | SW OFF | SW ON |
|--------|-------------|--------|-------|
| SW1 (Mic) | J2.1 (host) ↔ J2.1 (device) | **Open** | Closed |
| SW2 (Wi-Fi) | J3.1 ↔ J3.2 | **Open** | Closed |
| SW3 (GPU) | J4.1 ↔ J4.2 | **Open** | Closed |

All three must show **open circuit when switch is in the OFF (killed) position**.

---

## 2. Physical Mounting

### 2.1 Internal USB 2.0 header (Mic kill)

1. Locate the motherboard's internal USB 2.0 header (9-pin, near front-panel connectors).
2. Disconnect any existing front-panel USB cable.
3. Connect the **host-side** USB header cable from J2 to the motherboard header.
4. Connect the **device-side** USB header cable from J2 to the USB microphone or front-panel USB hub.
5. The SW1 kill switch is now inline on the +5V VCC pin.

### 2.2 Wi-Fi enable line (Wi-Fi kill)

1. Locate the M.2 Wi-Fi module (typically M.2 E-key slot).
2. Connect J3 flying leads between the motherboard M.2 CLKREQ# / enable GPIO and the module.
   Refer to your motherboard's service manual for the correct GPIO header pin.
3. SW2 is now inline on the Wi-Fi enable signal.

### 2.3 GPU PCIe AUX enable (GPU kill)

1. Locate the PCIe slot AUX power enable signal.
   On most consumer boards, this is a dedicated header labeled "PCIe_PWR_EN" or similar.
2. Connect J4 between the motherboard enable pin and the GPU's AUX power enable input.
3. SW3 is now inline. **Note:** This does NOT hard-cut the 12V rail. The GPU enters a
   controlled power-down state. Do not attempt to hard-cut 12V under load.

### 2.4 I2C/GPIO connection to host

**Option A — Native GPIO header (SBC or motherboard with GPIO header):**
Connect J1 (2×20 40-pin) directly to the host GPIO header.

**Option B — USB-I2C bridge (standard x86 desktop):**
1. Install a CH341A or CP2112 USB-I2C bridge.
2. Connect: Bridge SDA → J1.3, Bridge SCL → J1.5, Bridge +3.3V → J1.1, Bridge GND → J1.6.
3. For GPIO kill-state reading, add a USB-GPIO adapter connected to J1.7, J1.11, J1.13.
   Or use a microcontroller (Arduino Nano / Pi Pico) as a USB HID GPIO bridge.

### 2.5 Power sensor shunt connections

Connect the INA3221 shunt terminals (J6, J7, J8) inline with the circuits to monitor:

| Connector | Channel | Connect inline with |
|-----------|---------|---------------------|
| J6 | CH1 (12V system) | 12V PSU positive rail (via 0.1Ω shunt R_SHUNT1) |
| J7 | CH2 (Solar/battery) | Solar/battery positive terminal |
| J8 | CH3 (3.3V aux) | 3.3V motherboard AUX rail |

### 2.6 Kill switch panel mounting

1. Mount SW1, SW2, SW3 to the rear I/O bracket (M12 panel-mount holes, drill to fit).
2. Run flying leads from each switch to the corresponding HAT switch pads.
3. Label the bracket: **MIC KILL | WIFI KILL | GPU KILL** (printed or engraved).

---

## 3. Software Setup

### 3.1 Create service user

```bash
sudo useradd --system --no-create-home --groups gpio,i2c --shell /sbin/nologin hearth-hw
```

### 3.2 Install Python dependencies

```bash
cd /opt/iskander
python3 -m venv venv
source venv/bin/activate
pip install gpiozero smbus2 requests sdnotify cryptoauthlib
```

### 3.3 Provision ATECC608B (first boot only)

```bash
sudo -u hearth-hw /opt/iskander/venv/bin/python3 \
    /opt/iskander/firmware/solidarity_hat/atecc_provision.py

# Verify provisioning
python3 /opt/iskander/firmware/solidarity_hat/atecc_provision.py --verify
```

Provisioning record is saved to `/etc/iskander/atecc_provisioning.json` (public keys only).

### 3.4 Install and enable systemd services

```bash
sudo cp /opt/iskander/firmware/solidarity_hat/systemd/hearth-sovereignty.service \
        /etc/systemd/system/

sudo cp /opt/iskander/firmware/solidarity_hat/systemd/hearth-permacomputing.service \
        /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now hearth-sovereignty.service
sudo systemctl enable --now hearth-permacomputing.service
```

### 3.5 Verify daemons are running

```bash
sudo systemctl status hearth-sovereignty.service
sudo systemctl status hearth-permacomputing.service

# Watch live logs
sudo journalctl -u hearth-sovereignty -f
sudo journalctl -u hearth-permacomputing -f
```

Expected output when healthy:
```
hearth-sovereignty: Hardware verified — kill switch monitoring active.
hearth-sovereignty: Entering monitoring loop.
hearth-permacomputing: INA3221 initialized at I2C 0x40 on bus 1.
hearth-permacomputing: Active: monitoring battery/solar rail.
```

---

## 4. Functional Verification

### 4.1 Kill switch test

```bash
# Flip SW1 (Mic Kill) to OFF
# Check daemon log:
sudo journalctl -u hearth-sovereignty --since "1 min ago"
# Expect: "Kill state change: MIC=True ..."
# Expect: "MIC KILL active — muting all PipeWire capture sources."

# Verify sovereignty lock (if GPU kill was flipped):
cat /run/iskander/sovereignty.lock
```

### 4.2 Power monitoring test

```bash
# Smoke test INA3221 directly
python3 /opt/iskander/firmware/solidarity_hat/ina3221_poller.py
# Expect voltage/current readings on all 3 channels
```

### 4.3 ATECC608B sign test

```bash
# Verify chip responds and keys are provisioned
python3 /opt/iskander/firmware/solidarity_hat/atecc_provision.py --verify
# Expect: public keys printed for slots 0 and 1
```

---

## 5. Acceptance Criteria Checklist

- [ ] `i2cdetect` shows INA3221 at 0x40
- [ ] `i2cdetect` shows ATECC608B at 0x60
- [ ] All 3 kill switches: open circuit when OFF, confirmed with multimeter
- [ ] `hearth-sovereignty.service` status: active (running)
- [ ] `hearth-permacomputing.service` status: active (running)
- [ ] ATECC608B provisioning record exists at `/etc/iskander/atecc_provisioning.json`
- [ ] Flipping GPU kill switch: Ollama receives SIGSTOP (verify with `ps aux | grep ollama`)
- [ ] Restoring GPU kill: Ollama receives SIGCONT
- [ ] INA3221 CLI smoke test returns plausible voltage readings
- [ ] No sovereignty lock file at `/run/iskander/sovereignty.lock` during normal operation

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `i2cdetect` shows nothing | I2C pull-ups missing or wrong bus | Check R_PULL_SDA/SCL (4.7kΩ), verify bus number |
| Sovereignty lock written on boot | GPIO or INA3221 init failed | Check wiring, run `i2cdetect`, check `journalctl` |
| Kill state not changing in daemon | GPIO pin numbers wrong | Set `HEARTH_GPIO_*` env vars to match your adapter |
| ATECC608B provision fails | Data zone already locked | Use `--verify` to check existing keys, or replace chip |
| Daemon restarted 3 times then stopped | Persistent hardware failure | Manual intervention required; sovereignty lock is active |
