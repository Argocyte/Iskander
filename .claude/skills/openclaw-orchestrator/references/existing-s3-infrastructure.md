# Existing S3 Infrastructure (do not reinvent)

## Purpose

This file is the **"do not reinvent" manifest** for anyone building the openclaw-orchestrator runtime layer. Iskander already has a substantial S3 implementation in production: the schema, the tools, and three live agents. The orchestrator's job is to **coordinate between them**, not to re-describe the primitives.

Before introducing any new schema table, tool, or governance concept in the orchestrator, check this file. If a primitive is already here, reuse it — inventing a parallel one is a phantom invariant in the making (see `docs/red-team-threat-model.md` §1).

This file **extends** `dev-orchestrator/references/cooperative-topology.md` §9 with line-verified detail drawn from reading the source.

---

## S3 schema reference — `src/IskanderOS/services/decision-recorder/db.py`

Verified 2026-04-11 against the file on disk.

| S3 concept | Model / fields | Location |
|---|---|---|
| Agreement with review date | `Decision.review_date`, `review_circle`, `review_status` (pending/due/complete) | `db.py:68-72` |
| Accountability tracking | `Decision.accountability_status` (not_applicable/not_started/in_progress/implemented/not_implemented/deferred), `accountability_notes`, `accountability_updated_at`, `accountability_review_date` | `db.py:73-81` |
| Decision core | `Decision` — `loomio_poll_id`, `loomio_group_key`, `title`, `outcome`, `status` (passed/blocked/abstained), `stance_counts`, `ipfs_cid`, `decided_at`, `recorded_at` | `db.py:51-85` |
| Glass Box audit trail | `GlassBoxEntry` — `actor` (Mattermost user id), `agent` (e.g. "clerk"), `action`, `target`, `reasoning`, `timestamp` | `db.py:88-100` |
| Tension (Navigate Via Tension) | `Tension` — `logged_by`, `description`, `domain`, `driver_statement`, `status` (open/in_progress/resolved), `loomio_discussion_id`, `logged_at`, `resolved_at` | `db.py:103-125` |
| DisCO four-stream labour | `LabourLog` — `member_id`, `value_type` ∈ {productive, reproductive, care, commons}, `task_category`, `task_description`, `hours`, `timestamp_start`, `timestamp_end`, `loomio_discussion_id` | `db.py:128-157` |

**Fields beyond topology §9:** the table above adds `Decision.accountability_notes`/`accountability_updated_at`, `Tension.loomio_discussion_id`, and the full `LabourLog.timestamp_start`/`timestamp_end` pair. Topology §9 is otherwise accurate.

---

## S3 operating tools — `src/IskanderOS/openclaw/agents/clerk/tools.py`

Verified 2026-04-11 against the file on disk.

