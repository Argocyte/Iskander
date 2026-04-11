---
name: iskander-security-review
description: Iskander-specific security patterns to check during PR review of OpenClaw agents and decision-recorder service. Use alongside the standard code-review skill.
---

# Iskander Security Review Patterns

When reviewing PRs that touch `src/IskanderOS/openclaw/agents/` or `src/IskanderOS/services/decision-recorder/`, check these patterns in addition to the standard review.

---

## 1. `_ACTOR_TOOLS` / `_WRITE_TOOLS` Symmetry

**Location:** `src/IskanderOS/openclaw/agents/clerk/agent.py` and `steward/agent.py`

**Pattern:** Every tool that mutates cooperative data (in `_WRITE_TOOLS`) MUST also be in `_ACTOR_TOOLS` if it has an ownership parameter (`actor_user_id`, `updated_by`, `member_id`, `logged_by`).

`_ACTOR_TOOLS` is the trust boundary — it injects the server-authenticated `user_id` and causes the agent to send `X-Actor-User-Id` header. If a tool is in `_WRITE_TOOLS` but not `_ACTOR_TOOLS`, the ownership check on the server is always skipped (it's conditional on the header being present).

**Check:** For every tool name in `_WRITE_TOOLS`, verify it is also in `_ACTOR_TOOLS` if the tool has any user-identity parameter. If not, flag as HIGH severity.

**Canonical correct pattern** (from `dr_log_tension`):
```python
# In agent.py _ACTOR_TOOLS:
"dr_log_tension",

# In tools.py signature:
def dr_log_tension(*, actor_user_id: str, ...):
    with _http_client() as client:
        resp = client.post(url, json=payload,
                           headers={"X-Actor-User-Id": actor_user_id})
```

**Known violations introduced in PRs #101/#102 (not yet fixed as of 2026-04-11):**
- `dr_update_accountability` — missing from `_ACTOR_TOOLS`; `updated_by` is LLM-controlled
- `log_labour` — missing from `_ACTOR_TOOLS`; `member_id` is LLM-controlled

---

## 2. Token Comparison — `hmac.compare_digest`

**Location:** Any new service with Bearer token auth

**Pattern:** Internal service token comparisons MUST use `hmac.compare_digest`, not `==` or `!=`. Plain string comparison leaks timing information.

**Established pattern** (from `decision-recorder/main.py`):
```python
import hmac
if not hmac.compare_digest(auth[7:], INTERNAL_SERVICE_TOKEN):
    raise HTTPException(status_code=401)
```

**Known violation in PR #96 (not yet fixed as of 2026-04-11):**
- `steward-data/main.py` `_require_auth` uses `auth[len("Bearer "):] != _SERVICE_TOKEN`

---

## 3. Glass Box Prior-Round Enforcement

**Location:** `src/IskanderOS/openclaw/agents/clerk/agent.py` and `steward/agent.py`

**Pattern:** Write tools must not execute in the same round as `glass_box_log`. The `_glass_box_confirmed` flag tracks whether a prior-round log succeeded; it resets after each write.

**Check:** If adding a new write tool, verify:
- It appears in `_WRITE_TOOLS`
- The prior-round rejection message covers it
- Tests confirm the tool is blocked when `_glass_box_confirmed == False`

---

## 4. `list_tensions` / Filtering Logic

**Pattern:** The `logged_by` filter on `list_tensions` was deliberately removed in issue #64 as a security fix (enumeration vector). Any re-introduction of per-user filtering must be explicit and documented.

**Check:** If the PR touches `list_tensions` in `decision-recorder/main.py`, verify the docstring and code agree on whether filtering is applied.

---

## 5. PostgreSQL-only SQL in SQLite-tested services

**Pattern:** `steward-data` tests run on `sqlite:///:memory:`. Raw SQL using PostgreSQL-specific syntax (`INTERVAL '1 day'`, `TIMESTAMPTZ`, etc.) will fail silently (or return 500) in CI.

**Check:** Any raw SQL in `steward-data/main.py` that uses date arithmetic should use Python-computed cutoff dates passed as parameters rather than SQL `INTERVAL`.

---

## 6. DB Column Type: `Integer` vs `BigInteger` for PKs

**Pattern (established in PR #96):** Primary key columns use `Integer` (maps to SERIAL in Postgres, ROWID in SQLite — autoincrement works). Foreign key columns holding externally-generated IDs from Loomio/Mattermost use `BigInteger` (external IDs can exceed 32-bit). Do not use `BigInteger` for local autoincrement PKs.
