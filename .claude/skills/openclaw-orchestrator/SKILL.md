---
name: openclaw-orchestrator
description: >
  Runtime specification for the OpenClaw coordination layer — how the live Iskander
  agent system convenes cooperative members (Clerk, Steward, Librarian, Wellbeing,
  Sentry, ...) as S3 delegate circles around member drivers. This is a runtime
  spec, NOT a Claude Code orchestration loop (see sibling dev-orchestrator for that).
  Lean variant: points at existing decision-recorder schema + clerk tools rather
  than reinventing them. Triggers: "openclaw runtime design", "how should agents
  coordinate", "runtime orchestration layer", "agent routing spec", "Layer 2 design",
  "how does Clerk hand off to Steward".
version: 1.0.0
---

# OpenClaw Orchestrator — Runtime Coordination Layer

This skill is a **runtime specification** for the OpenClaw coordination layer — the thin
layer that sits above the existing S3 primitives and decides how a cooperative member's
message reaches the right agent, how ephemeral delegate circles form and dissolve, and
how paramount objections are enforced on live agent actions. It is **not** a Claude Code
build-side orchestration loop; the Claude Code orchestrator that builds Iskander during
development is described in `../dev-orchestrator/SKILL.md`. This spec governs what the
deployed runtime does when a member sends a message.

The lean-variant principle governs every addition: Iskander already has a substantial S3
implementation in production. The `Decision`, `Tension`, `LabourLog`, and `GlassBoxEntry`
schema, the full Clerk tool suite, and three live agents are all real and running. The
orchestrator's legitimate surface is the **coordination layer** between these primitives —
routing, ephemeral circle formation, lateral handoff, rounds facilitation, and runtime
paramount-objection enforcement. Any new field or tool must first fail the "does this
already exist?" check in `references/existing-s3-infrastructure.md`.

---

## When This Applies

Consult this skill when:

