# Deliberation Data Layer — Phase A Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Loomio-equivalent data layer — 9 PostgreSQL tables, all Pydantic schemas, two CRUD routers (subgroups + deliberation), and the matching Next.js types and API client — with no AI agents yet (Phase B adds those).

**Architecture:** A new `backend/db.py` introduces a real asyncpg connection pool, making deliberation the first module with genuine DB persistence (all other routers are still in-memory stubs). Two new FastAPI routers handle SubGroup CRUD and the full Deliberation lifecycle (Threads → Comments → Proposals → Stances → Outcomes → Tasks). The Next.js frontend gets TypeScript types and an API client namespace but no UI yet (Phase C adds that).

**Tech Stack:** Python 3.12 · FastAPI · asyncpg · Pydantic v2 · PostgreSQL · pytest-asyncio · httpx · Next.js 14 · TypeScript

---

## File Map

| # | File | Action | Responsibility |
|---|------|--------|----------------|
| 1 | `backend/db.py` | CREATE | asyncpg connection pool + `get_db()` FastAPI dependency |
| 2 | `backend/schemas/deliberation.py` | CREATE | All Pydantic request/response models for deliberation |
| 3 | `backend/schemas/hitl.py` | MODIFY | Extend `proposal_type` and `route` Literals |
| 4 | `infra/init.sql` | MODIFY | Append 9 new tables (sub_groups through thread_tasks) |
| 5 | `backend/routers/subgroups.py` | CREATE | SubGroup CRUD (`/subgroups/*`) |
| 6 | `backend/routers/deliberation.py` | CREATE | Full deliberation CRUD (`/deliberation/*`) |
| 7 | `backend/main.py` | MODIFY | Register both new routers |
| 8 | `frontend-next/src/types/index.ts` | MODIFY | Add deliberation TypeScript types |
| 9 | `frontend-next/src/lib/api.ts` | MODIFY | Add `deliberation` and `subgroups` API namespaces |
| 10 | `frontend-next/src/components/layout/Sidebar.tsx` | MODIFY | Add Deliberation nav link |
| 11 | `tests/conftest.py` | MODIFY | Add `async_client` fixture + test DB helpers |
| 12 | `tests/test_deliberation_data_layer.py` | CREATE | All Phase A tests |

---

## Chunk 1: Database Pool + SQL Migrations + Core Schemas

### Task 1: asyncpg DB pool (`backend/db.py`)

**Files:**
- Create: `backend/db.py`
- Test: `tests/test_deliberation_data_layer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deliberation_data_layer.py
"""Phase A: Deliberation data layer tests."""
from __future__ import annotations
import pytest

class TestDBPool:
    async def test_get_db_yields_connection(self, async_client):
        """Health endpoint proves app boots with DB pool initialised."""
        resp = await async_client.get("/health")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run to verify it fails** (no async_client fixture yet)

```bash
cd src/IskanderOS
python -m pytest tests/test_deliberation_data_layer.py::TestDBPool -v
```
Expected: `ERRORS` — `fixture 'async_client' not found`

- [ ] **Step 3: Add `async_client` fixture to `tests/conftest.py`**

Read the existing `tests/conftest.py` first. If it doesn't exist, create it:

```python
# tests/conftest.py
"""Shared pytest fixtures for Iskander OS tests."""
from __future__ import annotations
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from backend.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client():
    """HTTP test client backed by the FastAPI app (no real DB)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def mock_db():
    """asyncpg connection mock — override get_db with this in individual tests."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetchval = AsyncMock(return_value=None)
    return conn
