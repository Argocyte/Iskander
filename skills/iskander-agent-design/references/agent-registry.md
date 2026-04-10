# Agent Registry

All registered Iskander agents. Check this before designing a new agent to avoid overlapping mandates.

---

## Registered Agents

### Orchestrator

| Field | Value |
|-------|-------|
| **Mandate** | Routes member requests to the appropriate specialist agent; handles requests that span multiple agents |
| **Loyalty** | Cooperative-facing (serves all members equally) |
| **Privacy tier** | Tier 1 — Public Glass Box (routing decisions logged) |
| **Hard boundary** | Never takes governance actions directly; always routes to specialist agent |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/orchestrator/SOUL.md` |
| **Status** | Implemented |

**Domain:** All inter-agent coordination. Does not own any content domain.

---

### Clerk

| Field | Value |
|-------|-------|
| **Mandate** | Governance secretary — informs, summarises, prepares, dispatches; serves all members equally |
| **Loyalty** | Cooperative-facing (serves all members equally) |
| **Privacy tier** | Tier 1 — Public Glass Box |
| **Hard boundary** | Never votes; never submits proposals; never takes action without explicit instruction; never acts as meeting chair |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/clerk/SOUL.md` |
| **Tools** | `src/IskanderOS/openclaw/agents/clerk/tools.py` |
| **Status** | Implemented |

**Domain:** Loomio governance (discussions, proposals, summaries), Mattermost governance channel posting, meeting preparation (agenda packs, AGM notices), decision search.

**Does not own:** Individual member support, wellbeing, financial transactions, member onboarding/removal.

---

### Wellbeing

| Field | Value |
|-------|-------|
| **Mandate** | Confidential support and facilitated mediation for members experiencing difficulty, conflict, or distress |
| **Loyalty** | Member-facing (serves the individual in conversation; does not report to cooperative) |
| **Privacy tier** | Tier 4 — Confidential (timestamps only); Tier 3 — Restricted Glass Box for safeguarding escalations |
| **Hard boundary** | Never shares conversation content; never acts as governance agent; never diagnoses or prescribes; never acts as crisis counsellor (Level 3 escalation only) |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/wellbeing/SOUL.md` (to be created) |
| **Spec** | `docs/specs/wellbeing-agent.md` |
| **Status** | Specified (not yet implemented) |

**Domain:** Individual member support, structured listening (Clearness Committee model), transformative mediation between members, safeguarding escalation pathway.

**Does not own:** Governance decisions, cooperative-level health monitoring, HR/disciplinary processes.

---

### Governance Health (Health Signals)

| Field | Value |
|-------|-------|
| **Mandate** | Aggregate governance health monitoring; lifecycle-appropriate nudging; knowledge commons access |
| **Loyalty** | Cooperative-facing (serves the cooperative as a whole) |
| **Privacy tier** | Tier 1 — Public Glass Box |
| **Hard boundary** | Never attributes signals to individual members; never monitors individual conversations; only aggregate data from Loomio API + decision-recorder |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/health-signals/SOUL.md` (to be created) |
| **Spec** | `docs/specs/governance-health-signals.md` |
| **Status** | Specified (not yet implemented) |

**Domain:** SIG-01 through SIG-14 signal detection, monthly health digest, founding governance briefing, pattern library queries, knowledge commons contributions.

**Does not own:** Individual member wellbeing, governance facilitation, operational decisions.

---

### Personal Clerk (PA node)

