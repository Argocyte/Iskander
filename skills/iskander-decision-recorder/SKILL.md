---
name: iskander-decision-recorder
description: Build the decision recorder service and Glass Box audit trail. Use this skill when the user mentions decision recording, audit trail, decision logging, IPFS pinning, Loomio webhooks, Glass Box transparency, agent action logging, or building the webhook service that captures Loomio poll outcomes.
---

# Decision Recorder + Glass Box

Lightweight FastAPI service that records Loomio decisions with IPFS hashes and provides agent audit trail.

## Step 1: Create Database Schema

Write `src/IskanderOS/infra/decision_log.sql`:

```sql
CREATE TABLE IF NOT EXISTS decision_log (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loomio_poll_id INTEGER NOT NULL,
    poll_type      TEXT NOT NULL,
    title          TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    agree_count    INTEGER NOT NULL DEFAULT 0,
    disagree_count INTEGER NOT NULL DEFAULT 0,
    abstain_count  INTEGER NOT NULL DEFAULT 0,
    block_count    INTEGER NOT NULL DEFAULT 0,
    ipfs_cid       TEXT,
    discussion_url TEXT,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_actions (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id  TEXT NOT NULL,
    action    TEXT NOT NULL,
    rationale TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Step 2: Write FastAPI Service

Create `src/IskanderOS/services/decision-recorder/main.py` (~120 lines):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/hooks/loomio` | POST | Receive Loomio poll_closed webhook |
| `/glass-box/recent` | GET | Return recent agent actions (limit 50) |
| `/glass-box/log` | POST | Log an agent action |
| `/decisions` | GET | List recorded decisions |
| `/health` | GET | Health check |

Webhook handler flow:
1. Parse Loomio webhook payload (extract poll_id)
2. Fetch full discussion + poll + stances from Loomio API
3. Bundle into JSON document
4. Pin to IPFS Kubo: `POST http://localhost:5001/api/v0/add`
5. Insert into `decision_log` with IPFS CID
6. Return 200

Dependencies: `fastapi`, `uvicorn`, `asyncpg`, `httpx`

## Step 3: Write Dockerfile

Create `src/IskanderOS/services/decision-recorder/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
```

## Step 4: Create Glass Box OpenClaw Skill

Create `src/IskanderOS/openclaw/skills/glass-box/SKILL.md`.
Teaches agents to log actions and query the audit trail:
- `log-action`: POST to `/glass-box/log` with agent_id, action, rationale
- `query-recent`: GET `/glass-box/recent` — format as plain-language summary

## Step 5: Add IPFS Kubo to Docker Compose

Add to `docker-compose.mvp.yml`:
```yaml
ipfs:
  image: ipfs/kubo:latest
  ports:
    - "5001:5001"
  volumes:
    - ipfs_data:/data/ipfs
```

## Files to Create

| File | Purpose |
|------|---------|
| `src/IskanderOS/infra/decision_log.sql` | DB schema |
| `src/IskanderOS/services/decision-recorder/main.py` | FastAPI service |
| `src/IskanderOS/services/decision-recorder/Dockerfile` | Container image |
| `src/IskanderOS/services/decision-recorder/requirements.txt` | Python deps |
| `src/IskanderOS/openclaw/skills/glass-box/SKILL.md` | Audit trail skill |

## Verification

```bash
# Service responds
curl -s http://localhost:8100/health
# Expected: {"status":"ok"}

# Glass Box accepts log entries
curl -s -X POST http://localhost:8100/glass-box/log \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"clerk","action":"answered question","rationale":"member asked about treasury"}'
# Expected: 200

# Glass Box returns entries
curl -s http://localhost:8100/glass-box/recent
# Expected: JSON array of recent actions

# Decision recording (after Loomio poll closes)
# Check: SELECT * FROM decision_log ORDER BY recorded_at DESC LIMIT 1;
# Expected: Row with ipfs_cid populated
```
