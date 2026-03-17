# Genesis Boot Sequence — Design Specification

> **Project:** Iskander — Sovereign Agentic AI OS for Distributed Cooperatives
> **Date:** 2026-03-17
> **Status:** Draft
> **Scope:** InitializerAgent + GenesisBinding + Constitution.sol + RegulatoryLayer

---

## 1. Purpose

Build the Genesis Boot Sequence — the one-way initialization that onboards a cooperative's (or individual's) governance into the Orchestrator engine. Three modes:

1. **SOLO_NODE** — Single-user sovereign node. Only CCIN constitutional core + jurisdictional regulatory layer. No cooperative ceremony.
2. **LEGACY_IMPORT** — Cooperative importing existing bylaws via template-guided LLM extraction with HITL mapping confirmation.
3. **NEW_FOUNDING** — Cooperative selecting a governance template from the LibraryManager.

Core invariant: **identity first, governance second**. Founding members are onboarded before rules are ratified. Their first collective act is approving the governance framework. At genesis, all decisions require **unanimous consent** (N-of-N). Threshold governance (M-of-N) is adopted post-genesis as an operational rule.

The boot sequence is a **one-way trip**. Once the Genesis Manifest is anchored to `Constitution.sol`, the node is live.

---

## 2. Three-Tier Governance Model

Based on established cooperative practice (ICA, Mondragon, UK BenCom, DisCO):

| Tier | Changeability | Threshold | Examples |
|------|--------------|-----------|----------|
| **Constitutional Core (CCIN)** | Code-level, immutable | Code release only | Anti-extractive, democratic control, transparency, open membership |
| **Genesis + Amendments** | On-chain CIDs via Constitution.sol | 2/3 supermajority via MACIVoting | Membership rules, pay ratio, dissolution terms |
| **Operational Policy** | governance_manifest.json | Steward consensus via PolicyEngine | Spending limits, vendor policies, reporting thresholds |

Additionally, a **Regulatory Layer** acts as a permanent jurisdictional floor that cannot be weakened by any tier above it. Regulatory rules can only be tightened, never relaxed. Federations can push `RegulatoryUpdate` messages via ActivityPub to keep member cooperatives current with evolving legislation.

### Solo Node Simplification

Solo nodes operate with only two tiers: CCIN constitutional core + regulatory layer. No constitutional amendments (the owner updates their manifest directly). No M-of-N governance. The owner is the sole HITL authority.

---

## 3. Schemas & Data Model

**File:** `backend/schemas/genesis.py`

### GenesisMode Enum

```
SOLO_NODE       — Single-user sovereign node
LEGACY_IMPORT   — Cooperative importing existing bylaws
NEW_FOUNDING    — Cooperative founding from template
```

### BootState (extends AgentState — TypedDict)

BootState is a **TypedDict** (not Pydantic), consistent with all existing agent states in `backend/agents/state.py` (`InventoryState`, `GovernanceState`, `StewardshipCouncilState`, `CuratorDebateState`, etc.). Default values are provided via the graph's initial state dict, not on the TypedDict itself.

```
# Inherits from AgentState (TypedDict): messages, agent_id, action_log, error
mode:                     GenesisMode
node_type:                Literal["cooperative", "solo"]
coop_profile:             dict | None          — serialised CoopProfile
owner_profile:            dict | None          — solo node owner details
skeleton_template_cid:    str | None           — selected bylaw skeleton CID
extracted_rules:          list[dict]           — ExtractedRule dicts
mapping_confirmations:    dict[str, dict]      — founder_did -> {rule_id -> approved}
founder_confirmations:    dict[str, bool]      — founder_did -> ratified (for final sign-off)
ambiguous_rules:          list[str]            — rule_ids tagged Human-Judgment-Only
regulatory_layer:         dict | None          — serialised RegulatoryLayer
genesis_manifest:         dict | None          — compiled GovernanceManifest
constitution_cid:         str | None           — Ricardian constitution CID
genesis_manifest_cid:     str | None           — Mesh Archive CID
founding_tx_hash:         str | None           — Constitution.sol deployment tx
founder_sbt_ids:          list[int]            — minted SBT token IDs
safe_address:             str | None           — deployed Safe multi-sig address
boot_phase:               str                  — current phase identifier
boot_complete:            bool                 — one-way latch
requires_human_token:     bool
```