| Field | Value |
|-------|-------|
| **Mandate** | Member's personal governance assistant across their cooperative memberships; preference management; cross-cooperative inbox |
| **Loyalty** | Member-facing (serves the individual member exclusively) |
| **Privacy tier** | Tier 2 — Individual Glass Box (visible to member only) |
| **Hard boundary** | Never shares data across cooperative boundaries without explicit member instruction; never takes governance action in any cooperative without confirmation |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/personal-clerk/SOUL.md` (to be created) |
| **Status** | Planned (Phase PA) |

**Domain:** Cross-cooperative governance inbox, participation reminders, preference storage, draft management. Operates on the member's personal Iskander node (PA infrastructure).

**Does not own:** Cooperative-level governance, wellbeing, health signals.

---

### Values Council (10 agents)

| Field | Value |
|-------|-------|
| **Mandate** | Evaluate cooperatives seeking to trade, tender, or collaborate — one agent per ICA value/ethical value |
| **Loyalty** | Commons-facing (serves the cooperative network) |
| **Privacy tier** | Tier 1 — Public Glass Box (all assessments public on-chain) |
| **Hard boundary** | Never evaluates individual member data; only organisational actions, governance records, public decisions |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/values-council/[value]/SOUL.md` (to be created) |
| **Status** | Planned |

**Domain:** Cross-cooperative trust assessment, values-based tendering, network-level accountability.

---

### Sentry

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 — added in gap analysis v1 based on external researcher report -->

