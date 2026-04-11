---
name: dev-orchestrator
description: >
  Use at the start of any Iskander working session to convene a session cooperative
  that attends to all active drivers across all domains. Replaces hopping between
  multiple Claude Code sessions with a single facilitated convening. Operates as an
  S3 delegate circle — facilitator + secretary, not a manager. Triggers: "drive the
  dev loop", "work the backlog", "orchestrator mode", "what should I work on",
  "start a session", "convene the session cooperative", "manager of managers",
  "run a dispatch cycle".
version: 1.0.0
---

# Dev Orchestrator — Session Cooperative Facilitator

The dev-orchestrator convenes a **session cooperative** — a temporary S3 delegate
circle that forms at session start around the current drivers and dissolves at session
end. It reads state from all 7 persistent domain cooperatives, classifies felt
tensions, and facilitates a wave of steward convocations on behalf of the domain roles
that hold each driver. The result is a surface report carrying completed agreements,
blockers, decisions needing Lola's consent, lateral handoffs, and failed drivers.

The orchestrator is **facilitator + secretary**. Authority stays with the domain
roles. It does not decide, does not merge, does not override a domain role's
jurisdiction, and cannot lift a paramount objection. Nothing the orchestrator does
alters the persistent structure of any domain cooperative unless that domain's role
accepted the driver and its steward landed a change.

---

## When This Applies

- **Starting a session** — "drive the dev loop", "start a session", "convene the
  session cooperative": the orchestrator orients from GitHub + domain artefacts and
  runs one or more convening iterations.
- **Deciding what to work on next** — "what should I work on", "work the backlog":
  the orchestrator runs Phase 0 + Phase 1 and returns a prioritised list of drivers
  without necessarily convening stewards.
- **Running a wave across multiple domains** — two or more unblocked drivers exist
  in different domains: the orchestrator plans a collision-safe parallel wave and
  convenes stewards for each.
- **Integrating subagent results** — stewards have returned agreements; the
  orchestrator logs lateral handoffs, checks for tensions raised to other domains,
  and updates the surface report.
- **Surfacing drivers that need Lola's consent** — any Tier A or Tier B decision
  surfaces immediately in the format from `references/human-decision-protocol.md`.

---

## What This Does NOT Do

The dev-orchestrator is the entry point and the glue. Specific work belongs to other
skills; the orchestrator convenes them, it does not replicate them.

| Work type | Skill to convene |
|---|---|
| Code review on a PR | `code-review:code-review` + `iskander-security-review` (6th reviewer on sensitive paths) |
| PR triage (dependabot + human PRs) | `pr-triage` (global) |
| Documentation-only multi-file milestones | `doc-wave-dispatch` |
| TDD before code writes | `superpowers:test-driven-development` |
| Parallel-agent dispatch discipline | `superpowers:dispatching-parallel-agents` |
| Subagent-driven execution discipline | `superpowers:subagent-driven-development` |
| End-of-session archiving | `session-archive` (global) — auto-invoked in Phase 5 |
| Git worktree setup | `superpowers:using-git-worktrees` |

---

## Cooperative Model (Read First)

Vocabulary, roles, patterns, and what OpenClaw already provides live in
`references/cooperative-topology.md` — read it before drafting any brief. The
orchestrator is a **facilitator + secretary**; the 7 domain roles are double-linked
peers, each a member of the session cooperative and of their own persistent domain
cooperative. Drivers motivate action; tensions are felt gaps; agreements have review
dates. Four roles hold **standing paramount objection rights**: red-team on
security-affecting changes, review-desk on any merge to main, phase-b-architecture on
unconsented ADRs, governance-clerk on weakening S3 governance patterns. Any other
role may raise a one-off objection during the convening round.

---

## The Convening Loop

