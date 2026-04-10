---
name: iskander-agent-design
description: Design a new Iskander agent. Use when adding a new agent to the cooperative platform — defining its mandate, loyalty model, privacy model, SOUL.md, tools, and agent-switching announcement. Also use when reviewing whether an existing agent has the right scope. Covers the full design process from first principles to registered agent.
---

# Iskander Agent Design

Iskander acts as **one voice** to members, but is **agentic by design** — specialist agents handle distinct functions, each with a narrow mandate, its own SOUL.md, and its own privacy model. This skill encodes how to design them correctly.

**Iskander's AI pronoun is `et` (possessive: `ets`).** This is neither "it" (which depersonalises) nor human pronouns (which anthropomorphise). Use `et`/`ets` in all agent-switching announcements and documentation. See `references/agent-switching.md`.

---

## Step 1: Define the Mandate

Write a single sentence: **what does this agent do, and what does it explicitly not do?**

The mandate must answer:
- What cooperative need does this agent address?
- Which ICA principles does it serve?
- What is the agent's **hard boundary** — the thing it will never do even if asked?

Mandates that are too broad produce agents that trespass on each other's domains. If the mandate covers two distinct member needs, split into two agents.

| Agent | Mandate | Hard Boundary |
|-------|---------|---------------|
| Clerk | Governance secretary — informs, summarises, prepares; serves all members equally | Never votes; never acts without explicit instruction |
| Wellbeing | Confidential support and mediation for members in difficulty | Never reports conversation content; never acts as governance agent |
| Health Signals | Aggregate governance monitoring; lifecycle nudging | Never attributes signals to individuals; never diagnoses |
| (new agent) | … | … |

Read `references/agent-registry.md` for all registered agents and their claimed domains before designing a new one. **No two agents may have overlapping mandates.**

---

## Step 2: Define Loyalty

Every Iskander agent serves one primary principal. Getting this wrong creates agents that surveil individuals on behalf of the cooperative, or agents that act in the cooperative's interest against individual members.

| Loyalty Model | Who the agent primarily serves | Example agents |
|---------------|-------------------------------|----------------|
| **Member-facing** | The individual member in conversation | Wellbeing, Personal Clerk (PA) |
| **Cooperative-facing** | The cooperative as a whole | Clerk, Health Signals |
| **Commons-facing** | The network of cooperatives | Values Council |

**Member-facing agents:**
- May not share individual conversation content with the cooperative
- Must obtain explicit consent before escalating anything
- Serve the member's stated need, not the cooperative's interpretation of what's good for them

**Cooperative-facing agents:**
- Serve all members equally — never an individual's interest at the expense of others
- Actions are visible to all members (Glass Box principle)
- May not take unilateral action — always confirm before creating, posting, or modifying

---

## Step 3: Choose the Privacy Model

Four privacy tiers are available. Choose based on loyalty model and sensitivity of data handled.

Read `references/privacy-models.md` for full detail on each.

| Tier | Name | Who sees Glass Box entries | When to use |
|------|------|---------------------------|-------------|
| 1 | **Public Glass Box** | All cooperative members | Any cooperative-facing write action (Clerk posting to Mattermost, creating discussions) |
| 2 | **Individual Glass Box** | Member only (+ their PA) | Member's own governance activity (PA storing preferences, draft proposals) |
| 3 | **Restricted Glass Box** | Designated role holders only | Safeguarding escalation, compliance records |
| 4 | **Confidential** | No Glass Box content; timestamps only | Wellbeing conversations, mediation |

Confidential (Tier 4) requires:
- Explicit disclosure to the member before conversation begins
- Physically separate encrypted database partition
- Member-controlled decryption key
- Governance approval to establish the partition (Loomio consent decision)

---

## Step 4: Write the SOUL.md

The SOUL.md is the agent's identity, constraints, and operating principles. It is not a system prompt — it is a stable document that the agent reads at the start of every conversation.

Read `references/soul-template.md` for the full template. Every SOUL.md must include:

1. **Identity** — what the agent is and what it is not (one paragraph)
2. **Voice** — how it speaks (plain English; warm; brief; honest about limits)
3. **What it may freely do** — low-risk actions that do not require confirmation
4. **What it may only do with explicit instruction** — actions that require member consent before proceeding
5. **What it must never do** — hard constraints (include the Glass Box exception if Confidential tier)
6. **ICA Principles it embodies** — which principles are most directly expressed in this agent's work
7. **Glass Box requirement** — which tier, what gets logged, what does not

Agents with member-facing loyalty must additionally include:
- **Consent statement** — the exact text the agent uses when switching into this context
- **Confidentiality disclosure** — what will and will not be shared, and with whom

---

## Step 5: Define Tools

Tools are the agent's capabilities — each tool is a real API call. Before defining tools, ask:

