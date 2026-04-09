# NLnet NGI Zero Commons Fund Application
## Iskander: Lunarpunk Cooperative Infrastructure

**Fund**: NGI Zero Commons Fund
**Deadline**: June 1, 2026
**Form**: https://nlnet.nl/propose/
**Status**: DRAFT — review before submitting

---

> **How to submit**: Go to https://nlnet.nl/propose/, select "NGI Zero Commons Fund" from
> the thematic call dropdown, and copy each section below into the matching form field.
> Fields marked [FILL IN] need your personal details before submission.

---

## CONTACT INFORMATION

**Your name**: Tom Whipp
**Email**: [FILL IN — your email]
**Phone**: [FILL IN — optional but recommended]
**Organisation**: [FILL IN — leave blank or enter "Independent" if you have no registered org]
**Country**: United Kingdom

---

## PROPOSAL NAME

Iskander: Lunarpunk Cooperative Infrastructure

---

## WEBSITE / WIKI

https://github.com/Argocyte/Iskander

---

## ABSTRACT

*(Explain the whole project and its expected outcome(s))*

Cooperatives are democratic organisations governed by one-member-one-vote. Over 3 million cooperatives worldwide employ 280 million people and are founded on seven ICA principles that prioritise member control, autonomy, and community benefit. Yet the digital tools they rely on — Google Workspace, Slack, Zoom — are built for hierarchies. They centralise data on corporate servers, charge per-user fees that create participation barriers, and extract value from the communities they serve.

Iskander is self-hosted, federated cooperative infrastructure. A single installation command deploys 15 FOSS services on K3s — Loomio (democratic governance), Mattermost (team chat), Nextcloud (files and calendar), an AI Clerk agent that helps every member participate, plus SSO, encrypted backups, system monitoring, credential management, and mesh federation networking. All self-hosted. No corporate dependency. No per-user fees. Owned and controlled by the cooperative.

The project uses cryptography for exactly five problems that traditional technology cannot solve: tamper-evident decision records (IPFS content-addressing + append-only ledger), anti-coercion voting (MACI zero-knowledge proofs), Sybil-resistant identity without KYC (Soulbound Tokens + BrightID social graph), intermediary-free inter-cooperative trade (smart contract escrow with federated arbitration), and anti-extractive finance (1:1 fiat-backed settlement tokens with contract-enforced pay ratios). No component exists for speculation, marketing, or "innovation theatre."

The federation layer uses generous tit-for-tat game theory (Axelrod, 1984) with exponentially-decaying reputation (30-day half-life) to create emergent cooperative advantage across sovereign nodes connected by Headscale WireGuard mesh. No central authority. No platform intermediary.

The expected outcome is a production-ready cooperative-in-a-box — installable in under 10 minutes with one command — that any cooperative can run on a 16GB VPS or Raspberry Pi cluster, governed by its own democratic principles, federated on its own terms, and private by design. All outputs are published under AGPL-3.0.

---

## EXPERIENCE

*(Have you been involved with projects or organisations relevant to this project before?)*

I am a solo developer building Iskander using AI-assisted development (Claude Code). My background is in software engineering, and I have spent several years studying the cooperative movement, ICA Cooperative Principles, and the intersection of democratic governance with open-source technology.

The project draws directly on several bodies of work I have researched in depth: DisCO.coop's feminist economics framework (which shapes how the Clerk agent tracks care work alongside productive output), Hypha DAO's evolution from code-centric to human-centred governance (which informs the principle that humans deliberate and smart contracts notarise, never the other way around), the InterCooperative Network's trust-native federation model, and DarkFi's lunarpunk privacy philosophy.

The project is supported by Alyssa [FILL IN — surname if happy to include], a cooperative technology specialist who has offered cluster hosting for real-world testing and deployment.

I am honest about the project stage: Iskander is in active development. The architecture is fully designed, the roadmap is defined and phased, and Phase C (the Radical MVP) is under construction. I am not claiming a finished product — I am applying for funding to complete the core infrastructure and make it genuinely deployable by real cooperatives.

---

## AMOUNT

EUR 50,000

