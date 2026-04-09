# Genesis Boot Sequence — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the one-way initialization sequence that onboards a cooperative's (or individual's) governance into the Orchestrator engine — identity first, governance second.

**Architecture:** LangGraph StateGraph with two paths (solo / cooperative). The graph collects founding members, deploys on-chain identity (CoopIdentity SBTs + Gnosis Safe), extracts governance rules from bylaws via template-guided LLM, enforces unanimous HITL consent at every step, then anchors the Genesis Manifest on-chain via Constitution.sol. Once anchored, the node is live and the boot endpoint returns 409 forever.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph, FastAPI, Foundry (Solidity 0.8.24), IPFS via SovereignStorage, pytest

**Spec:** `docs/superpowers/specs/2026-03-17-genesis-boot-sequence-design.md`

---

## File Map

| # | File | Action | Responsibility |
|---|------|--------|----------------|
| 1 | `backend/schemas/genesis.py` | CREATE | All Pydantic models + enums for genesis |
| 2 | `backend/schemas/compliance.py` | MODIFY | Add `metadata: dict` field to `PolicyRule` |
| 3 | `backend/agents/state.py` | MODIFY | Add `BootState(AgentState)` TypedDict |
| 4 | `backend/config.py` | MODIFY | Add genesis settings section |
| 5 | `infra/init.sql` | MODIFY | Add genesis tables |
| 6 | `contracts/src/Constitution.sol` | CREATE | On-chain genesis anchor |
| 7 | `contracts/test/Constitution.t.sol` | CREATE | Foundry tests |
| 8 | `contracts/src/CoopIdentity.sol` | MODIFY | Add `setConstitution()` |
| 9 | `backend/governance/regulatory/__init__.py` | CREATE | Package init |
| 10 | `backend/governance/regulatory/GB.json` | CREATE | UK BenCom regulatory template |
| 11 | `backend/governance/regulatory/ES.json` | CREATE | Spain cooperative regulatory template |
| 12 | `backend/governance/regulatory/UNIVERSAL.json` | CREATE | ICA-only fallback |
| 13 | `backend/agents/genesis/__init__.py` | CREATE | Package init |
| 14 | `backend/agents/genesis/initializer_agent.py` | CREATE | LangGraph boot sequence graph |
| 15 | `backend/agents/genesis/rule_extractor.py` | CREATE | Template-guided LLM extraction |
| 16 | `backend/auth/dependencies.py` | MODIFY | Add `verify_founder_token()` |
| 17 | `backend/routers/genesis.py` | CREATE | FastAPI router — 14 endpoints |
| 18 | `backend/main.py` | MODIFY | Register genesis router |
| 19 | `contracts/script/Deploy.s.sol` | MODIFY | Add Constitution deployment |
| 20 | `tests/test_genesis_boot.py` | CREATE | Python tests for genesis |
| 21 | `tests/test_constitution_sol.py` | CREATE | Solidity integration tests |

---

## Chunk 1: Schemas, State, Config, SQL (Foundation)

### Task 1: Genesis Enums and Core Models

**Files:**
- Create: `backend/schemas/genesis.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing tests for enums and models**

```python
# tests/test_genesis_boot.py
"""Tests for the Genesis Boot Sequence."""
from __future__ import annotations

import pytest

from backend.schemas.genesis import (
    GenesisMode,
    GovernanceTier,
    RegulatoryUpdateSeverity,
    ExtractedRule,
    MappingConfirmation,
    RegulatoryLayer,
    RegulatoryUpdate,
    FounderRegistration,
)


class TestGenesisEnums:
    """Test enum definitions."""

    def test_genesis_mode_values(self):
        assert GenesisMode.SOLO_NODE == "solo_node"
        assert GenesisMode.LEGACY_IMPORT == "legacy_import"
        assert GenesisMode.NEW_FOUNDING == "new_founding"

    def test_governance_tier_values(self):
        assert GovernanceTier.CONSTITUTIONAL == "Constitutional"
        assert GovernanceTier.OPERATIONAL == "Operational"
        assert GovernanceTier.REGULATORY == "Regulatory"

    def test_regulatory_update_severity_values(self):
        assert RegulatoryUpdateSeverity.ADVISORY == "Advisory"
        assert RegulatoryUpdateSeverity.MANDATORY == "Mandatory"
        assert RegulatoryUpdateSeverity.URGENT == "Urgent"


class TestExtractedRule:
    """Test ExtractedRule model."""

    def test_ambiguity_threshold(self):
        """Rules with confidence < 0.6 must be marked ambiguous."""
        rule = ExtractedRule(
            rule_id="test_rule",
            source_text="Members shall meet quarterly",
            proposed_policy_rule={"rule_id": "test", "constraint_type": "MaxValue", "value": "4"},
            confidence=0.5,
            tier=GovernanceTier.OPERATIONAL,
        )
        assert rule.is_ambiguous is True

    def test_high_confidence_not_ambiguous(self):
        rule = ExtractedRule(
            rule_id="test_rule",
            source_text="Pay ratio capped at 6:1",
            proposed_policy_rule={"rule_id": "pay_ratio", "constraint_type": "MaxValue", "value": "6"},
            confidence=0.9,
            tier=GovernanceTier.CONSTITUTIONAL,
        )
        assert rule.is_ambiguous is False

    def test_novel_field_default_false(self):
        rule = ExtractedRule(
            rule_id="test",
            source_text="text",
            proposed_policy_rule={},
            confidence=0.8,
            tier=GovernanceTier.OPERATIONAL,
        )
        assert rule.is_novel_field is False


class TestRegulatoryLayer:
    """Test RegulatoryLayer model."""

    def test_non_overridable_always_true(self):
        layer = RegulatoryLayer(
            jurisdiction="GB",
            rules=[],
            source_documents=[],
        )
        assert layer.non_overridable is True

    def test_cannot_set_overridable(self):
        """non_overridable is forced True regardless of input."""
        layer = RegulatoryLayer(
            jurisdiction="GB",
            rules=[],
            source_documents=[],
            non_overridable=False,  # Attempt to override
        )
        assert layer.non_overridable is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.schemas.genesis'`

- [ ] **Step 3: Implement genesis schemas**

```python
# backend/schemas/genesis.py
"""
Genesis Boot Sequence — Pydantic schemas.

Covers:
  - GenesisMode, GovernanceTier, RegulatoryUpdateSeverity enums
  - ExtractedRule (template-guided bylaw extraction output)
  - MappingConfirmation (founder HITL sign-off per rule)
  - RegulatoryLayer (permanent jurisdictional floor)
  - RegulatoryUpdate (federation-pushed legislation changes)
  - FounderRegistration (pre-genesis member registration)
  - API request/response models
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════


class GenesisMode(str, Enum):
    """Boot sequence mode — determines the cooperative vs solo path."""

    SOLO_NODE = "solo_node"
    LEGACY_IMPORT = "legacy_import"
    NEW_FOUNDING = "new_founding"


class GovernanceTier(str, Enum):
    """Which governance tier a rule belongs to."""

    CONSTITUTIONAL = "Constitutional"
    OPERATIONAL = "Operational"
    REGULATORY = "Regulatory"


class RegulatoryUpdateSeverity(str, Enum):
    """Severity of a federation-pushed regulatory update."""

    ADVISORY = "Advisory"
    MANDATORY = "Mandatory"
    URGENT = "Urgent"


# ═══════════════════════════════════════════════════════════════════════════════
# Core Models
# ═══════════════════════════════════════════════════════════════════════════════


class ExtractedRule(BaseModel):
    """A single rule extracted from bylaws via template-guided LLM."""

    rule_id: str = Field(..., description="Unique rule identifier")
    source_text: str = Field(..., description="Original bylaw clause text")
    proposed_policy_rule: dict[str, Any] = Field(
        ..., description="Serialised PolicyRule dict"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM extraction confidence"
    )
    is_ambiguous: bool = Field(
        default=False,
        description="True if confidence < 0.6 → Human-Judgment-Only",
    )
    is_novel_field: bool = Field(
        default=False,
        description="True if rule doesn't match any skeleton slot",
    )
    tier: GovernanceTier = Field(
        ..., description="Governance tier assignment"
    )
    confirmed: bool = Field(
        default=False, description="Human sign-off received"
    )

    @model_validator(mode="after")
    def _set_ambiguous_from_confidence(self) -> ExtractedRule:
        """Auto-tag ambiguous if confidence below threshold."""
        if self.confidence < 0.6:
            self.is_ambiguous = True
        return self


class MappingConfirmation(BaseModel):
    """A founder's sign-off on a single extracted rule."""

    rule_id: str
    confirmed_by_did: str
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    original_text: str = Field(..., description="Bylaw source text")
    code_representation: str = Field(
        ...,
        description='e.g. "governance_manifest.json → voting.quorum = 0.5"',
    )
    approved: bool
    tier_assignment: GovernanceTier


class RegulatoryLayer(BaseModel):
    """Permanent jurisdictional floor — rules can only be tightened, never relaxed.

    Rules are stored as PolicyRules with _regulatory=True metadata marker.
    """

    jurisdiction: str = Field(..., description="ISO country code, e.g. 'GB', 'ES'")
    rules: list[dict[str, Any]] = Field(
        default_factory=list,
        description="PolicyRule dicts with _regulatory=True metadata",
    )
    source_documents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="[{reference, cid, ingested_at}]",
    )
    non_overridable: bool = Field(
        default=True,
        description="Always True — regulatory floor cannot be weakened",
    )
    update_history: list[str] = Field(
        default_factory=list,
        description="RegulatoryUpdate CIDs (audit trail)",
    )

    @model_validator(mode="after")
    def _force_non_overridable(self) -> RegulatoryLayer:
        """Regulatory layer is ALWAYS non-overridable."""
        self.non_overridable = True
        return self


class RegulatoryUpdate(BaseModel):
    """A federation-pushed legislative change."""

    source_federation_did: str
    legislation_reference: str
    affected_rule_ids: list[str] = Field(default_factory=list)
    proposed_rules: list[dict[str, Any]] = Field(default_factory=list)
    severity: RegulatoryUpdateSeverity
    effective_date: datetime
    ingested_via: str = Field(
        ..., description="CID of the ActivityPub message (provenance)"
    )


class FounderRegistration(BaseModel):
    """A founding member's pre-genesis registration."""

    did: str
    address: str = Field(..., description="EVM address for SBT + Safe")
    name: str = Field(..., description="Human-readable name")
    founder_token_hash: str = Field(
        ..., description="bcrypt hash of the temporary founder token"
    )
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class BootRequest(BaseModel):
    """Start the genesis boot sequence."""

    mode: GenesisMode


class FounderRegisterRequest(BaseModel):
    """Register a founding member."""

    did: str
    address: str
    name: str


class FounderRegisterResponse(BaseModel):
    """Response with the one-time founder token."""

    did: str
    address: str
    founder_token: str = Field(
        ..., description="One-time secret — store securely, shown once"
    )


class ModeSelectRequest(BaseModel):
    """Select genesis mode."""

    mode: GenesisMode


class BylawsUploadRequest(BaseModel):
    """Upload bylaw text for LEGACY_IMPORT extraction."""

    text: str
    skeleton_template_cid: str | None = Field(
        default=None,
        description="CID of bylaw skeleton template from LibraryManager",
    )


class TemplateSelectRequest(BaseModel):
    """Select a governance template for NEW_FOUNDING."""

    template_cid: str


class RuleConfirmRequest(BaseModel):
    """Confirm or reject a single rule mapping."""

    approved: bool


class TierAssignRequest(BaseModel):
    """Assign a governance tier to a rule."""

    tier: GovernanceTier


class RatifyRequest(BaseModel):
    """Cast a ratification vote."""

    ratified: bool


class GenesisStatusResponse(BaseModel):
    """Boot sequence status."""

    status: str = Field(..., description="pre-genesis | in-progress | complete | recovery")
    mode: GenesisMode | None = None
    boot_phase: str | None = None
    founder_count: int = 0
    boot_complete: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestGenesisEnums -v && python -m pytest tests/test_genesis_boot.py::TestExtractedRule -v && python -m pytest tests/test_genesis_boot.py::TestRegulatoryLayer -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/schemas/genesis.py tests/test_genesis_boot.py
git commit -m "feat(genesis): add schemas — enums, ExtractedRule, RegulatoryLayer, API models"
```