### ExtractedRule

```
rule_id:              str
source_text:          str              — original bylaw clause
proposed_policy_rule: dict             — serialised PolicyRule
confidence:           float (0-1)      — LLM extraction confidence
is_ambiguous:         bool             — True if confidence < 0.6 → Human-Judgment-Only
is_novel_field:       bool             — not in skeleton → propose as KnowledgeAsset
tier:                 GovernanceTier   — enum: Constitutional | Operational | Regulatory
confirmed:            bool             — human sign-off received
```

### MappingConfirmation

```
rule_id:              str
confirmed_by_did:     str
confirmed_at:         datetime
original_text:        str              — bylaw source text
code_representation:  str              — e.g. "governance_manifest.json → voting.quorum = 0.5"
approved:             bool
tier_assignment:      GovernanceTier   — enum: Constitutional | Operational | Regulatory
```

### RegulatoryLayer

Regulatory rules are stored as PolicyRules with a `_regulatory=True` metadata marker and `non_overridable=True` flag. This integrates with the existing PolicyRule-based PolicyEngine without requiring a new GovernanceManifest field. The `GovernanceManifest.policies` list contains both operational and regulatory rules; the engine distinguishes them via the metadata marker. Regulatory rules cannot be removed or weakened — only tightened.

```
jurisdiction:         str              — e.g. "GB", "ES"
rules:                list[PolicyRule] — permanent regulatory floor (each has _regulatory=True metadata)
source_documents:     list[dict]       — {reference, cid, ingested_at}
non_overridable:      bool             — always True
update_history:       list[str]        — RegulatoryUpdate CIDs (audit trail)
```

### RegulatoryUpdate

```
source_federation_did:  str            — DID of the broadcasting federation node
legislation_reference:  str            — e.g. "Co-operative and Community Benefit Societies Act 2014, Amendment 2026"
affected_rule_ids:      list[str]      — which existing PolicyRules are impacted
proposed_rules:         list[PolicyRule]
severity:               RegulatoryUpdateSeverity  — enum: Advisory | Mandatory | Urgent
effective_date:         datetime
ingested_via:           str            — CID of the ActivityPub message (provenance)
```

### FounderRegistration

```
did:                  str
address:              str              — EVM address for SBT + Safe
name:                 str              — human-readable (for persona injection)
founder_token:        str              — temporary pre-genesis auth secret
registered_at:        datetime
```

---

## 4. InitializerAgent — The Boot Sequence Graph

**File:** `backend/agents/genesis/initializer_agent.py` — LangGraph StateGraph

### Solo Node Path

```
select_mode
  → collect_owner_profile
  → inject_regulatory_layer
  → configure_solo_manifest
  → [HITL: owner_review]
  → execute_solo_genesis
  → END
```

### Cooperative Path

```
select_mode
  → register_founders         ← minimum 3 founders, collect DID + address
  → deploy_identity           ← deploy CoopIdentity.sol, mint founder SBTs
  → deploy_safe               ← create N-of-N Gnosis Safe with all founders
  → [LEGACY_IMPORT]: load_skeleton → extract_rules → tag_ambiguous
  → [NEW_FOUNDING]:  browse_templates → select_template → populate_profile
  → [BOTH PATHS CONVERGE]:
  → inject_regulatory_layer
  → [HITL: confirm_mappings]  ← every founder signs off on each rule + assigns tier
  → propose_novel_fields      ← novel fields → KnowledgeAsset proposals to LibraryManager
  → compile_genesis_manifest
  → validate_genesis_manifest ← ensures required PolicyEngine fields present
  → [HITL: ratify_genesis]    ← ALL founders must sign (N-of-N unanimous consent)
  → execute_genesis_binding   ← one-way trip
  → END
```

### Glass Box Protocol (All Nodes)

