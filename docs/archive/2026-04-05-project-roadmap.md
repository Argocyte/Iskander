# Iskander OS — Incremental Development Roadmap

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement any sprint. Each sprint has its own file map and TDD steps. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a working, hardened, self-hosting cooperative OS in sequential increments — each sprint producing independently testable, mergeable software.

**Architecture:** Phases 1–11 complete. Genesis boot sequence on `feature/genesis-boot-sequence`. Outstanding work: 7 security hardening fixes, then Phases 12–15 of the roadmap. New direction: Loomio (and a curated set of FOSS tools) replace ad-hoc HITL UI surfaces with purpose-built deliberation platforms.

**Tech Stack:** Python 3.12 · FastAPI · LangGraph · PostgreSQL + pgvector · Solidity 0.8.24 (Foundry) · Docker Compose · Loomio (Rails/Vue) · Matrix/Dendrite · IPFS · Gnosis Chain

---

## FOSS Platform Registry

These platforms integrate with Iskander at specific functional layers. Each is self-hostable (AGPL/GPL), has a documented REST API and/or webhook protocol, and has been verified against the cooperative's anti-extractive values.

| Platform | License | Role in Iskander | Integration Layer |
|---|---|---|---|
| **Loomio** | AGPL-3.0 | Primary HITL deliberation channel — threaded discussion + structured polls for every agent-triggered governance decision | `HITLRoutingManager` 3rd route → webhook resumes graph |
| **Decidim** | AGPL-3.0 | Large-scale participatory governance — annual budget cycles, member initiatives, multi-round assemblies | Future Phase 16 — ActivityPub bridge to Iskander governance router |
| **Polis** | AGPL-3.0 | Rapid consensus discovery — surfaces hidden agreement before formal Loomio votes; prevents wasted deliberation on non-controversial proposals | Future Phase 16 — pre-poll API call from governance router |
| **Matrix/Dendrite** | Apache 2.0 | Real-time encrypted member comms; agent bot commands (`!vote`, `!propose`); HITL fallback notification channel | Phase 14A — already planned |
| **Nextcloud** | AGPL-3.0 | Document collaboration, file storage for evidence packages, care-work photo uploads | Phase 13 App Store catalog |
| **Gitea** | MIT | Source code governance — Iskander's own codebase self-hosted; patch proposals as PRs | Phase 13 App Store catalog |
| **Plane** | AGPL-3.0 | Task tracking post-decision — converts Loomio outcomes to actionable work items | Phase 13 App Store catalog |
| **Penpot** | MPL-2.0 | Cooperative design tooling — governance document layout, member-facing reports | Phase 13 App Store catalog |

---

## Sprint 0 — Merge Genesis Branch

**Goal:** Close the genesis boot sequence feature branch cleanly before starting any new work.

**Branch:** `feature/genesis-boot-sequence` → `main`

### Tasks

- [ ] **0.1** Run full test suite on genesis branch
  ```bash
  cd src/IskanderOS && python -m pytest tests/test_genesis_boot.py tests/test_policy_engine.py -v
  ```
  Expected: all pass.

- [ ] **0.2** Run Foundry tests
  ```bash
  cd src/IskanderOS/contracts && forge test -vv
  ```
  Expected: all pass.

- [ ] **0.3** Create PR: `feature/genesis-boot-sequence` → `main`
  ```bash
  gh pr create --title "feat(genesis): complete one-way boot sequence" \
    --body "19-task genesis boot sequence: solo/coop modes, regulatory floor, HITL consent, Constitution.sol anchor."
  ```

- [ ] **0.4** Merge PR after review.

- [ ] **0.5** Update memory: mark genesis plan complete.
  ```bash
  # Update src/IskanderOS/docs/superpowers/plans/2026-03-17-genesis-boot-sequence.md
  # Add "## Status: COMPLETE — merged to main 2026-04-05" at top
  ```

---

## Sprint 1 — Critical Hardening

> **Spec:** `ISKANDER_HARDENING_PLAN.md` FIX 1 + FIX 2
> **Detailed plan:** Create `2026-04-05-hardening-sprint-1.md` before starting.

**Goal:** Fix the two CRITICAL vulnerabilities before any real member data touches the system.

**Branch:** `feature/hardening-critical`

### File Map

| # | File | Action | Responsibility |
|---|------|--------|----------------|
| 1 | `contracts/src/governance/StewardshipLedger.sol` | MODIFY | Oracle timelock, two-step rotation, emergency circuit breaker |
| 2 | `contracts/src/governance/IStewardshipLedger.sol` | MODIFY | New interface functions and events |
| 3 | `contracts/test/StewardshipLedger.t.sol` | MODIFY | Timelock tests, emergency breaker tests |
| 4 | `backend/agents/core/ica_verifier.py` | EXISTS | Verify present and wired up (was in hardening plan as CREATE) |
| 5 | `backend/schemas/glass_box.py` | MODIFY | Add `payload_hash: str`, `ica_verifier_version: str \| None` |
| 6 | `backend/agents/library/stewardship_scorer.py` | MODIFY | Call `verify_rationale()` after each AgentAction; halt on score > 25 |
| 7 | `backend/agents/library/fiat_gateway.py` | MODIFY | Same rationale verification pattern |
| 8 | `infra/init.sql` | MODIFY | Add `ica_verification_log` table with `verifier_version` column |
| 9 | `tests/test_hardening_critical.py` | CREATE | Python tests for rationale verification + hash binding |

### Chunk 1: Oracle Timelock (Solidity)

#### Task 1.1: Oracle Timelock

