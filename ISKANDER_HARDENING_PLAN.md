# Project Iskander — Red Team Hardening Plan

> **Purpose**: Address all 7 vulnerabilities identified by Gemini Red Team reviews (R1 + R3).
> **Generated**: 2026-03-17 | **Updated**: 2026-03-17 (R3 Boundary Agent amendment) | **Priority**: CRITICAL first, then HIGH, then MEDIUM.

---

## Context

Gemini performed three rounds of Red Team review. R1 identified 6 internal vulnerabilities, all confirmed against codebase. R2 added second-order amendments (Break-Glass protocols). R3 identified a 7th class: **cross-SDC interoperability failures** at federation boundaries.

**Confirmed vulnerabilities**:
1. **CRITICAL — Oracle Centralization**: `setOracle()` has zero multi-sig/timelock. Oracle can unilaterally rewrite scores, reserves, and rotate itself.
2. **CRITICAL — Glass Box Rationalization**: `AgentAction.rationale` is free-text with zero validation. Agents write their own justifications.
3. **HIGH — Mesh Data Availability**: CIDs pinned to single in-memory node. No replication count enforcement.
4. **HIGH — Sync-Conflict Split-Brain**: DeltaSync has no conflict resolution or canonical sequencer.
5. **MEDIUM — Hardware Privilege Escalation**: `psutil` can be spoofed by user-level code.
6. **MEDIUM — HITL Exhaustion DoS**: No rate-limiting on HITL-triggering endpoints.
7. **HIGH — Federation Boundary Exploitation** (R3): Foreign SDCs can inject ethically-laundered data, semantically-incompatible scores, and governance actions from weaker systems. No trust quarantine, ontology translation, or causal ordering at federation boundaries.

---

## FIX 1: Oracle Decentralization (CRITICAL)

### Problem
`StewardshipLedger.sol` lines 107-110: `onlyOracle` modifier gates 6 critical functions with a single address. `setOracle()` (line 262) lets the oracle rotate itself instantly with no timelock.

### Solution: Timelock + Multi-Sig Oracle

**Files to modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `contracts/src/governance/StewardshipLedger.sol` | MODIFY | Add 48-hour timelock on `setOracle()`, `setThreshold()`. Add `pendingOracle`, `pendingOracleActivation` state. Add `proposeOracle()` + `acceptOracle()` two-step pattern |
| 2 | `contracts/src/governance/StewardshipLedger.sol` | MODIFY | Add `quorumOracleUpdate` — require N-of-M signatures for `updateImpactScores()` batches above a size threshold |
| 3 | `contracts/src/governance/IStewardshipLedger.sol` | MODIFY | Add `proposeOracle()`, `acceptOracle()`, `OracleProposed`, `OracleAccepted` events |
| 4 | `contracts/test/StewardshipLedger.t.sol` | MODIFY | Add tests: timelock enforcement, early acceptance revert, propose→accept flow, threshold timelock |

**Design**:
```solidity
// Two-step oracle rotation with 48h timelock
address public pendingOracle;
uint256 public pendingOracleActivation; // block.timestamp + 48 hours
uint256 public constant ORACLE_TIMELOCK = 48 hours;

function proposeOracle(address newOracle) external onlyOracle {
    if (newOracle == address(0)) revert ZeroAddress();
    pendingOracle = newOracle;
    pendingOracleActivation = block.timestamp + ORACLE_TIMELOCK;
    emit OracleProposed(newOracle, pendingOracleActivation);
}

function acceptOracle() external {
    if (msg.sender != pendingOracle) revert NotPendingOracle();
    if (block.timestamp < pendingOracleActivation) revert TimelockActive(pendingOracleActivation);
    oracle = pendingOracle;
    pendingOracle = address(0);
    emit OracleAccepted(oracle);
}
```

**Why not full TSS**: The oracle is already intended to be a Safe multi-sig (Deploy.s.sol defaults `STEWARDSHIP_ORACLE` to `steward`). The timelock adds defense-in-depth — even if the multi-sig is compromised, there's a 48h window for the cooperative to react.

### AMENDMENT (Gemini R2): Emergency Bypass — The Liquidity Trap

**Second-order risk**: During a bank run or market crash, the 48h timelock prevents immediate circuit breaker activation. The cooperative is frozen when it most needs to act.

**Fix**: Add `triggerEmergencyCircuitBreaker()` that bypasses the timelock but requires **unanimous** multi-sig approval (all signers, not just threshold).

```solidity
// Emergency circuit breaker — bypasses timelock, requires UNANIMOUS Safe approval
// The Safe must be configured with a separate "emergency" threshold = total signers
function triggerEmergencyCircuitBreaker() external onlyOracle {
    // This function does NOT rotate the oracle — it only activates the breaker.
    // The oracle (Safe multi-sig) must be configured to require ALL signers for this call.
    totalEscrowValue = type(uint256).max; // Forces _checkCircuitBreaker() to trip
    emit CircuitBreakerTripped(totalEscrowValue, fiatReserveValue * solvencyFactorBps / 10000);
    emit EmergencyCircuitBreakerActivated(msg.sender, block.timestamp);
}

// Reset requires normal oracle flow (still timelocked for oracle rotation)
function resetEmergencyCircuitBreaker(uint256 actualEscrow) external onlyOracle {
    totalEscrowValue = actualEscrow;
    emit EmergencyCircuitBreakerReset(msg.sender, actualEscrow);
}
```

**Additional files**:
| # | File | Action | Change |
|---|------|--------|--------|
| 5 | `contracts/src/governance/StewardshipLedger.sol` | MODIFY | Add `triggerEmergencyCircuitBreaker()`, `resetEmergencyCircuitBreaker()`, new events |
| 6 | `contracts/src/governance/IStewardshipLedger.sol` | MODIFY | Add `EmergencyCircuitBreakerActivated`, `EmergencyCircuitBreakerReset` events |
| 7 | `contracts/test/StewardshipLedger.t.sol` | MODIFY | Add `test_emergencyCircuitBreaker_trips`, `test_emergencyCircuitBreaker_blocks_delegation`, `test_resetEmergencyCircuitBreaker` |