---

## BUDGET JUSTIFICATION

*(What will the requested budget be used for?)*

The budget funds six months of development work by the project founder, plus infrastructure costs for a public testing cluster and an independent security review.

**Developer time: EUR 45,000**
800 hours at EUR 56.25/hour. This rate reflects a mid-market rate for a UK-based FOSS developer working on infrastructure and cryptographic tooling. All work is on open-source outputs published under AGPL-3.0.

**Infrastructure and hosting: EUR 3,000**
A dedicated VPS and domain for a public demo cluster, allowing cooperatives to explore Iskander before self-hosting. Covers six months of cloud hosting costs plus the iskander.coop domain.

**Independent security review: EUR 2,000**
A targeted review of the K3s hardening, network policies, and Authentik SSO configuration by a peer with infrastructure security expertise. Cooperative deployments involve real member data; a review before public release is essential.

**Total: EUR 50,000**

---

## TASK BREAKDOWN

*(Breakdown in main tasks with associated effort and explicit rates)*

**Rate: EUR 56.25/hour (developer time)**

| Task | Effort | Cost |
|------|--------|------|
| **Phase C — Radical MVP** | | |
| K3s Helm charts for all 15 services (Authentik, Loomio, Mattermost, Nextcloud, PostgreSQL, Redis, IPFS, OpenClaw, Ollama, Vaultwarden, Backrest, Beszel, Cloudflared, Headscale) | 80h | EUR 4,500 |
| AI Clerk agent — loomio-bridge skill, document-collaboration skill, Glass Box audit trail | 70h | EUR 3,938 |
| Decision recorder service (Loomio webhook → PostgreSQL + IPFS anchoring) | 40h | EUR 2,250 |
| Steward agent (treasury monitoring, spending proposals) | 30h | EUR 1,688 |
| curl\|sh installer — Ansible playbooks, first-boot wizard, idempotent recovery | 60h | EUR 3,375 |
| Membership lifecycle (onboarding, offboarding, role management) | 30h | EUR 1,688 |
| End-to-end testing and ARM64 (Raspberry Pi) verification | 30h | EUR 1,688 |
| **Phase B — Web3 + Federation** | | |
| Anvil EVM deployment + 9 smart contracts (Constitution, CoopIdentity, MACIVoting, IskanderEscrow, ForeignReputation, InternalPayroll, StewardshipLedger, ArbitrationRegistry, CoopFiatToken) | 80h | EUR 4,500 |
| Circom circuit compilation pipeline + MACI trusted setup tooling | 100h | EUR 5,625 |
| Soulbound Token (SBT) minting + BrightID social graph integration | 60h | EUR 3,375 |
| ZK voting integration with Loomio (MACI ↔ Loomio bridge) | 70h | EUR 3,938 |
| Governance module (STV elections, delegated voters, term limits, surplus distribution) | 60h | EUR 3,375 |
| Federation protocol (Headscale mesh setup, ForeignReputation + Escrow deployment) | 80h | EUR 4,500 |
| Security hardening (CrowdSec, WAF, network policies, penetration testing) | 40h | EUR 2,250 |
| **Cooperative pilots and community** | | |
| Pilot deployment with 2–3 real cooperatives (setup, support, feedback integration) | 60h | EUR 3,375 |
| Documentation — administrator guide, contributor guide, cooperative onboarding guide | 60h | EUR 3,375 |
| **Infrastructure** | | |
| Public demo cluster hosting (6 months VPS + domain) | — | EUR 3,000 |
| Independent security review | — | EUR 2,000 |
| **TOTAL** | **800h + costs** | **EUR 50,000** |

---

## OTHER FUNDING

*(Does the project have other funding sources, both past and present?)*

No. Iskander currently has no external funding. All development to date has been self-funded by the founder. This NLnet application is the project's first external funding request.

If this grant is awarded, I plan to pursue complementary applications to the Interledger Foundation (for the inter-cooperative payment protocol work, cFIAT settlement tokens) and Power to Change's Community Tech Discovery Fund (for UK cooperative pilot deployments). Neither application has been submitted, and neither is contingent on NLnet funding.