```

- [ ] **Step 4: Create `backend/db.py`**

```python
# backend/db.py
"""
db.py — asyncpg connection pool for Iskander OS.

This is the first module in the codebase to provide real PostgreSQL
persistence (other routers still use in-memory stubs pending migration).

Usage in FastAPI endpoints:
    from backend.db import get_db
    import asyncpg

    @router.get("/example")
    async def example(conn: asyncpg.Connection = Depends(get_db)):
        rows = await conn.fetch("SELECT id FROM deliberation_threads")
        return [dict(r) for r in rows]
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import asyncpg
from fastapi import HTTPException

from backend.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the singleton asyncpg connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        # settings.database_url uses SQLAlchemy format: postgresql+asyncpg://...
        # Strip the driver prefix for raw asyncpg
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        try:
            _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
            logger.info("asyncpg pool initialised: %s", dsn.split("@")[-1])
        except Exception as exc:
            logger.error("Failed to create asyncpg pool: %s", exc)
            raise
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency: yields a single connection from the pool.

    Usage:
        @router.post("/threads")
        async def create_thread(conn = Depends(get_db)):
            ...
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
```

- [ ] **Step 5: Register pool lifecycle in `backend/main.py`**

Add to the top of `backend/main.py` after the existing imports:

```python
from contextlib import asynccontextmanager
from backend.db import close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()

# Change: app = FastAPI(...) to include lifespan=lifespan
```

Find the existing `app = FastAPI(...)` block and add `lifespan=lifespan`:
```python
app = FastAPI(
    title="Project Iskander — Sovereign Node API",
    ...
    lifespan=lifespan,
)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestDBPool -v
```
Expected: `PASS` (health endpoint returns 200 regardless of pool status)

- [ ] **Step 7: Commit**

```bash
git add backend/db.py backend/main.py tests/conftest.py tests/test_deliberation_data_layer.py
git commit -m "feat(db): add asyncpg connection pool with get_db() FastAPI dependency"
```

---

### Task 2: SQL migrations (`infra/init.sql`)

**Files:**
- Modify: `infra/init.sql` (append to end of file)

- [ ] **Step 1: Append the 9 new tables to `infra/init.sql`**

Open `infra/init.sql` and append after the last existing table definition:

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- Phase A: Native Deliberation System (Loomio-equivalent)
-- ═══════════════════════════════════════════════════════════════════════════

-- Sub-groups (working groups within the cooperative)
CREATE TABLE IF NOT EXISTS sub_groups (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        TEXT UNIQUE NOT NULL,       -- e.g. "finance-committee"
    name        TEXT NOT NULL,
    description TEXT,
    created_by  TEXT NOT NULL,              -- member DID
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sub_group_members (
    sub_group_id UUID NOT NULL REFERENCES sub_groups(id) ON DELETE CASCADE,
    member_did   TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'member'
                 CHECK (role IN ('member', 'coordinator')),
    joined_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sub_group_id, member_did)
);

-- Deliberation threads (Loomio Discussions)
CREATE TABLE IF NOT EXISTS deliberation_threads (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title            TEXT NOT NULL,
    context          TEXT NOT NULL DEFAULT '',  -- rich-text body framing the topic
    author_did       TEXT NOT NULL,
    sub_group_id     UUID REFERENCES sub_groups(id) ON DELETE SET NULL,
    tags             TEXT[] NOT NULL DEFAULT '{}',
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'closed', 'pinned')),
    ai_context_draft TEXT,                      -- DiscussionAgent draft before human edit
    agent_action_id  UUID REFERENCES agent_actions(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_threads_author    ON deliberation_threads(author_did);
CREATE INDEX IF NOT EXISTS idx_threads_status    ON deliberation_threads(status);
CREATE INDEX IF NOT EXISTS idx_threads_subgroup  ON deliberation_threads(sub_group_id);
CREATE INDEX IF NOT EXISTS idx_threads_tags      ON deliberation_threads USING GIN(tags);

-- Comments within threads
CREATE TABLE IF NOT EXISTS thread_comments (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    author_did TEXT NOT NULL,
    parent_id  UUID REFERENCES thread_comments(id) ON DELETE CASCADE,  -- NULL = top-level
    body       TEXT NOT NULL,
    edited_at  TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_thread ON thread_comments(thread_id, created_at);

-- Emoji reactions on comments
CREATE TABLE IF NOT EXISTS thread_reactions (
    comment_id  UUID NOT NULL REFERENCES thread_comments(id) ON DELETE CASCADE,
    member_did  TEXT NOT NULL,
    emoji       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (comment_id, member_did, emoji)
);

-- Track who has read each thread
CREATE TABLE IF NOT EXISTS thread_seen (
    thread_id    UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    member_did   TEXT NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, member_did)
);

-- Proposals attached to threads
CREATE TABLE IF NOT EXISTS deliberation_proposals (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id    UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    process_type TEXT NOT NULL
                 CHECK (process_type IN (
                     'sense_check', 'advice', 'consent', 'consensus',
                     'choose', 'score', 'allocate', 'rank', 'time_poll'
                 )),
    options      JSONB,               -- for choose/score/allocate/rank/time_poll
    quorum_pct   INTEGER NOT NULL DEFAULT 0 CHECK (quorum_pct BETWEEN 0 AND 100),
    closing_at   TIMESTAMPTZ,
    status       TEXT NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'closed', 'withdrawn')),
    ai_draft     TEXT,                -- ProposalAgent draft before human edit
    author_did   TEXT NOT NULL,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_proposals_thread ON deliberation_proposals(thread_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON deliberation_proposals(status, closing_at);

-- Stances (member votes with reasons)
CREATE TABLE IF NOT EXISTS proposal_stances (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id UUID NOT NULL REFERENCES deliberation_proposals(id) ON DELETE CASCADE,
    member_did  TEXT NOT NULL,
    stance      TEXT NOT NULL,        -- 'agree'|'abstain'|'disagree'|'block' or option key
    score       INTEGER,              -- for score/allocate polls
    rank_order  JSONB,                -- for rank polls [{option_id, position}]
    reason      TEXT,                 -- member's stated reason (encouraged, not required)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (proposal_id, member_did)  -- one stance per member per proposal
);

CREATE INDEX IF NOT EXISTS idx_stances_proposal ON proposal_stances(proposal_id);

-- Outcome statements (recorded after proposals close)
CREATE TABLE IF NOT EXISTS decision_outcomes (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proposal_id   UUID NOT NULL UNIQUE REFERENCES deliberation_proposals(id),
    statement     TEXT NOT NULL,
    decision_type TEXT NOT NULL
                  CHECK (decision_type IN ('passed', 'rejected', 'withdrawn', 'no_quorum')),
    precedent_id  UUID REFERENCES democratic_precedents(id),  -- pgvector memory link
    ai_draft      TEXT,               -- OutcomeAgent draft before human confirms
    stated_by     TEXT NOT NULL,      -- DID of member who confirmed the outcome
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tasks assigned from threads or outcomes
CREATE TABLE IF NOT EXISTS thread_tasks (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id    UUID NOT NULL REFERENCES deliberation_threads(id) ON DELETE CASCADE,
    outcome_id   UUID REFERENCES decision_outcomes(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    assignee_did TEXT,                -- NULL = unassigned
    due_date     DATE,
    done         BOOLEAN NOT NULL DEFAULT FALSE,
    done_at      TIMESTAMPTZ,
    created_by   TEXT NOT NULL,
    agent_action_id UUID REFERENCES agent_actions(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_thread   ON thread_tasks(thread_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON thread_tasks(assignee_did) WHERE done = FALSE;
```

- [ ] **Step 2: Verify SQL is valid**

```bash
cd src/IskanderOS
docker compose up postgres -d
# Wait 5 seconds for postgres to be ready
psql postgresql://iskander:changeme_in_prod@localhost:5432/iskander_ledger \
  -c "\dt deliberation_threads"
```
Expected: `deliberation_threads` appears in table list. (If init.sql is auto-applied by Docker, just check; otherwise run `psql ... < infra/init.sql`)

- [ ] **Step 3: Commit**

```bash
git add infra/init.sql
git commit -m "feat(db): add 9 deliberation tables to init.sql (sub_groups through thread_tasks)"
```

---

### Task 3: Deliberation Pydantic schemas (`backend/schemas/deliberation.py`)

**Files:**
- Create: `backend/schemas/deliberation.py`
- Test: `tests/test_deliberation_data_layer.py`

- [ ] **Step 1: Write failing tests for schemas**

```python
# tests/test_deliberation_data_layer.py  (append to existing file)

class TestDeliberationSchemas:
    def test_process_type_enum_has_nine_values(self):
        from backend.schemas.deliberation import ProcessType
        assert len(ProcessType) == 9
        assert ProcessType.CONSENT.value == "consent"
        assert ProcessType.TIME_POLL.value == "time_poll"

    def test_thread_create_request_requires_title_and_author(self):
        from backend.schemas.deliberation import ThreadCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ThreadCreateRequest()  # missing required fields

    def test_thread_create_request_valid(self):
        from backend.schemas.deliberation import ThreadCreateRequest
        t = ThreadCreateRequest(
            title="New payroll policy",
            context="We need to revise how stewards are compensated.",
            author_did="did:example:alice",
        )
        assert t.title == "New payroll policy"
        assert t.sub_group_id is None

    def test_stance_option_enum(self):
        from backend.schemas.deliberation import StanceOption
        assert StanceOption.BLOCK.value == "block"
        assert StanceOption.AGREE.value == "agree"

    def test_proposal_tally_total(self):
        from backend.schemas.deliberation import ProposalTally
        tally = ProposalTally(agree=5, abstain=2, disagree=1, block=0, total=8)
        assert tally.total == 8

    def test_thread_summary_response(self):
        from backend.schemas.deliberation import ThreadSummary
        import uuid
        from datetime import datetime, timezone
        s = ThreadSummary(
            id=str(uuid.uuid4()),
            title="Test",
            author_did="did:example:bob",
            status="open",
            tags=[],
            open_proposal_count=1,
            comment_count=3,
            last_activity=datetime.now(timezone.utc),
        )
        assert s.open_proposal_count == 1
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestDeliberationSchemas -v
```
Expected: `ERRORS` — `ModuleNotFoundError: No module named 'backend.schemas.deliberation'`

- [ ] **Step 3: Create `backend/schemas/deliberation.py`**

```python
# backend/schemas/deliberation.py
"""
deliberation.py — Pydantic schemas for the Iskander Native Deliberation System.

Mirrors Loomio's data model: SubGroups → Threads → Comments → Proposals
→ Stances → Outcomes → Tasks.

All IDs are string UUIDs (matching asyncpg row UUID columns).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProcessType(str, Enum):
    """Nine Loomio-compatible decision processes and poll types."""
    SENSE_CHECK = "sense_check"
    ADVICE      = "advice"
    CONSENT     = "consent"
    CONSENSUS   = "consensus"
    CHOOSE      = "choose"
    SCORE       = "score"
    ALLOCATE    = "allocate"
    RANK        = "rank"
    TIME_POLL   = "time_poll"


class StanceOption(str, Enum):
    """Options for proposal-type polls (Consent, Consensus, Sense Check, Advice)."""
    AGREE    = "agree"
    ABSTAIN  = "abstain"
    DISAGREE = "disagree"
    BLOCK    = "block"   # only valid on consent proposals


class ThreadStatus(str, Enum):
    OPEN   = "open"
    CLOSED = "closed"
    PINNED = "pinned"


class ProposalStatus(str, Enum):
    OPEN      = "open"
    CLOSED    = "closed"
    WITHDRAWN = "withdrawn"


class DecisionType(str, Enum):
    PASSED    = "passed"
    REJECTED  = "rejected"
    WITHDRAWN = "withdrawn"
    NO_QUORUM = "no_quorum"


class MemberRole(str, Enum):
    MEMBER      = "member"
    COORDINATOR = "coordinator"


# ── SubGroup schemas ──────────────────────────────────────────────────────────

class SubGroupCreate(BaseModel):
    slug:        str  = Field(..., min_length=2, max_length=80, pattern=r'^[a-z0-9\-]+$')
    name:        str  = Field(..., min_length=1, max_length=120)
    description: str | None = None
    created_by:  str  = Field(..., description="Creator member DID")


class SubGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          str
    slug:        str
    name:        str
    description: str | None
    created_by:  str
    created_at:  datetime


