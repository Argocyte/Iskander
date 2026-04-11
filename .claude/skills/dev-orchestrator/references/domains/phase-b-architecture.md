# phase-b-architecture (domain role)

## Primary driver

> "Phase B work must have consented ADRs before any code is written, with at least two alternatives evaluated for each decision."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## Hard rule (load-bearing)

**No code before ADR.** Every ADR brief must consider at least **two alternatives**. If a brief arrives with one alternative, it is **invalid**, and the session cooperative must propose additional alternatives or reject the brief outright.

## Domain of authority

| Artefact class | Location |
|---|---|
| ADRs | `docs/adr/` |
| Standards audit | `#127` |
| ValueFlows gate | `#131` |
| Federation security model | `#104` |
| Asymmetric GTFT decay formal analysis | `#111` |
| Migration plan | `#128` |
| Compliance overlay | `#129` |
| Metagov | `#130` |

## Dual-link structure

- **Upstream (session cooperative):** this role's steward represents Phase B design-consent concerns.
- **Downstream (persistent phase-b-architecture domain cooperative):** every agreement produced must land as one of:
  - a new ADR under `docs/adr/` (with two alternatives and a consent round)
  - an update to an existing ADR with a new review date
  - a closure comment on `#127`, `#131`, `#104`, `#111`, `#128`, `#129`, `#130`

## Current open drivers

| Issue | Driver | Class |
|---|---|---|
| **#127** | Standards audit — gate-blocking for Phase B architecture | Gate |
| **#131** | ValueFlows gate — gate-blocking for Phase B | Gate |
| **#104** | Federation security model — Phase B blocker | ADR |
| **#111** | Asymmetric GTFT decay formal analysis | Research + ADR |
| **#128** | Migration plan | ADR |
| **#129** | Compliance overlay | ADR |
| **#130** | Metagov | ADR |

## Paramount objection rights (from topology §7)

> Standing objection on "any code that implements an unconsented architectural decision. No code before ADR."

This role must veto any brief that proposes:
- implementation of a design that has not cleared a consent round
- an ADR with only one alternative evaluated
- a code change that implicitly commits to a not-yet-decided architectural direction
- any Phase B scoped implementation work while `#127` or `#131` are still open

## Typical brief template

**doc-only.** Phase B drivers produce ADRs (documents), not code. This role delegates almost all its work to `doc-wave-dispatch` for multi-file ADR drafting.

Every brief MUST include:
- the two-alternatives requirement (explicit in the brief, not implicit)
- a consent round procedure: ADR draft → session cooperative review → paramount objection check → review date
- a review date for the resulting ADR
- a citation to ICA Principle 2 (Democratic Member Control) — ADRs are **consented, not decided top-down**

## Default model

- **Opus ALWAYS.** Architectural decisions cost the most to rework; Opus is the cheapest choice over the whole lifecycle.
- Sonnet and Haiku are never appropriate for this role.

## Worktree convention

- Usually **none** — ADR writing is doc-only and touches `docs/adr/` directly on a branch or even main.
- If a multi-file ADR-plus-scaffolding change is needed, use a new worktree under `.claude/worktrees/` named after the ADR.

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| Consented ADR ready for runtime implementation | **governance-clerk** | Clerk-scoped implementation |
| Consented ADR ready for ops-stack implementation | **ops-stack** | Phase C.5 service work |
| Consented ADR ready for infra implementation | **infrastructure** | Install / helm / ansible change |
| ADR reveals a security-adjacent invariant question | **red-team** | Security review input to ADR |
| ADR needs merge | **review-desk** | ADR file merge |
| ADR reveals a missing cooperative role | **cooperative-roles** | File role-gap issue |

## ICA Principle link

- **Principle 2 (Democratic Member Control):** ADRs are consented, not decided top-down. The session cooperative's facilitation round is the consent mechanism.
- **Principle 4 (Autonomy and Independence):** once consented, the ADR is owned by the persistent phase-b-architecture domain cooperative and cannot be overridden by the session cooperative.

## First-run notes

- Check `#127` and `#131` status FIRST. If both are open, they are the highest-tension drivers for this role — everything else waits.
- Never steward a Phase B code driver (as opposed to ADR driver) under any circumstance.
