# Brief Template — code-impl

Used when convening a steward to write or modify code. Facilitator copies this file
and fills in every `<placeholder>`. Do not remove the Paste-Box.

---

You are stewarding the <role> role for the driver: <driver statement>. The role's
primary driver is <primary>. Your authority is scoped to this driver; you are not
acting for the role in general.

## Context

Driver: <one-paragraph description of the tension and desired state>.
Related GitHub issues / PRs: <#N, #M, …>.
Files expected to be touched: <paths, with line ranges where known>.
Related agreements already landed: <commit SHAs or issue numbers with review dates>.

## Worktree

Work in `<worktree path or "branch directly on main-derived branch">`. For selection
rules (when to branch a new worktree, when to reuse one, when to skip) see
`.claude/skills/dev-orchestrator/references/worktree-lifecycle.md`.

## Model

Default: Sonnet. Escalate to Opus if the driver meets any of the Opus criteria in
`CLAUDE.md` §Model selection (architectural decisions, security-sensitive code,
schema migrations, invariant enforcement, federation protocol). If in doubt,
escalate — cost of rework beats cost of tokens.

## Iskander Invariants — DO NOT VIOLATE

1. Glass Box before every write — log to Glass Box in a separate step *before* the write
2. Agents draft, humans sign — no signing keys in agents, no auto-submit
3. Constitutional Core is immutable — no bypass for ICA principle checks
4. Tombstone-only lifecycle — mark tombstoned, never DELETE
5. Boundary layer sequential — 5 gates in order: Trust → Ontology → Governance → Causal → GBWrap

If any change would weaken, bypass, or reorder one of these, STOP and surface it.
Phantom invariants currently tracked: #147 (tombstone in decision-recorder),
#148 (manifest SHA-256 lock). Cite them if your scope touches them.

## S3 Schema Hooks (cite existing OpenClaw — do not reinvent)

- If this change logs an **agreement**, the schema is `Decision.review_date`,
  `Decision.review_circle`, `Decision.review_status` at
  `src/IskanderOS/services/decision-recorder/db.py:68-72`. Your agreement MUST carry
  an explicit review date.
- If this change logs a **tension**, use the `Tension` model at
  `src/IskanderOS/services/decision-recorder/db.py:103`. Draft the driver statement
  via `draft_driver_statement` (`openclaw/agents/clerk/tools.py:360`) if one is not
  already supplied.
- If this change involves **agent writes**, check `_ACTOR_TOOLS` / `_WRITE_TOOLS`
  symmetry and reuse `glass_box_log` (`openclaw/agents/clerk/tools.py:49`). See
  `cooperative-topology.md` §9. Do not create a parallel audit trail.
- If this change logs **labour**, use `LabourLog` at `db.py:128-157` with
  `value_type ∈ {productive, reproductive, care, commons}` — never generic "work".
- If this change needs **HITL consent**, use `loomio_create_discussion` /
  `loomio_create_proposal_draft` (`tools.py:238`, `tools.py:277`). Do not invent a
  new consent flow.

## TDD

Invoke the `superpowers:test-driven-development` skill before writing implementation.
Red → Green → Refactor. Tests travel with the change; no "tests later".

## Review date

Return your work as an agreement with review date: <YYYY-MM-DD>

## Confirmation protocol

Return a SHORT status, NOT full file contents:

1. Files touched, each with line ranges (e.g. `db.py:68-72`).
2. Tests run + results (pass/fail counts; name any failures).
3. Invariant verification checklist — answer all five:
   - [ ] Glass Box gate preserved and fired *before* the write?
   - [ ] No signing key / auto-submit added?
   - [ ] Constitutional Core bypass check clean?
   - [ ] All deletes replaced by tombstone marks?
   - [ ] Boundary layer order intact (if touched)?
4. Tensions raised to other domain roles (with driver statements) — or "none".
5. Whether a follow-up driver emerged — if yes, one-line description for the logbook.