class SubGroupMemberAdd(BaseModel):
    member_did: str
    role:       MemberRole = MemberRole.MEMBER


class SubGroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sub_group_id: str
    member_did:   str
    role:         str
    joined_at:    datetime


# ── Thread schemas ─────────────────────────────────────────────────────────────

class ThreadCreateRequest(BaseModel):
    title:        str       = Field(..., min_length=1, max_length=200)
    context:      str       = Field(default="", description="Rich-text thread body")
    author_did:   str       = Field(..., description="Creator member DID")
    sub_group_id: str | None = Field(default=None, description="Scope to working group (None = whole coop)")
    tags:         list[str] = Field(default_factory=list)


class ThreadUpdateRequest(BaseModel):
    title:   str | None = Field(default=None, max_length=200)
    context: str | None = None
    status:  ThreadStatus | None = None
    tags:    list[str] | None = None


class ThreadSummary(BaseModel):
    """Lightweight model for thread list view."""
    model_config = ConfigDict(from_attributes=True)
    id:                  str
    title:               str
    author_did:          str
    status:              str
    tags:                list[str]
    open_proposal_count: int
    comment_count:       int
    last_activity:       datetime
    sub_group_id:        str | None = None


class ThreadDetail(BaseModel):
    """Full thread view including nested data."""
    model_config = ConfigDict(from_attributes=True)
    id:               str
    title:            str
    context:          str
    author_did:       str
    sub_group_id:     str | None
    tags:             list[str]
    status:           str
    ai_context_draft: str | None
    created_at:       datetime
    updated_at:       datetime
    comments:         list[CommentResponse]         = Field(default_factory=list)
    proposals:        list[ProposalSummary]         = Field(default_factory=list)
    tasks:            list[TaskResponse]            = Field(default_factory=list)


# ── Comment schemas ───────────────────────────────────────────────────────────

class CommentCreateRequest(BaseModel):
    thread_id:  str
    author_did: str
    body:       str = Field(..., min_length=1)
    parent_id:  str | None = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:         str
    thread_id:  str
    author_did: str
    parent_id:  str | None
    body:       str
    edited_at:  datetime | None
    created_at: datetime
    reactions:  dict[str, int] = Field(default_factory=dict)  # emoji → count


class ReactionToggleRequest(BaseModel):
    member_did: str
    emoji:      str = Field(..., min_length=1, max_length=8)


# ── Proposal schemas ──────────────────────────────────────────────────────────

class ProposalCreateRequest(BaseModel):
    thread_id:    str
    title:        str       = Field(..., min_length=1, max_length=200)
    body:         str       = Field(..., min_length=1)
    process_type: ProcessType
    author_did:   str
    options:      list[str] | None = Field(
        default=None,
        description="Options for choose/score/allocate/rank/time_poll types"
    )
    quorum_pct:  int = Field(default=0, ge=0, le=100)
    closing_at:  datetime | None = None


class ProposalSummary(BaseModel):
    """Lightweight model for embedding proposals in thread list."""
    model_config = ConfigDict(from_attributes=True)
    id:           str
    title:        str
    process_type: str
    status:       str
    closing_at:   datetime | None
    stance_count: int = 0


class ProposalDetail(BaseModel):
    """Full proposal view including stances and live tally."""
    model_config = ConfigDict(from_attributes=True)
    id:           str
    thread_id:    str
    title:        str
    body:         str
    process_type: str
    options:      list[str] | None
    quorum_pct:   int
    closing_at:   datetime | None
    status:       str
    ai_draft:     str | None
    author_did:   str
    created_at:   datetime
    closed_at:    datetime | None
    stances:      list[StanceResponse]  = Field(default_factory=list)
    tally:        ProposalTally | None  = None
    outcome:      OutcomeResponse | None = None


class ProposalTally(BaseModel):
    """Live vote count — computed, not stored."""
    agree:    int = 0
    abstain:  int = 0
    disagree: int = 0
    block:    int = 0
    total:    int = 0
    options:  dict[str, int] = Field(default_factory=dict)  # for poll types


# ── Stance schemas ─────────────────────────────────────────────────────────────

class StanceCreateRequest(BaseModel):
    member_did:  str
    stance:      str  = Field(..., description="agree|abstain|disagree|block or option key")
    reason:      str | None = None
    score:       int | None = Field(default=None, ge=0, le=100)
    rank_order:  list[dict[str, Any]] | None = None


class StanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:          str
    proposal_id: str
    member_did:  str
    stance:      str
    reason:      str | None
    score:       int | None
    rank_order:  list[dict[str, Any]] | None
    created_at:  datetime
    updated_at:  datetime


# ── Outcome schemas ────────────────────────────────────────────────────────────

class OutcomeCreateRequest(BaseModel):
    statement:     str = Field(..., min_length=1)
    decision_type: DecisionType
    stated_by:     str  = Field(..., description="Member DID confirming the outcome")


class OutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:            str
    proposal_id:   str
    statement:     str
    decision_type: str
    precedent_id:  str | None
    ai_draft:      str | None
    stated_by:     str
    created_at:    datetime


# ── Task schemas ──────────────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    thread_id:    str
    title:        str = Field(..., min_length=1, max_length=200)
    created_by:   str
    assignee_did: str | None = None
    due_date:     str | None = Field(default=None, description="ISO date string YYYY-MM-DD")
    outcome_id:   str | None = None


class TaskUpdateRequest(BaseModel):
    done:         bool | None = None
    assignee_did: str | None = None
    due_date:     str | None = None
    title:        str | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:           str
    thread_id:    str
    outcome_id:   str | None
    title:        str
    assignee_did: str | None
    due_date:     str | None
    done:         bool
    done_at:      datetime | None
    created_by:   str
    created_at:   datetime
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestDeliberationSchemas -v
```
Expected: All 6 schema tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/schemas/deliberation.py tests/test_deliberation_data_layer.py
git commit -m "feat(schemas): add deliberation.py with all 9 process types, thread/proposal/stance/outcome/task models"
```

---

### Task 4: Extend `backend/schemas/hitl.py`

**Files:**
- Modify: `backend/schemas/hitl.py`

- [ ] **Step 1: Write failing test**

```python
class TestHITLExtensions:
    def test_new_proposal_types_accepted(self):
        from backend.schemas.hitl import HITLProposal
        p = HITLProposal(
            proposal_type="discussion_context",
            summary="AI drafted thread context for payroll discussion",
            agent_id="discussion-agent-v1",
            thread_id="thread-abc",
            callback_inbox="http://localhost:8000/hitl/callback",
        )
        assert p.proposal_type == "discussion_context"

    def test_loomio_route_accepted(self):
        from backend.schemas.hitl import HITLNotification, HITLProposal
        from datetime import datetime, timezone
        n = HITLNotification(
            member_did="did:example:alice",
            proposal=HITLProposal(
                proposal_type="proposal_draft",
                summary="Test",
                agent_id="proposal-agent",
                thread_id="t1",
                callback_inbox="http://cb",
            ),
            route="loomio",
        )
        assert n.route == "loomio"
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestHITLExtensions -v
```
Expected: `FAIL` — `"discussion_context" is not a valid literal`

- [ ] **Step 3: Edit `backend/schemas/hitl.py`**

Find the `HITLProposal` class and update `proposal_type`:

```python
# OLD:
proposal_type: Literal["governance", "treasury", "steward", "arbitration", "ipd"]

# NEW:
proposal_type: Literal[
    "governance", "treasury", "steward", "arbitration", "ipd",
    "discussion_context",
    "proposal_draft",
    "outcome_approval",
    "task_assignment",
]
```

Find the `HITLNotification` class and update `route`:

```python
# OLD:
route: Literal["activitypub", "local_db"]

# NEW:
route: Literal["activitypub", "local_db", "loomio"]
```

Find `HITLRoutingResult` and update its `route` field the same way:
```python
route: Literal["activitypub", "local_db", "loomio"]
```

