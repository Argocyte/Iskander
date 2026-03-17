# Flashing Iskander OS and Activating the Commons Node

**OS installation, Ad-Hoc setup flow, UPS integration, and power sensor wiring
for the Tier 2 Commons Node.**

This guide picks up where [`building_the_commons_node.md`](./building_the_commons_node.md) ends.
Your node is physically assembled, closed, and connected to Ethernet and UPS.

---

## Table of Contents

1. [What Happens on First Boot](#1-what-happens-on-first-boot)
2. [Create the Iskander OS USB Installer](#2-create-the-iskander-os-usb-installer)
3. [BIOS Setup Before Installing](#3-bios-setup-before-installing)
4. [Boot the Installer](#4-boot-the-installer)
5. [The Ad-Hoc Setup Flow](#5-the-ad-hoc-setup-flow)
6. [Wiring the INA3221 Power Sensor](#6-wiring-the-ina3221-power-sensor)
7. [Connecting the UPS (NUT Integration)](#7-connecting-the-ups-nut-integration)
8. [How the Graceful Degradation Daemon Works](#8-how-the-graceful-degradation-daemon-works)
9. [Verifying Everything Is Running](#9-verifying-everything-is-running)
10. [Next Steps](#10-next-steps)

---

## 1. What Happens on First Boot

Here is the full picture of what Iskander OS does the first time it starts,
so you know what to expect at each step.

```
Power on
    │
    ▼
BIOS POST (5–10 seconds)
    │
    ▼
Iskander OS loads from USB/NVMe
    │
    ▼
Hardware detection (GPU, TPM, Wi-Fi, UPS, Sensors)
    │
    ├─► TPM 2.0 detected → seals key vault
    ├─► Intel AX210 detected → starts hostapd
    │       ↳ Broadcasts: SSID "Iskander_Hearth_Setup"
    ├─► INA3221 detected (if wired) → starts power telemetry daemon
    └─► UPS detected via USB/NUT → starts upsmon
    │
    ▼
Setup wizard becomes available (≈ 5 minutes after power-on)
    │
    ├─► Via monitor:  QR code displayed → scan with phone
    └─► Via Wi-Fi:    Connect to "Iskander_Hearth_Setup" → open browser
    │
    ▼
Cooperative onboarding wizard runs in browser
    │
    ▼
Node is live
```

---

## 2. Create the Iskander OS USB Installer

You need a **second computer** for this step. Any OS works.

**Requirements:**
- USB drive, minimum 32GB (T2-004 in BOM — or use any spare drive)
- Iskander OS disk image (`.img` or `.iso` file)

**Step 1 — Download the Iskander OS image**

Download the latest stable Iskander OS image from the official source.
Verify the SHA-256 checksum of the downloaded file before writing it.

```bash
# On Linux / macOS:
sha256sum iskander-os-latest.img
# Compare output against the published checksum on the Iskander OS releases page.

# On Windows (PowerShell):
Get-FileHash .\iskander-os-latest.img -Algorithm SHA256
```

Do not proceed if the checksum does not match. A corrupted or tampered image
will produce a broken install that is difficult to diagnose.

**Step 2 — Write the image to the USB drive**

Use **Balena Etcher** (free, all platforms): https://etcher.balena.io

Or via command line:

```bash
# Linux / macOS — replace /dev/sdX with your USB drive (find with: lsblk)
# WARNING: this overwrites everything on the target drive.
sudo dd if=iskander-os-latest.img of=/dev/sdX bs=4M status=progress conv=fsync

# Verify the write completed without errors. The command will exit cleanly if successful.
sync
```

```powershell
# Windows — use Rufus (https://rufus.ie) instead of dd.
# Select your USB drive, select the .img file, click START.
```

**Step 3 — Label the USB drive**

Write "Iskander OS Installer — [date]" on the drive with a permanent marker.
This drive is also the physical key for recovering the node if the NVMe fails.
Store it with the node's other documentation.

---

## 3. BIOS Setup Before Installing

Before booting the installer, configure the BIOS for correct boot order and security settings.

1. Plug the USB installer into a USB 3.0 port on the node (blue ports).
2. Power on the node and immediately press `Delete` (or `F2`) to enter BIOS.
3. Make the following changes:

**Boot Configuration:**

| Setting | Path | Value |
|---|---|---|
| Boot Option #1 | Boot → Boot Option Priorities | USB Drive |
| Boot Option #2 | Boot → Boot Option Priorities | NVMe SSD |
| Secure Boot | Security → Secure Boot | Disabled (during install; re-enable after if Iskander OS supports it) |
| Fast Boot | Boot → Fast Boot | Disabled (prevents USB detection) |

**Security:**

| Setting | Path | Value |
|---|---|---|
| TPM Device | Security → Intel PTT / AMD fTPM | Enabled (if using integrated TPM) |
| TPM Module | Security → TPM Header | Enabled (for discrete module T2-009) |
| Supervisor Password | Security | Set a strong password. Write it in the cooperative's shared credentials manager. |

**Power / Recovery:**

| Setting | Path | Value |
|---|---|---|
| Restore on AC Power Loss | Power → AC Recovery | Power On |
| Wake on LAN | Advanced → Wake on LAN | Enabled |

`Restore on AC Power Loss → Power On` is critical: if the UPS runs out of battery and
mains power returns, the node must restart itself without anyone pressing the power button.

4. Apply all power efficiency settings from `supply_chain/procurement_guidelines.md`, Section 4.
5. Press `F10` to save and exit. The node will reboot from the USB installer.

---

## 4. Boot the Installer

1. The node boots from the USB drive. You will see the Iskander OS boot menu.
2. Select **Install Iskander OS** (or equivalent option in the menu).
3. When prompted for the installation target, select the **1TB NVMe SSD** (T2-005).
   Do not select the USB drive or the SATA SSD (T2-006 — this is for data, not OS).
4. When prompted for the data drive, select the **2TB SATA SSD** (T2-006).
5. Follow the installer prompts. The installer will ask for:
   - **Cooperative name** (used as the node hostname, e.g. `sunrise-coop`)
   - **Admin passphrase** (minimum 16 characters; store in the cooperative's credentials manager)
   - **TPM sealing** — select "Seal vault to this hardware TPM". This binds key material to T2-009.
   - **Network**: select "Wired Ethernet (eth0)" for the primary connection.
     The Wi-Fi hotspot for setup is enabled automatically — do not configure it here.
6. Installation takes approximately 15–25 minutes depending on NVMe speed.
7. When the installer completes, it will prompt you to remove the USB drive and reboot.
8. Remove the USB drive and press Enter.

---

## 5. The Ad-Hoc Setup Flow

This is the Dappnode-inspired first-run experience. No monitor or keyboard is required
after this point. Any cooperative member with a phone or laptop can complete setup.

### What Is Happening

On first boot after installation, Iskander OS:
1. Brings up the Ethernet interface and attempts to get a DHCP address from your router.
2. Starts `hostapd` — the Wi-Fi Access Point daemon — on the Intel AX210 (T2-008).
3. Broadcasts the **`Iskander_Hearth_Setup`** SSID.
4. Starts the cooperative onboarding web server on port 80/443.
5. Displays a setup QR code on the HDMI output (if a monitor is connected).

This process takes approximately **4–6 minutes** from power button to setup-ready.
Do not panic if nothing appears to happen for the first few minutes. The OS is detecting
hardware, starting TPM services, and generating initial cryptographic keys.

### Connecting via Wi-Fi Hotspot (Recommended — no monitor needed)

1. Wait 5 minutes after pressing the power button.
2. On any phone, tablet, or laptop: scan for Wi-Fi networks.
3. Connect to **`Iskander_Hearth_Setup`**.
   - Password: printed on the physical setup card included in the chassis accessories,
     or shown on the monitor if one is connected.
   - Default (change immediately): `hearth-setup-[last4-of-mac]`
     (The last 4 characters of the AX210's MAC address are printed on the card in the box.)
4. Your device connects to the node's local network (192.168.42.x).
5. Open any browser. You will be automatically redirected to the setup wizard
   at `http://setup.iskander.local` (or `http://192.168.42.1`).
6. The wizard will walk you through:
   - Setting the cooperative name, display name, and contact information
   - Inviting the first cooperative members (by handle)
   - Configuring the Ethereum / Web3 Safe multi-sig wallet address
   - Setting the node's static IP address on your local network (recommended)
   - Confirming TPM key sealing is active
   - Setting the Wi-Fi network the node will permanently join (if desired)
7. When setup is complete, the `Iskander_Hearth_Setup` hotspot **turns off automatically**.
   The node is now reachable at its assigned local IP address.

### Connecting via Monitor / QR Code

If a monitor is connected:
1. On first boot, the HDMI output shows a QR code and the local IP address.
2. Scan the QR code with any phone camera — it opens the setup wizard URL directly.
3. Complete the wizard on your phone while viewing the monitor for status.

### If the Hotspot Does Not Appear

If `Iskander_Hearth_Setup` is not visible after 10 minutes:

```bash
# SSH into the node using its wired IP (check your router's DHCP table):
ssh admin@[node-ip]

# Check hostapd status:
sudo systemctl status hostapd

# Check if AX210 is detected:
iw list | grep "Wiphy"

# Restart the hotspot manually:
sudo systemctl restart hostapd

# Check for errors:
sudo journalctl -u hostapd -n 50
```

Common causes:
- AX210 not fully seated in M.2 slot (go back and reseat it — see Step 7 in build guide)
- Antenna pigtails not connected to AX210 (weak signal, card may not broadcast)
- Regulatory domain issue: `sudo iw reg set [YOUR-COUNTRY-CODE]`

---

## 6. Wiring the INA3221 Power Sensor

**Components:** T2-015 (INA3221 triple-channel power monitor)

The INA3221 is a small breakout board (roughly the size of a postage stamp) that measures
voltage and current on up to three channels simultaneously. Iskander OS reads it via I2C
and uses the data to trigger Graceful Degradation.

**What it measures for the Commons Node:**

| Channel | What Is Connected | What the OS Learns |
|---|---|---|
| Channel 1 | UPS mains input (from wall to UPS) | Whether mains power is present |
| Channel 2 | UPS output (UPS to node PSU) | Whether the node is running on battery |
| Channel 3 | Node total load (clamp on PSU cable) | Real-time wattage draw |

### INA3221 Pinout (Adafruit breakout — T2-015)

```
INA3221 Board Pin    →   Connect To
─────────────────────────────────────────────────────────
VCC (3.3V or 5V)     →   Motherboard 3.3V or 5V header pin
GND                  →   Motherboard GND header pin
SCL                  →   I2C clock (SCL) on motherboard header
SDA                  →   I2C data  (SDA) on motherboard header
A0, A1 (address)     →   Leave floating for default I2C address 0x40
```

### Does Your Motherboard Have an I2C Header?

**Check your board manual for any of these labels:**
- `I2C_HEADER` or `I2C_TPM` (not the TPM header itself, but near it)
- `SMBus` header
- `JDASH1` (on Supermicro / server boards)
- GPIO pin header with SCL/SDA pins listed

**If your Mini-ITX board has no I2C header** (most ASRock consumer boards do not expose
a GPIO/I2C header), use the **USB-I2C bridge** (T2 BOM item T1-007 — CP2112 breakout):

```
INA3221 VCC   →   CP2112 VCC (3.3V)
INA3221 GND   →   CP2112 GND
INA3221 SCL   →   CP2112 SCL
INA3221 SDA   →   CP2112 SDA
CP2112 USB    →   Any internal USB 2.0 header on motherboard
               (or external USB port — less clean, but functional)
```

The CP2112 presents as a USB HID device. Linux kernel 4.15+ includes the `hid_cp2112`
driver natively — no additional drivers needed.

### Current Sensing: Connecting the Shunt

The INA3221 measures current via a **shunt resistor** on the VIN+/VIN– pins of each channel.
For non-invasive measurement on standard power cables, use a **shunt inline adapter** or
**current sensing clip** rated for the expected current.

For cooperative nodes, a practical and safe approach:

```
Wall outlet
    │
    ▼  (1)
[INA3221 Channel 1 inline — measure mains voltage presence only]
    │
    ▼
[UPS unit]
    │
    ▼  (2)
[INA3221 Channel 2 inline — measure UPS output voltage + current]
    │
    ▼
[Node PSU IEC C14 inlet]
    │
    ▼  (3)
[INA3221 Channel 3 — PSU 12V rail shunt, OR inductive clamp on main cable]
    │
    ▼
[Node internals]
```

> ⚠️ **Safety note:** Do not open mains (230V/120V) cables. Measure only on the DC
> side of the PSU brick (for Tier 1 Mini PCs) or via an inline DC power monitor.
> For the Tier 2/3 ATX PSU, measure the low-voltage output rails only, not mains input.
> If unsure, use a smart PDU or smart UPS with USB monitoring instead — these provide
> equivalent data without any wiring.

### Alternative: Smart UPS Monitoring Only (Simpler)

If wiring the INA3221 feels too complex for your first deployment, the UPS USB/HID
connection alone (NUT daemon — see Section 7) provides sufficient data for basic
Graceful Degradation:

- **Battery percentage** → triggers graceful shutdown below threshold
- **Estimated runtime** → displayed to members in the Iskander OS dashboard
- **Load percentage** → approximate wattage draw (less precise than INA3221)

You can add the INA3221 later without any OS reinstallation.

### Detecting the INA3221 on Linux

Once the INA3221 is wired and the node is booted:

```bash
# Detect all I2C buses on the system
sudo i2cdetect -l

# Scan bus 0 (replace 0 with your bus number from the above output)
sudo i2cdetect -y 0

# You should see address 0x40 (default for INA3221 with A0/A1 floating):
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --

# Load the INA3221 kernel driver
sudo modprobe ina3221

# Check dmesg for device detection
dmesg | grep -i ina3221

# Read channel data (once Iskander OS sensor daemon is running)
cat /sys/bus/i2c/devices/*/iio\:device*/in_voltage0_input   # Channel 1 voltage (mV)
cat /sys/bus/i2c/devices/*/iio\:device*/in_current0_input   # Channel 1 current (mA)
```

If `0x40` does not appear in `i2cdetect`, recheck wiring (SCL/SDA not swapped, VCC connected).

---

## 7. Connecting the UPS (NUT Integration)

**Components:** T2-014 (850VA UPS with USB HID port)

NUT (Network UPS Tools) is the Linux daemon that monitors UPS status and triggers
clean shutdowns when battery runs low. Iskander OS includes NUT pre-configured.

### Physical Connection

1. Connect the UPS USB monitoring cable (usually USB-A to USB-B or USB-A to USB-A)
   from the UPS to any USB port on the node.
2. Ensure the node's power cable is plugged into the **battery-backed output** of the UPS
   (not the "surge only" outlets found on some models).

### Verifying NUT Detection

```bash
# Scan for UPS devices on the system
sudo nut-scanner -U

# Expected output (example for CyberPower CP850PFCLCD):
# [nutdev1]
#     driver = "usbhid-ups"
#     port = "auto"
#     vendorid = "0764"
#     productid = "0501"
#     ...

# Check NUT service status
sudo systemctl status nut-server nut-monitor

# Query live UPS data
upsc [ups-name]@localhost

# Key values to check:
#   battery.charge          (current charge %)
#   battery.runtime         (estimated runtime in seconds)
#   input.voltage           (mains voltage — drops to 0 if mains fails)
#   ups.load                (load % — divide by 100, multiply by UPS VA for wattage)
#   ups.status              (OL = on line, OB = on battery, LB = low battery)
```

### NUT Configuration in Iskander OS

Iskander OS ships with NUT pre-configured to:
- Trigger `SHUTDOWNCMD` when `battery.charge` drops below **15%**
- Notify all logged-in cooperative members when status changes to `OB` (on battery)
- Log all UPS events to the cooperative ledger on the ZFS data SSD

To adjust the shutdown threshold:

```bash
# Edit /etc/nut/upsmon.conf
sudo nano /etc/nut/upsmon.conf

# Find and change:
# MINSUPPLIES 1
# SHUTDOWNCMD "/sbin/shutdown -h +0"
# POWERDOWNFLAG /etc/killpower
# NOTIFYFLAG ONBATT SYSLOG+WALL+EXEC
# NOTIFYCMD /usr/sbin/iskander-graceful-degrade

# Adjust DEADTIME and RBWARNTIME for your UPS's typical recovery behaviour.
sudo systemctl restart nut-monitor
```

---

## 8. How the Graceful Degradation Daemon Works

Iskander OS includes the **`iskander-graceful-degrade`** daemon, a service that
bridges physical power telemetry to software behaviour across the node.

### The Signal Chain

```
INA3221 sensor     →  Kernel IIO driver  →  /sys/bus/i2c/...
UPS NUT daemon     →  upsmon             →  /var/run/nut/
                                                │
                                                ▼
                              iskander-graceful-degrade daemon
                              (reads both sources, applies policy)
                                                │
                              ┌─────────────────┼─────────────────┐
                              ▼                 ▼                  ▼
                        GPU power limit    AI inference       Member alerts
                        (nvidia-smi -pl)   queue paused       sent via OS
                              ▼                 ▼
                        CPU tuned profile   Background jobs
                        → powersave         → suspended
```

### Degradation Levels

The daemon implements three power states:

| Level | Trigger | Actions |
|---|---|---|
| **NORMAL** | Mains power present, battery ≥ 80% | All services run at full capacity. GPU at configured power limit. |
| **REDUCED** | On battery (UPS), OR INA3221 reports voltage drop, battery 40–80% | GPU power limit reduced by 30%. AI inference queue limited to 2 concurrent requests. Non-critical background sync suspended. Members notified. |
| **CRITICAL** | Battery < 20%, OR estimated runtime < 5 minutes | GPU suspended. AI inference paused. ZFS sync checkpoint committed. Members notified with estimated shutdown time. |
| **SHUTDOWN** | Battery < 15% (NUT threshold) | Clean shutdown initiated. ZFS pool exported. TPM key sealed. System powers off. |

### Configuring Degradation Policy

```bash
# View current degradation configuration
cat /etc/iskander/graceful-degrade.conf

# Key parameters:
#
# [thresholds]
# battery_reduced = 80          # % — enter REDUCED mode below this
# battery_critical = 20         # % — enter CRITICAL mode below this
# battery_shutdown = 15         # % — trigger NUT shutdown below this
# runtime_critical_seconds = 300 # 5 min — enter CRITICAL if runtime < this
#
# [gpu]
# reduced_power_limit_pct = 70  # % of configured GPU power limit in REDUCED mode
# critical_gpu_enabled = false  # Disable GPU entirely in CRITICAL mode
#
# [inference]
# reduced_concurrent_requests = 2
# critical_inference_enabled = false
#
# [notifications]
# member_alert_onbattery = true
# member_alert_reduced = true
# member_alert_critical = true
# alert_channel = "cooperative-alerts"  # Iskander OS notification channel name

# Reload daemon after config changes (no restart needed)
sudo systemctl reload iskander-graceful-degrade
```

### Simulating a Power Failure (Testing)

Before deploying the node in production, simulate a power failure to verify
the full signal chain works:

```bash
# Step 1: Verify all services are running
sudo systemctl status nut-monitor iskander-graceful-degrade

# Step 2: Simulate "on battery" condition in NUT (safe — does not actually cut power)
sudo upsmon -c fsd   # Forces Forced Shutdown — triggers full shutdown sequence

# Watch the logs in real time:
sudo journalctl -f -u iskander-graceful-degrade -u nut-monitor

# Expected log sequence:
# [INFO] UPS status: OL (on line)
# [INFO] UPS status: FSD (forced shutdown)
# [INFO] Entering CRITICAL mode
# [INFO] Committing ZFS checkpoint...
# [INFO] Suspending GPU inference queue...
# [INFO] Member alert sent: node shutting down
# [INFO] Initiating clean shutdown
```

If the node does not shut down cleanly, check:
- `SHUTDOWNCMD` path in `/etc/nut/upsmon.conf`
- `iskander-graceful-degrade` service is enabled and running
- ZFS pool is mounted at expected path

---

## 9. Verifying Everything Is Running

After setup is complete and the node is on the cooperative network, run this checklist:

```bash
# System health overview (Iskander OS built-in)
iskander status

# Individual checks:
systemctl status \
    hostapd \              # Wi-Fi (should show "inactive" after setup completes)
    nut-monitor \          # UPS monitoring
    nut-server \           # UPS data server
    iskander-graceful-degrade \
    ollama \               # Local AI inference (if configured)
    ipfs \                 # IPFS node
    iskander-sync          # Cooperative data sync

# TPM key vault status
iskander vault status
# Expected: "Vault sealed to hardware TPM. Key material: PRESENT."

# GPU inference check
ollama list               # Lists available local AI models
ollama run phi3:mini      # Test a lightweight model — should run entirely on GPU

# GPU VRAM verification
nvidia-smi                # Check VRAM used/total

# ZFS pool health
sudo zpool status         # Check all pools show ONLINE, no errors
sudo zpool list           # Verify data SSD pool is mounted

# Power sensor check (if INA3221 wired)
cat /sys/bus/i2c/devices/*/iio\:device*/in_voltage0_input
# Expected: mains voltage present (e.g. 12000 = 12V on DC side)

# NUT battery check
upsc iskander-ups@localhost | grep battery
# Expected: battery.charge: 100 (or current %), ups.status: OL
```

---

## 10. Next Steps

Your Commons Node is running. Here is what to do next:

### Immediate

- [ ] Change the BIOS supervisor password from the default (if not done in Step 3)
- [ ] Store the admin passphrase in the cooperative's shared credentials manager
- [ ] Store the USB installer drive in a safe, labelled location
- [ ] Complete the Material Passport for all components (`supply_chain/material_passport_template.csv`)
- [ ] Affix the QR code repair tiles inside the chassis (if not done during build)

### First Week

- [ ] Invite all cooperative members through the Iskander OS onboarding wizard
- [ ] Configure the Web3 Safe multi-sig address and assign key holders
- [ ] Test the graceful degradation sequence: `sudo upsmon -c fsd`
- [ ] Set node to automatically run `zpool scrub` weekly:
  ```bash
  echo "0 2 * * 0 root /sbin/zpool scrub data" | sudo tee /etc/cron.d/zpool-scrub
  ```
- [ ] Install the cooperative's primary AI models via Ollama:
  ```bash
  ollama pull mistral:7b    # 7B model — fits in 12GB VRAM
  ollama pull llama3:8b     # Meta LLaMA 3 8B
  ```

### First Month

- [ ] Connect to another cooperative's Federation Node (see Tier 3 BOM)
- [ ] Configure IPFS to pin the cooperative's shared content
- [ ] Run a physical repair drill: open the chassis, identify each QR code,
      scan it, and verify the link works. This familiarises all members with
      the repair process before a real failure happens.
- [ ] Review power draw logs from the INA3221 and tune GPU power limit
      (`supply_chain/procurement_guidelines.md`, Section 4) for your workload

---

> The Iskander Hearth is now a functioning piece of cooperative infrastructure.
> It does not belong to any corporation. It does not report to any cloud.
> It belongs to the people in the room with it.