Every graph node MUST create and append an `AgentAction` to `state["action_log"]`, following the pattern established in `stewardship_scorer.py`. Impact levels:
- **HIGH**: `deploy_identity`, `deploy_safe`, `execute_genesis_binding`, `execute_solo_genesis`, `ratify_genesis` (Web3 transactions, irreversible operations)
- **MEDIUM**: `extract_rules`, `tag_ambiguous`, `inject_regulatory_layer`, `compile_genesis_manifest`, `validate_genesis_manifest`, `propose_novel_fields`, `confirm_mappings`
- **LOW**: `select_mode`, `collect_owner_profile`, `register_founders`, `load_skeleton`, `browse_templates`, `select_template`, `populate_profile`, `owner_review`

Additionally, genesis is a one-time critical operation and should NOT be interruptible by `agents_are_paused()` (low-power mode). The graph should skip the power-mode check that other agents perform.

### Node Descriptions

| Node | Purpose |
|------|---------|
| `select_mode` | Read `mode` from state. Routes to `collect_owner_profile` for SOLO_NODE, or to `register_founders` for cooperative modes (LEGACY_IMPORT / NEW_FOUNDING). For cooperative modes, validates that `mode` requires >= 3 founders (enforced at `register_founders`) |
| `collect_owner_profile` | Solo mode: collect owner DID, address, jurisdiction, name |
| `register_founders` | Collect minimum 3 founding member registrations (DID + address + name) |
| `deploy_identity` | Deploy CoopIdentity.sol with first founder as initial steward. Mint founder SBTs for all founders |
| `deploy_safe` | Deploy Gnosis Safe with all founder addresses as owners, N-of-N threshold |
| `load_skeleton` | Fetch bylaw skeleton template from LibraryManager by CID. Skeleton defines expected rule categories (pay ratio, quorum, membership, dissolution, etc.) |
| `extract_rules` | Feed bylaw text + skeleton to OLMo. Output: list of ExtractedRule with slot-matched fields. Unmatched clauses get `is_novel_field=True`. Fields beyond the standard skeleton are captured and proposed back |
| `tag_ambiguous` | LLM confidence < 0.6 → `is_ambiguous=True`, tagged Human-Judgment-Only. PolicyEngine forces HITL vote for every future action touching that rule |
| `browse_templates` | Query LibraryManager for KnowledgeAssets tagged `governance-template`. Return options for human selection |
| `select_template` | Human picks a template (e.g. "DisCO Housing Standard"). Populate extracted_rules from template defaults |
| `populate_profile` | Build CoopProfile from template defaults + human overrides |
| `inject_regulatory_layer` | Load jurisdiction-specific RegulatoryLayer from `backend/governance/regulatory/{jurisdiction}.json`. These rules are the permanent floor — cannot be weakened |
| `configure_solo_manifest` | Solo mode: build minimal GovernanceManifest with CCIN core + regulatory layer + any personal operational rules |
| `confirm_mappings` | **HITL breakpoint (cooperative only).** Present each ExtractedRule as a mapping confirmation. Every founder approves/rejects each rule and assigns tier (Constitutional/Operational/Regulatory). Requires unanimous consent — every value in `mapping_confirmations[founder_did][rule_id]` must be True for all founders and all rules. (Note: `founder_confirmations` is reserved for the final `ratify_genesis` sign-off, not per-rule approval) |
| `owner_review` | **HITL breakpoint (solo only).** Owner reviews the compiled manifest. Single sign-off |
| `propose_novel_fields` | Rules with `is_novel_field=True` are packaged as KnowledgeAsset proposals to LibraryManager. The skeleton grows for future cooperatives via IKC curator consensus |
| `compile_genesis_manifest` | Merge confirmed rules by tier: regulatory layer (permanent floor) + constitutional rules + operational rules → GovernanceManifest + RegulatoryLayer |
| `validate_genesis_manifest` | Check all required PolicyEngine fields present. Verify CCIN constitutional core included. Verify regulatory layer covers jurisdiction minimums. Verify no regulatory rules were weakened |
| `ratify_genesis` | **HITL breakpoint (cooperative only).** Final sign-off by ALL founding members (N-of-N). Displays the full manifest diff. This is the point of no return. Solo nodes skip this (owner already approved in `owner_review`) |
| `execute_genesis_binding` | The one-way trip (see Section 5) |
| `execute_solo_genesis` | Lightweight version of genesis binding for solo nodes (see Section 5) |

