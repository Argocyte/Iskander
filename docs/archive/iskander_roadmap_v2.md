# Iskander OS — Strategic Roadmap v2
## Phases 12–15: ZK Democracy, App Orchestration, Matrix Federation, Inter-Coop Arbitration

> **Scope:** Architectural roadmap only. No code generation. Each phase lists patterns, dependencies, stub files, database migrations, and docker services required for sequential implementation.
>
> **Prerequisite:** Phases 1–11 complete (FastAPI sovereign node, CoopIdentity ERC-4973, InternalPayroll, Glass Box Protocol, Agent Library, AJD Spawner, pgvector democratic memory, ActivityPub stubs, Ubuntu ISO).

---

## Implementation Order

```
Phase 12 (ZK Democracy) ──┐
                           ├──► Phase 14 (Matrix & AP Federation) ──► Phase 15 (Arbitration)
Phase 13 (App Store)  ─────┘
```

Phases 12 and 13 have no cross-dependencies and can be developed in parallel. Phase 14 depends on both (Matrix notifications for polls and app deployments). Phase 15 depends on Phase 14 (federated jury selection via enriched ActivityPub; jury deliberation via Matrix rooms).

---

## Phase 12: Zero-Knowledge Democracy & Privacy

### Objective

Protect voter privacy and care-work dignity. On-chain governance results remain mathematically verifiable while *who voted for what* stays permanently hidden. Care-work quantification produces auditable scores without logging sensitive human interactions.

### 12A — MACI Secret Ballots

**Pattern:** MACI (Minimum Anti-Collusion Infrastructure) runs as an on-chain ZK voting protocol. Iskander wraps it with a Python service layer bridging the existing governance router (`/governance/vote`) and spawner voting (`/agents/vote`) to MACI's signup → publish → tally flow. A Node.js coordinator sidecar handles the MACI processing key and runs snarkjs tallying off-chain, posting results on-chain.

**Integration points:**
- `backend/routers/governance.py` — when a proposal is marked `secret_ballot=True`, votes route through MACI instead of the plaintext `VoteRequest.approved` field
- `backend/routers/spawner.py` — AJD votes gain the same optional MACI path
- `backend/agents/state.py` — `GovernanceState` and spawner state gain `maci_poll_id: str | None` field
- Existing HITL breakpoint at `human_vote` remains; graph resumption reads MACI tally result instead of plaintext votes

**HITL & Glass Box:**
- Creating a MACI poll → `AgentAction` with `ethical_impact=HIGH`
- All MACI state transitions (signup, vote publish, tally finalization) logged as `AgentAction` records
- Coordinator key held by system, not any individual

#### New Files

| File | Purpose |
|------|---------|
| `backend/zk/__init__.py` | Package init |
| `backend/zk/maci_wrapper.py` | Python wrapper around MACI CLI — signup, publish vote, tally. Calls Node sidecar via HTTP |
| `backend/routers/zk_voting.py` | FastAPI router: `POST /zk/polls/create`, `POST /zk/polls/{poll_id}/vote`, `GET /zk/polls/{poll_id}/tally` |
| `backend/schemas/zk.py` | Pydantic models: `MACIPollCreate`, `MACIVoteRequest`, `MACITallyResult` |
| `contracts/src/IskanderMACI.sol` | Thin wrapper deploying MACI instances per poll; binds to `CoopIdentity` for voter eligibility (checks SBT balance) |
| `contracts/test/IskanderMACI.t.sol` | Foundry tests |
| `infra/maci-coordinator/Dockerfile` | Node.js sidecar for MACI tallying |
| `infra/maci-coordinator/index.js` | Express server exposing `/tally` endpoint running snarkjs |
| `infra/maci-coordinator/package.json` | Node dependencies |
| `infra/zk-circuits/` | Directory for MACI ceremony artifacts (trusted setup `.zkey` files, `.wasm` verifiers) — downloaded, not generated |

#### Database Migration

```sql
CREATE TABLE IF NOT EXISTS maci_polls (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    poll_id         INTEGER NOT NULL,
    proposal_type   TEXT NOT NULL CHECK (proposal_type IN ('governance', 'ajd', 'arbitration')),
    reference_id    UUID NOT NULL,
    coordinator_key TEXT NOT NULL,
    signup_deadline TIMESTAMPTZ NOT NULL,
    voting_deadline TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'signup'
                    CHECK (status IN ('signup', 'voting', 'tallying', 'finalized')),
    tally_result    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS maci_signups (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    poll_id         UUID NOT NULL REFERENCES maci_polls(id),
    member_did      TEXT NOT NULL,
    state_index     INTEGER NOT NULL,
    signed_up_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Docker Service

```yaml
maci-coordinator:
    build: ./infra/maci-coordinator
    container_name: iskander_maci
    restart: unless-stopped
    environment:
      MACI_PRIVATE_KEY: ${MACI_COORDINATOR_KEY:-}
      CIRCUITS_DIR: /app/circuits
    volumes:
      - ./infra/zk-circuits:/app/circuits:ro
    ports:
      - "3100:3100"
    depends_on:
      - anvil
