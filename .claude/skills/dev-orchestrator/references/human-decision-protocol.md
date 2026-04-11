# Human Decision Protocol

**Purpose:** some drivers need Lola's explicit consent before the session
cooperative can act on them. This file is the surface format.

The session cooperative (ephemeral, forms per session) cannot override the
project cooperative's authority. Lola is double-linked into the session
cooperative from the project cooperative (see `cooperative-topology.md` §2)
and holds consent rights on anything that exceeds the session cooperative's
domain of autonomy.

---

## Two tiers

### Tier A — Queue decisions

**When:** ambiguous specs, scope questions, choice between equivalent
approaches with no felt tension favouring one. The session cooperative can
continue attending to other drivers while Lola considers.

**Surface mechanism:** include the decision in the Phase 4 Roll-up report.
Lola reviews at their convenience. The orchestrator does **not** convene a
steward for this driver until Lola consents.

### Tier B — Halt decisions

**When:** a domain role raises a **paramount objection** — red-team on
security, review-desk on a merge, phase-b-architecture on unconsented ADR
work, governance-clerk on weakening S3 patterns. See the full table in
`cooperative-topology.md` §7.

**Surface mechanism:** the session cooperative **halts the relevant
convening** until the objection is resolved. The facilitator surfaces the
halt and the objecting role's reason in the surface report, immediately,
not at Phase 4 roll-up. Other drivers that don't touch the halted domain
may continue.

---

## Tier A format (queue decision)

```
### Decision: <short title>
**Driver:** <one-line driver statement>
**Domain(s) affected:** <list of domain roles>
**Options:**
1. <option 1> — trade-offs
2. <option 2> — trade-offs
**Default (if no response):** <safe fallback>
**Review date (if accepted):** <YYYY-MM-DD>
```

Every Tier A decision that results in an accepted option becomes an
agreement, and every agreement has a review date (see
`cooperative-topology.md` §3 row "Agreement"). The facilitator must
pre-fill the review date field when drafting the decision.

---

## Tier B format (halt decision)

```
### HALT: <short title>
**Halt reason:** <what would be violated if this proceeded>
**Objecting role:** <domain role raising the paramount objection>
**Driver being halted:** <the driver this blocks>
**Unhalt condition:** <what must happen before the convening can resume>
**Affected worktree / issue / PR:** <identifiers>
```

Only the objecting role can lift a Tier B halt, and only by withdrawing
the paramount objection or declaring it resolved. The facilitator cannot
lift it.

---

## Worked example: issue #151 (system-prompt redesign)

Issue #151 is a driver with multiple architectural alternatives and no
clear tension favouring one. This is a classic Tier A queue decision.

```
### Decision: system-prompt redesign approach (#151)
**Driver:** The orchestrator's system prompt is growing past what Sonnet can hold
without crowding out working context, and two approaches are on the table.
**Domain(s) affected:** phase-b-architecture, cooperative-roles
**Options:**
1. Split the prompt into a core + a set of lazily-loaded domain context files
   — trade-off: adds loading latency per convening, simpler mental model
2. Compress the prompt into a single dense S3-vocabulary reference — trade-off:
   faster convening, less room for domain-specific detail
**Default (if no response):** continue with current prompt; re-raise at next
phase-b-architecture convening
**Review date (if accepted):** 2026-05-11
```

The session cooperative does not convene a steward for #151. Lola decides
at their convenience; the chosen option then gets convened as a separate
driver with the review date above.

---

## ICA Principle 2 link

**Democratic member control** (ICA Principle 2): cooperatives are democratic
organisations controlled by their members, who actively participate in
setting policies and making decisions.

Lola is the only human member of the Iskander project cooperative.
Therefore Lola holds consent rights over every proposal the session
cooperative produces that exceeds the domain of any existing agreement.
The session cooperative is a delegate circle of the project cooperative —
it has authority within its domain, and no authority beyond it. Tier A
and Tier B both exist to honour this boundary.

See `cooperative-topology.md` §2 on double-linking and §3 row "Autonomy
and independence" for the governing patterns.