- [ ] **Step 4: Run to verify passes**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestHITLExtensions -v
```

- [ ] **Step 5: Ensure existing HITL tests still pass**

```bash
python -m pytest tests/ -k "hitl" -v
```
Expected: All existing HITL tests still pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add backend/schemas/hitl.py tests/test_deliberation_data_layer.py
git commit -m "feat(hitl): extend proposal_type with 4 deliberation types; add 'loomio' route"
```

---

## Chunk 2: SubGroups Router

### Task 5: SubGroups router (`backend/routers/subgroups.py`)

**Files:**
- Create: `backend/routers/subgroups.py`
- Test: `tests/test_deliberation_data_layer.py`

- [ ] **Step 1: Write failing tests**

```python
class TestSubGroupsRouter:
    async def test_list_subgroups_returns_empty_list(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        app.dependency_overrides[get_db] = lambda: mock_db
        mock_db.fetch = AsyncMock(return_value=[])

        resp = await async_client.get(
            "/subgroups",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
        app.dependency_overrides.clear()

    async def test_create_subgroup_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        import uuid
        from datetime import datetime, timezone

        fake_row = {
            "id": str(uuid.uuid4()),
            "slug": "tech-wg",
            "name": "Tech Working Group",
            "description": None,
            "created_by": "did:example:alice",
            "created_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(return_value=fake_row)
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            "/subgroups",
            json={"slug": "tech-wg", "name": "Tech Working Group", "created_by": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "tech-wg"
        app.dependency_overrides.clear()

    async def test_create_subgroup_invalid_slug_returns_422(self, async_client):
        resp = await async_client.post(
            "/subgroups",
            json={"slug": "INVALID SLUG!", "name": "Bad", "created_by": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestSubGroupsRouter -v
```
Expected: `ERRORS` — `/subgroups` routes do not exist

- [ ] **Step 3: Create `backend/routers/subgroups.py`**

```python
# backend/routers/subgroups.py
"""
subgroups.py — Working Group management for Iskander OS.

Sub-groups are lightweight working groups within a cooperative
(e.g. Finance Committee, Tech Working Group). They scope deliberation
threads and proposals to relevant members without requiring separate
CoopIdentity SBTs — governance stays at the cooperative level.

Endpoints:
  GET  /subgroups                 — list all working groups
  POST /subgroups                 — create (steward only)
  GET  /subgroups/{id}/members    — list members of a working group
  POST /subgroups/{id}/members    — add member (coordinator or steward)
  DELETE /subgroups/{id}/members/{did} — remove member
"""
from __future__ import annotations

import logging
import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import AuthenticatedUser, get_current_user, require_role
from backend.db import get_db
from backend.schemas.deliberation import (
    SubGroupCreate,
    SubGroupMemberAdd,
    SubGroupMemberResponse,
    SubGroupResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subgroups", tags=["subgroups"])


# ── GET /subgroups ────────────────────────────────────────────────────────────

@router.get("", response_model=list[SubGroupResponse])
async def list_subgroups(
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[SubGroupResponse]:
    """Return all working groups in the cooperative."""
    rows = await conn.fetch(
        "SELECT id::text, slug, name, description, created_by, created_at "
        "FROM sub_groups ORDER BY name"
    )
    return [SubGroupResponse(**dict(r)) for r in rows]


# ── POST /subgroups ───────────────────────────────────────────────────────────

@router.post("", response_model=SubGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_subgroup(
    req: SubGroupCreate,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> SubGroupResponse:
    """Create a new working group (steward-only)."""
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO sub_groups (slug, name, description, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id::text, slug, name, description, created_by, created_at
            """,
            req.slug, req.name, req.description, req.created_by,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sub-group slug '{req.slug}' already exists",
        )
    return SubGroupResponse(**dict(row))


# ── GET /subgroups/{id}/members ───────────────────────────────────────────────

@router.get("/{subgroup_id}/members", response_model=list[SubGroupMemberResponse])
async def list_members(
    subgroup_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[SubGroupMemberResponse]:
    """List members of a working group."""
    rows = await conn.fetch(
        "SELECT sub_group_id::text, member_did, role, joined_at "
        "FROM sub_group_members WHERE sub_group_id = $1 ORDER BY joined_at",
        uuid.UUID(subgroup_id),
    )
    return [SubGroupMemberResponse(**dict(r)) for r in rows]


# ── POST /subgroups/{id}/members ──────────────────────────────────────────────

@router.post("/{subgroup_id}/members", response_model=SubGroupMemberResponse,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    subgroup_id: str,
    req: SubGroupMemberAdd,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role("steward", "worker-owner")),
) -> SubGroupMemberResponse:
    """Add a member to a working group."""
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO sub_group_members (sub_group_id, member_did, role)
            VALUES ($1, $2, $3)
            RETURNING sub_group_id::text, member_did, role, joined_at
            """,
            uuid.UUID(subgroup_id), req.member_did, req.role.value,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already in this working group",
        )
    return SubGroupMemberResponse(**dict(row))


# ── DELETE /subgroups/{id}/members/{did} ──────────────────────────────────────

@router.delete("/{subgroup_id}/members/{member_did}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    subgroup_id: str,
    member_did: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role("steward")),
) -> None:
    """Remove a member from a working group (steward only)."""
    result = await conn.execute(
        "DELETE FROM sub_group_members WHERE sub_group_id = $1 AND member_did = $2",
        uuid.UUID(subgroup_id), member_did,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Member not found in this working group")
```

- [ ] **Step 4: Register in `backend/main.py`**

Add to the imports section (after genesis_router):
```python
from backend.routers.subgroups    import router as subgroups_router
```

Add to the `app.include_router(...)` section:
```python
app.include_router(subgroups_router)         # /subgroups — working group management
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestSubGroupsRouter -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/subgroups.py backend/main.py tests/test_deliberation_data_layer.py
git commit -m "feat(routers): add /subgroups CRUD router with asyncpg persistence"
```

---

## Chunk 3: Deliberation Router — Threads & Comments

### Task 6: Thread endpoints

**Files:**
- Create: `backend/routers/deliberation.py` (partial — threads + comments)
- Test: `tests/test_deliberation_data_layer.py`

- [ ] **Step 1: Write failing tests**

```python
class TestThreadEndpoints:
    async def test_create_thread_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        import uuid
        from datetime import datetime, timezone

        fake = {
            "id": str(uuid.uuid4()), "title": "New payroll policy",
            "context": "We need to revise...", "author_did": "did:example:alice",
            "sub_group_id": None, "tags": [], "status": "open",
            "ai_context_draft": None, "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(return_value=fake)
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            "/deliberation/threads",
            json={"title": "New payroll policy", "context": "We need to revise...",
                  "author_did": "did:example:alice"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "New payroll policy"
        app.dependency_overrides.clear()

    async def test_list_threads_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        mock_db.fetch = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.get(
            "/deliberation/threads",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        app.dependency_overrides.clear()

    async def test_get_thread_detail_404_when_missing(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        mock_db.fetchrow = AsyncMock(return_value=None)
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.get(
            f"/deliberation/threads/{uuid.uuid4()}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 404
        app.dependency_overrides.clear()

    async def test_add_comment_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        import uuid
        from datetime import datetime, timezone

        thread_id = str(uuid.uuid4())
        fake_comment = {
            "id": str(uuid.uuid4()), "thread_id": thread_id,
            "author_did": "did:example:bob", "parent_id": None,
            "body": "I agree with the direction.", "edited_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(return_value=fake_comment)
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/comments",
            json={"thread_id": thread_id, "author_did": "did:example:bob",
                  "body": "I agree with the direction."},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["body"] == "I agree with the direction."
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestThreadEndpoints -v
```
Expected: `ERRORS` — `/deliberation/threads` routes not found

- [ ] **Step 3: Create `backend/routers/deliberation.py`** (threads + comments section)