### Ambiguity Handling

Rules tagged `Human-Judgment-Only` are stored in the manifest with `constraint_type=RequireApproval` and a metadata flag `_ambiguous=True`. The PolicyEngine treats these as mandatory HITL for every instance — the Orchestrator refuses to auto-execute any action touching an ambiguous rule.

### Novel Field Lifecycle

When the LLM extracts a bylaw clause that doesn't match any slot in the skeleton template:
1. The clause is marked `is_novel_field=True` in the ExtractedRule
2. During `propose_novel_fields`, it's packaged as a KnowledgeAsset proposal to LibraryManager
3. The proposal goes through IKC curator consensus (3 curator votes) before admission to the standard skeleton
4. If admitted, future cooperatives using that skeleton will see the new field as a standard slot
5. The founding cooperative's rule is still applied locally regardless of whether the KnowledgeAsset is admitted globally

---

## 5. The Genesis Binding — The One-Way Trip

### Cooperative Genesis (`execute_genesis_binding`)

Identity is established first (steps 1-3 happen earlier in the graph). The binding sequence:

1. **Generate Ricardian Constitution** — Call existing `POST /constitution/generate` with the CoopProfile. Returns `constitution_cid`.

2. **Pin Genesis Manifest to Mesh Archive** — Serialize compiled GovernanceManifest + RegulatoryLayer as JSON bytes. Pin via `SovereignStorage.pin(data=manifest_json_bytes, audience="federation", min_replicas=3)`. Returns `(genesis_manifest_cid, replica_count, AgentAction)`. Append the AgentAction to `state.action_log`.

3. **Deploy Constitution.sol** — On-chain anchor storing:
   - `genesisCIDHash` (immutable) — keccak256 of genesis manifest CID string
   - `constitutionCIDHash` (immutable) — keccak256 of Ricardian constitution CID string
   - `ratifiedAt` (block.timestamp)
   - `founderCount` (immutable)
   - `coopIdentity` (immutable) — linked CoopIdentity contract address
   - Emits `GenesisRatified(genesisCID, constitutionCID, founderCount)` event

4. **Wire cross-contract references** — `CoopIdentity.setConstitution(constitution_address)` (new one-time setter to be added to CoopIdentity.sol, same pattern as existing `setArbitrationRegistry`). Emits a `ConstitutionSet(address)` event.

5. **Load PolicyEngine** — `manifest, action = PolicyEngine.load_manifest(manifest_dict=genesis_manifest)`. Append the returned AgentAction to `state.action_log` (Glass Box Protocol). Regulatory layer rules injected as non-overridable PolicyRules with `_regulatory=True` metadata marker (see M3 note in Section 3). From this moment, all agents pass through the compliance gate.

6. **Inject Persona** — Call `build_agent_prompt(profile=coop_profile)` from `backend.agents.core.persona_generator` (module-level function, not a class method) to generate the persona block. Then call `inject_persona(base_prompt, profile=coop_profile)` to substitute `{PERSONA_BLOCK}` in each agent's base prompt. This configures all agent system prompts with cooperative identity.

7. **Create CausalEvent** — `CausalEvent.create("governance.genesis.ratified", ...)` with `audience="federation"`. Broadcasts genesis to federated peers.

8. **Set one-way latch** — `boot_complete = True`. The `/genesis/boot` endpoint returns 409 Conflict for all future calls.

### Solo Genesis (`execute_solo_genesis`)

Simplified version:

1. **Pin Genesis Manifest** — Serialize manifest as JSON bytes. `SovereignStorage.pin(data=manifest_json_bytes, audience="node", min_replicas=0)` (solo node, no federation requirement). Append AgentAction to `state.action_log`.

2. **Deploy Constitution.sol** — `founderCount=1`, `coopIdentity=address(0)` (solo nodes have no CoopIdentity contract and skip SBT minting). The deployment transaction is signed by the owner's private key (loaded from config `deployer_private_key`).

3. **Load PolicyEngine** — Same as cooperative path.

