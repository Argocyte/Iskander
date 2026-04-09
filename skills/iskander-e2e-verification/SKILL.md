---
name: iskander-e2e-verification
description: Run end-to-end verification of the Iskander MVP. Use this skill when the user mentions verifying the system, end to end testing, integration testing, testing the full decision loop, checking if Iskander works, or validating the MVP flows. Also use after completing implementation to confirm everything connects.
---

# End-to-End Verification

Four flows that prove the core proposition works. Run each in sequence — each depends on the previous passing.

## Prerequisites

All services running: `docker compose -f docker-compose.mvp.yml ps` shows 6 healthy services.

## Flow 1: Member Asks a Question

**Tests**: Iskander chat widget → OpenClaw web channel → Clerk → Ollama → response

Steps:
1. Open `http://localhost:3000` in browser
2. Click Iskander chat widget (bottom-right)
3. Type: "How much is in our treasury?"
4. Clerk should respond with treasury balance (or "no wallet configured" if Safe not set up)

**Pass criteria**:
- Response appears in chat widget within 30 seconds
- Response is plain language, not JSON or error
- Glass Box entry created: `curl http://localhost:8100/glass-box/recent | grep "treasury"`

## Flow 2: Member Proposes a Decision

**Tests**: Chat widget → Clerk → loomio-bridge → Loomio API → webhook → decision-recorder → IPFS

Steps:
1. In chat widget: "I'd like to propose we spend 200 tokens on server upgrades"
2. Clerk drafts proposal, asks for confirmation
3. Confirm → Clerk creates Loomio poll via API
4. Open Loomio — verify poll exists in cooperative group
5. Vote on the poll (need 2+ members for quorum)
6. Close the poll
7. Wait for webhook to fire → check decision-recorder

**Pass criteria**:
- Poll visible in Loomio within 10 seconds of confirmation
- `SELECT * FROM decision_log ORDER BY recorded_at DESC LIMIT 1` returns the decision
- `ipfs_cid` column is populated (non-null)
- Clerk reports outcome in chat: "The proposal [passed/failed]"

## Flow 3: Steward Flags an Anomaly

**Tests**: Steward heartbeat → threshold detection → loomio-bridge → Loomio proposal

Steps:
1. Manually trigger Steward's scan-transactions procedure (or wait for heartbeat)
2. If no real transactions, mock by calling the treasury-monitor skill directly
3. Verify a Loomio proposal appears in the cooperative group

**Pass criteria**:
- Loomio poll created by Steward (check poll author)
- Poll title mentions the transaction amount
- Glass Box shows Steward action: `curl http://localhost:8100/glass-box/recent | grep "steward"`

## Flow 4: Glass Box Transparency

**Tests**: Chat widget → Clerk → Glass Box query → formatted response

Steps:
1. In chat widget: "What have you done today?"
2. Clerk queries Glass Box API
3. Clerk responds with formatted list of recent actions

**Pass criteria**:
- Response lists actions from Flows 1-3 (if run in sequence)
- Each action includes: what was done, why, when
- No raw JSON in response — plain language only

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Chat widget not loading | Loomio running? Widget JS injected? Check browser console. |
| Clerk not responding | OpenClaw running on port 3100? `curl http://localhost:3100/health` |
| Loomio API 401 | API key valid? Check `Authorization: Bearer` header. |
| No decision recorded | Webhook configured? decision-recorder running on 8100? Check logs. |
| IPFS CID null | Kubo running on 5001? `curl http://localhost:5001/api/v0/id` |
| Steward not proposing | Heartbeat configured? Threshold set? Check Steward SOUL.md. |
