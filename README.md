# Iskander

**Lunarpunk Cooperative Infrastructure -- federated, private, self-hosted. Web3 in the hands of people who otherwise wouldn't touch it, in a decision-making environment that just works.**

[![License: AGPL-3.0-only](https://img.shields.io/badge/License-AGPL--3.0--only-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Solidity 0.8.24](https://img.shields.io/badge/Solidity-0.8.24-363636.svg)](https://soliditylang.org)

---

## What Is Iskander?

Iskander is a self-hosted cooperative platform that federates across groups, enforces democratic governance, and uses cryptography only where it solves problems no other technology can. Generous tit-for-tat game theory creates emergent cooperative behaviours that outcompete extractive capitalism.

Run it once and your cooperative gets:

- **Loomio** -- democratic decision-making (proposals, votes, discussions, STV elections)
- **Mattermost** -- real-time team chat, bridged to governance via the AI Clerk
- **AI Agent System** -- five specialised agents: Clerk (governance assistant), Steward (treasury monitor), Sentry (infrastructure health), Wellbeing (name changes and member dignity), Librarian (document search)
- **Nextcloud** -- shared files, calendar, contacts, email
- **Glass Box** -- every AI action is transparent and auditable by any member
- **Treasury monitoring** -- an AI Steward watches the cooperative's wallet and creates proposals for significant spending
- **Vaultwarden** -- shared credential and password management for the cooperative
- **Backrest** -- automated backups with Restic, managed through a clean UI
- **Beszel** -- lightweight system monitoring (replaces heavyweight Grafana + Prometheus stacks)
- **Single Sign-On** -- one account (via Authentik) accesses everything
- **Cloudflare Tunnel** -- public access with zero open ports
- **Headscale** -- mesh networking for inter-cooperative federation
- **Blockchain anchoring** -- decisions recorded on-chain with IPFS hashes for tamper-proof history
- **Zero-knowledge voting** -- MACI secret ballots where individual votes are never disclosed
- **Federation** -- cooperatives discover and communicate with each other over WireGuard mesh

All of this is aligned to the **ICA Cooperative Principles** -- the seven internationally recognised principles defined by the International Co-operative Alliance. The AI agents embody the six core cooperative values (self-help, self-responsibility, democracy, equality, equity, solidarity) and four ethical values (honesty, openness, social responsibility, caring for others).

---

## Privacy Model: Lunarpunk Selective Disclosure

Iskander follows a lunarpunk privacy architecture with three distinct layers:

- **Glass Box (internal)** -- aggregate outcomes, proposal results, treasury movements, and AI audit trails are visible to all members. Full transparency within the cooperative.
- **ZK-Private Voting** -- individual votes are never disclosed. MACI zero-knowledge proofs guarantee anti-coercion: even under duress, no one can prove how they voted.
- **Opaque Externally** -- the cooperative presents a unified face to the outside world. Internal deliberations, member identities, and governance processes are not exposed to non-members.

---

## Why Web3? Five Problems Only Cryptography Solves

Iskander does not use blockchain for its own sake. Every web3 component addresses a specific problem that cannot be solved with conventional infrastructure:

| Problem | Solution | Why No Alternative Exists |
|---------|----------|--------------------------|
| Tamper-evident decision records | IPFS content hashes + on-chain anchoring | No central admin can silently alter the historical record |
| Anti-coercion voting | MACI zero-knowledge proofs | Voters cannot be forced to prove how they voted, even to themselves |
| Sybil-resistant identity | Soulbound Tokens (ERC-4973) + BrightID | One-member-one-vote without trusting a central identity provider |
| Inter-cooperative trust without intermediaries | On-chain escrow + reputation + arbitration | Cooperatives transact directly; no platform extracts rent |
| Anti-extractive finance | cFIAT tokens, pay ratio enforcement | Treasury rules are code -- no board can override them unilaterally |

Everything else runs on proven, boring technology.

---

## Architecture

```
                   +-------------------------------+
                   |     Authentik (SSO / OIDC)     |
                   |    One login for everything    |
                   +----+------+------+------+------+
                        |      |      |      |
         +--------------+  +---+---+  |  +---+-----------+
         |  Loomio          |Matter|  |  | Nextcloud     |
         |  Governance      |most  |  |  | Files, Cal,   |
         |  Proposals,      |Chat  |  |  | Contacts      |
         |  Votes           |      |  |  +---------------+
         +-------+----------+--+---+  |
                 |              |      |
       OpenClaw (Clerk, Steward, Sentry, Wellbeing, Librarian)
                 |              |
      +----------+----------+  |
      |                     |  |
 Ollama (LLM)    Decision Recorder
                  (PostgreSQL + IPFS)
                                |
  +-----------------------------+-----------------------------+
  |              |              |             |               |
Vaultwarden  Backrest       Beszel      Cloudflared     Headscale
Credentials  Backups       Monitoring   Tunnel          Mesh VPN
```

All services run on **K3s** -- a single 40MB binary that replaces Docker Compose with production-grade Kubernetes orchestration. Native multi-node support means federation and horizontal scaling require no architectural changes.

### Services (Phase C -- 17 services, ~7.2GB RAM minimum, 16GB recommended)

| Service | Purpose | Footprint |
|---------|---------|-----------|
| K3s | Lightweight Kubernetes orchestration | ~40MB |
| PostgreSQL 16 | Shared database (Loomio, Nextcloud, Authentik, Mattermost, decisions) | ~256MB |
| Redis | Session store and job queue | ~50MB |
| Authentik | OAuth2/OIDC identity provider -- SSO for all services | ~500MB |
| Loomio | Democratic decision-making (proposals, votes, STV elections) | ~512MB |
| Mattermost | Real-time team chat, AI agent bridge | ~300MB |
| Nextcloud | File hosting, calendar, contacts, email client | ~512MB |
| Ollama | Local LLM inference (Phi-3-mini or OLMo) | ~2GB |
| OpenClaw | AI agent orchestrator (5 agents: Clerk, Steward, Sentry, Wellbeing, Librarian) | ~256MB |
| Decision Recorder | Loomio webhook capture, IPFS pinning, Glass Box audit trail | ~128MB |
| Provisioner | Member onboarding orchestrator (Authentik → Loomio → Mattermost) | ~128MB |
| IPFS Kubo | Decision record pinning for tamper-proof history | ~256MB |
| Vaultwarden | Bitwarden-compatible shared credential management | ~50MB |
| Backrest | Backup management with Restic backend | ~50MB |
| Beszel | Lightweight system monitoring and alerting | ~50MB |
| Cloudflared | Cloudflare Tunnel -- public access, zero open ports | ~50MB |
| Headscale | Self-hosted Tailscale control server for mesh federation | ~50MB |

### Phase B Expansion (Weeks 4-8)

Adds four more services, bringing the total to 19:

| Service | Purpose |
|---------|---------|
| Anvil | Local EVM node for smart contract interaction |
| Chain Bridge | Connects local contracts to L2 mainnet |
| Stalwart | Self-hosted email server |
| Caddy | Public cooperative website with automatic TLS |

---

## AI Agent System

Five specialised agents run in OpenClaw, each with a distinct mandate and domain boundary. All write actions go through the Glass Box -- any member can see the full audit trail.

### @clerk — Governance Secretary
Every member's governance assistant. Operates in Loomio and Mattermost.
- Drafts and revises proposals (Advice, Consent, Consensus process)
- Summarises discussions and archives decisions to Nextcloud
- Tracks action items, reviews, and tensions (S3: Navigate Via Tension)
- Prepares AGM and circle meeting agenda packs
- Runs governance health assessments (block rate, review debt, tension backlog)
- Never votes, never advocates for any position

### @steward — Treasury Monitor
Watches the cooperative's wallet and governance records.
- Monitors treasury thresholds and flags significant movements
- Drafts Loomio proposals when thresholds are crossed
- Posts treasury summaries to governance channel

### @sentry — Infrastructure Health Interpreter
Translates system health into cooperative language.
- Reads Beszel metrics and surface issues as actionable member updates
- Categorises alerts by severity and impact on cooperative operations

### @wellbeing — Member Dignity Agent
Handles dignity-critical operations. Separate from the Clerk by design.
- Platform-wide name changes: Authentik → Provisioner → Mattermost/Loomio redaction
- Old names are never logged, echoed, or surfaced -- Glass Box uses `[REDACTED]`
- Opt-in group notification; never mentions the old name

### @librarian — Knowledge Steward
Read-only access to the cooperative's documents and governance pattern library.
- Searches Nextcloud by file name and content
- Retrieves and summarises document text
- Searches the S3 governance pattern commons

---

## Key Influences

Iskander builds on the intellectual foundation of four projects that prove cooperative technology works:

- **DisCO** (Distributed Cooperative Organizations) -- feminist economics, care work valuation, pro-bono tracking. Iskander adopts DisCO's insistence that invisible labour be made visible and valued.
- **Hypha DAO 3.0** -- human-centered governance tooling. Hypha proved that DAOs can serve real organizations, not just token holders.
- **ICN** (Inter-Cooperative Network) -- trust-native federation between cooperatives. ICN's model of mutual aid without intermediaries directly informs Iskander's Headscale mesh.
- **DarkFi** -- lunarpunk privacy philosophy. The principle that privacy is not optional but foundational shapes Iskander's selective disclosure model.

---

## ICA Cooperative Principles

Every aspect of Iskander is designed around the seven cooperative principles:

| # | Principle | How Iskander Implements It |
|---|-----------|--------------------------|
| 1 | Voluntary and Open Membership | SSO onboarding, Clerk-guided welcome sequence, membership lifecycle |
| 2 | Democratic Member Control | Loomio voting (Consent, Consensus, STV elections), 1-member-1-vote via BrightID + MACI ZK proofs |
| 3 | Member Economic Participation | Treasury monitoring, member shares, surplus distribution, asset-lock enforcement, cFIAT tokens |
| 4 | Autonomy and Independence | Fully self-hosted on K3s, no cloud dependencies, cooperative owns all infrastructure |
| 5 | Education, Training, Information | Clerk-guided onboarding, values reflection, Librarian agent (Nextcloud document search + governance pattern commons) |
| 6 | Cooperation among Cooperatives | Headscale mesh federation, cooperative discovery protocol, shared governance pattern library |
| 7 | Concern for Community | SDG tracking, sustainability reporting, energy-aware scheduling |

---

## Repository Structure

```
iskander/
+-- README.md
+-- docs/
|   +-- ROADMAP.md                  # Phased project roadmap
|   +-- OVERVIEW.md                 # Non-technical overview for members
|   +-- PLAN.md                     # Detailed technical plan (Route C -> B)
|   +-- superpowers/specs/          # Agent and feature design specs
|   +-- archive/                    # Archived design specs (.odt, .txt)
+-- infra/
|   +-- helm/iskander/              # Helm chart (all Phase C services)
|   +-- ansible/                    # Installation playbooks
+-- install/                        # curl|sh installer entry point
+-- verify/                         # End-to-end smoke test scripts
+-- skills/                         # Claude Code skill plugins
+-- src/
    +-- IskanderOS/
    |   +-- openclaw/               # AI agent orchestrator (OpenClaw)
    |   |   +-- main.py             # FastAPI server, webhook routing
    |   |   +-- requirements.txt
    |   |   +-- governance_patterns.yaml  # S3 pattern library
    |   |   +-- agents/
    |   |   |   +-- orchestrator/   # Agent coordinator
    |   |   |   +-- clerk/          # Governance secretary (@clerk)
    |   |   |   +-- steward/        # Treasury monitor (@steward)
    |   |   |   +-- sentry/         # Infrastructure health (@sentry)
    |   |   |   +-- wellbeing/      # Member dignity agent (@wellbeing)
    |   |   |   +-- librarian/      # Knowledge steward (@librarian)
    |   |   +-- skills/
    |   |       +-- loomio-bridge/  # Loomio API integration
    |   |       +-- document-collab/# AI-assisted document drafting
    |   |       +-- values-reflection/
    |   |       +-- glass-box/      # Audit trail
    |   |       +-- treasury-monitor/
    |   |       +-- membership/     # Join/leave/onboard
    |   +-- services/
    |   |   +-- decision-recorder/  # Loomio webhook + IPFS + Glass Box (FastAPI)
    |   |   +-- provisioner/        # Member onboarding orchestrator (FastAPI)
    |   |   +-- authentik/          # SSO identity provider config
    |   |   +-- loomio/             # Governance platform config
    |   |   +-- nextcloud/          # Files, calendar, email config
    |   |   +-- website/            # Public cooperative website
    |   +-- contracts/              # Solidity smart contracts (Phase B)
    |   |   +-- src/
    |   |       +-- Constitution.sol
    |   |       +-- CoopIdentity.sol    # ERC-4973 Soulbound Tokens
    |   |       +-- governance/
    |   |           +-- MACIVoting.sol  # ZK secret ballot voting
    |   +-- docs/                   # ICA reference documents
    |   +-- legacy/                 # Archived: previous backend, frontend, agents
    +-- IskanderHearth/             # Open hardware (CERN-OHL-S v2)
```

---

## Getting Started

### Prerequisites

- A Linux machine (Ubuntu 24.04 recommended, any systemd-based distro works)
- 16GB RAM recommended (7.2GB minimum)
- A domain name (optional but recommended for Cloudflare Tunnel)

### Installation

```bash
curl -sfL https://get.iskander.coop | sh
```

That single command runs an Ansible playbook underneath that:

1. Installs K3s (single 40MB binary -- no Docker required)
2. Deploys all 17 Phase C services
3. Configures SSO across Loomio, Mattermost, Nextcloud, and Vaultwarden
4. Launches the first-boot wizard

The wizard will ask for:
1. Your cooperative's name
2. Founding members (name + email)
3. Optional: your domain name for Cloudflare Tunnel

Then it starts all services, creates accounts, and opens your browser. Your cooperative is ready.

The experience is modelled on Tailscale: one command, no prerequisites, works everywhere.

---

## Development Status

Iskander is in active development following the **Route C to B** plan:

- **Phase C (Weeks 1-3)**: Radical MVP -- 17 services: K3s + Loomio + Mattermost + Nextcloud + SSO + Glass Box + Decision Recorder + Provisioner + OpenClaw (5 agents) + Vaultwarden + Backrest + Beszel + Cloudflared + Headscale + IPFS + Ollama. Phase C is complete.
- **Phase B (Weeks 4-8)**: Expansion -- blockchain (Anvil + Chain Bridge), ZK voting, governance contracts, email (Stalwart), website (Caddy), bringing total to 21 services

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full phased roadmap.

---

## Security

Iskander is designed for deployment on the open internet with a zero-open-ports model:

- All public traffic routed through Cloudflare Tunnel (no exposed ports)
- Inter-cooperative federation over Headscale WireGuard mesh (encrypted, authenticated)
- TLS everywhere within the cluster
- Authentik SSO with MFA support
- Internal-only networking for databases
- Non-root containers with dropped capabilities
- Automated backups via Backrest + Restic
- System monitoring via Beszel with alerting
- Shared credentials managed in Vaultwarden (never in plaintext)

See the [Security Hardening](docs/PLAN.md#security-hardening-production-on-the-open-web) section of the plan for full details.

---

## License

| Component | License |
|-----------|---------|
| **IskanderOS** (software, contracts) | [AGPL-3.0-only](https://www.gnu.org/licenses/agpl-3.0) |
| **IskanderHearth** (hardware) | [CERN-OHL-S v2](https://ohwr.org/cern_ohl_s_v2.txt) |

The AGPL-3.0 ensures that any deployment must share its source code, preventing proprietary forks from extracting cooperative value.

---

## References

- [ICA Cooperative Identity](https://www.ica.coop/en/cooperatives/cooperative-identity) -- Definition, values, and principles
- [ICA Guidance Notes](src/IskanderOS/docs/ica-guidance-notes-index.md) -- Detailed interpretation of principles (project-local)
- [Co-ops for 2030](src/IskanderOS/docs/coops-for-2030-report.md) -- Cooperatives and UN SDGs (project-local)
- [Sociocracy 3.0](https://sociocracy30.org) -- Governance patterns
- [DisCO](https://disco.coop) -- Distributed Cooperative Organizations, feminist economics
- [Hypha DAO](https://hypha.earth) -- Human-centered governance tooling
- [DarkFi](https://dark.fi) -- Lunarpunk philosophy and anonymous infrastructure
- [Loomio](https://www.loomio.com) -- Decision-making platform
- [Mattermost](https://mattermost.com) -- Open-source team chat
- [OpenClaw](src/IskanderOS/openclaw/) -- AI agent orchestrator (project-local)
- [K3s](https://k3s.io) -- Lightweight Kubernetes
