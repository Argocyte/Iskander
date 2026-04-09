---
name: iskander-first-boot
description: Build the first-boot wizard that configures a fresh Iskander node. Use this skill when the user mentions first boot, setup wizard, node setup, initial configuration, cooperative bootstrapping, or deploying Iskander on new hardware. Also use when working on the docker-compose MVP configuration or the interactive CLI installer.
---

# First-Boot Wizard

Interactive CLI that configures a fresh Iskander cooperative node from zero to working system.

## What It Collects

| Prompt | Used For |
|--------|----------|
| "What's your cooperative's name?" | Loomio group name, SOUL.md templates |
| "Name the founding members (comma-separated)" | Loomio user invites |
| (auto-generated) | JWT secret, Redis password, PostgreSQL password |

## Step 1: Write docker-compose.mvp.yml

Create `src/IskanderOS/docker-compose.mvp.yml` with 6 services:

| Service | Image | Port | Depends On |
|---------|-------|------|------------|
| db | postgres:16 | 5432 | — |
| redis | redis:7 | 6379 | — |
| loomio | loomio/loomio:latest | 3000 | db, redis |
| ollama | ollama/ollama:latest | 11434 | — |
| openclaw | node:20 | 3100 | ollama |
| ipfs | ipfs/kubo:latest | 5001 | — |

Shared PostgreSQL for Loomio + decision-recorder. Use named volumes for persistence.

## Step 2: Write first-boot.py

Create `src/IskanderOS/scripts/first-boot.py` using `click` library.

Flow:
1. Collect cooperative name and founding members
2. Generate secrets: `secrets.token_hex(64)` for each
3. Write `.env` files for each service
4. Write `openclaw.json` with Ollama + web channel config
5. Template SOUL.md files with cooperative name
6. Run: `docker compose -f docker-compose.mvp.yml up -d db redis`
7. Wait for DB ready: poll `pg_isready`
8. Run: `docker compose -f docker-compose.mvp.yml up -d loomio`
9. Wait for Loomio ready: poll `http://localhost:3000/health`
10. Create Loomio admin + group via API (use Rails console or API)
11. Generate API key for Clerk agent
12. Run: `docker compose -f docker-compose.mvp.yml up -d ollama openclaw ipfs`
13. Run: `openclaw onboard --flow non-interactive`
14. Create Clerk + Steward agents
15. Inject Iskander chat widget into Loomio
16. Open browser: `http://localhost:3000`
17. Print: "Your cooperative is ready. Chat with your Clerk in Loomio."

## Step 3: Chat Widget Injection

The first-boot script copies the Iskander chat widget files into Loomio's public assets directory (Docker volume mount) and adds a script tag to load `widget.js`.

## Files to Create

| File | Purpose |
|------|---------|
| `src/IskanderOS/docker-compose.mvp.yml` | MVP service orchestration |
| `src/IskanderOS/scripts/first-boot.py` | Interactive setup CLI |
| `src/IskanderOS/scripts/requirements.txt` | click, httpx, rich |

## Verification

Test on a clean Ubuntu 24.04 system:

1. `python3 scripts/first-boot.py` completes without errors
2. `docker compose ps` shows 6 services running
3. Loomio loads at `http://localhost:3000`
4. Iskander chat widget visible in Loomio (bottom-right)
5. Clerk responds to "Hello" via chat widget
6. Total setup time < 10 minutes (excluding Docker image pulls)
