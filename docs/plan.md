# Iskander: Lunarpunk Cooperative Infrastructure

## Context

Iskander is being reframed from "cooperative-in-a-box" to **lunarpunk cooperative infrastructure** — a federated platform that puts web3 in the hands of people who otherwise wouldn't touch it, in a decision-making and project-planning environment that just works.

**The thesis**: Generous tit-for-tat is the optimal game theory strategy. A federated cooperative economy built on this principle will develop emergent behaviours that outcompete extractive capitalism over time. Iskander is the infrastructure that makes this possible.

**Vision shift**: Lunarpunk, not solarpunk, is the core. Privacy as a prerequisite for autonomy. Selective disclosure via ZK proofs — transparent to members, private from the world, secret at the individual level.

**Key decisions made**:
- **Loomio + Mattermost together** — governance engine + real-time chat, bridged by the AI Clerk
- **K3s from the start** — native multi-node, federation-ready orchestration
- **curl|sh installer** — Tailscale-style setup with Ansible underneath; ISO images as separate downstream project
- **Selective ZK disclosure** — Glass Box shows aggregate outcomes; individual votes are ZK-private; cooperative is opaque externally

---

## Part 1: Why Web3 — Five Problems Only Cryptography Solves

Web3 in Iskander is not blockchain for blockchain's sake. It solves five cooperative problems that traditional technology cannot:

### 1. Tamper-Evident Decision Records
**Problem**: Loomio decisions in PostgreSQL can be silently altered by any database admin.
**Solution**: IPFS-pinned decision payloads with on-chain hash anchoring. Digital equivalent of a notarized minute book.
**Contracts**: Constitution.sol (27 lines, append-only event emitter)

### 2. Anti-Coercion Voting
**Problem**: In worker cooperatives, your colleagues are your employers. Open ballots create social pressure.
**Solution**: MACI (Minimum Anti-Collusion Infrastructure) — encrypted votes, last-message-wins anti-coercion, ZK-proven tallies. The only system achieving: eligible-voter proof + correct-tally proof + unlinkable votes + vote-buying resistance simultaneously.
**Contracts**: MACIVoting.sol + zk_maci_wrapper.py (stubs → production circuits needed)

### 3. Sybil-Resistant Identity
**Problem**: One-member-one-vote requires proving each member is unique. Email verification is trivially Sybil-attackable. KYC is extractive and contrary to ICA Principle 1.
**Solution**: Soulbound Tokens (non-transferable, non-purchasable) + BrightID peer-to-peer verification (no government ID, no wealth signals).
**Contracts**: CoopIdentity.sol (ERC-4973, trust scores 0-1000)

### 4. Inter-Cooperative Trust Without Intermediaries
**Problem**: When cooperatives trade, who holds escrow? Who arbitrates? Banks extract fees, courts are slow, platforms accumulate power.
**Solution**: Code-locked escrow, federated human juries, exponential-decay reputation (30-day half-life forces continuous good behaviour). Trust as a commons that must be continuously maintained.
**Contracts**: IskanderEscrow.sol + ArbitrationRegistry.sol + ForeignReputation.sol

### 5. Anti-Extractive Finance
**Problem**: Payment networks (Visa/MC) extract 2-3% of every transaction. Cooperatives operating on thin margins pay extractive rent.
**Solution**: 1:1 fiat-backed cooperative tokens for inter-coop settlement without payment fees. Mondragon-style pay ratio enforcement at the contract level.
**Contracts**: CoopFiatToken.sol + InternalPayroll.sol (6:1 max ratio)

---

## Part 2: The Lunarpunk Privacy Model

### Solarpunk vs Lunarpunk

The Solarpunk article establishes web3 as "our alternative for doomerism in a world of rising coordination failure." But Rachel-Rose O'Leary's Lunarpunk critique warns that transparent systems build their own prison — surveillance capitalism will co-opt them.

**Iskander's resolution: Selective Disclosure**

| Layer | Visibility | Mechanism |
|-------|-----------|-----------|
| **Aggregate outcomes** | Transparent to members (Glass Box) | "Decision passed 7-2" visible in audit trail |
| **Individual votes** | Always secret | MACI ZK proofs — nobody, not even admins, can link votes to members |
| **Treasury flows** | Transparent to members | On-chain records readable by any member via Clerk |
| **External visibility** | Opaque by default | ZK proofs verify correctness without revealing internal data |
| **AI actions** | Transparent to members | Glass Box logs every Clerk/Steward action with rationale |