**Safe configuration requirement**: Document that the Safe multi-sig must have TWO thresholds — standard (e.g., 3-of-5) for normal oracle ops, and unanimous (5-of-5) for emergency bypass. This is enforced by deploying a separate Safe with `threshold = owners.length` and calling `triggerEmergencyCircuitBreaker()` from that Safe.

---

## FIX 2: Adversarial Rationale Verification (CRITICAL)

### Problem
`AgentAction.rationale` (glass_box.py line 32) is free-text. All agent nodes (stewardship_scorer.py lines 85-455, fiat_gateway.py lines 99-322) write their own rationales with zero cross-validation.

### Solution: CCIN Compliance Checker + Rationale Hash Binding

**Files to create/modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/agents/core/ccin_verifier.py` | CREATE | `verify_rationale(action: AgentAction) -> CCINVerdict` — second-pass LLM call that scores rationale against 10 CCIN principles. Returns violation score 0-100 |
| 2 | `backend/schemas/glass_box.py` | MODIFY | Add `payload_hash: str` field to `AgentAction` — SHA-256 of the payload at time of rationale writing. Binds rationale to specific data |
| 3 | `backend/agents/library/stewardship_scorer.py` | MODIFY | After each AgentAction creation, call `verify_rationale()`. If violation_score > 25, set `error` in state and halt graph |
| 4 | `backend/agents/library/fiat_gateway.py` | MODIFY | Same pattern |
| 5 | `infra/init.sql` | MODIFY | Add `ccin_verification_log` table: `agent_action_id FK, violation_score, flagged_principles TEXT[], verifier_model` |

**Design**:
```python
# backend/agents/core/ccin_verifier.py
CCIN_VERIFICATION_PROMPT = """
You are a CCIN Compliance Auditor. Given an agent's action and rationale,
score it against the 10 CCIN Cooperative Principles.
Output JSON: {"violation_score": 0-100, "flagged_principles": [...], "explanation": "..."}
A score of 0 = fully compliant. A score > 25 = HALT the action.
"""

async def verify_rationale(action: AgentAction) -> CCINVerdict:
    # Uses a DIFFERENT model instance than the action-generating agent
    # to prevent self-rationalization
    ...
```

**Why this works**: The verifier runs on a separate LLM call with a hardcoded adversarial prompt. It cannot be influenced by the agent's own prompt injection because it receives only the structured `AgentAction` object, not the agent's conversation history.

**`payload_hash` binding**: The rationale is cryptographically bound to the payload data. If the payload changes after the rationale is written, the hash mismatch is detected.

### AMENDMENT (Gemini R2): Compliance Drift — Versioned CCIN Definitions

**Second-order risk**: Over time, the CCIN verification prompt may be tuned to be more permissive. Past actions that were "compliant" under v1 may be non-compliant under v2, but the audit trail doesn't record which version was used.

**Fix**: Add `ccin_verifier_version: str` to both `AgentAction` and `ccin_verification_log`.

```python
# backend/agents/core/ccin_verifier.py
CCIN_VERIFIER_VERSION = "1.0.0"  # Bumped on every prompt change

async def verify_rationale(action: AgentAction) -> CCINVerdict:
    verdict = await _run_verification(action)
    verdict.verifier_version = CCIN_VERIFIER_VERSION
    return verdict
```

**Additional schema changes**:
| # | File | Action | Change |
|---|------|--------|--------|
| 6 | `backend/schemas/glass_box.py` | MODIFY | Add `ccin_verifier_version: str | None` to `AgentAction` |
| 7 | `infra/init.sql` | MODIFY | Add `verifier_version TEXT` column to `ccin_verification_log` |

**Governance rule**: CCIN prompt changes require the same HITL approval as steward threshold changes. The version history is stored in `ccin_verification_log` so auditors can retroactively evaluate compliance drift.

---

## FIX 3: Federated Pinning Protocol (HIGH)

### Problem
`sovereign_storage.py` line 69: in-memory store. `causal_event.py` line 87: CID returned without replication check. `delta_sync.py` lines 71-75: sync is stubbed.

### Solution: Minimum Replication Count + Pin Receipts

**Files to modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/mesh/sovereign_storage.py` | MODIFY | Add `pin()` return field `replica_count`. Add `verify_availability(cid) -> int` method that checks N peers |
| 2 | `backend/mesh/causal_event.py` | MODIFY | After `pin()`, call `broadcast_pin_request()` to federation. Wait for `min_replicas` acks before returning CID as committed |
| 3 | `backend/mesh/delta_sync.py` | MODIFY | Add `PinReceipt` dataclass. `sync_to_peer()` returns signed receipt. Track receipts per CID |
| 4 | `backend/config.py` | MODIFY | Add `mesh_min_replicas: int = 3` and `mesh_pin_timeout_seconds: int = 30` |
| 5 | `backend/schemas/mesh.py` | MODIFY | Add `replica_count` to `PinResponse`. Add `PinReceiptResponse` |
| 6 | `infra/init.sql` | MODIFY | Add `pin_receipts` table: `cid, peer_did, receipt_signature, received_at` |

**Design**:
```python
# Governance-critical events require 3+ replicas
async def pin(self, data: bytes, audience: str, min_replicas: int = 0) -> tuple[str, int, AgentAction]:
    cid = self._local_pin(data, audience)
    if min_replicas > 0:
        receipts = await self._broadcast_and_collect(cid, data, min_replicas, timeout=30)
        if len(receipts) < min_replicas:
            raise InsufficientReplication(cid, len(receipts), min_replicas)
    return cid, len(receipts), action
```