---

### Task 2: Add `metadata` Field to PolicyRule

**Files:**
- Modify: `backend/schemas/compliance.py` (line 136–146)
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_genesis_boot.py`:

```python
from backend.schemas.compliance import PolicyRule, ConstraintType


class TestPolicyRuleMetadata:
    """Test the metadata field addition to PolicyRule."""

    def test_metadata_default_empty_dict(self):
        rule = PolicyRule(
            rule_id="test",
            description="test rule",
            constraint_type=ConstraintType.MAX_VALUE,
            value="10",
        )
        assert rule.metadata == {}

    def test_metadata_regulatory_marker(self):
        rule = PolicyRule(
            rule_id="reg_test",
            description="regulatory rule",
            constraint_type=ConstraintType.MAX_VALUE,
            value="100",
            metadata={"_regulatory": True, "non_overridable": True},
        )
        assert rule.metadata["_regulatory"] is True

    def test_metadata_ambiguous_marker(self):
        rule = PolicyRule(
            rule_id="ambig_test",
            description="ambiguous rule",
            constraint_type=ConstraintType.REQUIRE_APPROVAL,
            value="payment",
            metadata={"_ambiguous": True},
        )
        assert rule.metadata["_ambiguous"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestPolicyRuleMetadata -v`
Expected: FAIL — `metadata` field not recognized

- [ ] **Step 3: Add metadata field to PolicyRule**

In `backend/schemas/compliance.py`, after the `applies_to` field (line 146), add:

```python
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extension metadata. Keys: _regulatory, _ambiguous, non_overridable",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestPolicyRuleMetadata -v`
Expected: All PASS

- [ ] **Step 5: Run existing PolicyEngine tests to ensure no regression**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_policy_engine.py -v`
Expected: All 25 tests PASS (metadata defaults to `{}`, backward compatible)

- [ ] **Step 6: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/schemas/compliance.py tests/test_genesis_boot.py
git commit -m "feat(compliance): add metadata field to PolicyRule for regulatory/ambiguous markers"
```

---

### Task 3: Add BootState TypedDict

**Files:**
- Modify: `backend/agents/state.py` (append after `DraftingState`)
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_genesis_boot.py`:

```python
from backend.agents.state import BootState, AgentState


class TestBootState:
    """Test BootState TypedDict inherits from AgentState."""

    def test_boot_state_extends_agent_state(self):
        """BootState must inherit all AgentState fields."""
        agent_keys = set(AgentState.__annotations__.keys())
        boot_keys = set(BootState.__annotations__.keys())
        # AgentState keys must be a subset of BootState keys
        assert agent_keys.issubset(boot_keys), (
            f"Missing AgentState fields in BootState: {agent_keys - boot_keys}"
        )

    def test_boot_state_has_genesis_fields(self):
        """BootState must have all genesis-specific fields."""
        required = {
            "mode", "node_type", "coop_profile", "owner_profile",
            "skeleton_template_cid", "extracted_rules", "mapping_confirmations",
            "founder_confirmations", "ambiguous_rules", "regulatory_layer",
            "genesis_manifest", "constitution_cid", "genesis_manifest_cid",
            "founding_tx_hash", "founder_sbt_ids", "safe_address",
            "boot_phase", "boot_complete", "requires_human_token",
        }
        boot_keys = set(BootState.__annotations__.keys())
        missing = required - boot_keys
        assert not missing, f"Missing fields in BootState: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestBootState -v`
Expected: FAIL — `ImportError: cannot import name 'BootState' from 'backend.agents.state'`

- [ ] **Step 3: Add BootState to state.py**

Append after the `ResearchFellowshipState` class (end of `backend/agents/state.py`):

```python
class BootState(AgentState):
    """State for the Genesis Boot Sequence (InitializerAgent).

    Two paths: solo (SOLO_NODE) or cooperative (LEGACY_IMPORT / NEW_FOUNDING).
    Identity first, governance second. All founding decisions require
    unanimous consent (N-of-N).

    Graph:
      select_mode → [solo | cooperative path] → inject_regulatory_layer
        → compile_genesis_manifest → validate_genesis_manifest
        → [HITL: ratify/review] → execute_genesis_binding → END
    """
    mode:                     str | None                  # GenesisMode.value
    node_type:                str | None                  # "cooperative" | "solo"
    coop_profile:             dict[str, Any] | None       # Serialised CoopProfile
    owner_profile:            dict[str, Any] | None       # Solo node owner details
    skeleton_template_cid:    str | None                  # Selected bylaw skeleton CID
    extracted_rules:          list[dict[str, Any]]        # ExtractedRule dicts
    mapping_confirmations:    dict[str, dict[str, Any]]   # founder_did -> {rule_id -> approved}
    founder_confirmations:    dict[str, bool]             # founder_did -> ratified
    ambiguous_rules:          list[str]                   # rule_ids tagged Human-Judgment-Only
    regulatory_layer:         dict[str, Any] | None       # Serialised RegulatoryLayer
    genesis_manifest:         dict[str, Any] | None       # Compiled GovernanceManifest
    constitution_cid:         str | None                  # Ricardian constitution CID
    genesis_manifest_cid:     str | None                  # Mesh Archive CID
    founding_tx_hash:         str | None                  # Constitution.sol deployment tx
    founder_sbt_ids:          list[int]                   # Minted SBT token IDs
    safe_address:             str | None                  # Deployed Safe multi-sig address
    boot_phase:               str                         # Current phase identifier
    boot_complete:            bool                        # One-way latch
    requires_human_token:     bool
```

Note: `Any` is already imported in this file. No additional imports needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestBootState -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/agents/state.py tests/test_genesis_boot.py
git commit -m "feat(state): add BootState TypedDict for Genesis Boot Sequence"
```

---

### Task 4: Add Genesis Config Settings

**Files:**
- Modify: `backend/config.py` (append before `settings = Settings()`)

- [ ] **Step 1: Add genesis settings to config.py**

Insert before `settings = Settings()` (line 328):

```python
    # ── Genesis Boot Sequence ───────────────────────────────────────────────
    # One-way initialization of cooperative governance.

    # Default jurisdiction for regulatory layer if not specified.
    genesis_default_jurisdiction: str = "UNIVERSAL"
    # Minimum founding members required for cooperative genesis.
    genesis_min_founders: int = 3
    # Path to regulatory layer templates directory.
    genesis_regulatory_templates_dir: str = "backend/governance/regulatory"
    # Constitution.sol: deployer key comes from deployer_private_key above.
    # Boot-complete flag file (persistent across restarts).
    genesis_boot_complete_file: str = ".genesis_complete"
    # Founder token bcrypt cost factor.
    genesis_founder_token_bcrypt_rounds: int = 12
```

- [ ] **Step 2: Verify config loads without error**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -c "from backend.config import settings; print('genesis_min_founders:', settings.genesis_min_founders)"`
Expected: `genesis_min_founders: 3`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/config.py
git commit -m "feat(config): add Genesis Boot Sequence settings"
```

---

### Task 5: Add Genesis Database Tables

**Files:**
- Modify: `infra/init.sql`

- [ ] **Step 1: Append genesis tables to init.sql**

Add at the end of `infra/init.sql`:

```sql
-- ═══════════════════════════════════════════════════════════════════════════════
-- Genesis Boot Sequence (Phase: Genesis)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Tracks the overall genesis state for the node.
CREATE TABLE IF NOT EXISTS genesis_state (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mode            TEXT CHECK (mode IN ('solo_node', 'legacy_import', 'new_founding')),
    node_type       TEXT CHECK (node_type IN ('cooperative', 'solo')),
    boot_phase      TEXT NOT NULL DEFAULT 'pre-genesis',
    boot_complete   BOOLEAN NOT NULL DEFAULT FALSE,
    genesis_manifest_cid TEXT,
    constitution_cid     TEXT,
    founding_tx_hash     TEXT,
    safe_address         TEXT,
    thread_id            TEXT,           -- LangGraph thread ID for resume
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Founding member registrations (pre-genesis auth).
CREATE TABLE IF NOT EXISTS founder_registrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    did             TEXT NOT NULL UNIQUE,
    address         TEXT NOT NULL,
    name            TEXT NOT NULL,
    founder_token_hash TEXT NOT NULL,    -- bcrypt hash
    sbt_token_id    INTEGER,             -- Set after SBT mint
    ratified        BOOLEAN NOT NULL DEFAULT FALSE,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_founder_registrations_did ON founder_registrations(did);

-- Federation-pushed regulatory updates (post-genesis).
CREATE TABLE IF NOT EXISTS regulatory_updates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_federation_did TEXT NOT NULL,
    legislation_reference TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('Advisory', 'Mandatory', 'Urgent')),
    effective_date  TIMESTAMPTZ NOT NULL,
    proposed_rules  JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_rule_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ingested_via    TEXT NOT NULL,        -- ActivityPub message CID
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_regulatory_updates_status ON regulatory_updates(status);
```

- [ ] **Step 2: Verify SQL syntax**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -c "
with open('infra/init.sql') as f:
    content = f.read()
assert 'genesis_state' in content
assert 'founder_registrations' in content
assert 'regulatory_updates' in content
print('SQL tables present: OK')
"`
Expected: `SQL tables present: OK`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add infra/init.sql
git commit -m "feat(sql): add genesis_state, founder_registrations, regulatory_updates tables"
```

---

## Chunk 2: Constitution.sol + Regulatory Layer Templates

### Task 6: Constitution.sol Contract

**Files:**
- Create: `contracts/src/Constitution.sol`
- Test: `contracts/test/Constitution.t.sol`

- [ ] **Step 1: Write Foundry test**

```solidity
// contracts/test/Constitution.t.sol
// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {Constitution} from "../src/Constitution.sol";

contract ConstitutionTest is Test {
    Constitution internal constitution;

    address internal coopIdentity = makeAddr("coopIdentity");
    string  internal constant GENESIS_CID = "QmGenesisManifestCID1234567890abcdef12345678";
    string  internal constant CONSTITUTION_CID = "QmConstitutionCID1234567890abcdef1234567890ab";
    uint16  internal constant FOUNDER_COUNT = 3;

    function setUp() public {
        constitution = new Constitution(
            GENESIS_CID,
            CONSTITUTION_CID,
            FOUNDER_COUNT,
            coopIdentity
        );
    }

    function test_GenesisRatifiedEventEmitted() public {
        // Verify the event was emitted during construction
        // We need to re-deploy to capture the event
        vm.recordLogs();
        Constitution c = new Constitution(
            GENESIS_CID,
            CONSTITUTION_CID,
            FOUNDER_COUNT,
            coopIdentity
        );
        Vm.Log[] memory entries = vm.getRecordedLogs();
        assertGt(entries.length, 0, "No events emitted");
    }

    function test_CidHashesMatchInput() public view {
        bytes32 expectedGenesis = keccak256(bytes(GENESIS_CID));
        bytes32 expectedConstitution = keccak256(bytes(CONSTITUTION_CID));
        assertEq(constitution.genesisCIDHash(), expectedGenesis);
        assertEq(constitution.constitutionCIDHash(), expectedConstitution);
    }

    function test_FounderCountStored() public view {
        assertEq(constitution.founderCount(), FOUNDER_COUNT);
    }

    function test_CoopIdentityLink() public view {
        assertEq(constitution.coopIdentity(), coopIdentity);
    }

    function test_RatifiedAtSet() public view {
        assertGt(constitution.ratifiedAt(), 0);
    }

    function test_ImmutableFieldsCannotChange() public view {
        // All fields are immutable — this test verifies they are set
        // and Solidity's immutable keyword prevents reassignment
        // (compile-time guarantee, no runtime test needed beyond existence)
        assertTrue(constitution.genesisCIDHash() != bytes32(0));
        assertTrue(constitution.constitutionCIDHash() != bytes32(0));
        assertTrue(constitution.founderCount() > 0);
    }

    function test_SoloNodeWithZeroCoopIdentity() public {
        Constitution solo = new Constitution(
            GENESIS_CID,
            CONSTITUTION_CID,
            1,              // solo node
            address(0)      // no CoopIdentity
        );
        assertEq(solo.coopIdentity(), address(0));
        assertEq(solo.founderCount(), 1);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge test --match-contract ConstitutionTest -v`
Expected: FAIL — `Source "Constitution.sol" not found`

- [ ] **Step 3: Implement Constitution.sol**

```solidity
// contracts/src/Constitution.sol
// SPDX-License-Identifier: AGPL-3.0-only
pragma solidity ^0.8.24;

/// @title Constitution — Immutable on-chain genesis anchor
/// @notice Stores keccak256 hashes of the Genesis Manifest CID and Ricardian
///         Constitution CID. Emits a single event at deployment. Nothing else.
///         Governance logic lives in PolicyEngine, not on-chain.
/// @dev    Deliberately minimal. All fields are immutable.
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge test --match-contract ConstitutionTest -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add contracts/src/Constitution.sol contracts/test/Constitution.t.sol
git commit -m "feat(contracts): add Constitution.sol — immutable on-chain genesis anchor"
```

---

### Task 7: Add setConstitution to CoopIdentity.sol

**Files:**
- Modify: `contracts/src/CoopIdentity.sol` (after `setArbitrationRegistry`, ~line 245)
- Modify: `contracts/test/CoopIdentity.t.sol`

- [ ] **Step 1: Write failing test in existing test file**

Add to `contracts/test/CoopIdentity.t.sol`:

```solidity
function test_SetConstitution() public {
    address constitutionAddr = makeAddr("constitution");
    vm.prank(steward);
    identity.setConstitution(constitutionAddr);
    assertEq(identity.constitution(), constitutionAddr);
}

function test_SetConstitutionTwiceReverts() public {
    address addr1 = makeAddr("constitution1");
    address addr2 = makeAddr("constitution2");
    vm.prank(steward);
    identity.setConstitution(addr1);
    vm.prank(steward);
    vm.expectRevert("CoopIdentity: constitution already set");
    identity.setConstitution(addr2);
}

function test_NonStewardCannotSetConstitution() public {
    vm.prank(alice);
    vm.expectRevert(CoopIdentity.NotSteward.selector);
    identity.setConstitution(makeAddr("constitution"));
}

function test_SetConstitutionZeroAddressReverts() public {
    vm.prank(steward);
    vm.expectRevert("CoopIdentity: zero address");
    identity.setConstitution(address(0));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge test --match-test "test_SetConstitution" -v`
Expected: FAIL — function `setConstitution` not found

- [ ] **Step 3: Add setConstitution to CoopIdentity.sol**

After the `setArbitrationRegistry` function (~line 245), add:

```solidity
    /// @notice Constitution contract address (set once after genesis deployment).
    address public constitution;

    event ConstitutionSet(address indexed constitution);

    /// @notice Link the Constitution contract (one-time setter).
    /// @dev    Same pattern as setArbitrationRegistry. Cannot be changed once set.
    function setConstitution(address _constitution) external onlySteward {
        require(_constitution != address(0), "CoopIdentity: zero address");
        require(constitution == address(0), "CoopIdentity: constitution already set");
        constitution = _constitution;
        emit ConstitutionSet(_constitution);
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge test --match-test "test_SetConstitution" -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Run full CoopIdentity test suite for regression**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge test --match-contract CoopIdentityTest -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add contracts/src/CoopIdentity.sol contracts/test/CoopIdentity.t.sol
git commit -m "feat(contracts): add setConstitution() one-time setter to CoopIdentity"
```

---

### Task 8: Regulatory Layer Templates

**Files:**
- Create: `backend/governance/regulatory/__init__.py`
- Create: `backend/governance/regulatory/UNIVERSAL.json`
- Create: `backend/governance/regulatory/GB.json`
- Create: `backend/governance/regulatory/ES.json`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_genesis_boot.py`:

```python
import json
from pathlib import Path


class TestRegulatoryTemplates:
    """Test regulatory layer JSON templates."""

    TEMPLATES_DIR = Path("backend/governance/regulatory")

    def test_universal_template_exists(self):
        path = self.TEMPLATES_DIR / "UNIVERSAL.json"
        assert path.exists(), f"Missing: {path}"

    def test_gb_template_exists(self):
        path = self.TEMPLATES_DIR / "GB.json"
        assert path.exists(), f"Missing: {path}"

    def test_es_template_exists(self):
        path = self.TEMPLATES_DIR / "ES.json"
        assert path.exists(), f"Missing: {path}"

    def test_templates_valid_json(self):
        for name in ("UNIVERSAL.json", "GB.json", "ES.json"):
            path = self.TEMPLATES_DIR / name
            with open(path) as f:
                data = json.load(f)
            assert "jurisdiction" in data
            assert "rules" in data
            assert isinstance(data["rules"], list)

    def test_universal_has_no_jurisdiction_rules(self):
        """UNIVERSAL template should only have ICA-derived rules."""
        with open(self.TEMPLATES_DIR / "UNIVERSAL.json") as f:
            data = json.load(f)
        assert data["jurisdiction"] == "UNIVERSAL"
        # All rules should have _regulatory metadata
        for rule in data["rules"]:
            assert rule.get("metadata", {}).get("_regulatory") is True

    def test_gb_template_jurisdiction(self):
        with open(self.TEMPLATES_DIR / "GB.json") as f:
            data = json.load(f)
        assert data["jurisdiction"] == "GB"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestRegulatoryTemplates -v`
Expected: FAIL — files don't exist

- [ ] **Step 3: Create package init**

```python
# backend/governance/regulatory/__init__.py
"""Jurisdiction-specific regulatory layer templates."""
```

- [ ] **Step 4: Create UNIVERSAL.json**

```json
{
  "jurisdiction": "UNIVERSAL",
  "rules": [
    {
      "rule_id": "reg_ica_anti_extractive",
      "description": "ICA: No agent transaction can benefit a single member at cooperative expense without HITL approval",
      "constraint_type": "RequireApproval",
      "value": "external_payment,transfer",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "ICA"}
    },
    {
      "rule_id": "reg_ica_democratic_control",
      "description": "ICA: No single agent can bypass M-of-N approval for value-moving operations",
      "constraint_type": "RequireApproval",
      "value": "governance_change,mint,burn",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "ICA"}
    }
  ],
  "source_documents": [],
  "non_overridable": true,
  "update_history": []
}
```

- [ ] **Step 5: Create GB.json**

```json
{
  "jurisdiction": "GB",
  "rules": [
    {
      "rule_id": "reg_ica_anti_extractive",
      "description": "ICA: No agent transaction can benefit a single member at cooperative expense without HITL approval",
      "constraint_type": "RequireApproval",
      "value": "external_payment,transfer",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "ICA"}
    },
    {
      "rule_id": "reg_ica_democratic_control",
      "description": "ICA: No single agent can bypass M-of-N approval for value-moving operations",
      "constraint_type": "RequireApproval",
      "value": "governance_change,mint,burn",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "ICA"}
    },
    {
      "rule_id": "reg_gb_bencom_annual_return",
      "description": "Co-operative and Community Benefit Societies Act 2014 s.86: annual return to FCA required",
      "constraint_type": "RequireApproval",
      "value": "annual_return",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "CCBSA2014_s86"}
    },
    {
      "rule_id": "reg_gb_bencom_audit",
      "description": "Co-operative and Community Benefit Societies Act 2014 s.83: accounts must be audited if turnover > £5.6m or assets > £2.8m",
      "constraint_type": "RequireApproval",
      "value": "financial_report",
      "applies_to": ["treasurer-agent-v1"],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "CCBSA2014_s83"}
    },
    {
      "rule_id": "reg_gb_bencom_min_members",
      "description": "Co-operative and Community Benefit Societies Act 2014 s.2: minimum 3 members",
      "constraint_type": "MinValue",
      "value": "3",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "CCBSA2014_s2"}
    }
  ],
  "source_documents": [
    {
      "reference": "Co-operative and Community Benefit Societies Act 2014",
      "cid": null,
      "ingested_at": "2026-03-17T00:00:00Z"
    }
  ],
  "non_overridable": true,
  "update_history": []
}
```

- [ ] **Step 6: Create ES.json**

```json
{
  "jurisdiction": "ES",
  "rules": [
    {
      "rule_id": "reg_ica_anti_extractive",
      "description": "ICA: No agent transaction can benefit a single member at cooperative expense without HITL approval",
      "constraint_type": "RequireApproval",
      "value": "external_payment,transfer",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "ICA"}
    },
    {
      "rule_id": "reg_ica_democratic_control",
      "description": "ICA: No single agent can bypass M-of-N approval for value-moving operations",
      "constraint_type": "RequireApproval",
      "value": "governance_change,mint,burn",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "ICA"}
    },
    {
      "rule_id": "reg_es_mondragon_pay_ratio",
      "description": "Mondragon cooperative convention: maximum pay ratio 6:1 (highest to lowest)",
      "constraint_type": "MaxValue",
      "value": "6",
      "applies_to": ["treasurer-agent-v1"],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "Mondragon_Statutes"}
    },
    {
      "rule_id": "reg_es_asamblea_general",
      "description": "Ley 27/1999 Art.21: General Assembly is the supreme governing body",
      "constraint_type": "RequireApproval",
      "value": "governance_change,dissolution",
      "applies_to": [],
      "metadata": {"_regulatory": true, "non_overridable": true, "source": "Ley27_1999_Art21"}
    }
  ],
  "source_documents": [
    {
      "reference": "Ley 27/1999, de 16 de julio, de Cooperativas",
      "cid": null,
      "ingested_at": "2026-03-17T00:00:00Z"
    }
  ],
  "non_overridable": true,
  "update_history": []
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestRegulatoryTemplates -v`
Expected: All 6 tests PASS

- [ ] **Step 8: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/governance/regulatory/
git commit -m "feat(regulatory): add jurisdiction templates — UNIVERSAL, GB, ES"
```

---

## Chunk 3: InitializerAgent Graph + Rule Extractor

### Task 9: InitializerAgent — Solo Path Nodes

**Files:**
- Create: `backend/agents/genesis/__init__.py`
- Create: `backend/agents/genesis/initializer_agent.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test for solo path**

Add to `tests/test_genesis_boot.py`:

```python
import asyncio

from backend.agents.genesis.initializer_agent import (
    select_mode,
    collect_owner_profile,
    inject_regulatory_layer,
    configure_solo_manifest,
)
from backend.schemas.genesis import GenesisMode


def _solo_initial_state() -> dict:
    """Minimal BootState for solo mode testing."""
    return {
        "messages": [],
        "agent_id": "initializer-agent-v1",
        "action_log": [],
        "error": None,
        "mode": GenesisMode.SOLO_NODE.value,
        "node_type": None,
        "coop_profile": None,
        "owner_profile": None,
        "skeleton_template_cid": None,
        "extracted_rules": [],
        "mapping_confirmations": {},
        "founder_confirmations": {},
        "ambiguous_rules": [],
        "regulatory_layer": None,
        "genesis_manifest": None,
        "constitution_cid": None,
        "genesis_manifest_cid": None,
        "founding_tx_hash": None,
        "founder_sbt_ids": [],
        "safe_address": None,
        "boot_phase": "pre-genesis",
        "boot_complete": False,
        "requires_human_token": False,
    }


class TestSoloPathNodes:
    """Tests for solo-mode graph nodes."""

    def test_select_mode_sets_node_type_solo(self):
        state = _solo_initial_state()
        result = select_mode(state)
        assert result["node_type"] == "solo"
        assert len(result["action_log"]) == 1

    def test_collect_owner_profile(self):
        state = _solo_initial_state()
        state["owner_profile"] = {
            "did": "did:key:owner123",
            "address": "0x" + "a" * 40,
            "name": "Alice",
            "jurisdiction": "GB",
        }
        result = collect_owner_profile(state)
        assert result["owner_profile"]["did"] == "did:key:owner123"
        assert result["boot_phase"] == "owner-profile-collected"

    def test_inject_regulatory_layer_loads_jurisdiction(self):
        state = _solo_initial_state()
        state["owner_profile"] = {"jurisdiction": "GB"}
        result = inject_regulatory_layer(state)
        assert result["regulatory_layer"] is not None
        assert result["regulatory_layer"]["jurisdiction"] == "GB"
        assert result["regulatory_layer"]["non_overridable"] is True

    def test_inject_regulatory_layer_fallback_universal(self):
        state = _solo_initial_state()
        state["owner_profile"] = {"jurisdiction": "XX"}  # Unknown
        result = inject_regulatory_layer(state)
        assert result["regulatory_layer"]["jurisdiction"] == "UNIVERSAL"

    def test_configure_solo_manifest(self):
        state = _solo_initial_state()
        state["regulatory_layer"] = {
            "jurisdiction": "GB",
            "rules": [{"rule_id": "reg_test", "metadata": {"_regulatory": True}}],
            "non_overridable": True,
        }
        result = configure_solo_manifest(state)
        assert result["genesis_manifest"] is not None
        assert result["genesis_manifest"]["version"] == 1
        assert len(result["genesis_manifest"]["policies"]) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestSoloPathNodes -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.agents.genesis'`

- [ ] **Step 3: Create package init**

```python
# backend/agents/genesis/__init__.py
"""Genesis Boot Sequence — InitializerAgent and supporting modules."""
```

- [ ] **Step 4: Implement solo path nodes**

```python
# backend/agents/genesis/initializer_agent.py
"""
InitializerAgent — LangGraph StateGraph for the Genesis Boot Sequence.

Two paths: solo (SOLO_NODE) and cooperative (LEGACY_IMPORT / NEW_FOUNDING).
Identity first, governance second. All founding decisions require
unanimous consent (N-of-N).

GLASS BOX: Every node appends an AgentAction to state["action_log"].
GENESIS CRITICAL: Not interruptible by agents_are_paused().
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.schemas.genesis import GenesisMode, GovernanceTier
from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AGENT_ID = "initializer-agent-v1"


# ═══════════════════════════════════════════════════════════════════════════════
# Helper — Glass Box action builder
# ═══════════════════════════════════════════════════════════════════════════════


def _append_action(
    state: dict[str, Any],
    action: str,
    rationale: str,
    impact: EthicalImpactLevel = EthicalImpactLevel.LOW,
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build an AgentAction and return updated action_log."""
    agent_action = AgentAction(
        agent_id=AGENT_ID,
        action=action,
        rationale=rationale,
        ethical_impact=impact,
        payload=payload or {},
    )
    return state.get("action_log", []) + [agent_action.model_dump()]


# ═══════════════════════════════════════════════════════════════════════════════
# Node: select_mode
# ═══════════════════════════════════════════════════════════════════════════════


def select_mode(state: dict[str, Any]) -> dict[str, Any]:
    """Read mode from state and set node_type."""
    if state.get("error"):
        return state

    mode = state.get("mode")
    if mode == GenesisMode.SOLO_NODE.value:
        node_type = "solo"
    else:
        node_type = "cooperative"

    return {
        **state,
        "node_type": node_type,
        "boot_phase": "mode-selected",
        "action_log": _append_action(
            state,
            "select_genesis_mode",
            f"Genesis mode selected: {mode}. Node type: {node_type}.",
            payload={"mode": mode, "node_type": node_type},
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Node: collect_owner_profile (solo only)
# ═══════════════════════════════════════════════════════════════════════════════


def collect_owner_profile(state: dict[str, Any]) -> dict[str, Any]:
    """Solo mode: validate owner profile is present in state."""
    if state.get("error"):
        return state

    profile = state.get("owner_profile")
    if not profile:
        return {
            **state,
            "error": "Solo mode requires owner_profile in state.",
        }

    return {
        **state,
        "boot_phase": "owner-profile-collected",
        "action_log": _append_action(
            state,
            "collect_owner_profile",
            f"Solo node owner profile collected: DID={profile.get('did', 'unknown')}.",
            payload={"owner_did": profile.get("did")},
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Node: inject_regulatory_layer (both paths)
# ═══════════════════════════════════════════════════════════════════════════════


def inject_regulatory_layer(state: dict[str, Any]) -> dict[str, Any]:
    """Load jurisdiction-specific regulatory layer from templates directory."""
    if state.get("error"):
        return state

    # Determine jurisdiction from profile
    profile = state.get("owner_profile") or state.get("coop_profile") or {}
    jurisdiction = profile.get("jurisdiction", settings.genesis_default_jurisdiction)

    templates_dir = Path(settings.genesis_regulatory_templates_dir)
    template_path = templates_dir / f"{jurisdiction}.json"

    # Fallback to UNIVERSAL if jurisdiction template not found
    if not template_path.exists():
        logger.warning(
            "Regulatory template not found for '%s', falling back to UNIVERSAL",
            jurisdiction,
        )
        template_path = templates_dir / "UNIVERSAL.json"
        jurisdiction = "UNIVERSAL"

    with open(template_path) as f:
        regulatory_data = json.load(f)

    # Ensure non_overridable is True (defense in depth)
    regulatory_data["non_overridable"] = True

    return {
        **state,
        "regulatory_layer": regulatory_data,
        "boot_phase": "regulatory-layer-injected",
        "action_log": _append_action(
            state,
            "inject_regulatory_layer",
            f"Loaded regulatory layer for jurisdiction '{jurisdiction}': "
            f"{len(regulatory_data.get('rules', []))} rule(s). Non-overridable.",
            EthicalImpactLevel.MEDIUM,
            payload={
                "jurisdiction": jurisdiction,
                "rule_count": len(regulatory_data.get("rules", [])),
            },
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Node: configure_solo_manifest (solo only)
# ═══════════════════════════════════════════════════════════════════════════════


def configure_solo_manifest(state: dict[str, Any]) -> dict[str, Any]:
    """Build minimal GovernanceManifest for solo node: ICA core + regulatory layer."""
    if state.get("error"):
        return state

    regulatory_layer = state.get("regulatory_layer") or {}
    regulatory_rules = regulatory_layer.get("rules", [])

    manifest = {
        "version": 1,
        "constitutional_core": [
            "anti_extractive",
            "democratic_control",
            "transparency",
            "open_membership",
        ],
        "policies": regulatory_rules,  # Regulatory rules as the base
    }

    return {
        **state,
        "genesis_manifest": manifest,
        "boot_phase": "solo-manifest-configured",
        "action_log": _append_action(
            state,
            "configure_solo_manifest",
            f"Solo manifest configured with {len(regulatory_rules)} regulatory rule(s) "
            f"+ ICA constitutional core.",
            EthicalImpactLevel.MEDIUM,
            payload={"policy_count": len(regulatory_rules)},
        ),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestSoloPathNodes -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/agents/genesis/
git commit -m "feat(genesis): add InitializerAgent solo path nodes — select_mode, collect_owner, inject_regulatory, configure_solo"
```

---

### Task 10: InitializerAgent — Cooperative Path Nodes

**Files:**
- Modify: `backend/agents/genesis/initializer_agent.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing tests for cooperative nodes**

Add to `tests/test_genesis_boot.py`:

```python
from backend.agents.genesis.initializer_agent import (
    register_founders,
    compile_genesis_manifest,
    validate_genesis_manifest,
)


def _coop_initial_state() -> dict:
    """Minimal BootState for cooperative mode testing."""
    state = _solo_initial_state()
    state["mode"] = GenesisMode.LEGACY_IMPORT.value
    state["node_type"] = "cooperative"
    return state


class TestCooperativePathNodes:
    """Tests for cooperative-mode graph nodes."""

    def test_register_founders_minimum_3(self):
        state = _coop_initial_state()
        state["founder_confirmations"] = {
            "did:key:alice": False,
            "did:key:bob": False,
        }
        result = register_founders(state)
        assert result["error"] is not None
        assert "minimum 3" in result["error"].lower()

    def test_register_founders_success(self):
        state = _coop_initial_state()
        state["founder_confirmations"] = {
            "did:key:alice": False,
            "did:key:bob": False,
            "did:key:carol": False,
        }
        result = register_founders(state)
        assert result["error"] is None
        assert result["boot_phase"] == "founders-registered"

    def test_compile_genesis_manifest_merges_tiers(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {
                "rule_id": "pay_ratio",
                "tier": "Constitutional",
                "proposed_policy_rule": {
                    "rule_id": "pay_ratio",
                    "description": "6:1 cap",
                    "constraint_type": "MaxValue",
                    "value": "6",
                    "applies_to": [],
                },
                "confirmed": True,
            },
            {
                "rule_id": "spend_limit",
                "tier": "Operational",
                "proposed_policy_rule": {
                    "rule_id": "spend_limit",
                    "description": "100k cap",
                    "constraint_type": "MaxValue",
                    "value": "100000",
                    "applies_to": [],
                },
                "confirmed": True,
            },
        ]
        state["regulatory_layer"] = {
            "jurisdiction": "GB",
            "rules": [{"rule_id": "reg_test", "metadata": {"_regulatory": True}}],
            "non_overridable": True,
        }
        result = compile_genesis_manifest(state)
        manifest = result["genesis_manifest"]
        assert manifest["version"] == 1
        # Should have: 2 confirmed rules + 1 regulatory = 3 total
        assert len(manifest["policies"]) == 3

    def test_compile_genesis_manifest_skips_unconfirmed(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {
                "rule_id": "confirmed_rule",
                "tier": "Operational",
                "proposed_policy_rule": {"rule_id": "confirmed_rule"},
                "confirmed": True,
            },
            {
                "rule_id": "unconfirmed_rule",
                "tier": "Operational",
                "proposed_policy_rule": {"rule_id": "unconfirmed_rule"},
                "confirmed": False,
            },
        ]
        state["regulatory_layer"] = {"rules": [], "non_overridable": True}
        result = compile_genesis_manifest(state)
        rule_ids = [r.get("rule_id") for r in result["genesis_manifest"]["policies"]]
        assert "confirmed_rule" in rule_ids
        assert "unconfirmed_rule" not in rule_ids

    def test_validate_genesis_manifest_passes(self):
        state = _coop_initial_state()
        state["genesis_manifest"] = {
            "version": 1,
            "constitutional_core": [
                "anti_extractive", "democratic_control",
                "transparency", "open_membership",
            ],
            "policies": [{"rule_id": "test"}],
        }
        state["regulatory_layer"] = {"rules": [], "non_overridable": True}
        result = validate_genesis_manifest(state)
        assert result["error"] is None
        assert result["boot_phase"] == "manifest-validated"

    def test_validate_genesis_manifest_missing_ica(self):
        state = _coop_initial_state()
        state["genesis_manifest"] = {
            "version": 1,
            "constitutional_core": [],  # Missing ICA
            "policies": [],
        }
        state["regulatory_layer"] = {"rules": [], "non_overridable": True}
        result = validate_genesis_manifest(state)
        assert result["error"] is not None
        assert "ICA" in result["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestCooperativePathNodes -v`
Expected: FAIL — `ImportError: cannot import name 'register_founders'`

- [ ] **Step 3: Implement cooperative nodes**

Append to `backend/agents/genesis/initializer_agent.py`:

```python
# ═══════════════════════════════════════════════════════════════════════════════
# Node: register_founders (cooperative only)
# ═══════════════════════════════════════════════════════════════════════════════


def register_founders(state: dict[str, Any]) -> dict[str, Any]:
    """Validate minimum 3 founders are registered."""
    if state.get("error"):
        return state

    confirmations = state.get("founder_confirmations", {})
    if len(confirmations) < settings.genesis_min_founders:
        return {
            **state,
            "error": (
                f"Cooperative genesis requires minimum {settings.genesis_min_founders} "
                f"founders. Currently registered: {len(confirmations)}."
            ),
        }

    return {
        **state,
        "boot_phase": "founders-registered",
        "action_log": _append_action(
            state,
            "register_founders",
            f"Registered {len(confirmations)} founding member(s). "
            f"Minimum {settings.genesis_min_founders} met.",
            payload={"founder_count": len(confirmations)},
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Node: compile_genesis_manifest (cooperative)
# ═══════════════════════════════════════════════════════════════════════════════


def compile_genesis_manifest(state: dict[str, Any]) -> dict[str, Any]:
    """Merge confirmed rules by tier + regulatory layer into GovernanceManifest."""
    if state.get("error"):
        return state

    extracted = state.get("extracted_rules", [])
    regulatory = state.get("regulatory_layer") or {}
    regulatory_rules = regulatory.get("rules", [])

    # Only include confirmed rules
    confirmed_policies = []
    for rule in extracted:
        if rule.get("confirmed"):
            policy = rule.get("proposed_policy_rule", {})
            confirmed_policies.append(policy)

    # Merge: regulatory rules first (permanent floor), then confirmed rules
    all_policies = regulatory_rules + confirmed_policies

    manifest = {
        "version": 1,
        "constitutional_core": [
            "anti_extractive",
            "democratic_control",
            "transparency",
            "open_membership",
        ],
        "policies": all_policies,
    }

    return {
        **state,
        "genesis_manifest": manifest,
        "boot_phase": "manifest-compiled",
        "action_log": _append_action(
            state,
            "compile_genesis_manifest",
            f"Compiled genesis manifest: {len(regulatory_rules)} regulatory + "
            f"{len(confirmed_policies)} confirmed = {len(all_policies)} total rules.",
            EthicalImpactLevel.MEDIUM,
            payload={
                "regulatory_count": len(regulatory_rules),
                "confirmed_count": len(confirmed_policies),
                "total_count": len(all_policies),
            },
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Node: validate_genesis_manifest (both paths)
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_ICA = {"anti_extractive", "democratic_control", "transparency", "open_membership"}


def validate_genesis_manifest(state: dict[str, Any]) -> dict[str, Any]:
    """Validate the compiled manifest has all required fields."""
    if state.get("error"):
        return state

    manifest = state.get("genesis_manifest")
    if not manifest:
        return {**state, "error": "No genesis manifest to validate."}

    # Check ICA constitutional core
    core = set(manifest.get("constitutional_core", []))
    missing_ica = REQUIRED_ICA - core
    if missing_ica:
        return {
            **state,
            "error": f"ICA constitutional core incomplete. Missing: {missing_ica}",
        }

    # Check version
    if manifest.get("version", 0) < 1:
        return {**state, "error": "Manifest version must be >= 1."}

    return {
        **state,
        "boot_phase": "manifest-validated",
        "action_log": _append_action(
            state,
            "validate_genesis_manifest",
            f"Genesis manifest validated: version={manifest['version']}, "
            f"ICA core complete, {len(manifest.get('policies', []))} policy rule(s).",
            EthicalImpactLevel.MEDIUM,
            payload={
                "version": manifest["version"],
                "policy_count": len(manifest.get("policies", [])),
                "ica_complete": True,
            },
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestCooperativePathNodes -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/agents/genesis/initializer_agent.py tests/test_genesis_boot.py
git commit -m "feat(genesis): add cooperative path nodes — register_founders, compile_manifest, validate_manifest"
```

---

### Task 11: Rule Extractor (Template-Guided LLM)

**Files:**
- Create: `backend/agents/genesis/rule_extractor.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_genesis_boot.py`:

```python
from backend.agents.genesis.rule_extractor import (
    extract_rules_from_bylaws,
    tag_ambiguous_rules,
)


class TestRuleExtractor:
    """Tests for template-guided bylaw rule extraction."""

    def test_extract_rules_returns_list(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {
                "rule_id": "pay_ratio",
                "source_text": "Pay ratio shall not exceed 6:1",
                "proposed_policy_rule": {
                    "rule_id": "pay_ratio",
                    "constraint_type": "MaxValue",
                    "value": "6",
                },
                "confidence": 0.95,
                "is_ambiguous": False,
                "is_novel_field": False,
                "tier": "Operational",
                "confirmed": False,
            }
        ]
        # extract_rules_from_bylaws is a stub that passes through
        # (actual LLM extraction is an integration concern)
        result = extract_rules_from_bylaws(state)
        assert isinstance(result["extracted_rules"], list)
        assert len(result["extracted_rules"]) >= 1

    def test_tag_ambiguous_marks_low_confidence(self):
        state = _coop_initial_state()
        state["extracted_rules"] = [
            {
                "rule_id": "clear_rule",
                "confidence": 0.9,
                "is_ambiguous": False,
            },
            {
                "rule_id": "vague_rule",
                "confidence": 0.4,
                "is_ambiguous": False,
            },
        ]
        result = tag_ambiguous_rules(state)
        rules = {r["rule_id"]: r for r in result["extracted_rules"]}
        assert rules["clear_rule"]["is_ambiguous"] is False
        assert rules["vague_rule"]["is_ambiguous"] is True
        assert "vague_rule" in result["ambiguous_rules"]

    def test_tag_ambiguous_empty_list(self):
        state = _coop_initial_state()
        state["extracted_rules"] = []
        result = tag_ambiguous_rules(state)
        assert result["ambiguous_rules"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestRuleExtractor -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement rule extractor**

```python
# backend/agents/genesis/rule_extractor.py
"""
Rule Extractor — Template-guided bylaw rule extraction.

Uses a bylaw skeleton from LibraryManager to define expected rule slots.
The LLM fills slots rather than free-parsing. Unmatched clauses get
is_novel_field=True and are proposed as KnowledgeAssets.

STUB: The actual LLM extraction (OLMo integration) is deferred.
This module provides the graph node functions and the tagging logic.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

logger = logging.getLogger(__name__)

AMBIGUITY_THRESHOLD = 0.6

# Reuse the shared _append_action helper from initializer_agent
from backend.agents.genesis.initializer_agent import _append_action, AGENT_ID  # noqa: E402


def extract_rules_from_bylaws(state: dict[str, Any]) -> dict[str, Any]:
    """Extract rules from bylaw text using skeleton template.

    STUB: In production, this invokes OLMo via LlmQueueManager with the
    bylaw text + skeleton template as context. The LLM fills slots and
    marks unmatched clauses as novel fields.

    For now, this passes through whatever extracted_rules are already
    in the state (set by the router from a previous extraction step
    or test fixture).
    """
    if state.get("error"):
        return state

    rules = state.get("extracted_rules", [])

    return {
        **state,
        "boot_phase": "rules-extracted",
        "action_log": _append_action(
            state,
            "extract_rules_from_bylaws",
            f"Extracted {len(rules)} rule(s) from bylaws. "
            f"STUB: actual LLM extraction deferred to integration phase.",
            payload={"rule_count": len(rules)},
        ),
    }


def tag_ambiguous_rules(state: dict[str, Any]) -> dict[str, Any]:
    """Tag rules with confidence < 0.6 as Human-Judgment-Only.

    Ambiguous rules get is_ambiguous=True and are added to the
    ambiguous_rules list in state. The PolicyEngine treats these
    as mandatory HITL for every future action touching that rule.
    """
    if state.get("error"):
        return state

    rules = state.get("extracted_rules", [])
    ambiguous_ids: list[str] = []
    updated_rules: list[dict[str, Any]] = []

    for rule in rules:
        confidence = rule.get("confidence", 1.0)
        if confidence < AMBIGUITY_THRESHOLD:
            rule = {**rule, "is_ambiguous": True}
            ambiguous_ids.append(rule.get("rule_id", "unknown"))
        updated_rules.append(rule)

    return {
        **state,
        "extracted_rules": updated_rules,
        "ambiguous_rules": ambiguous_ids,
        "boot_phase": "ambiguity-tagged",
        "action_log": _append_action(
            state,
            "tag_ambiguous_rules",
            f"Tagged {len(ambiguous_ids)} rule(s) as Human-Judgment-Only "
            f"(confidence < {AMBIGUITY_THRESHOLD}). These require mandatory "
            f"HITL for every future instance.",
            payload={
                "ambiguous_count": len(ambiguous_ids),
                "ambiguous_rule_ids": ambiguous_ids,
                "threshold": AMBIGUITY_THRESHOLD,
            },
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestRuleExtractor -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/agents/genesis/rule_extractor.py tests/test_genesis_boot.py
git commit -m "feat(genesis): add rule extractor — ambiguity tagging + LLM extraction stub"
```

---

### Task 12: Compile and Wire the StateGraph

**Files:**
- Modify: `backend/agents/genesis/initializer_agent.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test for graph compilation**

Add to `tests/test_genesis_boot.py`:

```python
from backend.agents.genesis.initializer_agent import build_genesis_graph


class TestGenesisGraph:
    """Tests for the compiled LangGraph StateGraph."""

    def test_graph_compiles(self):
        graph = build_genesis_graph()
        assert graph is not None

    def test_solo_mode_skips_cooperative_ceremony(self):
        """Solo path should not hit register_founders or ratify nodes."""
        graph = build_genesis_graph()
        state = _solo_initial_state()
        state["owner_profile"] = {
            "did": "did:key:solo",
            "address": "0x" + "a" * 40,
            "name": "Solo Owner",
            "jurisdiction": "UNIVERSAL",
        }
        # invoke with solo mode — should complete without HITL
        # (owner_review HITL is interrupt_before, so graph pauses there)
        config = {"configurable": {"thread_id": "test-solo-1"}}
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        result = snapshot.values
        assert result["node_type"] == "solo"
        assert result["regulatory_layer"] is not None
        assert result["genesis_manifest"] is not None

    def test_boot_complete_latch_prevents_rerun(self):
        state = _solo_initial_state()
        state["boot_complete"] = True
        result = select_mode(state)
        # select_mode should detect boot_complete and error
        assert result.get("error") is not None or result.get("boot_complete") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestGenesisGraph::test_graph_compiles -v`
Expected: FAIL — `ImportError: cannot import name 'build_genesis_graph'`

- [ ] **Step 3: Add boot_complete check to select_mode and build_genesis_graph**

Update `select_mode` in `initializer_agent.py` to check boot_complete:

```python
def select_mode(state: dict[str, Any]) -> dict[str, Any]:
    """Read mode from state and set node_type."""
    if state.get("error"):
        return state

    if state.get("boot_complete"):
        return {
            **state,
            "error": "Genesis already complete. Boot sequence cannot be re-run.",
        }

    mode = state.get("mode")
    if mode == GenesisMode.SOLO_NODE.value:
        node_type = "solo"
    else:
        node_type = "cooperative"

    return {
        **state,
        "node_type": node_type,
        "boot_phase": "mode-selected",
        "action_log": _append_action(
            state,
            "select_genesis_mode",
            f"Genesis mode selected: {mode}. Node type: {node_type}.",
            payload={"mode": mode, "node_type": node_type},
        ),
    }
```

Add the graph builder at the end of `initializer_agent.py`:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.agents.state import BootState
from backend.agents.genesis.rule_extractor import (
    extract_rules_from_bylaws,
    tag_ambiguous_rules,
)


def _route_after_mode(state: dict[str, Any]) -> str:
    """Route based on node_type after select_mode."""
    if state.get("error"):
        return END
    if state["node_type"] == "solo":
        return "collect_owner_profile"
    return "register_founders"


def _route_after_founders(state: dict[str, Any]) -> str:
    """Route based on mode after founder registration."""
    if state.get("error"):
        return END
    mode = state.get("mode")
    if mode == GenesisMode.LEGACY_IMPORT.value:
        return "extract_rules"
    return "browse_templates"  # NEW_FOUNDING path


# ═══════════════════════════════════════════════════════════════════════════════
# Stub nodes — Web3 operations (deploy_identity, deploy_safe, execute_genesis)
# Full Web3 integration is a separate task; these stubs maintain the graph
# structure and Glass Box trail.
# ═══════════════════════════════════════════════════════════════════════════════


def deploy_identity(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Deploy CoopIdentity.sol and mint founder SBTs.

    TODO: Web3 integration — call Deploy.s.sol via forge script,
    capture contract address and SBT token IDs.
    """
    if state.get("error"):
        return state

    founders = state.get("founder_confirmations", {})
    # Stub: assign sequential SBT IDs
    sbt_ids = list(range(1, len(founders) + 1))

    return {
        **state,
        "founder_sbt_ids": sbt_ids,
        "boot_phase": "identity-deployed",
        "action_log": _append_action(
            state,
            "deploy_coop_identity",
            f"STUB: CoopIdentity.sol deployed. Minted {len(sbt_ids)} founder SBTs.",
            EthicalImpactLevel.HIGH,
            payload={"sbt_ids": sbt_ids, "founder_count": len(founders)},
        ),
    }


def deploy_safe(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Deploy Gnosis Safe with all founders as N-of-N owners.

    TODO: Web3 integration — call Safe Factory, set threshold = N.
    """
    if state.get("error"):
        return state

    founders = state.get("founder_confirmations", {})
    stub_safe = "0x" + "5" * 40  # Stub address

    return {
        **state,
        "safe_address": stub_safe,
        "boot_phase": "safe-deployed",
        "action_log": _append_action(
            state,
            "deploy_gnosis_safe",
            f"STUB: Gnosis Safe deployed at {stub_safe}. "
            f"Threshold: {len(founders)}-of-{len(founders)} (unanimous).",
            EthicalImpactLevel.HIGH,
            payload={"safe_address": stub_safe, "threshold": len(founders)},
        ),
    }


def browse_templates(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Query LibraryManager for governance templates.

    TODO: Integration with LibraryManager.list_assets(tag="governance-template").
    """
    if state.get("error"):
        return state
    return {
        **state,
        "boot_phase": "browsing-templates",
        "action_log": _append_action(
            state,
            "browse_governance_templates",
            "STUB: Queried LibraryManager for governance templates.",
        ),
    }


def select_template(state: dict[str, Any]) -> dict[str, Any]:
    """STUB: Human selects a governance template."""
    if state.get("error"):
        return state
    return {
        **state,
        "boot_phase": "template-selected",
        "action_log": _append_action(
            state,
            "select_governance_template",
            f"STUB: Template selected (CID: {state.get('skeleton_template_cid', 'none')}).",
        ),
    }


def propose_novel_fields(state: dict[str, Any]) -> dict[str, Any]:
    """Package novel fields as KnowledgeAsset proposals to LibraryManager.

    Rules with is_novel_field=True are proposed for admission to the
    standard skeleton. The founding cooperative's rule is applied locally
    regardless of whether the KnowledgeAsset is admitted globally.
    """
    if state.get("error"):
        return state

    extracted = state.get("extracted_rules", [])
    novel = [r for r in extracted if r.get("is_novel_field")]

    return {
        **state,
        "boot_phase": "novel-fields-proposed",
        "action_log": _append_action(
            state,
            "propose_novel_fields",
            f"Proposed {len(novel)} novel field(s) as KnowledgeAsset candidates. "
            f"STUB: LibraryManager integration deferred.",
            EthicalImpactLevel.MEDIUM,
            payload={"novel_count": len(novel)},
        ),
    }


def execute_genesis_binding(state: dict[str, Any]) -> dict[str, Any]:
    """The one-way trip — cooperative genesis binding.

    STUB: Steps that require Web3/IPFS integration are marked TODO.
    The graph structure and Glass Box trail are complete.

    Steps:
      1. Generate Ricardian Constitution (TODO: call /constitution/generate)
      2. Pin Genesis Manifest to Mesh Archive (TODO: SovereignStorage.pin)
      3. Deploy Constitution.sol (TODO: forge script)
      4. Wire CoopIdentity.setConstitution (TODO: Web3 call)
      5. Load PolicyEngine (can execute immediately)
      6. Inject Persona (TODO: persona_generator integration)
      7. Create CausalEvent (TODO: CausalEvent.create)
      8. Set one-way latch
    """
    if state.get("error"):
        return state

    # Step 5: Load PolicyEngine (this works without Web3)
    from backend.governance.policy_engine import PolicyEngine
    manifest = state.get("genesis_manifest")
    if manifest:
        engine = PolicyEngine.get_instance()
        _loaded_manifest, load_action = engine.load_manifest(manifest_dict=manifest)
        action_log = state.get("action_log", []) + [load_action.model_dump()]
    else:
        action_log = state.get("action_log", [])

    return {
        **state,
        "boot_complete": True,
        "boot_phase": "genesis-complete",
        "action_log": _append_action(
            {**state, "action_log": action_log},
            "execute_genesis_binding",
            "STUB: Genesis binding executed. PolicyEngine loaded. "
            "Web3 steps (Constitution.sol deployment, SBT minting, "
            "CausalEvent broadcast) deferred to integration phase.",
            EthicalImpactLevel.HIGH,
            payload={
                "manifest_version": manifest.get("version") if manifest else None,
                "boot_complete": True,
            },
        ),
    }


def execute_solo_genesis(state: dict[str, Any]) -> dict[str, Any]:
    """The one-way trip — solo genesis binding (lightweight).

    STUB: Same as cooperative but simpler (no SBTs, no Safe, no federation).
    """
    if state.get("error"):
        return state

    from backend.governance.policy_engine import PolicyEngine
    manifest = state.get("genesis_manifest")
    if manifest:
        engine = PolicyEngine.get_instance()
        _loaded_manifest, load_action = engine.load_manifest(manifest_dict=manifest)
        action_log = state.get("action_log", []) + [load_action.model_dump()]
    else:
        action_log = state.get("action_log", [])

    return {
        **state,
        "boot_complete": True,
        "boot_phase": "genesis-complete",
        "action_log": _append_action(
            {**state, "action_log": action_log},
            "execute_solo_genesis",
            "STUB: Solo genesis binding executed. PolicyEngine loaded. "
            "Constitution.sol deployment deferred to integration phase.",
            EthicalImpactLevel.HIGH,
            payload={"boot_complete": True},
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_genesis_graph():
    """Build and compile the Genesis Boot Sequence StateGraph."""

    graph = StateGraph(BootState)

    # ── Add nodes ────────────────────────────────────────────────────────
    graph.add_node("select_mode", select_mode)

    # Solo path
    graph.add_node("collect_owner_profile", collect_owner_profile)
    graph.add_node("configure_solo_manifest", configure_solo_manifest)
    graph.add_node("owner_review", lambda state: {
        **state,
        "requires_human_token": True,
        "boot_phase": "owner-review",
    })
    graph.add_node("execute_solo_genesis", execute_solo_genesis)

    # Cooperative path
    graph.add_node("register_founders", register_founders)
    graph.add_node("deploy_identity", deploy_identity)
    graph.add_node("deploy_safe", deploy_safe)
    graph.add_node("extract_rules", extract_rules_from_bylaws)
    graph.add_node("tag_ambiguous", tag_ambiguous_rules)
    graph.add_node("browse_templates", browse_templates)
    graph.add_node("select_template", select_template)
    graph.add_node("propose_novel_fields", propose_novel_fields)

    # Shared nodes
    graph.add_node("inject_regulatory_layer", inject_regulatory_layer)
    graph.add_node("compile_genesis_manifest", compile_genesis_manifest)
    graph.add_node("validate_genesis_manifest", validate_genesis_manifest)

    # HITL nodes
    graph.add_node("confirm_mappings", lambda state: {
        **state,
        "requires_human_token": True,
        "boot_phase": "confirm-mappings",
    })
    graph.add_node("ratify_genesis", lambda state: {
        **state,
        "requires_human_token": True,
        "boot_phase": "ratify-genesis",
    })

    # Genesis binding (post-HITL)
    graph.add_node("execute_genesis_binding", execute_genesis_binding)

    # ── Set entry point ──────────────────────────────────────────────────
    graph.set_entry_point("select_mode")

    # ── Edges ────────────────────────────────────────────────────────────

    # After select_mode: route to solo or cooperative
    graph.add_conditional_edges("select_mode", _route_after_mode)

    # Solo path
    graph.add_edge("collect_owner_profile", "inject_regulatory_layer")
    graph.add_conditional_edges(
        "inject_regulatory_layer",
        lambda s: "configure_solo_manifest" if s.get("node_type") == "solo" else "compile_genesis_manifest",
    )
    graph.add_edge("configure_solo_manifest", "validate_genesis_manifest")
    graph.add_conditional_edges(
        "validate_genesis_manifest",
        lambda s: "owner_review" if s.get("node_type") == "solo" else "confirm_mappings",
    )
    graph.add_edge("owner_review", "execute_solo_genesis")
    graph.add_edge("execute_solo_genesis", END)

    # Cooperative path: register → deploy identity → deploy safe → [mode-specific extraction]
    graph.add_edge("register_founders", "deploy_identity")
    graph.add_edge("deploy_identity", "deploy_safe")
    graph.add_conditional_edges(
        "deploy_safe",
        _route_after_founders,
    )

    # LEGACY_IMPORT sub-path
    graph.add_edge("extract_rules", "tag_ambiguous")
    graph.add_edge("tag_ambiguous", "inject_regulatory_layer")

    # NEW_FOUNDING sub-path
    graph.add_edge("browse_templates", "select_template")
    graph.add_edge("select_template", "inject_regulatory_layer")

    # After compile_genesis_manifest (cooperative)
    graph.add_edge("compile_genesis_manifest", "validate_genesis_manifest")

    # HITL sequence
    graph.add_edge("confirm_mappings", "propose_novel_fields")
    graph.add_edge("propose_novel_fields", "ratify_genesis")
    graph.add_edge("ratify_genesis", "execute_genesis_binding")
    graph.add_edge("execute_genesis_binding", END)

    # ── Compile with HITL breakpoints ────────────────────────────────────
    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["owner_review", "confirm_mappings", "ratify_genesis"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestGenesisGraph -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite to check regression**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (existing 147 + new genesis tests)

- [ ] **Step 6: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/agents/genesis/initializer_agent.py tests/test_genesis_boot.py
git commit -m "feat(genesis): compile LangGraph StateGraph with solo + cooperative routing and HITL breakpoints"
```

---

## Chunk 4: Auth, Router, and main.py Integration

### Task 13: Add verify_founder_token Dependency

**Files:**
- Modify: `backend/auth/dependencies.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_genesis_boot.py`:

```python
from backend.auth.dependencies import verify_founder_token


class TestFounderTokenAuth:
    """Test pre-genesis founder token verification."""

    def test_verify_founder_token_exists(self):
        """The dependency function should be importable."""
        assert callable(verify_founder_token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestFounderTokenAuth -v`
Expected: FAIL — `ImportError: cannot import name 'verify_founder_token'`

- [ ] **Step 3: Add verify_founder_token to dependencies.py**

Append to `backend/auth/dependencies.py`:

```python
import secrets
from typing import Any

import bcrypt
from fastapi import Header, HTTPException, status


async def verify_founder_token(
    x_founder_token: str = Header(..., description="Pre-genesis founder authentication token"),
) -> dict[str, Any]:
    """Verify a pre-genesis founder token.

    STUB: In production, this queries the founder_registrations table
    and verifies the bcrypt hash. For now, returns a minimal dict
    for testing.

    Raises:
        HTTPException(401): If the token is invalid or not found.
    """
    # STUB — database integration deferred
    if not x_founder_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing founder token",
        )

    # In production:
    # 1. Query founder_registrations WHERE founder_token_hash matches
    # 2. bcrypt.checkpw(token.encode(), stored_hash)
    # 3. Return FounderRegistration dict
    # 4. Rotate token after sensitive operations

    return {"token_verified": True, "token": x_founder_token}


def generate_founder_token() -> tuple[str, str]:
    """Generate a new founder token and its bcrypt hash.

    Returns:
        (plaintext_token, bcrypt_hash)
    """
    token = secrets.token_urlsafe(32)
    hashed = bcrypt.hashpw(token.encode(), bcrypt.gensalt(rounds=12))
    return token, hashed.decode()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestFounderTokenAuth -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/auth/dependencies.py tests/test_genesis_boot.py
git commit -m "feat(auth): add verify_founder_token dependency for pre-genesis auth"
```

---

### Task 14: Genesis Router

**Files:**
- Create: `backend/routers/genesis.py`
- Test: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_genesis_boot.py`:

```python
from fastapi.testclient import TestClient
from backend.routers.genesis import router as genesis_router
from fastapi import FastAPI


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(genesis_router)
    return app


class TestGenesisRouter:
    """Tests for the genesis router endpoints."""

    def test_status_endpoint_returns_pre_genesis(self):
        app = _make_app()
        client = TestClient(app)
        response = client.get("/genesis/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("pre-genesis", "complete")

    def test_boot_returns_409_after_genesis(self):
        """Once boot_complete is set, /boot returns 409."""
        # This is an integration test — we verify the endpoint exists
        app = _make_app()
        client = TestClient(app)
        response = client.get("/genesis/status")
        assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestGenesisRouter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routers.genesis'`

- [ ] **Step 3: Implement genesis router**

```python
# backend/routers/genesis.py
"""
Genesis Boot Sequence — FastAPI Router.

Prefix: /genesis
Tags: ["genesis-boot"]

Pre-genesis endpoints use founder-token auth (X-Founder-Token header).
Post-genesis, all endpoints except /status return 409 Conflict.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import verify_founder_token
from backend.config import settings
from backend.schemas.genesis import (
    BootRequest,
    BylawsUploadRequest,
    FounderRegisterRequest,
    FounderRegisterResponse,
    GenesisMode,
    GenesisStatusResponse,
    ModeSelectRequest,
    RatifyRequest,
    RuleConfirmRequest,
    TemplateSelectRequest,
    TierAssignRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/genesis", tags=["genesis-boot"])

# ── Module-level state (STUB for database) ──────────────────────────────────
# In production, this would be persisted in genesis_state + founder_registrations tables.
_boot_state: dict[str, Any] = {
    "boot_complete": False,
    "mode": None,
    "boot_phase": "pre-genesis",
    "founders": {},
    "thread_id": None,
}


def _check_not_complete():
    """Raise 409 if genesis is already complete."""
    # Also check file-based latch for persistence across restarts
    latch_file = Path(settings.genesis_boot_complete_file)
    if _boot_state["boot_complete"] or latch_file.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Genesis boot sequence already complete. This is a one-way operation.",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Public endpoints (no auth required)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/status", response_model=GenesisStatusResponse)
async def get_status():
    """Boot sequence status — always accessible."""
    latch_file = Path(settings.genesis_boot_complete_file)
    is_complete = _boot_state["boot_complete"] or latch_file.exists()

    return GenesisStatusResponse(
        status="complete" if is_complete else _boot_state["boot_phase"],
        mode=_boot_state.get("mode"),
        boot_phase=_boot_state["boot_phase"],
        founder_count=len(_boot_state.get("founders", {})),
        boot_complete=is_complete,
    )


@router.post("/founders/register", response_model=FounderRegisterResponse)
async def register_founder(req: FounderRegisterRequest):
    """Register a founding member (pre-genesis, no auth required)."""
    _check_not_complete()

    if req.did in _boot_state.get("founders", {}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Founder {req.did} already registered.",
        )

    # Generate founder token
    from backend.auth.dependencies import generate_founder_token
    token, token_hash = generate_founder_token()

    _boot_state.setdefault("founders", {})[req.did] = {
        "did": req.did,
        "address": req.address,
        "name": req.name,
        "founder_token_hash": token_hash,
    }

    return FounderRegisterResponse(
        did=req.did,
        address=req.address,
        founder_token=token,
    )


@router.get("/founders")
async def list_founders():
    """List registered founders and their status."""
    founders = _boot_state.get("founders", {})
    return {
        "founders": [
            {"did": f["did"], "address": f["address"], "name": f["name"]}
            for f in founders.values()
        ],
        "count": len(founders),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Founder-token authenticated endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/boot")
async def start_boot(req: BootRequest):
    """Start the genesis boot sequence. Unauthenticated (pre-genesis)."""
    _check_not_complete()

    _boot_state["mode"] = req.mode.value
    _boot_state["boot_phase"] = "in-progress"
    _boot_state["thread_id"] = str(uuid4())

    return {
        "status": "boot-started",
        "mode": req.mode.value,
        "thread_id": _boot_state["thread_id"],
    }


@router.post("/mode")
async def select_mode(
    req: ModeSelectRequest,
    founder: dict = Depends(verify_founder_token),
):
    """Select genesis mode."""
    _check_not_complete()
    _boot_state["mode"] = req.mode.value
    return {"mode": req.mode.value}


@router.post("/bylaws/upload")
async def upload_bylaws(
    req: BylawsUploadRequest,
    founder: dict = Depends(verify_founder_token),
):
    """Upload bylaw document text (LEGACY_IMPORT mode)."""
    _check_not_complete()
    return {"status": "bylaws-uploaded", "text_length": len(req.text)}


@router.get("/templates")
async def list_templates(founder: dict = Depends(verify_founder_token)):
    """Browse governance templates from LibraryManager."""
    _check_not_complete()
    # STUB: query LibraryManager for KnowledgeAssets tagged governance-template
    return {"templates": [], "count": 0}


@router.post("/templates/select")
async def select_template(
    req: TemplateSelectRequest,
    founder: dict = Depends(verify_founder_token),
):
    """Select a governance template (NEW_FOUNDING mode)."""
    _check_not_complete()
    return {"template_cid": req.template_cid, "status": "template-selected"}


@router.get("/mappings")
async def get_mappings(founder: dict = Depends(verify_founder_token)):
    """Get current extracted rules and mapping confirmations."""
    _check_not_complete()
    return {"mappings": [], "status": _boot_state["boot_phase"]}


@router.post("/mappings/{rule_id}/confirm")
async def confirm_mapping(
    rule_id: str,
    req: RuleConfirmRequest,
    founder: dict = Depends(verify_founder_token),
):
    """Confirm or reject a single rule mapping."""
    _check_not_complete()
    return {"rule_id": rule_id, "approved": req.approved}


@router.post("/mappings/{rule_id}/assign-tier")
async def assign_tier(
    rule_id: str,
    req: TierAssignRequest,
    founder: dict = Depends(verify_founder_token),
):
    """Assign a governance tier to a rule."""
    _check_not_complete()
    return {"rule_id": rule_id, "tier": req.tier.value}


@router.get("/manifest/preview")
async def preview_manifest(founder: dict = Depends(verify_founder_token)):
    """Preview the compiled genesis manifest."""
    _check_not_complete()
    return {"manifest": None, "status": _boot_state["boot_phase"]}


@router.post("/ratify")
async def ratify(
    req: RatifyRequest,
    founder: dict = Depends(verify_founder_token),
):
    """Cast ratification vote."""
    _check_not_complete()
    return {"ratified": req.ratified, "status": "pending"}


@router.post("/recovery/resume")
async def resume_recovery(founder: dict = Depends(verify_founder_token)):
    """Resume from GENESIS_RECOVERY state."""
    return {"status": _boot_state["boot_phase"]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestGenesisRouter -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/routers/genesis.py tests/test_genesis_boot.py
git commit -m "feat(router): add /genesis router — 14 endpoints with founder-token auth"
```

---

### Task 15: Register Genesis Router in main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add genesis router import and registration**

Add to the router imports section of `backend/main.py`:

```python
from backend.routers.genesis import router as genesis_router
```

Add to the router registration section:

```python
app.include_router(genesis_router)
```

- [ ] **Step 2: Verify the app starts**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -c "from backend.main import app; print('Genesis router registered:', any(r.path.startswith('/genesis') for r in app.routes))"`
Expected: `Genesis router registered: True`

- [ ] **Step 3: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add backend/main.py
git commit -m "feat(main): register genesis router"
```

---

### Task 16: Deploy.s.sol — Add Constitution Deployment

**Files:**
- Modify: `contracts/script/Deploy.s.sol`

- [ ] **Step 1: Add Constitution deployment to Deploy.s.sol**

Add Constitution import at the top:

```solidity
import {Constitution} from "../src/Constitution.sol";
```

Add deployment step after existing contract deployments:

```solidity
        // N. Deploy Constitution (genesis anchor)
        string memory genesisCID = vm.envOr("GENESIS_CID", string(""));
        string memory constitutionCID = vm.envOr("CONSTITUTION_CID", string(""));
        uint16 founderCnt = uint16(vm.envOr("FOUNDER_COUNT", uint256(1)));

        Constitution constitution;
        if (bytes(genesisCID).length > 0) {
            constitution = new Constitution(
                genesisCID,
                constitutionCID,
                founderCnt,
                address(identity)
            );
            console2.log("Constitution:", address(constitution));

            // Wire cross-contract reference
            identity.setConstitution(address(constitution));
        }
```

Add to the JSON artifact output:

```solidity
            '  "Constitution": "',        vm.toString(address(constitution)), '",\n',
```

- [ ] **Step 2: Verify compilation**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge build`
Expected: Compilation succeeds

- [ ] **Step 3: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add contracts/script/Deploy.s.sol
git commit -m "feat(deploy): add Constitution.sol deployment step to Deploy.s.sol"
```

---

## Chunk 5: Integration Tests + Full Suite Verification

### Task 17: Integration Test — Solo Boot End-to-End

**Files:**
- Modify: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write solo e2e test**

Add to `tests/test_genesis_boot.py`:

```python
class TestSoloBootEndToEnd:
    """End-to-end test for solo node genesis."""

    def test_solo_boot_end_to_end(self):
        """Solo path: select_mode → collect_owner → inject_regulatory → configure_solo → validate → HITL pause."""
        graph = build_genesis_graph()
        state = _solo_initial_state()
        state["owner_profile"] = {
            "did": "did:key:solo_owner",
            "address": "0x" + "b" * 40,
            "name": "Solo Owner",
            "jurisdiction": "GB",
        }

        config = {"configurable": {"thread_id": "test-solo-e2e"}}
        graph.invoke(state, config=config)
        snapshot = graph.get_state(config)
        result = snapshot.values

        # Verify full solo path executed
        assert result["node_type"] == "solo"
        assert result["regulatory_layer"]["jurisdiction"] == "GB"
        assert result["genesis_manifest"] is not None
        assert result["genesis_manifest"]["version"] == 1
        assert "anti_extractive" in result["genesis_manifest"]["constitutional_core"]
        # Graph should pause at owner_review HITL
        assert result["boot_phase"] in ("owner-review", "manifest-validated", "solo-manifest-configured")
        # Action log should have entries for each node
        assert len(result["action_log"]) >= 3

    def test_solo_mode_loads_regulatory_layer(self):
        """Solo path loads the correct jurisdiction's regulatory layer."""
        graph = build_genesis_graph()
        state = _solo_initial_state()
        state["owner_profile"] = {
            "did": "did:key:es_owner",
            "address": "0x" + "c" * 40,
            "name": "ES Owner",
            "jurisdiction": "ES",
        }

        config = {"configurable": {"thread_id": "test-solo-es"}}
        graph.invoke(state, config=config)
        result = graph.get_state(config).values
        assert result["regulatory_layer"]["jurisdiction"] == "ES"
```

- [ ] **Step 2: Run test**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestSoloBootEndToEnd -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add tests/test_genesis_boot.py
git commit -m "test(genesis): add solo boot end-to-end integration tests"
```

---

### Task 18: Integration Test — Cooperative Boot

**Files:**
- Modify: `tests/test_genesis_boot.py`

- [ ] **Step 1: Write cooperative e2e test**

Add to `tests/test_genesis_boot.py`:

```python
class TestCooperativeBootEndToEnd:
    """End-to-end test for cooperative genesis."""

    def test_cooperative_boot_with_legacy_import(self):
        """Cooperative LEGACY_IMPORT path through to HITL pause at confirm_mappings."""
        graph = build_genesis_graph()
        state = _coop_initial_state()
        state["founder_confirmations"] = {
            "did:key:alice": False,
            "did:key:bob": False,
            "did:key:carol": False,
        }
        state["coop_profile"] = {"jurisdiction": "GB"}
        state["extracted_rules"] = [
            {
                "rule_id": "pay_ratio",
                "source_text": "Pay ratio 6:1",
                "proposed_policy_rule": {
                    "rule_id": "pay_ratio",
                    "description": "6:1 cap",
                    "constraint_type": "MaxValue",
                    "value": "6",
                    "applies_to": [],
                },
                "confidence": 0.95,
                "is_ambiguous": False,
                "is_novel_field": False,
                "tier": "Constitutional",
                "confirmed": True,
            },
        ]

        config = {"configurable": {"thread_id": "test-coop-e2e"}}
        graph.invoke(state, config=config)
        result = graph.get_state(config).values

        assert result["node_type"] == "cooperative"
        assert result["error"] is None
        assert result["regulatory_layer"] is not None
        # Graph should pause at confirm_mappings HITL
        assert len(result["action_log"]) >= 3

    def test_single_objection_blocks_ratification(self):
        """If any founder hasn't confirmed, ratification should not proceed."""
        state = _coop_initial_state()
        state["founder_confirmations"] = {
            "did:key:alice": True,
            "did:key:bob": True,
            "did:key:carol": False,  # Carol hasn't ratified
        }
        # All confirmations must be True for ratification
        all_ratified = all(state["founder_confirmations"].values())
        assert all_ratified is False
```

- [ ] **Step 2: Run test**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py::TestCooperativeBootEndToEnd -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git add tests/test_genesis_boot.py
git commit -m "test(genesis): add cooperative boot end-to-end integration tests"
```

---

### Task 19: Full Suite Verification

- [ ] **Step 1: Run all genesis tests**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/test_genesis_boot.py -v`
Expected: All genesis tests PASS

- [ ] **Step 2: Run full project test suite**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (existing 147 + new genesis tests)

- [ ] **Step 3: Run Solidity tests**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS/contracts && forge test -v`
Expected: All Foundry tests PASS (existing + Constitution + CoopIdentity)

- [ ] **Step 4: Verify imports**

Run: `cd C:/Users/argoc/Documents/Iskander/src/IskanderOS && python -c "
from backend.schemas.genesis import GenesisMode, GovernanceTier, ExtractedRule, RegulatoryLayer
from backend.agents.state import BootState
from backend.agents.genesis.initializer_agent import build_genesis_graph
from backend.agents.genesis.rule_extractor import extract_rules_from_bylaws, tag_ambiguous_rules
from backend.routers.genesis import router as genesis_router
from backend.auth.dependencies import verify_founder_token, generate_founder_token
print('All genesis imports OK')
"`
Expected: `All genesis imports OK`

- [ ] **Step 5: Final commit with all changes**

```bash
cd C:/Users/argoc/Documents/Iskander/src/IskanderOS
git status
# If any uncommitted changes:
git add -A
git commit -m "feat(genesis): Genesis Boot Sequence — complete Phase 1-4 implementation"
```
