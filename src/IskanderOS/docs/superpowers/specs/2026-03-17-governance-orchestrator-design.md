# Governance Orchestrator — Design Specification

> **Project:** Iskander — Sovereign Agentic AI OS for Distributed Cooperatives
> **Date:** 2026-03-17
> **Status:** Approved
> **Scope:** ComplianceFactory + PolicyEngine + TxOrchestrator

---

## 1. Purpose

Build a "Governance Orchestrator" layer where AI agents propose and humans execute. Three modules:

1. **ComplianceFactory** — jurisdiction-agnostic template DSL, RegulatoryScribe agent, DigitalNotary HITL flow
2. **PolicyEngine** — governance-as-code with immutable ICA constitutional core
3. **TxOrchestrator** — Safe multi-sig batch drafting, settlement reconciliation, TTL enforcement

Core invariant: **agents draft, humans sign**. The Iskander node never holds transaction-signing keys.

---

## 2. Existing Infrastructure

| Component | Status | Location |
|-----------|--------|----------|
| SecretaryAgent | Full | `backend/agents/library/secretary.py` |
| TreasuryAgent | Full | `backend/agents/library/treasurer.py` |
| MACIVoting.sol | Stub (Groth16 placeholder) | `contracts/src/governance/MACIVoting.sol` |
| StewardshipLedger.sol | Full | `contracts/src/governance/StewardshipLedger.sol` |
| CoopIdentity.sol | Full (ERC-4973 SBT) | `contracts/src/CoopIdentity.sol` |
| KnowledgeAsset | Full | `backend/schemas/knowledge.py` |
| Safe TX drafting | Exists in treasurer + governance_agent | `_build_safe_tx_draft()` pattern |
| SovereignStorage | Full (IPFS + Fernet) | `backend/mesh/sovereign_storage.py` |
| CausalEvent | Full | `backend/mesh/causal_event.py` |

**Not yet implemented:** ComplianceFactory, DigitalNotary, RegulatoryScribe, PolicyEngine, TxOrchestrator.

---

## 3. Schemas & Data Model

**File:** `backend/schemas/compliance.py`

### ComplianceManifest

```
template_id:      str          — unique ID, e.g. "uk-hmrc-ct600"
version:          int (≥1)     — monotonically increasing
jurisdiction:     str          — e.g. "GB", "ES", "*"
sector:           str          — e.g. "tax", "planning", "corporate"
title:            str          — human-readable name
boilerplate_hash: str          — SHA-256 of static template text (diff-lock anchor)
fields:           list[FieldDefinition]
content_cid:      str | None   — CID anchor after SovereignStorage registration
```

### FieldDefinition

```
field_id:          str          — unique within manifest, e.g. "company_name"
label:             str          — human-readable, e.g. "Registered Company Name"
data_source_path:  str          — dot-path into Iskander state, e.g. "treasury.pay_ratio"
validation_regex:  str | None   — optional value constraint
required:          bool (True)
```

### DraftDocument

```
draft_id:             UUID
manifest_id:          str
manifest_version:     int
manifest_content_cid: str          — exact manifest version CID (provenance)
filled_fields:        dict[str, str]
boilerplate_text:     str          — static text copied from template
rendered_text:        str          — final output with fields interpolated
status:               DraftStatus  — Draft|PendingReview|Approved|Notarized|Rejected
diff_lock_valid:      bool
created_at, reviewed_at, notarized_at: datetime
document_hash:        str | None   — SHA-256 of rendered_text (set at notarization)
signature:            str | None   — node signature over document_hash
mesh_cid:             str | None   — CID after Mesh Archive pinning
```

### DraftStatus Enum

```
Draft → PendingReview → Approved → Notarized
                      ↘ Rejected (terminal)
```

### GovernanceManifest

```
version:             int
content_cid:         str | None
policies:            list[PolicyRule]
constitutional_core: list[str]   — ICA principle IDs (cannot be overridden)
```

### PolicyRule

```
rule_id:         str          — e.g. "max_pay_ratio"
description:     str
constraint_type: enum(MaxValue, MinValue, RequireApproval, Deny)
value:           str          — threshold/parameter
applies_to:      list[str]   — agent IDs this rule constrains
```

### DraftedTransaction