**CausalEvent types requiring replication**: `governance`, `arbitration`, `veto` — must have `min_replicas=3`. Other types default to local-only.

### AMENDMENT (Gemini R2): Geo-Diversity Pinning — The Colocation Fallacy

**Second-order risk**: 3 replicas on 3 nodes in the same building, same ISP, same power grid. A single outage kills all replicas.

**Fix**: Track `NodeMetadata` and enforce spatial diversity in replica selection.

```python
# backend/mesh/sovereign_storage.py
@dataclass
class NodeMetadata:
    peer_did: str
    region: str          # e.g., "eu-west", "us-east", "latam"
    isp: str             # e.g., "hetzner", "digitalocean", "community-mesh"
    power_source: str    # e.g., "grid", "solar", "battery"

async def _select_diverse_peers(self, min_replicas: int, candidates: list[NodeMetadata]) -> list[NodeMetadata]:
    """Select peers maximizing region + ISP diversity."""
    selected = []
    used_regions = set()
    used_isps = set()
    # Priority: different regions first, then different ISPs
    for candidate in sorted(candidates, key=lambda c: (c.region in used_regions, c.isp in used_isps)):
        selected.append(candidate)
        used_regions.add(candidate.region)
        used_isps.add(candidate.isp)
        if len(selected) >= min_replicas:
            break
    return selected
```

**Additional files**:
| # | File | Action | Change |
|---|------|--------|--------|
| 7 | `backend/mesh/sovereign_storage.py` | MODIFY | Add `NodeMetadata` dataclass, `_select_diverse_peers()` method |
| 8 | `backend/config.py` | MODIFY | Add `mesh_require_geo_diversity: bool = True`, `mesh_min_distinct_regions: int = 2` |
| 9 | `infra/init.sql` | MODIFY | Add `node_metadata` table: `peer_did UNIQUE, region, isp, power_source, last_seen_at` |

**Governance rule**: For governance-critical events, replicas MUST span at least 2 distinct regions OR 3 distinct ISPs. Configurable via `mesh_min_distinct_regions`.

---

## FIX 4: Chain-Anchored Sync Resolution (HIGH)

### Problem
DeltaSync has no conflict resolution. Two partitioned nodes can issue conflicting governance changes.

### Solution: Blockchain as Canonical Sequencer

**Files to modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/mesh/delta_sync.py` | MODIFY | Add `validate_chain_anchor(cid, expected_block_hash)` — reject CIDs that don't reference a valid on-chain anchor |
| 2 | `backend/mesh/causal_event.py` | MODIFY | For governance events, write anchor hash to `causal_events.on_chain_anchor` before considering event committed |
| 3 | `backend/mesh/sovereign_storage.py` | MODIFY | Add `anchor_to_chain(cid) -> tx_hash` method — submits CID hash to a simple on-chain anchor contract |

**Design principle**: The IPFS mesh stores DATA/CONTEXT. The blockchain stores TRUTH/SEQUENCE. DeltaSync rejects any governance CID that doesn't have a matching `on_chain_anchor`. Split-brain is resolved by blockchain block ordering — whichever governance action has the earlier block number wins.

### AMENDMENT (Gemini R2): Batched Anchoring — The Gas Price Vulnerability

**Second-order risk**: A governance battle triggers hundreds of anchors. Gas spikes. Poorest nodes can't afford anchoring → effectively censored.

**Fix**: Implement Merkle-Root-as-a-Service. Multiple nodes pool their CID hashes into a single on-chain Merkle root transaction.

```python
# backend/mesh/anchor_batcher.py
class AnchorBatcher:
    """Collects CID hashes from multiple nodes into a single Merkle root."""

    def __init__(self, batch_window: int = 60):  # seconds
        self._pending: list[tuple[str, str]] = []  # (cid, source_node_did)
        self._batch_window = batch_window

    async def submit(self, cid: str, source_node_did: str) -> str:
        """Add CID to the current batch. Returns batch_id."""
        self._pending.append((cid, source_node_did))
        return self._current_batch_id

    async def flush(self) -> str:
        """Compute Merkle root and anchor to chain as single tx. Returns tx_hash."""
        leaves = [keccak256(cid.encode()) for cid, _ in self._pending]
        root = compute_merkle_root(leaves)
        tx_hash = await self._anchor_root(root)
        # All CIDs in the batch share this tx_hash as their on_chain_anchor
        for cid, _ in self._pending:
            await self._update_anchor(cid, tx_hash, root)
        self._pending.clear()
        return tx_hash
```

**Additional files**:
| # | File | Action | Change |
|---|------|--------|--------|
| 4 | `backend/mesh/anchor_batcher.py` | CREATE | `AnchorBatcher` with batch window, Merkle root computation, single-tx anchoring |
| 5 | `backend/config.py` | MODIFY | Add `mesh_anchor_batch_window_seconds: int = 60` |

**Cost reduction**: Instead of N transactions (one per CID), the batch produces 1 transaction per window. Nodes split the gas cost proportionally.

---

## FIX 5: Signed Sensor Protocol (MEDIUM)

### Problem
`hearth_interface.py` line 92: `psutil.sensors_battery()` can be spoofed by user-level code.

### Solution: Signature Verification with Graceful Degradation

**Files to modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/energy/hearth_interface.py` | MODIFY | Add `_read_signed_battery()` method that checks for signed telemetry from hardware HAT. Fallback to `psutil` with `is_verified=False` flag |
| 2 | `backend/energy/resource_policy_engine.py` | MODIFY | If `is_verified=False`, cap maximum energy level at YELLOW (never trust unverified GREEN) |
| 3 | `backend/config.py` | MODIFY | Add `energy_require_signed_telemetry: bool = False` (opt-in for hardware nodes) |

