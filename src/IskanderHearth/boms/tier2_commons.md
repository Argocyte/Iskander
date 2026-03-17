# Tier 2 – Commons Node

**Scale:** 10–50 cooperative members
**Form Factor:** Custom Mini-ITX build
**BOM:** [`tier2_commons.csv`](./tier2_commons.csv)
**Estimated Total Cost:** ~$960–$1,150 USD (mix of new + refurbished GPU)

---

## What Is This?

The Commons Node is **the workhorse of an active cooperative**. It is a purpose-built Mini-ITX
computer that does three things exceptionally well:

1. **Runs local AI** — 7B to 13B parameter language models (Mistral, LLaMA, Phi) entirely on
   the cooperative's hardware, with no data sent to OpenAI, Google, or any external service.
2. **Secures Web3 keys** — A hardware TPM 2.0 chip stores encrypted key shards for the
   cooperative's Web3 Safe multi-signature wallet, air-gapped from the OS.
3. **Broadcasts a setup hotspot** — On first boot, the node advertises a Wi-Fi network called
   `Iskander_Hearth_Setup` so any cooperative member can join and complete onboarding from
   a phone or laptop, without needing to plug in a monitor.

This tier is designed to feel like **assembling high-quality Lego** — standard parts, clear
documentation, and nothing that requires a professional technician.

---

## Design Priorities

### Local AI Inference: 12GB VRAM Minimum
The **NVIDIA RTX 3060 12GB** is the minimum GPU for meaningful cooperative AI work. With 12GB
of VRAM, it can run:
- Mistral-7B (full precision) or LLaMA-13B (4-bit quantized)
- Whisper large-v3 for local speech-to-text
- Stable Diffusion XL for cooperative media generation

The **AMD RX 6700 XT 12GB** is an acceptable alternative — it costs slightly less refurbished
and uses ROCm for GPU compute. NVIDIA is currently preferred for wider llama.cpp/Ollama
compatibility, but AMD support is improving rapidly.

**Why not cloud?** Because cooperative data — member communications, financial records,
governance votes — should never leave the cooperative's physical control. Local inference
is the only way to guarantee this.

### TPM 2.0: Web3 Key Security
The **Infineon SLB9665 TPM 2.0 module** plugs into the motherboard's TPM header. Iskander OS
uses it to:
- Store encrypted shards of the cooperative's Web3 Safe multi-sig private keys
- Require physical presence (the specific hardware) to decrypt key material
- Prevent key extraction even if the OS is compromised, because the TPM's secure enclave
  operates independently of the CPU

This means a remote attacker who breaks into the OS cannot steal the cooperative's treasury keys.
The keys are bound to the physical hardware.

### Ad-Hoc Setup Hotspot
The **Intel AX210** Wi-Fi card supports **AP (Access Point) mode** via `hostapd`. On first boot,
Iskander OS broadcasts:
- SSID: `Iskander_Hearth_Setup`
- Password: printed on the physical setup card included in the assembly guide

New members connect to this network from any device, open a browser, and complete the
cooperative onboarding wizard. No monitor, keyboard, or technical knowledge required.
This is directly inspired by DappNode's setup flow.

---

## Component Rationale

| Component | Why This Choice |
|---|---|
| Ryzen 5 7600 (AM5) | 6-core, 65W TDP. AM5 platform has long roadmap. Fast PCIe 4.0 for GPU/NVMe. |
| ASRock B650M-ITX/ax | TPM header, M.2 A+E Wi-Fi slot, dual NVMe. Best Mini-ITX feature set at price. |
| 32GB DDR5 | GPU handles models; RAM handles OS + multiple services running simultaneously. |
| RTX 3060 12GB | 12GB VRAM sweet spot. Widely available refurbished. Full CUDA support for llama.cpp. |
| 1TB NVMe (PCIe 4.0) | Fast model loading. Quantized 7B model = ~4GB; 13B = ~8GB. Multiple models fit. |
| 2TB SATA SSD | Cooperative data, IPFS node, encrypted backups. Enterprise refurb preferred. |
| SFX PSU 650W Gold | Efficient. Right-sized for GPU peak draw. SFX fits Mini-ITX chassis. |
| Intel AX210 | AP mode for setup hotspot. Wi-Fi 6E for fast cooperative mesh when needed. |
| TPM 2.0 (Infineon) | Hardware key enclave. Non-negotiable for Web3 treasury security. |
| INA3221 (3-channel) | Monitors wall / UPS / system draw simultaneously. Feeds Graceful Degradation. |
| CyberPower 850VA UPS | Pure sine wave. Covers GPU power spikes. NUT-compatible for OS integration. |

---

## Right to Repair Notes

- **Standard Mini-ITX form factor** means every component is replaceable with off-the-shelf parts.
- **No soldered RAM or storage** — unlike laptops, all components are socketed.
- GPU, RAM, NVMe, and PSU can all be swapped in under 10 minutes with a Phillips #2 screwdriver.
- Phase 2 of Iskander Hearth defines a **custom OpenSCAD chassis** with embossed QR code surfaces
  next to each major component bay, linking directly to the repair guide for that part.
- Until the custom chassis is built, use a **Fractal Design Node 304** or **Silverstone SG13**
  with 3D-printed QR code holders adhered to internal surfaces.

---

## Estimated Power Draw

| State | Draw |
|---|---|
| Idle (GPU idle) | ~45–60W |
| Active AI inference (GPU loaded) | ~220–260W |
| Peak (GPU + NVMe burst) | ~280W |

An 850VA / 510W UPS provides ~8–10 minutes runtime at inference load — sufficient for clean
ZFS snapshots and shutdown sequence on power failure.

---

## Upgrade Path

When a cooperative grows beyond 50 members, or requires ZFS RAID storage and ECC RAM for
ledger integrity, move to **Tier 3 – Federation**.

The Tier 2 GPU (RTX 3060) can be **repurposed** in the Federation build as a secondary
inference card.