```
tx_id:               UUID
safe_address:        str
transactions:        list[SafeTxPayload]
status:              TxStatus — Drafted|Pending|Executed|Settled|Stale|Cancelled
drafted_at, executed_at, settled_at: datetime
ttl_deadline:        datetime
on_chain_tx_hash:    str | None
rea_event_id:        str | None
policy_check_result: dict
manifest_diff:       str | None
```

### SafeTxPayload

```
to, value, data, operation, safeTxGas, baseGas, gasPrice,
gasToken, refundReceiver, nonce
# Iskander metadata extensions (underscore-prefixed):
_iskander_note, _iskander_payment_type, _iskander_mondragon_ratio
```

Mirrors the existing `_build_safe_tx_draft()` pattern from `treasurer.py` and
`governance_agent.py`, including all fields required by the Safe Transaction
Service API (`gasToken`, `refundReceiver`). Chain ID is set at export time.

### PolicyCheckResult

```
compliant: bool, violations: list[PolicyViolation],
warnings: list[str], checked_rules: int,
constitutional_checks_passed: bool
```

### PolicyViolation

```
rule_id, description, constraint_type, threshold,
actual_value: str | None, message: str
```

### DraftingState (extends AgentState in state.py)

```
# Inherits from AgentState: messages, agent_id, action_log, error
manifest_id, manifest_version, manifest_content_cid,
boilerplate_text, field_definitions, resolved_fields,
filled_fields, rendered_text, diff_lock_valid,
draft_status, rationale_log, version_warnings,
approval_status  # Pending|Approved|Settled|Expired
```

Note: `action_log` is inherited from AgentState — do NOT redeclare it.

---

## 4. ComplianceFactory & RegulatoryScribe

### Template Storage (Option B — Filesystem + CID Anchoring)

Templates stored as JSON files in `backend/compliance/manifests/`. Each version is content-hashed and the hash registered via SovereignStorage for provenance.

### ManifestRegistry (`backend/compliance/manifest_registry.py`)

Singleton (`get_instance()`). Loads manifests from the manifests directory.

| Method | Description |
|--------|-------------|
| `register_manifest(manifest)` | Validate, compute boilerplate_hash, pin CID anchor |
| `get_manifest(template_id, version=None)` | Return specific version (latest if None) |
| `list_manifests()` | All registered templates |
| `_check_version_currency(template_id, version)` | Warning if newer version exists |

### RegulatoryScribe (`backend/agents/compliance/regulatory_scribe.py`)

LangGraph StateGraph:

```
load_manifest → resolve_data_sources → fill_fields → validate_fields
  → render_document → diff_lock_check → END
```

| Node | Purpose |
|------|---------|
| `load_manifest` | Fetch manifest; warn if outdated |
| `resolve_data_sources` | Map `data_source_path` → values via DataSourceResolver |
| `fill_fields` | Substitute values into field slots. ONLY touches declared fields |
| `validate_fields` | Check `validation_regex`, flag missing required fields |
| `render_document` | Produce `rendered_text` by interpolating fields into boilerplate |
| `diff_lock_check` | SHA-256 boilerplate sections vs. `manifest.boilerplate_hash`. Mismatch → diff_lock_valid=False |

### DataSourceResolver

Maps dot-paths to internal state:
- `"identity.coop_name"` → `settings.coop_name`
- `"treasury.pay_ratio"` → InternalPayroll config
- `"treasury.safe_address"` → `settings.safe_address`
- Extensible per jurisdiction.

---

## 5. DigitalNotary

**File:** `backend/compliance/digital_notary.py` — singleton.

| Method | Description |
|--------|-------------|
| `submit_for_review(draft)` | Transition to PendingReview, generate diff |
| `approve(draft_id, reviewer_did)` | Check diff_lock_valid (auto-reject if False), transition to Approved |
| `notarize(draft_id)` | Compute hash, sign, pin to SovereignStorage, create CausalEvent("governance.document.notarized"), embed provenance footer |
| `reject(draft_id, reason)` | Terminal state, tombstone-only |

Notarization steps:
1. `document_hash` = SHA-256 of `rendered_text`
2. Sign with node key (STUB: HMAC-SHA256; production: Ed25519)
3. Pin signed document + signature via SovereignStorage
4. Create CausalEvent with `audience="federation"`
5. Embed `manifest_content_cid` + `document_hash` + `signature` in provenance footer

---

## 6. PolicyEngine

**File:** `backend/governance/policy_engine.py` — singleton.