**Design**:
```python
def _read_battery(self) -> dict[str, Any]:
    signed = self._read_signed_battery()  # Try hardware HAT first
    if signed is not None:
        return {**signed, "is_verified": True}
    # Fallback: psutil (unverified)
    psutil_data = self._read_psutil_battery()
    return {**psutil_data, "is_verified": False}
```

**Policy change**: Unverified sensors can never report GREEN. This prevents psutil spoofing from unlocking full agent capabilities. Only signed hardware telemetry gets GREEN.

### AMENDMENT (Gemini R2): Legacy Hardware Mode — The Obsolescence Trap

**Second-order risk**: New Hearth PCB releases change signature format. Old boards become "unverified" overnight, forcing all legacy nodes into YELLOW permanently.

**Fix**: Support versioned signature formats with a deprecation grace period.

```python
# backend/energy/hearth_interface.py
SUPPORTED_SIGNATURE_VERSIONS = {
    "v1": {"algorithm": "ed25519", "deprecated": False, "trust_penalty": 0},
    "v0": {"algorithm": "hmac-sha256", "deprecated": True, "trust_penalty": 1},
    # v0 gets trust_penalty=1 → max level capped at YELLOW after grace period
}
LEGACY_GRACE_PERIOD_DAYS = 180  # 6 months before deprecated versions lose GREEN

def _validate_signature(self, sig_data: dict) -> tuple[bool, int]:
    """Returns (is_valid, trust_penalty)."""
    version = sig_data.get("version", "v0")
    spec = SUPPORTED_SIGNATURE_VERSIONS.get(version)
    if spec is None:
        return False, 2  # Unknown version → RED
    if spec["deprecated"] and self._past_grace_period(version):
        return True, spec["trust_penalty"]  # Valid but penalized
    return self._verify_crypto(sig_data, spec["algorithm"]), 0
```

**Additional config**:
| # | File | Action | Change |
|---|------|--------|--------|
| 4 | `backend/config.py` | MODIFY | Add `energy_legacy_grace_period_days: int = 180` |

**Degradation path**: `v0` hardware gets 180 days at GREEN, then drops to YELLOW. Cooperative must plan hardware refresh within the grace window. No hard brick.

---

## FIX 6: HITL Rate Limiter (MEDIUM)

### Problem
`/fiat/mint`, `/fiat/burn`, `/stewardship/compute-scores` create unbounded HITL gates. No rate limiting. No batching.

### Solution: Per-Role Rate Limiter + Request Batching Window

**Files to create/modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/api/hitl_rate_limiter.py` | CREATE | `HITLRateLimiter` — sliding window rate limiter. Max N HITL-triggering requests per role per window |
| 2 | `backend/routers/fiat.py` | MODIFY | Add `Depends(hitl_rate_check)` to `/mint` and `/burn` endpoints |
| 3 | `backend/routers/stewardship.py` | MODIFY | Add `Depends(hitl_rate_check)` to `/compute-scores` and `/threshold/review` |
| 4 | `backend/config.py` | MODIFY | Add `hitl_max_requests_per_hour: int = 10`, `hitl_batch_window_seconds: int = 300` |
| 5 | `infra/init.sql` | MODIFY | Add `hitl_rate_log` table: `user_address, endpoint, requested_at` |

**Design**:
```python
class HITLRateLimiter:
    """Sliding window rate limiter for HITL-triggering endpoints."""

    async def check(self, user: AuthenticatedUser, endpoint: str) -> None:
        recent = self._count_recent(user.address, endpoint, window=3600)
        if recent >= settings.hitl_max_requests_per_hour:
            raise HTTPException(
                status_code=429,
                detail=f"HITL rate limit exceeded: {recent}/{settings.hitl_max_requests_per_hour} per hour"
            )
```

**Batching**: Multiple mint/burn requests within a 5-minute window are collapsed into a single HITL approval showing the aggregate.

### AMENDMENT (Gemini R2): Crisis Mode — The Emergency DoS Trap

**Second-order risk**: During an attack, humans need to approve 50 urgent remediation transactions. The rate limiter (10/hour) blocks them from fixing the attack.

**Fix**: Add "Break-Glass" crisis mode that auto-expands rate limits when `EmergencyVeto` or `CircuitBreaker` is active.

```python
# backend/api/hitl_rate_limiter.py
CRISIS_MULTIPLIER = 100  # 10/hour → 1000/hour during crisis

class HITLRateLimiter:
    async def check(self, user: AuthenticatedUser, endpoint: str) -> None:
        limit = settings.hitl_max_requests_per_hour
        if await self._is_crisis_mode_active():
            limit *= CRISIS_MULTIPLIER
            logger.warning("HITL crisis mode active — rate limit expanded to %d/hour", limit)
        recent = self._count_recent(user.address, endpoint, window=3600)
        if recent >= limit:
            raise HTTPException(status_code=429, detail=...)

    async def _is_crisis_mode_active(self) -> bool:
        """Check if EmergencyVeto is filed or CircuitBreaker is tripped."""
        # Check veto_records for any status='filed' in last 24 hours
        # Check solvency_snapshots for circuit_breaker_active=True
        # STUB: return False
        return False