This is the DarkFi AnonDAO principle applied to cooperatives: the collective's integrity is verifiable without exposing individual members to surveillance.

### ICA Principle Alignment

- **P2 (Democratic Control)**: Transparency of outcomes ensures accountability; privacy of votes ensures genuine expression
- **P4 (Autonomy)**: External opacity protects cooperative independence from regulatory overreach or competitor intelligence
- **P1 (Open Membership)**: No KYC — BrightID peer verification preserves privacy while proving uniqueness

---

## Part 3: Game Theory — Generous Tit-for-Tat as Federation Protocol

### Why GTFT Outcompetes

In Axelrod's iterated prisoner's dilemma tournaments, generous tit-for-tat (GTFT) dominates:
- **Cooperates first** (optimistic initial stance)
- **Mirrors** the other party's last move (reciprocity)
- **Forgives defection 5-33% of the time** (prevents death spirals from noise/accidents)

For inter-cooperative economics, "noise" = late payments, resource shortfalls, communication failures. GTFT prevents a single bad interaction from collapsing a trading relationship.

### Implementation in ForeignReputation.sol

The existing contract already implements this via exponential decay:
- 30-day half-life means trust decays naturally (forgiveness built in)
- 4 tiers: Quarantine → Provisional → Trusted → Allied
- Score capped at ±500 bps per transaction (prevents gaming)
- A cooperative that stops transacting decays to Quarantine in ~390 days
- New cooperatives can reach Allied through consistent good transactions

**Enhancement needed**: Add configurable forgiveness parameter (currently implicit in decay). The Clerk should surface federation health: "Our trust score with Coop B has decayed to Provisional — we haven't traded in 45 days. Should we initiate a collaboration?"

### Emergent Behaviour

Research consistently shows federated cooperative networks develop emergent properties:
- **Collective intelligence**: Diverse nodes sense market/regulatory shifts faster than any individual
- **Resource resilience**: Each node accesses the broader network's expertise and surplus
- **Trust as system property**: Emerges from norms of reciprocity, not individual decisions
- **Mondragon effect**: 65,000+ worker-owners across 80+ cooperatives demonstrate real-world cooperative emergence

---

## Part 4: Learning from Existing Projects

### DisCO (Distributed Cooperative Organizations)
- Feminist economics framework tracking three value streams: **livelihood work, love work (care), pro-bono commons work**
- Seven DisCO principles expand the seven ICA principles for the 21st century
- Key insight: **care work must be valued** — governance that ignores emotional labour reproduces extractive patterns
- **For Iskander**: The Clerk agent should help track and make visible all three value streams, not just "productive" output

### Hypha DAO → DHO → DAO 3.0
- Most technically mature cooperative-DAO platform (300+ organizations)
- Evolution: code-centric DAO 1.0 → protocol-optimized 2.0 → **human-centered 3.0**
- Key insight: "governing the machine" fails; governance is "an emergent property that must dynamically evolve as context shifts"
- Multi-layer modular voting, "leadership without control" protocols, membranic governance spaces
- **For Iskander**: Don't over-automate governance. The chain records and enforces; humans deliberate and decide.

### InterCooperative Network (ICN)
- Rust monorepo, 77% complete, 1134+ tests passing
- Nine integrated stations from identity through governance, accounting, execution
- Key insight: "identity, rules, decisions, obligations, execution, proof — should be one coherent substrate rather than seven tools held together by staff discipline"
- **Trust-native, not trustless** — trust as auditable system property
- **For Iskander**: ICN's federation protocol is the most architecturally aligned existing project. Consider interoperability rather than reinventing federation.

### ReFi Critique (Frontiers in Blockchain, 2025)
- 50% of 40 evaluated ReFi projects genuinely regenerative, 45% "sustainable DeFi" (greenwashing), 5% structurally misaligned
- Warning: "blockchain enables unprecedented commodification, potentially making the Global Commons the next, and final, commodity frontier"
- **For Iskander**: Every web3 feature must pass the test — does this serve cooperative emergence, or does it financialize something that shouldn't be financialized?

---

## Part 5: Revised Architecture

### Core Stack (Phase C MVP)

