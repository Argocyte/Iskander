# Project Iskander — Complete Implementation Specification

> **Purpose**: Machine-readable reference for cross-agent verification and stress testing.
> **Generated**: 2026-03-17 | **Toolchain**: Claude Opus 4.6 | **Target Reviewer**: Gemini

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Smart Contracts (Solidity 0.8.24)](#3-smart-contracts)
4. [Backend (Python / FastAPI / LangGraph)](#4-backend)
5. [Database Schema (PostgreSQL)](#5-database-schema)
6. [Agent System](#6-agent-system)
7. [API Surface (All Routers)](#7-api-surface)
8. [Security Model](#8-security-model)
9. [Energy-Aware Scheduling](#9-energy-aware-scheduling)
10. [Mesh Archive / Sovereign Data Fabric](#10-mesh-archive)
11. [Fiat-Crypto Bridge](#11-fiat-crypto-bridge)
12. [Cross-Cutting Invariants](#12-cross-cutting-invariants)
13. [Known Stubs & Gaps](#13-known-stubs-and-gaps)
14. [Stress Test Targets](#14-stress-test-targets)

---

## 1. EXECUTIVE SUMMARY

**Project Iskander** is a sovereign agentic AI operating system for Distributed Cooperatives (DisCOs). It combines:

- **AI decision-making** with mandatory Glass Box Protocol rationale on every action
- **Blockchain governance** via ERC-4973 Soulbound Tokens, ZK-SNARK MACI voting, and liquid delegation
- **Energy-aware hardware scheduling** with tri-state execution policies (GREEN/YELLOW/RED)
- **Federated mesh storage** with content-addressed IPFS and SBT-gated access control
- **Anti-extractive fiat bridge** bypassing payment processors with 1:1 cooperative bank-backed tokens

- **One-way genesis onboarding** with three-tier governance (Constitutional → Genesis → Operational) and regulatory floor enforcement

**Stack**: Solidity 0.8.24 (Foundry) | Python 3.11+ (FastAPI + LangGraph) | PostgreSQL + pgvector | IPFS | ActivityPub | Gnosis Chain

**License**: AGPL-3.0-only (all contracts and backend)

---

## 2. ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                    ISKANDER SOVEREIGN NODE                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Frontend    │  │  FastAPI     │  │  LangGraph Agents    │  │
│  │  (Streamlit)  │──│  29 Routers  │──│  13 StateGraphs      │  │
│  └──────────────┘  └──────┬───────┘  └──────────┬───────────┘  │
│                           │                      │              │
│  ┌────────────────────────┴──────────────────────┴───────────┐  │
│  │              Glass Box Protocol Layer                      │  │
│  │   AgentAction(agent_id, action, rationale, ethical_impact) │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────┐  ┌─────────┐  │  ┌────────────┐  ┌────────────┐  │
│  │PostgreSQL│  │ pgvector│  │  │   IPFS     │  │  Gnosis    │  │
│  │ 30+ tbl  │  │  RAG    │  │  │Mesh Archive│  │  Chain     │  │
│  └──────────┘  └─────────┘  │  └────────────┘  └────────────┘  │
│                              │                                   │
│  ┌──────────────────────────┴────────────────────────────────┐  │
│  │            Energy Gate (Hearth Driver)                     │  │
│  │   @energy_gated_execution → GREEN/YELLOW/RED policies     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Contract Dependency Graph

```
                    CoopIdentity (ERC-4973 SBT)
                     /      |       \         \
                    /       |        \         \
          InternalPayroll   |   ArbitrationRegistry
          (6:1 pay cap)     |    (Solidarity Court)
                            |        /
                      IskanderEscrow ◄──┘
                    (Inter-coop trade)
                            |
                    StewardshipLedger
                 (gSBT delegation + Impact Scores)
                            |
                       MACIVoting
                   (ZK-Privacy voting)

                   CoopFiatToken (ERC-20)
               (1:1 fiat-backed, standalone)

                   Constitution (immutable)
               (Genesis CID hash + founder count)
```

---

## 3. SMART CONTRACTS

**Compiler**: Solidity ^0.8.24 | **Framework**: Foundry | **Optimizer**: 200 runs | **Target Chain**: Gnosis Chain (dev: Anvil localhost:8545)

### 3.1 CoopIdentity.sol — ERC-4973 Soulbound Token

**Path**: `contracts/src/CoopIdentity.sol`
**Inheritance**: `ERC165, IERC4973`
**Purpose**: Non-transferable identity tokens encoding cooperative membership, roles, and trust scores.

**State Variables**:
| Variable | Type | Mutability | Purpose |
|----------|------|------------|---------|
| `legalWrapperCID` | `string` | public | IPFS CID of cooperative's legal wrapper |
| `coopName` | `string` | public | Cooperative name |
| `steward` | `address` | public | M-of-N Safe multi-sig admin |
| `arbitrationRegistry` | `address` | public | ArbitrationRegistry contract |
| `brightIdVerifier` | `IBrightID` | public | BrightID sybil resistance |
| `brightIdAppContext` | `bytes32` | public | BrightID app context hash |
| `memberRecords` | `mapping(uint256 => MemberRecord)` | public | Token → member data |
| `memberToken` | `mapping(address => uint256)` | public | Address → token reverse lookup |

**MemberRecord Struct**:
```solidity
struct MemberRecord {
    string  did;           // W3C DID
    string  role;          // "worker-owner", "steward", "associate"
    uint256 joinedAt;
    bool    active;
    uint16  trustScore;    // [0, 1000]; 1000 = full trust
}
```

**Key Functions**:
| Function | Visibility | Modifier | Description |
|----------|-----------|----------|-------------|
| `attest(address, string did, string role, string tokenURI)` | external | onlySteward | Mint SBT to new member |
| `revoke(address)` | external | onlySteward | Burn SBT, remove membership |
| `slashTrust(address, uint16 penalty, bytes32 caseHash)` | external | onlyArbitrationRegistry | Reduce trust score |
| `restoreTrust(address, uint16 restoration, bytes32 caseHash)` | external | onlySteward | Restore trust score |
| `balanceOf(address)` | view | — | Returns 0 or 1 (SBT) |
| `transferFrom()` | pure | — | Always reverts (account-bound) |

**Events**: `MembershipGranted`, `MembershipRevoked`, `TrustSlashed`, `TrustRestored`, `StewardTransferred`

**Custom Errors**: `NotSteward`, `AlreadyMember`, `NotAMember`, `TransferProhibited`, `BrightIDNotVerified`

**CRITICAL INVARIANT**: `transferFrom()`, `approve()`, `setApprovalForAll()` all revert unconditionally. Tokens are non-transferable by design (ERC-4973).

---

### 3.2 StewardshipLedger.sol — Liquid Delegation + Impact Scores

**Path**: `contracts/src/governance/StewardshipLedger.sol`
**Interface**: `contracts/src/governance/IStewardshipLedger.sol`
**Purpose**: O(1) gSBT-weighted liquid delegation with Impact Score oracle, emergency veto, and solvency circuit breaker.

**Immutable State**:
| Variable | Type | Set In |
|----------|------|--------|
| `coopIdentity` | `CoopIdentity` | constructor |
| `escrowContract` | `IskanderEscrow` | constructor |

**Mutable State**:
| Variable | Type | Access | Purpose |
|----------|------|--------|---------|
| `oracle` | `address` | onlyOracle | Authorized Impact Score updater |
| `stewardThresholdBps` | `uint256` | onlyOracle | Min score for steward eligibility (basis points 0-10000) |
| `solvencyFactorBps` | `uint256` | onlyOracle | Circuit breaker ratio |
| `fiatReserveValue` | `uint256` | onlyOracle | Current fiat reserve |
| `totalEscrowValue` | `uint256` | onlyOracle | Current on-chain escrow |
| `impactScores` | `mapping(address => uint256)` | onlyOracle | Per-node scores (basis points) |
| `delegation` | `mapping(address => address)` | onlyMember | Delegator → steward |
| `receivedDelegations` | `mapping(address => uint256)` | — | Inbound count per steward |
| `hasWeight` | `mapping(address => bool)` | — | Member registered? |
| `vetoCount` | `uint256` | — | Total vetos filed |
| `vetos` | `mapping(uint256 => VetoRecord)` | — | Veto records |

**Core Functions**:
| Function | Access | Gas Complexity | Description |
|----------|--------|----------------|-------------|
| `delegate(address steward)` | onlyMember | O(1) | Delegate to eligible steward; checks circuit breaker |
| `revoke()` | public | O(1) | Instant self-revoke; zero external calls |
| `getVotingWeight(address)` | view | O(1) | `hasWeight[node] + receivedDelegations[node]` |
| `emergencyVeto(uint256, string)` | onlyMember | O(1) | File veto with IPFS rationale CID |
| `updateImpactScores(address[], uint256[])` | onlyOracle | O(n) | Batch update; emits `StewardEligibilityLost` |
| `updateFiatReserve(uint256)` | onlyOracle | O(1) | Update reserve for circuit breaker |
| `updateTotalEscrow(uint256)` | onlyOracle | O(1) | Update escrow for circuit breaker |
| `registerMember(address)` | onlyOracle | O(1) | Register weight for new member |
| `setThreshold(uint256)` | onlyOracle | O(1) | Update steward threshold |
| `setOracle(address)` | onlyOracle | O(1) | Rotate oracle address |

**Circuit Breaker Logic**:
```solidity
function _checkCircuitBreaker() internal view {
    if (fiatReserveValue > 0 && totalEscrowValue > fiatReserveValue * solvencyFactorBps / 10000) {
        revert CircuitBreakerActive(totalEscrowValue, fiatReserveValue * solvencyFactorBps / 10000);
    }
}
```

**Events**: `Delegated`, `Revoked`, `EmergencyVetoFiled`, `ImpactScoresUpdated`, `StewardEligibilityLost`, `CircuitBreakerTripped`

**Custom Errors**: `NotAMember`, `NotOracle`, `StewardBelowThreshold`, `ArrayLengthMismatch`, `CircuitBreakerActive`, `NoDelegationToRevoke`, `EmptyRationale`, `ZeroAddress`

**Test Suite**: `contracts/test/StewardshipLedger.t.sol` — 16 Foundry tests covering delegation lifecycle, membership requirements, threshold enforcement, revoke safety, batch updates, eligibility loss events, array mismatch, oracle-only access, emergency veto, circuit breaker, voting weight accuracy, re-delegation, oracle admin.

**CRITICAL INVARIANT**: `revoke()` has ZERO external calls and NEVER reverts (except `NoDelegationToRevoke`). This ensures members can always exit delegation regardless of contract state.

**CRITICAL INVARIANT**: Voting weight is O(1) — `hasWeight[node] + receivedDelegations[node]`. No iteration over delegator sets.

---

### 3.3 MACIVoting.sol — ZK-SNARK Privacy-Preserving Voting

**Path**: `contracts/src/governance/MACIVoting.sol`
**Purpose**: Anti-bribery, collusion-resistant voting using Minimal Anti-Collusion Infrastructure (MACI).

**Proposal Lifecycle**: `Active → Processing → Finalized | Rejected`

**Key Design**: Individual votes are NEVER stored on-chain. Only aggregate tallies + ZK proofs. Coordinator processes encrypted messages off-chain and submits Groth16 proof.

**State**:
- `coordinator` — off-chain MACI Coordinator address
- `snarkVerifier` — Groth16 tally verifier contract
- `quorumBps` — quorum threshold (default 5100 = 51%)

**Functions**: `createProposal`, `signUp`, `publishMessage`, `beginProcessing`, `processMessages` (with ZK proof verification)

---

### 3.4 IskanderEscrow.sol — Inter-Cooperative Trade Escrow

**Path**: `contracts/src/IskanderEscrow.sol`
**Inheritance**: `ReentrancyGuard`

**Escrow Lifecycle**: `Active → Released | Disputed → Arbitrated | Expired`

**Functions**: `createEscrow`, `confirmDelivery`, `dispute`, `executeVerdict`, `claimExpiry`

**CRITICAL INVARIANT**: Only `ArbitrationRegistry` can call `executeVerdict()`. Only escrow parties can call `dispute()` and `claimExpiry()`.

---

### 3.5 CoopFiatToken.sol — 1:1 Fiat-Backed ERC-20

**Path**: `contracts/src/finance/CoopFiatToken.sol`
**Inheritance**: `ERC20`

**Functions**: `mint(address, uint256, string bankReference)` — onlyBankOracle | `burn(address, uint256, string bankReference)` — onlyBankOracle | `setBankOracle(address)` — onlyGovernance

**CRITICAL INVARIANT**: Only `bankOracle` can mint/burn. NOT fractional reserve. NOT algorithmic stablecoin. 1:1 backed by insured fiat in regulated cooperative bank trust account.

---

### 3.6 ArbitrationRegistry.sol — Solidarity Court

**Path**: `contracts/src/ArbitrationRegistry.sol`

**Case Lifecycle**: `openCase → recordVerdict` (+ automatic `slashTrust` on CoopIdentity)

**Verdict Outcomes**: `BuyerFavored | SellerFavored | Split | Dismissed`

---

### 3.7 InternalPayroll.sol — Mondragon Pay Ratio Enforcement

**Path**: `contracts/src/InternalPayroll.sol`

**Key Constraint**: `maxRatioScaled` enforces maximum pay ratio (default 600 = 6:1 highest:lowest). Any payment exceeding `lowestBasePay * maxRatioScaled / 100` reverts with `PayRatioExceeded`.

---

### 3.8 Constitution.sol — Immutable Genesis Anchor

**Path**: `contracts/src/governance/Constitution.sol`
**Purpose**: Minimal immutable on-chain record anchoring a cooperative's genesis moment. Deployed once per cooperative, never upgradeable.

**State Variables**:
| Variable | Type | Mutability | Purpose |
|----------|------|------------|---------|
| `genesisCIDHash` | `bytes32` | immutable | keccak256 of the IPFS CID containing the ratified GovernanceManifest |
| `constitutionCIDHash` | `bytes32` | immutable | keccak256 of the IPFS CID containing the constitutional document |
| `ratifiedAt` | `uint256` | immutable | Block timestamp of genesis ratification |
| `founderCount` | `uint8` | immutable | Number of founding members who ratified |
| `coopIdentity` | `address` | immutable | Address of the CoopIdentity SBT contract (`address(0)` for solo nodes) |

**Functions**:
| Function | Visibility | Description |
|----------|-----------|-------------|
| `constructor(bytes32, bytes32, uint8, address)` | — | Sets all immutable state; `ratifiedAt = block.timestamp` |
| `verify(bytes32 candidateCID)` | view | Returns true if `keccak256(candidateCID) == genesisCIDHash` |

**Events**: `GenesisRatified(bytes32 genesisCIDHash, bytes32 constitutionCIDHash, uint8 founderCount, uint256 ratifiedAt)`

**CRITICAL INVARIANT**: All state is immutable. No admin functions, no upgrade path. The genesis record is permanent.

---

### 3.8b CoopIdentity.sol — Genesis Extension

**Modification** to existing `CoopIdentity.sol` (§3.1):

| Function | Visibility | Modifier | Description |
|----------|-----------|----------|-------------|
| `setConstitution(address)` | external | onlySteward | One-shot: links CoopIdentity to Constitution.sol. Reverts if already set. |

**State Addition**: `constitution` (address, public) — set once by `setConstitution()`, immutable thereafter.

**CRITICAL INVARIANT**: `setConstitution()` can only be called once. Second call reverts `ConstitutionAlreadySet`.

---

### 3.9 Deploy.s.sol — Foundry Deployment Script

**Path**: `contracts/script/Deploy.s.sol`
**Deployment Order**:
1. CoopIdentity (with BrightID)
2. InternalPayroll
3. IskanderEscrow (address(0) ArbitrationRegistry, wired post-deploy)
4. ArbitrationRegistry
5. Cross-contract wiring (`setArbitrationRegistry`)
6. MACIVoting
7. StewardshipLedger
8. Constitution (deployed by genesis graph; `coopIdentity=address(0)` for solo nodes)
9. Cross-contract wiring (`CoopIdentity.setConstitution(constitution_address)`)
10. Write `script/deployment.json` artifact

**Environment Variables**: `DEPLOYER_PRIVATE_KEY` (required), `COOP_NAME`, `LEGAL_WRAPPER_CID`, `STEWARD_ADDRESS`, `MAX_PAY_RATIO_SCALED`, `BRIGHTID_VERIFIER`, `MACI_COORDINATOR`, `SNARK_VERIFIER`, `MACI_QUORUM_BPS`, `STEWARDSHIP_ORACLE`, `STEWARD_THRESHOLD_BPS`, `SOLVENCY_FACTOR_BPS`

---

## 4. BACKEND

**Entry Point**: `backend/main.py` → `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
**Framework**: FastAPI 0.115.0 + LangGraph 0.2.28 + langchain-ollama 0.2.0
**LLM**: OLMo (open-weight, open-data, open-training-code via AI2 Dolma corpus)
**Database**: PostgreSQL + asyncpg + pgvector (768-dim embeddings via nomic-embed-text)

### 4.1 Configuration (`backend/config.py`)

**Class**: `Settings(BaseSettings)` with `.env` file support.

| Category | Key Settings | Defaults |
|----------|-------------|----------|
| **Database** | `database_url` | `postgresql+asyncpg://iskander:changeme_in_prod@localhost:5432/iskander_ledger` |
| **LLM** | `ollama_base_url`, `ollama_model` | `http://localhost:11434`, `olmo` |
| **EVM** | `evm_rpc_url`, `evm_chain_id`, `deployer_private_key` | `http://localhost:8545`, `31337`, `""` |
| **IPFS** | `ipfs_api_url`, `ipfs_gateway_url` | `http://localhost:5001`, `http://localhost:8080` |
| **ActivityPub** | `activitypub_domain`, `activitypub_private_key_pem` | `iskander.local`, `""` |
| **Auth (SIWE+JWT)** | `jwt_secret`, `jwt_algorithm`, `jwt_access_expiry_minutes` | `""`, `HS256`, `1440` |
| **IPD Auditing** | `ipd_cooperation_floor`, `ipd_strategy`, `ipd_forgiveness_rate` | `0.4`, `generous_tft`, `0.1` |
| **Stewardship** | `stewardship_ledger_address`, `steward_threshold_default`, `steward_warning_margin`, `solvency_factor_bps` | `0x0...0`, `0.25`, `0.10`, `10000` |
| **Energy Gate** | `energy_green_battery_pct`, `energy_yellow_battery_pct` | `80`, `20` |
| **Mesh** | `mesh_encryption_key_env` | `ISKANDER_MESH_KEY` |
| **Fiat Bridge** | `cfiat_token_address`, `bank_oracle_address`, `open_banking_api_url`, `cfiat_mint_approval_threshold` | `0x0...0`, `0x0...0`, `http://localhost:9000/api/v1`, `10000` |
| **Genesis** | `genesis_max_founders`, `genesis_token_expiry_hours`, `genesis_max_bylaw_size_kb`, `genesis_regulatory_templates_dir`, `genesis_default_jurisdiction` | `12`, `72`, `512`, `backend/governance/templates`, `UNIVERSAL` |

### 4.2 Authentication (`backend/auth/dependencies.py`)

**Pattern**: Bearer JWT from SIWE (Sign-In with Ethereum) login flow.

```python
@dataclass
class AuthenticatedUser:
    address: str                 # Checksummed Ethereum address
    did: str | None              # W3C DID from CoopIdentity
    role: str                    # "steward", "worker-owner", "associate", "guest"
    member_token_id: int | None  # CoopIdentity SBT token ID
    chain_id: int                # EVM chain ID
```

**Key Dependencies**:
- `get_current_user` — extract + verify JWT → `AuthenticatedUser`
- `require_role(*allowed_roles)` — factory returning dependency that checks role
- `require_steward()` — shorthand for `require_role("steward")`
- `optional_auth` — returns `None` if no token present
- `optional_ws_auth` — WebSocket auth via query parameter

**Login Flow**: `GET /auth/nonce` → `POST /auth/login` (SIWE signature) → JWT pair → `POST /auth/refresh` → `POST /auth/logout`

### 4.3 Glass Box Protocol (`backend/schemas/glass_box.py`)

**CORE INVARIANT**: Every agent action MUST be wrapped in `AgentAction` before any side-effect executes.

```python
class EthicalImpactLevel(str, Enum):
    LOW    = "low"     # Read-only / informational
    MEDIUM = "medium"  # Writes to internal ledger only
    HIGH   = "high"    # Web3 tx draft or external federation message

class AgentAction(BaseModel):
    action_id:      UUID              = Field(default_factory=uuid4)
    agent_id:       str               # e.g. "steward-agent-v1"
    action:         str               # Short imperative description
    rationale:      str               # WHY the agent chose this action
    ethical_impact: EthicalImpactLevel
    payload:        dict[str, Any] | None
```

Stored verbatim in `agent_actions` table; NEVER truncated.

### 4.4 Genesis Schemas (`backend/schemas/genesis.py`)

**GenesisMode Enum**: `SOLO_NODE | LEGACY_IMPORT | NEW_FOUNDING`

**GovernanceTier Enum**: `CONSTITUTIONAL | OPERATIONAL | REGULATORY`

**Key Models**:
| Model | Purpose | Key Fields |
|-------|---------|------------|
| `GenesisBootRequest` | Start genesis flow | `mode (GenesisMode)`, `owner_did (str)`, `coop_name (str \| None)` |
| `FounderRegistration` | Register co-founder | `did (str)`, `display_name (str)`, `role_preference (str)` |
| `BylawUpload` | Upload existing bylaws | `content_base64 (str)`, `jurisdiction (str)` |
| `RuleMapping` | Extracted rule slot | `slot_id (str)`, `source_text (str)`, `confidence (float)`, `governance_tier (GovernanceTier)` |
| `MappingConfirmation` | Founder confirms/edits mapping | `founder_did (str)`, `slot_id (str)`, `approved (bool)`, `override_value (str \| None)` |
| `GenesisRatification` | Founder signs off | `founder_did (str)`, `approved (bool)`, `rationale (str)` |
| `GenesisStatusResponse` | Genesis thread status | `thread_id (str)`, `mode (GenesisMode)`, `phase (str)`, `founders_registered (int)`, `action_log (list)` |

### 4.5 Governance Compliance (`backend/governance/compliance.py`)

**PolicyRule Metadata Extension**: The existing `PolicyRule` model gains a `metadata: dict[str, Any]` field. Rules with `metadata["_regulatory"] = True` constitute the Regulatory Layer — a permanent jurisdictional floor that can only be tightened, never relaxed.

**RegulatoryUpdateSeverity Enum**: `TIGHTEN | RELAX | NEUTRAL`

**Regulatory Templates**: JSON files in `backend/governance/templates/` (e.g., `UNIVERSAL.json`, `GB.json`, `ES.json`) define baseline rules per jurisdiction. These are injected during genesis and cannot be weakened post-genesis.

---

## 5. DATABASE SCHEMA

**File**: `infra/init.sql` | **30+ tables across 26 phases**

### Core Tables

| Table | Phase | Purpose | Key Columns |
|-------|-------|---------|-------------|
| `agent_actions` | Core | Glass Box audit log | `agent_id, action, rationale, ethical_impact, payload JSONB` |
| `evm_reverts` | Core | EVM revert log | `tx_hash, contract, reason, agent_action_id FK` |
| `contributions` | 9 | DisCO contributory accounting | `member_did, stream CHECK(livelihood/care/commons), care_score, zk_proof` |
| `pending_transactions` | Core | Safe multi-sig HITL queue | `safe_address, to_address, value_wei, status CHECK(pending/approved/rejected/executed)` |
| `agent_job_descriptions` | 10 | AJD spawner | `agent_id UNIQUE, permissions JSONB, budget_limit_wei, ethical_ceiling CHECK(LOW/MEDIUM/HIGH)` |
| `democratic_precedents` | 11 | RAG memory (pgvector) | `embedding vector(768), decision_type, vote_result` |
| `zk_vote_tallies` | 12 | ZK-democracy tallies | `proposal_id, yes/no/abstain_votes, tally_commitment_root, zk_proof` |
| `app_deployments` | 13 | Democratic app store | `docker_image, container_id, status CHECK(proposed/approved/running/stopped/failed/removed)` |
| `matrix_room_bridges` | 14A | Matrix federation | `room_id, room_type CHECK(general/governance/treasury/steward/secretary)` |
| `federation_inbox/outbox` | 14B | ActivityPub federation | `activity_id UNIQUE, activity_type, raw_activity JSONB` |
| `escrow_contracts` | 15 | Escrow mirror | `escrow_id UNIQUE, buyer_coop, seller_coop, status CHECK(Active/Released/Disputed/Arbitrated/Expired)` |
| `arbitration_cases` | 15 | Solidarity court | `case_id UNIQUE, jurisdiction CHECK(intra_coop/inter_coop), outcome` |
| `trust_score_history` | 15 | Trust score audit | `member_address, event_type CHECK(slash/restore/initial), delta, new_score` |
| `interaction_history` | 18 | IPD game theory | `node_a, node_b, node_a_action CHECK(cooperate/defect), escrow_outcome` |
| `reputation_scores` | 18 | Cached reputation | `node_did UNIQUE, cooperation_ratio, on_chain_trust_score` |
| `pairwise_cooperation` | 18 | GTfT cooperation cache | `node_a, node_b, mutual_cooperate, mutual_defect` |
| `credit_accounts` | 19 | Custodial treasury | `member_did UNIQUE, balance NUMERIC CHECK>=0, is_on_chain` |
| `credit_transactions` | 19 | Credit audit trail | `tx_type CHECK(deposit/withdrawal/transfer/conversion_to_chain/conversion_from_chain)` |
| `hitl_notifications` | 20 | HITL routing | `proposal_type CHECK(governance/treasury/steward/arbitration/ipd), route CHECK(activitypub/local_db)` |
| `model_upgrade_proposals` | 21 | Democratic AI upgrades | `hardware_snapshot JSONB, status CHECK(hardware_rejected/pending_vote/approved_pulling/pull_complete/pull_failed_rollback)` |
| `fiat_settlements` | 22 | Fiat settlement links | `settlement_action CHECK(held_on_chain/offramped)` |
| `impact_scores` | 23 | Stewardship scores | `node_did, impact_score NUMERIC(5,4), is_eligible_steward, pushed_on_chain` |
| `delegation_events` | 23 | Delegation mirror | `event_type CHECK(delegate/revoke/auto_revoke)` |
| `steward_threshold_history` | 23 | Threshold audit | `threshold_value, proposed_by, rationale` |
| `council_rationale` | 23 | Council Glass Box | `rationale_ipfs_cid, ccin_principles TEXT[]` |
| `veto_records` | 23 | Emergency veto | `cited_principles TEXT[], status CHECK(filed/under_review/upheld/dismissed)` |
| `energy_events` | 24 | Energy state log | `level CHECK(GREEN/YELLOW/RED), previous_level, action_taken` |
| `causal_events` | 25 | IPFS event log | `ipfs_cid, audience CHECK(federation/council/node), on_chain_anchor` |
| `mesh_sync_log` | 25 | Delta-sync log | `peer_did, direction CHECK(push/pull), status CHECK(pending/synced/denied/failed)` |
| `fiat_operations` | 26 | Mint/burn audit | `operation_type CHECK(mint/burn), solvency_ratio, status CHECK(proposed/approved/executed/failed)` |
| `solvency_snapshots` | 26 | Solvency audit | `fiat_reserve, cfiat_supply_wei, solvency_ratio, circuit_breaker_active` |
| `genesis_state` | Genesis | Genesis boot state | `thread_id UNIQUE, mode CHECK(SOLO_NODE/LEGACY_IMPORT/NEW_FOUNDING), phase TEXT, owner_did TEXT, manifest_cid TEXT, constitution_address TEXT, completed_at TIMESTAMPTZ` |
| `founder_registrations` | Genesis | Founding member records | `thread_id FK, did TEXT, display_name TEXT, role_preference TEXT, token_hash TEXT, confirmed BOOLEAN, registered_at TIMESTAMPTZ` |
| `regulatory_updates` | Genesis | Regulatory floor audit trail | `id UUID PK, rule_id TEXT, severity CHECK(TIGHTEN/RELAX/NEUTRAL), previous_value TEXT, new_value TEXT, changed_by TEXT, agent_action_id FK, created_at` |

**CRITICAL INVARIANT**: `zk_vote_tallies` stores ONLY aggregate tallies + ZK proofs. NO individual votes are ever stored. Privacy is cryptographic, not policy-based.

**CRITICAL INVARIANT**: `fiat_transfer_drafts.status` starts as `'drafted'` — AI NEVER sets it to `'executed'`. Only human-approved transfers reach execution.

---

## 6. AGENT SYSTEM

All agents use LangGraph `StateGraph` with `MemorySaver` checkpointer. HITL is implemented via `interrupt_before` on approval nodes.

### 6.1 Agent State Types (`backend/agents/state.py`)

**Base**: `AgentState(TypedDict)` — `messages`, `agent_id`, `action_log`, `error`

| State Class | Phase | Key Fields |
|------------|-------|------------|
| `InventoryState` | Core | `resources, rea_report` |
| `ContributionState` | Core | `raw_contribution, classified_stream, ledger_entry` |
| `ContributionStateV2` | 9 | `+ care_score, conflict_resolution, requires_human_token` |
| `GovernanceState` | Core | `proposal, safe_tx_draft, hitl_approved, rejection_reason` |
| `SecretaryState` | 9 | `meeting_transcript, summary, consensus_items, activitypub_broadcast` |
| `TreasuryState` | 9 | `payment_request, mondragon_check, safe_tx_draft, requires_human_token` |
| `ProcurementState` | 9 | `purchase_request, vendor_candidates, rea_order` |
| `ProvisionerState` | 13 | `app_request, catalog_matches, deployment_spec, container_id, admin_credentials` |
| `ICAVettingState` | 17 | `candidate_partners, principle_assessments, value_matrix, ipd_predictions` |
| `ArbitrationState` | 15 | `dispute, evidence, jury_pool, verdict, escrow_id, case_id, jurisdiction` |
| `IPDAuditState` | 18 | `partner_did, audit_mode, cooperation_probability, payoff_matrix, recommended_strategy` |
| `StewardshipCouncilState` | 23 | `target_nodes, impact_scores, current_threshold, proposed_threshold, anticipatory_warnings` |
| `FiatGatewayState` | 26 | `reserve_balance, on_chain_supply, solvency_ratio, proposed_action, proposed_amount` |
| `BootState` | Genesis | `mode, owner_did, owner_profile, coop_name, founders, bylaw_text, jurisdiction, extracted_rules, ambiguous_rules, template_id, novel_field_proposals, regulatory_rules, manifest_draft, manifest_cid, constitution_address, ratifications, mapping_confirmations, founder_tokens, genesis_complete` |

### 6.2 Agents

| Agent | ID | Graph Nodes | HITL Gate |
|-------|-----|-------------|-----------|
| Stewardship Scorer | `stewardship-scorer-v1` | `aggregate_contributions → fetch_ethical_audit → compute_impact_scores → evaluate_steward_eligibility → propose_threshold_update → [human_review_threshold] → push_scores_to_chain` | Yes: threshold changes |
| Fiat Gateway | `fiat-gateway-v1` | `check_reserve → evaluate_solvency → propose_action → [hitl_gate] → execute_on_chain` | Yes: mints above threshold |
| Steward v2 | `steward-agent-v2` | Contribution classification + care score quantification | Yes: conflict resolution |
| Secretary | `secretary-agent` | Meeting summary + consensus extraction + ActivityPub broadcast | No |
| Treasurer | `treasurer-agent` | Payment request + Mondragon check + Safe tx draft | Yes: all payments |
| Procurement | `procurement-agent` | Purchase request + vendor search + REA order | No |
| Provisioner | `provisioner-agent-v1` | App request → catalog → deploy → proxy → credentials | Yes: all deployments |
| ICA Vetter | `ica-vetter-v1` | Partner intake → on/off-chain signals → ICA principles → value matrix | Yes: any FAIL score |
| Arbitrator | `arbitrator-agent` | Dispute → jurisdiction → jury → verdict → remedy | Yes: MANDATORY jury |
| IPD Auditor | `ipd-auditor-v1` | History → signals → P(coop) → payoff → strategy | Yes: P(coop) < floor |
| Genesis Initializer | `genesis-initializer-v1` | select_mode → [solo: collect_owner → inject_reg → configure_solo → validate → owner_review → execute_solo] [coop: register_founders → deploy_identity → deploy_safe → extract/browse → inject_reg → compile → validate → confirm_mappings → propose_novel → ratify → execute_genesis] | Yes: owner_review, confirm_mappings, ratify_genesis |

**Impact Score Formula** (stewardship-scorer):
```
Impact_Score = (Historical_Contribution_Value / Ecosystem_Total_Value) * Ethical_Audit_Score
```
- `Historical_Contribution_Value`: sum of member's `care_score + value_tokens` from `contributions`
- `Ethical_Audit_Score`: `cooperation_ratio` from IPD Auditor, normalized [0.0, 1.0]
- On-chain: stored as basis points (0-10000); Python: float (0.0-1.0)

**IPD Strategy**: Generous Tit-for-Tat (GTfT) — start cooperative, mirror partner's last move, forgive defections with probability `ipd_forgiveness_rate` (default 10%).

---

## 7. API SURFACE

### Registered Routers in `main.py` (29 total)

| Router | Prefix | Phase | Auth | Key Endpoints |
|--------|--------|-------|------|---------------|
| `constitution` | `/constitution` | Core | — | Constitutional dialogue |
| `federation` | `/federation` | 14B | — | ActivityPub inbox/outbox |
| `governance` | `/governance` | Core | steward | Proposal submission |
| `inventory` | `/inventory` | Core | worker-owner | REA resource management |
| `power` | `/power` | Core | — | Energy state management |
| `secretary` | `/secretary` | 9 | worker-owner | Meeting summaries |
| `treasury` | `/treasury` | 9 | steward | Payment requests |
| `steward_v2` | `/steward` | 9 | worker-owner | Contribution recording |
| `procurement` | `/procurement` | 9 | worker-owner | Vendor sourcing |
| `spawner` | `/spawner` | 10 | steward | Agent job descriptions |
| `appstore` | `/appstore` | 13 | worker-owner | App deployment |
| `matrix_admin` | `/matrix` | 14A | steward | Room bridging |
| `escrow` | `/escrow` | 15 | worker-owner | Inter-coop trade |
| `arbitration` | `/arbitration` | 15 | worker-owner | Solidarity court |
| `tasks` | `/tasks` | Core | — | Task management |
| `ws_router` | `/ws` | Core | optional | WebSocket events |
| `ica_vetting` | `/ica-vetting` | 17 | worker-owner | Ethics vetting |
| `brightid` | `/api/brightid` | 17 | — | BrightID sponsorship |
| `legal` | `/api/legal` | 17 | — | Ricardian generator |
| `ipd_audit` | `/ipd-audit` | 18 | worker-owner | Game theory auditing |
| `auth` | `/auth` | 19 | — | SIWE + JWT login |
| `credits` | `/credits` | 19 | worker-owner | Internal credit system |
| `system_capabilities` | `/api/system` | 21 | — | Hardware capabilities |
| `model` | `/api/models` | 21 | steward | Model lifecycle |
| `stewardship` | `/stewardship` | 23 | worker-owner/steward | Delegation & scoring |
| `mesh` | `/mesh` | 25 | worker-owner/steward | IPFS & causal events |
| `fiat` | `/fiat` | 26 | steward | cFIAT mint/burn |
| `genesis` | `/genesis` | Genesis | mixed | Genesis boot sequence |

### Genesis Router Detail (`/genesis`)

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| POST | `/boot` | — (unauthenticated) | Start genesis flow (returns thread_id + founder token) | Planned |
| GET | `/status/{thread_id}` | founder_token | Get genesis progress | Planned |
| POST | `/founders/register` | founder_token | Register a co-founder | Planned |
| POST | `/founders/confirm` | founder_token | Founder confirms registration phase | Planned |
| POST | `/bylaws/upload` | founder_token | Upload existing bylaws for rule extraction | Planned |
| GET | `/templates` | founder_token | Browse regulatory templates | Planned |
| POST | `/templates/select` | founder_token | Select a regulatory template | Planned |
| POST | `/mappings/confirm` | founder_token | Confirm/edit extracted rule mappings | Planned |
| POST | `/novel-fields/propose` | founder_token | Propose novel governance fields | Planned |
| POST | `/ratify` | founder_token | Cast ratification vote (N-of-N required at genesis) | Planned |
| POST | `/review/owner` | founder_token | HITL resume: solo owner review | Planned |
| POST | `/review/mappings` | founder_token | HITL resume: mapping confirmation | Planned |
| POST | `/review/ratify` | founder_token | HITL resume: ratification | Planned |
| GET | `/manifest/{thread_id}` | founder_token | Retrieve compiled manifest CID | Planned |

**Auth Model**: Founder tokens — `secrets.token_urlsafe(32)`, bcrypt-hashed, stored in `founder_registrations.token_hash`. Issued at `/boot` and `/founders/register`. Rotated on `/founders/confirm`. NOT JWT — genesis happens before SIWE identity is established.

### Stewardship Router Detail (`/stewardship`)

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| POST | `/compute-scores` | steward | Trigger StewardshipScorer agent | Implemented (invokes graph) |
| GET | `/scores` | worker-owner, steward | List all Impact Scores | STUB (returns []) |
| GET | `/scores/{node_did}` | worker-owner, steward | Single node score | STUB (returns 404) |
| POST | `/delegate` | worker-owner, steward | Submit delegation | STUB (no on-chain tx) |
| POST | `/revoke` | worker-owner, steward | Revoke delegation | STUB |
| GET | `/voting-weight/{address}` | worker-owner, steward | Read on-chain weight | STUB (returns 1) |
| POST | `/veto` | worker-owner, steward | File emergency veto | STUB |
| POST | `/rationale` | steward | Submit Council rationale | STUB |
| GET | `/eligible-stewards` | worker-owner, steward | List eligible stewards | STUB |
| POST | `/threshold/review` | steward | HITL threshold approval | Implemented (resumes graph) |

### Fiat Router Detail (`/fiat`)

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| POST | `/mint` | steward | cFIAT mint proposal | Implemented (invokes graph) |
| POST | `/burn` | steward | cFIAT burn proposal | Implemented (invokes graph) |
| GET | `/reserve` | worker-owner, steward | Bank reserve balance | Calls OpenBankingClient |
| GET | `/solvency` | worker-owner, steward | Solvency status | Calls SolvencyOracle |

### Mesh Router Detail (`/mesh`)

| Method | Path | Auth | Description | Status |
|--------|------|------|-------------|--------|
| POST | `/pin` | worker-owner, steward | Pin encrypted data to IPFS | Implemented (in-memory) |
| GET | `/cat/{cid}` | worker-owner, steward | Retrieve + decrypt by CID | Implemented (in-memory) |
| POST | `/events` | steward | Create causal event | Implemented |
| GET | `/events` | worker-owner, steward | List events | STUB (returns []) |
| POST | `/sync` | steward | Trigger delta-sync | STUB (logs + returns success) |

---

## 8. SECURITY MODEL

### Role-Based Access Control

| Role | Source | Capabilities |
|------|--------|-------------|
| `steward` | CoopIdentity SBT + Safe multi-sig | Full admin: deploy, mint/burn, threshold changes, rationale submission |
| `worker-owner` | CoopIdentity SBT | Read access, delegation, contribution recording, veto filing |
| `associate` | CoopIdentity SBT | Limited read access |
| `guest` | No SBT | Public endpoints only |

### On-Chain Access Control

| Modifier | Used By | Mechanism |
|----------|---------|-----------|
| `onlySteward` | CoopIdentity, InternalPayroll | `msg.sender == steward` (Safe multi-sig) |
| `onlyMember` | StewardshipLedger | `coopIdentity.balanceOf(msg.sender) > 0` |
| `onlyOracle` | StewardshipLedger | `msg.sender == oracle` |
| `onlyCoordinator` | MACIVoting | `msg.sender == coordinator` |
| `onlyBankOracle` | CoopFiatToken | `msg.sender == bankOracle` |
| `onlyArbitrationRegistry` | CoopIdentity, IskanderEscrow | `msg.sender == arbitrationRegistry` |
| `onlyOperator` | ArbitrationRegistry | `msg.sender == operator` (Safe multi-sig) |

### Security Invariants

1. **AI NEVER moves fiat**: `open_banking_client.py` only drafts transfers. Human OAuth approval required.
2. **AI NEVER mints/burns tokens autonomously**: All operations require HITL when above threshold.
3. **Revoke is unstoppable**: `StewardshipLedger.revoke()` has zero external calls, zero reverts (except no-delegation check).
4. **Private keys never in config defaults**: `deployer_private_key`, `jwt_secret`, `treasury_private_key` all default to `""`.
5. **SBT is non-transferable**: `transferFrom`, `approve`, `setApprovalForAll` all revert unconditionally.
6. **Votes are private**: ZK-SNARK MACI — no individual votes stored anywhere.
7. **Trust slash is court-only**: Only `ArbitrationRegistry` can call `slashTrust()`. Agents cannot.

### Personal Node as Cooperative Interface

Members who operate a personal Iskander solo node can use it as a unified client to aggregate all their cooperative memberships. This eliminates the need for separate logins per cooperative while maintaining sovereignty.

**Key Properties**:
- **SOLO_NODE genesis** creates a personal Constitution.sol with `coopIdentity=address(0)` — no cooperative dependency
- **MembershipContext** (future schema): aggregates cooperative memberships under one node, with per-cooperative credential delegation
- **Mid-membership introduction**: A member who initially joined a cooperative directly (via SIWE) can later introduce a personal solo node as their interface. The node assumes the member's existing credentials via a one-time SIWE-signed delegation. The cooperative sees no difference — all API calls still authenticate via the member's DID.
- **Fallback**: If a personal node goes offline, the member falls back to direct SIWE login against the cooperative node. No data loss — the cooperative's state is authoritative. The personal node is a convenience layer, not a dependency.
- **Additive only**: Acquiring a personal node never invalidates existing cooperative membership. Solo Constitution and cooperative Constitution are independent records.

**Scope**: Architectural intent documented here. Full `MembershipContext` schema, credential delegation flow, and node-offline detection are deferred to a dedicated spec.

---

## 9. ENERGY-AWARE SCHEDULING

**Path**: `backend/energy/` — 4 modules

### 9.1 HearthInterface (`hearth_interface.py`)

Singleton hardware sensor reading battery via `psutil.sensors_battery()`. Gracefully defaults to GREEN on desktops/VMs.

**Tri-State Logic**:
| Level | Trigger | Int Value |
|-------|---------|-----------|
| GREEN | Battery > 80% OR AC connected | 2 |
| YELLOW | Battery 20%-80% (on battery) | 1 |
| RED | Battery < 20% (on battery) | 0 |

State transitions emit `AgentAction` with `EthicalImpactLevel.LOW`.

### 9.2 ResourcePolicyEngine (`resource_policy_engine.py`)

Pure state machine — no side effects. Maps `EnergyLevel` → `ExecutionPolicy`.

```python
@dataclass(frozen=True)
class ExecutionPolicy:
    allowed_agents: list[str]   # ["*"] = all, ["secretary", "treasurer"] = restricted
    model_id: str               # LLM model to use at this level
    network_replication: bool   # Can sync IPFS CIDs to peers?
    batch_non_urgent: bool      # Should non-urgent tasks be queued?
    inference_allowed: bool     # Can LLM inference run at all?
```

| Level | Allowed Agents | Model | Network | Inference |
|-------|---------------|-------|---------|-----------|
| GREEN | `["*"]` (all) | `claude-opus-4-6` | Yes | Yes |
| YELLOW | `["secretary", "treasurer", "steward"]` | `claude-sonnet-4-6` | Yes | Yes |
| RED | `["heartbeat"]` | `claude-haiku-4-5-20251001` | No (SOS only) | **No** |

### 9.3 Governor (`governor.py`)

**Decorator**: `@energy_gated_execution(min_level=EnergyLevel.YELLOW, agent_id="treasurer")`

Pre-flight checks:
1. Current energy level ≥ `min_level`?
2. If not GREEN: is `agent_id` in `policy.allowed_agents`?
3. Rejection raises `EnergyGateRejected` with diagnostic message (includes mesh offload suggestion at RED)

Works with both sync and async callables.

### 9.4 TaskQueuer (`task_queuer.py`)

Singleton priority queue (`heapq` min-heap). Defers non-critical tasks at YELLOW/RED, processes on GREEN transition.

- `enqueue(task_id, callback, priority, is_critical)` — add to queue
- `process_queue()` — drain queue per energy policy (critical tasks also run at YELLOW)
- `flush()` — emergency discard all pending tasks

---

## 10. MESH ARCHIVE

**Path**: `backend/mesh/` — 4 modules

### 10.1 SovereignStorage (`sovereign_storage.py`)

Singleton IPFS wrapper with Fernet encryption per-audience.

- `pin(payload: bytes, audience: str)` → `(cid, AgentAction)` — encrypt + pin
- `cat(cid: str)` → `(plaintext, AgentAction)` — retrieve + decrypt
- `ls()` → list of stored CIDs

**Current**: In-memory store with SHA-256-derived fake CIDs (IPFS operations stubbed).
**Encryption**: Real Fernet encryption using key from `settings.mesh_encryption_key_env` env var.

### 10.2 Access Middleware (`access_middleware.py`)

**Decorator**: `@requires_access(token_type='steward')`

Currently stubbed — always allows access with warning log. Production: validates requester's gSBT via `CoopIdentity.balanceOf()`.

Raises `AccessDenied(token_type, requester)` on failure.

### 10.3 CausalEvent (`causal_event.py`)

`CausalEvent.create(event_type, source_agent_id, payload, audience)` → `(CausalEventRecord, AgentAction)`

Serializes payload to JSON, encrypts via `SovereignStorage.pin()`, returns record with `id, event_type, source_agent_id, ipfs_cid, audience, timestamp`.

### 10.4 DeltaSyncProtocol (`delta_sync.py`)

Singleton with `sync_to_peer(peer_did, cids)` and `receive_from_peer(peer_did, cids)`.

Both stubbed (log + return success). Returns `SyncResult(peer_did, direction, cids_synced, cids_denied, timestamp)`.

---

## 11. FIAT-CRYPTO BRIDGE

### 11.1 OpenBankingClient (`backend/finance/open_banking_client.py`)

Singleton stub wrapping PSD2/Open Banking API (Plaid, TrueLayer, etc.).

- `get_fiat_reserve_balance()` → `(FiatReserveBalance, AgentAction)` — STUB returns £25,000
- `draft_fiat_transfer(to_account, amount, currency, reference)` → `(PendingTransfer, AgentAction)` — STUB creates pending draft

**CRITICAL**: AI NEVER has write-access API keys. Only creates drafts requiring human OAuth approval.

### 11.2 SolvencyOracle (`backend/finance/solvency_oracle.py`)

Singleton comparing bank reserve against on-chain cFIAT supply + escrow.

- `check_solvency()` → `(SolvencySnapshot, AgentAction)` — Glass Box HIGH impact
- `push_to_chain()` → updates `StewardshipLedger.updateFiatReserve()` + `updateTotalEscrow()`

```python
@dataclass
class SolvencySnapshot:
    fiat_reserve: Decimal        # From OpenBankingClient
    total_escrow_wei: int        # On-chain (stubbed: 5000)
    cfiat_supply_wei: int        # On-chain (stubbed: 25000)
    solvency_ratio: float        # fiat_reserve / cfiat_supply
    circuit_breaker_active: bool # True if ratio < 1.0
```

### 11.3 Fiat Gateway Agent (`backend/agents/library/fiat_gateway.py`)

AGENT_ID: `fiat-gateway-v1`

**Graph**: `check_reserve → evaluate_solvency → propose_action → [hitl_gate] → execute_on_chain`

- HITL gate triggers when `proposed_amount > settings.cfiat_mint_approval_threshold`
- Every node produces `AgentAction` for Glass Box
- `evaluate_solvency` blocks if `solvency_ratio < 1.0`

---

## 12. CROSS-CUTTING INVARIANTS

These invariants MUST hold across ALL code paths. Violation of any is a critical bug.

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | **Glass Box**: Every agent-initiated side-effect has an `AgentAction` with non-empty `rationale` | All graph nodes produce AgentAction; stored in `action_log` state field |
| 2 | **HITL**: No financial transaction (payment, mint, burn, verdict) executes without human approval | `interrupt_before` on approval nodes; `requires_human_token` state field |
| 3 | **Non-Transferable SBT**: `CoopIdentity.transferFrom()` always reverts | Pure function with `revert TransferProhibited()` |
| 4 | **O(1) Voting Weight**: `getVotingWeight()` never iterates | `hasWeight[node] + receivedDelegations[node]` |
| 5 | **Revoke Safety**: `revoke()` never makes external calls | Only modifies storage; checked in Foundry tests |
| 6 | **Solvency**: cFIAT supply ≤ fiat reserve | Circuit breaker in StewardshipLedger + SolvencyOracle |
| 7 | **Pay Ratio**: No payment exceeds `lowestBasePay * maxRatio / 100` | InternalPayroll `PayRatioExceeded` revert |
| 8 | **Vote Privacy**: No individual votes stored on-chain or off-chain | MACI encrypted messages; only aggregate tallies stored |
| 9 | **AI Never Moves Fiat**: OpenBankingClient only drafts transfers | No write-access API key; `draft_fiat_transfer()` returns `PendingTransfer` |
| 10 | **Energy Survival**: RED state halts all non-critical inference | `@energy_gated_execution` + `ResourcePolicyEngine.RED.inference_allowed = False` |
| 11 | **No Hierarchical Permanence**: Steward roles auto-expire when scores drop | `StewardEligibilityLost` event + anticipatory warnings at 10% margin |
| 12 | **Anti-Extractive**: cFIAT bypasses Visa/MC/Stripe; inter-coop settlement via cooperative bank rails | CoopFiatToken + OpenBankingClient architecture |
| 13 | **Genesis One-Way Latch**: Once `genesis_complete = True`, the genesis graph cannot be re-invoked for that thread | `BootState.genesis_complete` checked at graph entry; Constitution.sol is immutable |
| 14 | **N-of-N Founding Consensus**: All founders must ratify at genesis; M-of-N threshold adopted post-genesis only | `ratify_genesis` node counts `all(r["approved"] for r in ratifications)` |
| 15 | **Regulatory Floor**: Rules marked `_regulatory=True` can only be tightened, never relaxed | `inject_regulatory_layer` node + `compliance.py` enforcement on PolicyEngine updates |
| 16 | **Tombstone-Only Identity**: Constitution.sol state is immutable; `setConstitution()` callable exactly once | Solidity: `require(constitution == address(0))` guard |

---

## 13. KNOWN STUBS AND GAPS

### Stubbed (code exists but returns mock data)

| Component | Current Behavior | Production Requirement |
|-----------|-----------------|----------------------|
| `SovereignStorage.pin/cat` | In-memory dict with fake CIDs | Real IPFS daemon via `ipfshttpclient` |
| `@requires_access` decorator | Always allows; logs warning | Validate gSBT via `CoopIdentity.balanceOf()` |
| `DeltaSyncProtocol.sync_to_peer` | Logs + returns success | Real ActivityPub CID negotiation |
| `OpenBankingClient.get_fiat_reserve_balance` | Returns £25,000 | Real PSD2 API call |
| `OpenBankingClient.draft_fiat_transfer` | Returns mock pending transfer | Real bank API draft |
| `SolvencyOracle` on-chain reads | cFIAT supply = 25000, escrow = 5000 | Real web3 contract calls |
| `/stewardship/scores` GET | Returns `[]` | Query `impact_scores` table |
| `/stewardship/delegate` POST | Returns stub message | Build + submit on-chain `delegate()` tx |
| `/stewardship/veto` POST | Returns stub message | Call `emergencyVeto()` on-chain |
| `/mesh/events` GET | Returns `[]` | Query `causal_events` table |
| All DB writes | Not wired | Need asyncpg connection pool + SQL inserts |

### Genesis Stubs (code planned — not yet implemented)

| Component | Current Behavior | Production Requirement |
|-----------|-----------------|----------------------|
| `deploy_identity` graph node | Returns stub `coopIdentity_address` | Deploy real CoopIdentity.sol via Foundry |
| `deploy_safe` graph node | Returns stub `safe_address` | Deploy real Gnosis Safe multi-sig |
| `execute_genesis_binding` graph node | Pins manifest to in-memory store, returns fake Constitution address | Deploy Constitution.sol on-chain, call `setConstitution()` |
| `execute_solo_genesis` graph node | Pins manifest, returns stub Constitution address | Deploy Constitution.sol with `coopIdentity=address(0)` |
| `browse_templates` / `select_template` | Return hardcoded UNIVERSAL template | Load from `genesis_regulatory_templates_dir` |
| `propose_novel_fields` | Returns empty novel proposals | LLM-powered extraction of unmatched bylaw clauses → KnowledgeAsset proposals |
| Founder token rotation | Token rotated on confirm | Production: add rate limiting, IP binding |

### Not Implemented

| Component | Description | Dependency |
|-----------|-------------|------------|
| **Diplomat Agent** | Cross-federation negotiation for inter-coop agreements | Needs spec; depends on Mesh Archive + Fiat Bridge |
| **DB Connection Pool** | No asyncpg pool wired to routers/agents | All STUB routes need this |
| **Alembic Migrations** | `init.sql` exists but no migration pipeline | Production deployment |
| **Real IPFS Integration** | `ipfshttpclient` calls stubbed | `ipfs_api_url` config exists |
| **Real Web3 Integration** | Contract ABI loading + tx submission stubbed | `web3==7.2.0` in requirements |
| **BrightID Verification** | Sponsor contract + verification flow stubbed | Phase 17 |
| **SNARK Verifier** | `address(0)` placeholder in deployment | Groth16 circuit compilation |

---

## 14. STRESS TEST TARGETS

### Smart Contract Stress Tests

| Test ID | Target | Attack Vector | Expected Behavior |
|---------|--------|---------------|-------------------|
| SC-01 | `StewardshipLedger.delegate()` | Delegate to non-member | Revert `NotAMember` |
| SC-02 | `StewardshipLedger.delegate()` | Delegate to below-threshold steward | Revert `StewardBelowThreshold` |
| SC-03 | `StewardshipLedger.delegate()` | Delegate while circuit breaker active | Revert `CircuitBreakerActive` |
| SC-04 | `StewardshipLedger.revoke()` | Revoke during contract pause/emergency | Must succeed (zero external calls) |
| SC-05 | `StewardshipLedger.updateImpactScores()` | Mismatched array lengths | Revert `ArrayLengthMismatch` |
| SC-06 | `StewardshipLedger.updateImpactScores()` | Score drop below threshold for active steward | Emit `StewardEligibilityLost` |
| SC-07 | `CoopIdentity.transferFrom()` | Transfer SBT between addresses | Revert `TransferProhibited` |
| SC-08 | `CoopFiatToken.mint()` | Non-oracle calls mint | Revert `OnlyBankOracle` |
| SC-09 | `IskanderEscrow.executeVerdict()` | Non-registry calls execute | Revert `NotArbitrationRegistry` |
| SC-10 | `InternalPayroll.pay()` | Payment exceeding Mondragon ratio | Revert `PayRatioExceeded` |
| SC-11 | `MACIVoting.processMessages()` | Invalid ZK proof | Revert `InvalidProof` |
| SC-12 | `StewardshipLedger.getVotingWeight()` | Gas cost with 10,000 delegations | Must remain O(1) |

### Backend Stress Tests

| Test ID | Target | Scenario | Expected Behavior |
|---------|--------|----------|-------------------|
| BE-01 | `@energy_gated_execution` | Call non-critical agent at RED | Raise `EnergyGateRejected` |
| BE-02 | `@energy_gated_execution` | Call critical agent at YELLOW | Allow execution |
| BE-03 | `ResourcePolicyEngine` | Unknown energy level | Default to RED policy |
| BE-04 | `TaskQueuer.process_queue()` | Mix of critical + non-critical at YELLOW | Process only critical |
| BE-05 | `SovereignStorage.pin()` | Pin + cat roundtrip | Decrypt equals original |
| BE-06 | `SolvencyOracle.check_solvency()` | Reserve < supply | `circuit_breaker_active = True` |
| BE-07 | `/fiat/mint` | Mint above threshold | Status = `pending_approval` (HITL) |
| BE-08 | `/stewardship/compute-scores` | Threshold change proposed | Status = `pending_threshold_review` |
| BE-09 | `/stewardship/threshold/review` | Reject threshold change | Status = `threshold_rejected` |
| BE-10 | `require_role("steward")` | Request with worker-owner JWT | HTTP 403 |
| BE-11 | Glass Box Protocol | Any agent action without rationale | Pydantic validation error |
| BE-12 | Concurrent graph invocations | 50 parallel `/compute-scores` | No state cross-contamination (thread_id isolation) |

### Integration Stress Tests

| Test ID | Flow | Steps | Invariant |
|---------|------|-------|-----------|
| INT-01 | Full delegation lifecycle | Register member → set score → delegate → check weight → revoke → check weight | Weight returns to 1 after revoke |
| INT-02 | Solvency circuit breaker | Set escrow > reserve → attempt delegate | Delegation blocked |
| INT-03 | Emergency veto | File veto → check on-chain event → review | Veto recorded with rationale CID |
| INT-04 | Fiat mint + solvency | Check reserve → mint → recheck solvency | Ratio updates correctly |
| INT-05 | Energy state cascade | Force RED → attempt agent → verify queue → force GREEN → verify drain | Tasks queued at RED, processed at GREEN |
| INT-06 | Mesh pin + cat | Pin data with audience=council → cat with authorized user → cat with unauthorized | Authorized succeeds, unauthorized fails |
| INT-07 | Score drop → auto-revoke | Delegate to steward → drop steward score below threshold → verify `StewardEligibilityLost` | Delegators notified, steward loses weight |
| INT-08 | HITL resume flow | Trigger agent with HITL → get thread_id → approve via review endpoint → verify completion | Graph resumes past HITL breakpoint |

### Genesis Stress Tests

| Test ID | Target | Scenario | Expected Behavior |
|---------|--------|----------|-------------------|
| GEN-01 | `Constitution.sol` | Call `verify()` with wrong CID hash | Returns `false` |
| GEN-02 | `CoopIdentity.setConstitution()` | Call twice | Second call reverts `ConstitutionAlreadySet` |
| GEN-03 | Genesis graph | Re-invoke after `genesis_complete = True` | Rejects with error in state |
| GEN-04 | `/genesis/ratify` | One founder rejects | Genesis fails; no Constitution deployed |
| GEN-05 | `/genesis/boot` | Concurrent boot requests | Each gets unique thread_id; no state cross-contamination |
| GEN-06 | Regulatory layer | Attempt to relax `_regulatory=True` rule post-genesis | PolicyEngine rejects with `RegulatoryFloorViolation` |
| GEN-07 | Founder token | Use expired token (>72h) | HTTP 401 |
| GEN-08 | Bylaw extraction | Upload 512KB+ bylaw document | Rejects with `PayloadTooLarge` |
| GEN-09 | Dependency chain | Solo genesis → later join cooperative | Solo Constitution preserved; cooperative membership additive |
| GEN-10 | N-of-N consensus | 12 founders, 11 approve, 1 rejects | Genesis does not proceed |

### Adversarial Tests

| Test ID | Attack | Target | Mitigation |
|---------|--------|--------|------------|
| ADV-01 | Sybil attack | Create multiple identities to accumulate voting weight | BrightID verification + `balanceOf() returns 0 or 1` |
| ADV-02 | Oracle manipulation | Push false Impact Scores | `onlyOracle` modifier; oracle is Safe multi-sig |
| ADV-03 | Circuit breaker bypass | Manipulate `fiatReserveValue` to disable breaker | `onlyOracle` + external bank API verification |
| ADV-04 | Vote buying | Bribe voters in governance proposals | MACI ZK-SNARK prevents knowledge of individual votes |
| ADV-05 | Permanent hierarchy | Accumulate permanent steward status | Auto-expiry when scores drop; no tenure advantage |
| ADV-06 | Extractive fees | Route payments through external processors | cFIAT settles via cooperative bank rails |
| ADV-07 | Data tampering | Modify Glass Box rationale post-facto | CausalEvent CID pinned to IPFS (content-addressed) |
| ADV-08 | Energy denial | Keep node in RED to block governance | SOS broadcast to mesh peers for offload |

---

## FILE MANIFEST

### Smart Contracts (9 files)
```
contracts/src/CoopIdentity.sol
contracts/src/IskanderEscrow.sol
contracts/src/ArbitrationRegistry.sol
contracts/src/InternalPayroll.sol
contracts/src/finance/CoopFiatToken.sol
contracts/src/governance/IStewardshipLedger.sol
contracts/src/governance/StewardshipLedger.sol
contracts/src/governance/MACIVoting.sol
contracts/src/governance/Constitution.sol
```

### Contract Tests (5 files)
```
contracts/test/CoopIdentity.t.sol
contracts/test/IskanderEscrow.t.sol
contracts/test/ArbitrationRegistry.t.sol
contracts/test/InternalPayroll.t.sol
contracts/test/StewardshipLedger.t.sol
```

### Backend — Core (3 files)
```
backend/main.py
backend/config.py
backend/requirements.txt
```

### Backend — Agents (20 files)
```
backend/agents/state.py
backend/agents/library/stewardship_scorer.py
backend/agents/library/fiat_gateway.py
backend/agents/library/steward.py
backend/agents/library/secretary.py
backend/agents/library/treasurer.py
backend/agents/library/procurement.py
backend/agents/library/provisioner.py
backend/agents/library/ica_vetter.py
backend/agents/library/arbitrator.py
backend/agents/library/ipd_auditor.py
backend/agents/library/genesis/initializer_agent.py
backend/agents/library/genesis/rule_extractor.py
backend/agents/core/prompt_stewardship_scorer.txt
backend/agents/core/prompt_fiat_gateway.txt
backend/agents/core/prompt_arbitrator.txt
backend/agents/core/prompt_steward.txt
backend/agents/core/prompt_secretary.txt
backend/agents/core/prompt_treasurer.txt
```

### Backend — Schemas (+ genesis)
```
backend/schemas/genesis.py
```

### Backend — Governance (new)
```
backend/governance/compliance.py
backend/governance/templates/UNIVERSAL.json
backend/governance/templates/GB.json
backend/governance/templates/ES.json
```

### Backend — Routers (23 files)
```
backend/routers/genesis.py
backend/routers/stewardship.py
backend/routers/fiat.py
backend/routers/mesh.py
backend/routers/power.py
backend/routers/constitution.py
backend/routers/federation.py
backend/routers/governance.py
backend/routers/inventory.py
backend/routers/secretary.py
backend/routers/treasury.py
backend/routers/steward_v2.py
backend/routers/procurement.py
backend/routers/spawner.py
backend/routers/appstore.py
backend/routers/matrix_admin.py
backend/routers/escrow.py
backend/routers/arbitration.py
backend/routers/tasks.py
backend/routers/ica_vetting.py
backend/routers/ipd_audit.py
backend/routers/auth.py
backend/routers/credits.py
```

### Backend — Schemas (10 files)
```
backend/schemas/glass_box.py
backend/schemas/stewardship.py
backend/schemas/fiat.py
backend/schemas/fiat_bridge.py
backend/schemas/mesh.py
backend/schemas/arbitration.py
backend/schemas/ipd_audit.py
backend/schemas/hitl.py
backend/schemas/matrix.py
backend/schemas/appstore.py
```

### Backend — Energy (4 files)
```
backend/energy/hearth_interface.py
backend/energy/governor.py
backend/energy/resource_policy_engine.py
backend/energy/task_queuer.py
```

### Backend — Mesh (4 files)
```
backend/mesh/sovereign_storage.py
backend/mesh/access_middleware.py
backend/mesh/causal_event.py
backend/mesh/delta_sync.py
```

### Backend — Finance (2 files)
```
backend/finance/open_banking_client.py
backend/finance/solvency_oracle.py
```

### Backend — Auth (4 files)
```
backend/auth/dependencies.py
backend/auth/jwt_manager.py
backend/auth/siwe.py
backend/auth/web3_provider.py
```

### Infrastructure (2 files)
```
infra/init.sql
contracts/script/Deploy.s.sol
```

---

> **END OF SPECIFICATION**
> Total: ~110 source files | 9 Solidity contracts | 13 LangGraph agents | 29 FastAPI routers | 33+ PostgreSQL tables
> Mission: "To build the Commons, we must first build the sovereign tool."