```

**Additional files**:
| # | File | Action | Change |
|---|------|--------|--------|
| 6 | `backend/api/hitl_rate_limiter.py` | MODIFY | Add `_is_crisis_mode_active()`, `CRISIS_MULTIPLIER` |
| 7 | `backend/config.py` | MODIFY | Add `hitl_crisis_multiplier: int = 100` |

**Trigger conditions**: Crisis mode activates when ANY of:
- `veto_records` has a row with `status='filed'` in the last 24 hours
- `solvency_snapshots` has `circuit_breaker_active=True`
- `energy_events` has `level='RED'` in the last hour

---

## Implementation Order

| Priority | Fix | Files Changed | Estimated Complexity |
|----------|-----|---------------|---------------------|
| 1 | Oracle Timelock (Fix 1) | 4 files | Medium — Solidity state changes + tests |
| 2 | HITL Rate Limiter (Fix 6) | 5 files | Low — Python middleware |
| 3 | CCIN Verifier (Fix 2) | 5 files | Medium — New LLM call + schema change |
| 4 | Federated Pinning (Fix 3) | 6 files | Medium — Async broadcast + receipts |
| 5 | Chain-Anchored Sync (Fix 4) | 3 files | Low — Validation logic |
| 6 | Signed Sensors (Fix 5) | 3 files | Low — Fallback logic |

**Rationale for order**: Fix 1 closes the "God Key" vulnerability immediately. Fix 6 is quick and prevents DoS. Fix 2 addresses the fundamental Glass Box trust gap. Fixes 3-4 harden the mesh. Fix 5 is hardware-dependent and can be opt-in.

---

## Verification

### Fix 1 (Oracle Timelock)
- `forge test` — new tests: `test_proposeOracle_timelock`, `test_acceptOracle_before_timelock_reverts`, `test_acceptOracle_wrong_sender_reverts`, `test_proposeOracle_then_accept`
- Verify `setOracle()` is removed or deprecated

### Fix 2 (CCIN Verifier)
- Unit test: craft an `AgentAction` with contradictory rationale (e.g., action="mint 1M tokens", rationale="aligned with anti-extractive principles") → verify `violation_score > 25`
- Unit test: craft a legitimate action → verify `violation_score < 10`

### Fix 3 (Federated Pinning)
- Test: pin with `min_replicas=3`, mock only 2 peers responding → verify `InsufficientReplication` raised
- Test: pin with `min_replicas=3`, mock 3 peers → verify CID returned with `replica_count=3`

### Fix 4 (Chain-Anchored Sync)
- Test: attempt to sync a governance CID without `on_chain_anchor` → verify rejection
- Test: sync CID with valid anchor → verify acceptance

### Fix 5 (Signed Sensors)
- Test: mock unsigned psutil reading → verify max level capped at YELLOW
- Test: mock signed HAT reading → verify GREEN allowed

### Fix 6 (HITL Rate Limiter)
- Test: send 11 `/fiat/mint` requests in 1 hour → verify 11th returns HTTP 429
- Test: send 3 requests within 5-minute window → verify batched into single HITL

---

## FIX 7: Boundary Agent / Embassy Architecture (HIGH) — Gemini R3

### Problem

Gemini R3's "Heterogeneous Infrastructure Interoperability" review identified 5 cross-SDC failure modes at federation boundaries. When multiple Iskander instances (or non-Iskander cooperatives) interact, the current system trusts foreign data uncritically:

1. **Ethical Laundering** — Foreign SDCs with weaker Glass Box enforcement export activities that appear compliant but were never verified. `inbox_processor.py` accepts them because they arrive with a valid HTTP Signature, but signatures prove identity, not compliance.

2. **Semantic Incommensurability** — Foreign SDCs use different contribution stream names (e.g. `"produktiv"` vs `"livelihood"`), different scoring frameworks, different impact score scales. The IPD auditor receives `cooperation_score: 0.9` from a foreign node with no way to verify equivalent rigor.

3. **Governance Impedance Mismatch** — Foreign SDC using simple majority voting (not MACI ZK-SNARK) sends `iskander:HITLProposalVote`. Cross-coop governance proposals decided by the weaker system's guarantees negate Iskander's anti-bribery protections.

4. **Glass Box Breakage at Boundaries** — Foreign data entering via `post_inbox()` or `receive_from_peer()` bypasses Glass Box wrapping. The ingestion records *that something was received*, not *what the foreign agent did*.

5. **Causal Drift** — ActivityPub activities arrive out-of-order. A `Verdict` arrives before the `ArbitrationRequest` that created it. `InboxProcessor.process()` dispatches in arrival order with no causal dependency checking.

### Solution: Boundary Agent Module (`backend/boundary/`)

A dedicated boundary module acting as the single point of contact for all foreign SDC data. Every foreign activity or sync payload passes through 5 layers: trust quarantine, ontology translation, governance verification, causal ordering, and Glass Box wrapping.

**Design principle**: The boundary is a *membrane*, not a *wall*. It normalizes, annotates, and quarantines so internal components make informed decisions with accurate trust metadata.

**Files to create/modify**:

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/boundary/__init__.py` | CREATE | Package init, exports `BoundaryAgent`, `TrustQuarantine`, `OntologyTranslator`, `GovernanceVerifier`, `CausalBuffer` |
| 2 | `backend/boundary/boundary_agent.py` | CREATE | `BoundaryAgent` singleton — orchestrates all 5 layers. Wraps every foreign ingestion in `AgentAction` chain |
| 3 | `backend/boundary/trust_quarantine.py` | CREATE | `TrustQuarantine` — assigns `trust_penalty` to foreign identities, tracks behavior, manages trust escalation/demotion |
| 4 | `backend/boundary/ontology_translator.py` | CREATE | `OntologyTranslator` — maps foreign contribution streams, scoring frameworks to Iskander schemas. Unknown fields quarantined |
| 5 | `backend/boundary/governance_verifier.py` | CREATE | `GovernanceVerifier` — checks foreign SDC governance guarantees. Tags weak-governance proposals for HITL |
| 6 | `backend/boundary/causal_buffer.py` | CREATE | `CausalBuffer` — buffers out-of-order activities, resolves causal dependencies, releases in dependency-satisfied order |
| 7 | `backend/boundary/schemas.py` | CREATE | Pydantic schemas: `ForeignIdentityProfile`, `BoundaryVerdict`, `TranslationResult`, `GovernanceCapabilities` |
| 8 | `backend/routers/federation.py` | MODIFY | Route through `BoundaryAgent.ingest()` before `InboxProcessor.process()` |
| 9 | `backend/mesh/delta_sync.py` | MODIFY | `receive_from_peer()` calls `BoundaryAgent.ingest_sync()` before accepting CIDs |
| 10 | `backend/agents/library/ipd_auditor.py` | MODIFY | `compute_cooperation_signals()` discounts foreign scores by `(1 - trust_penalty)` |
| 11 | `backend/config.py` | MODIFY | Add boundary configuration settings |
| 12 | `backend/schemas/glass_box.py` | MODIFY | Add `boundary_provenance: dict | None` to `AgentAction` |
| 13 | `infra/init.sql` | MODIFY | Add `foreign_identity_trust`, `boundary_quarantine`, `ontology_mappings`, `causal_buffer` tables |

