---
name: iskander-phase-b-expansion
description: Expand the Iskander MVP into the full Loomio-native system. Use this skill when the user mentions Phase B, expanding the MVP, Loomio-native expansion, adding blockchain recording, multi-channel support, web dashboard, federation, inter-cooperative networking, or any Phase B weekly milestone. Also use when porting existing codebase components to the new architecture.
---

# Phase B: Loomio-Native Expansion

Expand the validated MVP (Phase C) into the full cooperative-web3-architect spec. Weeks 4-8.

## Week 4-5: Blockchain Recording + Values Council

| Task | Details |
|------|---------|
| Add Anvil | Add `anvil` service to `docker-compose.full.yml`, port 8545 |
| Deploy Constitution.sol | Reuse existing `contracts/src/Constitution.sol` on local Anvil |
| Chain bridge | Update decision-recorder to submit IPFS hashes on-chain after DB write |
| ICA vetter skill | Port 27-question rubric from `backend/agents/library/ica_vetter.py` |
| Values Council | Use `iskander-values-council` skill for first 2 guardian agents |

Chain bridge addition to decision-recorder:
```python
# After IPFS pin, submit hash to Constitution.sol
tx_hash = await web3.eth.send_transaction({
    "to": CONSTITUTION_ADDRESS,
    "data": constitution.functions.recordDecision(ipfs_cid, poll_id).build_transaction()
})
```

## Week 5-6: Multi-Channel Expansion

| Task | Details |
|------|---------|
| Telegram | Create bot via BotFather, add to `openclaw.json` channels |
| Matrix/Dendrite | Add Dendrite service to docker-compose, configure OpenClaw Matrix channel |
| Loomio @mention | Webhook on new comments containing "@clerk" → route to OpenClaw |

OpenClaw multi-channel config addition:
```json5
channels: {
  web: { port: 3100 },          // Existing: Iskander chat widget
  telegram: { token: "..." },    // New: Telegram bot
  matrix: { homeserver: "...", token: "..." }  // New: Matrix
}
```

## Week 6-7: Web Dashboard

Lightweight status page (reuse some existing Next.js patterns if useful):

| Panel | Data Source |
|-------|------------|
| Active Proposals | Loomio API `/api/v1/polls?status=active` |
| Glass Box Trail | decision-recorder `/glass-box/recent` |
| Decision Log | decision-recorder `/decisions` with IPFS links |
| Treasury Balance | Steward's last reported balance |
| Values Profile | Values Council latest assessment |

## Week 7-8: Federation + Inter-Coop

| Task | Details |
|------|---------|
| MCP server | Expose cooperative's agent capabilities via MCP protocol |
| Liaison agent | New OpenClaw agent for inter-cooperative communication |
| Agent Card | Machine-readable description published to network registry |
| Discovery test | Two Iskander nodes discover each other |

## Code Porting Schedule

| Component | Source | Destination | Week |
|-----------|--------|-------------|------|
| ICA vetter rubric | `backend/agents/library/ica_vetter.py` | OpenClaw skill | 4 |
| Constitution.sol | `contracts/src/Constitution.sol` | Anvil deployment | 4 |
| CoopIdentity.sol | `contracts/src/CoopIdentity.sol` | Anvil deployment | 4 |
| Cooperation scoring | `backend/agents/library/ipd_auditor.py` | OpenClaw skill | 6 |
| Energy scheduling | `backend/energy/` | OpenClaw skill | 7 |

## docker-compose.full.yml Services

| Service | New in Phase B | Port |
|---------|---------------|------|
| anvil | Yes | 8545 |
| dendrite | Yes | 8008 |
| dashboard | Yes | 3200 |
| decision-recorder | Updated (chain bridge) | 8100 |

## Verification

Week 8 success criteria:
1. `SELECT d.*, encode(tx_hash, 'hex') FROM decision_log d` — every decision has on-chain hash
2. Two council agents produce assessment with IPFS evidence links
3. Clerk responds via chat widget, Telegram, and Matrix
4. Dashboard shows live cooperative status at `http://localhost:3200`
5. Two Iskander nodes: `openclaw discover --network` shows both
