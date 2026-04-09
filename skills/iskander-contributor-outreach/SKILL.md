---
name: iskander-contributor-outreach
description: Draft contributor recruitment content, funding applications, outreach emails, launch posts, and GitHub community setup for Iskander. Use this skill whenever the user mentions finding contributors, promoting the project, writing a launch post, applying for funding or grants (NLnet, Power to Change, DisCO, etc.), emailing aligned organisations, creating good-first-issues, drafting blog posts about the project, cooperative outreach, or anything related to growing the Iskander community. Also triggers for "outreach", "marketing", "community building", "contributor", "promotion", "funding application", "grant", or "launch".
---

# Iskander Contributor Outreach & Promotion

Automate the hybrid flywheel strategy: recruit developers through compelling content, engage cooperative organisations through direct outreach, and secure funding to sustain the work.

## Voice & Tone

All content is written in the founder's first-person voice. The founder is a solo developer building with Claude Code who genuinely believes in the cooperative movement. The tone is:

- **Passionate but grounded** — enthusiasm backed by real technical detail and ICA principles
- **Honest about stage** — early, ambitious, working prototype on the way, not vaporware claims
- **Technically credible** — lunarpunk architecture, game theory, K3s, ZK voting are real and substantive
- **Inviting** — "here's where you can help" not "please help us"
- **Anti-hype** — explicitly reject blockchain buzzwords, token speculation, and "web3 for everything" framing. Iskander uses crypto for 5 specific problems. Say so.

Read the whitepaper at `docs/white-paper.md` and `docs/overview.md` before drafting any content. These are your primary source of truth for messaging.

## Campaign Tracks

The strategy has four parallel tracks. When the user asks for help, identify which track they need and follow that section.

---

### Track 1: GitHub Community Readiness

Prepare the GitHub repo to welcome contributors.

**Good First Issues** — create issues from areas listed in `CONTRIBUTING.md`:

For each area, draft 2-3 specific, scoped issues. Each issue must include:
- A clear title starting with `[good first issue]`
- **Context**: why this matters (link to the relevant ICA principle or architectural goal)
- **What to do**: specific files/directories involved, expected outcome
- **Skills needed**: be honest about what's required
- **Getting started**: point to relevant docs (`docs/plan.md`, `docs/roadmap.md`, etc.)

Use `gh issue create` to create them. Label with `good first issue` and the relevant area (`helm`, `ansible`, `loomio`, `mattermost`, `circom`, `testing`, `i18n`).

**GitHub Discussions** — enable and seed with:
- An "Introductions" discussion (welcome thread)
- An "Architecture Decisions" category for RFC-style conversations
- A "Cooperative Use Cases" category where co-op members can describe their needs

**Project Board** — create a public project board mapping to the Phase C/B roadmap from `docs/roadmap.md`.

---

### Track 2: Developer Recruitment Content

Draft platform-specific launch content. Each platform has different norms — respect them.

**Hacker News (Show HN)**
- Title: "Show HN: Iskander -- Lunarpunk cooperative infrastructure (self-hosted, K3s, ZK voting)"
- Body: 3-4 paragraphs max. Lead with the problem (co-ops use Google/Slack), the thesis (GTFT game theory), what you get (15 services, one command), and the 5 crypto problems. End with the GitHub link.
- HN audience cares about: technical novelty, self-hosting, game theory, honest assessment of trade-offs. They are allergic to: blockchain hype, "changing the world" claims, anything that sounds like a pitch deck.

**Reddit** — draft separate posts for each subreddit, tailored to that community:
- `r/selfhosted`: focus on the K3s stack, one-command install, 15 services, compare to existing self-hosted solutions
- `r/kubernetes`: focus on K3s Helm charts, lightweight orchestration, the architecture
- `r/cooperative`: focus on ICA principles, democratic governance, why existing tools fail co-ops
- `r/ethereum`: focus on MACI ZK voting, SBTs, the 5 crypto problems, anti-speculation stance
- `r/solarpunk`: focus on lunarpunk philosophy, federated local economics, people/place/planet

**Fediverse/Mastodon** — draft a thread (series of toots):
- Mastodon audience skews privacy-conscious, anti-corporate, pro-FOSS. Lead with self-hosting and cooperative values. The lunarpunk framing resonates here.

**Blog posts** (save to `docs/blog/` as markdown):
- "Why I'm building cooperative infrastructure with AI" — personal story, the vision, honest about vibe-coding with Claude
- "Five problems only cryptography can solve for cooperatives" — adapted from whitepaper section 4
- "Game theory says cooperatives win: GTFT and the Iskander thesis" — adapted from section 2
- "The lunarpunk case for selective disclosure" — adapted from section 3.1

