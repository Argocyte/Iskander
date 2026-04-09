---
name: iskander-openclaw-clerk
description: Install OpenClaw, create the Clerk agent, build the Iskander chat widget for Loomio, and write the loomio-bridge and values-reflection skills. Use this skill when the user mentions setting up OpenClaw, creating the Clerk agent, configuring the Clerk, building the chat widget, writing agent SOUL files, or connecting AI agents to Loomio. Also use for Ollama integration with OpenClaw or writing custom OpenClaw skills.
---

# OpenClaw + Clerk Agent + Chat Widget

Install OpenClaw, create cooperative agents, build the Loomio-embedded chat interface.

## Step 1: Install OpenClaw

```bash
npm install -g openclaw@latest
openclaw onboard  # Select: Ollama provider, web channel
```

## Step 2: Write openclaw.json

Create `src/IskanderOS/openclaw/openclaw.json`:
```json5
{
  models: {
    providers: {
      ollama: {
        baseUrl: "http://localhost:11434"  // Native API, NOT /v1
      }
    }
  },
  channels: {
    web: {
      port: 3100,
      cors: ["http://localhost:3000"]  // Loomio frontend
    }
  }
}
```

## Step 3: Write Orchestrator SOUL.md

Create `src/IskanderOS/openclaw/agents/orchestrator/SOUL.md`.
The Orchestrator routes requests to specialist agents. Encode ICA cooperative values and significance classification rules. Read `references/orchestrator-soul.md` for the full template.

## Step 4: Write Clerk SOUL.md

Create `src/IskanderOS/openclaw/agents/clerk/SOUL.md`.
Read `references/clerk-soul.md` for the full template. Key constraints:
- Serves all members equally (ICA values: equality + democracy; Principle 1: Open Membership)
- Never votes, never advocates, never withholds information
- 6 ICA core values (self-help, self-responsibility, democracy, equality, equity, solidarity) as behavioral core
- 4 ICA ethical values (honesty, openness, social responsibility, caring for others) as ethical core
- Action significance: ROUTINE only (Notable for proposal drafting)

## Step 5: Create loomio-bridge Skill

Create `src/IskanderOS/openclaw/skills/loomio-bridge/SKILL.md`.
Teaches Clerk to call Loomio REST API. Read `references/loomio-bridge-skill.md` for procedures:

| Procedure | API Call | Output |
|-----------|----------|--------|
| list-proposals | `GET /api/v1/polls?group_id=X&status=active` | Plain-language list |
| summarise-thread | `GET /api/v1/discussions/{id}` + comments | LLM summary |
| create-proposal | `POST /api/v1/polls` | Loomio poll URL |
| check-outcome | `GET /api/v1/polls/{id}` + stances | Vote tally + outcome |
| remind-pending | `GET /api/v1/polls?closing_at_lt=24h` | Member nudge |

## Step 6: Create values-reflection Skill

Create `src/IskanderOS/openclaw/skills/values-reflection/SKILL.md`.
Guided ICA values self-assessment. Read `references/values-reflection-skill.md`.
- Walks members through all 10 ICA values (6 core + 4 ethical)
- Checks Loomio participation data for evidence
- Produces summary with strengths and improvement areas

## Step 7: Build Iskander Chat Widget

Create `src/IskanderOS/services/loomio/iskander-chat-widget/`.

| File | Purpose |
|------|---------|
| `widget.js` | Chat panel UI — floating bottom-right, WebSocket to OpenClaw |
| `inject.js` | Injects widget into Loomio pages via custom Rails initializer |
| `style.css` | Widget styling — matches Loomio's design language |

The widget:
- Authenticates via Loomio session cookie (pass user context to OpenClaw)
- Sends messages to `ws://localhost:3100/chat`
- Streams responses back
- Is context-aware: passes current Loomio thread/group ID to Clerk

Read `references/chat-widget.md` for implementation details.

## Files to Create

| File | Purpose |
|------|---------|
| `src/IskanderOS/openclaw/openclaw.json` | OpenClaw config |
| `src/IskanderOS/openclaw/agents/orchestrator/SOUL.md` | Orchestrator agent |
| `src/IskanderOS/openclaw/agents/clerk/SOUL.md` | Clerk agent |
| `src/IskanderOS/openclaw/skills/loomio-bridge/SKILL.md` | Loomio API skill |
| `src/IskanderOS/openclaw/skills/values-reflection/SKILL.md` | Values self-assessment |
| `src/IskanderOS/services/loomio/iskander-chat-widget/` | Chat widget |

## Verification

```bash
# OpenClaw running
curl -s http://localhost:3100/health
# Expected: {"status":"ok"}

# Clerk responds via web channel
curl -s -X POST http://localhost:3100/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What proposals are pending?","user_id":"test"}'
# Expected: Clerk response querying Loomio

# Chat widget loads in Loomio
# Open http://localhost:3000 — chat icon visible bottom-right
```