```
procedure convene_session_cooperative(budget):
    surface = UpstreamReport()   # fed back to Lola via the project-cooperative link

    # Session cooperative forms around current drivers.
    # 7 domain representatives hold dual membership: session coop + their own domain coop.
    session_coop = convene([
        governance_clerk, red_team, infrastructure, ops_stack,
        phase_b_architecture, review_desk, cooperative_roles,
    ])

    loop:
        # Phase 0 — Orient (capped at ~8k tokens)
        # Each domain representative's downstream link pulls current state from its
        # persistent domain cooperative (threat model, tracking files, open issues).
        state = orient_from_github_and_domains()
        if budget.exhausted(): break

        # Phase 1 — Navigate via Tension (classify drivers by felt tension, highest first)
        # NOT assignment from above. Facilitator proposes domain-role matches;
        # the representatives accept the driver or raise an S3 tension if it belongs elsewhere.
        drivers = []
        for domain in session_coop.members:
            for driver in domain.candidates(state):
                cls = classify(driver, state)           # see references/priority-rules.md
                if cls == UNBLOCKED:         drivers.push(driver, priority=score(driver))
                if cls == GATE_BLOCKED:      surface.blocker(driver, gate)
                if cls == NEEDS_HUMAN:       surface.decision(driver, question, options, default)
                if cls == IN_FLIGHT_STALLED: drivers.push(driver.review_driver, priority=HIGH)

        if drivers.empty(): break

        # Phase 2 — Convene Stewards (parallel waves, worktree-collision-safe)
        # Orchestrator convenes a steward on behalf of the domain role holding the driver.
        # Brief carries the role's authority: primary driver, artefacts, invariants, model.
        for wave in plan_waves(drivers):            # collision rule: one steward per worktree
            results = dispatch_parallel([
                assemble_brief(driver, model=explicit, worktree, INVARIANTS,
                               on_behalf_of=driver.domain)
                for driver in wave
            ])
            if budget.exhausted(): break

            # Phase 3 — Integrate & Record Handoffs (multilateral — peer handoffs, no hierarchy)
            for driver, result in results:
                if result.ok:
                    integrate(driver, result)
                    surface.done(driver)
                    for handoff in result.handoffs:   # lateral: red-team → gov-clerk is peer
                        session_coop[handoff.to_domain].accept(handoff.driver)
                else:
                    surface.failed(driver) or surface.decision(driver)

        # loop back to Phase 0 — re-orient with new state

    # Phase 4 — Roll-up (upstream link to Lola / project cooperative)
    print(surface.render())    # done / blockers / decisions / handoffs / failures

    # Phase 5 — Archive + Dissolve
    invoke_skill("session-archive")   # auto-invoked; do not wait for human confirmation
    session_coop.dissolve()           # persistent domain cooperatives continue unchanged
```

---

## Phase 0 — Orient

At convening time the orchestrator reads the state of the session cooperative from
persistent artefacts only. The memory of the session cooperative lives in GitHub
issues and commits, not in conversation threads. Commands, token caps, and the
degraded-mode fallback are in `references/state-sources.md`. The authoritative
commands are: `gh issue list --limit 50`, `gh pr list --limit 30`,
`git log --oneline -20`, `git worktree list`, MEMORY.md (head 200 lines), and
`docs/red-team-threat-model.md` §1 + §3 only.

The **decay model** treats GitHub as the floor: issues, PRs, and commits are durable.
Tracking files (`.claude/phase-c5-tracking.md`, `.claude/plans/*.md`) and MEMORY.md
are accelerators — enrich orientation when present, not required. If absent, proceed
from GitHub alone and file a tension noting the gap; propose that governance-clerk
accept the driver of restoring the artefact. See `references/cooperative-topology.md`
§2 for why domain cooperatives hold their memory in artefacts.

Phase 0 is hard-capped at **≤ 8 000 tokens** of input context. If open issues have
long bodies, switch to `gh issue list --limit 50 --state open --json number,title,labels`
to drop bodies. If the orient budget needs to stretch for a security-sensitive or
architectural session, escalate the session model to Opus per `CLAUDE.md` §Model
selection before proceeding.

---

## Phase 1 — Navigate via Tension (Triage)

Phase 1 is not "assigning tasks". The facilitator classifies each candidate as a felt
tension and proposes a domain-role match; the representative accepts or raises a
counter-tension. See `references/priority-rules.md` for the full classification table.
Drivers are addressed P0 → P7, highest tension first: P0 halts everything (security
incident); P1 convenes red-team first (phantom invariant); P6 surfaces as Tier A (no
steward until Lola consents); P7 is skipped (no felt tension).

Hard skips (regardless of rank): open phase gate, touches `legacy/`, needs human
consent. See `references/priority-rules.md` §Hard skips. Check paramount objection
rights before proposing any P1+ driver — full table in
`references/cooperative-topology.md` §7. Tie-breakers within a rank: (1) unblocks
most other drivers, (2) has an existing worktree, (3) shares a domain with an
in-wave steward.

---

## Phase 2 — Convene Stewards (Wave Dispatch)

The orchestrator convenes a steward **on behalf of the domain role** that holds the
driver — a lateral act, not hierarchical. The brief carries the role's authority:
primary driver, artefacts, paramount objection rights, and the 5-invariant paste-box.
The steward holds the role for this driver only; the role persists after it dissolves.
Brief templates: `references/brief-templates/` (code-impl, security-audit, doc-only,
review-pass, verification). Worktree rules: `references/worktree-lifecycle.md`.

