# ops-stack (domain role)

## Primary driver

> "Phase C.5 must provide the S3 domain backbone (ops-data + Quartermaster + Treasurer + Estates Warden) for cooperative operations."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## Gate (hard-skip rule — load-bearing)

**This role is BLOCKED until both of the following have preliminary outputs:**

- **#127** — Standards audit (gate-blocking for Phase B architecture)
- **#131** — ValueFlows gate (gate-blocking for Phase B)

Hard-skip rule: **do not convene stewards for ops-stack drivers if either gate is still open.** The session cooperative must surface the gate as a blocker to Lola and move on to other domains.

Rationale: Phase C.5 ops-data schema is downstream of the standards audit (which standards must the schema align to) and the ValueFlows gate (which economic event vocabulary is canonical). Writing ops-data before either gate clears creates expensive rework.

## Domain of authority

| Artefact class | Location |
|---|---|
| Phase C.5 tracking issues | `#134`–`#143` |
| ops-data service (planned) | `services/ops-data/` |
| Quartermaster role (agent) | `#136` |
| Treasurer role (agent) | `#137` |
| Estates Warden role (agent) | `#138` |
| Phase C.5 tracking file | `.claude/phase-c5-tracking.md` (read if present; reconstruct from GitHub issues if absent) |

## Dual-link structure

- **Upstream (session cooperative):** this role's steward represents Phase C.5 delivery concerns.
- **Downstream (persistent ops-stack domain cooperative):** every agreement produced must land as one of:
  - a commit under `services/ops-data/`
  - a new agent under `openclaw/agents/` with matching `SOUL.md`
  - an update to the Phase C.5 tracking file (create if absent)
  - a closure comment + review date on one of `#134`–`#143`

## Current open drivers

| Issue | Driver | Status |
|---|---|---|
| **#134–#143** | Phase C.5 ops-stack cluster | **BLOCKED on #127, #131** |
| **#136** | Quartermaster agent | Blocked |
| **#137** | Treasurer agent | Blocked |
| **#138** | Estates Warden agent | Blocked |

## Paramount objection rights

No standing paramount objection from this role. However:

- This role must NOT accept a driver while the hard-skip gate is active.
- Once unblocked, this role coordinates with **phase-b-architecture** for ops-data schema decisions (schema freeze is an ADR-class decision).

## Typical brief template

**code-impl** (once unblocked).

Every brief MUST include:
- the five-invariant paste-box from `invariants-cheatsheet.md`
- a review date for the resulting agreement
- citation to the Decision / Tension / LabourLog schema if the service persists state (topology §9)
- confirmation that #127 and #131 have cleared (the gate check)

## Default model

- **Sonnet** for routine implementation once unblocked.
- **Opus** for ops-data schema freeze (once frozen, rework is expensive — this is an Opus-class decision).
- Haiku never used here.

## Worktree convention

- `Iskander/.worktrees/steward-data` for Phase C.5 service work (already exists on disk).
- Other worktrees per-driver as needed under `.claude/worktrees/`.

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| A driver surfaces a schema decision needing an ADR | **phase-b-architecture** | ADR before implementation |
| A security-adjacent finding surfaces | **red-team** | Security review |
| Ready for merge | **review-desk** | Invariant verification |
| Requires install/helm/ansible changes | **infrastructure** | Cross-domain dependency |
| A new coop role (e.g. Quartermaster) needs organisational placement | **cooperative-roles** | Role inventory update |

## First-run notes

- Check `#127` and `#131` status FIRST. If either is open, do not convene a steward — return the gate as a surfaced blocker to the session cooperative.
- If `.claude/phase-c5-tracking.md` exists, read it as the authoritative state.
- If absent, reconstruct state from GitHub issues `#134`–`#143` and propose to Lola that a tracking file be created.
