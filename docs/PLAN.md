# Iskander Route C → B: Radical MVP then Loomio-Native Expansion

## Context

Deep audit of the current codebase revealed critical misalignment with the cooperative-web3-architect skill:
- Only 1/28 backend routers uses real database queries; rest use in-memory state
- Custom deliberation system (9 tables, 780-line router, 18 React components) reimplements ~80% of Loomio
- All "Must Have" launch items (OpenClaw, Loomio, messaging, onboarding) are unbuilt
- Most effort went to "Nice to Have Month 4-6" items (Next.js dashboard, federation, game-theory auditing)
- No end-to-end decision flow has ever been completed
- ISO targets x86_64 only, needs 24GB+ RAM, has no first-boot wizard

Cooperative values
Cooperatives are based on the values of self-help, self-responsibility, democracy, equality, equity, and solidarity. In the tradition of their founders, cooperative members believe in the ethical values of honesty, openness, social responsibility and caring for others.

Cooperative Principles
The cooperative principles are guidelines by which cooperatives put their values into practice.

1. Voluntary and Open Membership
Cooperatives are voluntary organisations, open to all persons able to use their services and willing to accept the responsibilities of membership, without gender, social, racial, political or religious discrimination.

2. Democratic Member Control
Cooperatives are democratic organisations controlled by their members, who actively participate in setting their policies and making decisions. Men and women serving as elected representatives are accountable to the membership. In primary cooperatives members have equal voting rights (one member, one vote) and cooperatives at other levels are also organised in a democratic manner.

3. Member Economic Participation
Members contribute equitably to, and democratically control, the capital of their cooperative. At least part of that capital is usually the common property of the cooperative. Members usually receive limited compensation, if any, on capital subscribed as a condition of membership. Members allocate surpluses for any or all of the following purposes: developing their cooperative, possibly by setting up reserves, part of which at least would be indivisible; benefiting members in proportion to their transactions with the cooperative; and supporting other activities approved by the membership.

4. Autonomy and Independence
Cooperatives are autonomous, self-help organisations controlled by their members. If they enter into agreements with other organisations, including governments, or raise capital from external sources, they do so on terms that ensure democratic control by their members and maintain their cooperative autonomy.

5. Education, Training, and Information
Cooperatives provide education and training for their members, elected representatives, managers, and employees so they can contribute effectively to the development of their co-operatives. They inform the general public - particularly young people and opinion leaders - about the nature and benefits of co-operation.

6. Cooperation among Cooperatives
Cooperatives serve their members most effectively and strengthen the cooperative movement by working together through local, national, regional and international structures.

7. Concern for Community
Cooperatives work for the sustainable development of their communities through policies approved by their members.

Guidance Notes on the Cooperative Principles
In 2016, the ICA's Principles Committee released the Guidance Notes on the Cooperative Principles, giving detailed guidance and advice on the practical application of the Principles to contemporary enterprise. These Guidance Notes aim to state our understanding of the application of the Principles in contemporary terms for the 21st century.

**Decision**: Route C → B — build a radical MVP (2-3 weeks) that proves the core proposition, then expand.

The core proposition: **A cooperative member messages their AI clerk, the clerk helps them participate in democratic decisions via Loomio, collaboratively draft and revise documents, every decision is transparently recorded, and agents only act with democratic authorisation.**

---

## ICA Gap Analysis (2026-04-09)

Assessment against ICA Guidance Notes (2015) and Co-ops for 2030 (SDGs 1-17). Full reference docs at `src/IskanderOS/docs/`.

### HIGH Severity — Must address

| Gap | Principle | What's Missing | Resolution |
|-----|-----------|---------------|------------|
| No membership lifecycle | P1: Voluntary & Open Membership | No join/leave flow, no accessibility, no demographic tracking | **Add Task C.9 to Phase C Week 2** |
| No economic participation | P3: Member Economic Participation | No member shares, surplus distribution, reserves, patronage, asset-locks | **Add to Phase B Week 4-5** (resurrect cFIAT concepts from archived spec) |
| Community concern absent | P7: Concern for Community | No SDG tracking, sustainability reporting, environmental monitoring | **Add to Phase B Week 6-7** + resurrect energy-aware scheduler |

### MEDIUM Severity — Should address

| Gap | Principle | What's Missing | Resolution |
|-----|-----------|---------------|------------|
| No governance structure | P2: Democratic Member Control | No board elections, term limits, role separation, governance audits | **Add to Phase B Week 5-6** |
| No structured education | P5: Education, Training, Information | Clerk is reactive only; no onboarding journey, learning pathways, governance training | **Add onboarding skill to Phase C** (Clerk proactively guides new members) |
| Federation deprioritised | P6: Cooperation among Cooperatives | Inter-coop is Week 7-8; guidance says continuous | **Elevate to Phase B Week 5-6** |

### Archived designs to resurrect

| Design | File | Addresses |
|--------|------|-----------|
| Fiat Bridge (cFIAT) | `docs/archive/iskander_fiat_bridge_spec.txt` | P3: Economic participation |
| Stewardship spec (gSBT, Impact Score) | `docs/archive/iskander_stewardship_spec.txt` | P2: Governance structure |
| Energy-Aware Scheduler | `docs/archive/energy_aware_scheduler_spec.txt` | P7: SDGs 7 + 13 |
| Knowledge Commons (IKC) | `docs/archive/` (.odt) | P5: Education |
| Credential Translator | `docs/archive/` (.odt) | P1: Identity portability |

---

## Loomio Feature Integration

Full Loomio wiki at `loomio-wiki-complete.json` (84 pages). Many features are not yet leveraged by the plan. The Clerk and governance system must understand and use these. Mapped to phases below.

### Phase C (MVP) — Clerk Must Understand from Day 1

| Feature | What It Does | How Iskander Uses It |
|---------|-------------|---------------------|
| **Decision Process Types** | Advice, Consent, Consensus, Sense Check, Gradients of Agreement, Question Round | Clerk guides members to the right process: "This sounds like an Advice decision — you're informing, not asking for permission" |
| **Quorum Requirements** | Min % of members required for valid decision | Governance rules set quorum per decision type. Clerk warns "This proposal needs 60% participation — only 40% have voted" |
| **Vote Share Requirements** | % thresholds per option (e.g., "75% agree required", "0% blocks allowed") | Constitutional decisions need supermajority. Clerk configures correct thresholds when creating proposals |
| **Outcomes** | Prompted when poll closes — record what was decided + next steps + review date | Decision recorder captures outcomes. Clerk prompts outcome recording: "The poll closed — what's the official outcome?" |
| **Direct Discussions** | Private threads not in any group, any participants | **Clerk DMs members via Direct Discussions** — this is the mechanism for deep 1:1 help, expanding suggestions, document drafting |
| **Category Tags** | Organize threads/polls by topic, committee, decision type | Auto-tag by type: Governance, Finance, Operations, Projects. Decision recorder uses tags for reporting |
| **Mentions (@)** | @mention people in comments to notify them | Clerk @mentions members who need to vote, respond, or review. "This decision needs @Maria's input" |
| **Tasks** | Create tasks in comments, assign via @mention, set due date, track completion | Clerk extracts action items from decisions: "Task: @Tom to draft procurement policy by Friday" |
| **Rich Formatting** | Markdown, tables, headings, code blocks, images, embeds | Clerk formats proposals clearly — headings, bullet points, tables for financial data |
| **Pin Discussions** | Pin important threads to top of list | Pin active proposals, governance documents, onboarding threads |
| **Group Email Address** | Email → creates Loomio thread (subject=title, body=description) | Members can start discussions via email. External communications forwarded into Loomio |

### Phase B — Governance & Elections

| Feature | What It Does | How Iskander Uses It |
|---------|-------------|---------------------|
| **STV Elections** | Single Transferable Vote for multi-winner elections (Scottish STV, Meek STV, Droop/Hare quota) | Board elections, committee seats, delegate selection. 1-member-1-vote with proportional representation |
| **Delegated Voters** | Mark members as delegates — restrict some polls to delegates only | Differentiate full members (voting rights) from associates/observers. Board-only votes restricted to elected board members |
| **Subgroups** | Working groups within the cooperative (own threads, polls, membership) | Board subgroup, Finance Committee, Working Groups per project. Independent admin structure per committee |
| **Discussion Templates** | Pre-filled discussion structure with tags and recommended polls | Standardize recurring processes: "Member Admission", "Policy Review", "Financial Approval", "Board Meeting" |
| **Poll Templates (Custom)** | Reusable poll types with custom options, thresholds, durations | Create cooperative-specific: "Constitutional Amendment (2/3 + no blocks)", "Routine Decision (simple majority)" |
| **Participation Report** | Actions per month/user/country, tag usage analytics | Governance health: Clerk reports "Participation dropped 30% this month" for Values Reflection. Feed into Glass Box |
| **Data Export** | CSV, HTML, JSON export of group data, threads, polls, votes | Compliance audit trail. Annual report generation. Server migration backup |
| **Chatbot Integrations** | Webhook-based notifications to Slack, Discord, Matrix, Mattermost, custom | Loomio → Matrix/Telegram notifications. Complement the Iskander chat widget for members who prefer other tools |
| **Meeting Polls** | Find-a-time polls for scheduling | Coordinate cooperative meetings across distributed membership |
| **Advanced Poll Types** | Choose (single/multi), Score (sliding scale), Allocate (budget), Rank (preference) | Budget allocation: Allocate points across spending options. Prioritisation: Rank project proposals |