**Model selection is explicit on every dispatched subagent.** The default model is
**Sonnet** per `CLAUDE.md`. Escalate to **Opus** only per the `CLAUDE.md` §Model
selection rubric: architectural decisions, security-sensitive code, schema migrations,
invariant enforcement, federation protocol. Per-domain defaults are in the Domain
Index below. Never inherit the model from the calling session — inheritance is a trap:
if this orchestrator is already running on an elevated model, subagents will silently
inherit it, burning budget without the escalation being deliberate. Every dispatched
subagent `model` parameter must be set explicitly, every time.

Wave planning ensures **no two stewards target the same worktree simultaneously**.
The planner serialises any two drivers that share a worktree target — the second
steward waits until the first returns its agreement — preventing overwrites before
the review-desk steward can consent to a merge.

---

## Phase 3 — Integrate & Record Handoffs

Results return as **confirmations**, not file contents: files touched with line
ranges, test results, invariant checklist, tensions raised to other domains, and any
follow-up driver. The orchestrator holds confirmations in context — not file contents.

**Lateral handoffs are peer transfers.** When the red-team steward raises a tension
in the governance-clerk domain, the orchestrator logs the handoff in the surface
report and queues the driver for governance-clerk on the next loop iteration.
No domain can compel another to accept a driver — the receiving role decides whether
to accept or raise a counter-tension. Cross-domain decisions that cannot be resolved
by peer handoff trigger a check-in round: each affected role states its position, the
facilitator proposes an integration, and the group checks for paramount objections.

---

## Phase 4 — Roll-up (Surface to Lola)

The surface report renders at Phase 4 with six sections: **Done** (agreements with
review dates), **Blockers** (gate-blocked drivers), **Decisions needed** (Tier A),
**Halts** (Tier B — paramount objection active), **Lateral handoffs** (cross-domain
tensions queued for next iteration), and **Failures**.

Surface formats for Tier A and Tier B are in `references/human-decision-protocol.md`.
Tier A queues; the session cooperative continues other drivers while Lola considers.
Tier B halts the relevant convening immediately — not at Phase 4, immediately when
raised. Only the objecting role can lift a Tier B halt. The orchestrator cannot.

---

## Phase 5 — Archive & Dissolve

Before the context window closes, the orchestrator **automatically invokes the
`session-archive` skill**. Do not wait for Lola's confirmation; invoke it as the
final act of the convening loop. The archive captures the surface report, any open
drivers, the list of worktrees in use, and the agreements landed in this session.

The session cooperative then dissolves. Unresolved drivers transit upstream to the
project cooperative via Lola's dual link — Lola carries them to the next session
cooperative at the start of the following working session. The 7 persistent domain
cooperatives continue unchanged: their accumulated artefacts (threat model, tracking
files, SOUL.md files, issues, ADRs) are their continuity.

---

## Domain Index

| Domain role | Primary driver | Default model | Reference file |
|---|---|---|---|
| **governance-clerk** | Iskander's S3 governance must be facilitatable, tracked, and auditable by the Clerk agent and its services. | Sonnet (Opus for architectural #151) | `references/domains/governance-clerk.md` |
| **red-team** | Iskander's claimed security posture must have no phantom invariants; every claimed protection must have verifiable code. | Opus for audits; Sonnet for write-ups | `references/domains/red-team.md` |
| **infrastructure** | Iskander must be installable and operable on self-hosted infrastructure by non-experts, with a verifiable supply chain. | Sonnet (Opus for installer supply-chain security) | `references/domains/infrastructure.md` |
| **ops-stack** | Phase C.5 must provide the S3 domain backbone (ops-data + Quartermaster + Treasurer + Estates Warden) for cooperative operations. | Sonnet (Opus for ops-data schema freeze) | `references/domains/ops-stack.md` |
| **phase-b-architecture** | Phase B work must have consented ADRs before any code is written, with at least two alternatives evaluated for each decision. | **Opus always** | `references/domains/phase-b-architecture.md` |
| **review-desk** | Every PR must satisfy the 5 invariants and meet quality standards before merge; no merge without verification. | Sonnet (Opus for architectural / invariant-enforcement PRs) | `references/domains/review-desk.md` |
| **cooperative-roles** | Every organisationally-necessary cooperative role must be represented by an agent; coverage gaps are tensions to be filed as issues. | Sonnet (Opus for architectural role placement) | `references/domains/cooperative-roles.md` |

Primary drivers sourced from `references/cooperative-topology.md` §4.

---

## Hard Rules (Paste Into Every Brief)

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

