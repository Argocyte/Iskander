# Invariants Cheatsheet

**Purpose:** canonical paste-box for every code-write brief. Copy verbatim into the
subagent prompt so the invariants travel with the task, not the session.

**Authoritative source:** `CLAUDE.md` §Invariants (lines 48–58). If this file drifts,
`CLAUDE.md` wins. Verify before starting any security-sensitive task.

---

## The Five Invariants — Never Violate

1. **Glass Box before every write.** Every agent write action must log to Glass Box in a
   separate step *before* the write executes. Never weaken or bypass this gate.

2. **Agents draft, humans sign.** No agent holds signing keys or auto-submits votes.
   Agents propose; members decide. Violating this is a critical security defect.

3. **Constitutional Core is immutable.** ICA principle checks cannot be overridden by
   configuration, manifest updates, or runtime flags. Do not add bypass logic.

4. **Tombstone-only lifecycle.** Decisions, attestations, and audit records are never
   deleted — only marked Tombstoned. Immutability is the audit trail.

5. **Boundary layer is sequential.** Foreign activity ingestion has five gates
   (Trust Quarantine → Ontology Translation → Governance Verification → Causal
   Ordering → Glass Box Wrap). Do not skip or reorder.

---

## Phantom Invariants (read before writing a brief)

A **phantom invariant** is a claimed protection with no corresponding code. These are
the highest-risk findings because developers, auditors, and funders all assume coverage
that doesn't exist. Living register: `docs/red-team-threat-model.md` §1.

**Currently confirmed phantoms:**

- **#147** — Tombstone-only lifecycle missing in `decision-recorder` (invariant #4)
- **#148** — Governance manifest has no SHA-256 lock (invariant #3, manifest layer)

**Orchestrator rule:** if a brief touches a file in `decision-recorder/` or anything that
loads `governance_manifest.json`, the brief MUST cite the relevant phantom issue and
require the implementer to either fix or explicitly document the gap they are leaving.

---

## Paste-Box (copy this into every code-write brief verbatim)

```
## Iskander Invariants — DO NOT VIOLATE

1. Glass Box before every write — log to Glass Box in a separate step *before* the write
2. Agents draft, humans sign — no signing keys in agents, no auto-submit
3. Constitutional Core is immutable — no bypass for ICA principle checks
4. Tombstone-only lifecycle — mark tombstoned, never DELETE
5. Boundary layer sequential — 5 gates in order: Trust → Ontology → Governance → Causal → GBWrap

If any change would weaken, bypass, or reorder one of these, STOP and surface it.
Phantom invariants currently tracked: #147 (tombstone in decision-recorder),
#148 (manifest SHA-256 lock). Cite them if your scope touches them.
```

---

## Verification Hook

Before returning "done" on any code-write brief, the implementer must answer (in their
confirmation summary):

- [ ] Did this change touch a Glass Box gate, a signing path, a principle check, a
      delete path, or the boundary layer?
- [ ] If yes — which invariant(s), and how is the change consistent with them?

If either answer is missing, the orchestrator rejects the confirmation and re-dispatches
with the verification requirement restated.