- [ ] **Step 1: Write failing Foundry test for timelock**
  ```solidity
  // contracts/test/StewardshipLedger.t.sol
  function test_proposeOracle_timelocks_rotation() public {
      address newOracle = makeAddr("newOracle");
      vm.prank(oracle);
      ledger.proposeOracle(newOracle);

      // Should revert before 48h
      vm.prank(newOracle);
      vm.expectRevert(abi.encodeWithSelector(TimelockActive.selector, block.timestamp + 48 hours));
      ledger.acceptOracle();
  }

  function test_acceptOracle_succeeds_after_timelock() public {
      address newOracle = makeAddr("newOracle");
      vm.prank(oracle);
      ledger.proposeOracle(newOracle);

      vm.warp(block.timestamp + 48 hours + 1);
      vm.prank(newOracle);
      ledger.acceptOracle();
      assertEq(ledger.oracle(), newOracle);
  }
  ```

- [ ] **Step 2: Run test to verify it fails**
  ```bash
  cd src/IskanderOS/contracts && forge test --match-test "test_proposeOracle" -v
  ```
  Expected: FAIL — `proposeOracle` function does not exist.

- [ ] **Step 3: Implement two-step oracle rotation in StewardshipLedger.sol**
  Add `pendingOracle`, `pendingOracleActivation`, `ORACLE_TIMELOCK`, `proposeOracle()`, `acceptOracle()` as specified in `ISKANDER_HARDENING_PLAN.md` FIX 1.

- [ ] **Step 4: Update IStewardshipLedger.sol** — add `proposeOracle`, `acceptOracle`, `OracleProposed`, `OracleAccepted`.

- [ ] **Step 5: Run tests to verify pass**
  ```bash
  forge test --match-test "test_proposeOracle\|test_acceptOracle" -v
  ```

- [ ] **Step 6: Write failing test for emergency circuit breaker**
  ```solidity
  function test_emergencyCircuitBreaker_trips_and_blocks() public {
      vm.prank(oracle);
      ledger.triggerEmergencyCircuitBreaker();
      // Delegation should now revert
      vm.expectRevert(CircuitBreakerActive.selector);
      ledger.delegateVote(member1, member2);
  }
  ```

- [ ] **Step 7: Run to verify fails** — `triggerEmergencyCircuitBreaker` not defined.

- [ ] **Step 8: Implement emergency circuit breaker** per `ISKANDER_HARDENING_PLAN.md` FIX 1 AMENDMENT.

- [ ] **Step 9: Run all StewardshipLedger tests**
  ```bash
  forge test --match-path "contracts/test/StewardshipLedger.t.sol" -v
  ```
  Expected: all pass.

- [ ] **Step 10: Commit**
  ```bash
  git add contracts/src/governance/StewardshipLedger.sol \
          contracts/src/governance/IStewardshipLedger.sol \
          contracts/test/StewardshipLedger.t.sol
  git commit -m "fix(contracts): add 48h oracle timelock + emergency circuit breaker"
  ```

### Chunk 2: Rationale Hash Binding (Python)

#### Task 1.2: Glass Box payload_hash

- [ ] **Step 1: Write failing test**
  ```python
  # tests/test_hardening_critical.py
  import hashlib, json
  from backend.schemas.glass_box import AgentAction, EthicalImpactLevel

  def test_agent_action_stores_payload_hash():
      payload = {"amount": 500, "currency": "GBP"}
      action = AgentAction(
          agent_id="treasurer",
          action="pay_invoice",
          rationale="Approved payment for office supplies",
          ethical_impact=EthicalImpactLevel.HIGH,
          payload=payload,
      )
      expected_hash = hashlib.sha256(
          json.dumps(payload, sort_keys=True).encode()
      ).hexdigest()
      assert action.payload_hash == expected_hash
  ```

- [ ] **Step 2: Run to verify fails**
  ```bash
  cd src/IskanderOS && python -m pytest tests/test_hardening_critical.py::test_agent_action_stores_payload_hash -v
  ```

- [ ] **Step 3: Add `payload_hash` to `AgentAction` in `backend/schemas/glass_box.py`**
  Add `payload_hash: str = ""` with a `@model_validator(mode="after")` that computes
  `sha256(json.dumps(self.payload, sort_keys=True).encode()).hexdigest()` when payload is set.

- [ ] **Step 4: Run to verify passes**

- [ ] **Step 5: Write failing test for ICA verification wiring**
  ```python
  from unittest.mock import AsyncMock, patch
  from backend.agents.core.ica_verifier import ICAVerdict, ICA_VERIFIER_VERSION

  async def test_stewardship_scorer_halts_on_high_violation_score():
      # Arrange: mock verify_rationale to return score=30
      mock_verdict = ICAVerdict(violation_score=30, flagged_principles=["P7"], explanation="test")
      with patch("backend.agents.library.stewardship_scorer.verify_rationale",
                 new=AsyncMock(return_value=mock_verdict)):
          from backend.agents.library.stewardship_scorer import quantify_care_work
          state = _make_test_state()
          result = await quantify_care_work(state)
          assert result.get("error") is not None
          assert "ICA violation" in result["error"]
  ```

- [ ] **Step 6: Run to verify fails**

- [ ] **Step 7: Wire `verify_rationale()` into `stewardship_scorer.py`** — after each `AgentAction` construction, call verifier; if `violation_score > 25`, set `state["error"]` and return early.

- [ ] **Step 8: Apply same pattern to `fiat_gateway.py`**

- [ ] **Step 9: Add `ica_verification_log` table to `infra/init.sql`**
  ```sql
  CREATE TABLE IF NOT EXISTS ica_verification_log (
      id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      agent_action_id   UUID REFERENCES agent_actions(id),
      violation_score   INTEGER NOT NULL,
      flagged_principles TEXT[],
      verifier_model    TEXT NOT NULL,
      verifier_version  TEXT NOT NULL,
      created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```

