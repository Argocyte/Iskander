# Iskander Hearth — Packaging & Labeling Specification

**License:** CERN-OHL-S v2
**Phase:** 8 — Distributed Cooperative Manufacturing
**Applies to:** All tiers. Tier-specific differences noted per section.

---

## Purpose

This document defines the materials, dimensions, labeling requirements, and assembly sequence for
packaging Iskander Hearth nodes for shipment or hand-delivery. It is designed so that any Hearth
Builder with access to standard retail packaging supplies can meet the specification without
specialist materials.

**Priority ordering:** protect hardware > communicate CERN-OHL-S compliance > communicate
cooperative values > minimise waste. All packaging decisions should be evaluated in this order.

---

## 1. Box Specifications

### 1.1 Tier 1 – Seed Node

| Parameter | Value |
|-----------|-------|
| Outer box (W × D × H) | 260 × 200 × 150 mm |
| Material | Single-wall corrugated cardboard (B-flute, 3mm) |
| Min. burst strength | 200 kPa (standard B-flute) |
| Source | Standard retail "small" or "book" shipping box |
| Preferred | Recycled/FSC-certified board |

The Tier 1 box must accommodate the N100 Mini PC (≈ 175 × 175 × 50mm) plus accessories.
If using a refurbished mini PC in its original OEM box, the OEM box may substitute as the inner
layer provided the outer box adds ≥ 20mm clearance on all sides for padding.

### 1.2 Tier 2 – Commons Node

| Parameter | Value |
|-----------|-------|
| Outer box (W × D × H) | 420 × 360 × 320 mm |
| Material | Double-wall corrugated cardboard (BC-flute, 6mm) |
| Min. burst strength | 440 kPa |
| Source | Standard retail "medium" shipping box |
| Preferred | Recycled/FSC-certified board |

The Tier 2 chassis (ext_w ≈ 330mm, ext_d ≈ 276mm, ext_h ≈ 256mm per hearth_chassis_v2.scad)
requires ≥ 40mm clearance on all faces for padding. Use double-wall board — single-wall is
insufficient for the chassis weight (~4.5kg without GPU, ~6kg with GPU).

### 1.3 Tier 3 – Federation Node

Tier 3 ships as **two separate boxes** (node + UPS) due to weight:

| Box | Contents | Outer Dims (W×D×H) | Material |
|-----|----------|---------------------|----------|
| T3-A (server) | Rackmount chassis + accessories | 600×650×200mm | Double-wall BC |
| T3-B (UPS) | 1500VA UPS | Manufacturer original packaging | — |

All T3-A components are anti-static bagged individually before boxing (see Section 3).
Tier 3 nodes are typically delivered in-person or shipped via freight pallet — courier shipment
is not recommended for the server box due to weight (≈ 22kg with GPUs).

---

## 2. Inner Packaging and Cushioning

### 2.1 Tier 1 and Tier 2

**Anti-static envelope (node only):**
- Wrap the node chassis in one layer of anti-static bubble wrap (pink/grey ESD-safe).
- Seal with ESD-safe tape. Do not use standard bubble wrap on bare PCBs.
- The Solidarity HAT is inside the chassis — the chassis itself is the ESD barrier.

**Cushioning sequence:**

```
Box base
  └── 30mm foam slab (EPE or similar) OR 50mm crumpled kraft paper
  └── Anti-static wrapped node
  └── Node accessories (power cable, Ethernet, etc.) in kraft paper envelope
  └── Document envelope (see Section 4) — laid flat on top
  └── 20mm foam slab or crumpled kraft paper to fill remaining space
Box lid
```

Shake test: once sealed, the box contents should not move or rattle when shaken. If they do,
add more kraft paper or foam. The node chassis should not contact the cardboard directly on
any face.

**Accessories within node box:**
- Power cable: fold and secure with velcro tie (included), in kraft paper envelope
- Ethernet cable: coil and velcro tie, in same envelope as power cable
- Wi-Fi antenna rods: in labelled zip-lock bag (write "Wi-Fi antennas" on bag with marker)
- USB installer backup drive: in anti-static bag, labelled with OS version and date

### 2.2 Tier 3 Additional Requirements

Each GPU must be removed from the chassis for shipping to prevent PCIe slot stress fracture.
Individually anti-static bag and foam-corner protect each GPU:
- Slide GPU PCBs into original anti-static GPU bags (or new ESD bags ≥ 0.1mm PE/metal)
- Place foam corner blocks on all 4 PCB corners (cut from EPE foam sheet)
- Pack GPU bags vertically (card edge up) in T3-A box with vertical foam divider