```

#### External Dependencies

- **npm:** `maci-contracts`, `maci-cli`, `maci-crypto`, `maci-domainobjs`
- **Python:** `py_ecc==7.0.1`, `poseidon-py`

---

### 12B — ZK-SNARKs for Steward Care Work Privacy

**Pattern:** A circom circuit proves "this member's care score equals `base_hours × multiplier` and the multiplier is within the valid range [1.2, 1.8]" without revealing the raw multiplier keyword or description excerpt that derived it. Proof verified locally via snarkjs or optionally on-chain via auto-generated Groth16 verifier.

**Integration points:**
- `backend/agents/library/steward.py` — the `quantify_care_work` node (currently logs multiplier and base hours in `AgentAction.payload`). When ZK mode is enabled, payload contains only the ZK proof and final `care_score`, not the multiplier source or description excerpt
- `backend/agents/state.py` — `ContributionStateV2` gains `zk_proof: dict | None` field

**HITL & Glass Box:**
- Care work quantification with ZK mode active → `ethical_impact=MEDIUM` (actively protecting privacy)
- Glass Box log records: "ZK proof generated, care_score=X, proof verified=true" — no multiplier source leaked

#### New Files

| File | Purpose |
|------|---------|
| `infra/zk-circuits/care_work_multiplier.circom` | Circom circuit: private inputs (multiplier, description_hash), public inputs (base_hours, care_score). Proves valid range |
| `backend/zk/care_proof.py` | Generates and verifies ZK proofs for care work. Calls snarkjs via the maci-coordinator sidecar (shared Node container) |
| `contracts/src/CareWorkVerifier.sol` | On-chain Groth16 verifier (auto-generated by snarkjs). Optional — verification can also be local-only |
| `contracts/test/CareWorkVerifier.t.sol` | Foundry tests |

#### Database Migration

```sql
ALTER TABLE contributions ADD COLUMN zk_proof JSONB;
ALTER TABLE contributions ADD COLUMN zk_verified BOOLEAN DEFAULT FALSE;
```

#### Config Additions (`backend/config.py`)

```python
maci_coordinator_url: str = "http://localhost:3100"
zk_circuits_dir: str = "/app/infra/zk-circuits"
zk_care_work_enabled: bool = False
```

---

## Phase 13: Democratic App Store & Container Orchestration

### Objective

Enable Iskander to host the coop's actual software (Nextcloud, Gitea, Loomio, Penpot) through a governance-gated container orchestration layer. Members request apps via natural language; the AI proposes vetted FOSS alternatives; a democratic vote approves deployment; the system automatically provisions the container with reverse-proxy routing and admin credentials.

### Architectural Pattern

A new **Provisioner Agent** follows the existing AJD spawner pattern (`spawner_graph.py`): propose → HITL vote → deploy → register. Docker SDK for Python manages container lifecycle. Traefik handles automatic reverse-proxy routing via Docker labels. A curated YAML catalog restricts deployable images to vetted FOSS software.

**Integration points:**
- `backend/agents/spawner/spawner_graph.py` — pattern template (propose → HITL vote → compile → deploy)
- `backend/agents/spawner/node_registry.py` — gains 7 new provisioner nodes
- `backend/agents/spawner/ajd_schema.py` — `AJDPermission` enum gains `CONTAINER_DEPLOY`
- Docker socket mounted read-write into backend container (or host process)

**HITL & Glass Box:**
- `deploy_container` → `ethical_impact=HIGH` (external side-effect: Docker container creation)
- HITL breakpoint at `human_vote_app` — graph suspends, members vote via `/apps/{app_id}/vote`
- Container removal also requires HITL approval
- Every Docker API call (pull, create, start, stop, remove) wrapped in `AgentAction` record

### LangGraph — Provisioner Agent

```
parse_app_request → search_app_catalog → propose_deployment → [HITL: human_vote_app]
    → deploy_container → configure_proxy → generate_credentials → END
```

#### New Files

| File | Purpose |
|------|---------|
| `backend/appstore/__init__.py` | Package init |
| `backend/appstore/catalog.py` | App catalog logic — loads and queries `catalog.yaml` |
| `backend/appstore/catalog.yaml` | Curated FOSS app catalog: Nextcloud, OnlyOffice, Gitea, Loomio, OpenProject, Penpot, Focalboard, Ghost |
| `backend/appstore/docker_manager.py` | Docker SDK wrapper: `pull_image()`, `create_container()`, `stop_container()`, `remove_container()`, `get_container_status()`. All methods Glass Box logged |
| `backend/agents/library/provisioner.py` | Provisioner LangGraph agent — 7 nodes |
| `backend/agents/library/prompt_provisioner.txt` | Agent persona prompt |
| `backend/routers/appstore.py` | FastAPI router: `POST /apps/request`, `GET /apps`, `POST /apps/{app_id}/vote`, `DELETE /apps/{app_id}` |
| `backend/schemas/appstore.py` | Pydantic models: `AppRequest`, `AppCatalogEntry`, `DeploymentSpec`, `AppStatus` |

#### State Type (`backend/agents/state.py`)

```python
class ProvisionerState(AgentState):
    app_request: dict[str, Any] | None
    catalog_matches: list[dict[str, Any]]
    deployment_spec: dict[str, Any] | None
    container_id: str | None
    proxy_configured: bool
    admin_credentials: dict[str, Any] | None
    requires_human_token: bool
```

#### Database Migration

```sql
CREATE TABLE IF NOT EXISTS app_deployments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    app_name        TEXT NOT NULL,
    docker_image    TEXT NOT NULL,
    container_id    TEXT,
    container_name  TEXT NOT NULL UNIQUE,
    port_mapping    JSONB,
    traefik_rule    TEXT,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed', 'approved', 'pulling', 'running',
                                      'stopped', 'failed', 'removed')),
    requested_by    TEXT NOT NULL,
    approved_at     TIMESTAMPTZ,
    resource_limits JSONB,
    admin_creds     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app_votes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id   UUID NOT NULL REFERENCES app_deployments(id),
    voter_did       TEXT NOT NULL,
    approved        BOOLEAN NOT NULL,
    reason          TEXT,
    voted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Docker Services