- [ ] **Step 10: Run all hardening tests**
  ```bash
  python -m pytest tests/test_hardening_critical.py -v
  ```

- [ ] **Step 11: Commit**
  ```bash
  git add backend/schemas/glass_box.py \
          backend/agents/core/ica_verifier.py \
          backend/agents/library/stewardship_scorer.py \
          backend/agents/library/fiat_gateway.py \
          infra/init.sql \
          tests/test_hardening_critical.py
  git commit -m "fix(security): bind AgentAction rationale to payload hash; wire ICA verifier into scorer + gateway"
  ```

- [ ] **Step 12: PR: `feature/hardening-critical` → `main`**

---

## Sprint 2 — Loomio HITL Integration

> **Detailed plan:** Create `2026-04-05-loomio-hitl.md` before starting (this chunk is the source of truth).

**Goal:** Members deliberate and vote on every agent-triggered governance decision inside a self-hosted Loomio instance. When a Loomio poll closes, a webhook resumes the suspended LangGraph agent.

**Branch:** `feature/loomio-hitl`

### Why Loomio

The current HITL fallback (local DB → Streamlit button) is bare-minimum. Loomio provides:
- **Threaded discussion** before the vote — members can ask clarifying questions
- **Multiple poll types** — consent proposal, ranked choice, score, STV
- **Audit trail** — every stance (vote + reasoning) permanently recorded in Loomio
- **Webhook push** — zero polling; Loomio calls Iskander when the poll closes
- **Email + mobile notifications** — members engage from any device, not just Streamlit

### HITL Routing Extension

```
route_hitl_proposal()
    ├── ActivityPub path (member runs personal node)     [existing]
    ├── Loomio path (member in coop Loomio group)        [NEW Sprint 2]
    └── Local DB path (fallback → Streamlit + Matrix)   [existing]
```

### Poll Type Mapping

| `HITLProposal.proposal_type` | Loomio `poll_type` | Rationale |
|---|---|---|
| `treasury_payment` | `proposal` (Agree/Abstain/Disagree) | Consent-based spending — any single block is significant |
| `member_admission` | `proposal` | Consent model for new members |
| `agent_deployment` | `proposal` | Container deploy is a side-effect requiring consent |
| `trust_slash` | `proposal` | High-stakes: consent required, cannot be casual |
| `arbitration_verdict` | `score` | Jury scores evidence quality; nuanced signal needed |
| `constitution_amendment` | `proposal` | Supermajority via closing threshold config |
| `app_catalog_update` | `poll` (multiple choice) | Members vote for preferred FOSS alternative |

### File Map

| # | File | Action | Responsibility |
|---|------|--------|----------------|
| 1 | `backend/integrations/__init__.py` | CREATE | Package init |
| 2 | `backend/integrations/loomio_client.py` | CREATE | Loomio REST API client — create group, create discussion, create poll, fetch outcome |
| 3 | `backend/integrations/loomio_poll_factory.py` | CREATE | Maps `HITLProposal` → Loomio poll config (type, closing_at, options, group_id) |
| 4 | `backend/routers/webhooks.py` | CREATE | `POST /hitl/webhooks/loomio` — validates signature, reads poll outcome, resumes graph |
| 5 | `backend/api/hitl_manager.py` | MODIFY | Add `_route_loomio()` method; extend routing logic |
| 6 | `backend/schemas/hitl.py` | MODIFY | Add `loomio_poll_id: str \| None` to `HITLNotification`; add `"loomio"` to route literal |
| 7 | `backend/config.py` | MODIFY | Add Loomio settings block |
| 8 | `infra/init.sql` | MODIFY | Add `loomio_poll_id TEXT` to `hitl_notifications` |
| 9 | `docker-compose.yml` | MODIFY | Add `loomio` service (postgres DB + Redis + app) |
| 10 | `tests/test_loomio_hitl.py` | CREATE | Unit + integration tests |

### Chunk 1: Loomio Client

#### Task 2.1: REST API Client

- [ ] **Step 1: Write failing test**
  ```python
  # tests/test_loomio_hitl.py
  import pytest
  from unittest.mock import AsyncMock, patch
  import httpx
  from backend.integrations.loomio_client import LoomioClient

  @pytest.fixture
  def client():
      return LoomioClient(base_url="http://loomio.test", api_key="test-key")

  async def test_create_discussion_returns_id(client):
      mock_response = {"discussion": {"id": 42, "key": "abc123"}}
      with patch.object(client._http, "post", new=AsyncMock(
          return_value=httpx.Response(200, json=mock_response)
      )):
          result = await client.create_discussion(
              group_id=1,
              title="Vote: Pay invoice #42",
              description="The treasurer agent has requested approval for a £500 payment.",
          )
          assert result["id"] == 42
          assert result["key"] == "abc123"

  async def test_create_poll_returns_id(client):
      mock_response = {"poll": {"id": 99, "key": "poll-xyz"}}
      with patch.object(client._http, "post", new=AsyncMock(
          return_value=httpx.Response(200, json=mock_response)
      )):
          result = await client.create_poll(
              discussion_id=42,
              poll_type="proposal",
              title="Approve £500 payment to Office Supplies Ltd?",
              closing_at="2026-04-08T18:00:00Z",
          )
          assert result["id"] == 99
  ```

- [ ] **Step 2: Run to verify fails** — `backend.integrations.loomio_client` does not exist.

