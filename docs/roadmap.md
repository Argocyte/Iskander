# Iskander Project Roadmap

## Route C to B: Radical MVP then Web3 + Federation

### Phase C: Radical MVP (Weeks 1-3)

**Goal**: A cooperative installs Iskander with one command and gets a fully functional democratic workspace -- decisions, real-time chat, AI clerk, shared files, password vault, backups, monitoring, and single sign-on -- all self-hosted, all private, all under member control.

#### Week 1: Infrastructure + Core Services

| Task | What | Status |
|------|------|--------|
| C.0a | Security baseline (K3s + Cloudflared/Headscale, TLS, headers) | Planned |
| C.0b | Authentik SSO + shared PostgreSQL/Redis + K3s Helm charts | Planned |
| C.1 | Loomio with OAuth SSO | Planned |
| C.1b | Mattermost with SSO + Loomio webhook integration | Planned |
| C.1c | Nextcloud with SSO + shared folders | Planned |
| C.2 | OpenClaw + Clerk agent + chat widget (Loomio + Mattermost) | Planned |

#### Week 2: Decision Loop + Operational Essentials

| Task | What | Status |
|------|------|--------|
| C.3 | Loomio-bridge skill (decision processes, quorum, tags, tasks, DMs) | Planned |
| C.3b | Document collaboration skill | Planned |
| C.4 | Decision recorder (Loomio webhook -> PostgreSQL + IPFS) | Planned |
| C.5 | Glass Box audit trail | Planned |
| C.6 | Steward agent (treasury monitoring) | Planned |
| C.7 | Vaultwarden + Backrest + Beszel (operational essentials) | Planned |

#### Week 3: Installer + Verification

| Task | What | Status |
|------|------|--------|
| C.8 | curl\|sh installer (Ansible + Helm charts + first-boot wizard) | Planned |
| C.9 | Membership lifecycle | Planned |
| C.10 | End-to-end verification | Planned |

**Phase C delivers**: K3s cluster + Authentik SSO + Loomio + Mattermost + Nextcloud + AI Clerk + Glass Box + Treasury monitoring + Vaultwarden + Backrest + Beszel + Document collaboration + Membership onboarding + One-command installer

---

### Phase B: Web3 + Federation (Weeks 4-8)

#### Week 4: Blockchain Foundation

- Deploy Anvil + 9 smart contracts (Constitution, CoopIdentity, MACIVoting, etc.)
- Chain-bridge service linking Loomio decisions to on-chain records
- Genesis ceremony for founding members

#### Week 5: Identity + ZK Voting

- Mint Soulbound Tokens (SBTs) for founding members
- Integrate BrightID for proof-of-unique-human (Sybil resistance)
- Compile Circom circuits for zero-knowledge proofs

#### Week 6: Governance + Economic Participation

- MACI trusted setup ceremony
- ZK voting integration with Loomio
- Stewardship module (STV elections, delegated voters, term limits)
- Economic participation (member shares, surplus distribution, asset-locks)

#### Week 7: Federation + Public Presence

- Federation protocol (ForeignReputation + Escrow contracts)
- Cooperative website (Caddy, public Glass Box, membership applications, federation directory)
- Email server (Stalwart for cooperative email addresses)

#### Week 8: Multi-Channel + Security Hardening

- Matrix/Dendrite for encrypted real-time communication
- Values Council agents (Democracy, Honesty, Equality, Solidarity guardians)
- Security hardening (CrowdSec, WAF, penetration testing, incident response)

**Phase B delivers**: Blockchain anchoring + ZK voting + SBT identity + BrightID + governance elections + economic participation + federation + website + email + Matrix + Values Council + security hardening

---

### Key Milestones

| Milestone | Description | Target |
|-----------|-------------|--------|
| First Decision | Member creates proposal via Clerk -> Loomio vote -> recorded | Week 1 |
| Full Workspace | SSO + Loomio + Mattermost + Nextcloud + Clerk operational | Week 1 |
| Decision Loop | Webhook -> PostgreSQL + IPFS, Glass Box queryable | Week 2 |
| Operational Stack | Vaultwarden + Backrest + Beszel deployed | Week 2 |
| One-Command Install | curl\|sh -> cooperative functional in 10 minutes | Week 3 |
| On-Chain | Every decision has a blockchain hash | Week 4 |
| 1 Member 1 Vote | BrightID + SBT + MACI ZK voting deployed | Week 6 |
| Federation | Two cooperatives discover and transact with each other | Week 7 |
| Public Website | Cooperative visible to the world with email | Week 7 |
| Full Stack | Complete cooperative-in-a-box with all security hardening | Week 8 |

---

### ICA Principle Coverage

| Principle | Phase C | Phase B |
|-----------|---------|---------|
| P1: Voluntary and Open Membership | Membership lifecycle, Clerk onboarding | BrightID identity, SBT credentials |
| P2: Democratic Member Control | Loomio voting (Consent, Advice, Consensus) | STV elections, MACI ZK voting, governance module |
| P3: Member Economic Participation | Treasury monitoring via Steward agent | Shares, surplus, patronage, asset-locks |
| P4: Autonomy and Independence | Fully self-hosted on K3s, Cloudflared/Headscale tunnels | Federation on cooperative terms |
| P5: Education, Training, Information | Clerk guidance, Glass Box transparency | Proactive learning pathways, mentoring |
| P6: Cooperation among Cooperatives | Mattermost cross-coop channels | ForeignReputation + Escrow federation |
| P7: Concern for Community | Public Glass Box via website | SDG tracking, sustainability reporting |

---

### Technology Stack

| Layer | Phase C | Phase B Addition |
|-------|---------|-----------------|
| Orchestration | K3s (Helm charts) | -- |
| Identity | Authentik (OAuth2/OIDC) | BrightID + CoopIdentity.sol SBTs |
| Decisions | Loomio | + MACIVoting.sol (ZK) |
| AI | OpenClaw + Ollama | + Values Council agents |
| Chat | Mattermost | + Matrix/Dendrite |
| Files | Nextcloud | -- |
| Data | PostgreSQL + Redis + IPFS | + Anvil (EVM blockchain) |
| Security | K3s + Cloudflared/Headscale + TLS | + CrowdSec + WAF |
| Web | Iskander chat widget (Loomio + Mattermost) | + Cooperative website (Caddy) |
| Email | -- | + Stalwart |
| Passwords | Vaultwarden | -- |
| Backups | Backrest | -- |
| Monitoring | Beszel | -- |
