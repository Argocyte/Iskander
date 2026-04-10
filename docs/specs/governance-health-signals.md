# Governance Health Signals and Cooperative Lifecycle Nudging

*Draft spec — April 2026*

---

## Purpose

New cooperatives face a halting problem: they don't know what they don't know. Experienced cooperators carry hard-won governance knowledge in their heads. This spec defines how Iskander's Clerk agent externalises that knowledge — observing governance health signals, matching them against a curated pattern library, and surfacing relevant suggestions at the right moment in a cooperative's lifecycle.

This is ICA Principle 5 (Education, Training, and Information) and Principle 6 (Cooperation Among Cooperatives) made operational.

---

## Design Principles

**Observe, don't diagnose.** The Clerk notices patterns and asks questions. It does not declare that a cooperative's governance is failing or prescribe a single correct response.

**Timely, not constant.** A cooperative receiving daily governance feedback will ignore it. Nudges are triggered by signals, not scheduled. The appropriate cadence is roughly monthly for health reports, immediate for acute signals.

**Contextual, not generic.** "Here is how some cooperatives at your size and stage addressed this" is useful. "You should adopt S3" is not. Suggestions reference the cooperative's type, size, and governance history.

**Opt-in knowledge sharing.** Cooperatives can contribute anonymised governance patterns to the commons. This is never automatic — it requires explicit consent.

**Members govern; the Clerk informs.** No nudge overrides member authority. Every suggestion can be dismissed, snoozed, or marked "not relevant to us."

---

## Architecture

### 1. Health Assessment Engine

The Clerk runs a governance health assessment periodically (default: monthly) and on-demand. The assessment reads from:

- **Loomio API**: poll results, stance counts, quorum rates, discussion activity, proposal closure times
- **Decision-recorder** (PostgreSQL): agreement review dates, tension backlog, decision velocity
- **Mattermost API**: channel activity, participation breadth, repeated facilitator detection

The output is a structured `GovernanceHealthReport` stored in the decision-recorder with the assessment date, signals detected, and any nudges triggered.

```
GovernanceHealthReport
  cooperative_id
  assessed_at
  lifecycle_stage          # enum: founding | growing | maturing | scaling | federated
  signals: [GovernanceSignal]
  nudges_triggered: [NudgeRecord]
  suppressed_nudges: [str]  # nudge IDs dismissed by members
```

### 2. Signal Catalogue

Each signal has:
- A **detection rule** (observable condition over Loomio/Mattermost/decision-recorder data)
- A **severity** (`advisory` | `warning` | `urgent`)
- A **lifecycle stage** where it is most relevant
- One or more **nudge templates** to offer

| Signal ID | Name | Detection Rule | Severity | Stage |
|-----------|------|---------------|----------|-------|
| `SIG-01` | Quorum erosion | Quorum missed in ≥3 of last 5 votes | warning | growing+ |
| `SIG-02` | Participation collapse | Active voter rate dropped >20% vs 90-day baseline | warning | any |
| `SIG-03` | Facilitator concentration | Same member facilitated >70% of governance meetings | advisory | growing+ |
| `SIG-04` | Decision velocity decline | Average proposal resolution time increased >50% vs 90-day baseline | advisory | maturing+ |
| `SIG-05` | Block rate spike | Consent proposals blocked in ≥3 of last 10 proposals | warning | any |
| `SIG-06` | Governance debt | ≥5 agreements with review date overdue >30 days | advisory | any |
| `SIG-07` | Tension backlog | ≥8 logged tensions unprocessed >14 days | advisory | any |
| `SIG-08` | Meeting length trend | Average governance meeting duration increased >40% vs baseline | advisory | growing+ |
| `SIG-09` | Structural scale threshold | Membership exceeded 15/30/50 with no circle structure change | advisory | growing |
| `SIG-10` | Founding group lock-in | <30% of active voters are post-founding members | warning | maturing |
| `SIG-11` | Unanimous voting pattern | >90% of decisions pass with no abstentions or objections | advisory | any |
| `SIG-12` | AGM quorum risk | Based on current participation, projected quorum at next AGM <80% likely | warning | any |
| `SIG-13` | Single-point governance | One member holds >3 formal governance roles simultaneously | warning | growing+ |
| `SIG-14` | Discussion-to-vote gap | >40% of proposals have <2 discussion comments before vote | advisory | any |