HDDs/SSDs: Remove and pack individually in anti-static bags. Label each with ZFS pool role
(e.g., "RAID-Z2 slot 0 of 4") to simplify reinstallation.

---

## 3. Anti-Static Requirements

| Component | Handling Requirement |
|-----------|----------------------|
| Solidarity HAT PCB (bare) | Anti-static bag + ESD wrist strap during installation |
| GPU | Anti-static bag for shipping; ESD mat during installation |
| NVMe drive (flashed) | Anti-static bag |
| ATECC608B (spare) | Anti-static tube or strip |
| Assembled chassis | Anti-static bubble wrap; no bare PCB contact |

ATECC608B is ESD-sensitive (per Phase 5 spec). Any spare ATECC608B chips in the package
must be individually anti-static bagged and stored in the documentation envelope.

---

## 4. Documentation Envelope

All nodes ship with a **physical documentation envelope** inside the box. This is a legal
requirement under CERN-OHL-S v2 (licensees must receive license text with hardware).

**Envelope contents (required):**

| Item | Format | Required? |
|------|--------|-----------|
| CERN-OHL-S v2 license summary | Printed A5 or folded A4 | **Required** |
| Source Location Notice | Printed (URL to this repository) | **Required** |
| Node serial number card | Printed, with QR code | **Required** |
| Material Passport (per-node CSV or printout) | Printed | **Required** |
| QA test log printout | Printed | **Required** |
| "Your Iskander Hearth node" setup card | Printed A5, plain language | Recommended |
| Cooperative welcome letter | Printed, personalised | Optional |

**License summary text (minimum, print verbatim on the card):**

```
This hardware was designed and manufactured under the CERN Open Hardware Licence
Version 2 – Strongly Reciprocal (CERN-OHL-S v2).

You are free to study, modify, manufacture, and distribute this hardware and
derivatives, provided that all modifications are also released under CERN-OHL-S v2
and include a Source Location Notice pointing to the original designs.

Source files: https://github.com/iskander-os/iskander-hearth
License text: https://ohwr.org/cern_ohl_s_v2.txt
```

**Envelope label:**
Print or write on the outside of the envelope:
```
OPEN HARDWARE DOCUMENTATION — DO NOT DISCARD
Iskander Hearth [Tier N] — Serial: [node_serial]
```

---

## 5. Node Serial Label

Every node must have a **permanent external serial label** affixed to the rear panel,
adjacent to the I/O shield.

### 5.1 Label Dimensions

| Parameter | Value |
|-----------|-------|
| Label size | 62 × 29 mm (Brother DK-22205 continuous roll segment) |
| Font (serial) | 10pt monospace bold |
| Font (QR caption) | 6pt sans-serif |
| Material | Polyester label stock (waterproof, heat-resistant to 80°C) |
| Printer | Brother QL-820NWB (P8-006) |

### 5.2 Label Content (per node)

```
┌──────────────────────────────────────────────┐
│  ISKANDER HEARTH  [TIER N] — Serial: IH-XXXXX │
│  Builder: [coop_id]   Date: YYYY-MM-DD        │
│  OS: iskander-os-vX.Y.Z                       │
│  [QR CODE]  github.com/iskander-os/iskander-  │
│             hearth                            │
│  CERN-OHL-S v2 — Open Hardware               │
└──────────────────────────────────────────────┘
```

QR code links to: `https://github.com/iskander-os/iskander-hearth/blob/main/supply_chain/passports/`

### 5.3 Serial Number Format

```
IH-[TIER][YEAR][SEQUENCE]
  IH = Iskander Hearth
  TIER = 1, 2, or 3
  YEAR = 2-digit year (e.g., 25 for 2025)
  SEQUENCE = 4-digit zero-padded build sequence per coop per year
```

Examples:
- `IH-12500001` — Tier 1, year 2025, first build
- `IH-22500047` — Tier 2, year 2025, 47th build
- `IH-32500003` — Tier 3, year 2025, 3rd build

Each cooperative maintains its own sequence counter. Sequence numbers do not need to be globally
unique — they are unique per cooperative and are disambiguated by `builder_coop_id` in the
Material Passport.

### 5.4 QR Code Interior Labels

In addition to the external serial label, three interior QR repair labels must be affixed
inside the chassis (Tier 2 only) at the positions defined in hearth_chassis_v1.scad:

