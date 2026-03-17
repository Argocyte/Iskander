# Iskander Hearth

**Open Hardware for Sovereign Cooperatives**

Iskander Hearth is the official open-source hardware companion to [Iskander OS](https://github.com/iskander-os). It defines the physical servers that cooperatives build, repair, and maintain — without vendor lock-in, black-box appliances, or cloud dependency.

## License

All hardware designs, BOMs, and documentation in this repository are released under the
**CERN Open Hardware Licence Version 2 – Strongly Reciprocal (CERN-OHL-S v2)**.
See [`LICENSE`](./LICENSE) for the full text.

## Principles

| Principle | Inspiration | Implementation |
|---|---|---|
| Right to Repair | Framework Laptop | Standardized ATX/ITX components, open fasteners, internal QR codes |
| Circular Economy | Fairphone | Refurbished enterprise gear, public Material Passports |
| Local AI + Crypto Security | Start9 | High-VRAM GPUs + TPM 2.0 for air-gapped Web3 keys |
| Permacomputing | Solar Protocol | Hardware power sensors → OS Graceful Degradation daemons |

## Tiers

| Tier | Scale | Form Factor | Primary Use |
|---|---|---|---|
| [Tier 1 – Seed](./boms/tier1_seed.md) | 1–10 members | Refurbished 1L / N100 Mini PC | Entry node, solar-ready, UPS-aware |
| [Tier 2 – Commons](./boms/tier2_commons.md) | 10–50 members | Mini-ITX custom build | LLM inference, TPM key storage, Ad-Hoc hotspot |
| [Tier 3 – Federation](./boms/tier3_federation.md) | 50+ members | 2U Rack / ATX Tower | ZFS ledger storage, ECC RAM, multi-GPU |

## Repository Structure

```
iskander-hearth/
├── boms/               # Bills of Materials (CSV + Markdown explainers)
├── enclosures/         # OpenSCAD parametric chassis designs
├── supply_chain/       # Material Passports, procurement ethics guidelines
└── assembly_guides/    # Step-by-step build and OS flashing instructions
```

## Pragmatic Hardware Note

We advocate for fully open silicon (RISC-V, POWER). In practice, achieving the AI inference
performance Iskander's cooperative agents require today demands x86/ARM CPUs and refurbished
NVIDIA/AMD GPUs. We use these pragmatically while tracking and minimising their supply chain
harms via Material Passports. As open silicon matures, this BOM will evolve.

## Contributing

Read [`CONTRIBUTING.md`](./CONTRIBUTING.md). All hardware changes must include updated BOMs
and, where applicable, updated Material Passport entries.