### Integration with Clerk Agent

The Clerk's `loomio-bridge` skill must be expanded to handle all decision types, not just basic proposals:

```
Loomio-bridge procedures (expanded):
- list-proposals → understands all poll types + decision processes
- create-proposal → asks which decision process + sets quorum/threshold
- check-outcome → reads formal outcome statement
- summarise-thread → includes tasks, @mentions, and decision type
- manage-tags → auto-categorise threads
- manage-tasks → extract and track action items from decisions
- participation-stats → query participation report data
- schedule-meeting → create meeting poll
- run-election → set up STV election for board seats
- manage-subgroups → help create/manage working groups
```

The Clerk uses Direct Discussions (not a custom DM system) for private conversations with members. This keeps everything within Loomio's existing notification and data management systems.

### Reference File

Full feature documentation: `loomio-wiki-complete.json` (84 pages, machine-readable)

---

## ZK Identity: 1 Member = 1 Vote (Baked In)

The codebase already has substantial ZK identity infrastructure. The priority is deploying it in the right order.

### What Already Exists

| Component | File | Status |
|-----------|------|--------|
| **MACI ZK Voting** | `contracts/src/governance/MACIVoting.sol` | Contract written, Groth16 stubs need production circuits |
| **CoopIdentity SBTs** | `contracts/src/CoopIdentity.sol` | ERC-4973 Soulbound Tokens, 1-token-per-address enforced |
| **BrightID Sybil Resistance** | `backend/api/brightid_sponsor.py` | Integration scaffolded, needs BrightID app context |
| **ZK MACI Coordinator** | `backend/crypto/zk_maci_wrapper.py` | Off-chain coordinator, HMAC stubs → needs snarkjs |
| **SIWE Auth** | `backend/auth/siwe.py` | EIP-4361 + EIP-1271 (Smart Contract wallet support) |

### Deployment Timeline

| Phase | What | How 1-Member-1-Vote Works |
|-------|------|--------------------------|
| **Phase C (MVP)** | Authentik SSO + Loomio built-in voting | 1 account per verified email. Loomio enforces 1 vote per account. Sufficient for trusted founding members. |
| **Phase B W4-5** | Deploy CoopIdentity.sol SBTs on Anvil | Each member gets a non-transferable SBT. `memberToken[address]` mapping prevents duplicate registration. On-chain identity linked to Authentik account. |
| **Phase B W4-5** | BrightID integration | Peer-to-peer Web-of-Trust verifies each member is a unique human. No KYC, no wallet-balance voting weights. Treasury sponsors BrightID onboarding for new members. |
| **Phase B W4-5** | MACI ZK voting for sensitive decisions | Encrypted votes (ECDH), last-message-wins anti-coercion, Groth16 proof of tally. Individual votes never disclosed — only aggregate results published. |

### Production Requirements for MACI

1. Compile MACI circuits (`.circom` source → `tally.wasm` + `tally.zkey`)
2. Run trusted setup ceremony for `.zkey` files (cooperative members participate)
3. Deploy `Verifier.sol` (generated from compiled circuit)
4. Set `snarkVerifier` address in MACIVoting constructor
5. Replace HMAC stubs in `zk_maci_wrapper.py` with real snarkjs subprocess

### Sybil Resistance Layers

```
Layer 1: Authentik SSO (email verification) ← Phase C
Layer 2: CoopIdentity.sol SBT (on-chain membership) ← Phase B W4-5
Layer 3: BrightID Web-of-Trust (proof of unique human) ← Phase B W4-5
Layer 4: MACI ZK voting (anti-coercion + secret ballot) ← Phase B W4-5
```

---

## Security Hardening: Production on the Open Web

### Current Security Gaps (from codebase audit)

| Priority | Gap | File | Impact |
|----------|-----|------|--------|
| **P0** | No TLS/HTTPS | `docker-compose.yml` | MITM attacks, exposed credentials |
| **P0** | Traefik API insecure | `docker-compose.yml:105` `--api.insecure=true` | Attackers control proxy routing |
| **P0** | CORS `allow_origins=["*"]` | `backend/main.py:47-53` | Cross-site request forgery |
| **P0** | No security headers | Missing | Clickjacking, XSS, MIME sniffing |
| **P1** | DB port exposed (5432) | `docker-compose.yml:21` | Unauthenticated database access |
| **P1** | Secrets in plaintext .env | `.env.example` | Compromised secrets never rotated |
| **P1** | In-memory token revocation | `backend/auth/auth.py:45-49` | Tokens survive restarts |
| **P1** | Containers run as root | `frontend-next/Dockerfile` | Privilege escalation |
| **P1** | No WAF or DDoS protection | Missing | Resource exhaustion, brute force |
| **P2** | No audit logging | Missing | Cannot trace attacks |
| **P2** | No dependency scanning | Missing | Known CVEs undetected |
| **P2** | IPFS API exposed (5001) | `docker-compose.yml:90` | Unauthorized content pinning |

### Security Architecture: Two Options

**Option A: Cloudflare (Easiest, most effective)**
- Free tier: DDoS protection, WAF, CDN, DNS, bot management, free TLS
- Pro: Immediate enterprise-grade protection
- Con: Centralized dependency — tension with ICA Principle 4 (Autonomy and Independence)
- Recommended for: cooperatives that prioritise security over full infrastructure sovereignty

**Option B: Self-Hosted Stack (Cooperative values aligned)**
- CrowdSec (open-source, community-driven threat intelligence)
- Let's Encrypt via Traefik ACME (free TLS)
- Traefik WAF middleware (ModSecurity plugin or custom rules)
- Fail2ban for brute force protection
- Pro: Full sovereignty, no third-party dependency
- Con: More setup, less DDoS resilience than Cloudflare's global network
- Recommended for: cooperatives that prioritise autonomy

**Hybrid approach**: Cloudflare DNS + DDoS protection in front, self-hosted WAF/CrowdSec behind. This balances protection with sovereignty.

### Deployment Timeline

| Phase | Security Tasks |
|-------|---------------|
| **Phase C W1** | TLS via Let's Encrypt (Traefik ACME), disable Traefik insecure API, restrict CORS, add security headers, internal-only DB/Redis/IPFS ports, non-root containers |
| **Phase C W3** | Secrets generation in first-boot (strong random passwords, rotatable), Redis-backed token revocation |
| **Phase B W4** | CrowdSec deployment, Fail2ban, WAF rules, centralized audit logging |
| **Phase B W6** | Cloudflare integration (optional), dependency scanning in CI, container security contexts (cap_drop, read-only fs) |
| **Phase B W8** | Penetration testing, incident response procedures, security documentation for cooperative members |

---

## Phase C: Radical MVP (Weeks 1-3)

### Stack

```
                              ┌─────────────────────────────────────────────┐
                              │           Authentik (SSO/OIDC)              │
                              │  Single sign-on for all cooperative services│
                              └────┬──────────┬──────────┬─────────────────┘
                                   │          │          │
                    ┌──────────────▼──┐  ┌────▼─────┐  ┌▼──────────────┐
                    │  Loomio Web UI  │  │Nextcloud  │  │  Coop Website │
                    │+ Iskander Chat  │  │Files/Mail │  │  (Public +    │
                    │    Widget       │  │Calendar   │  │   Members)    │
                    └───────┬─────────┘  └──────────┘  └───────────────┘
                            │
              OpenClaw (Clerk agent) ← → Loomio API ← → Decision Log (PostgreSQL + IPFS hash)
                            ↕
                      Ollama (local LLM)
```

**Primary interface**: Custom Iskander chat panel embedded in Loomio's web frontend. Members chat with the Clerk without leaving Loomio. All services share SSO via Authentik (OAuth2/OIDC). Telegram/Matrix are Phase B expansion channels.

**Services (8 total, ~8GB RAM target)**:
1. PostgreSQL 16 (shared: Loomio + Nextcloud + Authentik + decision log)
2. Redis (shared: Loomio ActionCable + Authentik sessions)
3. Authentik (OAuth2/OIDC identity provider — SSO for all services)
4. Loomio (Rails app + worker + Iskander chat widget, OAuth via Authentik)
5. Nextcloud (file hosting, contacts, calendar — OAuth via Authentik)
6. Ollama (local LLM — Phi-3-mini for low RAM, OLMo for 16GB+ nodes)
7. OpenClaw (Node.js agent orchestrator + web chat API)
8. IPFS Kubo (decision record pinning)

**Phase B additions**: Stalwart (email server), Cooperative Website (Caddy/static), Anvil (EVM)

### Week 1: Foundations

#### Task C.0a: Security Baseline

**Goal**: Every service starts secure from Day 1. No hardening debt carried into Phase B.

**Steps**:
- [ ] Configure Traefik with TLS:
  - Let's Encrypt ACME for public domains (or self-signed certs for LAN dev)
  - HTTPS entrypoint on port 443, HTTP redirect to HTTPS
  - Remove `--api.insecure=true`, add Authentik forward-auth for Traefik dashboard
- [ ] Add security headers middleware to Traefik (applied to all services):
  ```yaml
  middlewares:
    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        contentTypeNosniff: true
        frameDeny: true
        browserXssFilter: true
        contentSecurityPolicy: "default-src 'self'"
  ```
