# Building the Tier 2 Commons Node

**A step-by-step guide to physically assembling the Iskander Hearth Commons Node.**

This guide is written for someone who has never built a PC before.
If you have built one before, the BOM component IDs (`T2-xxx`) in each step
will orient you quickly.

> **Tone check:** You are assembling a sovereign server for your cooperative.
> Every cable you route is one less dependency on a cloud monopoly.
> Take your time. It is not complicated — it is just methodical.

---

## Table of Contents

1. [Safety and Static](#1-safety-and-static)
2. [Prepare Your Workspace](#2-prepare-your-workspace)
3. [Install CPU onto Motherboard](#3-install-cpu-onto-motherboard)
4. [Install RAM](#4-install-ram)
5. [Install NVMe SSDs](#5-install-nvme-ssds)
6. [Install the TPM 2.0 Module](#6-install-the-tpm-20-module)
7. [Install the Wi-Fi Card and Antenna Cables](#7-install-the-wi-fi-card-and-antenna-cables)
8. [Install Motherboard Standoffs in Chassis](#8-install-motherboard-standoffs-in-chassis)
9. [Install the I/O Shield](#9-install-the-io-shield)
10. [Mount the Motherboard](#10-mount-the-motherboard)
11. [Install the Power Supply](#11-install-the-power-supply)
12. [Install the GPU](#12-install-the-gpu)
13. [Install the SATA SSD](#13-install-the-sata-ssd)
14. [Connect Power Cables](#14-connect-power-cables)
15. [Connect Front Panel Headers](#15-connect-front-panel-headers)
16. [Connect Fan Headers](#16-connect-fan-headers)
17. [First Power-On Test (No OS)](#17-first-power-on-test-no-os)
18. [Install CPU Cooler](#18-install-cpu-cooler)
19. [Attach Antenna Cables to Chassis](#19-attach-antenna-cables-to-chassis)
20. [Affix QR Code Repair Tiles](#20-affix-qr-code-repair-tiles)
21. [Close the Chassis](#21-close-the-chassis)

---

## 1. Safety and Static

Static electricity is the main enemy of computer components. A static discharge you
cannot feel can permanently damage a CPU, GPU, or RAM stick.

**Always do one of the following before touching any component:**
- Wear an anti-static wrist strap connected to a grounded metal surface (e.g. the unpainted
  metal interior of the chassis, once it is plugged in but switched off at the mains).
- Touch the unpainted metal chassis frame before touching any component, and do so again
  every few minutes.

**Additional rules:**
- Never work on carpet. Bare wood, tile, or an anti-static mat are fine.
- Keep components in their anti-static bags until the moment you install them.
- Never touch the gold contacts (pins/pads) on CPUs, RAM, or PCIe cards with your fingers.
- If you take a break mid-build, unplug the PSU from the wall and touch the chassis metal
  before resuming.

---

## 2. Prepare Your Workspace

1. Clear a table large enough to hold the open chassis plus several anti-static bags.
2. Place the chassis on the table and open the side panel (the larger removable panel —
   usually secured by two thumbscrews on the rear).
3. Remove the chassis from its box and set all accessories aside (screws bag, cables, manual).
4. Lay the motherboard (T2-002) box and the CPU box (T2-001) to one side. Do not open yet.
5. Have your Phillips #2 screwdriver, #1 screwdriver, and needle-nose pliers within reach.

---

## 3. Install CPU onto Motherboard

**Components:** T2-001 (CPU), T2-002 (Motherboard)

The CPU is the brain of the node. It connects to the motherboard's AM5 socket.
AM5 uses a Land Grid Array (LGA) design — the pins are on the **socket**, not the CPU.
This means you cannot accidentally bend CPU pins.

> ⚠️ This is the most delicate step. Move slowly. The CPU only fits one way.

1. Remove the motherboard from its anti-static bag and place it on the anti-static bag
   (use it as a work mat — it is grounded and padded).
2. Locate the AM5 CPU socket in the centre-upper area of the board.
   It has a metal retention frame and a protective plastic cover.
3. Release the retention lever: push the lever sideways (away from the socket) and
   lift it upward. The frame will tilt open.
4. **Do not remove the plastic socket protector yet** — remove it only when you are
   about to lower the CPU in.
5. Remove the CPU from its packaging. Hold it by the edges only.
6. Look at the CPU: find the small golden triangle in one corner. Look at the socket:
   find a matching triangle marker. These triangles must align.
7. Remove the plastic socket protector (keep it — needed if you ever return the board).
8. Lower the CPU **straight down** into the socket. It will drop in with its own weight.
   **Do not press, twist, or force it.** If it does not drop in, check triangle alignment.
9. Lower the retention frame back over the CPU. Push the lever down and lock it under
   the retention hook. You will feel moderate resistance — this is normal.
10. The CPU is now installed.

---

## 4. Install RAM

**Components:** T2-003 (32GB DDR5 Kit — 2× 16GB sticks)

1. Locate the two RAM slots on the motherboard (beside the CPU socket, usually labelled
   A2 and B2 — check your board manual for the correct slots for a 2-stick configuration).
2. For a 2-stick kit in a 2-slot Mini-ITX board: use both slots.
3. Open the retention clips at each end of the RAM slots by pressing them outward.
4. Remove a RAM stick from its packaging. Look at the bottom edge: there is a notch
   offset to one side. Look at the slot: there is a matching key. They only fit one way.
5. Align the RAM stick over the slot, notch matching the key.
6. Press down **firmly and evenly on both ends simultaneously** until both retention
   clips click shut. The click is definitive — if it feels like the RAM is floating,
   press harder.
7. Repeat for the second stick.
8. Verify both clips are fully closed. If one side is up, the stick is not fully seated.

---

## 5. Install NVMe SSDs

**Components:** T2-005 (1TB NVMe — System Drive), T2-006 (SATA SSD — Data Drive, installed later)

The 1TB NVMe SSD (T2-005) installs in the board's primary M.2 slot.
Your ASRock B650M-ITX/ax has two M.2 slots — use the one closest to the CPU
(labelled M2_1 or ULTRA M.2 in the manual) for the fastest PCIe 4.0 lane.

1. Locate the M.2 slot on the motherboard. Remove the small screw holding the M.2 retention
   standoff (store this screw safely — it is tiny and easy to lose).
2. Remove the SSD from its packaging. Hold by the edges.
3. Insert the SSD into the M.2 slot at a 30-degree angle, gold contacts first.
   Push it in until it seats fully and sits slightly raised at the far end.
4. Press the far end of the SSD down flat and re-insert the retention screw.
   Tighten finger-tight, then a quarter-turn more. **Do not overtighten** — M.2 screws
   strip easily.
5. Some boards include an M.2 heatsink. If yours does, re-attach it over the SSD.

---

## 6. Install the TPM 2.0 Module

**Components:** T2-009 (TPM 2.0 Module — Infineon SLB9665 or board-matched equivalent)

The TPM module is the hardware security chip that stores Iskander OS's Web3 Safe key shards.
It plugs into the 14-pin TPM header on the motherboard.

> ⚠️ The TPM header has a **keyed pin** (one pin hole is blocked) to prevent incorrect
> insertion. Find it before pushing the module in.

1. Locate the TPM header on the motherboard. On ASRock boards it is labelled `TPM` and is
   usually near the front-panel header cluster (bottom edge of the board).
2. Check your board manual for the exact pin layout — confirm the module matches.
3. Align the TPM module connector with the header. The blocked pin position must align.
4. Press the module down firmly and evenly onto the header until it is fully seated.
   There is no click — it should sit flush with no wiggle.
5. The TPM will activate on first Iskander OS boot. It requires no further configuration here.

---

## 7. Install the Wi-Fi Card and Antenna Cables

**Components:** T2-008 (Intel AX210 — M.2 A+E key card + antenna pigtails)

The AX210 Wi-Fi card is what allows the node to broadcast the `Iskander_Hearth_Setup` hotspot
on first boot, and to join or form cooperative mesh networks.

1. Locate the M.2 A+E slot on the motherboard. On Mini-ITX boards this is usually the shorter
   M.2 slot near the board edge, often labelled `M2_WIFI` or `WIFI MODULE` in the manual.
2. Insert the AX210 at a 30-degree angle and press down. Secure with the M.2 retention screw
   (same process as the NVMe SSD in Step 5).
3. The AX210 has two small **U.FL / MHF4 connectors** on its top edge (labelled 1 and 2).
4. Take the two antenna pigtail cables from the AX210 package. Each has a tiny U.FL connector
   on one end and an RP-SMA connector on the other.
5. Press the U.FL connectors onto the AX210 pads firmly until you feel a click.
   Main antenna (thicker trace on cable) → connector labelled 1. Aux → connector labelled 2.
6. Route the antenna cables to the rear of the chassis. The RP-SMA connectors will thread
   through the chassis antenna holes and be secured with nuts on the outside (Step 19).

---

## 8. Install Motherboard Standoffs in Chassis

**Components:** T2-012 (Chassis), standoffs bag from chassis accessories

Standoffs are small threaded metal posts. They hold the motherboard above the chassis floor
and prevent short circuits between the PCB and the metal chassis.

1. Open the chassis accessories bag and find the brass standoffs and the I/O shield.
2. Hold the motherboard against the chassis motherboard tray and look through the
   motherboard mounting holes to identify which chassis holes to use.
   For Mini-ITX, there are 4 mounting holes.
3. Using needle-nose pliers, screw a standoff into each of the 4 matching chassis holes.
   **Finger-tight plus a half-turn** — do not overtighten.
4. Verify: the standoff pattern matches the 4 motherboard mounting holes exactly.
   If any standoff is under a location with no motherboard hole, remove it immediately —
   it will short the PCB.

---

## 9. Install the I/O Shield

1. Find the rectangular metal I/O shield in the chassis box. It matches the cutout on the
   rear of the chassis.
2. From inside the chassis, align the I/O shield tabs with the rear I/O cutout.
3. Press firmly around the entire perimeter until all tabs click into place.
   The shield should be flush with the chassis rear panel on the outside.
4. Run your finger around the inside edge. Any tabs sticking inward must be bent back —
   they will contact the motherboard I/O ports and cause connection issues.

---

## 10. Mount the Motherboard

1. Lift the motherboard (with CPU, RAM, NVMe, TPM, and Wi-Fi card installed) and lower it
   into the chassis.
2. Align the I/O ports on the back of the board with the I/O shield holes.
   The I/O shield tabs should gently contact the port housings.
3. Lower the board onto the standoffs. All 4 standoff holes must align.
4. Insert the 4 motherboard screws (from the chassis accessories bag) and tighten them
   in a diagonal pattern (opposite corners first) to distribute pressure evenly.
   **Finger-tight plus a quarter-turn only** — these are small threads and strip easily.

---

## 11. Install the Power Supply

**Components:** T2-007 (SFX PSU 650W)

1. Locate the PSU bay in the chassis. On most Mini-ITX cases, the PSU mounts at the top
   or rear of the case. Consult your specific chassis manual for orientation.
2. For SFX PSUs: slide the PSU into its bay with the fan facing the direction specified
   in your chassis manual (usually toward the chassis interior for intake, or toward a vent
   for exhaust — check the chassis airflow diagram).
3. Secure the PSU with the 4 screws provided. These are accessed from the **rear** of the
   chassis — the same face as the I/O shield.
4. Do not connect any cables yet.

---

## 12. Install the GPU

**Components:** T2-004 (RTX 3060 12GB or equivalent dual-slot GPU)

The GPU is the most physically substantial component. Handle it with both hands.

1. Locate the PCIe x16 slot on the motherboard (the longest slot, closest to the CPU).
2. On the rear of the chassis, identify the PCIe slot covers (2 adjacent blanking plates
   covering the bracket openings). Remove both of them — the GPU is dual-slot and needs both.
   Keep the removed covers in case you ever change the GPU.
3. The PCIe x16 slot has a retention clip at its far end. Press it to the open position.
4. Remove the GPU from its packaging. Hold it by the heatsink body or PCB edges — not the fans.
5. Align the GPU's PCIe connector (the gold-contact strip on its bottom edge) with the slot.
6. Lower the GPU so the rear bracket aligns with the rear chassis opening.
7. Press the GPU **firmly and evenly** into the PCIe slot until the retention clip clicks shut.
8. Secure the rear bracket with 2 screws into the chassis PCIe bracket rail.
9. Do not connect the power cables yet.

---

## 13. Install the SATA SSD

**Components:** T2-006 (2TB SATA SSD)

The SATA SSD mounts in a 2.5-inch drive bay.

1. Locate the drive bays in your chassis. Most Mini-ITX cases have 2× 2.5-inch bays.
2. Slide the SSD into the bay and secure with the small screws (usually 4× M3 side screws
   or a tool-free caddy — check your chassis).
3. Do not connect the data or power cable yet.

---

## 14. Connect Power Cables

Now connect the PSU cables. Route cables through any cable management holes as you go —
a tidy build has better airflow.

**In this order:**

1. **24-pin ATX motherboard connector** — the large connector near the right edge of the
   board. It clicks in firmly. Only fits one way.

2. **CPU / EPS power connector** (4+4 pin or 8-pin) — plugs into the square connector
   near the top-left of the motherboard, labelled `ATX12V` or `CPU_PWR`. Run this cable
   **behind the motherboard tray** if your chassis has a routing hole, to reduce clutter.

3. **GPU PCIe power connector** — the RTX 3060 requires one 8-pin or 12-pin PCIe connector
   (check your specific GPU). Plug it into the connector on the top edge of the GPU.
   It clicks in firmly. If using a 6+2 pin connector, snap both halves together before inserting.

4. **SATA power connector** — find a SATA power cable from the PSU (flat, L-shaped, 15-pin).
   Plug it into the SATA SSD (T2-006). Slide in until it seats; SATA power connectors do not click.

5. **SATA data cable** — connect the thin SATA data cable from the SSD to any SATA port
   on the motherboard. Use SATA port 1 (labelled on the board) if available.

---

## 15. Connect Front Panel Headers

The front panel headers connect the power button, reset button, and power LED on the chassis
front panel to the motherboard.

> This is the most fiddly wiring step. Use a flashlight. Take your time.

1. Locate the front panel header on the motherboard — a cluster of pins near the bottom
   edge of the board, labelled `PANEL` or `F_PANEL` in the manual.
2. Consult your motherboard manual for the exact pin layout (it differs per board).
3. Connect in this order:
   - **PWR_BTN** (power switch): 2-pin connector from chassis. No polarity.
   - **RESET_BTN** (reset switch): 2-pin connector. No polarity.
   - **PWR_LED+** and **PWR_LED–** (power LED): polarity matters — positive pin usually marked
     with a `+` or coloured wire (white/green = positive, black = negative).
   - **HD_LED+** / **HD_LED–** (storage activity LED, optional): same polarity rule.
4. If the node does not power on in Step 17, this is the first thing to recheck.

---

## 16. Connect Fan Headers

**Components:** T2-011 (2× 120mm PWM fans), T2-010 (CPU cooler — not yet installed, but fan cable applies)

1. Connect the chassis intake fan (usually front or top) to a `CHA_FAN` or `SYS_FAN` header
   on the motherboard. The 4-pin PWM connector only fits one way.
2. Connect the chassis exhaust fan to another `CHA_FAN` header.
3. Do not connect the CPU cooler fan yet — the cooler is installed in Step 18.
4. Note which headers you used — you will set fan curves in the BIOS after first POST.

---

## 17. First Power-On Test (No OS)

Before installing the CPU cooler (which is harder to remove), verify the system POSTs
(Power-On Self Test — the initial startup check).

1. Double-check: all large power connectors are seated (24-pin ATX, CPU EPS, GPU PCIe).
2. Connect a monitor to the GPU's HDMI or DisplayPort output.
3. Connect a keyboard via USB.
4. Plug the PSU into the wall and switch on the PSU rocker switch (if present).
5. Press the front panel power button.
6. Expected result: fans spin, GPU fans spin, monitor shows the motherboard BIOS splash screen
   or the ASRock logo, then enters POST.
7. If the system enters BIOS, you are good. Press `F2` or `Delete` to open BIOS setup.
   Verify that the CPU model, RAM amount (32GB), and NVMe SSD are all detected.
   Apply the power efficiency settings from `supply_chain/procurement_guidelines.md`, Section 4.
   Save and exit BIOS (`F10`). The system will reboot and show "No boot device" — that is correct.
   We have not installed the OS yet.

**If nothing happens on power button press:**
- Recheck front panel power button header (Step 15) — most common cause.
- Verify PSU switch is on.
- Verify 24-pin ATX and CPU EPS connectors are fully seated.

**If POST shows an error code or red LED on the board:**
- Note the error code. ASRock BIOS POST codes are in the board manual.
- Most common: RAM not seated (reseat both sticks), GPU not seated (reseat).

8. Power off by holding the power button for 5 seconds. Switch off the PSU at the wall.

---

## 18. Install CPU Cooler

**Components:** T2-010 (Low-profile CPU cooler — e.g. Noctua NH-L9a-AM5)

The cooler is installed after POST verification so it does not obscure diagnostic work.

1. The AM5 socket uses a standard mounting frame — check if your cooler uses the Intel or
   AMD mounting hardware. The NH-L9a-AM5 ships with dedicated AM5 mounting hardware.
2. Apply thermal paste: place a pea-sized dot (~4mm) in the centre of the CPU's Integrated
   Heat Spreader (the metallic top surface). Do not spread it — the cooler pressure will
   distribute it.
3. Lower the cooler onto the CPU, aligning the mounting holes with the board mounting points.
4. Tighten the mounting screws **alternately and diagonally** — a few turns on each, cycling
   through all four, until finger-tight plus a half-turn. This ensures even clamping pressure.
5. Connect the cooler's fan cable to the `CPU_FAN` header on the motherboard.

---

## 19. Attach Antenna Cables to Chassis

The Intel AX210 antenna pigtails (routed in Step 7) terminate at RP-SMA connectors.
These thread through small holes in the rear panel of the chassis.

1. Locate the two antenna holes on the rear panel (drilled or pre-punched by the chassis
   manufacturer, usually near the top of the rear panel).
2. Thread the RP-SMA connectors through from the inside.
3. Thread the nut onto each connector from the outside and tighten with pliers until snug.
   Do not overtighten — the RP-SMA threads are fine and the panel is thin.
4. Screw the external antenna rods (included with AX210 package or purchased separately)
   onto the RP-SMA connectors on the outside of the chassis.
5. Orient the antennas vertically (90° from horizontal) for best omnidirectional coverage.
   For the setup hotspot, this position maximises range.

---

## 20. Affix QR Code Repair Tiles

**Components:** T2-017 (Internal QR Code Label Set) or 3D-printed tiles from `enclosures/qr_surface_v1.scad`

This is the Framework-inspired repair step. QR codes on the interior of the chassis link
every cooperative member — technical or not — directly to the repair guide for each component.

**Generate QR codes before this step:**
1. Go to any QR code generator.
2. Create one QR code per component pointing to:
   - GPU: `[repo URL]/boms/tier2_commons.md` (or deep-link to T2-004 section)
   - PSU: same file, T2-007 section
   - SSD: same file, T2-006 section
3. Print on 30 × 30mm adhesive polyester labels (e.g. Avery 6450).

**Affix locations:**
| QR Code | Where to Stick |
|---|---|
| GPU | Left interior side panel, at GPU height — visible when the panel is removed |
| PSU | Near the PSU bay, on the interior wall — visible from the main chamber |
| SSD | Above or beside the drive bay — visible from the main chamber |

If using 3D-printed tiles from `qr_surface_v1.scad`: press the label into the tile's
recessed area, then apply 3M double-sided foam tape to the tile back and press onto the
chassis wall surface. Hold for 30 seconds.

---

## 21. Close the Chassis

1. Do a final cable management pass — tuck loose cables away from fans using cable ties.
   Ensure no cable is near a fan blade.
2. Verify all fans spin freely with a gentle nudge before closing.
3. Refit the side panel and secure with thumbscrews.
4. Place the node in its final location.
5. Connect Ethernet cable (T2-013) to the motherboard's RJ45 port.
6. Connect the INA3221 power sensor (T2-015) — see `flashing_iskander.md`, Sensor Bridging section.
7. Connect the UPS (T2-014) — plug the node's PSU power cable into the UPS output,
   and plug the UPS into the wall. Connect UPS to node via USB cable.

**The Commons Node is now physically complete.**

Continue to [`flashing_iskander.md`](./flashing_iskander.md) for OS installation,
the Ad-Hoc setup flow, and power sensor integration.