| S3 operation | Tool | Location | Short description |
|---|---|---|---|
| Glass Box write | `glass_box_log` | `tools.py:49` | POST to `/log`; MUST be called before any write tool. |
| Provision a member | `provision_member` | `tools.py:79` | Creates account across Authentik, Loomio, Mattermost via provisioner service. |
| Draft a driver statement | `draft_driver_statement` | `tools.py:360` | Formats the four-part S3 driver sentence; no API call. |
| Log a tension | `dr_log_tension` | `tools.py:382` | POST `/tensions`; writes a `Tension` row. |
| Update a tension | `dr_update_tension` | `tools.py:405` | PATCH `/tensions/{id}`; status, driver_statement, loomio_discussion_id. Only original logger may update. |
| Set a review date | `dr_set_review_date` | `tools.py:431` | PATCH `/decisions/{id}/review`; rejects past dates (#65). |
| List tensions (paginated) | `dr_list_tensions` | `tools.py:343` | GET `/tensions` with status/domain filters. |
| List tensions (simple) | `list_tensions` | `tools.py:600` | GET `/tensions` for meeting-prep, returns the `tensions` array. |
| List due reviews (paginated) | `dr_list_due_reviews` | `tools.py:332` | GET `/decisions/reviews/due?days_ahead=N`. |
| List due reviews (simple) | `list_due_reviews` | `tools.py:588` | GET `/decisions/reviews/due` for meeting-prep. |
| Log labour (DisCO) | `log_labour` | `tools.py:464` | POST `/labour`; value_type ∈ {productive, reproductive, care, commons}. |
| Summarise labour | `get_labour_summary` | `tools.py:505` | GET `/labour/summary`; returns totals and care_ratio. Read-only. |
| Update accountability | `dr_update_accountability` | `tools.py:520` | PATCH `/decisions/{id}/accountability`; enforces valid status + future review_date. |
| Recent decisions | `list_recent_decisions` | `tools.py:573` | GET `/decisions?limit=N` — for meeting agendas and surfacing history. |
| Meeting agenda (computed) | `prepare_meeting_agenda` | `tools.py:611` | Aggregates due reviews, open tensions, recent decisions into markdown. |
| HITL consent — discussion | `loomio_create_discussion` | `tools.py:238` | Creates a Loomio discussion; verifies actor group membership first. |
| HITL consent — proposal draft | `loomio_create_proposal_draft` | `tools.py:277` | Returns formatted draft text only. Clerk NEVER submits proposals or votes. |
| Loomio reads | `loomio_list_proposals`, `loomio_get_proposal`, `loomio_list_discussions`, `loomio_get_discussion`, `loomio_search` | `tools.py:129-203` | No Glass Box required. |
| Mattermost post | `mattermost_post_message` | `tools.py:317` | POST to `/api/v4/posts`; enforces 16k char cap. |

**Glass Box sequencing is prompt-based, not middleware.** Every write tool docstring carries `"Glass Box MUST be called before this function."` The enforcement lives in the Clerk's system prompt (`agent.py:39-47`), not in a dispatch guard. This is the #C6 audit item in `docs/red-team-threat-model.md` §3.

---

## Existing agents with live SOUL.md files

Confirmed on disk 2026-04-11:

- **Clerk** — `src/IskanderOS/openclaw/agents/clerk/SOUL.md` — cooperative governance facilitator/secretary. Holds the persistent governance-clerk domain cooperative. Specialist in S3 governance, Loomio, Mattermost, decision recording. Partisan for ICA principles; drafts proposals but never submits votes.
- **Steward** — `src/IskanderOS/openclaw/agents/steward/SOUL.md` — treasury transparency agent. Holds the persistent ops/treasury domain cooperative. Partisan for ICA Principle 3 (Member Economic Participation). Makes finances legible; does not move money or authorise transactions.
- **Sentry** — `src/IskanderOS/openclaw/agents/sentry/SOUL.md` — infrastructure health observer. Holds the persistent infrastructure-health domain cooperative. Partisan for ICA Principle 4 (Autonomy & Independence). Watches self-hosted infra; alerts but does not fix.

Additional runtime agents referenced elsewhere (may have separate docs pending): Librarian (#51), Wellbeing (#48).

---

## Glass Box enforcement status

From `docs/red-team-threat-model.md` §1 (invariant #1 row):

> **Status:** 🟢 Enforced (prompt-based). `clerk/agent.py:39-47` does system-prompt sequencing; `decision-recorder/main.py:44-78` has the rate-limited `/log` endpoint. **Caveat:** enforcement is prompt-based for Clerk, not middleware. This is the #C6 audit item and is tracked as a pending hardening target.

**Consequence for the orchestrator:** runtime orchestration of multi-agent flows must not bypass the Clerk's system-prompt sequencing. Any runtime "action dispatcher" the orchestrator adds must keep Glass Box as a precondition for writes, and should be a candidate surface for turning prompt-based enforcement into middleware enforcement (one of the few cases where the orchestrator could strengthen an existing invariant rather than reuse it).

---

## Loomio as HITL consent substrate

The `loomio_create_discussion` (`tools.py:238`) and `loomio_create_proposal_draft` (`tools.py:277`) tools are **the Human-in-the-Loop consent mechanism at runtime**. Any brief the orchestrator routes that needs member consent — a cross-circle decision, a resource allocation, a constitutional change — MUST route through these tools. The orchestrator does not invent a parallel consent flow.

Note that `loomio_create_proposal_draft` is intentionally a format-only function: it returns draft text that a human must submit themselves in Loomio. This is the "agents draft, humans sign" invariant (#2 in the threat model) at the governance layer.

---

## DisCO four-stream labour

`LabourLog.value_type` must be exactly one of `{productive, reproductive, care, commons}` (`db.py:142`, enforced in topology §9 and in `log_labour` docstring at `tools.py:464-483`).

**Consequence for the orchestrator:** any runtime work the orchestrator coordinates must log to `LabourLog` with the correct `value_type`. Governance facilitation is `care` or `reproductive`, not `productive`. Running a round across agents is `care`. Generating an agenda is `reproductive`. Writing code for a driver is `productive`. Maintaining the orchestrator's own infrastructure is `commons`. Do not invent a new enumeration; the four values are load-bearing for DisCO compliance (#91).

---

## Decision-recorder as the S3 logbook

The S3 primitives above are exposed over HTTP by `src/IskanderOS/services/decision-recorder/main.py`:

- `POST /log` / `GET /log` — Glass Box entries (`main.py:219`, `main.py:253`)
- `GET /decisions`, `GET /decisions/{id}` — decision history (`main.py:302`, `main.py:327`)
- `PATCH /decisions/{id}/review`, `GET /decisions/reviews/due` — review cycle (`main.py:367`, `main.py:387`)
- `PATCH /decisions/{id}/accountability`, `GET /decisions/accountability/overdue` — implementation follow-up (`main.py:475`, `main.py:517`)
- `POST /tensions`, `GET /tensions`, `PATCH /tensions/{id}` — tension lifecycle (`main.py:590`, `main.py:617`, `main.py:647`)
- `POST /labour`, `GET /labour`, `GET /labour/summary` — DisCO labour tracking (`main.py:746`, `main.py:793`, `main.py:829`)
- `POST /webhook/loomio` — HMAC-verified Loomio outcome ingest (`main.py:135`)

**Service-to-service auth pattern:** `_verify_internal_caller(request)` at `main.py:886-898` uses `hmac.compare_digest` against `INTERNAL_SERVICE_TOKEN` when the env var is set. In Phase C the NetworkPolicy is the primary guard and the token is optional; in Phase B (Headscale mesh) both layers enforce access. The orchestrator, when it adds new service-to-service calls, MUST reuse this pattern — do not invent a second auth scheme.

---

## Reuse rule

**Any runtime work the orchestrator coordinates that matches an S3 primitive MUST use the existing tool or schema row.** Inventing parallel machinery is a phantom invariant in the making: it duplicates state, evades the Glass Box, and splits the review/accountability surface. Reviewers (red-team and review-desk roles) will reject any brief that introduces a new consent flow, a new audit trail, a new tension record, or a new labour enumeration when the existing one already covers the case.

The openclaw-orchestrator's legitimate net-new surface is the **coordination layer** between these primitives — routing, ephemeral circle formation, lateral handoff, rounds facilitation, and runtime paramount-objection enforcement. Those are enumerated in `coordination-gaps.md`.