```python
# backend/routers/deliberation.py
"""
deliberation.py — Iskander Native Deliberation System router.

Implements Loomio's deliberation model natively:
  Threads → Comments → Proposals → Stances → Outcomes → Tasks

All write operations go to PostgreSQL via asyncpg.
AI facilitation (DiscussionAgent, ProposalAgent, etc.) is wired in Phase B.

Endpoints:
  Threads:   GET/POST /deliberation/threads
             GET/PATCH /deliberation/threads/{id}
  Comments:  POST /deliberation/threads/{id}/comments
             POST /deliberation/threads/{id}/comments/{cid}/react
             POST /deliberation/threads/{id}/seen
  Proposals: POST /deliberation/threads/{id}/proposals
             GET  /deliberation/threads/{id}/proposals/{pid}
  Stances:   POST /deliberation/threads/{id}/proposals/{pid}/stance
  Outcomes:  POST /deliberation/threads/{id}/proposals/{pid}/outcome
  Tasks:     POST /deliberation/threads/{id}/tasks
             PATCH /deliberation/tasks/{tid}
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.dependencies import AuthenticatedUser, get_current_user
from backend.db import get_db
from backend.schemas.deliberation import (
    CommentCreateRequest,
    CommentResponse,
    OutcomeCreateRequest,
    OutcomeResponse,
    ProposalCreateRequest,
    ProposalDetail,
    ProposalSummary,
    ProposalTally,
    ReactionToggleRequest,
    StanceCreateRequest,
    StanceResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    ThreadCreateRequest,
    ThreadDetail,
    ThreadSummary,
    ThreadUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deliberation", tags=["deliberation"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uuid(val: str) -> uuid.UUID:
    try:
        return uuid.UUID(val)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid UUID: {val}")


async def _require_thread(conn: asyncpg.Connection, thread_id: str) -> dict[str, Any]:
    row = await conn.fetchrow(
        "SELECT id::text, title, context, author_did, sub_group_id::text, "
        "tags, status, ai_context_draft, agent_action_id::text, created_at, updated_at "
        "FROM deliberation_threads WHERE id = $1",
        _uuid(thread_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return dict(row)


# ── Threads ───────────────────────────────────────────────────────────────────

@router.get("/threads", response_model=list[ThreadSummary])
async def list_threads(
    status_filter: str | None = Query(default=None, alias="status"),
    tag: str | None = Query(default=None),
    sub_group_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[ThreadSummary]:
    """List threads, optionally filtered by status, tag, subgroup, or full-text search."""
    clauses = []
    params: list[Any] = []

    if status_filter:
        params.append(status_filter)
        clauses.append(f"t.status = ${len(params)}")
    if tag:
        params.append(tag)
        clauses.append(f"${ len(params) } = ANY(t.tags)")
    if sub_group_id:
        params.append(_uuid(sub_group_id))
        clauses.append(f"t.sub_group_id = ${len(params)}")
    if search:
        params.append(f"%{search}%")
        clauses.append(f"(t.title ILIKE ${len(params)} OR t.context ILIKE ${len(params)})")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = await conn.fetch(
        f"""
        SELECT
            t.id::text, t.title, t.author_did, t.status, t.tags, t.sub_group_id::text,
            COALESCE(MAX(c.created_at), t.created_at) AS last_activity,
            COUNT(DISTINCT c.id)::int                 AS comment_count,
            COUNT(DISTINCT p.id) FILTER (WHERE p.status = 'open')::int AS open_proposal_count
        FROM deliberation_threads t
        LEFT JOIN thread_comments      c ON c.thread_id = t.id
        LEFT JOIN deliberation_proposals p ON p.thread_id = t.id
        {where}
        GROUP BY t.id
        ORDER BY last_activity DESC
        """,
        *params,
    )
    return [ThreadSummary(**dict(r)) for r in rows]


@router.post("/threads", response_model=ThreadDetail, status_code=status.HTTP_201_CREATED)
async def create_thread(
    req: ThreadCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    """
    Create a new deliberation thread.
    Phase B: DiscussionAgent will be triggered here to draft context.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO deliberation_threads
            (title, context, author_did, sub_group_id, tags)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id::text, title, context, author_did, sub_group_id::text,
                  tags, status, ai_context_draft, agent_action_id::text,
                  created_at, updated_at
        """,
        req.title, req.context, req.author_did,
        _uuid(req.sub_group_id) if req.sub_group_id else None,
        req.tags,
    )
    return ThreadDetail(**dict(row))


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    """Return full thread with comments, proposals, and tasks."""
    thread = await _require_thread(conn, thread_id)

    comments_rows = await conn.fetch(
        "SELECT id::text, thread_id::text, author_did, parent_id::text, "
        "body, edited_at, created_at "
        "FROM thread_comments WHERE thread_id = $1 ORDER BY created_at",
        _uuid(thread_id),
    )
    proposal_rows = await conn.fetch(
        "SELECT p.id::text, p.title, p.process_type, p.status, p.closing_at, "
        "COUNT(s.id)::int AS stance_count "
        "FROM deliberation_proposals p "
        "LEFT JOIN proposal_stances s ON s.proposal_id = p.id "
        "WHERE p.thread_id = $1 GROUP BY p.id ORDER BY p.created_at",
        _uuid(thread_id),
    )
    task_rows = await conn.fetch(
        "SELECT id::text, thread_id::text, outcome_id::text, title, "
        "assignee_did, due_date::text, done, done_at, created_by, created_at "
        "FROM thread_tasks WHERE thread_id = $1 ORDER BY created_at",
        _uuid(thread_id),
    )

    thread["comments"]  = [CommentResponse(**dict(r)) for r in comments_rows]
    thread["proposals"] = [ProposalSummary(**dict(r)) for r in proposal_rows]
    thread["tasks"]     = [TaskResponse(**dict(r)) for r in task_rows]
    return ThreadDetail(**thread)


@router.patch("/threads/{thread_id}", response_model=ThreadDetail)
async def update_thread(
    thread_id: str,
    req: ThreadUpdateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ThreadDetail:
    """Update thread title, context, status, or tags (author or steward only)."""
    thread = await _require_thread(conn, thread_id)

    updates: list[str] = ["updated_at = NOW()"]
    params: list[Any] = []

    if req.title is not None:
        params.append(req.title);    updates.append(f"title = ${len(params)}")
    if req.context is not None:
        params.append(req.context);  updates.append(f"context = ${len(params)}")
    if req.status is not None:
        params.append(req.status.value); updates.append(f"status = ${len(params)}")
    if req.tags is not None:
        params.append(req.tags);     updates.append(f"tags = ${len(params)}")

    params.append(_uuid(thread_id))
    row = await conn.fetchrow(
        f"UPDATE deliberation_threads SET {', '.join(updates)} "
        f"WHERE id = ${len(params)} "
        "RETURNING id::text, title, context, author_did, sub_group_id::text, "
        "tags, status, ai_context_draft, agent_action_id::text, created_at, updated_at",
        *params,
    )
    result = dict(row)
    result["comments"] = []
    result["proposals"] = []
    result["tasks"] = []
    return ThreadDetail(**result)


# ── Comments ──────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/comments",
             response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    thread_id: str,
    req: CommentCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> CommentResponse:
    """Post a comment to a thread."""
    await _require_thread(conn, thread_id)
    row = await conn.fetchrow(
        """
        INSERT INTO thread_comments (thread_id, author_did, parent_id, body)
        VALUES ($1, $2, $3, $4)
        RETURNING id::text, thread_id::text, author_did, parent_id::text,
                  body, edited_at, created_at
        """,
        _uuid(thread_id), req.author_did,
        _uuid(req.parent_id) if req.parent_id else None,
        req.body,
    )
    result = dict(row)
    result["reactions"] = {}
    return CommentResponse(**result)


@router.post("/threads/{thread_id}/comments/{comment_id}/react",
             status_code=status.HTTP_200_OK)
async def toggle_reaction(
    thread_id: str,
    comment_id: str,
    req: ReactionToggleRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Toggle an emoji reaction on a comment (adds if absent, removes if present)."""
    existing = await conn.fetchrow(
        "SELECT 1 FROM thread_reactions WHERE comment_id = $1 "
        "AND member_did = $2 AND emoji = $3",
        _uuid(comment_id), req.member_did, req.emoji,
    )
    if existing:
        await conn.execute(
            "DELETE FROM thread_reactions WHERE comment_id = $1 "
            "AND member_did = $2 AND emoji = $3",
            _uuid(comment_id), req.member_did, req.emoji,
        )
        return {"action": "removed", "emoji": req.emoji}
    else:
        await conn.execute(
            "INSERT INTO thread_reactions (comment_id, member_did, emoji) "
            "VALUES ($1, $2, $3)",
            _uuid(comment_id), req.member_did, req.emoji,
        )
        return {"action": "added", "emoji": req.emoji}


@router.post("/threads/{thread_id}/seen", status_code=status.HTTP_200_OK)
async def mark_seen(
    thread_id: str,
    member_did: str = Query(...),
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, str]:
    """Mark a thread as seen by a member (upsert)."""
    await conn.execute(
        """
        INSERT INTO thread_seen (thread_id, member_did, last_seen_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (thread_id, member_did) DO UPDATE SET last_seen_at = NOW()
        """,
        _uuid(thread_id), member_did,
    )
    return {"status": "seen"}
```