4. **Inject Persona** — Uses owner profile instead of CoopProfile.

5. **Create CausalEvent** — `audience="node"` (local only, not broadcast).

6. **Set one-way latch.**

### Atomicity & Recovery

Steps before Constitution.sol deployment are reversible (CIDs are just pinned data). The contract deployment is the commitment point. If post-deployment steps fail, the system enters a `GENESIS_RECOVERY` state where a steward (or solo owner) can manually resume. The contract is deployed but the node isn't fully configured — safe because no agents can operate without a loaded PolicyEngine.

### Constitution.sol Contract

```solidity
// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

contract Constitution {
    bytes32 public immutable genesisCIDHash;
    bytes32 public immutable constitutionCIDHash;
    uint256 public immutable ratifiedAt;
    uint16  public immutable founderCount;
    address public immutable coopIdentity;

    event GenesisRatified(
        string genesisCID,
        string constitutionCID,
        uint16 founderCount
    );

    constructor(
        string memory _genesisCID,
        string memory _constitutionCID,
        uint16 _founderCount,
        address _coopIdentity
    ) {
        genesisCIDHash = keccak256(bytes(_genesisCID));
        constitutionCIDHash = keccak256(bytes(_constitutionCID));
        ratifiedAt = block.timestamp;
        founderCount = _founderCount;
        coopIdentity = _coopIdentity;
        emit GenesisRatified(_genesisCID, _constitutionCID, _founderCount);
    }
}
```

Deliberately minimal — stores hashes, emits one event, nothing else. Governance logic lives in PolicyEngine, not on-chain.

---

## 6. Regulatory Update Pipeline (Post-Genesis)

Cooperatives don't just amend internally — they receive external regulatory updates from federations. This uses the existing Diplomatic Embassy pattern:

1. Federation broadcasts a `RegulatoryUpdate` via ActivityPub (same channel as SecretaryAgent governance broadcasts).
2. `IngestionEmbassy` receives it, FRS-checks the source federation's reputation tier.
3. If Trusted/Allied: auto-queue for steward review. If Provisional: quarantine sandbox.
4. Steward reviews the proposed rule changes via HITL.
5. On approval: PolicyEngine absorbs the new rules. If `severity=Mandatory`, rules go into the RegulatoryLayer (non-overridable). If `Advisory`, they go into the operational manifest.

Key invariant: regulatory rules can only be **added or tightened**, never relaxed, unless the legislation itself is repealed (which would come as a new RegulatoryUpdate with explicit repeal reference).

---

## 7. Router & Endpoints

