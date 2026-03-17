# Tier 3 – Federation Node

**Scale:** 50+ cooperative members (or federation of multiple cooperatives)
**Form Factor:** 2U Rackmount or Full ATX Tower
**BOM:** [`tier3_federation.csv`](./tier3_federation.csv)
**Estimated Total Cost:** ~$3,800–$4,800 USD (heavily refurbished server-grade hardware)

---

## What Is This?

The Federation Node is a **serious server** — the kind of machine a small cooperative network
would operate in a colocation facility, a community centre server room, or a collectively owned
data space. It is designed to:

1. **Store immutable cooperative ledgers** via ZFS RAID-Z2 — cryptographically verifiable,
   self-healing, and tolerant of two simultaneous drive failures.
2. **Run large-scale AI** — 70B parameter models via multi-GPU tensor parallelism, enabling
   the cooperative to offer AI services to its entire member network without cloud dependency.
3. **Provide ECC RAM protection** — Error-Correcting Code memory detects and corrects
   single-bit memory errors automatically, protecting long-running ZFS and database processes.
4. **Enable remote management** — IPMI/BMC out-of-band access lets any authorized cooperative
   member power cycle or access the server remotely, without physical presence.

This is the **infrastructure backbone of a cooperative federation** — think of it as the
digital equivalent of a collectively owned warehouse.

---

## Design Priorities

### ZFS RAID-Z2: Immutable Cooperative Ledger
The Federation Node runs **four 4TB enterprise SSDs** in a ZFS RAID-Z2 configuration. This means:
- Any **two drives can fail simultaneously** without data loss
- ZFS checksums every single block of data — silent corruption is detected and corrected
  automatically using the redundant drives
- **Snapshots** create point-in-time immutable copies of ledger data, making it
  cryptographically auditable: no record can be altered without leaving a trace

ZFS is the closest thing to **trustless storage** available on commodity hardware.

The HBA (Host Bus Adapter, T3-008) passes drives directly to ZFS in **IT mode** — no hardware
RAID controller stands between ZFS and the drives. ZFS must see raw drives to function correctly.
Hardware RAID hides drive health from ZFS and undermines its integrity guarantees.

### ECC RAM: Protection for Long-Running Processes
Consumer RAM silently flips bits due to cosmic ray interference and electrical noise. Over weeks
or months of continuous operation, this can corrupt database indices, ZFS metadata, or
cryptographic keys without any visible error.

**ECC RDIMM RAM** (T3-003) detects and corrects single-bit errors in real time. At Federation
scale — where the node runs continuously for months — ECC is not optional. It is the difference
between a trustworthy cooperative ledger and one that silently drifts.

### Multi-GPU: Serving 50+ Members
A single RTX 3090 24GB (T3-004) can run LLaMA-70B at 4-bit quantization, serving the entire
cooperative with a capable AI assistant. The second GPU slot (T3-005) enables:
- **Parallel inference** for multiple simultaneous member requests
- **Dedicated model loading** — one GPU for conversation models, one for code/image tasks
- **Future RISC-V/open-silicon expansion** as open GPU alternatives mature

### IPMI / BMC Remote Management
Supermicro's IPMI (Intelligent Platform Management Interface) gives cooperatives:
- Remote power on/off/reset via a web browser or API
- Serial console access (even before the OS loads)
- Hardware sensor monitoring (CPU temp, fan speeds, power draw) without OS dependency

This is critical for cooperatives whose Federation Node is hosted remotely — no one needs
to physically visit the server room for routine management.

---

## Component Rationale

| Component | Why This Choice |
|---|---|
| AMD EPYC 7003 (Milan) | 128 PCIe 4.0 lanes. Supports ECC RDIMM. Excellent single-thread + multi-core balance. |
| Supermicro H12SSL-i | EPYC SP3 socket. IPMI/BMC. 8 DIMM slots. Enterprise-grade refurb availability. |
| 128GB ECC RDIMM | ZFS ARC cache + AI inference + OS services. ECC mandatory for ledger integrity. |
| RTX 3090 24GB | 24GB VRAM runs LLaMA-70B Q4. Widely available refurbished. Strong CUDA ecosystem. |
| 4x 4TB Enterprise SSD | RAID-Z2 usable ~8TB. High endurance. Silent. Low power vs. spinning HDD. |
| LSI 9300-8i (IT mode) | Passthrough HBA. ZFS sees raw drives. Essential for ZFS integrity guarantees. |
| Redundant 1200W PSU | Hot-swap replacement without downtime. Platinum efficiency under sustained GPU load. |
| Intel X540-T2 10GbE | 10Gbps inter-node traffic. Dual-port bonding for failover. Excellent Linux support. |
| TPM 2.0 (Server-grade) | Buy new only. Federation holds highest-value key material. |
| INA3221 x2 | Per-GPU power rail monitoring + wall/UPS monitoring. Full power telemetry. |
| 1500VA+ Pure Sine UPS | ~8 minutes at 900W. Sufficient for ZFS snapshot commit + clean shutdown. |

---

## Right to Repair Notes

- **Supermicro** publishes full schematics, BIOS source, and replacement part numbers.
  No black-box firmware. BMC firmware is open-source (OpenBMC compatible).
- **LSI/Broadcom HBAs** have published IT mode firmware flashing guides. The flashing process
  is documented in `assembly_guides/`.
- Internal QR code labels (T3-017) should be affixed next to **every** component bay.
  At Federation scale, many different cooperative members may perform maintenance over the
  server's lifetime — QR codes ensure any member can identify and source replacement parts.
- All drives use standard **U.2 or SATA** interfaces. No proprietary connectors.

---

## Estimated Power Draw

| State | Draw |
|---|---|
| Idle (no GPU load) | ~120–180W |
| Active (single GPU inference) | ~400–500W |
| Peak (dual GPU + NVMe array) | ~700–800W |

A 1500VA / 900W UPS provides ~8–10 minutes at peak load — calibrated for a clean ZFS
checkpoint, snapshot commit, and graceful OS shutdown before battery exhaustion.

---

## Scaling Beyond One Node

Multiple Federation Nodes interconnect via the 10GbE managed switch (T3-012) into a
**cooperative federation mesh**. Each node holds a shard of the shared IPFS content
store and a replica of the ZFS ledger snapshot. Iskander OS's federation daemon manages
consensus across nodes using CRDT (Conflict-free Replicated Data Types) — no single node
is a point of failure for the cooperative's data.