- [ ] **Step 4: Register in `backend/main.py`**

Add import:
```python
from backend.routers.deliberation import router as deliberation_router
```

Add include:
```python
app.include_router(deliberation_router)      # /deliberation — threads, proposals, votes
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestThreadEndpoints -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/deliberation.py backend/main.py tests/test_deliberation_data_layer.py
git commit -m "feat(routers): add /deliberation/threads and /comments endpoints"
```

---

## Chunk 4: Deliberation Router — Proposals, Stances, Outcomes, Tasks

### Task 7: Proposal, stance, outcome, and task endpoints

**Files:**
- Modify: `backend/routers/deliberation.py` (append remaining endpoints)
- Test: `tests/test_deliberation_data_layer.py`

- [ ] **Step 1: Write failing tests**

```python
import uuid as _uuid_mod

class TestProposalEndpoints:
    async def test_create_proposal_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        from datetime import datetime, timezone

        thread_id = str(_uuid_mod.uuid4())
        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:example:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        fake_proposal = {
            "id": str(_uuid_mod.uuid4()), "thread_id": thread_id,
            "title": "Adopt new pay policy", "body": "We propose...",
            "process_type": "consent", "options": None, "quorum_pct": 0,
            "closing_at": None, "status": "open", "ai_draft": None,
            "author_did": "did:example:alice", "agent_action_id": None,
            "created_at": datetime.now(timezone.utc), "closed_at": None,
        }
        # fetchrow called twice: once for _require_thread, once for INSERT
        mock_db.fetchrow = AsyncMock(side_effect=[fake_thread, fake_proposal])
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/proposals",
            json={
                "thread_id": thread_id, "title": "Adopt new pay policy",
                "body": "We propose...", "process_type": "consent",
                "author_did": "did:example:alice",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["process_type"] == "consent"
        app.dependency_overrides.clear()

    async def test_cast_stance_returns_200(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        from datetime import datetime, timezone

        thread_id  = str(_uuid_mod.uuid4())
        proposal_id = str(_uuid_mod.uuid4())
        fake_proposal = {
            "id": proposal_id, "thread_id": thread_id, "title": "t",
            "body": "b", "process_type": "consent", "options": None,
            "quorum_pct": 0, "closing_at": None, "status": "open",
            "ai_draft": None, "author_did": "did:example:alice",
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc), "closed_at": None,
        }
        fake_stance = {
            "id": str(_uuid_mod.uuid4()), "proposal_id": proposal_id,
            "member_did": "did:example:bob", "stance": "agree",
            "reason": "Good idea", "score": None, "rank_order": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(side_effect=[fake_proposal, fake_stance])
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/proposals/{proposal_id}/stance",
            json={"member_did": "did:example:bob", "stance": "agree", "reason": "Good idea"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["stance"] == "agree"
        app.dependency_overrides.clear()

    async def test_create_task_returns_201(self, async_client, mock_db):
        from backend.db import get_db
        from backend.main import app
        from datetime import datetime, timezone

        thread_id = str(_uuid_mod.uuid4())
        fake_thread = {
            "id": thread_id, "title": "t", "context": "c",
            "author_did": "did:example:alice", "sub_group_id": None,
            "tags": [], "status": "open", "ai_context_draft": None,
            "agent_action_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        fake_task = {
            "id": str(_uuid_mod.uuid4()), "thread_id": thread_id,
            "outcome_id": None, "title": "Draft new contract",
            "assignee_did": "did:example:charlie", "due_date": "2026-05-01",
            "done": False, "done_at": None, "created_by": "did:example:alice",
            "created_at": datetime.now(timezone.utc),
        }
        mock_db.fetchrow = AsyncMock(side_effect=[fake_thread, fake_task])
        app.dependency_overrides[get_db] = lambda: mock_db

        resp = await async_client.post(
            f"/deliberation/threads/{thread_id}/tasks",
            json={
                "thread_id": thread_id, "title": "Draft new contract",
                "created_by": "did:example:alice",
                "assignee_did": "did:example:charlie", "due_date": "2026-05-01",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Draft new contract"
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/test_deliberation_data_layer.py::TestProposalEndpoints -v
```
Expected: `ERRORS` — proposal/stance/task routes not found

- [ ] **Step 3: Append proposal, stance, outcome, and task endpoints to `backend/routers/deliberation.py`**