- [ ] **Step 3: Create `backend/integrations/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/integrations/loomio_client.py`**
  ```python
  # backend/integrations/loomio_client.py
  """
  LoomioClient — thin async REST client for the Loomio v1 API.

  Docs: https://loomio.org/help/api (self-hosted instance endpoint)

  Authentication: API key passed as `Authorization: Bearer <key>` header.
  All methods return the parsed JSON payload dict or raise LoomioAPIError.
  """
  from __future__ import annotations
  import logging
  from typing import Any
  import httpx

  logger = logging.getLogger(__name__)

  class LoomioAPIError(Exception):
      def __init__(self, status: int, body: str) -> None:
          super().__init__(f"Loomio API {status}: {body}")
          self.status = status

  class LoomioClient:
      def __init__(self, base_url: str, api_key: str) -> None:
          self._base = base_url.rstrip("/")
          self._http = httpx.AsyncClient(
              headers={"Authorization": f"Bearer {api_key}",
                       "Content-Type": "application/json"},
              timeout=10.0,
          )

      async def create_discussion(
          self,
          group_id: int,
          title: str,
          description: str,
      ) -> dict[str, Any]:
          """Open a new Loomio thread for deliberation before the poll."""
          resp = await self._http.post(
              f"{self._base}/api/v1/discussions",
              json={"discussion": {
                  "group_id": group_id,
                  "title": title,
                  "description": description,
                  "private": True,
              }},
          )
          self._raise_for_status(resp)
          return resp.json()["discussion"]

      async def create_poll(
          self,
          discussion_id: int,
          poll_type: str,
          title: str,
          closing_at: str,
          details: str = "",
          options: list[str] | None = None,
      ) -> dict[str, Any]:
          """Create a poll attached to an existing discussion."""
          body: dict[str, Any] = {
              "poll": {
                  "discussion_id": discussion_id,
                  "poll_type": poll_type,
                  "title": title,
                  "details": details,
                  "closing_at": closing_at,
              }
          }
          if options:
              body["poll"]["poll_options_attributes"] = [
                  {"name": o} for o in options
              ]
          resp = await self._http.post(
              f"{self._base}/api/v1/polls", json=body
          )
          self._raise_for_status(resp)
          return resp.json()["poll"]

      async def get_poll_outcome(self, poll_key: str) -> dict[str, Any]:
          """Fetch a closed poll's outcome."""
          resp = await self._http.get(
              f"{self._base}/api/v1/polls/{poll_key}"
          )
          self._raise_for_status(resp)
          return resp.json()["poll"]

      def _raise_for_status(self, resp: httpx.Response) -> None:
          if resp.status_code >= 400:
              raise LoomioAPIError(resp.status_code, resp.text[:200])
  ```

- [ ] **Step 5: Run tests to verify pass**
  ```bash
  python -m pytest tests/test_loomio_hitl.py::test_create_discussion_returns_id \
                   tests/test_loomio_hitl.py::test_create_poll_returns_id -v
  ```

- [ ] **Step 6: Commit**
  ```bash
  git add backend/integrations/ tests/test_loomio_hitl.py
  git commit -m "feat(loomio): add LoomioClient with discussion + poll creation"
  ```

### Chunk 2: Poll Factory

#### Task 2.2: HITLProposal → Loomio Poll Config

- [ ] **Step 1: Write failing test**
  ```python
  from datetime import datetime, timezone, timedelta
  from backend.schemas.hitl import HITLProposal
  from backend.integrations.loomio_poll_factory import LooomioPollFactory

  def test_factory_maps_treasury_payment_to_consent_proposal():
      deadline = datetime.now(timezone.utc) + timedelta(days=3)
      proposal = HITLProposal(
          proposal_id="abc",
          proposal_type="treasury_payment",
          summary="Pay £500 to Office Supplies Ltd",
          agent_id="treasurer",
          voting_deadline=deadline,
          thread_id="thread-1",
          callback_inbox="http://localhost:8000/hitl/callback",
      )
      config = LooomioPollFactory.build(proposal)
      assert config["poll_type"] == "proposal"
      assert "£500" in config["title"]
      assert config["closing_at"] == deadline.isoformat()

  def test_factory_maps_arbitration_verdict_to_score_poll():
      proposal = HITLProposal(
          proposal_id="xyz",
          proposal_type="arbitration_verdict",
          summary="Score evidence in case #7",
          agent_id="arbitrator",
          thread_id="thread-2",
          callback_inbox="http://localhost:8000/hitl/callback",
      )
      config = LooomioPollFactory.build(proposal)
      assert config["poll_type"] == "score"
  ```

- [ ] **Step 2: Run to verify fails**

- [ ] **Step 3: Create `backend/integrations/loomio_poll_factory.py`**
  ```python
  # backend/integrations/loomio_poll_factory.py
  """Maps HITLProposal types to Loomio poll configurations."""
  from __future__ import annotations
  from datetime import datetime, timezone, timedelta
  from typing import Any
  from backend.schemas.hitl import HITLProposal

  _DEFAULT_WINDOW_DAYS = 3

  _POLL_TYPE_MAP: dict[str, str] = {
      "treasury_payment":      "proposal",
      "member_admission":      "proposal",
      "agent_deployment":      "proposal",
      "trust_slash":           "proposal",
      "constitution_amendment":"proposal",
      "arbitration_verdict":   "score",
      "app_catalog_update":    "poll",
  }

  class LooomioPollFactory:
      @staticmethod
      def build(proposal: HITLProposal) -> dict[str, Any]:
          poll_type = _POLL_TYPE_MAP.get(proposal.proposal_type, "proposal")
          deadline = proposal.voting_deadline or (
              datetime.now(timezone.utc) + timedelta(days=_DEFAULT_WINDOW_DAYS)
          )
          config: dict[str, Any] = {
              "poll_type": poll_type,
              "title": f"[{proposal.proposal_type.replace('_', ' ').title()}] {proposal.summary[:120]}",
              "details": (
                  f"{proposal.summary}\n\n"
                  f"_Agent: {proposal.agent_id} | Proposal ID: {proposal.proposal_id}_"
              ),
              "closing_at": deadline.isoformat(),
          }
          if poll_type == "poll":
              config["options"] = ["Approve", "Reject", "Defer"]
          return config
  ```

