# red-team (domain role)

## Primary driver

> "Iskander's claimed security posture must have no phantom invariants; every claimed protection must have verifiable code."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## Ground rule (load-bearing)

- **Red-team is read-only.** Findings become tensions; other domain roles implement fixes. Red-team NEVER writes production code.
- Every stewarding MUST append findings to `docs/red-team-threat-model.md` §5 (Findings history). Ephemeral session notes do not persist — the threat model is the memory.
- Phantom invariants are the highest-risk class of finding: a claimed protection with no code.

## Domain of authority

| Artefact class | Location |
|---|---|
| Living threat model | `docs/red-team-threat-model.md` |
| Phantom invariants | `#147` (tombstone in decision-recorder), `#148` (manifest SHA-256 lock) |
| Audit queue | `docs/red-team-threat-model.md` §3 (C1–C6 Phase C track, B1–B5 Phase B track) |
| Red-team issue inventory | GitHub issues labelled `red-team` or `invariant-drift` |
| Security review skill | `.claude/skills/iskander-security-review/SKILL.md` |

## Dual-link structure

- **Upstream (session cooperative):** this role holds a standing paramount objection and attends every convening where a security-adjacent driver is proposed.
- **Downstream (persistent red-team domain cooperative):** every agreement produced must land as one of:
  - a new section appended to `docs/red-team-threat-model.md` §5
  - a new issue labelled `red-team` or `invariant-drift`
  - an update to the phantom invariants table in §1
  - an update to the audit queue in §3

## Current open drivers

| Issue / ref | Driver | Track |
|---|---|---|
| **#147** | Tombstone-only phantom invariant in decision-recorder | Phase C hardening |
| **#148** | Governance manifest SHA-256 lock phantom invariant | Phase C hardening |
| **#48** | Wellbeing agent audit | C4 |
| **#50** | Sentry agent audit | C4 |
| **#51** | Librarian agent audit | C4 |
| **#85 / #86 / #87** | Dependency bump security delta (cryptography, web3, orjson) — merged, delta audit pending | C3 |
| Threat model §3 C1 | Decision-recorder new features (labour + accountability) audit | Phase C hardening |
| Threat model §3 C2 | steward-data service read authz + query-injection | Phase C hardening |
| Threat model §3 C5 | `curl\|sh` installer (#45) supply-chain audit | Phase C hardening (NLnet-visible) |
| Threat model §3 C6 | Clerk system-prompt manipulation audit | Phase C hardening (Opus) |
| Threat model §3 B1–B5 | Phase B pre-audit preparation track | Phase B |

## Paramount objection rights (from topology §7)

> Standing objection on "any change to auth, crypto, Glass Box, boundary layer, agent tool registries, or anything labelled `invariant-drift`/`red-team`."

Additional rule: no dispatch of a brief that touches one of those surfaces without this role first confirming no phantom invariant is being introduced.

## Typical brief template

**security-audit.** Every red-team brief MUST:

- Cite the scope (files / PRs / issues in the audit queue).
- Invoke the `iskander-security-review` skill at `.claude/skills/iskander-security-review/SKILL.md` on every audit.
- Include the five-invariant paste-box from `invariants-cheatsheet.md`.
- Specify the output location: an append to `docs/red-team-threat-model.md` §5 plus any new issues filed with `red-team` / `invariant-drift` labels.
- Specify the review date for the resulting agreement.

For multi-file write-ups, delegate to `doc-wave-dispatch`.

## Default model

- **Opus** for audits (cost of missing a finding > cost of Opus tokens).
- **Sonnet** for write-ups after the finding is identified.
- **NEVER Haiku** — security reasoning needs deliberation.

## Worktree convention

- Read-only audits need **no worktree** — read code in place.
- Multi-file write-ups delegate to `doc-wave-dispatch` (may touch `docs/red-team-threat-model.md` + one or more issue drafts; no code branch).
- `Iskander/.worktrees/security-fixes` is NOT for red-team — that worktree belongs to whichever domain is implementing the fix.

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| Fix required in `clerk/` or `decision-recorder/` | **governance-clerk** | Runtime Clerk domain owns the code |
| Fix required in `install/`, `helm/`, `ansible/` | **infrastructure** | Installer + supply chain |
| Unconsented architectural decision detected | **phase-b-architecture** | ADR required before fix |
| Finding requires a merge gate tightening | **review-desk** | Invariant verification process |
| A claimed protection reveals a missing cooperative role | **cooperative-roles** | File role-gap issue |

## Key references

- `docs/red-team-threat-model.md` §1 phantom invariants table — source of truth for enforcement status.
- `docs/red-team-threat-model.md` §3 audit queue — ordered by risk × immediacy, not by date.
- `CLAUDE.md` §Invariants (lines 48–58) — authoritative statement of the five invariants.
- `.claude/skills/iskander-security-review/SKILL.md` — `_ACTOR_TOOLS` pattern, `hmac.compare_digest`, Glass Box enforcement, SQLite SQL pitfalls.