**Note on SIG-11 (unanimous voting):** This appears positive but often indicates social pressure, disengagement, or decisions being made informally before formal votes. It warrants gentle inquiry, not alarm.

### 3. Lifecycle Stage Detection

The Clerk infers lifecycle stage from:

| Stage | Indicators |
|-------|-----------|
| `founding` | Cooperative age <6 months OR <3 completed governance cycles |
| `growing` | Age 6–24 months AND membership actively increasing |
| `maturing` | Age >18 months AND membership stable OR slow-growing |
| `scaling` | Membership crossed a structural threshold (15, 30, 50 members) |
| `federated` | Cooperative participates in multi-org governance (federation, secondary coop) |

Stage is used to filter which signals and nudges are surfaced. A founding cooperative does not need circle restructuring advice. A 5-year-old 80-member cooperative does not need founding-stage onboarding tips.

### 4. Nudge Templates

Each nudge is a structured message delivered via the Clerk in Mattermost (governance channel) and/or Loomio (pinned announcement). Nudges are:

- **Not prescriptive** — they present a pattern and ask a question
- **Evidence-based** — they reference what the Clerk observed
- **Actionable** — they offer a next step the cooperative can take or decline

Example nudge for `SIG-01` (quorum erosion):

> "Quorum has been missed in 3 of your last 5 votes. This is a common pattern when cooperatives reach the 15–20 member range — participation habits formed at founding don't always scale.
>
> Some cooperatives address this by:
> - Reviewing quorum thresholds (is 50% still the right bar for routine decisions?)
> - Moving more decisions to async Loomio rather than meeting-only votes
> - Delegating operational decisions to smaller circles, reserving full-membership votes for strategic matters
>
> Would you like to discuss this in a governance review session? I can prepare a summary of your participation trends."

Example nudge for `SIG-09` (structural scale threshold):

> "Your cooperative has grown to [N] members — a size where many cooperatives find that delegating some decisions to smaller circles makes governance more manageable.
>
> You don't need to restructure everything at once. A common starting point is creating a single Finance circle with spending authority up to [X], leaving everything else with the full membership. This typically reduces the agenda burden on general meetings by 30–40%.
>
> Radical Routes' toolkit and the S3 Practical Guide both have templates for this transition. I can help draft a circle charter if you'd like to explore it."

### 5. Pattern Library

The pattern library is a curated, versioned set of known governance failure modes and proven responses. It is distinct from the nudge templates — nudges are triggered automatically; the pattern library is searchable by members.

**Sources**:
- ICA Guidance Notes on the Co-operative Principles (`docs/reference/ica-guidance-notes-*.md`)
- Radical Routes Toolkit (governance and conflict resolution sections)
- S3 Practical Guide patterns
- Contributed cooperative experience (opt-in, anonymised)

**Structure of each pattern entry**:

```yaml
id: PAT-012
title: Founder personality capture
description: >
  A founding member's personal style becomes so embedded in governance
  norms that the cooperative struggles to function differently, even when
  that person's approach is no longer serving the group.
signals: [SIG-10, SIG-03]
lifecycle_stages: [maturing]
what_helps:
  - Explicit role rotation policy (no role held >2 years without reconfirmation)
  - Governance retrospective — "what norms did we inherit vs. choose?"
  - Circle structure separates domains from individuals
what_doesnt_help:
  - Waiting for the founder to volunteer to step back
  - Addressing it only when conflict has escalated
real_world_precedents:
  - Radical Routes working group rotation policy
  - S3 Role Selection pattern with regular review
references:
  - ICA Guidance Notes Part 2, Section 3.2
  - docs/sociocracy-integration.md Section 7.2
```

### 6. Knowledge Commons Contribution

Cooperatives can contribute their own patterns to the commons. The contribution flow:

1. Member triggers via Clerk: "We learned something — can I add it to the knowledge base?"
2. Clerk asks: what was the situation, what did you try, what happened, what would you do differently?
3. Clerk drafts a pattern entry and presents it to the cooperative for review
4. Cooperative approves (consent process) — Glass Box logs the approval
5. Pattern submitted to Iskander commons repository (public, anonymised — no cooperative names or identifying details unless explicitly approved)