#### Layer 1: Trust Quarantine (`trust_quarantine.py`)

```python
@dataclass
class ForeignIdentityProfile:
    actor_iri: str
    first_seen: datetime
    interaction_count: int = 0
    cooperation_count: int = 0        # Activities that passed all checks
    quarantine_count: int = 0         # Activities that were quarantined
    trust_penalty: float = 0.3        # Initial penalty for unknown foreign nodes
    declared_capabilities: dict[str, Any] = field(default_factory=dict)

class TrustQuarantine:
    """Trust model:
      - New foreign identities start with trust_penalty = 0.3
      - Each successful interaction reduces penalty by boundary_trust_recovery_rate (0.02)
      - Each quarantined interaction increases penalty by boundary_trust_decay_rate (0.1)
      - Penalty clamped to [0.0, 1.0]; 1.0 = fully untrusted
      - Applied as discount: effective_score = raw_score * (1.0 - trust_penalty)
    Mirrors Fix 5's hardware trust_penalty pattern."""

    def apply_discount(self, raw_score: float, actor_iri: str) -> float:
        profile = self.get_or_create_profile(actor_iri)
        return raw_score * (1.0 - profile.trust_penalty)
```

#### Layer 2: Ontology Translation (`ontology_translator.py`)

```python
_STREAM_MAPPINGS = {
    "produktiv": "livelihood", "productivo": "livelihood", "productif": "livelihood",
    "fuersorge": "care", "cuidado": "care", "soin": "care",
    "gemeinwohl": "commons", "comunes": "commons", "communs": "commons",
}

_SCORE_FRAMEWORKS = {
    "iskander_v1": {"min": 0.0, "max": 1.0, "normalize": lambda x: x},
    "kleros_v1": {"min": 0, "max": 100, "normalize": lambda x: x / 100.0},
    "colony_v1": {"min": 0, "max": 10, "normalize": lambda x: x / 10.0},
    "unknown": {"min": None, "max": None, "normalize": None},  # → quarantine
}

class OntologyTranslator:
    """Unknown fields are QUARANTINED, never silently dropped.
    Quarantined fields stored in boundary_quarantine table for cooperative review."""
    def translate_activity(self, activity, actor_iri) -> TranslationResult: ...
```

#### Layer 3: Governance Verifier (`governance_verifier.py`)

```python
@dataclass
class GovernanceCapabilities:
    has_zk_voting: bool = False       # MACI ZK-SNARK or equivalent
    has_sbt_identity: bool = False    # Soulbound token identity
    has_glass_box: bool = False       # Mandatory rationale disclosure
    has_human_jury: bool = False      # Human jury for arbitration
    voting_mechanism: str = "unknown" # "zk_maci", "simple_majority", "quadratic"

class GovernanceVerifier:
    GOVERNANCE_SENSITIVE_TYPES = {
        "iskander:HITLProposalVote", "iskander:Verdict",
        "iskander:JuryNomination", "iskander:ArbitrationRequest",
    }
    # Verdict without human jury → REJECT
    # Vote without ZK voting → ACCEPT with HITL flag
    # Jury nomination without SBT identity → ACCEPT with HITL flag
```

#### Layer 4: Causal Buffer (`causal_buffer.py`)

```python
_CAUSAL_PREDECESSORS = {
    "iskander:Verdict": ["iskander:ArbitrationRequest"],
    "iskander:JuryNomination": ["iskander:ArbitrationRequest"],
    "iskander:AuditResponse": ["iskander:AuditRequest"],
    "iskander:AuditSummary": ["iskander:AuditRequest"],
}

class CausalBuffer:
    """Buffer out-of-order activities. Release when predecessor arrives.
    Safety valves: max_age (300s), max_size (1000), per-actor limit (50)."""
    def ingest(self, activity, local_handle) -> list[tuple[dict, str]]: ...
```

#### Layer 5: Boundary Agent Orchestrator (`boundary_agent.py`)

```python
class BoundaryAgent:
    """Single point of contact for all foreign SDC data.
    Orchestrates: Trust → Ontology → Governance → Causal → Glass Box."""

    async def ingest(self, activity, local_handle) -> list[BoundaryVerdict]: ...
    async def ingest_sync(self, peer_did, cids) -> tuple[list[str], list[str], list[AgentAction]]: ...
```

#### Integration Points

**`federation.py`** — After HTTP Signature verification, before InboxProcessor:
```python
verdicts = await BoundaryAgent.get_instance().ingest(body, local_handle=handle)
for verdict in verdicts:
    if verdict.proceed:
        action = await _inbox_processor.process(verdict.translated_activity, local_handle=handle)
```

**`delta_sync.py`** — Replace stub accept-all with boundary-gated acceptance:
```python
accepted, denied, boundary_actions = await BoundaryAgent.get_instance().ingest_sync(peer_did, cids)
```

**`ipd_auditor.py`** — Discount foreign cooperation scores:
```python
trust_penalty = boundary_metadata.get("trust_penalty", 0.0)
coop_ratio_global = coop_ratio_global * (1.0 - trust_penalty)
```