---

## COMPARISON

*(Compare your project with existing or historical efforts)*

**Loomio** is the world's leading open-source governance platform and Iskander builds on it directly. But Loomio is a standalone tool — it does not integrate with files, chat, AI assistance, federation, or cryptographic decision records. A cooperative using Loomio still needs separate tools for everything else. Iskander wraps Loomio inside a complete cooperative workspace and extends it with capabilities Loomio cannot provide alone.

**Nextcloud and Mattermost** are mature self-hosted platforms included in Iskander's stack. They serve general organisations without democratic governance assumptions — no concept of one-member-one-vote, no cooperative identity, no governance workflow integration.

**Hypha DAO** pioneered human-centred DAO 3.0 governance but operates on blockchain-native infrastructure that requires crypto literacy from all participants. Iskander hides the entire blockchain layer — members interact with Loomio and an AI Clerk in plain language and never touch a wallet.

**InterCooperative Network (ICN)** shares Iskander's vision of trust-native inter-cooperative federation. ICN defines the protocol layer; Iskander provides the full deployable stack — from Kubernetes orchestration to end-user interfaces — that any cooperative can install without technical expertise.

**YunoHost, Sandstorm, FreedomBox** offer self-hosted app bundles for general use. None are built for democratic organisations, none integrate governance tooling, and none provide ZK voting, cooperative identity, or federation reputation.

**Colony, Aragon, DAOstack** are DAO governance platforms built for token-weighted plutocratic governance — the antithesis of ICA Principle 2 (one-member-one-vote). Iskander uses the same cryptographic primitives but in service of democratic cooperative governance aligned with internationally recognised cooperative principles.

No existing project combines self-hosted infrastructure, cooperative governance, zero-knowledge voting, AI assistance, and inter-cooperative federation in a single installable package. Iskander's distinctive contribution is the integration of these capabilities into a coherent system that non-technical cooperative members can install and operate.

---

## TECHNICAL CHALLENGES

*(Significant technical challenges expected during the project)*

**Zero-knowledge voting for non-technical users.** MACI (Minimum Anti-Collusion Infrastructure) has been deployed in Ethereum governance contexts but never integrated with a conventional governance platform like Loomio. The challenge is compiling Circom circuits for cooperative-scale voting (tens to hundreds of members), implementing a trusted setup ceremony that founding members can run without cryptographic expertise, and making the entire ZK layer invisible to members who simply click "vote" in Loomio. The MACI-Loomio bridge must translate between Loomio's poll lifecycle and MACI's encrypted ballot state machine without any user exposure to keys or proofs.

**Single-command deployment of 15 interconnected services.** Running Authentik, Loomio, Mattermost, Nextcloud, OpenClaw, Ollama, PostgreSQL, Redis, IPFS Kubo, Vaultwarden, Backrest, Beszel, Cloudflared, and Headscale on a single 16GB server requires precise resource management. Each service needs a production-quality Helm chart with health checks, resource limits, persistent volume claims, secrets management, and SSO integration. The Ansible installer must be idempotent — recoverable from partial failures — and must work across Ubuntu, Fedora, and Arch Linux without manual intervention.

**Federation trust with game-theoretic properties.** The ForeignReputation smart contract implements generous tit-for-tat with exponential decay (30-day half-life). The technical challenge is making reputation queries fast enough for real-time trust decisions during inter-cooperative trade negotiation, while maintaining a tamper-evident on-chain audit trail. This likely requires an off-chain indexing layer caching reputation scores with on-chain verification.

**Sybil resistance without discriminatory barriers.** BrightID's social graph verification enables one-member-one-vote without government ID, but requires members to attend verification events or receive vouches from existing verified members. Cooperatives need alternative paths for members who cannot attend in-person verification — asynchronous video verification and cooperative-vouching mechanisms that satisfy ICA Principle 1 (open membership without discrimination).