- Designing the runtime message router (which agent receives a member's message)
- Adding a new runtime agent (must describe dual-link membership and domain of authority)
- Building the rounds facilitation tool on the Clerk (`run_round`)
- Implementing paramount objection enforcement in the runtime dispatcher
- Designing the Layer 2 (life-activity) subsystem
- Building the `CircleMembership` schema (Phase B work)
- Scoping the multi-model MVT substrate (Commons feature, Phase B)

---

## What Already Exists (Do NOT Reinvent)

The S3 primitives are in production. The authoritative detail with verified file:line
references is in `references/existing-s3-infrastructure.md`. The table below gives the
highest-value items.

| Need | Already implemented | Location |
|---|---|---|
| S3 logbook (agreements + review dates) | `Decision` model | `services/decision-recorder/db.py:51-85` |
| Tensions (Navigate via Tension) | `Tension` model | `db.py:103-125` |
| DisCO labour log | `LabourLog` model | `db.py:128-157` |
| Glass Box audit trail | `GlassBoxEntry` model | `db.py:88-100` |
| Log a tension | `dr_log_tension` | `openclaw/agents/clerk/tools.py:382` |
| Set a review date | `dr_set_review_date` | `tools.py:431` |
| Log labour | `log_labour` | `tools.py:464` |
| Log Glass Box action | `glass_box_log` | `tools.py:49` |
| HITL consent | `loomio_create_discussion` / `loomio_create_proposal_draft` | `tools.py:238`, `tools.py:277` |

**Any runtime work that matches an S3 primitive MUST use the existing tool or schema.
Inventing parallel machinery is a phantom invariant in the making** — it duplicates state,
evades the Glass Box, and splits the accountability surface. See the reuse rule in
`references/existing-s3-infrastructure.md`.

---

## What Is Missing (The Coordination Gap)

The S3 primitives are there; the coordination layer is absent. The table below summarises
the 9 gaps. Full discussion of each is in `references/coordination-gaps.md`.

| Gap | Required | Phase | Notes |
|---|---|---|---|
| 1. Message routing | Intent classifier → agent selector → convene | MVP | No schema change; ephemeral per message |
| 2. Ephemeral delegate circles | Form around driver, dissolve on resolution | MVP | Driver lives in `Tension`; circle is runtime container |
| 3. Lateral handoff | Tension with `domain` routes to target agent as fresh driver | MVP | Reuses `Tension.domain` (`db.py:114`) |
| 4. Rounds facilitation | New Clerk tool: `run_round(driver, participants)` | MVP | Round correlated via `GlassBoxEntry` `round_id` |
| 5. Paramount objection enforcement | Runtime dispatcher checks before any write | MVP | Adds `Tension.paramount_objection bool` |
| 6. Double-linking schema | `CircleMembership` table linking agents to circles | Phase B | Implicit in Helm config for MVP |
| 7. Selection via consent | Runtime selection, not Helm config | Phase B | Layers on Gap 6 |
| 8. Layer 2 life-activity agents | `coop.type` specialist rosters, Self-scope-first | Phase B | Largest net-new subsystem; requires ADR |
| 9. Multi-model MVT substrate | `mvt_arm` + `exec_context` correlation on `LabourLog` | Phase B | Commons feature; model-agnostic substrate already exists |

---

## Two-Layer Runtime Architecture

**Layer 1 — Governance (universal).** Persistent agents on the cooperative's shared node.
Current: Clerk, Steward, Sentry (live SOUL.md files). Pending: Librarian (#51),
Wellbeing (#48). Future: DPO, Education Officer, Company Secretary, Electoral Officer,
Communications Officer, Ombudsperson. Persistent domain cooperatives; never dissolve.

**Layer 2 — Life-activity (domain-configured).** Ephemeral life-mirror agents assembled
on demand from a roster loaded via `coop.type` in Helm values or `member.activity_profile`.
**Self-scope first** — runs on the member's personal Iskander node when available;
cooperative compute is the fallback. A single member typically holds mirrors from several
rosters simultaneously because life has several facets at once. Example cooperative types:
`research`, `teachers`, `art`, `marketing`, `consultant`, `engagement`, `custom`.

**Commons property.** Because the runtime is model-agnostic (each node operator picks
their own stack), Layer 2 naturally accumulates MVT outcomes as a byproduct of real work.
Correlate via `mvt_arm` on `LabourLog` and `round_id` on `GlassBoxEntry`. Cross-stack
data flows upstream to the federation Commons. This is deliberate design, not afterthought.

---

## Runtime Flow (Spec)

```
on member_message(message, member_id):

  # Load context
  coop_config      = load_helm_values()          # includes coop.type, circle memberships
  member_profile   = load_activity_profile(member_id)

  # Classify intent
  intent           = classify_intent(message)    # governance | life-activity | cross-domain

  if intent == "governance":
    # Route to Layer 1
    agent          = select_layer1_agent(intent) # Clerk | Steward | Sentry | ...
    circle         = convene_delegate_circle(agent, driver=message)

    # Paramount objection check before any write
    objections     = check_paramount_objections(circle, driver)
    if objections:
      log_tension(domain=objections.role, paramount_objection=True)
      halt("Paramount objection raised — flow halted")

    # Glass Box before write (invariant #1)
    glass_box_log(actor=member_id, agent=agent, action="attend_driver", reasoning=intent)

    # Agent drafts; member signs (invariant #2)
    draft          = agent.attend(driver=message, circle=circle)
    surface_to_member(draft)

  elif intent == "life-activity":
    # Resolve execution node (Self-scope first)
    exec_node      = resolve_exec_node(member_id)  # personal node || cooperative compute

    # Assemble mirror team from coop.type roster
    mirror_team    = resolve_mirror_team(member_id, intent, coop_config)

    # Optional: MVT arms for Commons accumulation
    mvt_arm        = resolve_mvt_arm(coop_config)  # nullable; Commons feature

    # Coordinate and log labour
    glass_box_log(actor=member_id, agent=mirror_team, action="life_activity", reasoning=intent)
    result         = mirror_team.coordinate(driver=message, exec_node=exec_node)
    log_labour(member_id, value_type=classify_value_stream(intent),
               mvt_arm=mvt_arm, exec_context=exec_node)

    surface_to_member(result)

  elif intent == "cross-domain":
    # Lateral handoff (Gap 3): log tension against target domain
    tension_id = dr_log_tension(domain=resolve_target_domain(intent),
                                driver_statement=draft_driver_statement(message))
    notify_target_domain(tension_id)

  dissolve_circle(circle)  # dissolve ephemeral circle when driver resolved
```

---

## S3 Operating Model

The full operating model — session cooperatives, persistent domain cooperatives,
double-linking, the convening loop, paramount objection rights, rounds, and the
role/steward distinction — is described in
`../dev-orchestrator/references/cooperative-topology.md`. The runtime simply implements
that model with live agents and real member messages rather than development subagents
and GitHub issues. The paramount objection rights enumerated in topology §7 apply equally
at runtime: red-team holds a standing objection over security-affecting writes; review-desk
holds one over merges; governance-clerk holds one over changes that weaken S3 patterns.
The runtime dispatcher must honour these before any write proceeds.

---

## Invariants

All five invariants from `../dev-orchestrator/references/invariants-cheatsheet.md` apply
to runtime code with the same force as to build-side code. Two are most runtime-relevant:

- **Invariant #1 — Glass Box before every write.** The runtime dispatcher must call
  `glass_box_log` (`tools.py:49`) before every write action, regardless of which agent
  initiates it. This is currently prompt-enforced via `clerk/agent.py:39-47`; the
  orchestrator dispatcher is the candidate surface for hardening this to middleware.
  See #C6 audit item in `docs/red-team-threat-model.md`.

- **Invariant #2 — Agents draft, humans sign.** No runtime agent holds signing keys or
  auto-submits votes. `loomio_create_proposal_draft` (`tools.py:277`) intentionally
  returns draft text only; the member submits it in Loomio themselves. The runtime must
  not add an auto-submit path.

Phantom invariants currently tracked: **#147** (tombstone-only missing in
`decision-recorder`) and **#148** (manifest SHA-256 lock). Any runtime work touching
`decision-recorder/` or `governance_manifest.json` must cite these issues.

---

## Implementation Notes

- **New Clerk tools needed:** `run_round(driver, participants)` (Gap 4);
  `resolve_mirror_team(user_id, activity, coop_config)` (Gap 8);
  `dispatch_to_personal_node(user_id, task)` (Gap 8)
- **New schema fields (additive only):** `Tension.paramount_objection bool` (Gap 5);
  `LabourLog.mvt_arm string nullable` (Gap 9); `GlassBoxEntry.round_id string nullable` (Gap 4)
- **Deferred schema (Phase B):** `CircleMembership` table for double-linking (Gap 6)
- **Service-to-service auth:** reuse `_verify_internal_caller` pattern at
  `decision-recorder/main.py:886-898` (`hmac.compare_digest`). Do not invent a second
  auth scheme.
- **Integration points:** Mattermost (member messages), Loomio (HITL consent), decision-recorder (S3 logbook)
- **Model-agnostic design:** OpenClaw does not hardcode a model — node operators pick their
  stack. Deliberate Commons property enabling MVT. Do not add model-specific defaults.

---

## Related Skills

- `../dev-orchestrator/SKILL.md` — Claude Code build-side companion (builds the code described here)
- `../iskander-security-review/SKILL.md` — security patterns: Glass Box, `hmac.compare_digest`, `_ACTOR_TOOLS`
- `../doc-wave-dispatch/SKILL.md` — file coordination-gap work as issues

---

## First Implementation Drivers

In priority order for a team picking up this layer:

1. **Message router (Gap 1)** — smallest, highest-value; no schema change; classify intent
   and select Layer 1 agent using existing `Tension.domain` vocabulary
2. **Lateral handoff via `Tension.domain` (Gap 3)** — reuses `Tension` model (`db.py:114`)
   and `dr_log_tension` (`tools.py:382`); adds runtime subscription to `POST /tensions`
3. **`run_round` Clerk tool (Gap 4)** — new tool on the Clerk; correlates via
   `GlassBoxEntry` round_id; uses existing `glass_box_log` (`tools.py:49`)
4. **Ephemeral delegate circle tracking (Gap 2)** — runtime container keyed by tension_id;
   reuses `Tension` as the driver record; no new table
5. **Paramount objection enforcement (Gap 5)** — dispatcher check before writes; adds
   `Tension.paramount_objection bool`; hardens Glass Box from prompt to middleware (#C6)
6. **Gaps 6–9 deferred to Phase B** — double-linking, selection via consent, Layer 2
   agents, and MVT substrate require ADR before any code (phase-b-architecture paramount
   objection applies)
