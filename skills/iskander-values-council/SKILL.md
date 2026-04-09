---
name: iskander-values-council
description: Create the Values Council — multiple OpenClaw agents that assess cooperatives against ICA values and ethical principles. Use this skill when the user mentions Values Council, ICA values agents, council agents, cooperative assessment, values scoring, values guardians, or building the automated cooperative evaluation system. This is a Phase B task.
---

# Values Council

Multiple OpenClaw agents, each evaluating cooperatives against one ICA value or ethical principle. Phase B (Week 4-5).

Reference: `src/IskanderOS/docs/ica-statement-on-cooperative-identity.md`

## Council Agents

6 agents for core values + 4 agents for ethical values = 10 total.

| Agent | Value/Ethic | Evaluates |
|-------|-------------|-----------|
| Self-Help Guardian | Self-Help | Member capability building, self-service tools, training |
| Self-Responsibility Guardian | Self-Responsibility | Governance participation, workload distribution, commitment fulfilment |
| Democracy Guardian | Democracy | One-member-one-vote, HITL compliance, information access |
| Equality Guardian | Equality | Equal treatment, open membership, benefit distribution |
| Equity Guardian | Equity | Needs recognition, support structures, accessibility |
| Solidarity Guardian | Solidarity | Mutual aid, inter-coop support, commons contributions |
| Honesty Guardian | Honesty | Record consistency, financial transparency, accurate reporting |
| Openness Guardian | Openness | Decision transparency, public records, communication clarity |
| Social Responsibility Guardian | Social Responsibility | Conflict reduction, community impact, cooperation fostering |
| Caring Guardian | Caring for Others | Emotional support, member wellbeing, distress recognition |

## Step 1: Write Council Agent SOUL.md Template

Each agent gets a SOUL.md following this structure:
```markdown
## Identity
You are the [Value] Guardian of the Iskander network Values Council.
You evaluate cooperatives solely through the lens of [Value].

## Your Value
[Full ICA definition of the value]

## Evidence Sources (public on-chain records only)
- [3-5 specific data sources this guardian checks]

## What You Evaluate
- [3-5 specific questions this guardian asks]

## What You Never Access
- Individual member identities or personal data
- Private communications
- Any data not on the public blockchain or IPFS

## Voting Scale
- Strong alignment: Clear, consistent evidence of living this value
- Good alignment: Generally demonstrates with minor gaps
- Developing: Shows intention but inconsistent practice
- Needs attention: Significant gaps between stated values and actions
- Serious concern: Evidence of actions contradicting this value
```

## Step 2: Deploy First Two Agents

Start with Democracy Guardian + Honesty Guardian (most verifiable from on-chain data).

Create in `src/IskanderOS/openclaw/agents/council/`:
- `democracy-guardian/SOUL.md`
- `honesty-guardian/SOUL.md`

## Step 3: Port ICA Vetter Rubric

Extract the 27-question rubric from `backend/agents/library/ica_vetter.py` (lines 253-414).
Rewrite as an OpenClaw skill: `src/IskanderOS/openclaw/skills/ica-vetter/SKILL.md`.
Map each question to the appropriate council agent.

## Step 4: Council Assessment Smart Contract

Read `references/council-contract.md` for the CouncilAssessment.sol spec:
- Records 10 agent votes per assessment
- Stores IPFS references to full reasoning
- Links assessments to triggers (tenders, partnership requests)
- Enforces all agents must vote before publication

## Step 5: Assessment Interface

Build a view (in Loomio or web dashboard) showing:
- Cooperative's value profile (10-bar visualization)
- Full reasoning from each guardian
- Response from assessed cooperative
- Trend lines over time

## Files to Create

| File | Purpose |
|------|---------|
| `src/IskanderOS/openclaw/agents/council/democracy-guardian/SOUL.md` | Democracy agent |
| `src/IskanderOS/openclaw/agents/council/honesty-guardian/SOUL.md` | Honesty agent |
| `src/IskanderOS/openclaw/skills/ica-vetter/SKILL.md` | Ported ICA rubric |
| `src/IskanderOS/contracts/src/CouncilAssessment.sol` | On-chain vote recording |

## Verification

```bash
# Council agents registered
openclaw agents list | grep guardian
# Expected: democracy-guardian, honesty-guardian

# Assessment runs against test data
# Trigger: request self-assessment of own cooperative
# Expected: Both guardians produce vote + reasoning + IPFS evidence link
```
