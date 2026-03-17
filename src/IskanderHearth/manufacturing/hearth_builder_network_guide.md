# Hearth Builder Network Guide

**License:** CERN-OHL-S v2
**Revision:** 1.0 | 2026-03-16
**Status:** Living document — contributions via federation governance

---

## What This Is

The Hearth Builder Network is a decentralised network of Maker-Coops, FabLabs,
community workshops, and individual builders who manufacture and distribute
Iskander Hearth nodes. There is no central authority. There is no franchise.
There is no permission required.

If you can build it, you are a Hearth Builder.

This guide explains how to set up your workspace, qualify your builds, and
participate in the cooperative network — without ever asking anyone for the right
to do so.

---

## 1. The Franchise-Free Model

### 1.1 Your rights under CERN-OHL-S v2

By receiving these source files, you have the following irrevocable rights:

- **Build:** Manufacture Iskander Hearth nodes for yourself, your community, or for sale.
- **Sell:** Charge for your labour, materials, and expertise. There are no royalties.
- **Modify:** Change the design to suit your materials, tools, or community needs.
- **Distribute:** Share modified versions, under the same CERN-OHL-S v2 license.
- **Call it Iskander Hearth:** You may describe compatible builds as "Iskander Hearth"
  without trademark restriction, provided the CERN-OHL-S v2 source location is disclosed.

### 1.2 Your obligations under CERN-OHL-S v2

These are not requests. They are the legal conditions that keep the design free forever:

1. **Source disclosure:** All distributed hardware must include or clearly link to the full
   source (this repository). The source location notice on `B.SilkS` of the Solidarity HAT
   PCB fulfils this for the PCB. For assembled nodes: include the repository URL on the
   packaging or setup card.
2. **License propagation:** Any modified version must be distributed under CERN-OHL-S v2.
   You cannot make it proprietary.
3. **Change notation:** Modified versions must clearly state what was changed and from what
   source. Use the `CHANGES.md` format or equivalent.
4. **No additional restrictions:** You may not add DRM, patent licenses, or other conditions
   that restrict recipients' rights beyond CERN-OHL-S v2.

### 1.3 What "Hearth Builder" means

"Hearth Builder" is a self-declared status. There is no certification process,
no exam, no fee, no approval from the Iskander Hearth project. You build it;
you're a builder. The builder self-assessment (`builder_self_assessment.md`) is
a quality checklist for your own benefit, not a gatekeeping mechanism.

---

## 2. Setting Up Your Micro-Factory

The complete equipment list is in `microfactory_equipment_bom.csv`. Minimum
viable setup for a Tier 1 Seed node:

| Equipment | Minimum spec | Why |
|-----------|-------------|-----|
| FDM 3D printer | 256mm³ build vol, PETG-capable | Chassis panels, brackets |
| Soldering station | Temperature-controlled, ≥350°C | HAT assembly, wiring |
| Digital multimeter | Basic continuity + voltage | Kill switch verification |
| Anti-static mat | Grounded, ≥ 500×400mm | ESD protection (ATECC608B is sensitive) |

Full Tier 2 production (including Solidarity HAT SMD assembly) adds:
- Hot air rework station (for SOIC-14 INA3221 placement)
- Stencil paste printer or steady hand + flux
- USB flash duplicator (for Iskander OS bulk flashing)
- Label printer (for QR codes and Material Passports)

Total micro-factory setup cost: $705–$955 one-time. Amortises quickly across
a cooperative with regular build sessions.

---

## 3. Sourcing Components

### 3.1 Component availability strategy

All BOM components (see `boms/`) are specified with:
- Primary supplier (DigiKey, JLCPCB)
- Manufacturer part number for cross-referencing alternatives
- Specification sufficient to qualify substitutes

No single-source components are used. Every IC, connector, and passive has
at least two qualified substitutes available on the open market.

### 3.2 Group purchasing

Maker-Coops in the Hearth Builder Network often coordinate bulk orders to
reduce per-unit BOM cost. The ActivityPub-federated Iskander OS cooperative
ledger is designed to track and record group purchasing contributions.

Minimum order quantities to watch:
- Solidarity HAT PCB: JLCPCB minimum 5 units. Coordinate across builders.
- Shunt resistors (0.1Ω, 2512): typically sold in reels of 500. Split across coops.
- ATECC608B: individual pricing is reasonable; no minimum order at DigiKey.