```yaml
traefik:
    image: traefik:v3.0
    container_name: iskander_traefik
    restart: unless-stopped
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
    ports:
      - "80:80"
      - "8180:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

Backend service gains volume: `/var/run/docker.sock:/var/run/docker.sock`

#### External Dependencies

- **Python:** `docker==7.1.0`
- **Docker images:** `traefik:v3.0` (plus member-voted app images at runtime)

#### Config Additions (`backend/config.py`)

```python
docker_socket_url: str = "unix:///var/run/docker.sock"
traefik_network: str = "iskander_apps"
app_domain_suffix: str = "iskander.local"
```

---

## Phase 14: Real-Time Federation (Matrix & ActivityPub)

### Objective

Upgrade from broadcast-only ActivityPub to real-time encrypted collaboration. Members interact with Iskander agents from standard Matrix clients (Element, FluffyChat) on their phones — not just the Streamlit dashboard. Complete the ActivityPub implementation (HTTP Signatures, inbox processing, outbox persistence) for full inter-coop server-to-server federation.

---

### 14A — Embedded Dendrite Homeserver

**Pattern:** Dendrite (lightweight Matrix homeserver in Go) runs as a Docker service. Iskander agents register as Matrix Application Service (appservice) bots. Members use any Matrix client. The backend communicates with Dendrite via the Matrix Client-Server (CS) API.

**Integration points:**
- ActivityPub (`federation.py`) handles inter-coop S2S messaging — not replaced
- Matrix handles intra-coop real-time chat — complementary channel
- Governance router gains Matrix notification path for HITL approval requests (members approve from phones)

#### New Files

| File | Purpose |
|------|---------|
| `backend/matrix/__init__.py` | Package init |
| `backend/matrix/client.py` | Async Matrix client wrapper using `matrix-nio`. Methods: `send_message()`, `create_room()`, `invite_user()`, `register_bot()`, `listen_for_commands()`. Singleton pattern matching `pgvector_store.py` |
| `backend/matrix/appservice.py` | Matrix Application Service registration and event handler. Routes incoming Matrix messages to appropriate agent graph |
| `backend/matrix/bridge.py` | Bridges agent outputs to Matrix rooms. Each agent type gets a dedicated bot user: `@secretary:iskander.local`, `@treasurer:iskander.local`, `@steward:iskander.local` |
| `backend/routers/matrix_admin.py` | FastAPI router: `POST /matrix/rooms`, `GET /matrix/rooms`, `POST /matrix/bridge/{agent_id}`, `GET /matrix/status` |
| `backend/schemas/matrix.py` | Pydantic models: `MatrixRoom`, `MatrixMessage`, `BridgeConfig` |
| `infra/dendrite/dendrite.yaml` | Dendrite config — points to same PostgreSQL instance (separate `iskander_matrix` database) |
| `infra/dendrite/appservice-iskander.yaml` | Application service registration for Iskander agent bots |

#### LangGraph Modifications

- `backend/agents/spawner/node_registry.py` — add `send_matrix_notification` node (generic, reusable)
- `backend/agents/library/secretary.py` — `prepare_broadcast` node gains Matrix room message path alongside ActivityPub
- Matrix appservice command handler routes `!propose`, `!vote yes`, `!status` to existing router endpoints internally

#### Database Migration

```sql
CREATE DATABASE iskander_matrix;  -- Dendrite manages its own schema