- [ ] **Step 4: Run to verify passes**

- [ ] **Step 5: Commit**
  ```bash
  git add backend/integrations/loomio_poll_factory.py tests/test_loomio_hitl.py
  git commit -m "feat(loomio): add poll factory mapping HITL proposal types to Loomio poll configs"
  ```

### Chunk 3: HITL Manager Route Extension

#### Task 2.3: `_route_loomio()` in HITLRoutingManager

- [ ] **Step 1: Write failing test**
  ```python
  async def test_hitl_manager_routes_to_loomio_when_configured(monkeypatch):
      from backend.api.hitl_manager import HITLRoutingManager
      HITLRoutingManager._instance = None
      manager = HITLRoutingManager.get_instance()

      mock_client = AsyncMock()
      mock_client.create_discussion.return_value = {"id": 1, "key": "disc-1"}
      mock_client.create_poll.return_value = {"id": 99, "key": "poll-99"}
      monkeypatch.setattr(manager, "_loomio", mock_client)
      monkeypatch.setattr(manager, "_loomio_group_id", 5)

      proposal = _make_test_proposal(proposal_type="treasury_payment")
      result = await manager.route_hitl_proposal("did:example:alice", proposal)

      assert result.route == "loomio"
      assert result.delivery_success is True
      mock_client.create_poll.assert_awaited_once()
  ```

- [ ] **Step 2: Run to verify fails**

- [ ] **Step 3: Modify `backend/api/hitl_manager.py`**
  - Import `LoomioClient`, `LooomioPollFactory`
  - Add `self._loomio: LoomioClient | None` and `self._loomio_group_id: int | None` to `__init__`
  - Add `_route_loomio()` method that: creates discussion → creates poll → stores `loomio_poll_id` in notification → returns `HITLRoutingResult(route="loomio", ...)`
  - Extend routing logic: check `self._loomio is not None` before ActivityPub check (Loomio is preferred over local DB but below personal nodes)

- [ ] **Step 4: Update `backend/schemas/hitl.py`** — add `loomio_poll_id: str | None = None` to `HITLNotification` and `"loomio"` to the `route` Literal.

- [ ] **Step 5: Add Loomio config to `backend/config.py`**
  ```python
  loomio_base_url: str = ""           # e.g. "http://loomio:3000"
  loomio_api_key: str = ""
  loomio_default_group_id: int = 0   # 0 = disabled
  loomio_webhook_secret: str = ""    # HMAC-SHA256 shared secret
  ```

- [ ] **Step 6: Run to verify passes**

- [ ] **Step 7: Commit**
  ```bash
  git add backend/api/hitl_manager.py backend/schemas/hitl.py backend/config.py
  git commit -m "feat(hitl): add Loomio as 3rd HITL routing path in HITLRoutingManager"
  ```

### Chunk 4: Webhook Handler

#### Task 2.4: Loomio → Iskander Webhook

- [ ] **Step 1: Write failing test**
  ```python
  import hmac, hashlib, json
  from fastapi.testclient import TestClient
  from backend.main import app

  def _sign(body: bytes, secret: str) -> str:
      return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

  def test_loomio_webhook_resumes_graph_on_poll_closed(monkeypatch):
      secret = "test-secret"
      monkeypatch.setenv("LOOMIO_WEBHOOK_SECRET", secret)

      payload = {
          "event": "poll_closed_by_user",
          "poll": {"key": "poll-99", "id": 99},
          "outcome": {"statement": "Approved by consensus"},
      }
      body = json.dumps(payload).encode()
      sig = _sign(body, secret)

      client = TestClient(app)
      resp = client.post(
          "/hitl/webhooks/loomio",
          content=body,
          headers={"X-Loomio-Signature": sig,
                   "Content-Type": "application/json"},
      )
      assert resp.status_code == 200
      assert resp.json()["status"] == "resumed"
  ```

- [ ] **Step 2: Run to verify fails** — route does not exist.

- [ ] **Step 3: Create `backend/routers/webhooks.py`**
  ```python
  # backend/routers/webhooks.py
  """
  Inbound webhook handlers for external FOSS platforms.
  Current: Loomio poll outcomes.
  Future: Decidim proposal outcomes, Polis consensus signals.

  Security: all webhooks validated via HMAC-SHA256 shared secret.
  """
  from __future__ import annotations
  import hashlib, hmac, logging
  from typing import Any
  import asyncpg
  from fastapi import APIRouter, HTTPException, Header, Request
  from backend.config import settings
  from backend.api.hitl_manager import HITLRoutingManager

  router = APIRouter(prefix="/hitl/webhooks", tags=["webhooks"])
  logger = logging.getLogger(__name__)

  def _verify_loomio_signature(body: bytes, signature: str) -> bool:
      expected = hmac.new(
          settings.loomio_webhook_secret.encode(), body, hashlib.sha256
      ).hexdigest()
      return hmac.compare_digest(expected, signature)

  @router.post("/loomio")
  async def loomio_webhook(
      request: Request,
      x_loomio_signature: str = Header(...),
  ) -> dict[str, Any]:
      body = await request.body()
      if not _verify_loomio_signature(body, x_loomio_signature):
          raise HTTPException(status_code=401, detail="Invalid signature")

      event = await request.json()
      event_type = event.get("event")

      if event_type not in ("poll_closed_by_user", "poll_expired", "outcome_created"):
          return {"status": "ignored", "event": event_type}

      poll_key = event.get("poll", {}).get("key")
      if not poll_key:
          raise HTTPException(status_code=400, detail="Missing poll.key")

      # Find the HITLNotification for this poll
      manager = HITLRoutingManager.get_instance()
      notification = manager.get_notification_by_loomio_poll(poll_key)
      if not notification:
          logger.warning("No HITL notification found for Loomio poll %s", poll_key)
          return {"status": "not_found"}

      # Extract approval from Loomio outcome
      # Loomio proposal polls: majority of non-abstain stances determines outcome
      outcome = event.get("outcome", {})
      approved = _parse_loomio_outcome(event.get("poll", {}), outcome)
      manager.mark_notification_responded(notification.proposal.proposal_id, approved)

      logger.info("Loomio poll %s closed: approved=%s", poll_key, approved)
      return {"status": "resumed", "proposal_id": notification.proposal.proposal_id}

  def _parse_loomio_outcome(poll: dict, outcome: dict) -> bool:
      """Consent model: approved unless a blocking objection exists."""
      # For 'proposal' type: check if any stance was 'disagree'
      # Loomio tallies are in poll["results"] as list of {id, name, score, voter_count}
      results = poll.get("results", [])
      disagree = next((r for r in results if r.get("id") == "disagree"), None)
      if disagree and disagree.get("voter_count", 0) > 0:
          return False
      return True
  ```

