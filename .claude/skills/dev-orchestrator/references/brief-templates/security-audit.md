# Brief Template — security-audit

Used when convening the red-team role on an audit driver. Red-team holds the standing
paramount objection over security-affecting changes (see `cooperative-topology.md` §7),
so this brief is also the mechanism through which red-team's objection gets recorded.

---

You are stewarding the red-team role for the driver: <driver statement>. The role's
primary driver is: "Iskander's claimed security posture must have no phantom
invariants; every claimed protection must have verifiable code." Your authority is
scoped to this audit driver; you are not acting for the role in general.

## Scope

Files in scope: <paths, with line ranges>.
Commit SHAs in scope: <SHAs or PR #N>.
Invariants in scope: <subset of the 5; usually at least one of #1 Glass Box, #2
agents-draft-humans-sign, #3 Constitutional Core, #4 tombstone, #5 boundary>.
Labels in scope: <e.g. `red-team`, `invariant-drift`, `security`>.

## Ground rules

Red-team is **read-only** for this audit. Do not land code. Do not edit production
files. If a finding requires a fix, it becomes a **tension** raised in another
domain role (usually governance-clerk or the domain owning the affected file), not a
direct commit. Tensions are filed as GitHub issues per `cooperative-topology.md` §9
build-side logbook mapping.

## Iskander Invariants — DO NOT VIOLATE (reference, not implementation)

1. Glass Box before every write — log to Glass Box in a separate step *before* the write
2. Agents draft, humans sign — no signing keys in agents, no auto-submit
3. Constitutional Core is immutable — no bypass for ICA principle checks
4. Tombstone-only lifecycle — mark tombstoned, never DELETE
5. Boundary layer sequential — 5 gates in order: Trust → Ontology → Governance → Causal → GBWrap

If any change would weaken, bypass, or reorder one of these, STOP and surface it.
Phantom invariants currently tracked: #147 (tombstone in decision-recorder),
#148 (manifest SHA-256 lock). Cite them if your scope touches them.

## Reference skill — MUST invoke

Invoke the `iskander-security-review` skill at
`C:\Users\argoc\Documents\Iskander\.claude\skills\iskander-security-review\SKILL.md`
BEFORE forming any finding. It encodes the 6 Iskander-specific patterns the auditor
is expected to apply: `_ACTOR_TOOLS` / `_WRITE_TOOLS` symmetry, `hmac.compare_digest`
for any HMAC comparison, Glass Box enforcement in the call path, SQLite SQL
pitfalls, and the rest. A finding that ignores these patterns is not a red-team
finding — it is an unreviewed opinion.

## Phantom invariant check (primary driver work)

The phantom invariants register lives at `docs/red-team-threat-model.md` §1 and the
gap list is mirrored in `cooperative-topology.md` §9. Cross-reference the scope
against both. Cite #147 and #148 where relevant. If this audit reveals a new phantom,
its issue MUST carry the `invariant-drift` label and be appended to §1 of the threat
model in the same commit that lands this brief's agreement.

## Append to threat model

Every red-team stewarding MUST append its findings to §4 ("Audit History") of
`docs/red-team-threat-model.md`, with commit SHAs in scope, invariants checked,
findings list with severity, and the agreement's review date. The threat model is
the durable logbook for the red-team domain cooperative.

## Review date

Return your work as an agreement with review date: <YYYY-MM-DD — typically the next
Phase boundary, e.g. Phase C GA or Phase B start>

## Confirmation protocol

Return a SHORT status, NOT file contents:

1. Findings list, each with severity C/M/L and a one-line description.
2. Tensions filed as GitHub issues — `#N → title` for each, with label set.
3. Threat-model §4 diff summary — one paragraph describing what was appended.
4. Paramount objection status — is red-team raising a standing objection on any
   currently in-flight driver as a result of this audit? If yes: driver ID + reason.