This is the cooperative equivalent of Stack Overflow: accumulated real-world experience, accessible to the next cooperative facing the same problem.

---

## Onboarding Integration

The genesis boot wizard (existing, `docs/archive/2026-03-17-genesis-boot-sequence-design.md`) collects enough information to initialise governance health baselines:

| Question | What it initialises |
|----------|-------------------|
| Cooperative type (housing / worker / consumer / platform / other) | Pattern library filter; relevant precedents |
| Founding member count | Structural threshold alerts |
| Prior cooperative governance experience? (none / some / extensive) | Onboarding intensity |
| Legal structure (FCA / Companies House / unregistered / other) | Legal compliance nudges (AGM requirements, quorum rules) |
| Has the cooperative ever had a formal governance crisis? | Sensitises certain signals |

Based on this, the Clerk delivers a **founding governance briefing** — not a lecture, but a short set of prioritised starting points:

> "You're a 6-person worker cooperative, most of you new to formal cooperative governance. Based on what typically works at your stage:
>
> - Start with an advice process rather than full consent proposals — it's lighter and teaches the habit of consulting affected people before deciding
> - Create an agreement record for every decision, even informal ones — you'll thank yourself in 12 months
> - Set a governance review date 6 months from now to check whether your current approach is still working
>
> As you grow, I'll flag when patterns suggest it's time to introduce more structure. Nothing is imposed — these are starting points, not rules."

---

## Mattermost / Loomio Delivery

| Nudge type | Delivery channel | Who sees it |
|------------|-----------------|-------------|
| Monthly health digest | Governance Mattermost channel (pinned post) | All members |
| Acute signal alert | DM to governance role holders + governance channel | Role holders |
| Onboarding briefing | Clerk DM to founding members | Founding members |
| Pattern library query | Clerk response in any channel | Requesting member |
| Knowledge commons contribution | Governance channel consent proposal | All members |

---

## Privacy and Consent

- Health signals are derived from aggregate cooperative behaviour, not individual member tracking
- The Clerk never tells a member "you specifically are a governance bottleneck" — it tells the cooperative "facilitator concentration is high"
- Knowledge commons contributions are explicitly opt-in, consent-approved, and anonymised
- Signal history and nudge records are visible to all members (Glass Box principle) — no hidden assessments

---

## Implementation Notes

### What's New

- `GovernanceHealthReport` model and storage in decision-recorder
- Signal detection logic (14 signals — most computable from existing Loomio API responses)
- Nudge template system (structured messages, not freeform AI prose)
- Pattern library data format and search
- Monthly assessment scheduler
- Knowledge commons contribution flow

### What Reuses Existing Infrastructure

- Loomio API read calls — existing `_loomio_get()` in `tools.py`
- Mattermost posting — existing `mattermost_post_message()` in `tools.py`
- Glass Box logging — existing `glass_box_log()` in `tools.py`
- Decision-recorder PostgreSQL — existing schema patterns from `src/IskanderOS/services/decision-recorder/`
- Genesis wizard — existing boot sequence in `docs/archive/2026-03-17-genesis-boot-sequence-design.md`

### Phased Delivery

**Phase 1** (minimum viable): 5 highest-signal signals (SIG-01, SIG-02, SIG-09, SIG-06, SIG-13) + monthly health digest + founding briefing.

**Phase 2**: Full 14-signal catalogue + pattern library (ICA + Radical Routes + S3 sources only).

**Phase 3**: Knowledge commons contribution flow + cross-cooperative anonymised patterns.

---

## References

1. ICA Guidance Notes on the Co-operative Principles, Parts 1 & 2 (`docs/reference/`)
2. Radical Routes Toolkit — https://toolkit.radicalroutes.org.uk/
3. Bockelbrink et al., *S3 Practical Guide* — https://sociocracy30.org/
4. `docs/sociocracy-integration.md` — Section 7 (Governance Burnout Prevention)
5. `src/IskanderOS/openclaw/agents/clerk/SOUL.md` — Clerk identity constraints
6. `src/IskanderOS/openclaw/agents/clerk/tools.py` — existing tool patterns