- [ ] **Step 4: Register router in `backend/main.py`**
  ```python
  from backend.routers.webhooks import router as webhooks_router
  app.include_router(webhooks_router)
  ```

- [ ] **Step 5: Run to verify passes**
  ```bash
  python -m pytest tests/test_loomio_hitl.py -v
  ```

- [ ] **Step 6: Commit**
  ```bash
  git add backend/routers/webhooks.py backend/main.py tests/test_loomio_hitl.py
  git commit -m "feat(webhooks): add Loomio poll-closed webhook handler with HMAC verification"
  ```

### Chunk 5: Docker Service

#### Task 2.5: Self-hosted Loomio in docker-compose.yml

> Only run this step once the API integration is tested. Loomio requires PostgreSQL + Redis.

- [ ] **Step 1: Add Loomio service to `docker-compose.yml`**
  ```yaml
  loomio:
    image: loomio/loomio:stable
    container_name: iskander_loomio
    restart: unless-stopped
    environment:
      DATABASE_URL: "postgresql://loomio:${LOOMIO_DB_PASSWORD:-loomio}@postgres/iskander_loomio"
      REDIS_URL: "redis://redis:6379/2"
      CANONICAL_HOST: "${LOOMIO_HOST:-loomio.iskander.local}"
      SECRET_KEY_BASE: "${LOOMIO_SECRET_KEY:-changeme}"
      SMTP_DOMAIN: "${SMTP_DOMAIN:-iskander.local}"
      FEATURES_WEBHOOKS: "true"
    depends_on:
      - postgres
      - redis
    ports:
      - "3000:3000"
    volumes:
      - loomio_uploads:/loomio/public/system
  ```

- [ ] **Step 2: Add `iskander_loomio` database to `infra/init.sql`**
  ```sql
  CREATE DATABASE iskander_loomio;
  CREATE USER loomio WITH PASSWORD 'loomio';
  GRANT ALL PRIVILEGES ON DATABASE iskander_loomio TO loomio;
  ```

- [ ] **Step 3: Add `loomio_uploads` to volumes block in docker-compose.yml**

- [ ] **Step 4: Smoke test — start and verify Loomio UI reachable**
  ```bash
  docker compose up loomio -d
  curl -f http://localhost:3000/api/v1/version
  ```

- [ ] **Step 5: Commit**
  ```bash
  git add docker-compose.yml infra/init.sql
  git commit -m "feat(infra): add self-hosted Loomio service to docker-compose"
  ```

- [ ] **Step 6: PR: `feature/loomio-hitl` → `main`**

---

## Sprint 3 — HIGH Hardening

> **Spec:** `ISKANDER_HARDENING_PLAN.md` FIX 3 + FIX 4
> **Detailed plan:** Create `2026-04-05-hardening-sprint-3.md` before starting.

**Goal:** Mesh data availability and sync split-brain protection before any real cooperative data is stored.

**Branch:** `feature/hardening-high`

### Summary

| Fix | Problem | Solution |
|---|---|---|
| FIX 3 | CIDs pinned to single in-memory node | Min replication count + geo-diverse peer selection + pin receipts |
| FIX 4 | DeltaSync has no conflict resolution | Blockchain as canonical sequencer + Merkle-root batched anchoring |

### File Map

| # | File | Action |
|---|------|--------|
| 1 | `backend/mesh/sovereign_storage.py` | MODIFY — `pin()` returns `(cid, replica_count)`, add `NodeMetadata`, `_select_diverse_peers()` |
| 2 | `backend/mesh/causal_event.py` | MODIFY — wait for `min_replicas` acks before CID is "committed" |
| 3 | `backend/mesh/delta_sync.py` | MODIFY — `PinReceipt` dataclass, `sync_to_peer()` returns signed receipt, `validate_chain_anchor()` |
| 4 | `backend/mesh/anchor_batcher.py` | EXISTS — verify and complete stub implementation |
| 5 | `backend/config.py` | MODIFY — mesh settings |
| 6 | `backend/schemas/mesh.py` | MODIFY — `PinReceiptResponse`, `replica_count` on `PinResponse` |
| 7 | `infra/init.sql` | MODIFY — `pin_receipts`, `node_metadata` tables |
| 8 | `tests/test_hardening_high.py` | CREATE |

> Detailed step-by-step: expand into `2026-04-05-hardening-sprint-3.md` following the same TDD format as Sprint 1.

---

## Sprint 4 — Democratic App Store (Phase 13)

> **Spec:** `docs/iskander_roadmap_v2.md` Phase 13
> **Detailed plan:** Create `2026-04-05-app-store.md` before starting.