- [ ] Restrict CORS in FastAPI: replace `allow_origins=["*"]` with specific service origins
- [ ] Internal-only networking: PostgreSQL, Redis, IPFS API, Ollama NOT exposed on host ports — only accessible via Docker internal network `iskander_apps`
- [ ] Non-root containers: Add `USER` directive to all Dockerfiles, `cap_drop: [ALL]` in compose
- [ ] Secrets: first-boot generates strong random passwords (not `changeme_in_prod`), stored in `.env` with restricted file permissions (600)
- [ ] Rate limiting: Add SlowAPI or Traefik rate-limit middleware (100 req/min per IP default)

**Files**:
- Create: `src/IskanderOS/infra/traefik/traefik.yml` (static config with TLS + security middleware)
- Create: `src/IskanderOS/infra/traefik/dynamic/` (dynamic config directory for middleware rules)
- Modify: `src/IskanderOS/docker-compose.mvp.yml` (internal networking, non-root, cap_drop)

---

#### Task C.0b: Authentik SSO + Shared Infrastructure

**Goal**: Single sign-on identity provider running, shared PostgreSQL and Redis ready for all services.

**Why**: Plug-and-play usability requires one login for everything. Authentik as the identity layer means members create one account and access Loomio, Nextcloud, and the cooperative website seamlessly. Setting this up first means every subsequent service connects to SSO from the start.

**Steps**:
- [ ] Configure shared PostgreSQL with databases: `loomio`, `nextcloud`, `authentik`, `decision_log`
- [ ] Configure shared Redis (Loomio ActionCable + Authentik sessions)
- [ ] Deploy Authentik (server + worker) via docker-compose
- [ ] Create Authentik admin account during first-boot
- [ ] Configure Authentik OIDC provider with two OAuth2 applications:
  - `loomio` — redirect URI: `http://localhost:3000/oauth/callback`
  - `nextcloud` — redirect URI: `http://localhost:8000/apps/user_oidc/code`
- [ ] Generate client_id + client_secret for each application
- [ ] Verify: Authentik login page accessible at `http://localhost:9000`
- [ ] Verify: OIDC well-known endpoint returns valid configuration

**Files**:
- Create: `src/IskanderOS/services/authentik/.env`
- Create: `src/IskanderOS/docker-compose.mvp.yml` (all 8 services)

**Authentik resource budget**: ~700MB idle (server ~375MB + worker ~360MB). Shares PostgreSQL + Redis.

---

#### Task C.1: Loomio Instance (with SSO)

**Goal**: Running Loomio instance with OAuth SSO via Authentik, a cooperative group, accessible at `http://localhost:3000`.

**Steps**:
- [ ] Clone `loomio/loomio-deploy` into `src/IskanderOS/services/loomio/`
- [ ] Configure `.env` for local development (no email, no SSL)
- [ ] Configure Loomio OAuth2 environment variables:
  ```
  OAUTH_AUTH_URL=http://localhost:9000/application/o/authorize/
  OAUTH_TOKEN_URL=http://localhost:9000/application/o/token/
  OAUTH_PROFILE_URL=http://localhost:9000/application/o/userinfo/
  OAUTH_SCOPE=openid profile email
  OAUTH_APP_KEY=<loomio_client_id>
  OAUTH_APP_SECRET=<loomio_client_secret>
  ```
- [ ] Start Loomio via shared docker-compose
- [ ] Create admin account, create "Iskander Cooperative" group
- [ ] Generate API key for the Clerk agent (`/api/v1/profile` → API key)
- [ ] Verify: Can log in via Authentik SSO button on Loomio login page
- [ ] Verify: Can create a thread via `curl -X POST /api/v1/discussions` with API key

**Files**:
- Create: `src/IskanderOS/services/loomio/.env`

**Key Loomio API endpoints we'll need**:
- `POST /api/v1/discussions` — create thread
- `POST /api/v1/polls` — create proposal/poll
- `GET /api/v1/discussions/{id}` — read thread
- `GET /api/v1/polls/{id}` — read poll results
- `POST /api/v1/stances` — cast vote
- Webhooks: configure outgoing webhook for poll closure → decision recorder