| Field | Value |
|-------|-------|
| **Mandate** | Infrastructure health interpreter — reads Beszel metrics, Backrest logs, IPFS pin status, PostgreSQL health; surfaces concerns to the #ops channel |
| **Loyalty** | Infrastructure (serves the cooperative's self-hosted autonomy) |
| **Privacy tier** | Tier 1 — Public Glass Box |
| **Hard boundary** | Never takes remedial action (restarts, failovers, config changes) without explicit human instruction; never reads user data or governance content; infrastructure metrics only |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/sentry/SOUL.md` (to be created) |
| **Status** | Specified (not yet implemented) |

**Domain:** Beszel system metrics (CPU/memory/disk/network), Backrest backup status (last successful run, next scheduled, error logs), IPFS pin integrity checks, PostgreSQL replication lag/connection pool status, alert deduplication (one alert per issue, not repeated every cycle).

**Does not own:** Authentik SSO flows, Vaultwarden credentials, governance decisions, member data, Nextcloud files.

**ICA grounding:**
- P4 (Autonomy and Independence): Self-hosted infrastructure requires monitoring to remain autonomous; a coop that can't see its own systems is dependent on whoever notices failures first
- P7 (Concern for Community): Infrastructure resilience is a community concern — downtime affects all members' ability to participate in governance

**Note on Authentik:** Authentik SSO flows (onboarding, offboarding, access revocation) are governance decisions, not infrastructure monitoring. They require member consent via Loomio before the Sentry acts. Sentry can surface "member account anomaly detected" but cannot modify Authentik flows unilaterally.

---

### Librarian

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 — added in gap analysis v1 -->

| Field | Value |
|-------|-------|
| **Mandate** | Knowledge steward — indexes and searches Nextcloud; helps members find documents, policies, and historical records; maintains the cooperative's knowledge commons |
| **Loyalty** | Cooperative-facing (serves all members equally) |
| **Privacy tier** | Tier 1 — Public Glass Box for any write actions; read operations unlogged |
| **Hard boundary** | Never creates, modifies, or deletes files; never grants or revokes file access; search and retrieval only |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/librarian/SOUL.md` (to be created) |
| **Status** | Specified (not yet implemented) |

**Domain:** Nextcloud file search and retrieval, document summarisation on request, knowledge commons indexing (cross-cooperative patterns from `docs/specs/governance-health-signals.md` knowledge commons), helping members locate governance documents, meeting records, and policies.

**Does not own:** File creation/editing (member action), access control (Authentik + Nextcloud sharing governed by member consent), Loomio decisions (Clerk's domain).

**ICA grounding:**
- P5 (Education, Training, and Information): The Librarian is P5 made operational for documents — every member can access the cooperative's collective knowledge without knowing where to look
- P6 (Cooperation Among Cooperatives): Cross-cooperative knowledge sharing (contributed governance patterns) requires a steward to maintain the commons

---

### Steward

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 — formalising existing stub at src/IskanderOS/openclaw/agents/steward/ -->

| Field | Value |
|-------|-------|
| **Mandate** | Treasury transparency and compliance — monitors cooperative finances, tracks economic participation, surfaces compliance obligations; Phase B adds blockchain treasury integration |
| **Loyalty** | Cooperative bylaws (serves the cooperative's legal and financial obligations) |
| **Privacy tier** | Tier 1 — Public Glass Box (financial transparency is a cooperative value) |
| **Hard boundary** | Never moves money; never executes transactions; never accesses individual member financial data; aggregate reporting only |
| **SOUL.md** | `src/IskanderOS/openclaw/agents/steward/SOUL.md` (to be created — stub directory exists) |
| **Status** | Stubbed (directory exists; Phase C.4 delivery) |

**Domain:** Treasury balance reporting (aggregate), surplus allocation tracking, compliance deadline surfacing (filing dates, AGM financial report requirements), Phase B: blockchain treasury contract monitoring, economic participation token tracking.

**Does not own:** Financial transactions (requires human authorisation), member economic data (individual privacy), governance decisions about surplus allocation (Loomio, not Steward).

**ICA grounding:**
- P3 (Member Economic Participation): Members have a right to understand their cooperative's finances; the Steward makes financial transparency effortless
- P4 (Autonomy): Cooperative autonomy requires financial self-awareness — a coop that can't see its own treasury is vulnerable

---

## Mandate Boundaries Reference

Use this table to determine which agent owns a given capability:

| Capability | Owner | Notes |
|------------|-------|-------|
| Summarise open Loomio proposals | Clerk | — |
| Draft a governance proposal | Clerk | Member submits; Clerk drafts |
| Post AGM notice to Mattermost | Clerk | Prepare only; human distributes to all channels |
| Run a consent round | ❌ Nobody | Humans facilitate; Clerk prepares |
| Monthly governance health report | Health Signals | To governance channel, not DMs |
| Individual participation trends | ❌ Nobody | Aggregate only; individual surveillance prohibited |
| Member in distress | Wellbeing | With consent + switching announcement |
| Conflict between two members | Wellbeing | Transformative mediation model |
| Safeguarding concern | Wellbeing → Restricted Glass Box | Level 1/2/3 escalation |
| Cross-cooperative governance inbox | Personal Clerk | PA node only |
| Values assessment for partner coop | Values Council | Public on-chain result |
| Financial transactions | ❌ Nobody (current scope) | Steward reports; humans authorise |
| Treasury balance and surplus reporting | Steward | Aggregate only; no individual financial data |
| Compliance deadline surfacing | Steward | AGM filing dates, regulatory obligations |
| Member removal | ❌ Nobody | Requires Loomio consent decision by members |
| Beszel metrics interpretation | Sentry | Posts to #ops; no remedial action without instruction |
| Backrest backup health | Sentry | Alerts to #ops on failure; humans respond |
| IPFS pin integrity | Sentry | Verification only; no re-pinning without instruction |
| PostgreSQL health | Sentry | Connection pool, replication lag; humans respond |
| Authentik SSO flows | ❌ Nobody unilaterally | Sentry can surface anomalies; changes need Loomio consent |
| Nextcloud file search | Librarian | Read-only; member must open/edit directly |
| Document summarisation | Librarian | On request; never auto-summarises unasked |
| Knowledge commons indexing | Librarian | Cross-coop patterns from opt-in contributions |
| Enforce code of conduct | ❌ Nobody | Human governance function; AI moderation violates uninvited monitoring principle |
| Onboarding facilitation | Clerk (P5) | Clerk explains and educates; not a separate agent |
| IPFS pinning (automated) | Decision-Recorder service | Not an agent; service-level automation |

---

## Adding a New Agent

When adding a new agent, append a row to this file with:
- Agent name
- Mandate (one sentence)
- Loyalty model
- Privacy tier
- Hard boundary
- SOUL.md location
- Status

Then check the Mandate Boundaries Reference for conflicts with existing agents and update the table with the new agent's capabilities.
