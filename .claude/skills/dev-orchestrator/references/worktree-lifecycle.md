# Worktree Lifecycle

**Purpose:** every steward brief that writes code must target a worktree. This
file is the convention for choosing one, the lookup table of current feature
worktrees, and the collision and pruning rules.

The facilitator picks the worktree when proposing a brief; the domain role
accepts or raises a paramount objection. See `cooperative-topology.md` §6
(convening loop) for how this fits into dispatch.

---

## Three locations

Iskander has **three** places worktrees live, each with a different meaning.

### 1. `C:/Users/argoc/Documents/Iskander/` — main checkout (`main` branch)

**NEVER** convene a code-write steward against this path. The main checkout
is the reader's copy. Code-write stewards always target a branch worktree.
Directly modifying `main` would bypass the review-desk paramount objection
on merges (see `cooperative-topology.md` §7).

### 2. `C:/Users/argoc/Documents/Iskander/.worktrees/` — long-lived feature worktrees

These are the **preferred reuse target** when a new driver matches the driver
of an existing branch. Re-using a worktree is a tie-breaker in
`priority-rules.md`.

### 3. `C:/Users/argoc/Documents/Iskander/.claude/worktrees/` — transient session worktrees

Claude session branches (e.g. `awesome-snyder`, `zealous-lederberg`). Created
fresh per convening when **no** feature worktree matches the driver. These
are disposable by design — the session cooperative forms and dissolves
around them.

---

## Lookup table — current feature worktrees (as of 2026-04-11)

Verified via `git worktree list`. Each entry shows the driver it currently
holds and the domain role most likely to steward it.

| Worktree | Branch | Driver | Typical domain role |
|---|---|---|---|
| `.worktrees/e2e-verification` | `feature/e2e-verification` | End-to-end verification harness | review-desk |
| `.worktrees/governance-health-signals` | `feature/governance-health-signals` | Governance health telemetry | governance-clerk |
| `.worktrees/librarian-agent` | `feature/librarian-agent` | Librarian agent (issue #51) | cooperative-roles |
| `.worktrees/meeting-prep-clerk` | `feature/meeting-prep-clerk` | Clerk meeting-prep tool | governance-clerk |
| `.worktrees/membership-provisioning` | `feature/membership-provisioning` | Clerk member provisioning | cooperative-roles / governance-clerk |
| `.worktrees/security-fixes` | `fix/red-team-security-hardening` | Red-team audit fixes | red-team |
| `.worktrees/steward-data` | `feature/steward-data-service` | Steward (ops/treasury) data service | ops-stack |

Transient `.claude/worktrees/` present at verification time:
`awesome-snyder`, `zealous-lederberg` — no fixed driver, available for
the next convening cycle.

---

## Collision rule

Within a single convening wave, **no two stewards may target the same
worktree**. The wave planner serialises stewards that share a worktree:
only one holds the worktree at a time, the next waits until the first
steward returns its agreement.

This rule exists because parallel code writes on the same branch race each
other — the second steward's agreement would overwrite the first's before
the review-desk steward gets a chance to consent.

---

## Orphan detection

An **orphaned worktree** is a directory that exists under
`.claude/worktrees/` but is not listed in `git worktree list` (e.g. a
directory left behind by a crashed session or an incomplete prune).

Detection procedure:

1. `ls .claude/worktrees/` — list directories on disk
2. `git worktree list` — list worktrees git knows about
3. Any directory in (1) but not in (2) is an orphan

**Current state (2026-04-11):** no orphans detected. Both
`.claude/worktrees/awesome-snyder` and `.claude/worktrees/zealous-lederberg`
are registered in `git worktree list`.

---

## Pruning protocol

**Never prune automatically.** Pruning is a decision, not a mechanical
action. The facilitator surfaces pruning proposals as **Tier A decisions**
via `human-decision-protocol.md` — Lola consents before any worktree is
removed.

This is because a worktree can carry uncommitted work, an in-flight
agreement with no review date yet, or a driver that a domain steward has
not yet accepted. Only Lola (as the sole human member of the project
cooperative) can consent to discarding any of those.

See also **issue #145** — the open tension tracking worktree cleanup.
Any pruning proposal must cite it.