| Method | Description |
|--------|-------------|
| `load_manifest(path)` | Read JSON, validate, compute CID anchor |
| `check_compliance(agent_id, action_type, params)` | Returns PolicyCheckResult(compliant, violations, warnings) |

### Constitutional Core

Hardcoded ICA checks that run after manifest checks and cannot be overridden by manifest updates:

- **Anti-extractive:** No transaction can benefit a single member at the expense of the collective
- **Democratic control:** No single agent can bypass M-of-N approval
- **Transparency:** Every proposal must produce a Glass Box AgentAction
- **Open membership:** Agent proposals cannot discriminate by identity attributes

These are code-level invariants, not manifest-configurable.

### Integration

TreasuryAgent's `validate_payment` node calls `PolicyEngine.check_compliance()` before `draft_payment_tx`. Non-compliant → graph short-circuits with violation details.

---

## 7. TxOrchestrator

**File:** `backend/finance/tx_orchestrator.py` — singleton extending existing Safe-drafting pattern.

| Method | Description |
|--------|-------------|
| `draft_batch(proposals, requester_did)` | PolicyEngine check → build Safe payload → store in pending_transactions |
| `verify_settlement(tx_id, tx_hash)` | Check chain (STUB); on confirm: status→Settled, CausalEvent("governance.transaction.settled"), link REA entry |
| `purge_stale()` | Scan past-TTL drafts → status→Stale, emit warning. No auto-cancel |
| `cancel(tx_id, reason)` | Manual cancellation by steward |
| `export_safe_batch(tx_id)` | Export as Gnosis Safe batch JSON (compatible with Safe UI import) |

### Security Invariant

The node holds a `propose_key` (submit unsigned drafts). It NEVER holds a `sign_key`. Fraudulent proposals are harmless unsigned payloads. Safe owners revoke propose_key immediately if compromised.

---

## 8. Router & Endpoints

