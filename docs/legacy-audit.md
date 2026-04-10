# Legacy Backend Audit

`src/IskanderOS/legacy/backend/` — 148 Python files across 18 module directories from the original monolithic architecture. This document records the disposition of each module to inform migration planning and prevent redundant reinvention.

**Do not extend this code. Do not run it in production. Read it before building.**

## Dispositions

| Code | Meaning |
|------|---------|
| **MIGRATE** | Valuable logic that must be ported to an isolated service |
| **REFERENCE** | Useful patterns or designs; read before building equivalents |
| **HOLD** | Valuable but not yet relevant; revisit when the domain becomes active |
| **RETIRE** | Superseded or out of scope for the current direction |

---

## Root-level files

| File | Disposition | Notes |
|------|-------------|-------|
| `config.py` | REFERENCE | Phase-gated feature flags and ICA principle definitions. Extract constitutional constants to a policy service; do not import this directly. |
| `db.py` | MIGRATE | asyncpg connection pool with JSONB codec. Pattern is sound; port to the relevant service's database layer. |
| `main.py` | REFERENCE | FastAPI lifespan pattern for async queue lifecycle and graceful shutdown. Useful model; the monolithic router registration pattern is not. |

---

## Modules

### `agents/`

| Path | Disposition | Notes |
|------|-------------|-------|
| `agents/core/glass_box_parser.py` | **MIGRATE** | Pydantic output parser enforcing Glass Box audit schema (`AgentAction` + `EthicalImpactLevel`). Foundational — every agent service needs this wrapping pattern. |
| `agents/core/ica_verifier.py` | **MIGRATE** | Validates actions against ICA cooperative principles. Mission-critical; must exist in every service that takes governance actions. |
| `agents/core/persona_generator.py` | **MIGRATE** | Injects member history and precedent into agent system prompts. Port alongside `memory/precedent_retriever.py`. |
| `agents/genesis/` | REFERENCE | One-time cooperative genesis bootstrap (contract deployment, founder token minting, regulatory template loading). Irreversible operation; keep as documentation of the genesis sequence. |
| `agents/library/arbitrator.py` | MIGRATE | Game-theoretic arbitration with Iterated Prisoner's Dilemma scoring. No equivalent exists. |
| `agents/library/curator_network.py` | MIGRATE | Multi-agent knowledge asset lifecycle (Efficiency/Ethics/Resilience curators, dialectic consensus). Directly relevant to knowledge commons work. |
| `agents/library/discussion.py` | RETIRE | Replaced by Loomio. |
| `agents/library/fiat_gateway.py` | MIGRATE | Cooperative Fiat Token bridge with HITL proposal flow. |
| `agents/library/ica_vetter.py` | MIGRATE | Ethics vetting against ICA principles with composite scoring. Required for any onboarding or governance action pipeline. |
| `agents/library/ipd_auditor.py` | MIGRATE | Post-trade IPD auditing for inter-cooperative trust scoring. Unique; no equivalent. |
| `agents/library/outcome.py` | REFERENCE | Outcome recording pattern for completed governance cycles. |
| `agents/library/procurement.py` | MIGRATE | Democratic procurement with governance-enforced catalog constraint. Prevents deployment of unapproved software. |
| `agents/library/proposal.py` | RETIRE | Replaced by Loomio. |
| `agents/library/provisioner.py` | MIGRATE | Democratic app store orchestration with HITL voting gates. Catalog-driven deployment is novel and not yet ported. |
| `agents/library/secretary.py` | MIGRATE | Meeting management and agenda drafting. Port to Secretary service. |
| `agents/library/steward.py` | MIGRATE | Stewardship role automation (S3 steward patterns). |
| `agents/library/stewardship_scorer.py` | MIGRATE | Impact Score calculation from Valueflows data, used for delegated voting weight. |
| `agents/library/task_extractor.py` | REFERENCE | Extracts actionable tasks from governance discussion. Pattern worth preserving. |
| `agents/library/voting.py` | RETIRE | Replaced by Loomio + MACI (Phase B). |
| `agents/research/ritl_manager.py` | HOLD | Researcher-in-the-Loop peer review with ZK blind review. Novel pattern; not yet integrated. Revisit for research fellowship module. |
| `agents/spawner/` | REFERENCE | Dynamic agent spawning with runtime registry and AJD schema. Architecturally interesting; compare against orchestrator design (issue #133) before building. |
| `agents/governance_agent.py` | RETIRE | Root-level stub; replaced by OpenClaw agent architecture. |
| `agents/steward_agent.py` | RETIRE | Root-level stub; replaced by OpenClaw + Decision Recorder. |

### `api/`

| File | Disposition | Notes |
|------|-------------|-------|
| `brightid_sponsor.py` | MIGRATE | BrightID sponsor proof minting. Required for Sybil-resistant identity (Phase B). |
| `constitutional_dialogue.py` | **MIGRATE** | Ricardian contract generator with New York Convention arbitration clause. Critical for legal enforceability of inter-cooperative agreements. Do not lose this. |
| `hitl_manager.py` | MIGRATE | DID-based HITL routing (ActivityPub inbox vs. local WebSocket). Core federation infrastructure. |
| `hitl_rate_limiter.py` | REFERENCE | Rate limiting for HITL proposals. Reimplement as middleware if needed. |
| `model_manager.py` | MIGRATE | Hardware-aware Ollama model lifecycle with VRAM margin enforcement. Relevant for multi-node deployments. |
| `websocket_notifier.py` | REFERENCE | WebSocket event broadcasting pattern. Reimplement per service. |

### `appstore/`

| File | Disposition | Notes |
|------|-------------|-------|
| `catalog.py` / `catalog.yaml` | MIGRATE | Read-only FOSS app catalog with governance-enforced constraint. Catalog-driven deployment prevents unapproved images; this is the design to port to the Provisioner service. |
| `docker_manager.py` | REFERENCE | Container orchestration pattern (image pull, network attachment, credential generation). |

### `auth/`

| File | Disposition | Notes |
|------|-------------|-------|
| `siwe.py` | MIGRATE | EIP-4361 Sign-In-with-Ethereum with EIP-1271 Smart Contract wallet support (Gnosis Safe). Not available in Authentik out of box; port to auth layer or Authentik custom backend. |
| `web3_provider.py` | MIGRATE | Web3 provider abstraction for on-chain interactions. |
| `jwt_manager.py` | RETIRE | Replaced by Authentik token system. |
| `dependencies.py` | RETIRE | FastAPI dependency injection wrappers; replaced per service. |

### `boundary/`

| File | Disposition | Notes |
|------|-------------|-------|
| `boundary_agent.py` | **MIGRATE** | Five-layer foreign activity ingestion (Trust Quarantine → Ontology Translation → Governance Verification → Causal Ordering → Glass Box Wrap). Entirely novel. Do not rebuild from scratch — port this. |
| `causal_buffer.py` | **MIGRATE** | Causal message ordering for federated events. Required for correct federation behaviour. |
| `governance_verifier.py` | MIGRATE | Verifies foreign governance actions against local policy. |
| `ontology_translator.py` | MIGRATE | Maps foreign schemas to canonical internal forms. Required for multi-standard federation. |

### `core/`

| File | Disposition | Notes |
|------|-------------|-------|
| `llm_queue_manager.py` | MIGRATE | Async concurrency queue preventing LLM calls from blocking the event loop. Essential for CPU-only or single-GPU nodes. |
| `hardware_profiler.py` | MIGRATE | Reads system specs for energy-aware scheduling gates. Port alongside `energy/`. |

### `crypto/`

| File | Disposition | Notes |
|------|-------------|-------|
| `zk_maci_wrapper.py` | REFERENCE | MACI coordinator role: vote secrecy, anti-coercion, ZK tally. **Poseidon hash, BabyJubJub, and Groth16 are stubs.** Do not ship. Requires expert cryptographic review before any production use. |

### `diplomacy/`

| File | Disposition | Notes |
|------|-------------|-------|
| `vc_verifier.py` | MIGRATE | W3C VC verification against on-chain TrustRegistry. Offline-first with revocation caching. Port to identity service. |
| `identity_attestation_agent.py` | MIGRATE | Converts verified VCs to internal SBT attestations with tombstone-only lifecycle. |

### `energy/`

| File | Disposition | Notes |
|------|-------------|-------|
| `governor.py` | HOLD | Tri-state energy policy (GREEN/YELLOW/RED) with graceful degradation. |
| `hearth_interface.py` | HOLD | Battery telemetry from Hearth hardware HATs. Revisit when hardware deployment is active. |
| `resource_policy_engine.py` | HOLD | Task prioritisation and mesh offload based on power state. |
| `task_queuer.py` | HOLD | Energy-gated task queue. |

### `federation/`

| File | Disposition | Notes |
|------|-------------|-------|
| `arbitration_protocol.py` | **MIGRATE** | Custom Iskander ActivityPub extensions for arbitration federation (ArbitrationRequest, JuryNomination, Verdict). Novel and irreplaceable. |
| `did_resolver.py` | MIGRATE | DID resolution with TTL caching. Required for any federation or identity work. |
| `http_signatures.py` | MIGRATE | ActivityPub HTTP signature verification for incoming federated messages. |
| `inbox_processor.py` | MIGRATE | Inbox message processing with causal buffering. Port alongside `boundary/causal_buffer.py`. |

### `finance/`

| File | Disposition | Notes |
|------|-------------|-------|
| `frs_client.py` | MIGRATE | Foreign Reputation System: exponential-decay reputation with tier-based trust (Quarantine → Provisional → Trusted → Allied). Unique; no equivalent. |
| `open_banking_client.py` | MIGRATE | PSD2-compliant Open Banking API for fiat bridge. |
| `solvency_oracle.py` | MIGRATE | Escrow vs. fiat reserve ratio monitoring with circuit-breaker. Prevents over-leverage. |
| `tx_orchestrator.py` | **MIGRATE** | Safe multi-sig batch drafting with TTL enforcement and PolicyEngine validation. Agents propose only — never sign. This invariant must survive the port. |

### `governance/`

| File | Disposition | Notes |
|------|-------------|-------|
| `policy_engine.py` | **MIGRATE** | Governance-as-code with immutable ICA Constitutional Core. Four hardcoded ICA checks that cannot be overridden. Foundational — port with full test coverage. |
| `governance_manifest.json` | MIGRATE | SHA-256 diff-locked policy manifest. Must be versioned and archived with every deployment. |

### `matrix/`

| File | Disposition | Notes |
|------|-------------|-------|
| `appservice.py` | REFERENCE | Matrix Application Service protocol with per-agent Matrix identities. |
| `bridge.py` | REFERENCE | Cross-protocol messaging bridge pattern. |
| `client.py` | REFERENCE | Async Matrix client with stub mode for development without a live homeserver. |

### `memory/`

| File | Disposition | Notes |
|------|-------------|-------|
| `pgvector_store.py` | MIGRATE | pgvector embeddings store for governance precedent. |
| `precedent_retriever.py` | MIGRATE | RAG retrieval of past decisions as prompt injections for agents. Precedent-driven governance is novel and valuable. |

### `mesh/`

| File | Disposition | Notes |
|------|-------------|-------|
| `causal_event.py` | **MIGRATE** | Content-addressed IPFS pinning with audience-based encryption. Foundational for data sovereignty. |
| `anchor_batcher.py` | MIGRATE | Chain-anchored sync batching to reduce on-chain costs. |
| `delta_sync.py` | MIGRATE | Incremental federated replication. |
| `access_middleware.py` | MIGRATE | SBT/EVM access control for mesh archive. |

### `routers/`

| All files | REFERENCE | Endpoint patterns document legacy API surface. Logic migrates to the appropriate service; thin router wrappers can be recreated. Do not port routers directly — port the underlying agent or service logic first. |

### `schemas/`

| File | Disposition | Notes |
|------|-------------|-------|
| `glass_box.py` | **MIGRATE** | `AgentAction` + `EthicalImpactLevel` schema. This is the audit protocol foundation. Port first; every other schema depends on it. |
| All others | MIGRATE | Pydantic models for arbitration, compliance, deliberation, diplomacy, finance, HITL, IPD, knowledge, mesh, stewardship. Port alongside the corresponding service. |

---

## Critical warnings

These apply regardless of which modules are being migrated. They represent invariants that must be preserved across the port.

1. **Glass Box is mandatory.** `AgentAction` + `EthicalImpactLevel` must wrap every agent write action in every service. Port `schemas/glass_box.py` and `agents/core/glass_box_parser.py` before anything else.

2. **No auto-sign.** `tx_orchestrator.py` strictly separates proposal from execution. Agents draft; multisig signers execute. This separation must survive the migration.

3. **Constitutional Core is immutable.** `governance/policy_engine.py` encodes four ICA checks that cannot be overridden at runtime. Do not add bypass paths during the port.

4. **Tombstone-only.** Attestations and records are never deleted. This lifecycle constraint must be encoded in the data model of every migrated service.

5. **Boundary gates are sequential.** The five layers in `boundary/` must execute in order. Do not parallelise or skip gates.

6. **MACI cryptography is stubbed.** `crypto/zk_maci_wrapper.py` is not production-ready. Poseidon hash, BabyJubJub ECDH, and Groth16 proof generation are placeholders. Expert cryptographic review is required before any production ZK voting deployment.

7. **Arbitration clause must survive.** `api/constitutional_dialogue.py` generates Ricardian contracts with binding New York Convention arbitration clauses. This is real-world legal enforceability — do not drop or simplify it.

---

## Migration sequence guidance

Port in this order to minimise dependency gaps:

1. `schemas/glass_box.py` + `agents/core/glass_box_parser.py` — audit foundation
2. `governance/policy_engine.py` — constitutional layer
3. `memory/` — precedent RAG
4. `boundary/` — foreign activity ingestion (all four files together)
5. `federation/` — ActivityPub and DID infrastructure
6. `agents/library/` high-priority agents (ica_vetter, stewardship_scorer, provisioner, secretary)
7. `finance/` — in order: solvency_oracle → tx_orchestrator → frs_client → open_banking_client
8. `mesh/` — data sovereignty layer
9. Remaining agents and API modules

Refer to GitHub issue #128 for the active migration tracking document.