**Goal:** Members request FOSS apps in natural language; the AI proposes from the curated catalog; a Loomio poll (Sprint 2) approves deployment; Docker provisions the container.

**Branch:** `feature/app-store`

### Key Integration: Loomio in the App Store

The Provisioner Agent's `human_vote_app` HITL breakpoint now uses Sprint 2's `HITLRoutingManager` — it creates a Loomio `poll` (multiple choice: which app to deploy?) or `proposal` (approve this specific image?). No new HITL plumbing needed.

### FOSS App Catalog (initial entries)

```yaml
# backend/appstore/catalog.yaml
apps:
  - name: Nextcloud
    image: nextcloud:28
    category: document_management
    description: "File sync, collaborative editing, calendar, contacts"
    port: 80
    resource_limits: {cpus: "2", memory: "2G"}

  - name: Gitea
    image: gitea/gitea:1.21
    category: code_governance
    description: "Cooperative source code hosting with PR-based patch governance"
    port: 3000
    resource_limits: {cpus: "1", memory: "512M"}

  - name: Loomio
    image: loomio/loomio:stable
    category: deliberation
    description: "Democratic decision-making platform (already provisioned in Sprint 2)"
    port: 3000
    note: "Deploy via Sprint 2 docker-compose block, not via App Store"

  - name: Penpot
    image: penpotapp/frontend:latest
    category: design
    description: "Open-source design and prototyping"
    port: 80
    resource_limits: {cpus: "2", memory: "1G"}

  - name: Plane
    image: makeplane/plane-frontend:latest
    category: project_management
    description: "AGPL project tracking — converts Loomio outcomes to tasks"
    port: 3000
    resource_limits: {cpus: "1", memory: "1G"}

  - name: Polis
    image: compdemocracy/polis:latest
    category: consensus_discovery
    description: "Rapid opinion clustering before formal Loomio votes"
    port: 5000
    resource_limits: {cpus: "1", memory: "1G"}
```

### File Map

| # | File | Action |
|---|------|--------|
| 1 | `backend/appstore/catalog.py` | EXISTS — extend to parse YAML, add `search_by_category()` |
| 2 | `backend/appstore/catalog.yaml` | CREATE — initial 6-app catalog above |
| 3 | `backend/appstore/docker_manager.py` | EXISTS — verify and complete stub |
| 4 | `backend/agents/library/provisioner.py` | EXISTS — verify all 7 LangGraph nodes wired |
| 5 | `backend/routers/appstore.py` | EXISTS — verify endpoints complete |
| 6 | `tests/test_app_store.py` | CREATE |

> Detailed step-by-step: expand into `2026-04-05-app-store.md`.

---

## Sprint 5 — ZK Democracy (Phase 12)

> **Spec:** `docs/iskander_roadmap_v2.md` Phase 12A + 12B
> **Detailed plan:** Create `2026-04-05-zk-democracy.md` before starting.

**Goal:** Secret ballots (MACI) for governance votes requiring voter privacy. ZK proof of care-work multiplier range without revealing the multiplier itself.

**Branch:** `feature/zk-democracy`

### Loomio + MACI Relationship

Loomio (Sprint 2) handles discussion and non-secret votes. MACI handles secret ballots where `secret_ballot=True`. The governance router chooses the path:
- `secret_ballot=False` → Loomio poll (transparent, with discussion)
- `secret_ballot=True` → MACI on-chain (ZK, private) — no Loomio involvement

### File Map (summary)

| # | File | Action |
|---|------|--------|
| 1 | `backend/zk/__init__.py` | CREATE |
| 2 | `backend/zk/maci_wrapper.py` | CREATE — Python wrapper around MACI CLI Node sidecar |
| 3 | `backend/zk/care_proof.py` | CREATE — care work multiplier ZK proof generation |
| 4 | `backend/routers/zk_voting.py` | CREATE — `/zk/polls/*` endpoints |
| 5 | `backend/schemas/zk.py` | CREATE — `MACIPollCreate`, `MACIVoteRequest`, `MACITallyResult` |
| 6 | `contracts/src/IskanderMACI.sol` | CREATE — thin MACI wrapper binding to CoopIdentity |
| 7 | `contracts/test/IskanderMACI.t.sol` | CREATE |
| 8 | `infra/maci-coordinator/` | CREATE — Node.js sidecar (Dockerfile + index.js) |
| 9 | `infra/zk-circuits/care_work_multiplier.circom` | CREATE |

> Detailed step-by-step: expand into `2026-04-05-zk-democracy.md`.

---

## Sprint 6 — Matrix & ActivityPub Federation (Phase 14)

> **Spec:** `docs/iskander_roadmap_v2.md` Phase 14A + 14B
> **Detailed plan:** Create `2026-04-05-federation.md` before starting.

**Goal:** Real-time encrypted comms via embedded Dendrite homeserver. Agents as Matrix bots. Full ActivityPub HTTP Signature implementation. Members approve HITL proposals from any Matrix client.

**Branch:** `feature/matrix-ap-federation`

### Loomio + Matrix Relationship

- Matrix: real-time, ephemeral chat → `!vote yes`, `!status`, quick queries
- Loomio: async, threaded deliberation → formal governance decisions
- ActivityPub: federated inter-coop messaging → proposals to sister coops

These are complementary layers, not competing. The HITL routing order becomes:
1. ActivityPub → member's personal Iskander node (highest sovereignty)
2. Loomio → deliberation + formal vote (default for coop members)
3. Matrix → real-time notification + quick response (parallel to Loomio)
4. Local DB → Streamlit fallback (last resort)

### File Map (summary)

