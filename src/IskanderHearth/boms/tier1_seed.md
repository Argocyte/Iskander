# Tier 1 – Seed Node

**Scale:** 1–10 cooperative members
**Form Factor:** Refurbished 1L Mini PC / N100 SBC
**BOM:** [`tier1_seed.csv`](./tier1_seed.csv)
**Estimated Total Cost:** ~$330–$390 USD (refurbished)

---

## What Is This?

The Seed Node is the entry point to Iskander Hearth. It is a small, quiet, low-power computer
about the size of a paperback book. A cooperative of even two or three people can pool resources
to build one. It runs on less electricity than a lightbulb and can operate on solar power
with the right UPS setup.

Think of it as a **digital hearth for a small group** — hosting your encrypted files, running
lightweight AI assistants, and keeping your communications off corporate servers.

---

## Design Priorities

### Refurbished First
The heart of the Seed Node is a **refurbished N100 Mini PC** — a class of small computers
originally sold by companies like Lenovo, HP, Dell, and Beelink. When businesses upgrade their
fleets, these machines enter the secondhand market in excellent condition. Buying one diverts
e-waste and costs 60–70% less than buying new.

Alternatives include the **Lenovo ThinkCentre M75q Tiny** (AMD Ryzen Embedded) or the
**HP EliteDesk 800 G4 Mini** — both widely available through ITAD (IT Asset Disposition) resellers.

### Permacomputing Power Awareness
The Seed Node includes an **INA219 power sensor** wired between the power brick and the computer.
This tiny sensor speaks I2C — a simple two-wire protocol — and reports real-time wattage to
Iskander OS. When the OS detects the cooperative is running on battery or solar (via the UPS USB
connection), it can automatically:
- Pause non-essential background tasks
- Reduce screen brightness and network polling
- Notify members that the node is in low-power mode

This is **Graceful Degradation**: the system keeps serving members even as power becomes scarce,
rather than crashing suddenly.

### UPS Integration
The **CyberPower CP600LCD** or equivalent UPS connects via USB to the Mini PC. Iskander OS runs
**NUT (Network UPS Tools)** to read battery level, load percentage, and estimated runtime.
When battery drops below a configured threshold (default: 20%), the OS initiates a safe shutdown
sequence, committing any open data to disk before power is lost.

---

## Component Rationale

| Component | Why This Choice |
|---|---|
| N100 Mini PC | 6W TDP. Silent. AES-NI for encryption. Widely available refurbished. |
| 16GB DDR5 SO-DIMM | Minimum for running small LLMs (Phi-3, Gemma-2B via llama.cpp). Upgradeable. |
| 512GB NVMe | Enough for OS + 2–3 quantized model files + cooperative data. |
| INA219 Sensor | $10 component. Gives OS real wattage telemetry. Essential for solar deployments. |
| CyberPower 600VA UPS | NUT-compatible. Pure sine wave protects Mini PC PSU. USB HID monitoring. |
| USB Wi-Fi (optional) | Alfa AWUS036ACS supports AP mode for emergency mesh networking. |

---

## Right to Repair Notes

- The N100 Mini PC uses **standard Phillips and Torx screws** with no glue. Disassembly is
  documented on iFixit for most ThinkCentre/EliteDesk models.
- Replace thermal paste (T1-010) on first disassembly — refurbished units often have dried paste
  causing thermal throttling that reduces performance.
- All components are available at standard electronics retailers. No proprietary replacements.
- Print a QR code linking to this repository and affix it inside the chassis lid.

---

## Upgrade Path

When a cooperative grows beyond 10 members, this node can be **repurposed** as:
- A dedicated backup/archival node
- A network gateway or DNS resolver
- A solar power monitoring station

Move to **Tier 2 – Commons** for the primary node when local AI inference becomes a core need.

---

## Estimated Power Draw

| State | Draw |
|---|---|
| Idle | ~6–8W |
| Active (CPU load) | ~15–20W |
| Peak (NVMe + network) | ~25W |

At 15W average, a 600VA UPS provides ~25 minutes of runtime — enough for a clean shutdown
during an outage, or to bridge a solar cloud gap.
