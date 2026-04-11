# Brief Template — doc-only

Used for documentation-only drivers: ADRs, tracking files, SOUL.md cross-references,
plan/roadmap updates, GitHub issue filing, issue/discussion comments. No code
writes. Short template — delegates to `doc-wave-dispatch`.

---

You are stewarding the <role> role for the driver: <driver statement>. The role's
primary driver is <primary>. Your authority is scoped to this driver; you are not
acting for the role in general.

## Delegation

Invoke the `doc-wave-dispatch` skill at
`C:\Users\argoc\Documents\Iskander\.claude\skills\doc-wave-dispatch\SKILL.md`.
Follow its two-wave pattern exactly: Wave 1 (local files, parallel) must complete
before Wave 2 (GitHub operations, parallel), and the tracking file micro-update
comes after Wave 2.

## Scope

Files to write or edit (with format-reference file noted for each):
- <path> — format ref: <path>
- <path> — format ref: <path>

Issues / discussions to comment on:
- #<N> — <one-line purpose>
- discussion #<N> — <one-line purpose>

New issues to file (with labels):
- <title> — labels: <labels>
- <title> — labels: <labels>

## S3 logbook reminder

Every new agreement this brief produces is logged build-side as a GitHub issue with
an explicit review date in the body (see `cooperative-topology.md` §9 build-side vs
runtime-side S3 mapping). "Agreement without a review date" is invalid. Tensions
filed as issues should carry the `tension` or `invariant-drift` label and a driver
statement in the first paragraph of the body.

## No worktree

Doc-only drivers do not need a worktree — per `doc-wave-dispatch` §Common Mistakes,
worktree setup on doc-only agents wastes time with no isolation benefit. Do not
pass `isolation: "worktree"` to any delegated agent.

## Review date

Return your work as an agreement with review date: <YYYY-MM-DD>

## Confirmation protocol

Per the delegated skill: confirmation lines only, NOT file contents. Expected form:

- Wave 1: `filename → created ✓` or `filename → updated ✓` per file.
- Wave 2: `#N → comment posted ✓` per comment; `#N — title → created ✓` per new issue.
- Tracking file micro-update status: `updated with #<first>–#<last> ✓`.