**File:** `backend/routers/genesis.py` — prefix `/genesis`, tags `["genesis-boot"]`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/boot` | unauthenticated (pre-genesis) | Start boot sequence. Returns 409 if already complete |
| POST | `/founders/register` | unauthenticated (pre-genesis) | Register a founding member (DID + address). Min 3 required |
| GET | `/founders` | unauthenticated | List registered founders and their confirmation status |
| POST | `/mode` | founder-token | Select SOLO_NODE, LEGACY_IMPORT, or NEW_FOUNDING |
| POST | `/bylaws/upload` | founder-token | Upload bylaw document text (LEGACY mode) |
| GET | `/templates` | founder-token | Browse governance templates from LibraryManager |
| POST | `/templates/select` | founder-token | Select a template (NEW_FOUNDING mode) |
| GET | `/mappings` | founder-token | Get current extracted rules + mapping confirmations |
| POST | `/mappings/{rule_id}/confirm` | founder-token | Confirm/reject a single rule mapping |
| POST | `/mappings/{rule_id}/assign-tier` | founder-token | Assign rule tier (Constitutional/Operational/Regulatory) |
| GET | `/manifest/preview` | founder-token | Preview the compiled genesis manifest before ratification |
| POST | `/ratify` | founder-token | Cast ratification vote. Genesis executes when ALL founders have ratified |
| GET | `/status` | any | Boot sequence status (pre-genesis, in-progress, complete, recovery) |
| POST | `/recovery/resume` | founder-token | Resume from GENESIS_RECOVERY state |

### Pre-Genesis Auth Model

Before the cooperative exists, there's no SIWE/JWT auth. The `/genesis/*` endpoints use a temporary "founder token":

- **Token format**: opaque URL-safe secrets generated via `secrets.token_urlsafe(32)`
- **Generation**: one token per founder, created during `POST /founders/register`, returned in the response body (shown once)
- **Storage**: stored in the `founder_registrations` table (see Section 9, row 16), hashed with bcrypt
- **Validation**: new FastAPI dependency `verify_founder_token()` added to `backend/auth/dependencies.py`. Extracts the `X-Founder-Token` header, verifies against stored hashes, returns `FounderRegistration` or raises HTTP 401
- **Rotation**: token rotated on each `POST /mappings/{rule_id}/confirm` call (new token returned in response)
- **Invalidation**: all founder tokens invalidated when genesis completes. Post-genesis, standard SIWE auth takes over

Solo nodes use a single owner token for all pre-genesis endpoints (same mechanism, single registration).

---

## 8. Personal Node as Cooperative Interface

A member who already runs a personal Iskander node (SOLO_NODE) can use that node as their **unified interface** to multiple cooperative memberships. Rather than running separate clients per cooperative, the personal node aggregates membership contexts.

### Architecture

- **Personal node** is a SOLO_NODE with its own genesis (CCIN + regulatory layer + personal operational rules)
- **Cooperative membership** is a remote relationship — the personal node holds the member's SBT proof and Safe signer key, but the cooperative's governance lives on the cooperative's node(s)
- **Membership registry**: `membership_contexts: dict[str, MembershipContext]` — keyed by cooperative DID, stores: cooperative name, Safe address, SBT token ID, cooperative node endpoint, governance manifest CID (cached), role (worker-owner / steward), last sync timestamp
- **Context switching**: the personal node presents cooperative-specific governance context when the member acts on behalf of a specific cooperative (proposals, votes, HITL approvals)

### Fallback & Offline Resilience

If the personal Iskander node goes offline:
1. **Direct cooperative access**: members fall back to the cooperative node's own web interface (every cooperative node exposes its own API). The member authenticates via SIWE using the same key their personal node holds
2. **Cached governance**: the personal node periodically syncs governance manifests from cooperative nodes. If the cooperative node is offline too, the cached manifest allows read-only review of pending proposals
3. **Queued actions**: if the personal node comes back online after downtime, it syncs missed events from cooperative nodes via the existing Mesh Archive CausalEvent replication

### Integration with Genesis

When a founder participates in a cooperative's genesis boot sequence, they can do so **from their personal Iskander node**. The genesis router accepts requests from any authenticated source — the founder token mechanism works regardless of whether the request comes from a direct browser, a cooperative node's UI, or a personal Iskander node acting as a proxy.

Post-genesis, the personal node registers a new `MembershipContext` entry, storing the cooperative's DID, the founder's SBT ID, and the Safe address.

### Mid-Membership Node Introduction

Members who initially joined a cooperative directly (via SIWE against the cooperative node) can later introduce a personal solo node as their interface:

1. **Acquire solo node**: Member runs genesis boot in SOLO_NODE mode, creating their personal Constitution.sol
2. **Credential delegation**: Member performs a one-time SIWE-signed delegation from the cooperative node, authorizing their personal node's DID to act on their behalf. The cooperative registers this delegation.
3. **Transparent proxy**: The personal node begins proxying all API calls to the cooperative node using the member's existing DID. The cooperative sees no difference — authentication still resolves to the same member identity.
4. **Additive only**: Introducing a personal node never invalidates existing cooperative membership. The member retains direct SIWE fallback access at all times.

This ensures members aren't penalised for not having a personal node at the time of cooperative founding, and can adopt sovereignty incrementally.

### Scope Note

The full MembershipContext schema, credential delegation flow, and node-offline detection are deferred to a separate spec ("Personal Node Federation"). This section establishes the architectural intent so the genesis boot sequence doesn't preclude it.

---

## 9. Red Team Analysis

### Genesis-Specific Vulnerabilities

| ID | Vector | Severity | Mitigation |
|----|--------|----------|------------|
| VULN-G1 | Attacker registers as founder before real founders | HIGH | Founder registration requires out-of-band coordination (physical ceremony, shared secret). Minimum 3 founders. Boot endpoint disabled after genesis |
| VULN-G2 | LLM hallucinates bylaw rules during LEGACY_IMPORT | CRITICAL | Template-guided extraction (skeleton slots). Every rule requires unanimous HITL confirmation. Ambiguous rules tagged Human-Judgment-Only |
| VULN-G3 | Regulatory layer outdated at genesis | MEDIUM | RegulatoryLayer loaded from versioned filesystem templates. Federation pushes RegulatoryUpdate post-genesis. Mandatory rules can only be tightened |
| VULN-G4 | Genesis re-run after compromise | CRITICAL | One-way latch: `boot_complete` flag + `/boot` returns 409. Constitution.sol immutable on-chain. No code path to re-deploy |
| VULN-G5 | Novel field proposals poisoning skeleton for future coops | MEDIUM | Novel fields proposed as KnowledgeAssets go through IKC curator consensus (3 curator votes) before admission to standard skeleton |
| VULN-G6 | Founding member key compromised before genesis completes | HIGH | N-of-N consensus means compromised key can only block (not forge). Recovery: remove compromised founder, register replacement, restart mapping confirmations |
| VULN-G7 | Founder token leaked pre-genesis | HIGH | Tokens are single-use per session. Token rotation on each `/mappings/confirm` call. All founder tokens invalidated at genesis completion |
| VULN-G8 | Solo node bypasses cooperative requirements | LOW | `node_type` is immutable after genesis. Solo nodes cannot mint SBTs, deploy Safe, or participate in federated governance votes. Upgrading solo→cooperative requires a new genesis (new node) |

### Interaction with Existing Modules

| Interaction | Risk | Mitigation |
|-------------|------|------------|
| Genesis ↔ PolicyEngine | Genesis manifest invalid for PolicyEngine | `validate_genesis_manifest` node checks all required fields before ratification |
| Genesis ↔ CoopIdentity.sol | SBTs minted before governance exists | By design — identity precedes governance. Founder SBTs carry `role="founder"` which grants bootstrap authority |
| Genesis ↔ LibraryManager | Template not found or corrupted | Skeleton CID verified against LibraryManager registry. Missing template → graph halts with error |
| Genesis ↔ IngestionEmbassy | RegulatoryUpdate arrives during genesis | Queued in sandbox. Only processed after genesis completes and PolicyEngine is live |
| Genesis ↔ existing /constitution/generate | Existing endpoint generates Markdown constitution | Reused as-is. Genesis wraps the existing endpoint, adds manifest compilation and on-chain anchoring |

---

## 10. Files to Create/Modify

| # | File | Action | Purpose |
|---|------|--------|---------|
| 1 | `backend/schemas/genesis.py` | CREATE | All Pydantic models: GenesisMode, GovernanceTier, RegulatoryUpdateSeverity, ExtractedRule, MappingConfirmation, RegulatoryLayer, RegulatoryUpdate, FounderRegistration, API request/response models |
| 2 | `backend/schemas/compliance.py` | MODIFY | Add `metadata: dict` field to `PolicyRule` (default `{}`) for `_regulatory=True` and `_ambiguous=True` markers |
| 3 | `backend/agents/state.py` | MODIFY | Add BootState(AgentState) |
| 4 | `backend/agents/genesis/__init__.py` | CREATE | Package init |
| 5 | `backend/agents/genesis/initializer_agent.py` | CREATE | LangGraph StateGraph — the full boot sequence graph |
| 6 | `backend/agents/genesis/rule_extractor.py` | CREATE | LLM-powered template-guided bylaw rule extraction |
| 7 | `backend/governance/regulatory/__init__.py` | CREATE | Package init |
| 8 | `backend/governance/regulatory/GB.json` | CREATE | UK BenCom regulatory layer template |
| 9 | `backend/governance/regulatory/ES.json` | CREATE | Spain/Basque cooperative regulatory layer template |
| 10 | `backend/governance/regulatory/UNIVERSAL.json` | CREATE | Universal CCIN-only regulatory layer (fallback) |
| 11 | `contracts/src/CoopIdentity.sol` | MODIFY | Add `setConstitution(address)` one-time setter and `ConstitutionSet` event |
| 12 | `contracts/src/Constitution.sol` | CREATE | Minimal on-chain genesis anchor |
| 13 | `contracts/test/Constitution.t.sol` | CREATE | Foundry tests for Constitution.sol |
| 14 | `contracts/script/Deploy.s.sol` | MODIFY | Add Constitution.sol deployment step |
| 15 | `backend/auth/dependencies.py` | MODIFY | Add `verify_founder_token()` FastAPI dependency for pre-genesis auth |
| 16 | `backend/routers/genesis.py` | CREATE | FastAPI router — 14 endpoints |
| 17 | `backend/main.py` | MODIFY | Register genesis router |
| 18 | `backend/config.py` | MODIFY | Add genesis settings |
| 19 | `infra/init.sql` | MODIFY | Add genesis_state, founder_registrations, regulatory_updates tables |
| 20 | `tests/test_genesis_boot.py` | CREATE | InitializerAgent + genesis binding tests |
| 21 | `tests/test_constitution_sol.py` | CREATE | Constitution.sol integration tests |

---

## 11. Implementation Phases (Token-Efficient)

### Phase 1: Schemas + State + Config (Foundation)
- `backend/schemas/genesis.py` — all models
- `backend/agents/state.py` — BootState addition
- `backend/config.py` — genesis settings
- `infra/init.sql` — table additions

### Phase 2: Constitution.sol + Regulatory Layer
- `contracts/src/Constitution.sol`
- `contracts/test/Constitution.t.sol`
- `backend/governance/regulatory/` — jurisdiction templates (GB, ES, UNIVERSAL)

### Phase 3: InitializerAgent Graph
- `backend/agents/genesis/initializer_agent.py` — full LangGraph
- `backend/agents/genesis/rule_extractor.py` — LLM extraction logic

### Phase 4: Router + Integration
- `backend/routers/genesis.py`
- `backend/main.py` — register router
- `contracts/script/Deploy.s.sol` — add Constitution deployment

### Phase 5: Tests
- `tests/test_genesis_boot.py`
- `tests/test_constitution_sol.py`

---

## 12. Test Plan

### Phase 1 Tests (Schemas)
- `test_genesis_mode_enum_values`
- `test_extracted_rule_ambiguity_threshold`
- `test_regulatory_layer_non_overridable_always_true`
- `test_boot_state_extends_agent_state`

### Phase 2 Tests (Constitution.sol)
- `test_genesis_ratified_event_emitted`
- `test_cid_hashes_match_input`
- `test_immutable_fields_cannot_change`
- `test_founder_count_stored`
- `test_coop_identity_link`

### Phase 3 Tests (InitializerAgent)
- `test_solo_mode_skips_cooperative_ceremony`
- `test_solo_mode_loads_regulatory_layer`
- `test_legacy_import_extracts_rules_from_skeleton`
- `test_ambiguous_rules_tagged_human_judgment_only`
- `test_novel_fields_proposed_as_knowledge_assets`
- `test_confirm_mappings_requires_unanimous_consent`
- `test_single_objection_blocks_ratification`
- `test_ratify_requires_all_founders`
- `test_boot_complete_latch_prevents_rerun`
- `test_genesis_recovery_resumes_from_failure`
- `test_regulatory_layer_cannot_be_weakened`
- `test_tier_assignment_persists`

### Phase 4 Tests (Router)
- `test_boot_returns_409_after_genesis`
- `test_founder_registration_minimum_3`
- `test_founder_token_invalidated_after_genesis`
- `test_solo_boot_end_to_end`
- `test_cooperative_boot_end_to_end`

### Integration Scenario
- `test_leeds_housing_coop_genesis` — 3 founders register → select "UK BenCom Housing" template → GB regulatory layer injected → map 12 rules with tier assignments → 2 ambiguous rules tagged → all 3 founders ratify → Constitution.sol deployed → PolicyEngine loaded → founder SBTs verified → one-way latch set → `/boot` returns 409
