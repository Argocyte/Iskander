---
name: iskander-loomio-setup
description: Deploy and configure a self-hosted Loomio instance for cooperative decision-making. Use this skill whenever the user mentions setting up Loomio, installing Loomio, configuring Loomio, deploying the HITL layer, or starting the cooperative's decision platform. Also use when troubleshooting Loomio Docker deployment, API configuration, or webhook setup.
---

# Loomio Setup

Deploy a self-hosted Loomio instance for Iskander cooperative governance.

## Prerequisites

- Docker and Docker Compose installed
- Port 3000 available
- ~1-2GB RAM free

## Steps

1. Clone loomio-deploy into `src/IskanderOS/services/loomio/`:
   ```bash
   cd src/IskanderOS/services/loomio
   git clone https://github.com/loomio/loomio-deploy.git .
   ```

2. Write `.env` with these minimum values:
   ```env
   CANONICAL_HOST=localhost
   SECRET_KEY_BASE=<generate with: openssl rand -hex 64>
   SMTP_DOMAIN=disabled
   FEATURES__DISABLE_EMAIL=1
   ```

3. Start services in order:
   ```bash
   docker compose up -d db
   docker compose run --rm app rake db:setup
   docker compose up -d
   ```

4. Create admin account at `http://localhost:3000` — use the cooperative's name.

5. Create group "Iskander Cooperative" — set to "Members only" visibility.

6. Generate API key: Profile → API Keys → create key named "clerk-agent".

7. Configure outgoing webhook for decision recording:
   - Group Settings → Webhooks → Add
   - URL: `http://decision-recorder:8100/hooks/loomio`
   - Events: `poll_closed`

## Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/discussions` | Create thread |
| GET | `/api/v1/discussions?group_id=X` | List threads |
| POST | `/api/v1/polls` | Create proposal/poll |
| GET | `/api/v1/polls/{id}` | Read poll results |
| POST | `/api/v1/stances` | Cast vote |
| GET | `/api/v1/polls?group_id=X&status=active` | Active proposals |

All API calls require header: `Authorization: Bearer <API_KEY>`

## Files to Create

| File | Purpose |
|------|---------|
| `src/IskanderOS/services/loomio/.env` | Loomio environment config |
| `src/IskanderOS/services/loomio/docker-compose.yml` | Use loomio-deploy's default |

## Verification

Run these checks — all must pass:

```bash
# Loomio web UI loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
# Expected: 200

# API responds with auth
curl -s -H "Authorization: Bearer $API_KEY" http://localhost:3000/api/v1/profile
# Expected: JSON with user data

# Can create a discussion
curl -s -X POST http://localhost:3000/api/v1/discussions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"discussion":{"title":"Test","group_id":GROUP_ID,"description":"Test thread"}}'
# Expected: 201 with discussion JSON
```
