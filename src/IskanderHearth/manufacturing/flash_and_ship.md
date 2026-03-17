# Flash-and-Ship Procedure

**License:** CERN-OHL-S v2
**Phase:** 8 — Distributed Cooperative Manufacturing
**Target:** Under 2 hours per node (excluding 3D print time)

---

## Pre-requisites

- Iskander OS image downloaded and SHA256 verified
- USB flash duplicator (P8-003) loaded and tested
- QA test station ready (monitor, keyboard, Ethernet)
- Packaging materials staged

---

## Step 1 — Verify OS Image (5 min)

```bash
# Download latest Iskander OS image (URL from federation announcement)
wget https://[mirrors]/iskander-os-latest.img.xz
wget https://[mirrors]/iskander-os-latest.img.xz.sha256

# Verify checksum BEFORE flashing — a corrupt image will brick nodes
sha256sum -c iskander-os-latest.img.xz.sha256
# Must print: iskander-os-latest.img.xz: OK
```

Decompress:
```bash
xz -d iskander-os-latest.img.xz
# Result: iskander-os-latest.img
```

---

## Step 2 — Flash NVMe via USB Duplicator (15 min for 1–7 nodes)

1. Insert NVMe drives into USB-to-NVMe adapters. Load adapters into duplicator slots.
2. Load master USB drive (pre-flashed with verified OS image) into source slot.
3. Select "Duplicate 1:N" on duplicator panel.
4. Start duplication. LED indicators show progress.
5. Wait for all slot indicators to show GREEN (complete).
6. Remove NVMe drives. Label each drive with node serial sticker.

**Verify one drive per batch** by mounting and checking:
```bash
# Mount the flashed NVMe and verify OS partition
fdisk -l /dev/sdX        # Verify partition table
mount /dev/sdX2 /mnt     # Mount OS root partition
cat /mnt/etc/iskander-os-version
umount /mnt
```

---

## Step 3 — Install NVMe + Complete Hardware Assembly (30 min)

1. Install flashed NVMe into node chassis (M.2 2280 slot).
2. Install Solidarity HAT if not already mounted.
3. Connect all HAT wiring (kill switches, I2C, power sensor).
4. Connect Glass Box UX wiring (buttons, NeoPixel strip).
5. Close chassis panels. Do not install front panel yet (needed for first-boot display).

---

## Step 4 — First Boot in Test Jig (20 min)

Connect to test jig: monitor (HDMI), keyboard (USB), Ethernet (cat6 to local network).

1. Power on. Observe:
   - BIOS POST passes
   - Iskander OS boots (GRUB → systemd)
   - NeoPixel strip shows **rainbow sweep** (SETUP state) → confirms LED daemon started
2. Login as `iskander` (default first-boot password from OS image docs).
3. Complete first-boot provisioning:
   ```bash
   sudo /opt/iskander/first-boot/setup.sh
   # Wizard: set node name, cooperative ID, network config, time zone
   ```
4. Provision ATECC608B:
   ```bash
   sudo python3 /opt/iskander/firmware/solidarity_hat/atecc_provision.py
   # Confirm: "Provisioning complete. ATECC608B is deployment-ready."
   ```

---

## Step 5 — Run Automated QA Test (20 min)

```bash
sudo bash /opt/iskander/manufacturing/qa_automated_test.sh
```

**If all checks PASS:** proceed to Step 6.
**If any check FAILS:** diagnose and resolve before continuing. Do not ship a failing node.

Save QA log:
```bash
# QA log is auto-saved to /var/log/iskander/qa_results_<date>.log
# Copy to Material Passport directory:
cp /var/log/iskander/qa_results_*.log \
   /opt/iskander/supply_chain/passports/qa_log_$(hostname).log
```

---

## Step 6 — Seal Chassis and Affix QR Codes (10 min)

1. Route all cables neatly. Secure with cable ties.
2. Install front panel (HITL buttons should now be accessible).
3. Verify NeoPixel diffuser is flush in top panel channel.
4. Install and finger-tighten all panel screws.
5. Affix QR repair code stickers to the three interior locations:
   - Left panel interior (GPU repair QR)
   - Right panel interior upper (PSU repair QR)
   - Right panel interior lower (SSD repair QR)
6. Affix node serial label to rear panel near I/O shield.

---

## Step 7 — Print and Prepare Material Passport (5 min)

```bash
# Generate Material Passport PDF (if iskander-docs tool installed)
# Otherwise: print supply_chain/passports/solidarity_hat_passport.csv as is

# Generate node-specific QR code pointing to this node's serial on the
# federation ledger (for long-term repair traceability):
qrencode -o /tmp/node_qr.png "https://[federation]/nodes/$(hostname)"
```

Print Material Passport (or export to PDF). Include in packaging.

---

## Step 8 — Pack and Ship (10 min)

Box contents (in order of packing):

1. Iskander Hearth node (bubble-wrapped)
2. Power cable (IEC C13, region-appropriate)
3. Ethernet cable (Cat6, 2m, with velcro tie)
4. UPS (APC Back-UPS 600 or equivalent, in own box)
5. Wi-Fi antenna rods (×2, in small zip bag)
6. USB installer backup drive (labelled with OS version)
7. Printed setup card ("Your Iskander Hearth node" — one page, plain language)
8. CERN-OHL-S v2 license summary card (printed, required by license)
9. Material Passport (printed)
10. QA test log printout

Seal box. Apply shipping label. Apply "FRAGILE" sticker if using courier.

---

## Time Budget

| Step | Target time |
|------|-------------|
| Image verify | 5 min |
| NVMe flash (per batch of 7) | 15 min |
| Hardware assembly | 30 min |
| First boot + provisioning | 20 min |
| Automated QA | 20 min |
| Seal + QR codes | 10 min |
| Material Passport | 5 min |
| Pack | 10 min |
| **Total** | **≤ 115 min** |

Target met: under 2 hours per node.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Node doesn't POST | Memory not seated | Reseat RAM modules |
| OS boots to initramfs | Corrupted NVMe flash | Reflash from verified image |
| NeoPixel no rainbow on boot | hearth-leds.service failed | `journalctl -u hearth-leds` |
| ATECC608B provision fails | I2C wiring | `i2cdetect -y 1`; re-check HAT wiring |
| QA test fails: GPU temp | Thermal paste / pads | Replace GPU thermal pads (P7-003) |
| QA test fails: acoustic | Fan speed too high | Adjust BIOS fan curve; check thermal pads |
