# Iskander Project Roadmap

## Route C to B: Radical MVP then Loomio-Native Expansion

### Phase C: Radical MVP (Weeks 1-3)

**Goal**: Prove the core proposition -- a cooperative member messages their AI clerk, the clerk helps them participate in democratic decisions via Loomio, collaboratively draft and revise documents, every decision is transparently recorded, and agents only act with democratic authorisation.

#### Week 1: Foundations

| Task | What | Status |
|------|------|--------|
| C.0a | Security baseline (TLS, headers, CORS, internal networking, non-root containers) | Planned |
| C.0b | Authentik SSO + shared PostgreSQL/Redis infrastructure | Planned |
| C.1 | Loomio instance with OAuth SSO, cooperative group, API key | Planned |
| C.1b | Nextcloud instance with SSO, shared folders, Loomio file integration | Planned |
| C.2 | OpenClaw + Clerk agent + Iskander chat widget on Loomio frontend | Planned |
| C.3 | Loomio-bridge skill (full feature integration: decision processes, quorum, tags, tasks, DMs) | Planned |
| C.3b | Document collaboration skill (draft, revise, incorporate feedback, save to Nextcloud) | Planned |

#### Week 2: Decision Loop + Audit Trail

| Task | What | Status |
|------|------|--------|
| C.4 | Decision recorder (Loomio webhook -> PostgreSQL + IPFS pin) | Planned |
| C.5 | Glass Box audit trail (agent action logging + query endpoint) | Planned |
| C.6 | Steward agent (treasury monitoring, threshold-based Loomio proposals) | Planned |
| C.9 | Membership lifecycle (join/leave/onboard, Clerk welcome sequence) | Planned |

#### Week 3: First-Boot + Integration Test

| Task | What | Status |
|------|------|--------|
| C.7 | First-boot wizard (configures all 8 services, provisions accounts, opens browser) | Planned |
| C.8 | End-to-end verification (4 test flows proving the full decision loop) | Planned |

**Phase C delivers**: SSO + Loomio + AI Clerk + Nextcloud + Glass Box + Treasury + Document collaboration + Membership onboarding

---

### Phase B: Loomio-Native Expansion (Weeks 4-8)

#### Week 4-5: Blockchain + ZK Identity + Economic Participation + Values Council

- Deploy smart contracts on Anvil (Constitution.sol, CoopIdentity.sol, MACIVoting.sol)
- Mint Soulbound Tokens (SBTs) for founding members
- Integrate BrightID for proof-of-unique-human (Sybil resistance)
- Deploy MACI ZK voting (compile Circom circuits, trusted setup ceremony)
- Economic participation module (member shares, surplus distribution, asset-locks)
- First 4 Values Council agents (Democracy, Honesty, Equality, Solidarity guardians)
- Production security hardening (CrowdSec, Fail2ban, WAF, audit logging)

#### Week 5-6: Governance Structure + Federation + Education

- Governance module (STV elections via Loomio, delegated voters, term limits, subgroups)
- Federation (MCP server, Liaison agent, cooperative discovery)
- Structured education (proactive Clerk learning pathways, governance training, mentoring)
- Loomio templates for recurring governance processes

#### Week 6-7: Community Impact + Cooperative Website + Email

- Community impact module (SDG tracking, sustainability reporting, environmental monitoring)
- Cooperative website (public Glass Box, membership applications, federation directory, members dashboard)
- Email server (Stalwart + Nextcloud Mail for cooperative email addresses)

#### Week 7-8: Multi-Channel + Complete Values Council + Security Finalisation

- Telegram + Matrix channels for Clerk accessibility
- Complete all 10 Values Council agents
- Security finalisation (optional Cloudflare, container hardening, penetration testing, incident response docs)

**Phase B delivers**: Blockchain anchoring + ZK voting + governance elections + community impact + website + email + federation + 10 Values Council agents + full security hardening

---

### Key Milestones

| Milestone | Description | Target |
|-----------|-------------|--------|
| First Decision | Member creates proposal via Clerk -> Loomio vote -> recorded | Week 2 |
| First Boot | Fresh Ubuntu VM -> cooperative functional in 10 minutes | Week 3 |
| On-Chain | Every decision has a blockchain hash | Week 5 |
| 1 Member 1 Vote | BrightID + SBT + MACI ZK voting deployed | Week 5 |
| Public Website | Cooperative visible to the world | Week 7 |
| Federation | Two cooperatives discover each other | Week 6 |
| Full Stack | Complete cooperative-in-a-box | Week 8 |

---

### ICA Principle Coverage

| Principle | Phase C | Phase B |
|-----------|---------|---------|
| P1: Voluntary and Open Membership | Membership lifecycle, Clerk onboarding | BrightID identity, Credential Translator |
| P2: Democratic Member Control | Loomio voting (Consent, Advice, Consensus) | STV elections, MACI ZK voting, governance module |
| P3: Member Economic Participation | Treasury monitoring | Shares, surplus, patronage, asset-locks |
| P4: Autonomy and Independence | Fully self-hosted | Federation on cooperative terms |
| P5: Education, Training, Information | Values reflection, Clerk guidance | Proactive learning pathways, mentoring |
| P6: Cooperation among Cooperatives | -- | MCP federation, Liaison agent |
| P7: Concern for Community | -- | SDG tracking, sustainability reporting |

---

### Technology Stack

| Layer | Phase C | Phase B Addition |
|-------|---------|-----------------|
| Identity | Authentik (OAuth2/OIDC) | BrightID + CoopIdentity.sol SBTs |
| Decisions | Loomio | + MACIVoting.sol (ZK) |
| AI | OpenClaw + Ollama | + Values Council (10 agents) |
| Files | Nextcloud | + Stalwart (email server) |
| Data | PostgreSQL + IPFS | + Anvil (EVM blockchain) |
| Security | TLS + headers + internal networking | + CrowdSec + WAF + Fail2ban |
| Web | Iskander chat widget on Loomio | + Cooperative website (Caddy) |
| Comms | Loomio Direct Discussions | + Telegram + Matrix/Dendrite |