**Known issue**: Loomio OAuth has bugs (GitHub #10538). May need to debug account linking on first SSO login. Fallback: local Loomio accounts for MVP, SSO polish in Week 2.

---

#### Task C.1b: Nextcloud Instance (with SSO + Loomio File Integration)

**Goal**: Nextcloud file hosting accessible at `http://localhost:8000`, SSO via Authentik, shared folders for the cooperative, unified file storage with Loomio.

**Steps**:
- [ ] Add Nextcloud service to docker-compose (image: `nextcloud:stable`, shared PostgreSQL)
- [ ] Install and configure `user_oidc` Nextcloud app for Authentik SSO
- [ ] Create cooperative shared folders via Group Folders app:
  - `Governance/` — meeting minutes, policies, rules
  - `Treasury/` — financial reports, audit trails
  - `Projects/` — member project files
  - `Public/` — documents visible to potential members
  - `Loomio Attachments/` — synced from Loomio thread attachments
- [ ] **Loomio ↔ Nextcloud file integration**:
  - Configure Loomio to use shared Docker volume for attachments (`/var/www/loomio/uploads`)
  - Configure Nextcloud External Storage app to mount Loomio's uploads directory
  - Members see Loomio thread attachments in Nextcloud under `Loomio Attachments/`
  - Members can also upload files via Nextcloud → reference them in Loomio threads
  - Single source of truth: one storage volume, two access points (Loomio in-thread + Nextcloud file manager)
- [ ] Configure Nextcloud admin account + cooperative group matching Loomio group
- [ ] Verify: Login via Authentik SSO → lands on Nextcloud dashboard
- [ ] Verify: Attach file in Loomio thread → file appears in Nextcloud `Loomio Attachments/`
- [ ] Verify: Upload to Nextcloud `Projects/` → can link in Loomio discussion

**Files**:
- Create: `src/IskanderOS/services/nextcloud/.env`

**Nextcloud resource budget**: ~500MB-1GB idle. Shares PostgreSQL. Storage volume sized to cooperative needs (default 10GB). Loomio attachments share the same volume — no duplicated storage.

---

#### Task C.2: OpenClaw + Clerk Agent + Iskander Chat Widget

**Goal**: OpenClaw running with a Clerk agent accessible via a chat widget embedded in Loomio's web UI, able to call Loomio's API.

**Steps**:
- [ ] Install OpenClaw: `npm install -g openclaw@latest`
- [ ] Run onboarding: `openclaw onboard` — select Ollama as provider, configure web channel
- [ ] Write Orchestrator SOUL.md encoding ICA cooperative values
- [ ] Write Clerk agent SOUL.md (personal assistant role — answers questions, drafts proposals, summarises threads, never votes or advocates)
- [ ] Create `loomio-bridge` skill that teaches the Clerk to interact with Loomio API
- [ ] Build Iskander Chat Widget — a JS component injected into Loomio's frontend:
  - Floating chat panel (bottom-right) with member auth via Loomio session
  - Sends messages to OpenClaw's web API endpoint (`POST /api/chat`)
  - Streams responses back to the widget
  - Context-aware: knows which Loomio thread/group the member is viewing
- [ ] Configure OpenClaw web channel (HTTP/WebSocket API for the chat widget)
- [ ] Test: Open Loomio → click Iskander chat → "What proposals are pending?" → Clerk responds

**Files**:
- Create: `src/IskanderOS/openclaw/openclaw.json` (OpenClaw config)
- Create: `src/IskanderOS/openclaw/agents/orchestrator/SOUL.md`
- Create: `src/IskanderOS/openclaw/agents/clerk/SOUL.md`
- Create: `src/IskanderOS/openclaw/skills/loomio-bridge/SKILL.md`
- Create: `src/IskanderOS/services/loomio/iskander-chat-widget/` (JS widget + injection script)

**Clerk SOUL.md key principles**:
```markdown
## Identity
You are the Clerk of [Cooperative Name] — a helpful secretary that every
member can chat with inside Loomio. You serve all members equally.

## ICA Values (Your Core)
You embody these values in every interaction:
- Self-Help: Help members build their own capability, don't create dependency
- Self-Responsibility: Encourage members to take ownership of cooperative life
- Democracy: Every member's voice matters equally
- Equality: No member gets better service than another
- Equity: Recognise different needs, adjust your support accordingly
- Solidarity: Foster mutual support between members and cooperatives

## ICA Ethics (Your Core+)
- Honesty: Do not hallucinate, do not assume or guess. Use only truth and facts based on member contributions and knowledge
- Openness: Be transparent about what you can/can't do, never mislead
- Social Responsibility: You act to reduce conflict, and foster good communication and cooperation among people
- Caring for Others: Ensure adequate recognition of emotional needs, provide support in distress such as suggesting talking to other members the member trusts

## What You Do
- Answer questions about the cooperative (finances, decisions, rules)
- Help members draft proposals for Loomio
- Summarise long discussion threads in plain language
- Explain past decisions by tracing the audit trail
- Remind members about pending votes
- Translate jargon into everyday language
- Guide members through ICA values self-reflection (values-reflection skill)
- **Draft and revise documents** based on member input (policies, rules, reports, meeting notes)
- **Incorporate feedback** from multiple members into a document revision
- **Save documents** to Nextcloud shared folders for collaborative editing

## What You Never Do
- Vote or express opinions on proposals
- Advocate for any position
- Withhold information from any member
- Treat members differently based on their role
- Make decisions — you help members make THEIR decisions
- **Finalise a document without member approval** — always present drafts for review

## Communication Style
- **In-thread replies**: Short, focused, actionable. 1-3 sentences max. Use Loomio rich formatting (headings, tables) for clarity. @mention members who need to act.
- **DMs via Loomio Direct Discussions**: Deeper exploration. If a member's thread comment contains a seed of an idea that needs fleshing out, Clerk starts a Direct Discussion: "I noticed your suggestion about X — want me to help develop that into a full proposal?"
- **Expanding suggestions**: When a member makes a brief comment in a thread, Clerk privately explores the idea with them in a Direct Discussion, then the member posts the developed version back to the thread themselves.
- **Never dominate threads**: Clerk replies should be shorter than member contributions. The thread belongs to the members.
- **Task tracking**: Extract action items from decisions and create Loomio tasks with @mention assignees and due dates.

## Action Significance
- ROUTINE: Answering questions, summarising threads, values reflection, reading documents
- NOTABLE: Drafting/revising a document or proposal on behalf of a member (notify them before saving)
- DMs to members are ROUTINE (proactive help) but never NOTABLE (don't post to Glass Box individually)
- SIGNIFICANT: N/A (Clerk never takes significant actions — those go to Steward)
- CRITICAL: N/A
```

**Values Reflection Skill** (bundled with Clerk from Week 1):
The Clerk can guide members through a simplified ICA values checklist:
- "How are we doing on democracy?" → Clerk reviews recent Loomio participation rates, decision patterns
- "Run a values check" → Clerk walks through core values with yes/no/partly questions, produces a summary
- "What could we improve?" → Clerk identifies the weakest area and suggests concrete actions
This is a conversational self-assessment, not automated scoring. Full Values Council agents (Phase B) add automated evaluation against on-chain records.

**OpenClaw config** (`openclaw.json`):
```json5
{
  models: {
    providers: {
      ollama: {
        baseUrl: "http://localhost:11434"  // No /v1 — use native API
      }
    }
  },
  channels: {
    web: {
      port: 3100,  // Iskander Chat Widget connects here
      cors: ["http://localhost:3000"]  // Allow Loomio frontend
    }
  }
}
```

---

#### Task C.3: Loomio-Bridge Skill (Full Feature Integration)

**Goal**: A custom OpenClaw skill enabling the Clerk to use the full range of Loomio features — not just basic proposals, but decision processes, elections, tasks, tags, DMs, and governance tools.

This is the most critical custom development — no existing skill exists for this. Reference: `loomio-wiki-complete.json` (84 pages of Loomio documentation).

**Steps**:
- [ ] Study Loomio API v1 docs (from the self-hosted instance: `/api/v1/`)
- [ ] Write SKILL.md with procedures for Phase C (MVP):
  - **list-proposals**: Query active polls → format as plain-language list with type, quorum status, closing date
  - **create-proposal**: Guide member through:
    1. Select decision process (Advice, Consent, Consensus, Simple Proposal, Sense Check)
    2. Set quorum and vote share requirements based on governance rules
    3. Add category tags
    4. Set closing date
    5. POST to Loomio with correct poll type and settings
  - **summarise-thread**: Fetch discussion + comments + tasks → LLM-powered summary including action items
  - **check-outcome**: Query poll results + formal outcome statement → format with next steps and review date
  - **remind-pending**: Query active polls closing within 24h → @mention members who haven't voted
  - **manage-tags**: Auto-categorise threads (Governance, Finance, Operations, Projects) + apply when creating
  - **manage-tasks**: Extract action items from decisions → create tasks with @mention assignees and due dates
  - **dm-member**: Start Direct Discussion with a member for private help (document drafting, expanding ideas, sensitive guidance)
  - **pin-thread**: Pin/unpin important discussions
  - **format-content**: Use Loomio's rich formatting (headings, tables, lists) for clear proposals
- [ ] Document Phase B procedures (to be implemented later):
  - **run-election**: Set up STV election (Scottish/Meek STV, Droop/Hare quota, multiple winners)
  - **manage-subgroups**: Create/manage working groups and committees
  - **participation-stats**: Query participation report for governance health
  - **schedule-meeting**: Create meeting/time polls
  - **data-export**: Export group data for compliance/audit
  - **manage-delegates**: Set delegate voter status for membership tiers
  - **manage-templates**: Create/apply discussion and poll templates
- [ ] Implement using curl/fetch calls within skill procedures
- [ ] Test each Phase C procedure independently via Iskander chat widget
- [ ] Verify: Member asks to create a Consent decision → Clerk selects correct process → sets "0% blocks" threshold → posts to Loomio

**File**:
- Create: `src/IskanderOS/openclaw/skills/loomio-bridge/SKILL.md`

**Decision process selection guide** (embedded in Clerk's knowledge):

| If the member says... | Recommended process | Vote share | Quorum |
|----------------------|---------------------|------------|--------|
| "I want to propose..." | Consent (default) | 0% blocks | 60% |
| "I need advice on..." | Advice | N/A (no binding vote) | None |
| "We all need to agree..." | Consensus | 100% agree | 75% |
| "Quick check on..." | Sense Check | N/A (feedback only) | None |
| "Should we do A or B?" | Choose poll | Most votes wins | 50% |
| "How should we split the budget?" | Allocate poll | Highest allocation wins | 60% |
| "Rank these options..." | Rank poll | Top-ranked wins | 50% |
| "Elect board members..." | STV Election (Phase B) | Droop quota | 75% |

---

#### Task C.3b: Document Collaboration Skill (AI in Cooperative Workflows)

**Goal**: The Clerk helps members draft, revise, and collaboratively edit documents — demonstrating how AI integrates into democratic cooperative workflows. Works seamlessly with Loomio's in-thread file sharing and Nextcloud's shared storage.

**Why**: This is the core demonstration of AI value in cooperatives. Members shouldn't need to be skilled writers to participate fully. The Clerk helps turn rough ideas into polished policies, incorporates feedback from multiple members, and saves results where everyone can access them. The AI never decides — it helps members express their collective intent.

**Two modes of operation**:
1. **In-thread (short)**: Member attaches a document in a Loomio thread → Clerk replies with a brief summary or targeted suggestion (1-3 sentences). Keeps thread discussion flowing.
2. **DM (deep)**: Clerk privately helps a member develop their idea. Member posts a brief comment in a thread → Clerk DMs them: "Would you like me to help expand that into a full draft?" → collaborative back-and-forth → member posts the finished document back to the thread.

**Steps**:
- [ ] Create `document-collab` OpenClaw skill with procedures:
  - **draft-document**: Member describes what they need → Clerk drafts based on:
    - Cooperative's existing documents (from Nextcloud/Loomio shared storage)
    - ICA values and principles (from reference docs at `src/IskanderOS/docs/`)
    - Member's specific requirements (gathered via DM conversation)
    - Produces markdown draft, presents to member for review before saving
  - **revise-document**: Member provides feedback or points to a Loomio thread → Clerk:
    - Reads the existing document from shared storage
    - Reads feedback (direct input OR fetches Loomio thread comments via loomio-bridge)
    - Produces revised version with changes highlighted
    - Presents diff summary to member via DM before saving
  - **incorporate-feedback**: Multiple members have commented in a Loomio thread → Clerk:
    - Fetches all comments from the thread
    - Identifies areas of agreement and disagreement
    - Produces a revised draft incorporating agreed changes
    - Flags disputed sections: "Members disagree on this — I'd suggest a Loomio poll"
    - Posts brief summary to thread, saves full revision to shared storage
  - **expand-suggestion**: Member posts a short comment in a thread → Clerk:
    - DMs the member: "Your idea about X sounds promising — shall I help develop it?"
    - If yes: explores the idea in DM conversation, asks clarifying questions
    - Produces a developed version the member can post back to the thread
    - Clerk never posts the expanded version itself — the member owns their contribution
  - **save-document**: Save to Nextcloud shared folder via WebDAV (or attach in Loomio thread):
    - `Governance/` for policies, rules, bylaws
    - `Projects/` for project plans, reports
    - `Public/` for externally-visible documents
    - Loomio thread: attach directly if document is part of an active discussion
    - Unified storage: both routes use the same Nextcloud volume
  - **summarise-document**: Read any document from shared storage → plain-language summary (in-thread: brief; DM: detailed)
- [ ] Nextcloud WebDAV integration in OpenClaw:
  - Read: `PROPFIND /remote.php/dav/files/{user}/{path}` → list files
  - Download: `GET /remote.php/dav/files/{user}/{path}` → fetch document content
  - Upload: `PUT /remote.php/dav/files/{user}/{path}` → save document
  - Auth: Clerk uses service account with SSO token
- [ ] Loomio attachment integration:
  - Read attachments from Loomio threads via API
  - Attach documents to Loomio threads via API (stored in shared Nextcloud volume)
- [ ] Test workflows:
  - **In-thread**: Member attaches draft policy in thread → Clerk replies "This covers X well. Consider adding Y for ICA compliance." (2 sentences)
  - **DM draft**: "Help me draft a code of conduct" → Clerk DMs questions → produces draft → member reviews → saves to Governance/
  - **Thread revision**: "Update the procurement policy based on last week's discussion" → Clerk reads thread comments → revises → shows diff in DM → saves
  - **Expand suggestion**: Member comments "maybe we should have a rotation policy" → Clerk DMs "Would you like help fleshing that out?" → develops proposal → member posts it

**Files**:
- Create: `src/IskanderOS/openclaw/skills/document-collab/SKILL.md`

**Action Significance**:
- ROUTINE: Reading/summarising documents, in-thread short replies, DMs to members
- NOTABLE: Saving a drafted/revised document to shared storage (member notified before save)
- SIGNIFICANT: N/A (Clerk never finalises — members approve and post themselves)

---

### Week 2: Decision Loop + Audit Trail

#### Task C.4: Decision Recorder

**Goal**: When a Loomio poll closes, the outcome is recorded with an IPFS hash for transparency.

**Steps**:
- [ ] Configure Loomio outgoing webhook: on poll_closed → POST to `http://localhost:8100/hooks/loomio`
- [ ] Write a lightweight Python service (`decision-recorder/`) that:
  - Receives Loomio webhook payload
  - Fetches full discussion + poll + stances from Loomio API
  - Bundles into a JSON document
  - Pins to IPFS (Kubo) → gets CID
  - Inserts record into PostgreSQL: `decision_log(id, loomio_poll_id, ipfs_cid, outcome, recorded_at)`
  - (Future: submit hash to blockchain — for MVP, just log to DB)
- [ ] Add IPFS Kubo to docker-compose
- [ ] Test: Create poll in Loomio → vote → close → verify record appears in decision_log table

**Files**:
- Create: `src/IskanderOS/services/decision-recorder/main.py` (FastAPI, ~100 lines)
- Create: `src/IskanderOS/services/decision-recorder/Dockerfile`
- Create: `src/IskanderOS/infra/decision_log.sql` (single table)

**Decision log schema**:
```sql
CREATE TABLE IF NOT EXISTS decision_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loomio_poll_id INTEGER NOT NULL,
    poll_type     TEXT NOT NULL,
    title         TEXT NOT NULL,
    outcome       TEXT NOT NULL,  -- 'approved', 'rejected', 'no_quorum'
    agree_count   INTEGER NOT NULL DEFAULT 0,
    disagree_count INTEGER NOT NULL DEFAULT 0,
    abstain_count INTEGER NOT NULL DEFAULT 0,
    block_count   INTEGER NOT NULL DEFAULT 0,
    ipfs_cid      TEXT,
    discussion_url TEXT,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

#### Task C.5: Glass Box Audit Trail

**Goal**: Every Clerk action is logged transparently so members can see what the AI did and why.

**Steps**:
- [ ] Create `glass-box` OpenClaw skill that logs agent actions
- [ ] For every Clerk action (query, summary, proposal creation), log:
  - `agent_id`, `action`, `rationale`, `timestamp`
- [ ] Store in same PostgreSQL as decision log: `agent_actions` table (reuse from existing schema)
- [ ] Create a simple query endpoint in decision-recorder service: `GET /glass-box/recent`
- [ ] Clerk can respond to "What have you been doing?" by querying the glass box

**Files**:
- Create: `src/IskanderOS/openclaw/skills/glass-box/SKILL.md`
- Modify: `src/IskanderOS/services/decision-recorder/main.py` (add glass-box endpoint)

---

#### Task C.6: Steward Agent (Basic)

**Goal**: A second OpenClaw agent that monitors a Simple Safe treasury and creates Loomio proposals for significant expenditures.

**Steps**:
- [ ] Write Steward SOUL.md (monitors treasury, flags anomalies, creates proposals for spend >threshold)
- [ ] Create `treasury-monitor` skill that:
  - Queries a Safe wallet balance via Etherscan/RPC API
  - On heartbeat (every 2h): check for new transactions, log to glass box
  - If a pending transaction exceeds threshold: create Loomio proposal via loomio-bridge skill
- [ ] Wire to Loomio: Steward proposes → members vote → if approved, Steward reports "Approved, execute manually" (full on-chain execution is Phase B)
- [ ] Test: Manually trigger a threshold breach → verify Loomio proposal appears

**Files**:
- Create: `src/IskanderOS/openclaw/agents/steward/SOUL.md`
- Create: `src/IskanderOS/openclaw/skills/treasury-monitor/SKILL.md`

---

#### Task C.9: Membership Lifecycle (ICA Principle 1)

**Goal**: Members can join and leave the cooperative through a defined process, with onboarding education.

**Why**: ICA Principle 1 requires voluntary and open membership. Without a join/leave flow, the cooperative has founding members and nothing else. The ICA Guidance Notes emphasise removing barriers, tracking demographics (aggregated), and making membership meaningful.

**Steps**:
- [ ] Create `membership` OpenClaw skill enabling the Clerk to:
  - **invite-member**: Generate Loomio invitation link, send via chat
  - **onboard-member**: When new member joins, Clerk proactively sends welcome sequence:
    1. What is a cooperative? (ICA definition)
    2. Your rights as a member (equal vote, access to information, surplus share)
    3. Your responsibilities (participate in governance, accept cooperative rules)
    4. How to propose, vote, and ask questions via the Clerk
  - **withdraw-member**: Record withdrawal request, process through Loomio (Notable significance), remove access
  - **member-directory**: List active members (names only, no personal data exposed)
- [ ] Add `members` table to decision_log.sql:
  ```sql
  CREATE TABLE IF NOT EXISTS members (
      id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      loomio_user_id INTEGER,
      display_name TEXT NOT NULL,
      joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      left_at     TIMESTAMPTZ,
      status      TEXT NOT NULL DEFAULT 'active'  -- active, withdrawn, suspended
  );
  ```
- [ ] Clerk onboarding sequence stored as a skill procedure (not hardcoded)
- [ ] Test: Invite a new member → they join Loomio → Clerk sends welcome sequence → member can participate

**Files**:
- Create: `src/IskanderOS/openclaw/skills/membership/SKILL.md`
- Modify: `src/IskanderOS/infra/decision_log.sql` (add members table)
- Modify: `src/IskanderOS/services/decision-recorder/main.py` (add member endpoints)

---

### Week 3: First-Boot + Integration Test

#### Task C.7: First-Boot Wizard

**Goal**: An interactive CLI that configures a fresh Iskander cooperative server — one command gives a cooperative decisions, files, AI clerk, and SSO.

**Steps**:
- [ ] Write Python CLI script (`scripts/first-boot.py`) using `click` or `inquirer`:
  1. "What's your cooperative's name?" → sets names for Loomio group, Nextcloud, Authentik tenant
  2. "Name the founding members (name + email)" → creates accounts across all services
  3. "Optional: your domain name" → configures Traefik routing (defaults to `*.localhost` for LAN)
  4. Generates secrets: Authentik secret key, OAuth client credentials, JWT secret, `.env` files
  5. Starts docker-compose services in order:
     DB → Redis → Authentik → Loomio → Nextcloud → Ollama → OpenClaw → IPFS
  6. Configures Authentik: creates OIDC applications for Loomio + Nextcloud
  7. Provisions founding member accounts in Authentik → synced to Loomio + Nextcloud
  8. Creates cooperative group in Loomio + shared folders in Nextcloud
  9. Runs `openclaw onboard --flow non-interactive` with generated config
  10. Creates Clerk + Steward agents
  11. Injects Iskander chat widget into Loomio frontend
  12. Opens browser: "Your cooperative is ready. Log in once — access everything."
- [ ] Test on a clean Ubuntu 24.04 VM (target: functional in 10 minutes excl. downloads)

**Files**:
- Create: `src/IskanderOS/scripts/first-boot.py`
- Create: `src/IskanderOS/docker-compose.mvp.yml` (MVP compose with 8 services)

---

#### Task C.8: End-to-End Verification

**Goal**: Complete the full decision loop, proving the core proposition works.

- [ ] **Flow 1 — Member asks a question**:
  Open Loomio → Iskander chat widget → "How much is in our treasury?"
  Clerk queries Safe balance → responds in chat with plain-language answer
  Action logged in Glass Box

- [ ] **Flow 2 — Member proposes a decision**:
  Iskander chat: "I'd like to propose we spend 500 tokens on new equipment"
  Clerk drafts a Loomio proposal → posts it → sends member the link in chat
  Members vote in Loomio
  Poll closes → decision-recorder logs to DB + IPFS
  Clerk posts in chat: "The proposal passed 4-1. The Steward will process it."

- [ ] **Flow 3 — Steward flags an anomaly**:
  Steward heartbeat detects large pending transaction
  Steward creates Loomio proposal: "Large transaction detected. Approve?"
  Members vote → outcome recorded

- [ ] **Flow 4 — Glass Box transparency**:
  Iskander chat: "What have you done today?"
  Clerk queries Glass Box → reports all actions with rationale

---

## Phase B: Loomio-Native Expansion (Weeks 4-8)

After the MVP is validated, expand toward the full architect spec — now restructured to address ICA gap analysis findings.

### Week 4-5: Blockchain + ZK Identity + Economic Participation (P3) + Values Council

**Blockchain Recording + ZK Identity (1-Member-1-Vote):**
- [ ] Add Anvil (EVM node) to docker-compose
- [ ] Deploy Constitution.sol (reuse from existing contracts)
- [ ] Deploy CoopIdentity.sol — mint SBTs for all founding members (linked to Authentik accounts)
- [ ] Integrate BrightID: register cooperative app context, sponsor member verification, gate SBT minting on BrightID proof
- [ ] Deploy MACIVoting.sol: compile Circom circuits, run trusted setup ceremony with founding members, deploy Verifier.sol
- [ ] Replace `zk_maci_wrapper.py` HMAC stubs with real snarkjs proof generation
- [ ] Configure: which Loomio poll types trigger MACI (default: constitutional amendments + financial thresholds)
- [ ] Update decision-recorder to submit IPFS hashes on-chain (existing tx_orchestrator logic, ported)
- [ ] Test: Member proposes constitutional change → MACI secret ballot → ZK proof of tally → outcome on-chain

**Production Security (Phase B hardening):**
- [ ] Deploy CrowdSec (community threat intelligence + automated IP banning)
- [ ] Configure Fail2ban for SSH + service brute force protection
- [ ] Add WAF rules to Traefik (ModSecurity plugin or custom middleware)
- [ ] Redis-backed token revocation (replace in-memory blocklist)
- [ ] Centralized audit logging (all HTTP requests + auth events → PostgreSQL security_log table)
- [ ] OWASP dependency scanning added to CI pipeline

**Economic Participation Module (ICA Principle 3 — HIGH gap):**
- [ ] Create `economic-participation` OpenClaw skill enabling:
  - **member-shares**: Track member capital contributions (share purchase/withdrawal)
  - **surplus-distribution**: Record surplus allocation decisions (reserves, patronage, member benefit)
  - **asset-lock**: Enforce indivisible reserve rules per ICA guidance (common property protection)
  - **patronage-tracking**: Log member transactions with the cooperative for proportional benefit calculation
- [ ] Add `member_shares` and `surplus_allocations` tables to PostgreSQL schema
- [ ] Resurrect concepts from archived cFIAT bridge spec (`docs/archive/iskander_fiat_bridge_spec.txt`) — adapt fiat-to-cooperative-token bridge for member share accounting
- [ ] Steward agent extended to manage economic data (balance + shares + reserves reporting)
- [ ] Test: Member purchases shares → Steward reports updated capital → surplus proposal → allocation recorded

**Values Council Foundation:**
- [ ] Port ICA vetter logic into an OpenClaw skill (extract 27-question rubric from `backend/agents/library/ica_vetter.py`)
- [ ] Create first 4 Values Council agents: Democracy Guardian, Honesty Guardian, Equality Guardian, Solidarity Guardian
- [ ] Each agent evaluates cooperative using public on-chain records + Loomio participation data

### Week 5-6: Governance Structure (P2) + Federation (P6 — elevated)

**Governance Structure Module (ICA Principle 2 — MEDIUM gap):**
- [ ] Create `governance` OpenClaw skill enabling:
  - **board-elections**: Run STV elections via Loomio (Scottish STV / Droop quota) with nomination, ranked voting, proportional representation
  - **delegate-management**: Configure Loomio delegated voters — full members vs associates, restrict board votes to elected delegates
  - **term-limits**: Track elected representative terms, alert when approaching expiry, auto-trigger new election
  - **role-separation**: Define and enforce board roles (chair, secretary, treasurer) with rotation schedules
  - **governance-audit**: Periodic review via Loomio participation report (participation rates, quorum achievement, tag-based decision analysis)
  - **subgroup-management**: Create Loomio subgroups for Board, Finance Committee, Working Groups per project
  - **template-management**: Create standardised discussion + poll templates for recurring governance processes
- [ ] Resurrect stewardship spec concepts (`docs/archive/iskander_stewardship_spec.txt`) — adapt gSBT (governance Soulbound Token) for role tracking
- [ ] Add `governance_roles` and `elections` tables to PostgreSQL schema
- [ ] Create Loomio discussion templates: "Board Meeting", "Policy Review", "Financial Approval", "Member Admission"
- [ ] Create Loomio poll templates: "Constitutional Amendment (2/3 + 0% blocks)", "Routine Decision (simple majority)", "Board Election (STV)"
- [ ] Test: Nomination → STV election → proportional winners → role assignment → term tracking → expiry alert

**Federation (ICA Principle 6 — elevated from W7-8):**
- [ ] Set up MCP server exposing cooperative's capabilities (decision log, agent directory, public assessments)
- [ ] Create Liaison agent for inter-cooperative communication
- [ ] Publish Agent Card to network registry
- [ ] Implement cooperative discovery protocol (find nearby cooperatives by geography/sector)
- [ ] Test: Two cooperative nodes discover each other → Liaison agents exchange public assessments

**Structured Education (ICA Principle 5 — MEDIUM gap):**
- [ ] Extend Clerk's onboarding skill with proactive learning pathways:
  - Governance training: "You haven't voted in 3 proposals — would you like me to explain how voting works?"
  - Cooperative education: monthly digest of ICA principles with real examples from the cooperative's own decisions
  - New member mentoring: pair new members with experienced members via Clerk coordination
- [ ] Resurrect Knowledge Commons (IKC) concepts from archived spec for shared learning resources

### Week 6-7: Community Impact (P7) + Cooperative Website + Email

**Community Impact Module (ICA Principle 7 — HIGH gap):**
- [ ] Create `community-impact` OpenClaw skill enabling:
  - **sdg-tracking**: Map cooperative activities to UN SDGs 1-17 (using Co-ops for 2030 framework at `src/IskanderOS/docs/coops-for-2030-report.md`)
  - **sustainability-report**: Generate periodic community impact reports from decision log + economic data
  - **environmental-monitor**: Track energy usage and environmental decisions (foundation for energy-aware scheduling)
  - **community-benefit**: Log and categorise community-directed spending and activities
- [ ] Resurrect energy-aware scheduler concepts (`docs/archive/energy_aware_scheduler_spec.txt`) — adapt for carbon-aware agent scheduling (SDGs 7 + 13)
- [ ] Add `community_impact` and `sdg_mappings` tables to PostgreSQL schema
- [ ] Values Council Principle 7 agent: Community Guardian evaluates cooperative's community engagement
- [ ] Test: Member proposes community activity → tagged with SDGs → impact report generated

**Cooperative Website (public + members area):**
- [ ] Deploy lightweight static site via Caddy behind Traefik (NOT Nextcloud — it's not designed for this)
- [ ] **Public pages** (no login required):
  - About: cooperative name, mission, values, ICA alignment
  - Glass Box: live transparency feed (recent agent actions, decision outcomes)
  - Membership: application form → feeds into Clerk onboarding flow (Task C.9)
  - Federation: directory of connected cooperatives + public contact info
  - Community Impact: SDG progress dashboard, sustainability metrics
- [ ] **Members area** (Authentik SSO):
  - Dashboard: active Loomio proposals, treasury balance, member share summary
  - Governance: participation rates, upcoming elections, role directory
  - Decision log: full history with IPFS links + on-chain hashes
  - Quick links: Loomio, Nextcloud, chat with Clerk
- [ ] API backend: extend decision-recorder service with endpoints for website data
- [ ] Test: Public visitor sees Glass Box + can apply → member logs in via SSO → sees full dashboard

**Email Server (cooperative email addresses):**
- [ ] Add Stalwart mail server to docker-compose (modern Rust-based, IMAP/SMTP/JMAP)
- [ ] Configure Nextcloud Mail app as webmail client (members read/send email from Nextcloud)
- [ ] Authentik provisions email accounts automatically for new members (`member@coop-domain.org`)
- [ ] Add to first-boot: optional domain configuration for email (requires DNS MX records)
- [ ] Fallback for cooperatives without a domain: skip email, use existing addresses
- [ ] Test: Member logs into Nextcloud → opens Mail → sends/receives from cooperative address

### Week 7-8: Multi-Channel Expansion + Remaining Values Council

**Multi-Channel (Telegram + Matrix):**
- [ ] Create Telegram bot via BotFather, configure OpenClaw Telegram channel
- [ ] Add Matrix/Dendrite to docker-compose
- [ ] Configure OpenClaw Matrix channel (E2E encryption)
- [ ] Clerk accessible via Iskander chat widget (primary) + Telegram + Matrix
- [ ] @mention Clerk in Loomio threads (via Loomio API webhook → OpenClaw)

**Complete Values Council (10 agents total):**
- [ ] Create remaining 6 Values Council agents: Self-Help, Self-Responsibility, Equity, Openness, Social Responsibility, Caring for Others
- [ ] Full 10-agent cooperative assessment capability
- [ ] CouncilAssessment smart contract for on-chain vote recording
- [ ] Assessment interface: ten-value profile visualization

**Security Finalisation:**
- [ ] Cloudflare integration (optional — for cooperatives wanting DDoS protection; document ICA P4 autonomy tradeoff)
- [ ] Container security contexts: `cap_drop: [ALL]`, `read_only: true`, `security_opt: [no-new-privileges:true]`
- [ ] Dependency vulnerability scanning in CI (OWASP Dependency-Check or Snyk)
- [ ] Penetration testing checklist for cooperative sysadmins
- [ ] Incident response procedure documented for cooperative members
- [ ] Security documentation: "Keeping your cooperative safe" guide for non-technical members

---

## What Gets Ported From Current Codebase

| Component | Source | Destination | Phase | How |
|-----------|--------|-------------|-------|-----|
| ICA vetter rubric | `backend/agents/library/ica_vetter.py` (847 lines) | OpenClaw skill `ica-vetter/SKILL.md` | B W4-5 | Extract 27-question rubric, rewrite as skill procedures |
| Glass Box concept | `infra/init.sql` agent_actions table | `decision_log.sql` + OpenClaw skill | C W2 | Reuse schema, simplify |
| Constitution.sol | `contracts/src/Constitution.sol` | Same (deploy on Anvil) | B W4-5 | No changes needed |
| CoopIdentity.sol | `contracts/src/CoopIdentity.sol` | Same | B W4-5 | No changes needed |
| cFIAT bridge | `docs/archive/iskander_fiat_bridge_spec.txt` | `economic-participation/SKILL.md` | B W4-5 | Adapt concepts for member share accounting + surplus distribution |
| Stewardship spec | `docs/archive/iskander_stewardship_spec.txt` | `governance/SKILL.md` | B W5-6 | Adapt gSBT for governance role tracking + term management |
| Energy scheduler | `docs/archive/energy_aware_scheduler_spec.txt` | `community-impact/SKILL.md` | B W6-7 | Carbon-aware agent scheduling for SDGs 7 + 13 |
| Knowledge Commons | `docs/archive/` (IKC .odt) | Clerk education pathways | B W5-6 | Shared learning resources for P5 education |
| Credential Translator | `docs/archive/` (.odt) | Membership identity portability | B W5-6 | Identity verification for P1 open membership |
| Energy scheduling | `backend/energy/` | OpenClaw skill | B W6-7 | Port hearth driver interface |
| Cooperation scoring | `backend/agents/library/ipd_auditor.py` (875 lines) | OpenClaw skill | B W5-6 | Extract scoring logic for federation |
| MACIVoting.sol | `contracts/src/governance/MACIVoting.sol` | Deploy on Anvil + compile circuits | B W4-5 | Replace Groth16 stubs with production snarkjs |
| ZK MACI Coordinator | `backend/crypto/zk_maci_wrapper.py` | Port to OpenClaw skill | B W4-5 | Replace HMAC stubs with real proof generation |
| BrightID Sponsor | `backend/api/brightid_sponsor.py` | Port to membership skill | B W4-5 | Register app context, treasury-funded sponsorship |
| HITL Rate Limiter | `backend/api/hitl_rate_limiter.py` | Traefik middleware | C W1 | Move from app-level to infrastructure-level |
| ISO build scripts | `os_build/iso/` | Update for new stack | B W8+ | Fix ports, add OpenClaw + Loomio |

---

## Directory Structure (New)

```
src/IskanderOS/
├── docker-compose.mvp.yml          # Phase C: 8 services (DB, Redis, Authentik, Loomio, Nextcloud, Ollama, OpenClaw, IPFS)
├── docker-compose.full.yml         # Phase B: 11+ services (adds Anvil, Stalwart, Caddy website, Dendrite)
├── openclaw/
│   ├── openclaw.json               # OpenClaw configuration
│   ├── agents/
│   │   ├── orchestrator/SOUL.md    # Orchestrator agent
│   │   ├── clerk/SOUL.md           # Clerk agent (member-facing)
│   │   └── steward/SOUL.md         # Steward agent (treasury)
│   └── skills/
│       ├── loomio-bridge/SKILL.md  # Loomio API integration
│       ├── values-reflection/SKILL.md  # ICA values self-assessment
│       ├── glass-box/SKILL.md      # Audit trail logging
│       ├── treasury-monitor/SKILL.md
│       ├── document-collab/SKILL.md # Phase C: AI-assisted document drafting/revision
│       ├── membership/SKILL.md     # Phase C: Join/leave/onboard (P1)
│       ├── economic-participation/SKILL.md  # Phase B: Shares/surplus/patronage (P3)
│       ├── governance/SKILL.md     # Phase B: Elections/terms/roles (P2)
│       └── community-impact/SKILL.md  # Phase B: SDG tracking/sustainability (P7)
├── services/
│   ├── authentik/                  # SSO identity provider
│   │   └── .env
│   ├── loomio/                     # Decision-making platform
│   │   └── .env
│   ├── nextcloud/                  # File hosting, calendar, contacts, email client
│   │   └── .env
│   ├── decision-recorder/          # Webhook service + Glass Box + website API
│   │   ├── main.py                 # FastAPI, ~200 lines
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── website/                    # Phase B: Cooperative public website
│       ├── public/                 # Static HTML/CSS/JS
│       └── Caddyfile               # Reverse proxy config
├── infra/
│   └── decision_log.sql            # Schema for all tables
├── contracts/                      # Existing, unchanged
│   └── src/
│       ├── Constitution.sol
│       ├── CoopIdentity.sol
│       └── ...
├── scripts/
│   └── first-boot.py              # Interactive setup wizard (configures all 8 services + SSO)
└── legacy/                         # Archived current backend + frontend
    ├── backend/
    └── frontend-next/
```

---

## Task Skills (Create Before Execution)

Each task has a corresponding plugin skill that guides the planning and implementation of that specific step. Create these as `.skill` files in the project root before beginning execution.

### Skill 1: `iskander-loomio-setup.skill`
**Triggers**: "set up Loomio", "install Loomio", "configure Loomio"
**Covers**: Task C.1
**Knowledge embedded**:
- Loomio deploys via `loomio/loomio-deploy` (Docker)
- Services: PostgreSQL, Redis, Rails app, worker
- API v1 endpoints: `/api/v1/discussions`, `/api/v1/polls`, `/api/v1/stances`
- API auth: per-user API key from `/api/v1/profile`
- Outgoing webhooks for poll_closed events
- Minimum RAM: 1-2GB for Loomio stack
- Must create: admin account, cooperative group, API key for Clerk agent
- Test verification: curl commands to create/read threads and proposals

### Skill 2: `iskander-openclaw-clerk.skill`
**Triggers**: "set up OpenClaw", "create Clerk agent", "configure Clerk"
**Covers**: Tasks C.2 + C.3 + C.3b
**Knowledge embedded**:
- Install: `npm install -g openclaw@latest`
- Onboard: `openclaw onboard` (interactive) or `--flow non-interactive`
- Config: `~/.openclaw/openclaw.json` (JSON5 format)
- Ollama integration: use native API (`http://localhost:11434`), NOT `/v1`
- SOUL.md format: Identity, Personality, Behavioral Rules, Action Significance
- Clerk role: answers questions, drafts proposals, drafts/revises documents, summarises threads, NEVER votes
- Clerk serves all members equally (ICA Principle 1 + 4)
- Skills go in `~/.openclaw/skills/<name>/SKILL.md`
- Primary channel: web (Iskander chat widget on Loomio frontend, port 3100)
- Telegram/Matrix channels are Phase B expansion
- Multi-agent: Orchestrator + Clerk as specialist
- Loomio-bridge skill: custom SKILL.md that teaches Clerk to call Loomio API
  - list-proposals, summarise-thread, create-proposal, check-outcome, remind-pending
- Document-collab skill: AI-assisted document drafting, revision, and collaborative editing
  - Two modes: in-thread (short, 1-3 sentence replies) and DM (deep exploration + drafting)
  - draft-document, revise-document, incorporate-feedback, expand-suggestion, save-document, summarise-document
  - Loomio ↔ Nextcloud unified storage (shared Docker volume, files accessible in both)
  - Reads Loomio thread attachments + comments to incorporate member feedback
  - Saves to appropriate Nextcloud shared folders OR attaches to Loomio threads
  - expand-suggestion: DMs members to develop brief thread comments into full proposals (member posts result, not Clerk)
  - Never finalises without member approval — always presents diff before saving
  - Clerk replies in threads are always shorter than member contributions
- Values-reflection skill: guided ICA values self-assessment through conversation
  - Core values checklist, Loomio participation analysis, improvement suggestions
- Iskander chat widget: JS component injected into Loomio, connects to OpenClaw web API
- Test verification: Loomio chat widget → Clerk response → Loomio API call → result
- Test verification: "Draft a code of conduct" → Clerk drafts → saves to Nextcloud → member reviews

### Skill 3: `iskander-decision-recorder.skill`
**Triggers**: "decision recorder", "audit trail service", "decision logging"
**Covers**: Tasks C.4 + C.5
**Knowledge embedded**:
- Lightweight FastAPI service (~150 lines)
- Receives Loomio webhook (POST /hooks/loomio) on poll_closed
- Fetches full discussion + poll + stances from Loomio API
- Bundles into JSON, pins to IPFS Kubo → gets CID
- Inserts into `decision_log` table (PostgreSQL)
- Glass Box endpoint: `GET /glass-box/recent` returns recent agent actions
- Schema: `decision_log` + `agent_actions` tables (minimal)
- Docker: Python 3.12-slim image, asyncpg + httpx + FastAPI
- IPFS Kubo: `http://localhost:5001/api/v0/add` for pinning
- Test: Create poll → vote → close → verify DB record + IPFS pin

### Skill 4: `iskander-steward-agent.skill`
**Triggers**: "Steward agent", "treasury monitor", "treasury agent"
**Covers**: Task C.6
**Knowledge embedded**:
- OpenClaw agent with SOUL.md (monitors treasury, flags anomalies)
- Treasury-monitor skill: queries Safe wallet via RPC/Etherscan API
- Heartbeat: every 2h, check for new transactions
- Threshold-based significance: spend > X triggers Loomio proposal via loomio-bridge
- Glass Box logging for every action
- Does NOT execute transactions (Phase B adds on-chain execution)
- Reuses loomio-bridge skill for proposal creation
- Test: Mock a threshold breach → verify Loomio proposal appears

### Skill 5: `iskander-first-boot.skill`
**Triggers**: "first boot", "setup wizard", "node setup"
**Covers**: Tasks C.0a + C.0b + C.1 + C.1b + C.7
**Knowledge embedded**:
- Interactive Python CLI (click or inquirer)
- Collects: cooperative name, founding members (name + email), optional domain
- Security first: generates strong random secrets (Authentik key, OAuth credentials, JWT, DB passwords), writes Traefik TLS config, internal-only networking
- Starts: docker-compose (8 services): DB → Redis → Authentik → Loomio → Nextcloud → Ollama → OpenClaw → IPFS
- All services behind Traefik with HTTPS (Let's Encrypt for domain, self-signed for LAN)
- Configures: Authentik OIDC apps (Loomio + Nextcloud), provisions member accounts across all services
- Creates: cooperative group in Loomio, shared folders in Nextcloud (Governance, Treasury, Projects, Public)
- Runs: `openclaw onboard --flow non-interactive` with generated config
- Creates: Clerk + Steward agents with configured SOUL.md
- Injects Iskander chat widget into Loomio frontend
- Opens browser: "Log in once — access everything"
- Targets: clean Ubuntu 24.04 (x86_64 or ARM64), 8GB RAM minimum
- Test: Run on fresh VM → full cooperative server functional within 10 minutes (excl. downloads)

### Skill 6: `iskander-e2e-verification.skill`
**Triggers**: "verify", "end to end test", "integration test"
**Covers**: Task C.8
**Knowledge embedded**:
- Flow 1: Member question via Iskander chat widget → Clerk → answer (tests: web channel + Clerk + LLM)
- Flow 2: Proposal creation → Loomio vote → decision record (tests: full loop)
- Flow 3: Steward anomaly → Loomio proposal (tests: heartbeat + significance routing)
- Flow 4: Glass Box transparency query (tests: audit trail)
- Each flow has: setup steps, execution steps, verification assertions
- Failures: common failure modes and debugging steps for each service

### Skill 7: `iskander-values-council.skill`
**Triggers**: "Values Council", "ICA values agents", "council agents"
**Covers**: Phase B Week 4-5 (Values Council expansion)
**Knowledge embedded**:
- Multiple OpenClaw agents, each with specialized SOUL.md for one ICA value
- Agents: Self-Help, Self-Responsibility, Democracy, Equality, Equity, Solidarity, and ethical value agents of honesty, openness, social responsibility, and caring for others
- Each evaluates cooperatives using public on-chain records only
- Voting: 5-point scale (Strong alignment → Serious concern)
- Port ICA vetter rubric from `backend/agents/library/ica_vetter.py` (lines 253-414)
- CouncilAssessment smart contract for on-chain vote recording
- Assessment interface: seven-value profile visualization
- Privacy: only organizational behavior, never individual member data

### Skill 8: `iskander-coop-website.skill`
**Triggers**: "cooperative website", "public website", "membership application page", "Glass Box public"
**Covers**: Phase B Week 6-7 (cooperative website)
**Knowledge embedded**:
- Lightweight static site served via Caddy behind Traefik
- Public pages: About, Glass Box feed, Membership application, Federation directory, Community Impact
- Members area: Dashboard, Governance health, Decision log, Quick links (Loomio/Nextcloud)
- Members area behind Authentik SSO (same login as Loomio/Nextcloud)
- Membership application form → creates pending member in Authentik → triggers Clerk onboarding
- Glass Box feed: real-time agent transparency via decision-recorder API
- Federation directory: connected cooperatives from MCP discovery
- API: extends decision-recorder FastAPI with website data endpoints
- Test: Public visitor sees transparency feed → applies → member logs in via SSO → full dashboard

### Skill 9: `iskander-security-hardening.skill`
**Triggers**: "security hardening", "production security", "TLS setup", "Cloudflare", "CrowdSec", "WAF", "DDoS protection", "security audit"
**Covers**: Tasks C.0a (security baseline) + Phase B W4 (production hardening) + Phase B W8 (security finalisation)
**Knowledge embedded**:
- Phase C baseline: TLS via Traefik ACME, security headers, CORS restriction, internal networking, non-root containers, rate limiting
- Traefik config: `infra/traefik/traefik.yml` static + `infra/traefik/dynamic/` for middleware
- Security headers: STS, X-Frame-Options, CSP, X-Content-Type-Options
- Known gaps: 13 identified from codebase audit (see plan Security Hardening section)
- Phase B: CrowdSec, Fail2ban, WAF rules, Redis-backed token revocation, audit logging
- Cloudflare vs self-hosted: document ICA Principle 4 autonomy tradeoff, recommend hybrid
- Container hardening: cap_drop ALL, read_only fs, no-new-privileges, non-root USER
- Secrets: strong random generation in first-boot, file permissions 600, no plaintext defaults
- Existing code to port: HITL rate limiter → Traefik middleware, SIWE nonce store → Redis
- Test: External port scan shows only 80/443, pentest checklist passes

### Skill 10: `iskander-zk-identity.skill`
**Triggers**: "ZK identity", "zero knowledge", "MACI voting", "BrightID", "Sybil resistance", "1 member 1 vote", "secret ballot"
**Covers**: Phase B W4-5 (ZK identity + MACI deployment)
**Knowledge embedded**:
- Existing contracts: CoopIdentity.sol (SBTs), MACIVoting.sol (ZK voting), TrustRegistry.sol
- Existing backend: zk_maci_wrapper.py (coordinator), brightid_sponsor.py (Sybil resistance)
- SBT minting: one per address, BrightID-gated, non-transferable
- MACI flow: signUp → publishMessage (encrypted) → processMessages → verifyTally
- Production deployment: compile Circom circuits, trusted setup ceremony, deploy Verifier.sol
- Stub replacements: HMAC → snarkjs Groth16, sha256 → Poseidon hash
- BrightID: register app context, treasury sponsors verification for new members
- Sybil layers: SSO (email) → SBT (on-chain) → BrightID (proof of human) → MACI (anti-coercion)
- Trust scoring: [0,1000] basis points, affects stewardship eligibility but NOT voting weight
- Test: Member signs up → BrightID verified → SBT minted → votes in MACI poll → ZK proof of tally

### Skill 11: `iskander-phase-b-expansion.skill`
**Triggers**: "Phase B", "expand MVP", "Loomio-native expansion"
**Covers**: Phase B Weeks 4-8
**Knowledge embedded**:
- Week 4-5: Blockchain + ZK Identity (MACI + BrightID + SBTs) + Economic Participation (P3) + Values Council (4 agents) + Security hardening (CrowdSec, WAF)
- Week 5-6: Governance Structure (P2, gSBT) + Federation elevated (P6) + Structured Education (P5)
- Week 6-7: Community Impact (P7, energy scheduler) + Cooperative Website (Caddy) + Email (Stalwart)
- Week 7-8: Multi-channel (Telegram + Matrix) + Complete Values Council (10 agents) + Security finalisation
- Full stack: 11+ Docker services, plug-and-play cooperative server
- ZK deployment: Circom circuits, trusted setup ceremony, snarkjs integration
- Port schedule: MACI/BrightID (W4-5), cFIAT (W4-5), stewardship/gSBT (W5-6), energy scheduler (W6-7)
- Each week builds on the previous — strict dependency order

---

## Verification

**Phase C success** (Week 3):
1. First-boot wizard configures a full cooperative server in under 10 minutes (excl. downloads)
2. Member creates ONE account (Authentik) → logs into Loomio AND Nextcloud with same credentials
3. All services accessible only via HTTPS, security headers present, no exposed DB/Redis ports
4. Member opens Loomio → Iskander chat widget → asks Clerk a question → gets plain-language answer
5. Member asks Clerk to create a proposal → proposal appears in Loomio
6. Members vote in Loomio → poll closes → decision recorded in DB with IPFS hash
7. Member asks "What have you done today?" → Clerk reports Glass Box audit trail
8. Steward detects anomaly → creates Loomio proposal automatically
9. Members share files via Nextcloud shared folders (Governance, Treasury, Projects)
10. New member joins via Clerk onboarding → gets accounts across all services
11. Member asks Clerk to "draft a procurement policy" → Clerk produces draft → saves to Nextcloud → member reviews and refines collaboratively
12. Member asks Clerk to "revise the bylaws based on the discussion thread" → Clerk reads Loomio comments + existing document → produces revision with diff summary
13. Clerk correctly selects decision process: Consent for proposals, Advice for information-seeking, sets quorum + vote thresholds
14. Clerk DMs a member via Loomio Direct Discussion to help expand a brief thread comment into a full proposal
15. Action items from decisions are tracked as Loomio tasks with @mentions and due dates

**Phase B success** (Week 8):
1. Every decision has an on-chain hash traceable to the Loomio discussion
2. Each member has a non-transferable SBT, BrightID-verified as unique human (1-member-1-vote proven)
3. Sensitive decisions use MACI ZK voting — individual votes never disclosed, only ZK-proven tallies
4. Members can purchase/withdraw shares, surplus allocation recorded (P3 economic participation)
5. Board elections run via Loomio with term tracking and role separation (P2 governance)
6. Cooperative activities mapped to SDGs with sustainability reporting (P7 community concern)
7. Two cooperative nodes can discover each other via MCP (P6 federation)
8. Clerk proactively guides governance education and member mentoring (P5 education)
9. All 10 Values Council agents can assess a cooperative's public record
10. Clerk accessible via Iskander chat widget + Telegram + Matrix
11. Cooperative website live: public Glass Box, membership applications, federation directory
12. Members have cooperative email addresses via Stalwart + Nextcloud Mail
13. CrowdSec + WAF + Fail2ban active, external pentest checklist passes
14. Full plug-and-play server: one boot → SSO + decisions + files + email + website + AI clerk + treasury + ZK identity
