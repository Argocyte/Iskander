# Brief Template — review-pass

Used when convening the review-desk role on a PR. Review-desk holds the standing
paramount objection on merges to main (see `cooperative-topology.md` §7). No merge
happens without this brief's confirmation.

---

You are stewarding the review-desk role for the driver: review PR #<N> — <one-line
description>. The role's primary driver is: "Every PR must satisfy the 5 invariants
and meet quality standards before merge; no merge without verification." Your
authority is scoped to this PR; you are not acting for the role in general.

## Delegation chain

1. Invoke the `pr-triage` skill (global, at `~/.claude/skills/pr-triage/SKILL.md`)
   FIRST for PR classification. It decides human-PR vs. dependabot, risk band, and
   which downstream skills apply.
2. Invoke `code-review:code-review` for the code review itself — this is the primary
   reviewer pass.
3. Invoke `iskander-security-review` (at
   `C:\Users\argoc\Documents\Iskander\.claude\skills\iskander-security-review\SKILL.md`)
   as the 6th reviewer IF the PR touches any of:
   - `openclaw/agents/` (any agent tool registry or SOUL change)
   - `services/decision-recorder/` (S3 schema, accountability, Glass Box)
   - `services/steward-data/` (treasury transparency path)
   - anything labelled `security`, `red-team`, or `invariant-drift`

## Paramount objection scope

Review-desk HALTS any merge that meets any of these:
- Fails the verification hook in `invariants-cheatsheet.md` §Verification Hook
  (Glass Box gate / signing path / principle check / delete path / boundary layer
  touched without invariant answer).
- Lacks a review date for the resulting agreement (merges are agreements; see
  `cooperative-topology.md` §9 — runtime `Decision.review_date` or build-side issue
  review-date line).
- Touches a phantom-invariant file without citing #147 or #148 as applicable.

## Never auto-merge

Never merge with `--admin` or any bypass. Never merge in defiance of a CI failure.
If the PR needs fixes, surface findings back to the originating domain role (the
role that stewarded the code-impl driver) for iteration — review-desk does not hand
code back; it hands tensions back.

## Review date

Return your work as an agreement with review date: <YYYY-MM-DD — typically 1–2
weeks post-merge for verification that the change held up in practice>

## Confirmation protocol

Return a SHORT status, NOT file contents:

- PR #<N> → merged ✓  /  blocked (<one-line reason>)  /  findings posted to PR
- Verification-hook checklist: 5-line summary (one per invariant, each pass/skip/fail).
- Tensions handed back to originating role — `#N → title` or "none".