| Service | Purpose | RAM |
|---------|---------|-----|
| **K3s** | Orchestration (single-node initially, multi-node ready) | ~800MB |
| **PostgreSQL 16** | Shared database | ~500MB |
| **Redis** | Sessions, queues | ~100MB |
| **Authentik** | SSO/OIDC identity provider | ~700MB |
| **Loomio** | Democratic decision-making (governance engine) | ~1.5GB |
| **Mattermost** | Real-time chat + coordination | ~500MB |
| **Nextcloud** | Files, calendar, contacts, email client | ~500MB |
| **Ollama** | Local LLM inference | ~2GB |
| **OpenClaw** | AI agent orchestrator (Clerk + Steward) | ~200MB |
| **IPFS Kubo** | Decision record pinning | ~200MB |
| **Vaultwarden** | Shared credential management | ~50MB |
| **Backrest** | Backup management (Restic UI) | ~50MB |
| **Cloudflared** | Tunnel for public access (no open ports) | ~30MB |
| **Beszel** | System monitoring (lightweight) | ~50MB |
| **Headscale** | Mesh networking for federation | ~50MB |

**Total: ~7.2GB** — fits 8GB minimum with headroom; 16GB recommended for comfortable operation.

### Phase B Additions

| Service | Purpose | RAM |
|---------|---------|-----|
| **Anvil** | Local EVM node (decision anchoring + contracts) | ~200MB |
| **Chain Bridge** | Loomio→blockchain bridge service | ~100MB |
| **Stalwart** | Email server (cooperative addresses) | ~200MB |
| **Caddy** | Cooperative website (public + members) | ~50MB |

### K3s Strategy (Addressing GitHub Issue #8)

**Why K3s from the start**:
- Single 40MB binary, minimum 512MB RAM for control plane
- Native multi-node: cooperatives add servers by running `k3s agent` on new hardware
- Load balancing between nodes for resilience
- Rolling updates without downtime
- Self-healing: crashed containers restart automatically
- Helm charts for declarative service management
- **Federation**: each cooperative's K3s cluster is a sovereign unit; Headscale creates the mesh between them

**Minimum requirements**:
- Single node: 8GB RAM (tight), 16GB recommended
- Multi-node cluster: 4GB per worker node minimum
- ARM64 + x86_64 supported natively

**Migration path**: The curl|sh installer provisions K3s on a single node. Adding nodes later is `curl -sfL https://get.k3s.io | K3S_URL=... K3S_TOKEN=... sh -`. No architectural changes needed.

### Installation: curl|sh with Ansible Underneath

```bash
curl -sfL https://get.iskander.coop/install | sh -s -- \
  --coop-name "Sunrise Workers" \
  --admin-email "founder@sunrise.coop" \
  --domain "sunrise.coop"      # optional, uses Cloudflare tunnel if omitted
```

**What happens**:
1. Detects OS (Debian/Ubuntu/Fedora/Arch), installs K3s if missing
2. Downloads Ansible playbook + Helm charts
3. Runs playbook: provisions all services, generates secrets, configures SSO
4. Creates founding member account in Authentik
5. Opens browser: "Your cooperative is ready. Log in once — access everything."

**For non-technical users**: The same script, but shipped as a pre-configured image (Debian + K3s + all services) for Raspberry Pi clusters or mini-PCs. This is the **IskanderHearth** hardware project — a separate downstream deliverable.

### DDNS / Cloudflare Strategy

- **Default**: Cloudflared tunnel (outbound-only, no open ports, no router config, free HTTPS + DDoS protection)
- **Sovereignty option**: Headscale + DDNS (cloudflare-ddns or ddclient) for cooperatives that refuse Cloudflare dependency
- **The installer asks**: "Do you have a domain? → Yes: configure Cloudflare tunnel or DDNS. No: localhost-only with Headscale for federation."
- Document the ICA Principle 4 tradeoff: Cloudflare is pragmatic but centralized; DDNS + Let's Encrypt is sovereign but harder

---

## Part 6: How Web3 Integrates with Loomio + Mattermost

### The Bridge Pattern

Loomio is the source of truth for decisions. The blockchain is the auditable anchor. Mattermost is where daily work happens.

