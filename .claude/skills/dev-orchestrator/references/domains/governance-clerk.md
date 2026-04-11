# governance-clerk (domain role)

## Primary driver

> "Iskander's S3 governance must be facilitatable, tracked, and auditable by the Clerk agent and its services."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## Runtime counterpart

- The runtime Clerk agent is live in Phase C and already holds the **persistent governance-clerk domain cooperative** (see `src/IskanderOS/openclaw/agents/clerk/SOUL.md`).
- This build-side role is **double-linked** with that runtime cooperative: the artefacts the runtime Clerk depends on (schemas, tools, SOUL.md, system prompt) are the same artefacts this role stewards on the build side.
- Session cooperative is upstream; runtime Clerk domain cooperative is downstream.

## Domain of authority

| Artefact class | Location |
|---|---|
| Clerk agent source | `src/IskanderOS/openclaw/agents/clerk/` |
| Decision recorder service | `src/IskanderOS/services/decision-recorder/` |
| S3 schemas | `Tension`, `Decision`, `LabourLog`, `GlassBoxEntry` in `decision-recorder/db.py` |
| Clerk write tools | `_ACTOR_TOOLS` / `_WRITE_TOOLS` symmetry in `clerk/tools.py` |
| Clerk SOUL + system prompt | `clerk/SOUL.md`, `clerk/agent.py` |
| Loomio / Mattermost HITL plumbing | `clerk/tools.py` Loomio block |

## Dual-link structure

- **Upstream (session cooperative):** this role's steward represents Clerk concerns in the current session. Raises tensions into the session logbook; accepts drivers from Lola or lateral handoffs.
- **Downstream (persistent Clerk domain cooperative):** every agreement produced must land as one of:
  - a commit to `clerk/` or `decision-recorder/`
  - an update to `clerk/SOUL.md`
  - a new row type / field on `Tension` / `Decision` / `LabourLog`
  - a new `_ACTOR_TOOLS` entry with matching `_WRITE_TOOLS` symmetry

## Current open drivers

| Issue / PR | Driver | Tension class |
|---|---|---|
| **#96** | steward-data service has open review findings (timing oracle in `_require_auth`, `list_tensions` docstring/code contradiction) | code-impl, fix round 2 |
| **#101** | Clerk accountability tracking PR — `_ACTOR_TOOLS` missing `dr_update_accountability` | code-impl, invariant-drift |
| **#102** | Clerk DisCO labour tracking PR — `_ACTOR_TOOLS` missing `dr_update_accountability` AND `log_labour` | code-impl, invariant-drift |
| **#149** | circle-membership authz (`dr_*` tools) | code-impl |
| **#150** | tension state machine (open → in_progress → resolved) | code-impl + schema |
| **#151** | system-prompt write-tools gap — needs human decision, Tier A surface | design review, Opus |

## Paramount objection rights (from topology §7)

> Standing objection on "any change that weakens S3 governance patterns (tensions, agreements, review dates, consent)."

This role must veto any brief that proposes:
- removing review dates from agreements
- skipping tension logging
- introducing a decision path that doesn't produce a `Decision` row
- auto-approving without explicit consent
- removing or weakening the `_ACTOR_TOOLS` / `_WRITE_TOOLS` symmetry

## Typical brief template

**code-impl** for #96, #101, #102, #149, #150.
**design review (Opus)** for #151.

Every brief MUST include:
- the five-invariant paste-box from `invariants-cheatsheet.md`
- a review date for the resulting agreement
- a citation to the existing schema field or tool the change modifies (topology §9 list)

## Default model

- **Sonnet** for implementation work on #96, #101, #102, #149, #150.
- **Opus** for #151 (system-prompt redesign — expensive rework, architectural).
- Never Haiku (write paths are security-sensitive).

## Worktree convention

- Reuse `Iskander/.worktrees/governance-health-signals` for health-signal-adjacent drivers.
- Reuse `Iskander/.worktrees/meeting-prep-clerk` for meeting-agenda-adjacent drivers.
- Otherwise create a new branch under `.claude/worktrees/` named after the driver (e.g. `accountability-actor-tools-fix`).

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| Any security-adjacent finding surfaces during code-write | **red-team** | Security review + invariant check |
| A PR is ready for invariant verification before merge | **review-desk** | Merge gate |
| A new Clerk capability requires a design decision | **phase-b-architecture** | ADR before code |
| A finding reveals a missing cooperative role | **cooperative-roles** | File role-gap issue |
| A finding requires install / supply-chain change | **infrastructure** | Scope change |

## First-run notes

- On first convening of this role in any session, read `CLAUDE.md` §Invariants and `clerk/SOUL.md` before drafting any brief.
- If #151 is still open, flag it as a Tier A human-decision surface for Lola — do not steward it without explicit consent.