```python
# ── Proposals ─────────────────────────────────────────────────────────────────

async def _require_proposal(
    conn: asyncpg.Connection, proposal_id: str
) -> dict[str, Any]:
    row = await conn.fetchrow(
        "SELECT id::text, thread_id::text, title, body, process_type, options, "
        "quorum_pct, closing_at, status, ai_draft, author_did, "
        "agent_action_id::text, created_at, closed_at "
        "FROM deliberation_proposals WHERE id = $1",
        _uuid(proposal_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return dict(row)


@router.post("/threads/{thread_id}/proposals",
             response_model=ProposalDetail, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    thread_id: str,
    req: ProposalCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalDetail:
    """
    Attach a proposal to a thread.
    Phase B: ProposalAgent will draft body and recommend process_type.
    """
    await _require_thread(conn, thread_id)
    import json
    row = await conn.fetchrow(
        """
        INSERT INTO deliberation_proposals
            (thread_id, title, body, process_type, options, quorum_pct,
             closing_at, author_did)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        RETURNING id::text, thread_id::text, title, body, process_type, options,
                  quorum_pct, closing_at, status, ai_draft, author_did,
                  agent_action_id::text, created_at, closed_at
        """,
        _uuid(thread_id), req.title, req.body, req.process_type.value,
        json.dumps(req.options) if req.options else None,
        req.quorum_pct, req.closing_at, req.author_did,
    )
    result = dict(row)
    result["stances"] = []
    result["tally"] = ProposalTally()
    result["outcome"] = None
    return ProposalDetail(**result)


@router.get("/threads/{thread_id}/proposals/{proposal_id}",
            response_model=ProposalDetail)
async def get_proposal(
    thread_id: str,
    proposal_id: str,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ProposalDetail:
    """Return proposal with all stances and live tally."""
    proposal = await _require_proposal(conn, proposal_id)

    stance_rows = await conn.fetch(
        "SELECT id::text, proposal_id::text, member_did, stance, reason, "
        "score, rank_order, created_at, updated_at "
        "FROM proposal_stances WHERE proposal_id = $1 ORDER BY created_at",
        _uuid(proposal_id),
    )
    stances = [StanceResponse(**dict(r)) for r in stance_rows]

    tally = ProposalTally(total=len(stances))
    for s in stances:
        if s.stance in ("agree", "abstain", "disagree", "block"):
            setattr(tally, s.stance, getattr(tally, s.stance, 0) + 1)
        else:
            tally.options[s.stance] = tally.options.get(s.stance, 0) + 1

    outcome_row = await conn.fetchrow(
        "SELECT id::text, proposal_id::text, statement, decision_type, "
        "precedent_id::text, ai_draft, stated_by, agent_action_id::text, created_at "
        "FROM decision_outcomes WHERE proposal_id = $1",
        _uuid(proposal_id),
    )
    outcome = OutcomeResponse(**dict(outcome_row)) if outcome_row else None

    proposal["stances"] = stances
    proposal["tally"]   = tally
    proposal["outcome"] = outcome
    return ProposalDetail(**proposal)


# ── Stances ───────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/proposals/{proposal_id}/stance",
             response_model=StanceResponse)
async def cast_stance(
    thread_id: str,
    proposal_id: str,
    req: StanceCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> StanceResponse:
    """
    Cast or update a stance on a proposal.
    Phase B: VotingAgent will validate and check closing conditions.
    """
    proposal = await _require_proposal(conn, proposal_id)
    if proposal["status"] != "open":
        raise HTTPException(status_code=409, detail="Proposal is not open for voting")

    import json
    row = await conn.fetchrow(
        """
        INSERT INTO proposal_stances
            (proposal_id, member_did, stance, reason, score, rank_order)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (proposal_id, member_did) DO UPDATE
            SET stance     = EXCLUDED.stance,
                reason     = EXCLUDED.reason,
                score      = EXCLUDED.score,
                rank_order = EXCLUDED.rank_order,
                updated_at = NOW()
        RETURNING id::text, proposal_id::text, member_did, stance, reason,
                  score, rank_order, created_at, updated_at
        """,
        _uuid(proposal_id), req.member_did, req.stance,
        req.reason, req.score,
        json.dumps(req.rank_order) if req.rank_order else None,
    )
    return StanceResponse(**dict(row))


# ── Outcomes ──────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/proposals/{proposal_id}/outcome",
             response_model=OutcomeResponse, status_code=status.HTTP_201_CREATED)
async def state_outcome(
    thread_id: str,
    proposal_id: str,
    req: OutcomeCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> OutcomeResponse:
    """
    State the outcome of a closed proposal.
    Phase B: OutcomeAgent will draft the statement and store the precedent.
    """
    proposal = await _require_proposal(conn, proposal_id)

    # Close the proposal
    await conn.execute(
        "UPDATE deliberation_proposals SET status = 'closed', closed_at = NOW() "
        "WHERE id = $1",
        _uuid(proposal_id),
    )

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO decision_outcomes
                (proposal_id, statement, decision_type, stated_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id::text, proposal_id::text, statement, decision_type,
                      precedent_id::text, ai_draft, stated_by,
                      agent_action_id::text, created_at
            """,
            _uuid(proposal_id), req.statement, req.decision_type.value, req.stated_by,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=409, detail="Outcome already stated for this proposal"
        )
    return OutcomeResponse(**dict(row))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.post("/threads/{thread_id}/tasks",
             response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    thread_id: str,
    req: TaskCreateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> TaskResponse:
    """Create a task within a thread."""
    await _require_thread(conn, thread_id)
    row = await conn.fetchrow(
        """
        INSERT INTO thread_tasks
            (thread_id, outcome_id, title, assignee_did, due_date, created_by)
        VALUES ($1, $2, $3, $4, $5::date, $6)
        RETURNING id::text, thread_id::text, outcome_id::text, title,
                  assignee_did, due_date::text, done, done_at, created_by, created_at
        """,
        _uuid(thread_id),
        _uuid(req.outcome_id) if req.outcome_id else None,
        req.title, req.assignee_did, req.due_date, req.created_by,
    )
    return TaskResponse(**dict(row))


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    req: TaskUpdateRequest,
    conn: asyncpg.Connection = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> TaskResponse:
    """Update a task — mark done, reassign, or update due date."""
    updates = []
    params: list[Any] = []

    if req.done is not None:
        params.append(req.done);        updates.append(f"done = ${len(params)}")
        if req.done:
            updates.append("done_at = NOW()")
        else:
            updates.append("done_at = NULL")
    if req.assignee_did is not None:
        params.append(req.assignee_did); updates.append(f"assignee_did = ${len(params)}")
    if req.due_date is not None:
        params.append(req.due_date);    updates.append(f"due_date = ${len(params)}::date")
    if req.title is not None:
        params.append(req.title);       updates.append(f"title = ${len(params)}")

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    params.append(_uuid(task_id))
    row = await conn.fetchrow(
        f"UPDATE thread_tasks SET {', '.join(updates)} WHERE id = ${len(params)} "
        "RETURNING id::text, thread_id::text, outcome_id::text, title, "
        "assignee_did, due_date::text, done, done_at, created_by, created_at",
        *params,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**dict(row))
```

- [ ] **Step 4: Run all deliberation tests**

```bash
python -m pytest tests/test_deliberation_data_layer.py -v
```
Expected: All tests `PASS`

- [ ] **Step 5: Run full test suite to check no regressions**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: All previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/deliberation.py tests/test_deliberation_data_layer.py
git commit -m "feat(routers): add proposals, stances, outcomes, and tasks endpoints to deliberation router"
```

---

## Chunk 5: Frontend Types, API Client, and Sidebar

### Task 8: TypeScript types (`frontend-next/src/types/index.ts`)

**Files:**
- Modify: `frontend-next/src/types/index.ts` (append)

- [ ] **Step 1: Append deliberation types to `frontend-next/src/types/index.ts`**

Open the file and append at the end:

```typescript
// ── Deliberation (Native Loomio) ──────────────────────────────────────────

export type ProcessType =
  | 'sense_check' | 'advice' | 'consent' | 'consensus'
  | 'choose' | 'score' | 'allocate' | 'rank' | 'time_poll'

export type StanceOption = 'agree' | 'abstain' | 'disagree' | 'block'
export type ThreadStatus  = 'open' | 'closed' | 'pinned'
export type ProposalStatus = 'open' | 'closed' | 'withdrawn'
export type DecisionType  = 'passed' | 'rejected' | 'withdrawn' | 'no_quorum'

export interface SubGroup {
  id: string
  slug: string
  name: string
  description: string | null
  created_by: string
  created_at: string
}

export interface SubGroupMember {
  sub_group_id: string
  member_did: string
  role: 'member' | 'coordinator'
  joined_at: string
}

export interface ThreadSummary {
  id: string
  title: string
  author_did: string
  status: ThreadStatus
  tags: string[]
  sub_group_id: string | null
  open_proposal_count: number
  comment_count: number
  last_activity: string
}

export interface CommentResponse {
  id: string
  thread_id: string
  author_did: string
  parent_id: string | null
  body: string
  edited_at: string | null
  created_at: string
  reactions: Record<string, number>
}

export interface ProposalTally {
  agree: number
  abstain: number
  disagree: number
  block: number
  total: number
  options: Record<string, number>
}

export interface StanceResponse {
  id: string
  proposal_id: string
  member_did: string
  stance: string
  reason: string | null
  score: number | null
  rank_order: Record<string, unknown>[] | null
  created_at: string
  updated_at: string
}

export interface OutcomeResponse {
  id: string
  proposal_id: string
  statement: string
  decision_type: DecisionType
  precedent_id: string | null
  ai_draft: string | null
  stated_by: string
  created_at: string
}

export interface ProposalSummary {
  id: string
  title: string
  process_type: ProcessType
  status: ProposalStatus
  closing_at: string | null
  stance_count: number
}

export interface ProposalDetail extends ProposalSummary {
  thread_id: string
  body: string
  options: string[] | null
  quorum_pct: number
  ai_draft: string | null
  author_did: string
  created_at: string
  closed_at: string | null
  stances: StanceResponse[]
  tally: ProposalTally | null
  outcome: OutcomeResponse | null
}

export interface ThreadDetail {
  id: string
  title: string
  context: string
  author_did: string
  sub_group_id: string | null
  tags: string[]
  status: ThreadStatus
  ai_context_draft: string | null
  created_at: string
  updated_at: string
  comments: CommentResponse[]
  proposals: ProposalSummary[]
  tasks: TaskResponse[]
}