| Location | QR Code Links To |
|----------|-----------------|
| Left panel interior (GPU zone) | GPU repair section in tier2_commons.md |
| Right panel interior upper (PSU zone) | PSU repair section in tier2_commons.md |
| Right panel interior lower (SSD zone) | SSD repair section in tier2_commons.md |

Print these on 30×30mm square labels (cut from DK-22205 roll). They must fit flush within
the qr_recess_depth = 0.8mm recess in the chassis interior.

---

## 6. Outer Box Labeling

Labels affixed to the **outside** of the shipping box:

### 6.1 Shipping Label (standard carrier requirements)
- Full name and address of sender (Hearth Builder / cooperative)
- Full name and address of recipient
- Weight and dimensions
- Barcode / tracking number (carrier-generated)

### 6.2 Open Hardware Declaration Label (required, CERN-OHL-S v2)

Affix to the top face of the box, adjacent to shipping label:

```
┌─────────────────────────────────────────────┐
│  OPEN HARDWARE — CERN-OHL-S v2              │
│  Iskander Hearth [Tier N]                   │
│  Source: github.com/iskander-os/iskander-   │
│          hearth                             │
│  Documentation enclosed. Do not discard.   │
└─────────────────────────────────────────────┘
```

Print on 62×43mm label (Brother DK-22205 segment) or write by hand with permanent marker.

### 6.3 Handling Labels

| Label | Condition | Tier |
|-------|-----------|------|
| FRAGILE | Always (contains electronics) | 1, 2, 3 |
| THIS SIDE UP | Always | 1, 2, 3 |
| HEAVY | Box ≥ 10kg | 2 (with GPU), 3 |
| ESD SENSITIVE | If shipping bare PCBs | Any |

---

## 7. Packaging Waste and Materials Reduction

In alignment with the permacomputing ethic of the project:

1. **Reuse shipping materials** from inbound deliveries whenever safe. Reused corrugated board
   that passes visual inspection (no crush damage, >80% structural integrity) is acceptable.
2. **Avoid polystyrene foam**. Prefer EPE foam, kraft paper crumple, or compostable air pillows.
3. **Avoid excess void fill**. Pack snugly. If the shake test passes with less fill, use less.
4. **Document packaging material weights** in the DisCO labor log
   (`manufacturing/disco_labor_accounting.md`) as reproductive labor (supply chain management).

---

## 8. Tier-Specific Checklist Summary

### Tier 1 – Seed Node

- [ ] Node in anti-static bubble wrap
- [ ] 30mm foam base pad
- [ ] Accessories envelope (power, Ethernet, USB installer)
- [ ] Documentation envelope (CERN-OHL-S card, serial card, Material Passport, QA log)
- [ ] Serial label affixed to rear of mini PC
- [ ] QR label inside lid (per tier1_seed.md Right to Repair Notes)
- [ ] Outer box: FRAGILE, THIS SIDE UP, Open Hardware Declaration labels
- [ ] Shake test passed

### Tier 2 – Commons Node

- [ ] Node in anti-static bubble wrap
- [ ] 40mm foam base pad + top pad
- [ ] Three interior QR repair stickers installed (pre-ship)
- [ ] Accessories: power cable, Ethernet, antenna rods, USB installer
- [ ] Documentation envelope
- [ ] Serial label affixed to rear panel
- [ ] Outer box: FRAGILE, THIS SIDE UP, HEAVY, Open Hardware Declaration labels
- [ ] Shake test passed

### Tier 3 – Federation Node

- [ ] GPUs individually anti-static bagged, foam-cornered, packed vertically
- [ ] NVMe drives individually bagged and labelled with ZFS slot role
- [ ] Documentation envelope (two copies: one per box)
- [ ] Serial label affixed to chassis rear I/O area
- [ ] All component QR labels installed inside chassis
- [ ] T3-A box: FRAGILE, THIS SIDE UP, HEAVY, ESD SENSITIVE, Open Hardware Declaration
- [ ] T3-B (UPS): HEAVY, THIS SIDE UP (use manufacturer label if present)
- [ ] Shake test passed (T3-A)
- [ ] Considered in-person or freight delivery for T3-A

---

## 9. Record Keeping

After sealing each box, record in the DisCO labor log:
- Node serial
- Packaging date
- Packer cooperative handle
- Destination cooperative name
- Box dimensions and weight (for carrier cost tracking)
- Any deviation from this spec (with justification)

Packaging labor is classified as **reproductive labor** in the DisCO framework (not directly
billable productive labor, but essential coordination/maintenance labor). Log it accordingly.