| # | File | Action |
|---|------|--------|
| 1 | `backend/matrix/client.py` | EXISTS — verify and complete |
| 2 | `backend/matrix/appservice.py` | EXISTS — verify and complete |
| 3 | `backend/matrix/bridge.py` | EXISTS — verify and complete |
| 4 | `backend/federation/http_signatures.py` | EXISTS — verify RFC 9421 compliance |
| 5 | `backend/federation/inbox_processor.py` | EXISTS — verify custom Iskander types handled |
| 6 | `backend/federation/outbox_store.py` | EXISTS — verify persistence complete |
| 7 | `infra/dendrite/dendrite.yaml` | CREATE |
| 8 | `infra/dendrite/appservice-iskander.yaml` | CREATE |
| 9 | `tests/test_federation.py` | CREATE |

> Detailed step-by-step: expand into `2026-04-05-federation.md`.

---

## Sprint 7 — Inter-Coop Arbitration (Phase 15)

> **Spec:** `docs/iskander_roadmap_v2.md` Phase 15
> **Detailed plan:** Create `2026-04-05-arbitration.md` before starting.

**Goal:** Federated solidarity court — disputes between cooperatives resolved by a jury of peers from sister coops, with on-chain verdict recording and SBT reputation slashing.

**Branch:** `feature/arbitration`

### Loomio in the Arbitration Flow

The jury deliberation step (`human_jury_deliberation` HITL breakpoint) uses Loomio's `score` poll type — each juror scores evidence quality. The Arbitrator Agent aggregates scores and proposes a verdict. Final verdict confirmation uses a `proposal` poll requiring jury consent.

Matrix rooms (Sprint 6) provide real-time jury discussion; Loomio provides the formal verdict record.

### File Map (summary)

| # | File | Action |
|---|------|--------|
| 1 | `contracts/src/IskanderEscrow.sol` | CREATE |
| 2 | `contracts/src/ArbitrationRegistry.sol` | CREATE |
| 3 | `backend/agents/library/arbitrator.py` | EXISTS — verify and complete |
| 4 | `backend/routers/arbitration.py` | EXISTS — verify all endpoints complete |
| 5 | `backend/routers/escrow.py` | EXISTS — verify complete |
| 6 | `backend/federation/arbitration_protocol.py` | EXISTS — verify custom AP types complete |
| 7 | `tests/test_arbitration.py` | CREATE |

> Detailed step-by-step: expand into `2026-04-05-arbitration.md`.

---

## Sprint 8 — MEDIUM Hardening + Governance UX

> **Spec:** `ISKANDER_HARDENING_PLAN.md` FIX 5 + FIX 6 + FIX 7 (R3 Boundary Agent)
> **Detailed plan:** Create `2026-04-05-hardening-medium.md` before starting.

**Goal:** Signed hardware telemetry, HITL rate limiting, and federation boundary trust quarantine. Also: wire Polis for pre-vote consensus discovery.

**Branch:** `feature/hardening-medium`

### Polis Pre-Vote Integration

Before creating a Loomio proposal, the governance router optionally creates a Polis conversation to discover whether consensus already exists:

```
governance_router.create_proposal()
    → if polis_enabled: create_polis_conversation() → wait 24h
    → summarise Polis consensus for Loomio context (NEVER skip Loomio)
    → create_loomio_poll() [always — Polis informs, Loomio decides]
```

High Polis consensus speeds up Loomio deliberation but does not substitute
for formal member consent. Auto-approve bypasses democratic control (ICA P2)
and is explicitly prohibited. See issue #92.

### File Map (summary)

| # | File | Action |
|---|------|--------|
| 1 | `backend/energy/hearth_interface.py` | MODIFY — signed sensor, versioned formats |
| 2 | `backend/energy/resource_policy_engine.py` | MODIFY — cap unverified to YELLOW |
| 3 | `backend/api/hitl_rate_limiter.py` | EXISTS — verify and complete per FIX 6 |
| 4 | `backend/boundary/trust_quarantine.py` | EXISTS — verify R3 fix complete |
| 5 | `backend/boundary/ontology_translator.py` | EXISTS — verify complete |
| 6 | `backend/boundary/causal_buffer.py` | EXISTS — verify complete |
| 7 | `backend/integrations/polis_client.py` | CREATE — creates Polis conversations, fetches consensus score |
| 8 | `backend/routers/governance.py` | MODIFY — optional Polis pre-check before Loomio poll |
| 9 | `docker-compose.yml` | MODIFY — add Polis service |
| 10 | `tests/test_hardening_medium.py` | CREATE |

---

## Dependency Graph

```
Sprint 0 (Merge genesis)
    │
Sprint 1 (CRITICAL hardening) ──────────────────────┐
    │                                                 │
Sprint 2 (Loomio HITL) ──────────────────────────┐  │
    │                                              │  │
Sprint 3 (HIGH hardening)                         │  │
    │                                             ▼  ▼
Sprint 4 (App Store) ◄─── uses Sprint 2 Loomio + Sprint 1 security
    │
Sprint 5 (ZK Democracy) ◄─── parallel to Sprint 4
    │
Sprint 6 (Matrix + AP Federation) ◄─── extends Sprint 2 HITL routing
    │
Sprint 7 (Arbitration) ◄─── requires Sprint 6 Matrix + ActivityPub
    │
Sprint 8 (MEDIUM hardening + Polis)
```

Sprints 4 and 5 are **independent** and can be developed in parallel on separate worktrees.

---

## How to Use This Plan

1. **Per sprint:** create a dedicated worktree (`superpowers:using-git-worktrees`), then expand the sprint's file map into a detailed plan doc using `superpowers:writing-plans` before implementing.
2. **Per task:** follow TDD strictly — write failing test → run → implement → pass → commit.
3. **Per sprint completion:** run `superpowers:requesting-code-review` before merging.
4. **When stuck:** use `superpowers:systematic-debugging`.

The detailed plan docs (one per sprint) are the executable artifacts. This document is the navigation layer.
