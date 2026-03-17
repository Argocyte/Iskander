# Procurement Guidelines

**Ethical sourcing, ITAD verification, conflict mineral acknowledgement,
and BIOS power efficiency configuration for Iskander Hearth nodes.**

---

## Table of Contents

1. [Sourcing Refurbished Enterprise Gear via ITAD](#1-sourcing-refurbished-enterprise-gear-via-itad)
2. [Grading Standards and What to Verify](#2-grading-standards-and-what-to-verify)
3. [Conflict Minerals: Acknowledgement and Action](#3-conflict-minerals-acknowledgement-and-action)
4. [BIOS Configuration for Maximum Power Efficiency](#4-bios-configuration-for-maximum-power-efficiency)
5. [Completing the Material Passport](#5-completing-the-material-passport)
6. [End-of-Life and Circular Economy](#6-end-of-life-and-circular-economy)

---

## 1. Sourcing Refurbished Enterprise Gear via ITAD

**ITAD** (IT Asset Disposition) is the industry that handles decommissioned enterprise
hardware. When a bank, hospital, university, or cloud provider upgrades its fleet,
thousands of machines enter the ITAD market. This is the cooperative's primary sourcing
channel for Tier 1 and Tier 2 builds.

### Why Enterprise Refurb Is Better Than Consumer Secondhand

| Factor | Enterprise ITAD | Consumer Secondhand |
|---|---|---|
| Usage hours | Typically 3–5 years / 8h day | Unknown — could be 24/7 |
| Data erasure | NIST 800-88 certified wipe | Usually none |
| Testing | Burn-in + diagnostic reports | Usually none |
| Warranty | 90-day minimum from ITAD seller | None |
| Provenance | Traceable to corporate fleet | Unknown |

### Vetted ITAD Suppliers

These suppliers are known to provide graded, tested hardware with documentation.
This is not an endorsement — do your own due diligence. Prices vary significantly.

| Supplier | Region | Speciality | Notes |
|---|---|---|---|
| **ServerMonkey** | US | Servers, workstations, NICs | Good for Tier 3 EPYC/Xeon gear |
| **IT Creations** | US | Mini PCs, workstations, laptops | Good for Tier 1 EliteDesk/ThinkCentre |
| **Newegg Refurbished** | US/CA | Consumer + enterprise mix | Inspect grades carefully |
| **BackMarket Business** | EU/US | Phones, laptops, PCs | Grade A consumer hardware. Good for Tier 1 |
| **Bargain Hardware** | UK/EU | Servers, server CPUs, ECC RAM | Excellent for Tier 3 EPYC + RDIMM |
| **Techbuyer** | UK/EU/AU | Full servers, drives, GPUs | Sustainability reports available on request |
| **RefurbUPS** (or local e-waste brokers) | Regional | UPS units | Verify NUT compatibility list before purchase |

### Questions to Ask Any ITAD Seller

Before purchasing, ask (or look for in the listing):

1. **What grade is this?** (See Section 2 for grade definitions.)
2. **What diagnostic tests were run?** Ask for the test report if Grade A is claimed.
3. **How was data erasure performed?** Acceptable: NIST 800-88 DoD wipe certificate,
   Blancco certificate, or physical destruction log. Unacceptable: "formatted" with no certificate.
4. **What is the warranty period and what does it cover?** Minimum: 90 days, parts failure.
5. **Are firmware/BIOS updates available from the OEM for this model?**
   (Critical for security — some older enterprise gear is no longer receiving BIOS updates.)
6. **What is the return policy if S.M.A.R.T. or POST reveals a fault?**

### Finding Local ITAD and E-Waste Brokers

Global ITAD directories:
- **R2 Certified Recyclers**: https://sustainableelectronics.org/r2-certified-facilities/
- **e-Stewards Certified**: https://e-stewards.org/find-a-recycler/
- **WEEE Compliance (EU)**: Check your national WEEE producer compliance scheme register

Many cities have local e-waste brokers who sell directly to individuals and small organisations.
Search: `"ITAD" + [your city]` or `"e-waste reseller" + [your city]`.
Local sourcing reduces shipping carbon and supports regional circular economies.

---

## 2. Grading Standards and What to Verify

ITAD grading is not standardised industry-wide. This is the Iskander Hearth interpretation
of common grade labels. Always ask the seller to define their own grades.

| Grade | Iskander Hearth Interpretation | Acceptable For |
|---|---|---|
| **Grade A / Certified Refurbished** | Cosmetically near-new. Full diagnostic pass. OEM firmware updated. | All tiers. Preferred for Tier 3. |
| **Grade B** | Minor cosmetic damage (scratches, scuffs). Full diagnostic pass. | Tier 1 and Tier 2 where appearance is irrelevant (server room). |
| **Grade C** | Visible damage or missing non-essential parts (bezels, feet). Functional. | Tier 1 only, with careful inspection. Not Tier 3. |
| **For Parts / AS-IS** | Not tested. Unknown functionality. | Not recommended for production nodes. Acceptable for spare parts harvesting. |

### Pre-Deployment Verification Checklist

Run these checks on every refurbished component before building a production node:

#### CPU
- [ ] Boot into BIOS and verify CPU model, core count, and base/boost clock
- [ ] Run `stress-ng --cpu 0 --cpu-method all -t 30m` — no crashes or thermal throttle
- [ ] Check `journalctl -k | grep -i mce` for Machine Check Errors after stress test

#### RAM (ECC at Tier 3)
- [ ] Run `memtest86+` for a full pass (minimum 1 pass, 2 recommended)
- [ ] For ECC RAM: `edac-util -s` after OS boot — zero corrected errors expected
- [ ] Check `dmidecode --type 17` to confirm ECC type and speed

#### NVMe / SATA SSD
- [ ] Run `smartctl -a /dev/nvme0` — check `Percentage Used`, `Available Spare`, `Media Errors`
- [ ] Percentage Used > 70%: do not use for production; acceptable for test/dev
- [ ] Run `fio --name=rand-rw --ioengine=libaio --iodepth=32 --rw=randrw --bs=4k --size=1G` for 10 minutes
- [ ] Verify write speed is within 20% of manufacturer spec

#### GPU (especially refurbished)
- [ ] Run `gpu-burn` (CUDA) or `clpeak` (OpenCL/ROCm) for 10 minutes
- [ ] After burn, run `nvidia-smi -q | grep -i error` — zero errors expected
- [ ] Check fan bearing: listen for grinding or whine. Replace fans rather than the whole card.
- [ ] Check VRAM: `cuda-memtest` or `ocl-memtest` for one full pass
- [ ] Note GPU-Z VBIOS version — record in Material Passport

#### UPS
- [ ] Confirm NUT compatibility: https://networkupstools.org/stable-hcl.html
- [ ] Connect via USB, run `nut-scanner` to detect device
- [ ] Perform a load test: `upsmon -c fsd` forces a simulated power failure — verify OS graceful shutdown triggers

---

## 3. Conflict Minerals: Acknowledgement and Action

### What Are Conflict Minerals?

Modern electronics — including every GPU, CPU, motherboard, and SSD in our BOMs —
contain **3TG minerals**: tantalum, tin, tungsten, and gold.

These minerals are mined in regions where armed groups use mining revenues to fund
ongoing conflicts. The Democratic Republic of Congo (DRC) and adjoining countries are
the primary concern. This is not a niche issue: the DRC produces ~70% of the world's cobalt
(used in batteries) and significant portions of global tantalum (used in capacitors).

**Buying a GPU does not make you complicit in conflict. Ignoring it does.**

Iskander Hearth's position: acknowledge honestly, improve incrementally, track progress.

### The Responsible Minerals Initiative (RMI)

The RMI (https://www.responsibleminerals.org) operates:

- **RMAP**: Responsible Minerals Assurance Process — audits smelters/refiners
- **CMRT**: Conflict Minerals Reporting Template — standardised disclosure form
- **Smelter/Refiner lookup**: Check if your hardware manufacturer's suppliers are certified

**Check your manufacturer's status:**

| Manufacturer | Conflict Minerals Report Location |
|---|---|
| AMD | amd.com → Corporate Responsibility → Supply Chain |
| NVIDIA | nvidia.com → CSR → Conflict Minerals |
| Intel | intel.com → Corporate Responsibility → Supply Chain |
| Supermicro | supermicro.com → About → Corporate Responsibility |

### What a Small Cooperative Can Realistically Do

**Tier 1 (Minimum — do this now):**

1. Log `conflict_minerals_status` honestly in the Material Passport:
   - `UNVERIFIED` = no research done
   - `PARTIAL` = manufacturer has a public policy but no per-SKU smelter list
   - `CERTIFIED` = manufacturer's RMAP-certified smelter list covers this product

2. Prefer manufacturers with active RMI membership (AMD, Intel, NVIDIA are all members).

3. When buying refurbished, acknowledge that you cannot verify the original supply chain —
   but that buying refurbished already extends the use life of existing mineral extraction,
   reducing new mining demand.

**Tier 2 (Within 12 months):**

1. Download the CMRT from your GPU and CPU manufacturer's websites.
2. Check whether the smelters listed are on the RMI Conformant Smelter list.
3. Record findings in the Material Passport `conflict_minerals_notes` field.

**Tier 3 (Ongoing):**

1. When next replacing a component, actively prefer vendors who can produce
   a current CMRT and whose smelters are RMAP conformant.
2. Consider a small annual contribution to:
   - **RESOLVE** (https://www.resolve.ngo) — conflict minerals advocacy
   - **Pact** (https://www.pactworld.org) — on-the-ground mining community support
3. Publish your cooperative's conflict minerals position in your governance documents.

### A Note on "Conflict-Free" Claims

No supply chain for modern consumer electronics can currently be certified
**fully** conflict-free at the per-atom level. Smelter-level certification (RMAP)
is the best available industry standard, and it is imperfect.

Be honest about this in member communications. The goal is not moral purity —
it is honest acknowledgement and continuous improvement.

---

## 4. BIOS Configuration for Maximum Power Efficiency

Configuring the BIOS correctly before first boot can reduce idle power draw by 15–40%
and dramatically improve Iskander OS's Graceful Degradation telemetry accuracy.

### General Principles

- **Disable anything you don't use**: onboard audio, serial ports, unused SATA controllers,
  RGB controllers, and unused USB controllers all draw small amounts of power continuously.
- **Enable C-states**: These allow CPU cores to drop to ultra-low power sleep states
  between tasks. Disable only if running a real-time workload (rare for cooperative nodes).
- **Set power limits explicitly**: Default "Auto" BIOS power limits are often higher than needed,
  causing unnecessary heat and power consumption during sustained workloads.

### AMD Ryzen (Tier 2 — B650M-ITX/ax)

Access BIOS: `Delete` key on POST screen.

| Setting | Path | Recommended Value | Why |
|---|---|---|---|
| **ECO Mode** | AMD Overclocking → ECO Mode | Enable (65W or 45W) | Reduces peak TDP, cuts idle draw. 45W ECO mode on Ryzen 5 7600 still delivers full performance for most cooperative AI workloads. |
| **Global C-State Control** | CPU Configuration → | Enabled | Allows all C-states (C6 sleep). Required for idle power reduction. |
| **S0i3 / Modern Standby** | Power → | Enable | Deeper idle state. Compatible with Iskander OS power management. |
| **CPPC** (Collaborative Processor Performance Control) | AMD CBS → | Enabled | Lets OS request performance levels. Required for `cpupower` integration. |
| **FCLK Frequency** | AMD Overclocking → | 1800 MHz (auto) | Leave at auto unless you have matched DDR5-3600. |
| **RGB / LED control** | Peripherals → | Disabled | No illumination needed on a server. Saves ~1–2W. |
| **Onboard Audio** | Advanced → Onboard Devices | Disabled | Server nodes do not need audio. Saves ~1W. |
| **USB Power in S4/S5** | Advanced → USB | Disabled | Prevents USB ports drawing power during shutdown/sleep. |
| **ErP Ready** | Power → | Enable | S5 draws <1W. Required for EU ErP directive compliance. |
| **Fan control** | H/W Monitor → Fan Tuning | Run Fan Tuning wizard | Sets fan curves based on actual thermal headroom. Reduces noise and power. |

**BIOS Power Limit (PPT) tuning via OS after boot:**

```bash
# Install ryzenadj (AMD CPU power management CLI)
# https://github.com/FlyGoat/RyzenAdj

# Check current power limits
sudo ryzenadj --info

# Set Package Power Tracking limit to 45W (suitable for Ryzen 5 7600 in cooperative workloads)
sudo ryzenadj --power-saving

# Or set explicitly:
sudo ryzenadj --stapm-limit=45000 --fast-limit=45000 --slow-limit=45000
```

### Intel N100 (Tier 1 — Mini PC BIOS)

Mini PC BIOSes vary by manufacturer. Common settings across Beelink/Minisforum:

| Setting | Recommended Value | Notes |
|---|---|---|
| **Intel SpeedStep (EIST)** | Enabled | P-state scaling. Never disable. |
| **C1E Enhanced Halt** | Enabled | CPU halts between tasks. Saves ~2–5W idle. |
| **C3/C6/C7 States** | Enabled | Deep sleep states. Essential for N100 low power. |
| **Turbo Boost** | Enabled | N100 boost is conservative (3.4GHz). Safe to leave on. |
| **PL1 / PL2 Power Limits** | PL1: 10W, PL2: 15W | N100 default is often 6W PL1. Increase slightly for sustained loads without throttle. |
| **Primary Display** | Auto or iGPU | If no discrete GPU at Tier 1, iGPU preferred. |
| **Serial Port / Parallel Port** | Disabled | Not used. Small power saving. |
| **Wake on LAN** | Enabled | Allows Iskander OS to remotely wake the node. Useful for scheduled tasks. |
| **Auto Power On** | Enabled | Node should restart automatically after a power cut. |

### NVIDIA GPU Power Limit (Tier 2 & 3 — Post-OS)

After Iskander OS is installed, set a persistent power limit on the GPU.
RTX 3060 12GB default TGP is 170W. For cooperative AI inference (not gaming),
140W provides identical throughput with ~18% less power draw.

```bash
# Enable persistence mode (survives reboots via systemd service)
sudo nvidia-smi -pm 1

# Query current power limit and min/max range
nvidia-smi -q | grep -i "power limit"

# Set power limit (example: 140W for RTX 3060)
sudo nvidia-smi -pl 140

# Create systemd service to persist across reboots
sudo tee /etc/systemd/system/nvidia-power-limit.service > /dev/null <<EOF
[Unit]
Description=NVIDIA GPU Power Limit
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/nvidia-smi -pm 1
ExecStart=/usr/bin/nvidia-smi -pl 140
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable nvidia-power-limit.service
```

### AMD GPU Power Limit (ROCm — Alternative GPU)

```bash
# List GPU power profiles
cat /sys/class/drm/card0/device/power_dpm_force_performance_level

# Set to "auto" for OS-managed scaling (recommended default)
echo auto | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level

# Query current wattage
cat /sys/class/drm/card0/device/hwmon/hwmon*/power1_average

# Cap power (example: 150W for RX 6700 XT, default is 186W)
# Value is in microwatts
echo 150000000 | sudo tee /sys/class/drm/card0/device/hwmon/hwmon*/power1_cap
```

### NVMe Power Efficiency (All Tiers)

```bash
# Check current NVMe power state
sudo nvme get-feature /dev/nvme0 -f 0x0c -H

# Enable APST (Autonomous Power State Transitions) — allows NVMe to sleep when idle
# Usually enabled by default in modern kernels. Verify:
sudo nvme get-feature /dev/nvme0 -f 0x0c | grep -i apst

# If not enabled, add kernel parameter to /etc/default/grub:
# nvme_core.default_ps_max_latency_us=5500
# Then: sudo update-grub && sudo reboot
```

### Linux System-Level Power Tuning (All Tiers)

Install and use `tuned` for cooperative workload profiles:

```bash
sudo apt install tuned tuned-utils

# For standard cooperative node (balanced power/performance):
sudo tuned-adm profile balanced

# For a node in Graceful Degradation mode (low power / solar):
sudo tuned-adm profile powersave

# For full AI inference performance mode:
sudo tuned-adm profile throughput-performance

# Check current active profile:
tuned-adm active
```

Install `powertop` to audit per-device power draw:

```bash
sudo apt install powertop

# Interactive audit:
sudo powertop

# Auto-tune all devices to optimal power state:
sudo powertop --auto-tune

# Persist auto-tune across reboots via systemd:
sudo tee /etc/systemd/system/powertop.service > /dev/null <<EOF
[Unit]
Description=PowerTOP auto-tune
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/powertop --auto-tune
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable powertop.service
```

---

## 5. Completing the Material Passport

When a component is procured and verified, fill one row in `material_passport_template.csv`.

### Field Guidance

| Field | How to Fill |
|---|---|
| `passport_id` | Format: `MP-[COOP-ID]-[YEAR]-[SEQUENCE]`, e.g. `MP-SUNRISECOOP-2025-007` |
| `embodied_carbon_kg_co2e` | Use the [Boavizta API](https://doc.api.boavizta.org) or [Ecoinvent database](https://ecoinvent.org) for estimates. For GPUs: typical range 80–120 kg CO₂e. For a mini PC: 30–60 kg CO₂e. If unknown, write `ESTIMATED: [value]` with your source. |
| `e_waste_diverted_kg` | The physical weight of the refurbished unit. Most Mini PCs: 0.8–1.5kg. Most GPUs: 0.7–1.2kg. If new, enter `0.0`. |
| `conflict_minerals_status` | `UNVERIFIED` / `PARTIAL` / `CERTIFIED`. See Section 3 for definitions. |
| `planned_eol_disposition` | Be specific: "Return to [seller] takeback programme" or "Donate to [local repair café]" or "R2-certified recycler in [city]". |
| `logged_by` | Cooperative member handle, not full name — respect member privacy. |

### Where to Publish the Passport

Completed passports should be committed to:
1. This repository under `supply_chain/passports/[coop-name]/passport-[year].csv`
2. The cooperative's Iskander OS instance (auto-synced to IPFS if configured)

The IPFS content hash of the passport file serves as a tamper-evident public record —
once published, its integrity can be verified by any member at any time.

---

## 6. End-of-Life and Circular Economy

### Target Component Lifespans

| Component | Target Lifespan | Signal to Replace |
|---|---|---|
| N100 Mini PC | 7–10 years | Thermal throttle that paste replacement doesn't fix; POST failure |
| CPU (socketed) | 8–12 years | Physically fine until platform obsolescence |
| GPU | 5–8 years | VRAM errors in memtest; fan bearing failure (replace fans, not card) |
| NVMe SSD | 5–7 years | S.M.A.R.T. `Percentage Used` > 80% or `Available Spare` < 10% |
| SATA SSD | 5–8 years | Same S.M.A.R.T. thresholds |
| PSU (SFX) | 8–10 years | Fan noise; efficiency drop (measure with INA3221 before/after load) |
| UPS Battery | 3–5 years | NUT reports battery charge < 80% of rated capacity |
| Motherboard | 10–15 years | Capacitor bulge; POST failure |

### UPS Battery Replacement

UPS batteries are the most frequent replacement item in this stack.
Most UPS units use standard 12V 7Ah or 12V 9Ah sealed lead-acid (SLA) batteries,
available from any battery retailer. Replacing the battery yourself costs ~$20–30 and
extends the UPS chassis lifespan by another 3–5 years.

Many UPS manufacturers (APC, CyberPower) sell branded replacement batteries at 3×
the price of equivalent generic SLA batteries. The generic SLA battery from a local
battery shop is electrically identical.

### End-of-Life Disposal

**Do not send working hardware to landfill. Do not send it to a non-certified recycler.**

| Hardware type | Preferred EOL path |
|---|---|
| Functioning computers | Donate to local repair café, school, or community tech programme |
| Functioning GPUs | Sell on secondary market (extends use life) |
| Non-functioning CPUs / RAM / SSDs | R2-certified e-waste recycler (see Section 1 for directories) |
| UPS batteries (SLA) | Automotive shop battery recycling (most accept SLA for free) |
| PCBs with no resale value | R2 or e-Stewards certified recycler only |

**Never ship e-waste internationally to non-OECD countries.** This is illegal under the
Basel Convention and causes direct harm to informal recycling communities.

### The Repair Café Network

Before declaring a component end-of-life, check:
- **Restart Project / Repair Café International**: https://www.repaircafe.org/en/visit/
- **iFixit Pro Tech Toolkit**: available at most repair cafés for community use
- **OpenRepair Data**: https://openrepair.org — database of fixable faults by model

A failing GPU fan bearing is a $5 fix, not a $200 card replacement.
A dried CPU thermal paste is a $7 fix, not a Mini PC replacement.
The Iskander Hearth internal QR codes are designed precisely to make this repair
culture accessible to every cooperative member, not just technical ones.