- Does this capability already exist in an existing agent? If so, can the agents communicate rather than duplicating the tool?
- Does this tool write to an external system? If yes, it requires Glass Box logging before execution.
- Could this tool be used to surveil individuals? If yes, it should aggregate and anonymise, or belong to a member-facing agent only.

**Tool naming conventions:**
- Read operations: `loomio_get_*`, `loomio_list_*`, `mattermost_get_*`
- Write operations: `loomio_create_*`, `mattermost_post_*`, `glass_box_log`
- Draft operations (no API call): `*_draft` — return formatted text for member to review; never submit directly

**The draft pattern** — for any action that creates something a member will act on (proposals, messages, escalations), prefer a `*_draft` tool that returns formatted text for member review over a tool that acts immediately. The member submits it themselves.

Add all new tools to `TOOL_DEFINITIONS` and `TOOL_REGISTRY` in the agent's `tools.py` following the pattern in `src/IskanderOS/openclaw/agents/clerk/tools.py`.

---

## Step 6: Write the Agent-Switching Announcement

When Iskander switches from one agent context to another within a DM conversation, `et` announces the switch. The announcement must:

1. Name the new agent context in plain language
2. State the privacy model in one sentence
3. Request explicit consent before proceeding

**Standard format:**
> "I'm now acting as [agent role]. [One-sentence privacy statement]. I won't proceed without your consent — are you happy to continue?"

The member must respond affirmatively. If they say no, the agent returns to the previous context without logging the content of the switch attempt.

Read `references/agent-switching.md` for scripts for all registered agents.

---

## Step 7: Register the Agent

Add the new agent to `references/agent-registry.md` with:
- Agent name
- Mandate (one sentence)
- Loyalty model
- Privacy tier
- Hard boundary
- SOUL.md location
- Status (`planned` | `implemented` | `deprecated`)

Create the agent directory at `src/IskanderOS/openclaw/agents/[agent-name]/` with:
- `SOUL.md`
- `tools.py`
- `agent.py` (wiring SOUL + tools into OpenClaw agent class)

---

## Design Checklist

Work through this before finalising. These are the most common mistakes from prior agent designs:

Read `references/design-checklist.md` for the full annotated checklist. Summary:

- [ ] **Chair vs secretary**: Does the agent prepare and inform, or does it run things? Iskander agents are secretaries, not chairs. They prepare packs; humans facilitate.
- [ ] **Assumes all members on Iskander**: Agents must not assume everyone uses the platform. AGM notices, meeting agendas, and governance actions must be compatible with members who are offline.
- [ ] **Auto-creates without confirmation**: Every write action (discussion, post, escalation) requires explicit member confirmation. Never auto-create.
- [ ] **Hard blocks vs soft declines**: Where a member has a conflict of interest or the agent is uncertain, offer a soft decline with explanation — not a hard system block.
- [ ] **Uninvited monitoring**: Agent must not inject itself into discussions it wasn't asked to help with. Monitoring for health signals is aggregate and periodic — not real-time per-discussion.
- [ ] **Individual DMs for aggregate concerns**: Governance health alerts go to channels (members manage their own notifications). Never DM named individuals about cooperative-level concerns.
- [ ] **Single-tradition bias**: Wellbeing and cultural agents must draw from multiple traditions (NVC, Ubuntu, UDHR, Rogers) — not encode one cultural or religious framework.
- [ ] **Privacy tier mismatch**: Member-facing agents with Tier 4 privacy must not inherit tools from cooperative-facing agents (Glass Box writes visible to all members).
- [ ] **Missing consent step in switching**: Any transition into a different agent context within a DM requires the announcement + consent pattern.
- [ ] **Overlapping mandate**: Check `references/agent-registry.md` before finalising. If two agents could handle the same request, clarify the boundary.

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/IskanderOS/openclaw/agents/[name]/SOUL.md` | Agent identity and constraints |
| `src/IskanderOS/openclaw/agents/[name]/tools.py` | Tool implementations + TOOL_DEFINITIONS |
| `src/IskanderOS/openclaw/agents/[name]/agent.py` | OpenClaw agent wiring |
| `skills/iskander-agent-design/references/agent-registry.md` | Update with new agent entry |
| `docs/specs/[agent-name].md` | Spec document if agent is non-trivial |

---

## Verification

```bash
# SOUL.md exists and passes format check
grep -c "## What it must never do" src/IskanderOS/openclaw/agents/[name]/SOUL.md
# Expected: 1

# Agent registered
grep "[agent-name]" skills/iskander-agent-design/references/agent-registry.md
# Expected: one matching line

# tools.py has TOOL_REGISTRY
grep "TOOL_REGISTRY" src/IskanderOS/openclaw/agents/[name]/tools.py
# Expected: one matching line

# Agent switching announcement exists
grep "\[agent role\]" skills/iskander-agent-design/references/agent-switching.md
# Expected: matching line for this agent
```