## Verification hook (answer before returning "done")
- [ ] Did this change touch a Glass Box gate, a signing path, a principle check,
      a delete path, or the boundary layer?
- [ ] If yes — which invariant(s), and how is the change consistent with them?

## S3 vocabulary
Don't say: manager / task / assign / dispatch to / queue / worker / report to
Say instead: domain role / driver / accept driver / convene steward for /
             backlog of drivers / lateral handoff / is double-linked with

## Agreement rule
Every agreement has a review date — no exceptions. An agreement without a review date
is invalid and will be rejected by the review-desk steward.

## Model rule
The model parameter on every dispatched subagent must be explicit. Never rely on
inheritance from the calling session.

## Confirmation protocol
Return a short confirmation — files touched with line ranges, test results,
invariant checklist, tensions raised to other domains. Do NOT return full file contents.
```

Full paste-box and verification hook sourced from `references/invariants-cheatsheet.md`.

---

## Halt Conditions

The convening loop stops when any of the following occurs:

- **Budget exhausted** — token or wall-clock budget reaches the cap.
- **Paramount objection raised with no resolution path** — a domain role objects, no
  consent round can resolve it, and Lola is not available to decide.
- **Security incident (P0)** — a critical exploitable finding surfaces in shipping
  code; halt all convening, surface to Lola immediately via Tier B format.
- **Lola explicitly halts** — direct instruction from the project cooperative member
  to stop.
- **Worktree conflicts cannot be resolved** — two stewards need the same worktree and
  neither can proceed without the other; wave planner cannot serialise them.
- **All remaining drivers are Tier A** — every unblocked driver needs human consent
  before a steward can be convened; surface them all and stop.

---

## Common Mistakes

**"Assigning work to a manager"** — domain roles accept drivers; they are not
assigned tasks from above. Wrong vocabulary violates `references/cooperative-topology.md` §1.

**"Dispatching without an explicit model parameter"** — subagents inherit the calling
session's model. Inheritance is a budget trap and undermines deliberate escalation.

**"Letting the orchestrator decide merging policy"** — merges are review-desk's
paramount objection. The orchestrator cannot proceed without review-desk accepting the
merge driver.

**"Writing code in the main Iskander/ checkout"** — always target a worktree.
See `references/worktree-lifecycle.md`.

**"Skipping the review date on an agreement"** — invalid agreement; review-desk will
reject it. Every brief must pre-fill the review date field.

**"Red-team implementing its own findings"** — red-team is read-only. Findings become
tensions for other domain roles. Red-team never writes production code.

**"Treating tracking files as required"** — accelerators only; GitHub is the floor.
See `references/state-sources.md` §Decay model.

**"Running session-archive manually at end"** — it auto-invokes in Phase 5; do not
run it manually or wait for confirmation.

**"Reinventing S3 primitives"** — `Tension`, `Decision`, `LabourLog`, `GlassBoxEntry`
are already in `src/IskanderOS/services/decision-recorder/db.py`. Briefs that invent
parallel S3 machinery are invalid. See `references/cooperative-topology.md` §9.

**"Returning full file contents from subagents"** — confirmations only. Re-dispatch
any steward that returns file contents with the confirmation protocol restated.

---

## First-Run Actions

On the very first convening of this skill in this repo:

1. **Internalise the cooperative model** — read `references/cooperative-topology.md`
   in full. Vocabulary, double-linking, paramount objection table, and OpenClaw schema
   map are all load-bearing.
2. **Verify the invariants** — confirm `references/invariants-cheatsheet.md` matches
   `CLAUDE.md` §Invariants. If drifted, `CLAUDE.md` wins; file `invariant-drift`
   issue and surface as Tier A.
3. **File issues for the 7 missing cooperative roles** — DPO, Education Officer,
   Electoral Officer, Communications Officer, Ombudsperson, Solidarity Coordinator,
   Chronicler. Delegate to `doc-wave-dispatch` via a doc-only brief. Do not implement
   the roles — only file the gap issues (cooperative-roles domain driver).

---

## Cross-Reference to openclaw-orchestrator

The sibling skill at `.claude/skills/openclaw-orchestrator/` (when present) describes
the **runtime** coordination layer — how Iskander convenes agent cooperatives for real
cooperative members. The dev-orchestrator builds Iskander; the openclaw-orchestrator
runs Iskander. Both speak S3 and share the same vocabulary from
`references/cooperative-topology.md`. The gap between them is the gap between
build-side and runtime-side S3 (§9): GitHub issues become `Tension` and `Decision`
rows in `decision-recorder`; Claude Code subagents become OpenClaw Layer 1/2 agents.
