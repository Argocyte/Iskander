# Priority Rules (Tension Classification)

**Purpose:** during Phase 1 "Navigate via Tension", the facilitator proposes
driver-to-domain matches. This file is the tension classification table used
to rank drivers by felt tension, highest first, per S3 Navigate Via Tension.

This is **not** a priority ranking of work items. It is a way for the
facilitator to recognise which tensions in the cooperative are most painful
so they get convened first. See `cooperative-topology.md` §3 (Patterns
Applied, row "Navigate via tension") for the governing pattern.

---

## Classification table

| Rank | Tension class | Convening action |
|---|---|---|
| **P0** | Security incident — critical, exploitable in shipping code | **Halt convening**; surface directly to Lola via Tier B (see `human-decision-protocol.md`) |
| **P1** | Phantom invariant in shipping code — confirmed, code path exists (e.g. #147, #148) | Convene **red-team** steward first. Red-team holds a standing paramount objection on this domain — no other steward accepts drivers that touch the affected area until red-team clears |
| **P2** | In-flight PR with open review findings (#96/#101/#102 pattern) | Convene the originating domain's steward to accept the driver of resolving the findings |
| **P3** | Gate-blocking driver — blocks ≥ 2 downstream domains (#127/#131 pattern) | Convene **phase-b-architecture** steward; this unblocks the most felt tension in the cooperative |
| **P4** | Audit queue top item per `docs/red-team-threat-model.md` §3 | Convene **red-team** steward. Escalate session model to **Opus** per `CLAUDE.md` §Model selection |
| **P5** | Unblocked feature driver, labelled `ready` | Convene the originating domain's steward |
| **P6** | Driver needs human consent first — ambiguous spec, scope question, equivalent alternatives | Do **not** convene a steward. Surface as a Tier A decision per `human-decision-protocol.md` |
| **P7** | No felt tension — backlog polish, nice-to-have | Skip this convening cycle. The session cooperative does not form around drivers with no tension |

Drivers are addressed in rank order (P0 → P7). Within a rank, use the
tie-breakers below.

---

## Tie-breakers (within a rank)

1. **Unblocks most other drivers.** Pick the driver whose resolution frees the
   largest number of other tensions in the backlog.
2. **Has an existing worktree.** Re-using a worktree is cheaper than creating
   one. See `worktree-lifecycle.md`.
3. **Same domain already has a steward in this wave.** Grouping two drivers
   under one domain's steward is cheaper than convening a new steward.

---

## Hard skips (never convene, regardless of rank)

- **Gate open** — a phase gate on the driver is not yet consented. Skip and
  leave the tension in the backlog.
- **Touches `legacy/`** — no new work in the legacy monolith per `CLAUDE.md`
  §Legacy codebase. Skip and file a tension proposing an extraction driver.
- **Needs human consent first** — surface as a Tier A decision per
  `human-decision-protocol.md` rather than convening.

---

## Paramount objection rights

Several domain roles hold **standing** paramount objections that override
rank-based convening. Red-team can halt any P2/P3 driver that introduces a
phantom invariant; review-desk can halt any merge. For the full table see
`cooperative-topology.md` §7. The facilitator must check these before
proposing a steward for any driver ranked P1 or higher.

---

## Agreements have review dates

Every driver that is accepted and resolved becomes an **agreement** in the
S3 sense. Every agreement has a **review date** — no exceptions. The brief
the facilitator writes for the steward MUST specify the review date the
resulting agreement should carry. An agreement without a review date is
invalid and will be rejected by the review-desk steward.

See `cooperative-topology.md` §3 row "Agreement" and §8 "What this reframe
changes in practice".
