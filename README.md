# Project Iskander

**Sovereign AI Operating System for Cooperative Autonomy**

[![License: AGPL-3.0-only](https://img.shields.io/badge/License-AGPL--3.0--only-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Hardware: CERN-OHL-S v2](https://img.shields.io/badge/Hardware-CERN--OHL--S%20v2-orange.svg)](https://ohwr.org/cern_ohl_s_v2.txt)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg)](https://python.org)
[![Solidity 0.8.24](https://img.shields.io/badge/Solidity-0.8.24-363636.svg)](https://soliditylang.org)
[![Gnosis Chain](https://img.shields.io/badge/Chain-Gnosis-3e6957.svg)](https://www.gnosis.io)

---

## Overview

Cooperatives and platform co-ops face a structural dilemma: the digital tools they depend on are built by and for extractive business models. Cloud platforms centralise data, SaaS vendors capture value, and off-the-shelf governance software assumes hierarchical command structures that contradict cooperative principles. The result is cooperatives running their democratic organisations on autocratic infrastructure.

Project Iskander is a sovereign agentic AI operating system purpose-built for Distributed Cooperatives (DisCOs) and Platform Co-ops. It combines AI-assisted decision-making with mandatory transparency (the Glass Box Protocol), blockchain-anchored governance on Gnosis Chain, federated mesh storage via IPFS, energy-aware hardware scheduling, and anti-extractive economics -- all aligned to the ICA Cooperative Principles. Every agent action carries a structured rationale with an ethical impact assessment; no black-box decisions are permitted by design.

Iskander ships as a complete stack: smart contracts for on-chain governance, a Python backend with 13+ LangGraph agent graphs, a Next.js frontend, and open hardware specifications (Iskander Hearth) so cooperatives can build, own, and repair their own physical infrastructure. The genesis boot sequence enforces identity-first, governance-second initialisation with regulatory floor compliance, ensuring that every cooperative starts from a legally and ethically sound foundation.

---

## Architecture

```
+-------------------------------------------------------------------+
|                     ISKANDER SOVEREIGN NODE                       |
+-------------------------------------------------------------------+
|  +--------------+  +--------------+  +----------------------+     |
|  |   Frontend   |  |   FastAPI    |  |  LangGraph Agents    |     |
|  |  (Next.js)   |--|  27+ Routers |--|  13+ StateGraphs     |     |
|  +--------------+  +------+-------+  +----------+-----------+     |
|                           |                      |                |
|  +------------------------+----------------------+-------------+  |
|  |               Glass Box Protocol Layer                      |  |
|  |  AgentAction(agent_id, action, rationale, ethical_impact)   |  |
|  +----------------------------+--------------------------------+  |
|                               |                                   |
|  +----------+  +---------+   |   +------------+  +------------+  |
|  |PostgreSQL|  | pgvector|   |   |    IPFS    |  |  Gnosis    |  |
|  | 30+ tbl  |  |   RAG   |   |   |Mesh Archive|  |  Chain     |  |
|  +----------+  +---------+   |   +------------+  +------------+  |
|                               |                                   |
|  +----------------------------+--------------------------------+  |
|  |             Energy Gate (Hearth Driver)                      |  |
|  |    @energy_gated_execution -> GREEN / YELLOW / RED policies |  |
|  +-------------------------------------------------------------+  |
+-------------------------------------------------------------------+
```

The architecture is layered around a single principle: **every action must be transparent and reversible by collective decision**. The Glass Box Protocol sits between the API surface and all data stores, ensuring that no agent can write to the database, blockchain, or mesh without emitting a structured rationale. The Energy Gate at the bottom enforces hardware-aware scheduling, gracefully degrading non-essential services when power budgets tighten.

---

## Key Subsystems

| Subsystem | Description | Key Files / Contracts |
|---|---|---|
| **Glass Box Protocol** | Mandatory transparency layer; every agent action includes rationale and ethical impact level | `backend/core/` |
| **Governance Orchestrator** | LangGraph agent coordinating proposals, consent rounds, and delegation | `backend/agents/governance_agent.py` |
| **Genesis Boot Sequence** | One-way cooperative initialisation: identity first, governance second, with HITL breakpoints | `backend/agents/genesis/` |
| **PolicyEngine** | ICA compliance gate; hardcoded principles that cannot be overridden at runtime | `backend/core/` |
| **Smart Contracts** | 10 Solidity contracts on Gnosis Chain (SBT identity, MACI voting, escrow, payroll, etc.) | `contracts/src/` |
| **Mesh Archive** | Federated IPFS storage with SBT-gated access control and content addressing | `backend/mesh/` |
| **Energy Scheduler** | Tri-state GREEN/YELLOW/RED execution policies driven by Hearth hardware sensors | `backend/energy/` |
| **Fiat Bridge** | Anti-extractive cFIAT token (ERC-20) backed 1:1 by cooperative bank deposits | `contracts/src/finance/CoopFiatToken.sol` |
| **Federation / Diplomacy** | Cross-cooperative trust scoring, foreign reputation, and inter-coop escrow | `backend/federation/`, `backend/diplomacy/` |
| **Stewardship** | Liquid delegation, Impact Scores, and stewardship council management | `backend/governance/`, `contracts/src/governance/StewardshipLedger.sol` |

---

## Monorepo Structure

```
iskander/
+-- README.md                          # This file
+-- ISKANDER_IMPLEMENTATION_SPEC.md    # Full machine-readable specification
+-- ISKANDER_HARDENING_PLAN.md         # Security hardening roadmap
+-- docs/                              # Design specs and working documents
+-- tests/                             # Integration / cross-cutting tests
+-- src/
    +-- IskanderOS/                    # Software (AGPL-3.0-only)
    |   +-- backend/
    |   |   +-- agents/                # LangGraph StateGraph agents
    |   |   |   +-- genesis/           # Genesis boot sequence nodes
    |   |   |   +-- core/              # Agent base classes, queue, registry
    |   |   |   +-- library/           # Shared agent utilities
    |   |   |   +-- research/          # RITL and curator agents
    |   |   |   +-- spawner/           # Cooperative spawner agent
    |   |   +-- routers/               # 27+ FastAPI route modules
    |   |   +-- core/                  # PolicyEngine, Glass Box, config
    |   |   +-- governance/            # Governance models and logic
    |   |   +-- federation/            # Inter-cooperative federation
    |   |   +-- diplomacy/             # Cross-federation diplomacy
    |   |   +-- energy/                # Energy-aware scheduling
    |   |   +-- mesh/                  # IPFS mesh archive
    |   |   +-- finance/               # Treasury, credits, fiat bridge
    |   |   +-- auth/                  # SIWE + JWT authentication
    |   |   +-- schemas/               # Pydantic v2 models
    |   |   +-- main.py                # FastAPI application entry point
    |   |   +-- requirements.txt
    |   +-- contracts/                 # Solidity 0.8.24 (Foundry)
    |   |   +-- src/                   # Contract sources
    |   |   |   +-- CoopIdentity.sol   # ERC-4973 Soulbound Token
    |   |   |   +-- Constitution.sol   # Immutable genesis anchor
    |   |   |   +-- InternalPayroll.sol# Mondragon 6:1 pay ratio cap
    |   |   |   +-- IskanderEscrow.sol # Inter-coop escrow + disputes
    |   |   |   +-- ArbitrationRegistry.sol
    |   |   |   +-- governance/        # MACIVoting, StewardshipLedger, etc.
    |   |   |   +-- finance/           # CoopFiatToken (ERC-20)
    |   |   +-- test/                  # Foundry tests
    |   |   +-- script/                # Deployment scripts
    |   +-- frontend-next/             # Next.js 14 + Wagmi frontend
    |   +-- infra/                     # Docker Compose, Dendrite config, SQL
    |   +-- os_build/                  # Ubuntu 24.04 custom ISO build
    |   +-- tests/                     # Backend test suite
    +-- IskanderHearth/                # Open hardware (CERN-OHL-S v2)
        +-- boms/                      # Bills of Materials (3 tiers)
        +-- enclosures/                # OpenSCAD parametric chassis
        +-- pcb/                       # Solidarity Hat PCB designs
        +-- firmware/                  # Hardware controller firmware
        +-- thermal/                   # Thermal and acoustic test data
        +-- manufacturing/             # Production documentation
        +-- supply_chain/              # Material Passports, ethics guidelines
        +-- assembly_guides/           # Build and OS flashing instructions
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Language** | Python 3.12 | Backend and agents |
| **Web Framework** | FastAPI | Async, 27+ routers |
| **Agent Framework** | LangGraph | StateGraph-based, 13+ agent graphs |
| **Data Validation** | Pydantic v2 | Schemas and config |
| **Smart Contracts** | Solidity 0.8.24, Foundry | 10 contracts |
| **Blockchain** | Gnosis Chain | Low-cost, EVM-compatible |
| **Database** | PostgreSQL + pgvector | 30+ tables, RAG vector search |
| **Distributed Storage** | IPFS | Content-addressed mesh archive |
| **Frontend** | Next.js 14 + Wagmi | Wallet-connected UI |
| **Messaging** | Matrix (Dendrite) | Federated cooperative chat |
| **Auth** | SIWE + JWT | Sign-In with Ethereum |
| **Local LLM** | Ollama | On-node inference |
| **Caching** | Redis | Session and task queue |
| **Containerisation** | Docker Compose | 8 services |
| **OS Image** | Ubuntu 24.04 | Custom ISO for Hearth hardware |
| **Hardware License** | CERN-OHL-S v2 | Strongly reciprocal open hardware |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Node.js 18+ (for frontend)
- Foundry (`forge`, `cast`, `anvil`) for smart contract development

### Quick Start

```bash
# Clone the repository
git clone https://github.com/iskander-os/iskander.git
cd iskander/src/IskanderOS

# Copy environment template and configure
cp .env.example .env
# Edit .env with your settings (database credentials, RPC URL, etc.)

# Start all services
docker compose up -d

# The API will be available at http://localhost:8000
# The frontend at http://localhost:3000
```

### Smart Contract Development

```bash
cd src/IskanderOS/contracts

# Build contracts
forge build

# Run tests
forge test

# Deploy to local Anvil node (started by Docker Compose)
forge script script/Deploy.s.sol --rpc-url http://localhost:8545 --broadcast
```

### Backend Development

```bash
cd src/IskanderOS/backend

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Governance Model

Iskander's governance system is grounded in the **ICA Cooperative Principles** -- the seven internationally recognised principles defined by the International Co-operative Alliance:

| # | ICA Cooperative Principle | Iskander Implementation |
|---|---|---|
| 1 | **Voluntary and Open Membership** | Open registration via SIWE; BrightID sybil resistance; no gatekeeping beyond identity verification |
| 2 | **Democratic Member Control** | One-member-one-vote via MACIVoting (ZK-SNARK privacy); consent-based decision-making; liquid delegation via StewardshipLedger |
| 3 | **Member Economic Participation** | InternalPayroll enforces Mondragon-inspired 6:1 pay ratio cap; cooperative surplus distribution |
| 4 | **Autonomy and Independence** | Sovereign node architecture; no cloud dependency; self-hosted infrastructure on Hearth hardware |
| 5 | **Education, Training, and Information** | Knowledge Commons (IKC); Glass Box Protocol ensures all decisions are explainable |
| 6 | **Cooperation among Cooperatives** | Federation protocol; ForeignReputation cross-trust scoring; inter-coop escrow and arbitration |
| 7 | **Concern for Community** | Energy-aware scheduling; Material Passports for hardware; regulatory floor enforcement |

The **ICA Cooperative Values** -- self-help, self-responsibility, democracy, equality, equity, and solidarity -- are encoded as invariants in the PolicyEngine, which acts as an immutable compliance gate that no agent or user can bypass.

### Three-Tier Governance

Iskander enforces a strict governance hierarchy:

1. **Constitutional Core** -- The ICA Cooperative Principles and values. Immutable. Hardcoded in the PolicyEngine and anchored on-chain via the Constitution contract. Cannot be amended by any vote or agent action.

2. **Genesis Layer** -- Founding decisions made during the boot sequence: cooperative name, jurisdiction, founding members, initial roles, and governance parameters. Stored as on-chain CID hashes. Amendable only by supermajority constitutional amendment process.

3. **Operational Policy** -- Day-to-day rules, budgets, role assignments, and working agreements. Managed via the Governance Orchestrator agent. Amendable by standard consent process.

### Decision-Making

Governance draws on **Sociocracy 3.0** (S3) patterns and **Radical Routes** consensus practices:

- **Consent decision-making**: proposals pass unless there is a reasoned, paramount objection
- **Circle structure**: nested domains with clear authority boundaries
- **Liquid delegation**: members can delegate their vote to trusted stewards via the StewardshipLedger, revocable at any time
- **HITL breakpoints**: the genesis boot sequence and governance orchestrator include mandatory human-in-the-loop checkpoints for high-impact decisions

---

## Architecture Status

### Implemented

- 10 Solidity smart contracts with Foundry test suite
- 27+ FastAPI routers covering all major subsystems
- 13+ LangGraph StateGraph agents (governance, genesis, steward, secretary, treasurer, procurement, ICA vetter, IPD auditor, persona generator, curator network, RITL manager, model manager)
- Genesis boot sequence with 18 nodes, 3 HITL breakpoints, solo + cooperative paths
- PolicyEngine with ICA compliance gating
- Glass Box Protocol transparency layer
- AsyncAgentQueue for serialised LLM/graph execution
- Three-tier governance model (Constitutional / Genesis / Operational)
- Regulatory floor enforcement with jurisdiction templates (UNIVERSAL, GB, ES)
- Iskander Hearth hardware specifications (3 tiers, BOMs, enclosures, PCB designs)
- Docker Compose infrastructure (8 services)
- Database schema (30+ tables, PostgreSQL + pgvector)

### Stubbed or In Progress

- Frontend (Next.js 14 + Wagmi) -- scaffolded, not feature-complete
- Ubuntu 24.04 custom ISO build -- scripts present, not fully automated
- Matrix/Dendrite integration -- configuration present, agent integration partial
- BrightID sybil resistance -- router exists, verification flow stubbed
- Fiat bridge banking integration -- contract complete, bank API connector stubbed
- IPFS mesh archive -- data model complete, cross-node replication logic partial
- Cross-federation diplomacy -- models defined, protocol handshake in progress

### Known Gaps and Priorities

- End-to-end integration tests across the full genesis-to-operational lifecycle
- Production hardening (see `ISKANDER_HARDENING_PLAN.md`)
- Smart contract formal verification and audit
- Accessibility audit for frontend
- Additional jurisdiction templates beyond UNIVERSAL, GB, ES
- Hardware thermal validation under sustained GPU inference load

---

## License

| Component | License |
|---|---|
| **IskanderOS** (all software, contracts, backend, frontend) | [AGPL-3.0-only](https://www.gnu.org/licenses/agpl-3.0) |
| **IskanderHearth** (hardware designs, BOMs, enclosures, PCBs) | [CERN-OHL-S v2](https://ohwr.org/cern_ohl_s_v2.txt) |

The AGPL-3.0 ensures that any deployment of Iskander must share its source code, preventing proprietary forks from extracting cooperative value. The CERN-OHL-S v2 applies the same reciprocal principle to hardware: any derivative designs must remain open.

---

## References

- [Implementation Specification](./ISKANDER_IMPLEMENTATION_SPEC.md) -- Full machine-readable architecture spec with contract ABIs, database schemas, API surface, and cross-cutting invariants
- [Hardening Plan](./ISKANDER_HARDENING_PLAN.md) -- Security audit roadmap and production readiness checklist
- [Iskander Hearth README](./src/IskanderHearth/README.md) -- Open hardware companion: tiers, BOMs, assembly guides, and material passports
- [ICA Cooperative Principles](https://www.ica.coop/en/cooperatives/cooperative-identity) -- International Co-operative Alliance statement on cooperative identity
- [Sociocracy 3.0 Practical Guide](https://sociocracy30.org) -- Governance patterns used in Iskander's decision-making model
- [Radical Routes](https://www.radicalroutes.org.uk) -- Consensus practices informing cooperative governance design