---

### Track 3: Cooperative & Organisation Outreach

Draft emails and messages for organisations with aligned missions.

**For each outreach email, include:**
1. Who you are (solo developer, cooperative movement believer)
2. What Iskander is (one sentence: "self-hosted cooperative infrastructure — Loomio + Mattermost + AI clerk + 12 more services, one command to install")
3. Why you're reaching them specifically (what about their work aligns)
4. A specific ask (feedback, testing, partnership, advice — not "please use our thing")
5. Links: GitHub repo, whitepaper, overview doc

**Target organisations** — read `references/outreach-targets.md` for the full list and tailor each email. Key targets:

| Organisation | Why | Ask |
|---|---|---|
| CoTech (coops.tech) | UK tech co-op network, uses Loomio already | Testing, feedback, potential early adopters |
| Platform Cooperativism Consortium | Academic hub for platform co-ops at The New School | Research partnership, visibility |
| DisCO.coop | Feminist economics, value tracking — directly influenced Iskander | Feedback on DisCO value stream integration |
| Loomio team | Iskander builds on Loomio, extends it with AI and web3 | Technical partnership, API guidance |
| Mattermost community | Plugin ecosystem, self-hosted chat | Contributor recruitment for Mattermost plugin |
| Radical Routes | UK network of housing/worker co-ops | Real-world testing, user feedback |
| Co-operatives UK | National apex body | Visibility, network access |
| Hypha DAO | DAO 3.0 governance tooling — cited in whitepaper | Technical collaboration |
| DarkFi | Lunarpunk privacy philosophy | Philosophical alignment, potential ZK collaboration |
| InterCooperative Network (ICN) | Trust-native federation — cited in whitepaper | Architecture feedback, potential interop |

---

### Track 4: Funding Applications

Draft funding applications. Read `references/funding-targets.md` for deadlines and criteria.

**For each application, follow this structure:**
1. Read the funder's criteria and format requirements
2. Read Iskander's whitepaper and roadmap to map project goals to funder priorities
3. Draft application answers that are honest about project stage
4. Highlight what makes Iskander distinctive (not just "another blockchain project")
5. Be specific about what the money would fund (hosting, contributor stipends, ZK circuit development, etc.)

**Key funding targets:**

| Funder | Amount | Deadline | Fit |
|---|---|---|---|
| NLnet NGI Zero Commons Fund | EUR 5k-50k | June 1, 2026 | Excellent — FOSS, internet commons, P2P infrastructure |
| Power to Change Discovery Fund | GBP 10k | Rolling | Good — community tech for community businesses |
| Interledger Foundation | Varies | Rolling | Good — DisCO previously funded, inter-cooperative payments |
| Cooperative Development Foundation | Varies | Annual | Good — cooperative development specifically |
| National Lottery Community Fund | Varies | Rolling | Moderate — community-led tech, broader scope |
| Innovate UK | GBP varies | Competition-based | Moderate — digital tech, would need commercial framing |

**NLnet is the highest priority.** The June 1, 2026 deadline is imminent. Their criteria map almost perfectly to Iskander:
- Free/libre/open source (AGPL-3.0 -- yes)
- Helps fix the internet (federated, self-hosted, privacy-first -- yes)
- From libre silicon to end-user applications (cooperative infrastructure -- yes)
- P2P infrastructure (Headscale mesh, federation protocol -- yes)

When drafting the NLnet application, read their proposal form at nlnet.nl/propose/ and structure answers to match their questions exactly.

---

## Campaign Tracker

After executing any track, update a campaign tracker at `docs/outreach/campaign-tracker.md` with:

```markdown
## [Track Name]

### [Action] — [Date]
- **Status**: drafted / sent / published / response received
- **Platform/Target**: where it went
- **Link**: URL if published
- **Notes**: any response or follow-up needed
```

Create `docs/outreach/` directory if it doesn't exist.

---

## Sequencing

If the user asks "what should I do first?" or "where do I start?", recommend this order:

1. **NLnet application** (deadline-driven, June 1 2026 — start immediately)
2. **GitHub readiness** (good first issues + Discussions — takes 30 minutes, unblocks everything)
3. **Hacker News Show HN post** (highest developer reach per effort)
4. **CoTech + Loomio team emails** (highest-alignment cooperative contacts)
5. **Reddit posts** (fan out across subreddits over a week, not all at once)
6. **Blog posts** (build over time, one per week)
7. **Remaining outreach emails** (as capacity allows)
8. **Other funding applications** (after NLnet, one at a time)
