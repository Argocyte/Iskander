# Coordination Gaps (what the openclaw-orchestrator must build)

## Purpose

This file is the **negative-space complement** to `existing-s3-infrastructure.md`. Everything listed there is already in production and must be reused. Everything listed **here** is what does NOT yet exist and is therefore the legitimate scope of the openclaw-orchestrator work.

The orchestrator is a **runtime** spec. It describes how Iskander should route messages between live agents, enforce paramount objections on agent actions, form ephemeral delegate circles, and coordinate multi-agent flows. It is not a build-side tool; it does not run in Claude Code.

When in doubt whether a gap below requires a new schema row or tool, **default to "no"** — most gaps are coordination layers over primitives that already exist. See the "No new schema needed" notes on each gap.

---

## Gap 1 — Message routing (intent classification)

**Current state:** each agent is addressed directly. A member either talks to the Clerk (governance questions) or the Steward (treasury questions) or the Sentry (infra questions). There is no runtime intent classifier.

**Needed:** intent classification → agent selection → convene. When a member sends a message, the orchestrator must classify the intent, pick the domain cooperative that holds the driver, and convene that domain's agent as the steward for this specific driver.

**Pattern to implement:** the convening loop described in `dev-orchestrator/references/cooperative-topology.md` §1–2 and §6. The orchestrator is **facilitator + secretary**, not a supervisor; authority stays with the members (the domain agents).

**No new schema needed.** Routing state is ephemeral and per-message.

---

## Gap 2 — Ephemeral delegate circles

**Current state:** every runtime agent is always-on. There is no concept of "a cooperative that forms around this driver and then dissolves".

**Needed:** the orchestrator must support forming a delegate circle per member activity (the "session cooperative" pattern from topology §2), convening the agents that are members, and dissolving the circle when the driver is resolved. This is the S3 "delegate circle" pattern (topology §3).

**No new schema needed** if the circle is represented as a transient record keyed by driver ID. The driver lives in `Tension`; the circle is a runtime container that references the tension and the participating agents.

---

## Gap 3 — Multi-agent lateral handoff

**Current state:** when red-team (or an equivalent role) notices a gap in the clerk domain, the handoff is manual — a human files a GitHub issue and the next Clerk steward picks it up on a later run. There is no runtime handoff.

**Needed:** when a tension is logged via `dr_log_tension` with a `domain` field set to another cooperative, the orchestrator must route that tension to the target domain's agent as a fresh driver. This is **lateral** (S3 autonomy, not delegation): the target domain accepts the driver on its own terms.

**No new schema needed.** `Tension.domain` already exists (`db.py:114`). The orchestrator just needs to watch the tensions table (or subscribe to `POST /tensions`) and route accordingly.

---

## Gap 4 — Rounds facilitation

**Current state:** no tool for "run a structured check-in round across N agents". Cross-agent decisions happen by whoever-speaks-first rather than by S3 rounds.

**Needed:** a new Clerk tool, e.g. `clerk.run_round(participants, driver)`, that:
1. Takes a list of agent participants and a driver (tension id).
2. Sequentially asks each participant for their position.
3. Records each position as a `GlassBoxEntry` with a shared `round_id` for correlation.
4. Returns the collected positions for integration by the facilitator.

**Schema delta:** no new table. Add a round correlation id to `GlassBoxEntry` reasoning text (or as a structured field if a tiny migration is acceptable). The round is an ephemeral orchestration; the evidence of it is the correlated Glass Box rows.

---

## Gap 5 — Paramount objection enforcement at runtime

**Current state:** red-team's standing paramount objection over security-affecting changes (topology §7) is **human-enforced** via PR reviews. The runtime has no concept of a paramount objection that halts an agent action flow.

**Needed:** when a flow touches code or config in a domain where another role holds a standing objection, the runtime must verify that role has no open paramount objection on the driver. If one exists, the flow halts and a tension is raised against the proposing role.