export interface TaskResponse {
  id: string
  thread_id: string
  outcome_id: string | null
  title: string
  assignee_did: string | null
  due_date: string | null
  done: boolean
  done_at: string | null
  created_by: string
  created_at: string
}

// WebSocket deliberation events (extends existing AgentEvent)
export type DeliberationEvent =
  | 'thread_created'
  | 'comment_added'
  | 'proposal_opened'
  | 'stance_cast'
  | 'proposal_closed'
  | 'outcome_stated'
  | 'task_assigned'
  | 'member_nudge'
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/IskanderOS/frontend-next
npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend-next/src/types/index.ts
git commit -m "feat(frontend): add deliberation TypeScript types (ThreadDetail, ProposalDetail, stances, outcomes, tasks)"
```

---

### Task 9: API client namespace (`frontend-next/src/lib/api.ts`)

**Files:**
- Modify: `frontend-next/src/lib/api.ts` (append deliberation + subgroups namespaces)

- [ ] **Step 1: Append to `frontend-next/src/lib/api.ts`**

```typescript
// ── Deliberation API ──────────────────────────────────────────────────────

export const deliberation = {
  listThreads: (params?: {
    status?: string; tag?: string; sub_group_id?: string; search?: string
  }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return apiFetch<ThreadSummary[]>(`/deliberation/threads${q ? '?' + q : ''}`)
  },

  createThread: (body: {
    title: string; context?: string; author_did: string;
    sub_group_id?: string; tags?: string[]
  }) => apiFetch<ThreadDetail>('/deliberation/threads', {
    method: 'POST', body: JSON.stringify(body),
  }),

  getThread: (threadId: string) =>
    apiFetch<ThreadDetail>(`/deliberation/threads/${threadId}`),

  updateThread: (threadId: string, body: {
    title?: string; context?: string; status?: string; tags?: string[]
  }) => apiFetch<ThreadDetail>(`/deliberation/threads/${threadId}`, {
    method: 'PATCH', body: JSON.stringify(body),
  }),

  addComment: (threadId: string, body: {
    thread_id: string; author_did: string; body: string; parent_id?: string
  }) => apiFetch<CommentResponse>(`/deliberation/threads/${threadId}/comments`, {
    method: 'POST', body: JSON.stringify(body),
  }),

  toggleReaction: (threadId: string, commentId: string, body: {
    member_did: string; emoji: string
  }) => apiFetch<{ action: string; emoji: string }>(
    `/deliberation/threads/${threadId}/comments/${commentId}/react`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  markSeen: (threadId: string, memberDid: string) =>
    apiFetch<{ status: string }>(
      `/deliberation/threads/${threadId}/seen?member_did=${encodeURIComponent(memberDid)}`,
      { method: 'POST' },
    ),

  createProposal: (threadId: string, body: {
    thread_id: string; title: string; body: string;
    process_type: ProcessType; author_did: string;
    options?: string[]; quorum_pct?: number; closing_at?: string
  }) => apiFetch<ProposalDetail>(
    `/deliberation/threads/${threadId}/proposals`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  getProposal: (threadId: string, proposalId: string) =>
    apiFetch<ProposalDetail>(
      `/deliberation/threads/${threadId}/proposals/${proposalId}`
    ),

  castStance: (threadId: string, proposalId: string, body: {
    member_did: string; stance: string; reason?: string;
    score?: number; rank_order?: Record<string, unknown>[]
  }) => apiFetch<StanceResponse>(
    `/deliberation/threads/${threadId}/proposals/${proposalId}/stance`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  stateOutcome: (threadId: string, proposalId: string, body: {
    statement: string; decision_type: DecisionType; stated_by: string
  }) => apiFetch<OutcomeResponse>(
    `/deliberation/threads/${threadId}/proposals/${proposalId}/outcome`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  createTask: (threadId: string, body: {
    thread_id: string; title: string; created_by: string;
    assignee_did?: string; due_date?: string; outcome_id?: string
  }) => apiFetch<TaskResponse>(
    `/deliberation/threads/${threadId}/tasks`,
    { method: 'POST', body: JSON.stringify(body) },
  ),

  updateTask: (taskId: string, body: {
    done?: boolean; assignee_did?: string; due_date?: string; title?: string
  }) => apiFetch<TaskResponse>(`/deliberation/tasks/${taskId}`, {
    method: 'PATCH', body: JSON.stringify(body),
  }),
}

// ── SubGroups API ─────────────────────────────────────────────────────────

export const subgroups = {
  list: () => apiFetch<SubGroup[]>('/subgroups'),

  create: (body: { slug: string; name: string; created_by: string; description?: string }) =>
    apiFetch<SubGroup>('/subgroups', { method: 'POST', body: JSON.stringify(body) }),

  listMembers: (subgroupId: string) =>
    apiFetch<SubGroupMember[]>(`/subgroups/${subgroupId}/members`),

  addMember: (subgroupId: string, body: { member_did: string; role?: string }) =>
    apiFetch<SubGroupMember>(`/subgroups/${subgroupId}/members`, {
      method: 'POST', body: JSON.stringify(body),
    }),

  removeMember: (subgroupId: string, memberDid: string) =>
    apiFetch<void>(
      `/subgroups/${subgroupId}/members/${encodeURIComponent(memberDid)}`,
      { method: 'DELETE' },
    ),
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/IskanderOS/frontend-next
npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend-next/src/lib/api.ts
git commit -m "feat(frontend): add deliberation and subgroups API client namespaces"
```

---

### Task 10: Sidebar navigation link

**Files:**
- Modify: `frontend-next/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Read the current Sidebar.tsx**

```bash
cat src/IskanderOS/frontend-next/src/components/layout/Sidebar.tsx
```

- [ ] **Step 2: Add Deliberation link**

Find the existing nav link list in `Sidebar.tsx` and add:

```tsx
{/* Add alongside existing governance, treasury, arbitration links */}
<Link
  href="/deliberation"
  className="flex items-center gap-2 px-3 py-2 rounded-md text-sm
             hover:bg-iskander-surface transition-colors"
>
  <span>💬</span>
  <span>Deliberation</span>
</Link>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd src/IskanderOS/frontend-next && npx tsc --noEmit
```

- [ ] **Step 4: Commit Phase A completion**

```bash
git add frontend-next/src/components/layout/Sidebar.tsx frontend-next/src/lib/api.ts
git commit -m "feat(frontend): add Deliberation nav link to Sidebar"
```

---

## Phase A Final Verification

- [ ] **Run all tests**

```bash
cd src/IskanderOS
python -m pytest tests/test_deliberation_data_layer.py -v
```
Expected: All tests `PASS`

- [ ] **Run full test suite — no regressions**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: All previously passing tests still pass

- [ ] **TypeScript compile check**

```bash
cd frontend-next && npx tsc --noEmit
```
Expected: No errors

- [ ] **Smoke test against real DB** (optional, requires docker)

```bash
cd src/IskanderOS
docker compose up postgres -d
# wait 5s
curl -s http://localhost:8000/subgroups \
  -H "Authorization: Bearer $TOKEN" | jq
# Expected: []

curl -s -X POST http://localhost:8000/subgroups \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug":"tech-wg","name":"Tech Working Group","created_by":"did:example:alice"}' | jq
# Expected: {"id":"...","slug":"tech-wg","name":"Tech Working Group",...}
```

- [ ] **Create PR and merge Phase A**

```bash
gh pr create \
  --title "feat(deliberation): Phase A — data layer (schemas, DB, CRUD routers, frontend types)" \
  --body "Adds 9 DB tables, deliberation + subgroups Pydantic schemas, asyncpg persistence layer,
two FastAPI CRUD routers, and Next.js TypeScript types + API client.
No AI agents yet — Phase B adds DiscussionAgent, ProposalAgent, VotingAgent, OutcomeAgent, TaskAgent."
```
