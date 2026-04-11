# cooperative-roles (domain role)

## Primary driver

> "Every organisationally-necessary cooperative role must be represented by an agent; coverage gaps are tensions to be filed as issues."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## What this role is

A **meta-role**. Its job is to notice when a cooperative role is organisationally necessary but not represented by an agent, and to file the gap as a tension (GitHub issue). It does not itself implement the missing roles — that work hands laterally to `phase-b-architecture` (for the ADR) and then to `governance-clerk` / `ops-stack` / `infrastructure` (for runtime implementation).

## Domain of authority

| Artefact class | Location |
|---|---|
| Role inventory (this file's coverage table) | below |
| Role-gap issues | GitHub issues labelled `role-gap` or similar |
| ICA principle mapping | each role's link to the 7 ICA cooperative principles |
| Clerk-vs-Company-Secretary boundary | this file (distinction is load-bearing) |

## Current coverage gap (the reason this role exists)

| Role | ICA link | Phase | Status |
|---|---|---|---|
| **Company Secretary** | Legal compliance, FCA filings, member register | C | Not designed — file issue |
| **Education Officer** | ICA Principle 5 (education, training, public info) | C / B | Not designed — file issue (P5 is constitutional) |
| **Data Protection Officer (DPO)** | GDPR — mandatory given AI + member PII | C | Not designed — file issue |
| **Electoral Officer** | Circle elections, scrutineering, electoral roll | C | Not designed — file issue |
| **Communications Officer** | Public website, newsletter, cooperative identity (ties to #117, #124) | C | Owner missing |
| **Ombudsperson / Advocate** | Neutral member complaints handler | B | Not designed |
| **Solidarity / Mutual Aid Coordinator** | ICA Principle 6 (cooperation among cooperatives) — hardship fund | B | Not designed |
| **Chronicler / Historian** | Cooperative memory over time | B | Not designed |

## Clerk vs Company Secretary distinction (load-bearing)

- **Clerk** = S3 facilitator (day-to-day governance). Runtime: `src/IskanderOS/openclaw/agents/clerk/`. Owned by the `governance-clerk` domain role.
- **Company Secretary** = legal compliance (annual returns, FCA filings, member register, registered office obligations). Not yet designed.

**Both must exist.** A cooperative cannot substitute the Clerk for the Company Secretary; the legal compliance obligations are distinct from the S3 facilitation obligations. Any brief that conflates them is invalid.

## Non-optional roles (flagged as constitutional)

- **DPO is not optional.** GDPR Article 37 mandates a DPO given the combination of AI processing and member PII. File as Phase C priority. If Iskander ships without one, it is in breach of GDPR.
- **Education Officer is constitutional.** ICA Principle 5 (Education, Training and Information) is load-bearing per `CLAUDE.md` §Design rules. A cooperative violating it is in breach of its own constitution.

## Dual-link structure

- **Upstream (session cooperative):** this role's steward represents organisational-role coverage concerns.
- **Downstream (persistent cooperative-roles domain cooperative):** every agreement produced must land as one of:
  - a new GitHub issue with `role-gap` label (one per missing role)
  - an update to the coverage table above
  - a lateral handoff to `phase-b-architecture` for a new-agent ADR

## First-run action

On the **first convening** of the dev-orchestrator session that includes this role:

1. File GitHub issues for each missing role in the coverage table above (8 issues if none exist yet).
2. Delegate the issue-filing via a **doc-only brief** to `doc-wave-dispatch`.
3. Link each issue to its ICA principle (Principle 5 for Education Officer, Principle 6 for Solidarity Coordinator, etc.).
4. Reference related existing issues (`#117`, `#124` for Communications Officer).

## Paramount objection rights

> Role-specific: any decision that **removes** or **weakens** a cooperative role without explicit consent from the project cooperative.

This role must veto any brief that proposes:
- merging two organisationally-distinct roles (e.g. Clerk + Company Secretary)
- deferring the DPO indefinitely (GDPR breach)
- demoting the Education Officer below constitutional status (ICA Principle 5 breach)

## Typical brief template

**doc-only** (for filing the role-gap issues and updating the coverage table).

Every brief MUST include:
- the coverage table from this file as the starting state
- citation to the relevant ICA principle for each role
- an explicit instruction NOT to implement the roles (this role only files gaps)
- a review date for the resulting agreement

## Default model

- **Sonnet** for inventory work (filing gap issues, updating tables).
- **Opus** for architectural placement of new roles (which domain cooperative should each new role live in? this is an Opus-class design question).
- Haiku never used here (classification work is nuanced).

## Worktree convention

- Usually **none** — doc-only work touches the issue tracker + this file.
- If a multi-file role-placement change is needed, create a new branch under `.claude/worktrees/` named after the role.

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| A filed role-gap issue needs architectural placement | **phase-b-architecture** | ADR for the new agent |
| A filed role-gap issue is runtime-ready (design already exists) | **governance-clerk** | Runtime agent implementation |
| Role requires treasury / ops-data integration | **ops-stack** | Phase C.5 coordination |
| Role requires install / helm changes (e.g. new service) | **infrastructure** | Infra scope |
| Role-gap finding reveals a security invariant gap | **red-team** | Security review |
| New role ready to ship | **review-desk** | Merge gate |

## ICA principle mapping reference

- **Principle 1 (Voluntary and Open Membership):** Electoral Officer supports this
- **Principle 2 (Democratic Member Control):** Clerk + Electoral Officer + Ombudsperson
- **Principle 3 (Member Economic Participation):** Treasurer + Quartermaster
- **Principle 4 (Autonomy and Independence):** Company Secretary + DPO
- **Principle 5 (Education, Training and Information):** Education Officer + Communications Officer + Chronicler
- **Principle 6 (Cooperation among Cooperatives):** Solidarity / Mutual Aid Coordinator
- **Principle 7 (Concern for Community):** Communications Officer + Solidarity Coordinator

## First-run notes

- On first convening in any session, check whether the role-gap issues from the coverage table have already been filed. If not, this role's highest-tension driver is filing them (first-run action above).
- Do NOT attempt to implement any missing role. File the gap, hand across, dissolve the steward.