-- Iskander tracking tables:
CREATE TABLE IF NOT EXISTS matrix_room_bridges (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id     TEXT NOT NULL,
    room_alias  TEXT,
    agent_id    TEXT,
    room_type   TEXT NOT NULL CHECK (room_type IN
                    ('general', 'governance', 'treasury', 'steward', 'secretary')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matrix_events_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id        TEXT NOT NULL,
    room_id         TEXT NOT NULL,
    sender          TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    content         JSONB,
    agent_action_id UUID REFERENCES agent_actions(id),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Docker Service

```yaml
dendrite:
    image: matrixdotorg/dendrite-monolith:latest
    container_name: iskander_dendrite
    restart: unless-stopped
    volumes:
      - ./infra/dendrite/dendrite.yaml:/etc/dendrite/dendrite.yaml:ro
      - ./infra/dendrite/appservice-iskander.yaml:/etc/dendrite/appservice-iskander.yaml:ro
      - dendrite_data:/var/dendrite
      - dendrite_media:/var/dendrite/media
    ports:
      - "8448:8448"  # Matrix S2S federation
      - "8008:8008"  # Matrix CS API
    depends_on:
      - postgres
```

Add volumes: `dendrite_data:`, `dendrite_media:`

#### External Dependencies

- **Python:** `matrix-nio==0.24.0`, `aiofiles`
- **Docker image:** `matrixdotorg/dendrite-monolith:latest`

---

### 14B — ActivityPub Completion

**Pattern:** Fill the existing TODOs in `backend/routers/federation.py`. Extract federation logic into a dedicated `backend/federation/` package. Implement HTTP Signature signing/verification, inbox activity processing, and outbox persistence.

#### New Files

| File | Purpose |
|------|---------|
| `backend/federation/__init__.py` | Package init |
| `backend/federation/http_signatures.py` | HTTP Signature signing and verification (RFC 9421). Uses existing `cryptography` dependency |
| `backend/federation/inbox_processor.py` | Processes inbound activities by type: Follow (add follower), Announce (reshare), Create (store note), plus custom Iskander types |
| `backend/federation/outbox_store.py` | Persists outbound activities to Postgres. Fills the currently-empty outbox endpoint |

#### Database Migration

```sql
CREATE TABLE IF NOT EXISTS federation_inbox (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id   TEXT NOT NULL UNIQUE,
    activity_type TEXT NOT NULL,
    actor_iri     TEXT NOT NULL,
    raw_activity  JSONB NOT NULL,
    processed     BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS federation_outbox (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id   TEXT NOT NULL UNIQUE,
    activity_type TEXT NOT NULL,
    raw_activity  JSONB NOT NULL,
    delivered     BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS federation_followers (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    local_handle TEXT NOT NULL,
    follower_iri TEXT NOT NULL,
    accepted     BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(local_handle, follower_iri)
);
```

#### HITL & Glass Box (Phase 14 Combined)

- All Matrix messages sent by agent bots → `AgentAction` with `ethical_impact=MEDIUM`
- Creating a Matrix room or inviting users → `ethical_impact=HIGH`, requires HITL
- Matrix command handler (`!vote`, `!propose`) calls same router endpoints as Streamlit — existing HITL breakpoints apply transparently
- ActivityPub outbound delivery → `ethical_impact=HIGH`, logged per Glass Box

#### Config Additions (`backend/config.py`)

```python
matrix_homeserver_url: str = "http://localhost:8008"
matrix_domain: str = "iskander.local"
matrix_appservice_token: str = ""
matrix_bot_prefix: str = "@iskander_"
```

---

## Phase 15: Inter-Coop Arbitration (The Solidarity Court)

### Objective

When `IskanderEscrow.sol` is used for inter-coop trade and a delivery dispute arises that the local Conflict Resolver agents cannot resolve, escalate to a federated jury of sister cooperatives. Bad-faith actors face SBT reputation slashing on their `CoopIdentity` token. The Arbitrator Agent never renders a verdict autonomously — it facilitates the human jury process.

### Architectural Pattern

Three components:
1. **`IskanderEscrow.sol`** — holds funds for inter-coop trade with locked release
2. **Federated Jury Protocol** — ActivityPub-based jury selection from sister coops (inspired by Kleros/Aragon Court but federated, not blockchain-only)
3. **SBT Reputation Slashing** — `CoopIdentity.sol` gains `trustScore` field with `slashTrust()` / `restoreTrust()` methods

**Integration points:**
- `contracts/src/CoopIdentity.sol` — `MemberRecord` gains `uint16 trustScore` (default 1000, range 0–1000). New functions `slashTrust()`, `restoreTrust()` callable by escrow contract or steward
- `backend/routers/federation.py` (via 14B's inbox/outbox) — custom ActivityPub types: `iskander:ArbitrationRequest`, `iskander:JuryNomination`, `iskander:Verdict`
- Existing governance router pattern reused for arbitration case management
- Matrix rooms (Phase 14A) used for asynchronous jury deliberation

### LangGraph — Arbitrator Agent

```
receive_dispute → assess_jurisdiction → request_jury_federation
    → [HITL: human_jury_deliberation] → record_verdict → execute_remedy → END
```

Conditional edge: if `assess_jurisdiction` determines intra-coop dispute, routes to existing governance process instead of federated jury.

### Federated Jury Selection Protocol

1. Complainant's coop sends `iskander:ArbitrationRequest` via ActivityPub outbox to 5+ sister coops
2. Sister coops' inboxes receive request; their governance process selects 1–2 volunteer jurors
3. Sister coops respond with `iskander:JuryNomination` activity
4. 3–5 jurors randomly selected (deterministic randomness: `keccak256(blockHash, caseId)`)
5. Jurors receive evidence via IPFS CIDs (not raw data — privacy preserved)
6. Jury deliberates asynchronously via Matrix room (Phase 14A)
7. Verdict sent as `iskander:Verdict` activity and recorded on-chain via `ArbitrationRegistry.sol`

#### New Files — Solidity

| File | Purpose |
|------|---------|
| `contracts/src/IskanderEscrow.sol` | Escrow for inter-coop trade. `createEscrow()`, `confirmDelivery()`, `dispute()`, `executeVerdict()`. Uses `ReentrancyGuard`. References `CoopIdentity` for membership verification |
| `contracts/src/ArbitrationRegistry.sol` | On-chain verdict records. Stores case hashes, verdicts, trust score adjustments. Lightweight — most logic off-chain |
| `contracts/test/IskanderEscrow.t.sol` | Foundry tests |
| `contracts/test/ArbitrationRegistry.t.sol` | Foundry tests |

#### New Files — Python

| File | Purpose |
|------|---------|
| `backend/agents/library/arbitrator.py` | Arbitrator Agent LangGraph — 6 nodes |
| `backend/agents/library/prompt_arbitrator.txt` | Agent persona: impartial, procedural, references cooperative law principles |
| `backend/routers/arbitration.py` | FastAPI router: `POST /arbitration/disputes`, `GET /arbitration/disputes/{id}`, `POST /arbitration/disputes/{id}/evidence`, `POST /arbitration/disputes/{id}/verdict`, `GET /arbitration/disputes/{id}/jury` |
| `backend/routers/escrow.py` | FastAPI router: `POST /escrow/create`, `GET /escrow/{id}`, `POST /escrow/{id}/release`, `POST /escrow/{id}/dispute` |
| `backend/schemas/arbitration.py` | Pydantic models: `DisputeCreate`, `DisputeStatus`, `EvidenceSubmission`, `Verdict`, `JuryMember`, `EscrowCreate`, `EscrowStatus` |
| `backend/federation/arbitration_protocol.py` | ActivityPub extensions: serializes/deserializes custom activity types for jury selection |

#### Modifications to Existing Contracts

**`contracts/src/CoopIdentity.sol`:**
- `MemberRecord` struct gains: `uint16 trustScore` (default 1000)
- New function: `slashTrust(address member, uint16 penalty, bytes32 caseHash)` — callable by steward or `ArbitrationRegistry`
- New function: `restoreTrust(address member, uint16 restoration, bytes32 caseHash)` — rehabilitation path
- New event: `TrustSlashed(address indexed member, uint16 penalty, uint16 newScore, bytes32 caseHash)`
- New event: `TrustRestored(address indexed member, uint16 restoration, uint16 newScore, bytes32 caseHash)`

#### State Type (`backend/agents/state.py`)

```python
class ArbitrationState(AgentState):
    dispute: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    jury_pool: list[dict[str, Any]]
    jury_selected: list[dict[str, Any]]
    verdict: dict[str, Any] | None
    escrow_id: str | None
    remedy_executed: bool
    requires_human_token: bool
```

#### Database Migration

```sql
CREATE TABLE IF NOT EXISTS escrow_contracts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    escrow_address  TEXT NOT NULL,
    buyer_coop_did  TEXT NOT NULL,
    seller_coop_did TEXT NOT NULL,
    token_address   TEXT NOT NULL,
    amount_wei      NUMERIC(30, 0) NOT NULL,
    terms_ipfs_cid  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'released', 'disputed', 'arbitrated', 'expired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS arbitration_cases (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    escrow_id         UUID REFERENCES escrow_contracts(id),
    complainant_did   TEXT NOT NULL,
    respondent_did    TEXT NOT NULL,
    description       TEXT NOT NULL,
    evidence_cids     JSONB DEFAULT '[]',
    jury_members      JSONB DEFAULT '[]',
    jury_source_coops JSONB DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'filed'
                      CHECK (status IN ('filed', 'jury_selection', 'deliberation',
                                        'verdict_rendered', 'remedy_executed', 'appealed')),
    verdict           JSONB,
    arbitration_tx    TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trust_score_history (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    member_did      TEXT NOT NULL,
    old_score       INTEGER NOT NULL,
    new_score       INTEGER NOT NULL,
    reason          TEXT NOT NULL,
    case_id         UUID REFERENCES arbitration_cases(id),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### HITL & Glass Box

- `receive_dispute` → `ethical_impact=HIGH` (triggers cross-coop process)
- `request_jury_federation` → `ethical_impact=HIGH` (sends ActivityPub messages to external coops)
- `human_jury_deliberation` → **mandatory HITL breakpoint** — jury (humans from sister coops) deliberate via Matrix rooms or ActivityPub
- `execute_remedy` → `ethical_impact=HIGH` (on-chain escrow release + potential trust slashing)
- Every trust score change → `AgentAction` with `ethical_impact=HIGH`
- **The Arbitrator Agent never renders a verdict autonomously.** It facilitates the process, presents evidence, and records the human jury's decision

#### Config Additions (`backend/config.py`)

```python
arbitration_jury_size: int = 5
arbitration_timeout_days: int = 30
escrow_default_timeout_days: int = 90
trust_score_default: int = 1000
trust_score_min: int = 0
```

---

## Appendix: Complete New File Index

| Phase | File | Type |
|-------|------|------|
| 12 | `backend/zk/__init__.py` | Python |
| 12 | `backend/zk/maci_wrapper.py` | Python |
| 12 | `backend/zk/care_proof.py` | Python |
| 12 | `backend/routers/zk_voting.py` | Python |
| 12 | `backend/schemas/zk.py` | Python |
| 12 | `contracts/src/IskanderMACI.sol` | Solidity |
| 12 | `contracts/src/CareWorkVerifier.sol` | Solidity |
| 12 | `contracts/test/IskanderMACI.t.sol` | Solidity |
| 12 | `contracts/test/CareWorkVerifier.t.sol` | Solidity |
| 12 | `infra/maci-coordinator/Dockerfile` | Docker |
| 12 | `infra/maci-coordinator/index.js` | Node.js |
| 12 | `infra/maci-coordinator/package.json` | Node.js |
| 12 | `infra/zk-circuits/care_work_multiplier.circom` | Circom |
| 13 | `backend/appstore/__init__.py` | Python |
| 13 | `backend/appstore/catalog.py` | Python |
| 13 | `backend/appstore/catalog.yaml` | YAML |
| 13 | `backend/appstore/docker_manager.py` | Python |
| 13 | `backend/agents/library/provisioner.py` | Python |
| 13 | `backend/agents/library/prompt_provisioner.txt` | Text |
| 13 | `backend/routers/appstore.py` | Python |
| 13 | `backend/schemas/appstore.py` | Python |
| 14 | `backend/matrix/__init__.py` | Python |
| 14 | `backend/matrix/client.py` | Python |
| 14 | `backend/matrix/appservice.py` | Python |
| 14 | `backend/matrix/bridge.py` | Python |
| 14 | `backend/routers/matrix_admin.py` | Python |
| 14 | `backend/schemas/matrix.py` | Python |
| 14 | `backend/federation/__init__.py` | Python |
| 14 | `backend/federation/http_signatures.py` | Python |
| 14 | `backend/federation/inbox_processor.py` | Python |
| 14 | `backend/federation/outbox_store.py` | Python |
| 14 | `infra/dendrite/dendrite.yaml` | YAML |
| 14 | `infra/dendrite/appservice-iskander.yaml` | YAML |
| 15 | `contracts/src/IskanderEscrow.sol` | Solidity |
| 15 | `contracts/src/ArbitrationRegistry.sol` | Solidity |
| 15 | `contracts/test/IskanderEscrow.t.sol` | Solidity |
| 15 | `contracts/test/ArbitrationRegistry.t.sol` | Solidity |
| 15 | `backend/agents/library/arbitrator.py` | Python |
| 15 | `backend/agents/library/prompt_arbitrator.txt` | Text |
| 15 | `backend/routers/arbitration.py` | Python |
| 15 | `backend/routers/escrow.py` | Python |
| 15 | `backend/schemas/arbitration.py` | Python |
| 15 | `backend/federation/arbitration_protocol.py` | Python |

## Appendix: Modified Existing Files (Per Phase)

| Phase | File | Change |
|-------|------|--------|
| 12 | `backend/agents/state.py` | Add `maci_poll_id` to `GovernanceState`; add `zk_proof` to `ContributionStateV2` |
| 12 | `backend/routers/governance.py` | Conditional MACI path when `secret_ballot=True` |
| 12 | `backend/routers/spawner.py` | Optional MACI path for AJD votes |
| 12 | `backend/agents/library/steward.py` | ZK proof generation in `quantify_care_work` node |
| 12 | `backend/config.py` | MACI/ZK config fields |
| 12 | `backend/main.py` | Mount `zk_voting` router |
| 12 | `docker-compose.yml` | Add `maci-coordinator` service |
| 12 | `infra/init.sql` | Add `maci_polls`, `maci_signups` tables |
| 13 | `backend/agents/state.py` | Add `ProvisionerState` |
| 13 | `backend/agents/spawner/node_registry.py` | Register 7 provisioner nodes |
| 13 | `backend/agents/spawner/ajd_schema.py` | Add `CONTAINER_DEPLOY` permission |
| 13 | `backend/config.py` | Docker/Traefik config fields |
| 13 | `backend/main.py` | Mount `appstore` router |
| 13 | `docker-compose.yml` | Add `traefik` service; mount Docker socket to backend |
| 13 | `infra/init.sql` | Add `app_deployments`, `app_votes` tables |
| 14 | `backend/agents/library/secretary.py` | `prepare_broadcast` gains Matrix room message path |
| 14 | `backend/agents/spawner/node_registry.py` | Add `send_matrix_notification` node |
| 14 | `backend/routers/federation.py` | Refactor to use `backend/federation/` package |
| 14 | `backend/config.py` | Matrix config fields |
| 14 | `backend/main.py` | Mount `matrix_admin` router |
| 14 | `docker-compose.yml` | Add `dendrite` service + volumes |
| 14 | `infra/init.sql` | Add federation + matrix tables |
| 15 | `contracts/src/CoopIdentity.sol` | Add `trustScore`, `slashTrust()`, `restoreTrust()`, events |
| 15 | `backend/agents/state.py` | Add `ArbitrationState` |
| 15 | `backend/config.py` | Arbitration config fields |
| 15 | `backend/main.py` | Mount `arbitration`, `escrow` routers |
| 15 | `infra/init.sql` | Add `escrow_contracts`, `arbitration_cases`, `trust_score_history` tables |
| 15 | `backend/requirements.txt` | All new Python deps across phases |

---

## Phase 16: Hardware-Software Symbiosis & OS Resilience

### Objective

Make the Iskander node robust on commodity hardware (Raspberry Pi, NUC, repurposed laptops) with limited RAM, slow storage, and intermittent power. Ensure LLM inference does not block HTTP request handling, that heavy ZK-crypto operations push status updates to the UI asynchronously, and that the OS configuration extends SSD longevity under a write-heavy workload (Postgres WAL, Docker layers, IPFS blocks).

---

### 16A — LLM Concurrency Queue

**Problem:** Ollama on a CPU-only node serialises inference requests but the FastAPI event loop still receives concurrent HTTP requests. An LangGraph graph that calls Ollama (10–60 s per invocation) blocks all other agents in the same process.

**Pattern:** `AsyncAgentQueue` wraps every `agent_graph.invoke()` call. It is an `asyncio.Queue`-backed middleware class that:
- Accepts tasks and returns a `task_id` immediately (HTTP 202).
- Enforces a maximum queue depth (50). Requests beyond this get HTTP 503 with `{"error": "queue_full", "queue_length": 50}`.
- Runs a single background `asyncio.Task` worker that pulls from the queue and calls `graph.invoke()` sequentially (serialising Ollama calls).
- Publishes status events (queued → running → complete/error) to `WebSocketNotifier` (see 16B).
- Is thread-safe: each LangGraph `invoke()` is wrapped in `asyncio.to_thread()` so blocking checkpoints do not stall the event loop.

**Integration points:**
- All agent graph routers (`/governance`, `/treasury`, `/steward`, `/appstore`, `/arbitration`) gain an optional `?async=true` query parameter. When set, the call is queued and the response is `{"task_id": "...", "queue_position": N, "status_url": "/tasks/{task_id}"}`.
- `GET /tasks/{task_id}` returns current status and result when complete.
- Synchronous path (default) unchanged — existing tests unaffected.

#### New Files

| File | Purpose |
|------|---------|
| `backend/core/__init__.py` | Package init |
| `backend/core/llm_queue_manager.py` | `AsyncAgentQueue` class. Singleton. `enqueue(graph, state, config) → TaskHandle`. Internal `_worker()` coroutine. `get_status(task_id)` and `get_result(task_id)` methods. |
| `backend/routers/tasks.py` | `GET /tasks/{task_id}` — status/result polling endpoint. Consumed by Streamlit and Matrix bot. |

#### Modifications to Existing Files

| File | Change |
|------|--------|
| `backend/main.py` | Mount `tasks` router; start queue worker on `startup` event |
| `backend/config.py` | Add `agent_queue_max_depth: int = 50`, `agent_queue_workers: int = 1` |

---

### 16B — Asynchronous WebSocket Status Updates

**Problem:** ZK proof generation (MACI tally), jury federation (ActivityPub round-trips), and Docker image pulls are multi-second operations. The Streamlit UI currently has no feedback — users see a spinner until the synchronous call resolves (or times out).

**Pattern:** `WebSocketNotifier` is a FastAPI WebSocket broadcast bus. Agent nodes push status events; Streamlit connects over `ws://iskander.local:8000/ws/events` to receive a real-time JSON stream. The Matrix bridge also listens on the internal event bus so that agents can echo progress into Matrix rooms without a separate HTTP call.

**Event schema:**
```json
{
  "task_id": "uuid",
  "agent_id": "arbitrator-agent-v1",
  "event": "node_entered | node_exited | hitl_required | task_complete | error",
  "node": "request_jury_federation",
  "timestamp": "ISO-8601",
  "payload": {}
}
```

**Integration points:**
- `AsyncAgentQueue._worker()` emits `task_complete` / `error` events.
- High-impact LangGraph nodes (`request_jury_federation`, `execute_remedy`, `deploy_container`, `generate_tally_proof`) emit `node_entered` / `node_exited` events via `WebSocketNotifier.broadcast()`.
- `human_jury_deliberation` HITL node emits `hitl_required` — Streamlit shows a persistent banner; Matrix bridge sends a message to the governance room.
- `AgentBridge.send_matrix_notification_node` subscribes to the internal bus and forwards `hitl_required` events to Matrix automatically.

#### New Files

| File | Purpose |
|------|---------|
| `backend/api/__init__.py` | Package init |
| `backend/api/websocket_notifier.py` | `WebSocketNotifier` singleton. `broadcast(event_dict)` fan-out to all connected clients. FastAPI `WebSocket` endpoint at `/ws/events`. Internal `asyncio.Queue`-backed pub/sub bus used by the Matrix bridge without opening a real WebSocket. |

#### Modifications to Existing Files

| File | Change |
|------|--------|
| `backend/main.py` | Mount WebSocket route from `websocket_notifier` |
| `backend/agents/spawner/node_registry.py` | Register `broadcast_ws_event` generic node that calls `WebSocketNotifier.broadcast()` |

---

### 16C — Docker Log Rotation (Disk Longevity)

**Problem:** On a 64 GB SSD, unbounded Docker container logs from Ollama inference and Dendrite federation will consume the entire disk within weeks.

**Pattern:** Add `logging` config to every service in `docker-compose.yml`. Use the built-in `json-file` driver with `max-size: "10m"` and `max-file: "3"` (maximum 30 MB per service, ~210 MB total across 7 services).

#### Modifications to Existing Files

| File | Change |
|------|--------|
| `docker-compose.yml` | Add `logging: driver: "json-file", options: {max-size: "10m", max-file: "3"}` to all services |

---

### 16D — PostgreSQL I/O Optimisation

**Problem:** PostgreSQL's default `synchronous_commit = on` and `wal_writer_delay = 200ms` produce excessive write amplification on SSDs. The Iskander ledger (agent_actions, contributions, federation_inbox) is append-only and loss-tolerant for non-financial records — a 1-second commit delay is acceptable for audit logs but NOT for `pending_transactions` or `zk_vote_tallies`.

**Pattern:** A post-install script patches `postgresql.conf` with tuned values and restarts the service. Financial tables (`pending_transactions`, `zk_vote_tallies`) use a dedicated synchronous tablespace (future: `synchronous_commit = on` per-session override). Non-financial tables use `synchronous_commit = off` via a Postgres role.

#### New Files

| File | Purpose |
|------|---------|
| `os_build/scripts/optimize_postgres_io.sh` | Bash script that appends Iskander-tuned settings to `postgresql.conf` and reloads. Idempotent (checks for `# ISKANDER_TUNED` marker). |

#### Modifications to Existing Files

| File | Change |
|------|--------|
| `os_build/iso/user-data` | Add step to run `optimize_postgres_io.sh` in `late-commands` |

---

### 16E — Filesystem `noatime` Mount Flag

**Problem:** The Linux kernel updates the `atime` (access time) inode field on every file read. On an Iskander node serving IPFS blocks, Postgres pages, and Docker layer reads, this generates one write per read — effectively doubling write amplification on the SSD.

**Pattern:** Add `noatime` to root (`/`) and any LVM data partitions in `/etc/fstab` during post-install. This is the single highest-impact I/O change available without application code changes.

#### Modifications to Existing Files

| File | Change |
|------|--------|
| `os_build/iso/user-data` | Add `late-commands` step to `sed` the `fstab` replacing `relatime` with `noatime` for all ext4/xfs mounts |

---

### HITL & Glass Box (Phase 16)

- Queue depth > 80% capacity → `AgentAction` with `ethical_impact=MEDIUM` logged and WebSocket event broadcast.
- Queue rejection (depth = 50) → `AgentAction` with `ethical_impact=LOW`, 503 response.
- WebSocket connections are unauthenticated in dev; in production add Bearer token middleware (same pattern as appservice token auth).
- All I/O tuning changes are deterministic and reversible — no agent is involved; no Glass Box required.

---

### Config Additions (`backend/config.py`)

```python
agent_queue_max_depth: int = 50
agent_queue_workers: int = 1
websocket_ping_interval: int = 30  # seconds
```

---

### New File Index (Phase 16)

| File | Type | Purpose |
|------|------|---------|
| `backend/core/__init__.py` | Python | Package init |
| `backend/core/llm_queue_manager.py` | Python | `AsyncAgentQueue` — serialise LLM calls, expose status |
| `backend/routers/tasks.py` | Python | `GET /tasks/{task_id}` polling endpoint |
| `backend/api/__init__.py` | Python | Package init |
| `backend/api/websocket_notifier.py` | Python | WebSocket broadcast bus + internal pub/sub |
| `os_build/scripts/optimize_postgres_io.sh` | Bash | Idempotent Postgres I/O tuning |

### Modified File Index (Phase 16)

| File | Change |
|------|--------|
| `docs/iskander_roadmap_v2.md` | This document — add Phase 16 |
| `backend/main.py` | Mount tasks router; mount WS route; start queue worker |
| `backend/config.py` | Add queue/WS config fields |
| `backend/agents/spawner/node_registry.py` | Register `broadcast_ws_event` node |
| `docker-compose.yml` | Log rotation on all services |
| `os_build/iso/user-data` | Run IO optimisation script; add `noatime` fstab patch |

---

## Genesis Boot Sequence: Cooperative & Solo Node Onboarding

### Objective

Build the one-way initialization sequence that onboards a cooperative's (or individual's) governance into the Orchestrator engine. Three modes: SOLO_NODE (single-user sovereign node), LEGACY_IMPORT (cooperative importing existing bylaws), NEW_FOUNDING (cooperative selecting a governance template). Core invariant: **identity first, governance second** — founding members are onboarded before rules are ratified.

### Architecture

- **Three-tier governance model**: Constitutional Core (ICA, code-level immutable) → Genesis + Amendments (on-chain CIDs via Constitution.sol, ⅔ supermajority) → Operational Policy (governance_manifest.json, steward consensus)
- **Regulatory Layer**: Permanent jurisdictional floor (GB, ES, UNIVERSAL templates). Rules can only be tightened, never relaxed. Federations push `RegulatoryUpdate` messages via ActivityPub.
- **InitializerAgent**: LangGraph StateGraph with solo path (owner profile → regulatory layer → manifest → HITL review → genesis binding) and cooperative path (register founders → deploy CoopIdentity/SBTs → deploy Safe → extract/select rules → HITL rule confirmation → compile manifest → HITL ratification → genesis binding)
- **Constitution.sol**: Minimal on-chain anchor storing `genesisCIDHash`, `constitutionCIDHash`, `ratifiedAt`, `founderCount`, `coopIdentity`. Deliberately minimal — governance logic lives in PolicyEngine, not on-chain.
- **N-of-N Founding Consensus**: All founding decisions require unanimous consent. Threshold governance (M-of-N) is adopted post-genesis as an operational rule.
- **One-way latch**: Once Constitution.sol is deployed and PolicyEngine loaded, the node is live. `/genesis/boot` returns 409 forever.
- **Personal Node as Cooperative Interface**: A member's SOLO_NODE can aggregate memberships across multiple cooperatives, acting as unified client with fallback to direct cooperative access if the personal node goes offline.

### Dependencies

- **Requires**: Governance Orchestrator (PolicyEngine, TxOrchestrator) — Phase: Orchestrator v2.0 (completed)
- **Requires**: IKC LibraryManager — for template browsing and novel field proposals
- **Requires**: SovereignStorage — for manifest pinning with federated replication
- **Requires**: CoopIdentity.sol — for SBT minting (extended with `setConstitution()`)
- **Requires**: Gnosis Safe Factory — for N-of-N multi-sig deployment

### New Files

| File | Purpose |
|------|---------|
| `backend/schemas/genesis.py` | GenesisMode, GovernanceTier, RegulatoryUpdateSeverity enums + ExtractedRule, MappingConfirmation, RegulatoryLayer, RegulatoryUpdate, FounderRegistration models + API request/response models |
| `backend/agents/state.py` (MODIFY) | Add BootState(AgentState) TypedDict |
| `backend/schemas/compliance.py` (MODIFY) | Add `metadata: dict` field to PolicyRule for `_regulatory` and `_ambiguous` markers |
| `backend/config.py` (MODIFY) | Genesis settings: min founders, regulatory templates dir, boot-complete file |
| `backend/agents/genesis/__init__.py` | Package init |
| `backend/agents/genesis/initializer_agent.py` | LangGraph StateGraph — full boot sequence graph with 18 nodes |
| `backend/agents/genesis/rule_extractor.py` | Template-guided LLM bylaw extraction + ambiguity tagging |
| `backend/governance/regulatory/__init__.py` | Package init |
| `backend/governance/regulatory/UNIVERSAL.json` | ICA-only regulatory layer (fallback) |
| `backend/governance/regulatory/GB.json` | UK BenCom regulatory layer |
| `backend/governance/regulatory/ES.json` | Spain/Basque cooperative regulatory layer |
| `contracts/src/Constitution.sol` | Immutable on-chain genesis anchor |
| `contracts/test/Constitution.t.sol` | Foundry tests |
| `contracts/src/CoopIdentity.sol` (MODIFY) | Add `setConstitution(address)` one-time setter + `ConstitutionSet` event |
| `backend/auth/dependencies.py` (MODIFY) | Add `verify_founder_token()` FastAPI dependency |
| `backend/routers/genesis.py` | FastAPI router — 14 endpoints with pre-genesis founder-token auth |
| `backend/main.py` (MODIFY) | Register genesis router |
| `contracts/script/Deploy.s.sol` (MODIFY) | Add Constitution.sol deployment step |

### Database Migration

```sql
CREATE TABLE IF NOT EXISTS genesis_state (...);        -- Node-level genesis state tracking
CREATE TABLE IF NOT EXISTS founder_registrations (...); -- Pre-genesis member registration with bcrypt tokens
CREATE TABLE IF NOT EXISTS regulatory_updates (...);    -- Federation-pushed legislation changes
```

### Config Additions (`backend/config.py`)

```python
genesis_default_jurisdiction: str = "UNIVERSAL"
genesis_min_founders: int = 3
genesis_regulatory_templates_dir: str = "backend/governance/regulatory"
genesis_boot_complete_file: str = ".genesis_complete"
genesis_founder_token_bcrypt_rounds: int = 12
```

### Red Team Mitigations

- **VULN-G1** (attacker registers as founder): Out-of-band coordination required, min 3 founders, boot endpoint disabled after genesis
- **VULN-G2** (LLM hallucinates bylaw rules): Template-guided extraction, unanimous HITL confirmation, ambiguity tagging
- **VULN-G4** (genesis re-run after compromise): One-way latch + Constitution.sol immutability
- **VULN-G7** (founder token leaked): Single-use tokens, rotation on confirm, bcrypt hashing

### Detailed Spec & Plan

- **Design spec**: `docs/superpowers/specs/2026-03-17-genesis-boot-sequence-design.md`
- **Implementation plan**: `docs/superpowers/plans/2026-03-17-genesis-boot-sequence.md` (19 tasks, 5 chunks, TDD)
