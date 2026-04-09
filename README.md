# Iskander

**A cooperative-in-a-box: one boot gives your cooperative decisions, files, AI assistance, and a web presence -- all behind single sign-on.**

[![License: AGPL-3.0-only](https://img.shields.io/badge/License-AGPL--3.0--only-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Solidity 0.8.24](https://img.shields.io/badge/Solidity-0.8.24-363636.svg)](https://soliditylang.org)

---

## What Is Iskander?

Iskander is a self-hosted server for cooperatives. Run it once and your cooperative gets:

- **Loomio** -- democratic decision-making (proposals, votes, discussions, STV elections)
- **AI Clerk** -- a conversational assistant that helps members participate, draft documents, and understand decisions
- **Nextcloud** -- shared files, calendar, contacts, email
- **Glass Box** -- every AI action is transparent and auditable by any member
- **Treasury monitoring** -- an AI Steward watches the cooperative's wallet and creates proposals for significant spending
- **Cooperative website** -- public transparency, membership applications, federation directory
- **Single Sign-On** -- one account (via Authentik) accesses everything
- **Blockchain anchoring** -- decisions recorded on-chain with IPFS hashes for tamper-proof history
- **Zero-knowledge voting** -- MACI secret ballots where individual votes are never disclosed
- **Federation** -- cooperatives discover and communicate with each other

All of this is aligned to the **ICA Cooperative Principles** -- the seven internationally recognised principles defined by the International Co-operative Alliance. The AI agents embody the six core cooperative values (self-help, self-responsibility, democracy, equality, equity, solidarity) and four ethical values (honesty, openness, social responsibility, caring for others).

---

## Architecture

```
                        +---------------------------+
                        |    Authentik (SSO/OIDC)    |
                        |  One login for everything  |
                        +----+--------+--------+-----+
                             |        |        |
              +--------------+--+ +---+----+ +-+-------------+
              |  Loomio + Chat  | |Nextcloud| | Coop Website  |
              |  Widget (Clerk) | | Files   | | (Public +     |
              |  Decisions      | | Email   | |  Members)     |
              +-------+---------+ +--------++ +---------------+
                      |
        OpenClaw (Clerk + Steward agents)
                      |
           +----------+-----------+
           |                      |
      Ollama (LLM)     Decision Recorder
                        (PostgreSQL + IPFS)
```

### Services (Phase C MVP -- 8 containers, ~8GB RAM)

| Service | Purpose |
|---------|---------|
| PostgreSQL 16 | Shared database (Loomio, Nextcloud, Authentik, decisions) |
| Redis | Session store and job queue |
| Authentik | OAuth2/OIDC identity provider -- SSO for all services |
| Loomio | Democratic decision-making platform with Iskander chat widget |
| Nextcloud | File hosting, calendar, contacts, email client |
| Ollama | Local LLM inference (Phi-3-mini or OLMo) |
| OpenClaw | AI agent orchestrator (Clerk + Steward agents) |
| IPFS Kubo | Decision record pinning for tamper-proof history |

### Phase B Expansion (Weeks 4-8)

Adds: Anvil (EVM node), Stalwart (email server), Caddy (cooperative website), Dendrite (Matrix chat), bringing the total to 11+ services.

---

## The AI Clerk

The Clerk is every member's personal assistant inside Loomio. It appears as a chat widget in the bottom-right corner.

**What it does:**
- Answers questions about the cooperative (finances, decisions, rules)
- Helps draft proposals -- guides members to the right decision process (Advice, Consent, Consensus)
- Drafts and revises documents based on member input, saves to Nextcloud
- Incorporates feedback from multiple members into document revisions
- Summarises long discussion threads in plain language
- Tracks action items as Loomio tasks with due dates
- Reminds members about pending votes via @mentions
- Guides members through ICA values self-reflection
- DMs members via Loomio Direct Discussions to help expand ideas into full proposals

**What it never does:**
- Vote or express opinions
- Advocate for any position
- Withhold information from any member
- Finalise a document without member approval

Every Clerk action is logged in the Glass Box -- any member can ask "What have you been doing?" and get a full audit trail.

---

## ICA Cooperative Principles

Every aspect of Iskander is designed around the seven cooperative principles:

| # | Principle | How Iskander Implements It |
|---|-----------|--------------------------|
| 1 | Voluntary and Open Membership | SSO onboarding, Clerk-guided welcome sequence, membership lifecycle |
| 2 | Democratic Member Control | Loomio voting (Consent, Consensus, STV elections), 1-member-1-vote via BrightID + MACI ZK proofs |
| 3 | Member Economic Participation | Treasury monitoring, member shares, surplus distribution, asset-lock enforcement |
| 4 | Autonomy and Independence | Fully self-hosted, no cloud dependencies, cooperative owns all infrastructure |
| 5 | Education, Training, Information | Clerk-guided onboarding, values reflection, proactive governance training |
| 6 | Cooperation among Cooperatives | MCP-based federation, Liaison agent, cooperative discovery protocol |
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
|   +-- archive/                    # Archived design specs (.odt, .txt)
+-- skills/                         # Claude Code skill plugins (11 skills)
+-- loomio-wiki-complete.json       # Full Loomio feature documentation
+-- src/
    +-- IskanderOS/
    |   +-- openclaw/               # AI agent system
    |   |   +-- openclaw.json       # OpenClaw configuration
    |   |   +-- agents/
    |   |   |   +-- orchestrator/   # Agent coordinator
    |   |   |   +-- clerk/          # Member-facing assistant
    |   |   |   +-- steward/        # Treasury monitor
    |   |   +-- skills/
    |   |       +-- loomio-bridge/  # Loomio API integration
    |   |       +-- document-collab/# AI-assisted document drafting
    |   |       +-- values-reflection/
    |   |       +-- glass-box/      # Audit trail
    |   |       +-- treasury-monitor/
    |   |       +-- membership/     # Join/leave/onboard
    |   +-- services/
    |   |   +-- authentik/          # SSO identity provider
    |   |   +-- loomio/             # Decision platform + chat widget
    |   |   +-- nextcloud/          # Files, calendar, email
    |   |   +-- decision-recorder/  # Webhook service (FastAPI)
    |   |   +-- website/            # Public cooperative website
    |   +-- infra/
    |   |   +-- decision_log.sql    # Database schema
    |   |   +-- traefik/            # Reverse proxy + TLS + security
    |   +-- contracts/              # Solidity smart contracts
    |   |   +-- src/
    |   |       +-- Constitution.sol
    |   |       +-- CoopIdentity.sol    # ERC-4973 Soulbound Tokens
    |   |       +-- governance/
    |   |           +-- MACIVoting.sol  # ZK secret ballot voting
    |   +-- scripts/
    |   |   +-- first-boot.py       # Interactive setup wizard
    |   +-- docs/                   # ICA reference documents
    |   +-- legacy/                 # Archived: previous backend, frontend, agents
    +-- IskanderHearth/             # Open hardware (CERN-OHL-S v2)
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- 8GB+ RAM
- Ubuntu 24.04 (recommended) or any Linux with Docker

### First Boot

```bash
git clone https://github.com/Argocyte/Iskander.git
cd Iskander/src/IskanderOS

python3 scripts/first-boot.py
```

The wizard will ask for:
1. Your cooperative's name
2. Founding members (name + email)
3. Optional: your domain name

Then it starts all services, configures SSO, creates accounts, and opens your browser. Your cooperative is ready.

---

## Development Status

Iskander is in active development following the **Route C to B** plan:

- **Phase C (Weeks 1-3)**: Radical MVP -- Loomio + Clerk + Nextcloud + SSO + Glass Box + Treasury
- **Phase B (Weeks 4-8)**: Expansion -- blockchain, ZK voting, governance, community impact, email, website, federation

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full phased roadmap.

---

## Security

Iskander is designed for deployment on the open internet:

- TLS everywhere (Let's Encrypt via Traefik)
- Security headers (STS, CSP, X-Frame-Options)
- Internal-only networking for databases
- Non-root containers with dropped capabilities
- Rate limiting and CrowdSec threat intelligence
- Optional Cloudflare integration for DDoS protection

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
- [Loomio](https://www.loomio.com) -- Decision-making platform
- [OpenClaw](https://openclaw.dev) -- AI agent orchestrator