**File:** `backend/routers/compliance.py` — prefix `/compliance`, tags `["compliance-factory"]`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/manifests/register` | steward | Register a ComplianceManifest |
| GET | `/manifests` | worker-owner, steward | List all manifests |
| GET | `/manifests/{template_id}` | worker-owner, steward | Get manifest |
| POST | `/generate-draft` | worker-owner, steward | Invoke RegulatoryScribe |
| GET | `/drafts/{draft_id}` | worker-owner, steward | Get draft with diff |
| POST | `/drafts/{draft_id}/approve` | steward | HITL approval |
| POST | `/drafts/{draft_id}/reject` | steward | HITL rejection |
| POST | `/drafts/{draft_id}/notarize` | steward | Digital notarization |
| POST | `/tx/draft` | steward | Draft Safe batch transaction |
| GET | `/tx/{tx_id}` | worker-owner, steward | Get drafted transaction |
| POST | `/tx/{tx_id}/settle` | steward | Record settlement |
| GET | `/tx/{tx_id}/export` | steward | Export Safe batch JSON |
| GET | `/tx/stale` | steward | List stale transactions |
| POST | `/policy/check` | worker-owner, steward | Check action against PolicyEngine |

### Config Additions

```
compliance_manifests_dir: str = "backend/compliance/manifests"
tx_draft_ttl_days: int = 14
notary_signing_key_env: str = "ISKANDER_NOTARY_KEY"
governance_manifest_path: str = "backend/governance/governance_manifest.json"
tx_stale_check_interval_hours: int = 24
```

---

## 9. Red Team Analysis

### Cross-Module Attack Surface

| ID | Vector | Severity | Mitigation |
|----|--------|----------|------------|
| VULN-CF-1 | Scribe modifies boilerplate to insert malicious clauses | CRITICAL | **Diff-Lock:** SHA-256 of boilerplate must match manifest hash. Mismatch → auto-reject before human review |
| VULN-CF-2 | Outdated manifest used for live submission | HIGH | ManifestRegistry checks latest version, emits warning. Notary refuses drafts >2 versions behind |
| VULN-CF-3 | Compromised propose_key submits fraudulent Safe batches | HIGH | **No Auto-Sign:** Node never holds signing keys. Unsigned proposals cannot move funds. Safe owners revoke immediately |
| VULN-CF-4 | PolicyEngine manifest tampered to disable ICA checks | CRITICAL | **Constitutional Core:** ICA invariants are hardcoded. Manifest can only add constraints, never remove constitutional ones |
| VULN-CF-5 | Stale transactions accumulate as DoS on pending_transactions | MEDIUM | TTL enforcement: `purge_stale()` transitions to Stale. Manual cancel by steward |
| VULN-CF-6 | Notary signs document, manifest retroactively changed | HIGH | **Provenance CID:** Notarized doc embeds `manifest_content_cid`. Immutable via CausalEvent |

### Systemic Risks

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| SYS-1 | DataSourceResolver returns stale data during field filling | Incorrect compliance docs | Resolver reads live state (singletons). Filled values shown in HITL diff for human verification |
| SYS-2 | PolicyEngine.check_compliance() becomes a bottleneck (called by every agent) | Latency spike | PolicyEngine is in-memory, manifest loaded at startup. No I/O per check. Reload only on manifest file change |
| SYS-3 | Constitutional Core checks are too rigid for evolving ICA principles | Cooperative cannot adapt governance | Constitutional Core is a code-level minimum floor, not a ceiling. Manifest adds rules on top. Principle evolution requires a code release (deliberate, auditable friction) |
| SYS-4 | TxOrchestrator verify_settlement fails to detect reorgs | Double-counted settlement | Production: wait for N confirmations (configurable). Stub: immediate. CausalEvent is append-only, so reorg detection adds a new event, doesn't delete the old one |
| SYS-5 | Multiple concurrent Scribe invocations for same manifest produce conflicting drafts | Confusion over which draft is canonical | Each draft gets unique UUID. Only one can be Approved at a time per manifest_id (enforced by DigitalNotary) |
| SYS-6 | DigitalNotary signing key leaked | Forged notarizations | Key loaded from env var (never in code). STUB uses HMAC; production uses Ed25519 with hardware key. CausalEvent provides tamper-evident audit trail. Compromised key → tombstone all notarizations from that key (same pattern as Credential Embassy) |

### Interaction with Existing Modules

| Interaction | Risk | Mitigation |
|-------------|------|------------|
| PolicyEngine ↔ TreasuryAgent | Treasury ignores PolicyEngine | `check_compliance()` called at graph node level. Non-compliant → graph short-circuits. Test enforces this |
| ComplianceFactory ↔ KnowledgeAsset | Notarized documents not tracked in Knowledge Commons | Notarized docs are pinned to SovereignStorage and get a CID. Optional: register as KnowledgeAsset for curator review. Phase B concern |
| TxOrchestrator ↔ existing `_build_safe_tx_draft()` | Two competing Safe-drafting patterns | TxOrchestrator supersedes the inline pattern. Phase B: refactor treasurer to call `TxOrchestrator.draft_batch()` instead of building payloads inline |
| DigitalNotary ↔ Credential Embassy | Document signing uses different key than VC verification | Separate key purposes: notary_signing_key (document integrity) vs. TrustRegistry keys (VC issuer identity). No cross-contamination |

---

## 10. Files to Create/Modify

| # | File | Action | Purpose |
|---|------|--------|---------|
| 1 | `backend/schemas/compliance.py` | CREATE | All Pydantic models: ComplianceManifest, FieldDefinition, DraftDocument, DraftStatus, GovernanceManifest, PolicyRule, DraftedTransaction, SafeTxPayload, TxStatus, API request/response models |
| 2 | `backend/agents/state.py` | MODIFY | Add DraftingState(AgentState) |
| 3 | `backend/compliance/__init__.py` | CREATE | Package init |
| 4 | `backend/compliance/manifest_registry.py` | CREATE | ManifestRegistry singleton — template loading, CID anchoring, version checks |
| 5 | `backend/compliance/data_source_resolver.py` | CREATE | DataSourceResolver — maps dot-paths to Iskander state |
| 6 | `backend/agents/compliance/__init__.py` | CREATE | Package init |
| 7 | `backend/agents/compliance/regulatory_scribe.py` | CREATE | LangGraph StateGraph — manifest→fill→validate→render→diff-lock |
| 8 | `backend/compliance/digital_notary.py` | CREATE | DigitalNotary singleton — HITL approval, signing, Mesh pinning |
| 9 | `backend/governance/__init__.py` | CREATE | Package init |
| 10 | `backend/governance/policy_engine.py` | CREATE | PolicyEngine singleton — manifest reading, compliance checks, constitutional core |
| 11 | `backend/governance/governance_manifest.json` | CREATE | Default governance manifest with ICA constitutional core |
| 12 | `backend/finance/tx_orchestrator.py` | CREATE | TxOrchestrator singleton — Safe batch drafting, settlement, TTL |
| 13 | `backend/compliance/manifests/example-uk-payment.json` | CREATE | Example manifest for testing |
| 14 | `backend/routers/compliance.py` | CREATE | FastAPI router — 14 endpoints |
| 15 | `backend/main.py` | MODIFY | Register compliance router |
| 16 | `backend/config.py` | MODIFY | Add compliance/governance/tx settings |
| 17 | `infra/init.sql` | MODIFY | Add compliance_manifests, draft_documents, drafted_transactions tables |
| 18 | `tests/test_compliance_factory.py` | CREATE | ComplianceFactory + RegulatoryScribe + DigitalNotary tests |
| 19 | `tests/test_policy_engine.py` | CREATE | PolicyEngine + constitutional core tests |
| 20 | `tests/test_tx_orchestrator.py` | CREATE | TxOrchestrator + settlement + TTL tests |
| 21 | `tests/test_governance_integration.py` | CREATE | Leeds Housing Co-op end-to-end scenario |

---

## 11. Implementation Phases (Token-Efficient)

### Phase 1: Schemas + Config + State (Foundation)
- `backend/schemas/compliance.py` — all models
- `backend/agents/state.py` — DraftingState
- `backend/config.py` — settings additions
- `infra/init.sql` — table additions

**Why first:** Every other module imports from schemas. Zero dependencies, maximum reuse.

### Phase 2: PolicyEngine (Governance Core)
- `backend/governance/policy_engine.py`
- `backend/governance/governance_manifest.json`
- `tests/test_policy_engine.py`

**Why second:** PolicyEngine has no dependencies on ComplianceFactory or TxOrchestrator, but both depend on it. Building it early means Phase 3 and 4 can call `check_compliance()` immediately.

### Phase 3: ComplianceFactory (Templates + Scribe + Notary)
- `backend/compliance/manifest_registry.py`
- `backend/compliance/data_source_resolver.py`
- `backend/agents/compliance/regulatory_scribe.py`
- `backend/compliance/digital_notary.py`
- `backend/compliance/manifests/example-uk-payment.json`
- `tests/test_compliance_factory.py`

**Why third:** Depends on schemas (Phase 1) and PolicyEngine (Phase 2). Self-contained otherwise.

### Phase 4: TxOrchestrator (Safe Batch + Settlement)
- `backend/finance/tx_orchestrator.py`
- `tests/test_tx_orchestrator.py`

**Why fourth:** Depends on schemas and PolicyEngine. Extends the existing Safe-drafting pattern from treasurer.py.

### Phase 5: Router + Integration + Wiring
- `backend/routers/compliance.py`
- `backend/main.py` — register router
- `tests/test_governance_integration.py` — Leeds Housing Co-op scenario
- Package `__init__.py` files

**Why last:** Router is a thin HTTP layer over the modules built in Phases 2-4. Integration test exercises the full pipeline.

---

## 12. Test Plan

### Phase 2 Tests (PolicyEngine)
- `test_compliant_action_passes`
- `test_non_compliant_action_blocked`
- `test_constitutional_core_cannot_be_overridden`
- `test_policy_applies_to_correct_agents`
- `test_manifest_load_and_cid_anchor`
- `test_missing_manifest_raises`

### Phase 3 Tests (ComplianceFactory)
- `test_register_manifest`
- `test_manifest_version_warning`
- `test_scribe_fills_fields_only`
- `test_diff_lock_rejects_modified_boilerplate`
- `test_notarize_pins_to_mesh`
- `test_provenance_cid_in_notarized_doc`
- `test_draft_status_transitions`
- `test_reject_is_terminal`
- `test_auto_reject_on_diff_lock_violation`

### Phase 4 Tests (TxOrchestrator)
- `test_draft_batch_stores_in_pending`
- `test_verify_settlement_updates_status`
- `test_stale_detection`
- `test_export_safe_batch_format`
- `test_policy_check_before_draft`
- `test_cancel_transition`

### Phase 5 Tests (Integration)
- `test_leeds_housing_coop_payment` — Register manifest → PolicyEngine loaded → Treasury drafts £35k payment → passes policy → Safe batch exported → settlement verified → REA entry → CausalEvent pinned