**AI Clerk safety in a democratic context.** The Clerk agent must help members participate in governance without ever influencing their decisions. Robust guardrails are required: the Clerk explains, summarises, and drafts, but never advocates, expresses preferences, or takes autonomous action. Every Clerk action is logged in the Glass Box audit trail. The failure mode — an AI agent that subtly steers cooperative decisions — is a serious governance risk that requires careful prompt engineering and architectural enforcement.

---

## ECOSYSTEM

*(Describe the project ecosystem and engagement with relevant actors)*

**Direct technical ecosystem:**
Iskander is built on and contributes back to several established FOSS ecosystems. Helm charts for cooperative-ready deployment of Loomio, Mattermost, Nextcloud, and Authentik on K3s will be published and useful beyond Iskander. The MACI-Loomio bridge is a reusable component for any governance platform wanting ZK voting. The AI Clerk architecture (facilitate, never decide) is a pattern applicable to any democratic organisation.

**Cooperative movement engagement:**
The target users are the 3 million+ cooperatives worldwide. Specific first-mover communities:
- **CoTech** (coops.tech) — UK network of ~40 tech cooperatives who already use Loomio; primary target for pilot deployments and real-world feedback
- **Radical Routes** — UK network of housing and worker cooperatives; testing with non-technical co-op members
- **Co-operatives UK** — national apex body providing network access and visibility
- **Platform Cooperativism Consortium** — academic hub for research partnership and global cooperative network access

**Aligned project collaboration:**
- **Loomio team** — I will engage for API guidance and to discuss the MACI integration as a potential upstream contribution
- **DisCO.coop** — whose feminist economics framework directly influenced Iskander's value tracking design; I will seek feedback on the implementation
- **InterCooperative Network** — for interoperability discussion and shared protocol standards

**Promotion:**
All code is publicly available on GitHub under AGPL-3.0 from day one. A public demo cluster (funded by this grant) will allow cooperatives to explore before self-hosting. Launch content is planned for Hacker News (targeting infrastructure and game theory communities), Reddit (r/selfhosted, r/cooperative, r/ethereum), and the Fediverse (privacy and FOSS communities). Blog posts will explain the five cryptographic solutions, the GTFT game theory, and the lunarpunk philosophy for different audiences.

---

## THEMATIC CALL

NGI Zero Commons Fund

---

## GENERATIVE AI DISCLOSURE

*(Did you use generative AI in writing this proposal?)*

**Yes.** This proposal was drafted with assistance from Claude Code (Anthropic, claude-opus-4-6 / claude-sonnet-4-6), an AI-assisted development tool I use for the Iskander project itself. The AI helped structure the proposal and draft initial text across all sections; all content was reviewed, edited, and approved by me as accurate and representative of the project.

The Iskander project uses Claude Code throughout its development — this is honest about who I am and how I work. The whitepaper, roadmap, and all project documentation were similarly produced with AI assistance and reflect my genuine technical and philosophical commitments.

**Model used**: Claude (Anthropic) — claude-opus-4-6 and claude-sonnet-4-6
**Used for**: proposal structure, drafting, editing

---

## NOTES FOR SUBMISSION

Before submitting, verify:
- [ ] Fill in your email address in the Contact Information section
- [ ] Fill in phone number (optional but recommended — NLnet may want to discuss)
- [ ] Fill in Organisation field (leave blank or "Independent" if no registered entity)
- [ ] Include Alyssa's surname if she's happy to be named as a collaborator
- [ ] Attach the whitepaper PDF/markdown as an additional document (docs/white-paper.md)
- [ ] Review the task breakdown hours — adjust if your genuine estimate differs
- [ ] Check hourly rate is appropriate for your situation (EUR 56.25/hr = ~£48/hr, reasonable for UK FOSS dev)
- [ ] Read: https://nlnet.nl/commonsfund/ one more time before submitting to confirm nothing has changed

**Strongest sections**: Abstract, Technical Challenges, Comparison — these directly match NLnet's review criteria.
**Weakest section**: Experience — being a solo developer without prior NLnet history is a real gap. If Alyssa is willing to be named as a technical advisor/collaborator in the Experience section, that would strengthen this.

---

*Drafted: April 2026. Campaign tracker entry: docs/outreach/campaign-tracker.md*