```
Member ←→ Mattermost (chat) ←→ Clerk Agent (OpenClaw)
                                      ↕
                                Loomio (governance)
                                      ↕
                           Decision Recorder (FastAPI)
                              ↕              ↕
                           IPFS           Chain Bridge
                              ↕              ↕
                         CID hash      Anvil (EVM)
                              ↕              ↕
                        Glass Box    Smart Contracts
```

### Contract Integration Points

| Contract | Trigger | Direction |
|----------|---------|-----------|
| Constitution.sol | First-boot genesis ceremony | Deploy once |
| CoopIdentity.sol | Loomio membership vote → chain-bridge mints/burns SBT | Loomio → chain |
| MACIVoting.sol | Clerk offers ZK ballot for sensitive decisions | Parallel to Loomio |
| InternalPayroll.sol | Steward reads pay ceiling before proposals | Chain → Steward agent |
| IskanderEscrow.sol | Loomio approves inter-coop trade | Loomio → chain |
| ArbitrationRegistry.sol | Federated jury Safe multi-sig | External |
| StewardshipLedger.sol | Oracle pushes Impact Scores from Loomio participation | Loomio stats → chain |
| ForeignReputation.sol | Oracle updates after inter-coop transactions | Chain-bridge monitors |
| TrustRegistry.sol | Loomio approves credential issuer trust | Loomio → chain |

### Mattermost ↔ Loomio ↔ Clerk Integration

- **Mattermost**: Daily chat, quick questions, informal coordination. Clerk agent available as a bot (`@clerk help me draft a proposal`)
- **Loomio**: Formal proposals, votes, decisions, outcomes. Clerk creates proposals from Mattermost conversations
- **Bridge**: Mattermost webhook plugin posts Loomio decision notifications to relevant channels. Clerk summarizes Loomio threads in Mattermost for members who prefer chat.
- **Unified search**: Clerk agent queries both Mattermost history and Loomio threads to answer member questions

---

## Part 7: Phased Implementation

### Phase C: Radical MVP (Weeks 1-3)

**Goal**: A cooperative member installs Iskander, messages their AI clerk via Mattermost or Loomio, the clerk helps them participate in decisions, every decision is transparently recorded, and agents only act with democratic authorisation.

#### Week 1: Foundation
- **C.0a**: Security baseline (K3s + Cloudflared/Headscale, TLS, headers, internal networking)
- **C.0b**: Authentik SSO + shared PostgreSQL/Redis + K3s Helm charts for all services
- **C.1**: Loomio instance with OAuth SSO, cooperative group, API key
- **C.1b**: Mattermost instance with SSO, Loomio webhook integration
- **C.1c**: Nextcloud instance with SSO, shared folders, Loomio file integration
- **C.2**: OpenClaw + Clerk agent + Iskander chat widget (on both Loomio and Mattermost)

#### Week 2: Decision Loop + Operations
- **C.3**: Loomio-bridge skill (full decision process types, quorum, tags, tasks, DMs)
- **C.3b**: Document collaboration skill (draft, revise, incorporate feedback, save to Nextcloud)
- **C.4**: Decision recorder (Loomio webhook → PostgreSQL + IPFS pin)
- **C.5**: Glass Box audit trail (agent action logging + query endpoint)
- **C.6**: Steward agent (treasury monitoring, threshold-based Loomio proposals)
- **C.7**: Vaultwarden + Backrest + Beszel (operational essentials)

#### Week 3: First-Boot + Integration
- **C.8**: curl|sh installer (Ansible playbook + Helm charts + first-boot wizard)
- **C.9**: Membership lifecycle (join/leave/onboard, Clerk welcome sequence)
- **C.10**: End-to-end verification (4 test flows)

### Phase B: Web3 + Federation (Weeks 4-8)

#### Week 4: Chain Foundation
- Deploy Anvil + all 9 contracts via Deploy.s.sol
- Build chain-bridge service (Loomio webhook → IPFS → on-chain hash)
- Genesis ceremony: founding SBTs minted, Constitution.sol deployed

#### Week 5: Identity + ZK Preparation
- SBT minting integrated with Loomio membership votes
- BrightID integration (optional, treasury-funded sponsorship)
- Circom circuit compilation + trusted setup ceremony planning

#### Week 6: ZK Democracy + Stewardship
- Trusted setup ceremony with founding members
- MACI coordinator service (replace stubs with real snarkjs)
- StewardshipLedger integration (Impact Scores from Loomio participation)
- Economic participation module (member shares, surplus distribution)