**Schema delta:** one new boolean field, e.g. `Tension.paramount_objection bool` (default false). The orchestrator's action dispatcher checks for open paramount-objection tensions on the driver before allowing the write.

This is also the lever for hardening Glass Box enforcement from prompt-based to middleware (the #C6 audit item in `docs/red-team-threat-model.md` §3): the same dispatcher that checks for paramount objections can enforce Glass Box as a precondition.

---

## Gap 6 — Double-linking representation

**Current state:** no schema for "this agent is a member of both circle X and circle Y". Topology §2 describes the double-linking pattern as structural but it has no persistent representation.

**Needed:** a `CircleMembership` table linking agents (or members) to circles with role attribution. This is **Phase B work**; not MVP-critical. For MVP, double-linking is implicit in the agent configuration (Helm config).

**Flag as constraint:** name this gap in the orchestrator design but do not block MVP on it.

---

## Gap 7 — Selection via consent

**Current state:** membership of circles is set by Helm config, not selected at runtime by the affected members. Topology §3 lists "Selection via consent" as an S3 pattern but the runtime does not implement it.

**Acceptable for MVP.** The orchestrator should flag this as a Phase B improvement — once circles are first-class (Gap 6), selection via consent can layer on top.

---

## Gap 8 — Layer 2 life-activity agents

**Current state:** Layer 1 governance agents (Clerk, Steward, Sentry) exist. Layer 2 specialist rosters — life-activity agents keyed by a `coop.type` (housing, food, credit union, energy, health, etc.) — **do not exist yet**. This is a net-new subsystem.

**Needed:** a two-layer architecture in which:
- **Layer 1 (Governance agents)** run on the cooperative's shared Iskander node and hold persistent domain cooperatives (the existing pattern).
- **Layer 2 (Life-activity agents)** run **Self-scope-first** on a member's personal Iskander node (per the plan's lunarpunk architecture: `reference_lunarpunk_architecture`). They are specialists in a life-activity domain and are selected into a life-activity delegate circle on demand.

**Design source:** the plan file's openclaw-orchestrator section; and the Self/Cooperative/Community/Federation/Commons scope model in `reference_icn_architecture`.

**This is the largest net-new piece of the orchestrator work.** It should be scoped, ADR'd by the phase-b-architecture role, and staged — not built in one sweep.

---

## Gap 9 — Multi-model MVT substrate

**Current state:** OpenClaw runtime is model-agnostic at install time (each node operator picks their own stack), but there is no runtime ability to dispatch the same driver to multiple mirror teams with different `exec_context` (model, prompt, team) and correlate the results.

**Needed:** expose multi-model MVT (Minimum Viable Team) as a **Commons feature** of the orchestrator. Same driver, multiple parallel executions, correlated via a `mvt_arm` field on `LabourLog` (so labour attribution is preserved per arm) and/or a round_id on `GlassBoxEntry` (so audit correlation is preserved).

**Schema delta:** one optional field `LabourLog.mvt_arm` (string, nullable). Low-risk additive migration.

**Source:** the plan file's MVT section. This is a Commons-scope feature — the correlation data, once produced, flows upstream to the federation Commons so other cooperatives benefit from cross-stack experience reports.

---

## Summary of schema deltas required (if any)

Most gaps are pure coordination layers with no schema change. The minimal set of additive fields:

| Gap | Field | Table | Type |
|---|---|---|---|
| 4 | `round_id` (optional) | `GlassBoxEntry` | string, nullable |
| 5 | `paramount_objection` | `Tension` | bool, default false |
| 9 | `mvt_arm` (optional) | `LabourLog` | string, nullable |

Gaps 1, 2, 3, 6, 7, 8 require no schema change at the decision-recorder layer — they are either pure routing (1–3), explicitly Phase B (6–7), or a net-new subsystem with its own schema surface (8).

Before introducing any additional field, verify against `existing-s3-infrastructure.md` that the primitive is not already present under a different name. The reuse rule applies to this file too.
