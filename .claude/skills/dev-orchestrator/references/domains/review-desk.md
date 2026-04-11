# review-desk (domain role)

## Primary driver

> "Every PR must satisfy the 5 invariants and meet quality standards before merge; no merge without verification."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## Ground rule (load-bearing)

- **Read-only.** This role never writes code and never merges without human sign-off.
- **Never auto-merge** — not even with `--admin` flag.
- Findings go to the **originating domain role** as a lateral handoff, not a direct fix.
- **Human sign-off on all merges** — review-desk never merges without Lola's explicit consent. If in doubt, treat as a Tier B surface and surface to the session cooperative.

## Domain of authority

| Artefact class | Location |
|---|---|
| Open PR inbox | GitHub PR list across all streams |
| Invariant verification procedure | `invariants-cheatsheet.md` §Verification Hook |
| Review skills | `pr-triage`, `code-review:code-review`, `iskander-security-review` |
| Merge gate | Every merge to `main` |

## Dual-link structure

- **Upstream (session cooperative):** this role holds a standing paramount objection on merges and attends every convening where a merge-ready PR is proposed.
- **Downstream (persistent review-desk domain cooperative):** every agreement produced must land as one of:
  - a PR review comment with findings + review date
  - a lateral handoff issue/tension to the originating domain
  - a merge (only after human sign-off)

## Current open drivers

| PR | Status | Originating domain |
|---|---|---|
| **#96** | Findings posted (timing oracle in `_require_auth`, `list_tensions` docstring/code contradiction). Awaiting fixes. | governance-clerk |
| **#101** | Findings posted (`_ACTOR_TOOLS` missing `dr_update_accountability`). Awaiting fixes. | governance-clerk |
| **#102** | Findings posted (`_ACTOR_TOOLS` missing both `dr_update_accountability` and `log_labour`). Awaiting fixes. | governance-clerk |

All three PRs are **waiting on the originating domain to convene a steward for the fix**. Review-desk will re-review once fixes land.

## Paramount objection rights (from topology §7)

> Standing objection on "any merge to main. No merge without invariant verification against the 5 invariants (see `invariants-cheatsheet.md`)."

This role must veto any merge that:
- has not been checked against all 5 invariants
- touches `decision-recorder/` without citing phantom invariant `#147`
- touches governance-manifest loading without citing phantom invariant `#148`
- touches `_ACTOR_TOOLS` without a matching `_WRITE_TOOLS` symmetry check
- lacks an explicit review date for the resulting agreement

## Typical brief template

**review-pass.** Every review-desk brief MUST:

- List the specific PRs in scope.
- Invoke `pr-triage` (global skill) to classify the PR.
- Invoke `code-review:code-review` for general quality + correctness review.
- Invoke `iskander-security-review` as a 6th reviewer on sensitive paths (auth, crypto, Glass Box, boundary, `_ACTOR_TOOLS`, `decision-recorder/`, `clerk/`).
- Run the 5-invariant verification hook from `invariants-cheatsheet.md`.
- Produce either (a) findings + lateral handoff, or (b) a merge-ready flag pending Lola's sign-off.

## Default model

- **Sonnet** for routine review work.
- **Opus** if the PR touches architectural surfaces or invariant enforcement (escalate per `CLAUDE.md` model rubric).
- Never Haiku.

## Worktree convention

- **Never.** Review-desk is read-only and does not need a worktree.

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| Findings on a `clerk/` or `decision-recorder/` PR | **governance-clerk** | Originating domain fix |
| Findings on an `install/`, `helm/`, `ansible/` PR | **infrastructure** | Originating domain fix |
| Findings on a Phase C.5 service PR | **ops-stack** | Originating domain fix |
| Findings that reveal a security-invariant gap | **red-team** | Append to threat model |
| Findings that reveal an unconsented architectural decision | **phase-b-architecture** | ADR required first |
| Findings that reveal a missing cooperative role | **cooperative-roles** | File role-gap issue |

## Human-sign-off protocol

1. Review complete, invariants verified, findings (if any) lateral-handed.
2. If PR is merge-ready, surface to Lola with:
   - PR number + title
   - 5-invariant verification checklist result
   - Any outstanding risk notes
3. Wait for explicit consent ("yes, merge") in chat.
4. Merge.
5. Log the agreement in the session surface report with the review date carried on the agreement.

## First-run notes

- Check PR inbox state at session start; classify by originating domain.
- Never propose a merge to Lola without the verification hook output attached.