#### Week 7: Federation + Community
- ForeignReputation.sol activated for inter-coop SDC registration
- IskanderEscrow.sol for trade proposals approved in Loomio
- Cooperative website (public Glass Box, membership applications)
- Email server (Stalwart + Nextcloud Mail)

#### Week 8: Multi-Channel + Security
- Matrix/Dendrite for additional communication channel
- Complete Values Council (10 agents assessing ICA compliance)
- CrowdSec + WAF + container hardening
- Penetration testing checklist + security documentation

---

## Part 8: Release Deliverables

### Source Release
- Git repository with tagged release (e.g., `v0.1.0-alpha`)
- ZIP of source code downloadable from GitHub Releases
- All Helm charts, Ansible playbooks, and Docker images

### Disk Usage Requirements

| Component | Storage |
|-----------|---------|
| K3s + container images | ~8GB |
| PostgreSQL databases | ~2GB initial, grows with usage |
| Nextcloud shared storage | ~10GB default (configurable) |
| IPFS decision records | ~1GB per 10,000 decisions |
| Ollama LLM model | ~4GB (Phi-3-mini) or ~8GB (larger) |
| Backrest backup repository | External drive recommended |
| **Minimum total** | **~30GB** |
| **Recommended** | **64GB+ SSD** |

### Setup Instructions
- `curl|sh` one-liner for Linux (Debian/Ubuntu/Fedora/Arch)
- Step-by-step manual guide for airgapped environments
- Helm chart values documentation for customization
- Domain setup guide (Cloudflare tunnel vs DDNS vs localhost-only)

### Backup Solution (Backrest + Restic)
- Backrest web UI integrated into the cooperative's admin dashboard
- Automated daily backups of: PostgreSQL dumps, Nextcloud files, IPFS pins, Vaultwarden vault
- Supports: local disk, S3, B2, SFTP, remote server via Headscale mesh
- Member-facing: "Your cooperative's data is backed up. Last backup: 2 hours ago. ✓"
- Restore: browse backups in web UI, point-in-time recovery

### System Monitoring (Beszel)
- Lightweight (~50MB RAM) vs Grafana+Prometheus (400-800MB)
- Pre-built dashboards: CPU, memory, disk, network, container health
- Alerts: disk full, service down, backup failed → Mattermost notification
- If advanced monitoring needed later: Prometheus + Grafana as optional Helm chart

### ISO Images (Downstream Project — IskanderHearth)
- ARM64 (Raspberry Pi 4/5, Orange Pi) + x86_64
- Pre-configured Debian + K3s + all services
- Boot from USB/SD → cooperative functional immediately
- Update mechanism: `iskander update` pulls new Helm charts
- Separate repository, separate release cycle

---

## Part 9: White Paper — "People, Place, Planet"

**Deliverable**: A white paper explaining why Iskander is necessary, to be produced after the technical plan is approved. Structure:

### 1. The Problem: Coordination Failure
- Cooperatives are the democratic alternative to extractive capitalism
- But they lack digital infrastructure designed for democracy
- Current tools (Google Workspace, Slack, Zoom) are built for hierarchies
- Web3 promises decentralization but delivers speculation and plutocracy
- ReFi claims regeneration but 45% is "sustainable DeFi" greenwashing (Frontiers 2025)

### 2. The Thesis: Emergent Cooperative Advantage
- Game theory: GTFT is the optimal strategy in iterated games with noise
- Federated cooperatives develop emergent properties: collective intelligence, resource resilience, trust as system property
- Historical proof: Mondragon (65,000+ worker-owners), Emilia-Romagna cooperative district
- Web3 can encode these patterns into infrastructure — making cooperation the path of least resistance

### 3. The Vision: Lunarpunk Cooperative Infrastructure
- Privacy as prerequisite for autonomy (O'Leary's Lunarpunk thesis)
- Selective disclosure: transparent to members, private from the world, secret at the individual level
- Infrastructure as resistance (Flynn): "opposition that begins with infrastructure as a form of resistance"
- Not "blockchain for cooperatives" but "cooperative infrastructure that happens to use cryptography where it uniquely solves problems"

