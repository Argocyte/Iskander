# Privacy Models

Iskander agents operate under one of four Glass Box tiers. The tier determines what is logged, where, and who can read it. **Choose the tier at design time** — it shapes the agent's SOUL.md, tools, and Glass Box configuration.

---

## Tier 1: Public Glass Box

**Who can read it:** All cooperative members.

**What is logged:** Every write action — what the agent did, which member requested it, the agent's reasoning, and the outcome. Read operations are not logged.

**When to use:** Any cooperative-facing agent whose actions affect the shared governance of the cooperative. The Glass Box is the audit trail that gives members confidence the agent is acting within its mandate.

**Examples:**
- Clerk creates a Loomio discussion → Glass Box entry visible to all members
- Clerk posts to governance Mattermost channel → Glass Box entry
- Health Signals sends a governance nudge to the governance channel → Glass Box entry

**Implementation:** `glass_box_log()` in `tools.py` posts to `GLASS_BOX_URL/log`. Entry includes `actor`, `agent`, `action`, `target`, `reasoning`, `timestamp`.

**SOUL.md snippet:**
```
## Glass Box requirement

Every write action you take must be logged to the Glass Box before you take it.
Read operations do not require logging. If the Glass Box is unavailable, do not proceed.

The log entry must include: (1) what you are about to do, (2) which member asked, (3) your reasoning.
```

---

## Tier 2: Individual Glass Box

**Who can read it:** The member themselves (and their Personal Clerk on their PA node).

**What is logged:** Actions taken on behalf of this specific member — draft proposals saved, preferences stored, cross-cooperative notifications dispatched.

**When to use:** Personal Assistant (PA) nodes; member-facing agents that store personal data on behalf of one member.

**Examples:**
- PA stores a member's governance notification preferences
- PA saves a draft proposal the member is working on
- PA logs cross-cooperative participation data for the member's own view

**Implementation:** Glass Box partition scoped to `member_id`. Entry is not returned by cooperative-level Glass Box queries.

**SOUL.md snippet:**
```
## Glass Box requirement

Actions you take on behalf of this member are logged to their personal Glass Box partition.
This is visible only to them — not to the cooperative's governance structures.
Read operations are not logged.
```

---

## Tier 3: Restricted Glass Box

**Who can read it:** Designated role holders only (e.g. safeguarding officers, compliance leads).

**What is logged:** Escalation actions — that an escalation occurred, when, what type, and a reference ID. **Not** the content of the underlying conversation.

**When to use:** Safeguarding escalation; compliance records that must be held securely but are not public.

**Establishing the partition:** Requires a cooperative consent decision in Loomio (decision-recorder record). The agent queries the governance manifest `safeguarding_officers` field (set via consent decision) — not a config file an administrator can edit unilaterally.

**Examples:**
- Wellbeing agent escalates a Level 2 safeguarding concern → restricted Glass Box entry: `{type: "safeguarding_alert", level: 2, reference_id: "WB-2026-04-09-001", timestamp: "..."}`
- Compliance agent records a regulatory filing → restricted Glass Box entry

**What is never logged in this tier:** Conversation content, member names beyond the reference ID, what was said.

**Implementation:** Separate database partition. `glass_box_log_restricted(partition="safeguarding", ...)` — does not call the public Glass Box endpoint.

**SOUL.md snippet:**
```
## Glass Box requirement

Escalation actions are logged to the restricted safeguarding Glass Box partition,
readable only by designated safeguarding officers. Conversation content is never logged.
Only the fact that an escalation occurred, its level, and a reference ID are recorded.
```

---

## Tier 4: Confidential

**Who can read it:** Nobody — not the cooperative, not other members, not governance role holders.

**What is logged:** Timestamps only — "conversation started", "conversation ended". No content, no summary, no reference to what was discussed.

**When to use:** Wellbeing conversations; mediation sessions; any context where a member needs to speak freely without any record being kept.

**Establishing confidential mode:** The agent announces the privacy model and requests explicit consent before proceeding (see `agent-switching.md`). If the member does not consent, the conversation does not happen.

**Physical isolation:** Confidential conversations must not be stored in the main conversation history database. The conversation exists only in memory for the duration of the session. When the session ends, nothing is written.

**The Glass Box exception:** Iskander's Glass Box principle requires all write actions to be logged. The Confidential tier is a named exception to this principle, requiring:
1. A SOUL.md that explicitly names the exception
2. The agent announcing the exception to the member before conversation
3. The member's explicit consent

**SOUL.md snippet:**
```
## Glass Box exception

This agent operates under a Glass Box exception approved by cooperative consent.
Conversation content is never logged. Only the fact that a conversation took place
is recorded (timestamps). This means no audit trail exists for the content of conversations
with this agent. Members are told this before conversation begins and must consent.

If the Glass Box service is called from this agent context, it MUST only receive
timestamp entries — never content, summaries, or reasoning.
```

---

## Choosing a Tier

```
Is this agent cooperative-facing (serves all members collectively)?
  └─ Yes → Tier 1 (Public Glass Box)
  └─ No → Is it member-facing (serves one member)?
        └─ Yes → Does it handle sensitive personal data (wellbeing, conflict)?
              └─ Yes → Does it need escalation to role holders (safeguarding)?
                    └─ Yes → Tier 3 (Restricted) for escalations + Tier 4 (Confidential) for conversation
                    └─ No → Tier 4 (Confidential)
              └─ No → Tier 2 (Individual)
```

---

## Mixing Tiers

An agent may use multiple tiers for different actions:

- The **Wellbeing Agent** uses Tier 4 for conversation content, and Tier 3 for safeguarding escalations. These are separate operations with separate logging paths.
- A **Personal Clerk** uses Tier 2 for preference storage, but if the member asks it to post to a cooperative channel on their behalf, that action uses Tier 1.

When an agent switches tier mid-conversation, announce it:
> "I'm about to [action]. This will be visible to [who]. Are you happy for me to proceed?"