**Config additions** (`backend/config.py`):
```python
boundary_initial_trust_penalty: float = 0.3
boundary_trust_recovery_rate: float = 0.02
boundary_trust_decay_rate: float = 0.1
boundary_causal_buffer_max_age_seconds: int = 300
boundary_causal_buffer_max_size: int = 1000
boundary_require_governance_proof: bool = True
boundary_unknown_field_policy: str = "quarantine"  # "quarantine" | "drop" | "pass"
```

#### SQL Schema Additions (`infra/init.sql`)

```sql
CREATE TABLE IF NOT EXISTS foreign_identity_trust (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_iri TEXT NOT NULL UNIQUE,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_count INTEGER NOT NULL DEFAULT 0,
    cooperation_count INTEGER NOT NULL DEFAULT 0,
    quarantine_count INTEGER NOT NULL DEFAULT 0,
    trust_penalty NUMERIC(5,4) NOT NULL DEFAULT 0.3,
    declared_capabilities JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS boundary_quarantine (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_iri TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    quarantine_reason TEXT NOT NULL,
    quarantined_fields JSONB DEFAULT '{}',
    source_framework TEXT DEFAULT 'unknown',
    reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    resolution TEXT CHECK (resolution IN ('accepted','rejected','mapping_added',NULL)),
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ontology_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_framework TEXT NOT NULL,
    source_field TEXT NOT NULL,
    source_value TEXT NOT NULL,
    target_field TEXT NOT NULL,
    target_value TEXT NOT NULL,
    created_by TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (source_framework, source_field, source_value)
);

CREATE TABLE IF NOT EXISTS causal_buffer (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_type TEXT NOT NULL,
    actor_iri TEXT NOT NULL,
    causal_key TEXT NOT NULL,
    required_types TEXT[] NOT NULL,
    raw_activity JSONB NOT NULL,
    buffered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_at TIMESTAMPTZ,
    expired BOOLEAN NOT NULL DEFAULT FALSE
);
```

### AMENDMENT (Self-identified R3 second-order risks)

**Risk 1: Trust Penalty Gaming** — Attacker builds trust through benign Follow/Announce activities, then exploits reduced penalty for a single high-impact governance action.

**Fix**: Interaction-class weighting. Low-risk activities (Follow, Announce) earn only 25% trust recovery. Only governance-sensitive types that pass all checks earn full recovery.

```python
INTERACTION_RISK_WEIGHTS = {
    "Follow": 0.25, "Accept": 0.25, "Announce": 0.25, "Create": 0.5,
    "iskander:AuditRequest": 1.0, "iskander:Verdict": 1.0,
    "iskander:HITLProposalVote": 1.0,
}
```

**Risk 2: Ontology Typosquatting** — Foreign node sends `cooperatlon_score` (l not i). Field quarantined, but untranslated activity passes through with missing field → null defaults used instead of real scores.

**Fix**: Fuzzy field matching via `SequenceMatcher`. Fields within similarity > 0.85 of known fields flagged as `SUSPICIOUS_TYPO` and quarantined with explicit warning.

**Risk 3: Causal Buffer Exhaustion** — Thousands of `iskander:Verdict` activities referencing nonexistent `caseId` values fill buffer.

**Fix**: Per-actor buffer limit (50 slots). When exceeded, force-release oldest for that actor. Combined with existing max_age (300s) and max_size (1000) safety valves.

### Verification (Fix 7)

- Test: New foreign actor → verify `trust_penalty == 0.3`; 15 successful interactions → penalty decreases; 1 quarantine → penalty increases
- Test: Activity with `stream: "produktiv"` → translated to `livelihood`; unknown stream → quarantined
- Test: `iskander:Verdict` without `governanceProof.human_jury` → rejected
- Test: `iskander:HITLProposalVote` with `simple_majority` → accepted with `requires_hitl=True`
- Test: Send Verdict before ArbitrationRequest → Verdict buffered; ArbitrationRequest arrives → both released in order
- Test: Peer with `trust_penalty >= 0.8` → all DeltaSync CIDs denied
- Test: Foreign `cooperationScore: 0.9` from unknown framework → quarantined, not used raw

---

## Break-Glass Protocols (Gemini R2 Amendments)

Three cross-cutting emergency protocols added based on Gemini's second-order vulnerability analysis:

| Protocol | Trigger | Effect | Override Requirement |
|----------|---------|--------|---------------------|
| **Oracle Emergency Bypass** | Bank run, market crash, solvency crisis | `triggerEmergencyCircuitBreaker()` — bypasses 48h timelock, instantly trips circuit breaker | **Unanimous** multi-sig (all signers, not just threshold) |
| **HITL Crisis Mode** | `EmergencyVeto` filed OR `CircuitBreaker` active OR `RED` energy state | Rate limits expand 100x (10/hr → 1000/hr) | Automatic — triggered by on-chain/DB state |
| **Geo-Diversity Enforcement** | Every governance-critical pin operation | Replicas must span ≥2 regions OR ≥3 ISPs | Configurable via `mesh_min_distinct_regions` |

### Additional Second-Order Fixes

| Fix | Vulnerability | Amendment |
|-----|--------------|-----------|
| **CCIN Version Tracking** | Compliance drift — prompt updates silently change compliance definition | `ccin_verifier_version` stored in every `AgentAction` + `ccin_verification_log` |
| **Batched Anchoring** | Gas price censorship — poor nodes can't afford on-chain anchors | Merkle-Root-as-a-Service batches CIDs into single tx per 60s window |
| **Legacy Hardware Mode** | Hard brick of old Hearth PCBs on signature format change | 180-day grace period with degradation path (GREEN → YELLOW) |
| **Trust Penalty Gaming** (R3) | Attacker farms trust via benign Follow/Announce, exploits for governance attack | Interaction-class weighting: low-risk activities earn 25% trust recovery |
| **Ontology Typosquatting** (R3) | Near-miss field names bypass translation, cause null defaults | Fuzzy matching via `SequenceMatcher` flags similarity > 0.85 as `SUSPICIOUS_TYPO` |
| **Causal Buffer Exhaustion** (R3) | Phantom predecessor references fill buffer unbounded | Per-actor limit (50 slots) + force-release oldest on overflow |