### 4. The Architecture: Five Cryptographic Solutions
- Tamper-evident decisions, anti-coercion voting, Sybil-resistant identity, intermediary-free federation, anti-extractive finance
- Each grounded in a specific cooperative problem, not speculative technology

### 5. Values Alignment
- ICA 7 Principles as design constraints, not marketing
- DisCO's three value streams (livelihood, love, commons)
- Hypha's "governance as emergent property" — don't over-automate
- ICN's "trust-native, not trustless" — trust as auditable system property

### 6. For People, Place, and Planet
- **People**: Every member gets an AI clerk — democratizing access to governance participation regardless of technical literacy
- **Place**: Self-hosted, locally controlled, community-scale — not global platforms extracting local value
- **Planet**: Energy-aware scheduling, SDG tracking, environmental accountability baked into governance

### 7. Call to Action
- How cooperatives can adopt Iskander
- How developers can contribute
- How the cooperative movement can build the federation

---

## Verification

### Phase C Success (Week 3):
1. `curl|sh` installer provisions a full cooperative server on clean Debian/Ubuntu
2. K3s cluster running with all services healthy (Beszel dashboard shows green)
3. Member creates ONE account (Authentik) → accesses Loomio + Mattermost + Nextcloud
4. Member chats with Clerk in Mattermost → Clerk creates Loomio proposal
5. Members vote in Loomio → decision recorded in DB + IPFS hash
6. Backrest shows daily backup status; Vaultwarden stores cooperative credentials
7. Cloudflared tunnel or Headscale mesh provides external/federation access

### Phase B Success (Week 8):
1. Every decision has an on-chain hash traceable to the Loomio discussion
2. Sensitive decisions use MACI ZK voting — individual votes never disclosed
3. Each member has a non-transferable SBT, optionally BrightID-verified
4. Two cooperative nodes discover each other via Headscale mesh
5. Inter-cooperative trade uses IskanderEscrow with ForeignReputation scoring
6. Full GTFT dynamics observable: trust decays, rebuilds through interaction

---

## Critical Files

| File | Purpose |
|------|---------|
| `src/IskanderOS/contracts/script/Deploy.s.sol` | Deployment orchestrator for all 9 contracts |
| `src/IskanderOS/contracts/src/CoopIdentity.sol` | Foundational membership SBT (367 lines) |
| `src/IskanderOS/contracts/src/governance/MACIVoting.sol` | ZK secret ballot voting |
| `src/IskanderOS/legacy/backend/crypto/zk_maci_wrapper.py` | MACI coordinator (stubs → production) |
| `src/IskanderOS/legacy/backend/finance/solvency_oracle.py` | Reserve monitoring |
| `src/IskanderOS/legacy/backend/api/brightid_sponsor.py` | BrightID integration |
| `src/IskanderOS/services/decision-recorder/` | Chain bridge service (to be built) |
| `src/IskanderOS/openclaw/agents/clerk/` | Clerk agent SOUL.md |
| `src/IskanderOS/openclaw/skills/loomio-bridge/` | Loomio API integration skill |

## Research Sources

- [Solarpunk and Web3 — EBC](https://eblockchainconvention.com/solarpunk-and-web3/)
- [Solarpunk as Planetary Infrastructure — Zora Zine](https://zine.zora.co/solarpunk-web3-kareola)
- [ReFi Regenerative Claims Evaluation — Frontiers 2025](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2025.1564083/full)
- [ReFi and Global Commons — Frontiers 2025](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2025.1564073/full)
- [Hypha DAO to DAO 3.0 — Frontiers 2025](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2025.1630402/full)
- [InterCooperative Network](https://intercooperative.network/)
- [DisCO.coop](https://www.disco.coop/about/)
- [DisCO Governance Model V3.0](https://mothership.disco.coop/Distributed_Cooperative_Organization_(DisCO)_Governance_Model_V_3.0)
- [Quadratic Funding — Gitcoin](https://qf.gitcoin.co/)
- [DarkFi — Lunarpunk L1](https://dark.fi/)
- [K3s Requirements](https://docs.k3s.io/installation/requirements)
- [Backrest (Restic UI)](https://github.com/garethgeorge/backrest)
- [Vaultwarden](https://github.com/dani-garcia/vaultwarden)
- [Beszel Monitoring](https://github.com/henrygd/beszel)
- [Headscale (Self-hosted Tailscale)](https://github.com/juanfont/headscale)