### 3.3 Local substitution

If a specific component is unavailable in your region:
1. Check the datasheet for the electrical specification.
2. Find a component meeting that specification from a local distributor.
3. Document the substitution in your build's Material Passport
   (`supply_chain/passports/`) with the replacement part's datasheet URL.
4. Test the substitution per the acceptance criteria before shipping.

---

## 4. Build Process Overview

The complete step-by-step assembly procedure is in:
- `assembly_guides/building_the_commons_node.md` — Tier 2 hardware assembly
- `assembly_guides/installing_solidarity_hat.md` — Phase 5 HAT installation
- `assembly_guides/installing_glass_box_ux.md` — Phase 6 UX installation
- `assembly_guides/flashing_iskander.md` — OS installation

Flash-and-ship target: **under 2 hours per node** (excluding 3D print time).

### 4.1 Build session structure (recommended for cooperative builds)

A four-person cooperative build session can assemble 4 Tier 2 nodes per day:

| Station | Person | Time |
|---------|--------|------|
| Hardware assembly | 1 | 60 min/node |
| OS flashing + QA testing | 1 | 30 min/node |
| Chassis + 3D print install | 1 | 20 min/node |
| Material Passport + packaging | 1 | 10 min/node |

3D printing runs overnight. One printer can produce chassis panels for 2 nodes/night.

---

## 5. Quality Assurance

Every node must pass the automated QA test before leaving your workshop:

```bash
sudo bash /opt/iskander/manufacturing/qa_automated_test.sh
```

The script checks all hardware peripherals, runs a 5-minute inference stress test,
and verifies thermal management. Results are written to the QA log.

Manual checks that require the acoustic test protocol:
- Acoustic measurement at 1m (target: < 35 dBA during inference)
- GPU temperature under 30-minute `gpu-burn` load (target: < 83°C)

Record all results in `qa_qc_checklist.csv` and include with the Material Passport.

---

## 6. Shipping

Each shipped node must include:

| Item | Purpose |
|------|---------|
| Iskander Hearth node | The build |
| Power cable (IEC C13, region-appropriate) | Power |
| Ethernet cable (Cat6, 2m) | Network connection |
| UPS (APC Back-UPS 600 or equivalent) | Power reliability |
| Antenna rods (×2, for Wi-Fi module) | Wireless |
| USB installer backup drive | OS recovery |
| Printed setup card | First-boot instructions |
| CERN-OHL-S v2 license summary (printed) | Legal requirement |
| Material Passport (printed or QR-linked) | Repairability |

Box dimensions: 400×350×300mm minimum for Tier 2 node + all accessories.
Use recycled cardboard with paper void fill — no single-use plastics.

---

## 7. DisCO Value Tracking Integration

The Iskander Hearth project uses the DisCO (Distributed Cooperative Organization)
framework to track three types of labour value:

| Value type | Examples | How to log |
|------------|----------|-----------|
| **Productive** | Assembly, testing, shipping | Log hours against build serial number |
| **Reproductive** | Documentation updates, supply chain management | Log hours against task type |
| **Care** | Training new builders, community support | Log hours against person helped |

Log your labour contributions to the Iskander OS cooperative ledger via the
ActivityPub-federated interface. The COGS calculator agent uses these records
to compute fair pricing recommendations and cooperative dividend distributions.

Full schema: `manufacturing/disco_labor_accounting.md`.

---

## 8. Federation and Mutual Aid

Hearth Builder nodes are themselves Iskander Hearth nodes. They are part of
the federated network and participate in:

- **Spare parts mutual aid:** Builders announce surplus components via the
  ActivityPub router. Sister nodes can request parts without going through
  commercial channels.
- **Build support:** If a builder gets stuck, they can post a request to the
  federation. Other builders respond — no tickets, no support tiers.
- **Dispute resolution:** If there is a conflict between builders (IP, labour,
  quality), it goes to cooperative federation governance — not courts.
  The governance protocol is in the federation operating agreement
  (linked from the project repository README).

---

## 9. Contacting the Network

There is no central office. Contact happens via:
- ActivityPub federation (your Iskander OS node's social interface)
- Matrix rooms: ask any existing builder for current room addresses
- Git issues: file at the project repository

If you are a new builder and cannot reach the network, just build a node.
The network will find you.