---

## Updated Implementation Order

| Priority | Fix | Files Changed | Complexity | Round |
|----------|-----|---------------|------------|-------|
| 1 | Oracle Timelock + Emergency Bypass (Fix 1) | 7 Solidity files | Medium-High | R1+R2 |
| 2 | HITL Rate Limiter + Crisis Mode (Fix 6) | 7 Python files | Low-Medium | R1+R2 |
| 3 | CCIN Verifier + Version Tracking (Fix 2) | 7 Python files | Medium | R1+R2 |
| 4 | **Boundary Agent / Embassy (Fix 7)** | **13 Python/SQL files** | **Medium-High** | **R3** |
| 5 | Federated Pinning + Geo-Diversity (Fix 3) | 9 files | Medium-High | R1+R2 |
| 6 | Chain-Anchored Sync + Batch Anchoring (Fix 4) | 5 files | Medium | R1+R2 |
| 7 | Signed Sensors + Legacy Mode (Fix 5) | 4 Python files | Low | R1+R2 |

**Rationale for Fix 7 at position 4**: Must come after CCIN Verifier (Fix 3) because the Governance Verifier checks whether foreign nodes have Glass Box/CCIN capabilities. Must come before Federated Pinning (Fix 5) because trust quarantine should gate DeltaSync before replication enforcement is added.

**Total files**: ~52 across all 7 fixes

---

## Gemini R4 Review Questions

After implementing all 7 fixes, send these to Gemini for fourth-round review:

1. **Emergency Bypass**: "Can a compromised-but-unanimous multi-sig abuse `triggerEmergencyCircuitBreaker()` to permanently DoS the system by keeping the breaker tripped? Should there be a maximum duration before auto-reset?"
2. **Crisis Mode**: "If an attacker can trigger crisis mode (e.g., by filing a frivolous EmergencyVeto), they get 100x rate limit expansion. Is this an amplification vector? Should crisis mode require multi-sig confirmation?"
3. **CCIN Versioning**: "If a cooperative forks the CCIN principles (legitimate governance evolution), should the verifier support multiple active principle sets simultaneously?"
4. **Geo-Diversity**: "How do we handle a cooperative with only 3 nodes all in the same city? Should `mesh_require_geo_diversity` gracefully degrade to 'best effort' with a warning rather than blocking pins?"
5. **Batch Anchoring**: "If the batcher accumulates 1000 CIDs before flush, and the Merkle proof is on-chain, can any node verify inclusion of their specific CID without reconstructing the full tree? (Standard Merkle proof inclusion — confirm this is implemented)"
6. **Legacy Hardware**: "180-day grace period is generous. But what if a cooperative in the Global South can't afford new hardware? Should the grace period be extendable by cooperative vote?"
7. **Boundary Trust Gaming**: "The interaction-class weighting gives Follow/Announce only 25% trust recovery. But what about a Sybil-like attack where 100 different foreign actor IRIs all controlled by the same entity each send benign activities? Each builds independent trust profiles. Should we detect colocation patterns (same IP, same domain, same signing key) across foreign identities?"
8. **Ontology Translation Centralization**: "The `_STREAM_MAPPINGS` dict is hardcoded. If 50 SDCs each use unique stream names, the mapping table becomes a governance bottleneck. Should ontology mappings be proposable via MACI voting rather than steward-only approval?"
9. **Causal Buffer as Timing Oracle**: "An attacker who controls when ArbitrationRequests arrive can delay Verdict processing by withholding the predecessor. Is the 300s buffer timeout sufficient, or should there be an escalation path (e.g., after 60s without predecessor, alert the steward)?"

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
│  │  (Streamlit)  │──│  28 Routers  │──│  12 StateGraphs      │  │
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

### 3.8 Deploy.s.sol — Foundry Deployment Script

**Path**: `contracts/script/Deploy.s.sol`
**Deployment Order**:
1. CoopIdentity (with BrightID)
2. InternalPayroll
3. IskanderEscrow (address(0) ArbitrationRegistry, wired post-deploy)
4. ArbitrationRegistry
5. Cross-contract wiring (`setArbitrationRegistry`)
6. MACIVoting
7. StewardshipLedger
8. Write `script/deployment.json` artifact

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

### Registered Routers in `main.py` (28 total)

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

### Smart Contracts (8 files)
```
contracts/src/CoopIdentity.sol
contracts/src/IskanderEscrow.sol
contracts/src/ArbitrationRegistry.sol
contracts/src/InternalPayroll.sol
contracts/src/finance/CoopFiatToken.sol
contracts/src/governance/IStewardshipLedger.sol
contracts/src/governance/StewardshipLedger.sol
contracts/src/governance/MACIVoting.sol
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

### Backend — Agents (17 files)
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
backend/agents/core/prompt_stewardship_scorer.txt
backend/agents/core/prompt_fiat_gateway.txt
backend/agents/core/prompt_arbitrator.txt
backend/agents/core/prompt_steward.txt
backend/agents/core/prompt_secretary.txt
backend/agents/core/prompt_treasurer.txt
```

### Backend — Routers (22 files)
```
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
> Total: ~100 source files | 8 Solidity contracts | 12 LangGraph agents | 28 FastAPI routers | 30+ PostgreSQL tables
> Mission: "To build the Commons, we must first build the sovereign tool."
