# Phase C Completion Sprint Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase C of Iskander — membership provisioning, meeting prep Clerk tools, and end-to-end verification against a Debian VM.

**Architecture:** Three sequential feature branches: (1) a new `provisioner` FastAPI service wired into the Clerk's tool loop via a `provision_member` write tool; (2) three new read-only Clerk tools for meeting agenda assembly pulling live data from decision-recorder and Loomio; (3) a `verify.sh` smoke test script plus GitHub Actions CI workflow that validates the full stack on every PR.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, httpx, Anthropic SDK, Helm/K3s, Ansible, Bash, GitHub Actions, K3d

**Spec:** `docs/superpowers/specs/2026-04-09-phase-c-completion-sprint-design.md`
**Session:** 2375b4e8-754a-428b-aa00-c0b80430f9dc | **Tracking:** #53

---

## Prerequisites (before starting any chunk)

- [ ] Confirm PR #49 (`feature/s3-governance-clerk`) is merged to `main`. It adds `GET /tensions`, `POST /tensions`, `PATCH /tensions/{id}`, `GET /decisions/reviews/due`, `PATCH /decisions/{id}/review`, the `Tension` model, and review-scheduling columns to `Decision`. Chunk 2 depends on these endpoints.
- [ ] Branch all three feature branches from `main` **after** PR #49 merges — not from `feature/steward-agent`.

---

## Chunk 1: feature/membership-provisioning (C.9)

**New service:** `src/IskanderOS/services/provisioner/`
**Clerk extension:** `src/IskanderOS/openclaw/agents/clerk/tools.py` + `agent.py` + `SOUL.md`
**Helm:** `infra/helm/iskander/templates/provisioner.yaml` + `values.yaml`
**Installer:** `install/roles/secrets/templates/generated-values.yaml.j2`
**Docs:** `docs/operations/member-provisioning.md`
**Tests:** `src/IskanderOS/services/provisioner/tests/test_provisioner.py` + `src/IskanderOS/openclaw/agents/clerk/tests/test_agent_provision.py`

### File map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/IskanderOS/services/provisioner/main.py` | Create | FastAPI app: `POST /members`, `GET /members/{username}`, `GET /health` |
| `src/IskanderOS/services/provisioner/db.py` | Create | SQLAlchemy `ProvisioningRecord` model + session factory |
| `src/IskanderOS/services/provisioner/authentik.py` | Create | Authentik admin API calls: create user, generate recovery link |
| `src/IskanderOS/services/provisioner/loomio.py` | Create | Loomio API calls: add user to group |
| `src/IskanderOS/services/provisioner/mattermost.py` | Create | Mattermost API calls: post welcome message to onboarding channel |
| `src/IskanderOS/services/provisioner/Dockerfile` | Create | Same pattern as decision-recorder |
| `src/IskanderOS/services/provisioner/requirements.txt` | Create | fastapi, uvicorn, httpx, pydantic, sqlalchemy, psycopg2-binary |
| `src/IskanderOS/services/provisioner/tests/test_provisioner.py` | Create | Unit tests for `POST /members`, `GET /members/{username}` with mocked clients |
| `src/IskanderOS/openclaw/agents/clerk/tools.py` | Modify | Add `provision_member` tool function + DECISION_RECORDER_BASE already present; add PROVISIONER_BASE |
| `src/IskanderOS/openclaw/agents/clerk/agent.py` | Modify | Add `provision_member` to `_WRITE_TOOLS` |
| `src/IskanderOS/openclaw/agents/clerk/SOUL.md` | Modify | Add "New member onboarding" section |
| `src/IskanderOS/openclaw/agents/clerk/tests/test_agent_provision.py` | Create | Unit test: `_validate_response_ordering` rejects `provision_member` without prior `glass_box_log` |
| `infra/helm/iskander/templates/provisioner.yaml` | Create | Deployment + Service + NetworkPolicy + Secret |
| `infra/helm/iskander/values.yaml` | Modify | Add `provisioner` block |
| `install/roles/secrets/templates/generated-values.yaml.j2` | Modify | Add `PROVISIONER_WELCOME_CHANNEL_ID` prompt + wire into provisioner secret |
| `docs/operations/member-provisioning.md` | Create | Operator guide |

---

### Task 1.1: Provisioner database model

**Files:**
- Create: `src/IskanderOS/services/provisioner/db.py`
- Create: `src/IskanderOS/services/provisioner/tests/__init__.py`
- Create: `src/IskanderOS/services/provisioner/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# src/IskanderOS/services/provisioner/tests/test_db.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from provisioner.db import Base, ProvisioningRecord, create_tables


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_provisioning_record_roundtrip():
    db = make_session()
    rec = ProvisioningRecord(
        username="alice",
        email="alice@example.coop",
        display_name="Alice",
        authentik_id="auth-123",
        authentik_exists=True,
        loomio_membership_id=42,
        loomio_member=True,
        mattermost_post_id="post-xyz",
        mattermost_notified=True,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    assert rec.id is not None
    assert rec.username == "alice"
    assert rec.loomio_member is True
    assert rec.provisioned_at is not None


def test_get_by_username_returns_none_for_unknown():
    db = make_session()
    result = db.query(ProvisioningRecord).filter_by(username="ghost").first()
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/IskanderOS/services/provisioner
pip install fastapi uvicorn httpx pydantic sqlalchemy psycopg2-binary pytest
pytest tests/test_db.py -v
```
Expected: `ModuleNotFoundError: No module named 'provisioner'` or `ImportError`

- [ ] **Step 3: Create `db.py`**

```python
# src/IskanderOS/services/provisioner/db.py
"""
SQLAlchemy models for the provisioner service.

One table:
  provisioning_records — audit log of member provisioning operations
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class ProvisioningRecord(Base):
    """Audit log entry for a member provisioning operation."""
    __tablename__ = "provisioning_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(128), nullable=False, unique=True, index=True)
    email = Column(String(256), nullable=False)
    display_name = Column(String(256), nullable=True)

    # Authentik
    authentik_id = Column(String(128), nullable=True)
    authentik_exists = Column(Boolean, nullable=False, default=False)

    # Loomio
    loomio_membership_id = Column(BigInteger, nullable=True)
    loomio_member = Column(Boolean, nullable=False, default=False)

    # Mattermost
    mattermost_post_id = Column(String(128), nullable=True)
    mattermost_notified = Column(Boolean, nullable=False, default=False)

    # Stored ephemerally on creation so the Clerk can surface it to the requesting member.
    # The link is single-use and time-limited — it becomes useless after first use.
    password_reset_url = Column(Text, nullable=True)

    provisioned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
```

Also create `src/IskanderOS/services/provisioner/__init__.py` (empty) and `src/IskanderOS/services/provisioner/tests/__init__.py` (empty).

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_db.py -v
```
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/IskanderOS/services/provisioner/
git commit -m "feat(provisioner): db model — ProvisioningRecord audit table"
```

---

### Task 1.2: Authentik client

**Files:**
- Create: `src/IskanderOS/services/provisioner/authentik.py`
- Create: `src/IskanderOS/services/provisioner/tests/test_authentik.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/IskanderOS/services/provisioner/tests/test_authentik.py
import os
os.environ.setdefault("AUTHENTIK_URL", "http://authentik-test")
os.environ.setdefault("AUTHENTIK_TOKEN", "test-token")

from unittest.mock import MagicMock, patch
import pytest
from provisioner.authentik import create_user, get_recovery_link


def test_create_user_returns_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"pk": "uuid-abc-123", "username": "alice"}
    mock_resp.raise_for_status = MagicMock()
    with patch("provisioner.authentik._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        result = create_user(username="alice", email="alice@example.coop", display_name="Alice")
    assert result["pk"] == "uuid-abc-123"


def test_get_recovery_link_returns_url():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"link": "https://auth.example.coop/recovery/abc123/"}
    mock_resp.raise_for_status = MagicMock()
    with patch("provisioner.authentik._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        link = get_recovery_link(user_pk="uuid-abc-123")
    assert link.startswith("https://")
    assert "recovery" in link


def test_create_user_raises_on_http_error():
    import httpx
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "409", request=MagicMock(), response=MagicMock()
    )
    with patch("provisioner.authentik._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        with pytest.raises(httpx.HTTPStatusError):
            create_user(username="alice", email="alice@example.coop", display_name="Alice")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_authentik.py -v
```
Expected: `ImportError: cannot import name 'create_user'`

- [ ] **Step 3: Create `authentik.py`**

```python
# src/IskanderOS/services/provisioner/authentik.py
"""
Authentik admin API client.

Uses the Authentik REST API v3. The AUTHENTIK_TOKEN must be a superuser-scoped
bootstrap token (generated by the installer). Phase B should replace this with
a scoped service account token.

Recovery link endpoint: POST /api/v3/core/users/{id}/recovery/
Generates a single-use expiring link the new member follows to set their password.
DO NOT use /set_password/ — that sets the password directly to a caller-provided value.

Confirm the exact endpoint against the deployed Authentik version before deploying.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

AUTHENTIK_BASE = os.environ["AUTHENTIK_URL"].rstrip("/")
AUTHENTIK_TOKEN = os.environ["AUTHENTIK_TOKEN"]

_TIMEOUT = float(os.environ.get("PROVISIONER_HTTP_TIMEOUT", "30"))


def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=_TIMEOUT,
        headers={"Authorization": f"Bearer {AUTHENTIK_TOKEN}"},
    )


def create_user(*, username: str, email: str, display_name: str) -> dict[str, Any]:
    """
    Create a new Authentik user. Returns the created user object including 'pk'.
    Raises httpx.HTTPStatusError on failure (e.g. 409 if username already exists).
    """
    payload = {
        "username": username,
        "name": display_name,
        "email": email,
        "is_active": True,
        "groups": [],
        "attributes": {},
    }
    with _http_client() as client:
        resp = client.post(f"{AUTHENTIK_BASE}/api/v3/core/users/", json=payload)
        resp.raise_for_status()
        return resp.json()


def get_recovery_link(*, user_pk: str) -> str:
    """
    Generate a single-use recovery link for the given Authentik user PK.
    The link is sent to the new member in the onboarding channel.
    """
    with _http_client() as client:
        resp = client.post(f"{AUTHENTIK_BASE}/api/v3/core/users/{user_pk}/recovery/")
        resp.raise_for_status()
        return resp.json()["link"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_authentik.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/IskanderOS/services/provisioner/authentik.py \
        src/IskanderOS/services/provisioner/tests/test_authentik.py
git commit -m "feat(provisioner): Authentik admin client — create user + recovery link"
```

---

### Task 1.3: Loomio and Mattermost clients

**Files:**
- Create: `src/IskanderOS/services/provisioner/loomio.py`
- Create: `src/IskanderOS/services/provisioner/mattermost.py`
- Create: `src/IskanderOS/services/provisioner/tests/test_loomio.py`
- Create: `src/IskanderOS/services/provisioner/tests/test_mattermost.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/IskanderOS/services/provisioner/tests/test_loomio.py
import os
os.environ.setdefault("LOOMIO_URL", "http://loomio-test")
os.environ.setdefault("LOOMIO_API_KEY", "test-key")
os.environ.setdefault("LOOMIO_DEFAULT_GROUP_KEY", "my-coop")

from unittest.mock import MagicMock, patch
from provisioner.loomio import add_member_to_group


def test_add_member_to_group_returns_membership_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"memberships": [{"id": 99, "user_id": 7}]}
    mock_resp.raise_for_status = MagicMock()
    with patch("provisioner.loomio._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        membership_id = add_member_to_group(email="alice@example.coop")
    assert membership_id == 99
```

```python
# src/IskanderOS/services/provisioner/tests/test_mattermost.py
import os
os.environ.setdefault("MATTERMOST_URL", "http://mm-test")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-token")
os.environ.setdefault("PROVISIONER_WELCOME_CHANNEL_ID", "chan-abc")

from unittest.mock import MagicMock, patch
from provisioner.mattermost import post_welcome_message


def test_post_welcome_message_returns_post_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "post-xyz", "create_at": 1234567890}
    mock_resp.raise_for_status = MagicMock()
    with patch("provisioner.mattermost._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp
        post_id = post_welcome_message(
            display_name="Alice",
            username="alice",
            recovery_link="https://auth.example.coop/recovery/abc/",
        )
    assert post_id == "post-xyz"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_loomio.py tests/test_mattermost.py -v
```
Expected: `ImportError` for both

- [ ] **Step 3: Create `loomio.py`**

```python
# src/IskanderOS/services/provisioner/loomio.py
"""
Loomio API client for member provisioning.
Adds a new member to the cooperative's default Loomio group by email.
"""
from __future__ import annotations

import os
import httpx

LOOMIO_BASE = os.environ["LOOMIO_URL"].rstrip("/")
LOOMIO_API_KEY = os.environ["LOOMIO_API_KEY"]
LOOMIO_DEFAULT_GROUP_KEY = os.environ["LOOMIO_DEFAULT_GROUP_KEY"]

_TIMEOUT = float(os.environ.get("PROVISIONER_HTTP_TIMEOUT", "30"))


def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=_TIMEOUT,
        headers={"Authorization": f"Token {LOOMIO_API_KEY}"},
    )


def add_member_to_group(*, email: str, group_key: str = LOOMIO_DEFAULT_GROUP_KEY) -> int:
    """
    Add a user to a Loomio group by email. Returns the new membership ID.
    Raises httpx.HTTPStatusError on failure.
    """
    with _http_client() as client:
        resp = client.post(
            f"{LOOMIO_BASE}/api/v1/memberships",
            json={"group_key": group_key, "email": email},
        )
        resp.raise_for_status()
        memberships = resp.json().get("memberships", [])
        return memberships[0]["id"]
```

- [ ] **Step 4: Create `mattermost.py`**

```python
# src/IskanderOS/services/provisioner/mattermost.py
"""
Mattermost API client for member provisioning.

Welcome messages are posted to a RESTRICTED onboarding channel (not #general)
because they contain a single-use password recovery link.
Set PROVISIONER_WELCOME_CHANNEL_ID to your cooperative's onboarding channel ID.
"""
from __future__ import annotations

import os
import httpx

MATTERMOST_BASE = os.environ["MATTERMOST_URL"].rstrip("/")
MATTERMOST_BOT_TOKEN = os.environ["MATTERMOST_BOT_TOKEN"]
WELCOME_CHANNEL_ID = os.environ["PROVISIONER_WELCOME_CHANNEL_ID"]

_TIMEOUT = float(os.environ.get("PROVISIONER_HTTP_TIMEOUT", "30"))


def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=_TIMEOUT,
        headers={"Authorization": f"Bearer {MATTERMOST_BOT_TOKEN}"},
    )


def post_welcome_message(
    *,
    display_name: str,
    username: str,
    recovery_link: str,
    channel_id: str = WELCOME_CHANNEL_ID,
) -> str:
    """
    Post a welcome message to the onboarding channel. Returns the Mattermost post ID.
    """
    message = (
        f"👋 Welcome to the cooperative, **{display_name}** (`{username}`)!\n\n"
        f"**Set your password here (link expires in 30 minutes):**\n{recovery_link}\n\n"
        f"Once you're in:\n"
        f"- Say hello in **#general**\n"
        f"- Message the **Clerk** (our AI secretary) if you have questions\n"
        f"- Check **Loomio** for open proposals and discussions\n\n"
        f"_This message was sent by the Iskander provisioner. "
        f"The recovery link is single-use — if it expires, ask any member to re-run provisioning._"
    )
    with _http_client() as client:
        resp = client.post(
            f"{MATTERMOST_BASE}/api/v4/posts",
            json={"channel_id": channel_id, "message": message},
        )
        resp.raise_for_status()
        return resp.json()["id"]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_loomio.py tests/test_mattermost.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add src/IskanderOS/services/provisioner/loomio.py \
        src/IskanderOS/services/provisioner/mattermost.py \
        src/IskanderOS/services/provisioner/tests/test_loomio.py \
        src/IskanderOS/services/provisioner/tests/test_mattermost.py
git commit -m "feat(provisioner): Loomio group membership + Mattermost welcome message clients"
```

---

### Task 1.4: Provisioner FastAPI service

**Files:**
- Create: `src/IskanderOS/services/provisioner/main.py`
- Modify: `src/IskanderOS/services/provisioner/tests/test_provisioner.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/IskanderOS/services/provisioner/tests/test_provisioner.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AUTHENTIK_URL", "http://authentik-test")
os.environ.setdefault("AUTHENTIK_TOKEN", "test-token")
os.environ.setdefault("LOOMIO_URL", "http://loomio-test")
os.environ.setdefault("LOOMIO_API_KEY", "test-key")
os.environ.setdefault("LOOMIO_DEFAULT_GROUP_KEY", "my-coop")
os.environ.setdefault("MATTERMOST_URL", "http://mm-test")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-token")
os.environ.setdefault("PROVISIONER_WELCOME_CHANNEL_ID", "chan-abc")

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from provisioner.main import app

client = TestClient(app)


def _mock_all_clients(authentik_pk="uuid-1", loomio_id=99, mm_post="post-1", recovery="https://auth/r/"):
    return {
        "provisioner.authentik.create_user": MagicMock(return_value={"pk": authentik_pk, "username": "alice"}),
        "provisioner.authentik.get_recovery_link": MagicMock(return_value=recovery),
        "provisioner.loomio.add_member_to_group": MagicMock(return_value=loomio_id),
        "provisioner.mattermost.post_welcome_message": MagicMock(return_value=mm_post),
    }


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_provision_member_success():
    mocks = _mock_all_clients()
    with patch("provisioner.main.create_user", mocks["provisioner.authentik.create_user"]), \
         patch("provisioner.main.get_recovery_link", mocks["provisioner.authentik.get_recovery_link"]), \
         patch("provisioner.main.add_member_to_group", mocks["provisioner.loomio.add_member_to_group"]), \
         patch("provisioner.main.post_welcome_message", mocks["provisioner.mattermost.post_welcome_message"]):
        resp = client.post("/members", json={
            "username": "alice", "email": "alice@example.coop", "display_name": "Alice"
        })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "alice"
    assert data["authentik_id"] == "uuid-1"
    assert data["loomio_membership_id"] == 99
    assert data["password_reset_url"] == "https://auth/r/"


def test_provision_member_idempotency():
    """Second provision of same username returns 409."""
    mocks = _mock_all_clients()
    with patch("provisioner.main.create_user", mocks["provisioner.authentik.create_user"]), \
         patch("provisioner.main.get_recovery_link", mocks["provisioner.authentik.get_recovery_link"]), \
         patch("provisioner.main.add_member_to_group", mocks["provisioner.loomio.add_member_to_group"]), \
         patch("provisioner.main.post_welcome_message", mocks["provisioner.mattermost.post_welcome_message"]):
        client.post("/members", json={"username": "bob", "email": "bob@example.coop", "display_name": "Bob"})
        resp2 = client.post("/members", json={"username": "bob", "email": "bob@example.coop", "display_name": "Bob"})
    assert resp2.status_code == 409


def test_get_member_status_found():
    mocks = _mock_all_clients()
    with patch("provisioner.main.create_user", mocks["provisioner.authentik.create_user"]), \
         patch("provisioner.main.get_recovery_link", mocks["provisioner.authentik.get_recovery_link"]), \
         patch("provisioner.main.add_member_to_group", mocks["provisioner.loomio.add_member_to_group"]), \
         patch("provisioner.main.post_welcome_message", mocks["provisioner.mattermost.post_welcome_message"]):
        client.post("/members", json={"username": "carol", "email": "carol@example.coop", "display_name": "Carol"})
    resp = client.get("/members/carol")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authentik_exists"] is True
    assert data["loomio_member"] is True
    assert data["mattermost_notified"] is True


def test_get_member_status_not_found():
    resp = client.get("/members/ghost")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_provisioner.py -v
```
Expected: `ImportError: cannot import name 'app'`

- [ ] **Step 3: Create `main.py`**

```python
# src/IskanderOS/services/provisioner/main.py
"""
Provisioner service — automates cooperative member onboarding.

Endpoints:
  POST /members              Provision a new member: Authentik → Loomio → Mattermost
  GET  /members/{username}   Check provisioning status across all three systems
  GET  /health               Service health

Internal service only — protected by NetworkPolicy + optional INTERNAL_SERVICE_TOKEN.
The welcome message goes to a restricted onboarding channel, not #general,
because it contains a single-use Authentik password recovery link.
"""
from __future__ import annotations

import hmac
import logging
import os
import time
from collections import defaultdict
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from provisioner.authentik import create_user, get_recovery_link
from provisioner.db import ProvisioningRecord, SessionLocal, create_tables, get_db
from provisioner.loomio import add_member_to_group
from provisioner.mattermost import post_welcome_message

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("provisioner")

app = FastAPI(
    title="Provisioner",
    description="Cooperative member onboarding — Authentik + Loomio + Mattermost",
    version="0.1.0",
)

INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

_RATE_WINDOW = 60
_PROVISION_MAX = int(os.environ.get("PROVISIONER_RATE_LIMIT", "10"))
_rate_counters: dict[str, list[float]] = defaultdict(list)


def _rate_check(key: str) -> None:
    now = time.monotonic()
    window_start = now - _RATE_WINDOW
    _rate_counters[key] = [t for t in _rate_counters[key] if t > window_start]
    if len(_rate_counters[key]) >= _PROVISION_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    _rate_counters[key].append(now)


def _verify_internal_caller(request: Request) -> None:
    if not INTERNAL_SERVICE_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Internal service token required")
    if not hmac.compare_digest(auth[7:], INTERNAL_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid service token")


@app.on_event("startup")
def startup() -> None:
    create_tables()
    logger.info("Provisioner ready.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class MemberProvisionRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., max_length=256)
    display_name: str = Field("", max_length=256)

    @field_validator("username")
    @classmethod
    def username_safe(cls, v: str) -> str:
        if not v.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise ValueError("username may only contain letters, numbers, hyphens, underscores, dots")
        return v.lower()


@app.post("/members", status_code=status.HTTP_201_CREATED)
def provision_member(
    body: MemberProvisionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Provision a new cooperative member across Authentik, Loomio, and Mattermost.
    Idempotency: returns 409 if username already has a provisioning record.
    """
    _verify_internal_caller(request)
    client_host = request.client.host if request.client else "unknown"
    _rate_check(f"provision:{client_host}")

    existing = db.query(ProvisioningRecord).filter_by(username=body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' already provisioned. Use GET /members/{body.username} to check status.")

    record = ProvisioningRecord(
        username=body.username,
        email=body.email,
        display_name=body.display_name or body.username,
    )
    db.add(record)
    db.commit()

    # Step 1: Authentik
    try:
        user_data = create_user(
            username=body.username,
            email=body.email,
            display_name=body.display_name or body.username,
        )
        record.authentik_id = user_data["pk"]
        record.authentik_exists = True
        db.commit()
        logger.info("Authentik user created: %s (%s)", body.username, user_data["pk"])
    except Exception:
        logger.exception("Authentik user creation failed for %s", body.username)
        raise HTTPException(status_code=502, detail="Authentik provisioning failed. The error has been logged.")

    # Step 2: Recovery link
    try:
        recovery_link = get_recovery_link(user_pk=record.authentik_id)
        record.password_reset_url = recovery_link
        db.commit()
    except Exception:
        logger.exception("Recovery link generation failed for %s", body.username)
        raise HTTPException(status_code=502, detail="Recovery link generation failed. The error has been logged.")

    # Step 3: Loomio
    try:
        membership_id = add_member_to_group(email=body.email)
        record.loomio_membership_id = membership_id
        record.loomio_member = True
        db.commit()
        logger.info("Loomio membership created: %s → %d", body.username, membership_id)
    except Exception:
        logger.exception("Loomio membership failed for %s", body.username)
        raise HTTPException(status_code=502, detail="Loomio provisioning failed. The error has been logged.")

    # Step 4: Mattermost welcome
    try:
        post_id = post_welcome_message(
            display_name=record.display_name,
            username=body.username,
            recovery_link=recovery_link,
        )
        record.mattermost_post_id = post_id
        record.mattermost_notified = True
        db.commit()
        logger.info("Welcome message posted for %s: %s", body.username, post_id)
    except Exception:
        logger.exception("Mattermost welcome failed for %s", body.username)
        # Non-fatal: provisioning succeeded even if welcome message failed
        logger.warning("Provisioning complete for %s but welcome message failed", body.username)

    return {
        "username": record.username,
        "authentik_id": record.authentik_id,
        "loomio_membership_id": record.loomio_membership_id,
        "mattermost_post_id": record.mattermost_post_id,
        "password_reset_url": record.password_reset_url,
        "provisioned_at": record.provisioned_at.isoformat(),
    }


@app.get("/members/{username}")
def get_member_status(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Check provisioning status for a member across all three systems."""
    record = db.query(ProvisioningRecord).filter_by(username=username).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"No provisioning record for '{username}'")
    return {
        "username": record.username,
        "authentik_exists": record.authentik_exists,
        "loomio_member": record.loomio_member,
        "mattermost_notified": record.mattermost_notified,
        "provisioned_at": record.provisioned_at.isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_provisioner.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/IskanderOS/services/provisioner/main.py \
        src/IskanderOS/services/provisioner/tests/test_provisioner.py
git commit -m "feat(provisioner): FastAPI service — POST /members, GET /members/{username}, GET /health"
```

---

### Task 1.5: Dockerfile and requirements

**Files:**
- Create: `src/IskanderOS/services/provisioner/Dockerfile`
- Create: `src/IskanderOS/services/provisioner/requirements.txt`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
httpx>=0.28.0
pydantic[email]>=2.9.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
```

- [ ] **Step 2: Create `Dockerfile`** (same non-root pattern as decision-recorder)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r provisioner && useradd -r -g provisioner provisioner

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R provisioner:provisioner /app

USER provisioner

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import httpx; httpx.get('http://localhost:3001/health').raise_for_status()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
```

- [ ] **Step 3: Build the image to confirm it works**

```bash
cd src/IskanderOS/services/provisioner
docker build -t iskander-provisioner:test .
```
Expected: successful build, no errors

- [ ] **Step 4: Commit**

```bash
git add src/IskanderOS/services/provisioner/Dockerfile \
        src/IskanderOS/services/provisioner/requirements.txt
git commit -m "feat(provisioner): Dockerfile + requirements"
```

---

### Task 1.6: Clerk `provision_member` tool + Glass Box enforcement unit test

**Files:**
- Modify: `src/IskanderOS/openclaw/agents/clerk/tools.py`
- Modify: `src/IskanderOS/openclaw/agents/clerk/agent.py`
- Modify: `src/IskanderOS/openclaw/agents/clerk/SOUL.md`
- Create: `src/IskanderOS/openclaw/agents/clerk/tests/test_agent_provision.py`

- [ ] **Step 1: Write the Glass Box enforcement unit test**

```python
# src/IskanderOS/openclaw/agents/clerk/tests/test_agent_provision.py
"""
Unit tests for provision_member Glass Box enforcement.
Tests the _validate_response_ordering function directly — the guard operates
at agent loop level, not via HTTP, so cannot be tested as a smoke test.
"""
from unittest.mock import MagicMock
from agents.clerk.agent import _validate_response_ordering


def _make_tool_block(name: str) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    return block


def test_provision_member_without_glass_box_is_rejected():
    content = [_make_tool_block("provision_member")]
    error = _validate_response_ordering(content)
    assert error is not None
    assert "glass_box_log" in error.lower() or "write tool" in error.lower()


def test_provision_member_after_glass_box_is_accepted():
    content = [
        _make_tool_block("glass_box_log"),
        _make_tool_block("provision_member"),
    ]
    error = _validate_response_ordering(content)
    assert error is None


def test_provision_member_before_glass_box_is_rejected():
    content = [
        _make_tool_block("provision_member"),
        _make_tool_block("glass_box_log"),
    ]
    error = _validate_response_ordering(content)
    assert error is not None
    assert "before" in error.lower() or "must come" in error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/IskanderOS/openclaw
pytest agents/clerk/tests/test_agent_provision.py -v
```
Expected: `provision_member` not in `_WRITE_TOOLS`, so tests fail

- [ ] **Step 3: Add `provision_member` to `tools.py`**

In `src/IskanderOS/openclaw/agents/clerk/tools.py`, add after the `DECISION_RECORDER_BASE` line:

```python
PROVISIONER_BASE = os.environ.get("PROVISIONER_URL", "http://provisioner:3001")
# Internal service token — forwarded to provisioner when set, so NetworkPolicy + token
# both enforce access (same defence-in-depth pattern as decision-recorder).
_INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
```

Add this function before the `TOOL_DEFINITIONS` block:

```python
# ---------------------------------------------------------------------------
# Provisioner — member onboarding (write operation: Glass Box required)
# ---------------------------------------------------------------------------

def provision_member(
    *,
    username: str,
    email: str,
    display_name: str = "",
) -> dict:
    """
    Provision a new cooperative member (Authentik account → Loomio group → Mattermost welcome).
    Glass Box MUST be called before this function.
    The actor_user_id of the requesting member is NOT injected here — provisioning
    creates a DIFFERENT user, not the requester.
    """
    payload = {
        "username": username,
        "email": email,
        "display_name": display_name or username,
    }
    headers = (
        {"Authorization": f"Bearer {_INTERNAL_SERVICE_TOKEN}"}
        if _INTERNAL_SERVICE_TOKEN
        else {}
    )
    with _http_client() as client:
        resp = client.post(f"{PROVISIONER_BASE}/members", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
```

Add the tool definition to `TOOL_DEFINITIONS`:

```python
    {
        "name": "provision_member",
        "description": (
            "Provision a new cooperative member: creates their Authentik account, "
            "adds them to the Loomio group, and posts a welcome message with their "
            "password setup link to the onboarding channel. "
            "REQUIRES glass_box_log to be called first. "
            "REQUIRES explicit confirmation from the requesting member before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Login username for the new member (lowercase, letters/numbers/hyphens only)"},
                "email": {"type": "string", "description": "Email address for the new member"},
                "display_name": {"type": "string", "description": "Full name or display name (optional)"},
            },
            "required": ["username", "email"],
        },
    },
```

Add to `TOOL_REGISTRY`:

```python
    "provision_member": provision_member,
```

- [ ] **Step 4: Add `provision_member` to `_WRITE_TOOLS` in `agent.py`**

In `src/IskanderOS/openclaw/agents/clerk/agent.py`, update `_WRITE_TOOLS`:

```python
_WRITE_TOOLS = {
    "loomio_create_discussion",
    "mattermost_post_message",
    "dr_log_tension",
    "dr_update_tension",
    "dr_set_review_date",
    "provision_member",
}
```

Note: `provision_member` is NOT added to the actor-injection check. The requesting member's `actor_user_id` is only injected into `glass_box_log` and tools where the actor and target are the same person.

Also update the `SYSTEM_PROMPT` critical tool ordering section to include `provision_member` in the list of write tools.

- [ ] **Step 5: Add "New member onboarding" section to `SOUL.md`**

Add before the `## Glass Box requirement` section:

```markdown
## New member onboarding

When a member asks you to onboard or provision a new colleague, follow this sequence carefully:

1. Ask for the new member's **username** (lowercase, letters/numbers/hyphens only), **email address**, and optionally their **display name**
2. Confirm the details: "I'm about to provision an account for [display_name] with username [username] and email [email]. This will create their Authentik login, add them to Loomio, and send a welcome message with their password setup link to the onboarding channel. Shall I go ahead?"
3. Wait for explicit confirmation before proceeding
4. Call `glass_box_log` with the provisioning intent, then `provision_member` in the next round
5. Report the outcome: confirm what was created and where the welcome message was sent

The welcome message contains a single-use password setup link. If the new member does not receive it or the link expires, any member can ask you to re-provision — `POST /members` returns 409 if the username already exists, so the requesting member would need to check `GET /members/{username}` to confirm status.

You cannot remove members. Member removal requires a circle decision via Loomio.
```

- [ ] **Step 6: Run unit tests to verify they pass**

```bash
cd src/IskanderOS/openclaw
pytest agents/clerk/tests/test_agent_provision.py -v
```
Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add src/IskanderOS/openclaw/agents/clerk/tools.py \
        src/IskanderOS/openclaw/agents/clerk/agent.py \
        src/IskanderOS/openclaw/agents/clerk/SOUL.md \
        src/IskanderOS/openclaw/agents/clerk/tests/test_agent_provision.py
git commit -m "feat(clerk): provision_member tool — Glass Box enforced, SOUL.md onboarding guidance"
```

---

### Task 1.7: Helm chart and values

**Files:**
- Create: `infra/helm/iskander/templates/provisioner.yaml`
- Modify: `infra/helm/iskander/values.yaml`
- Modify: `install/roles/secrets/templates/generated-values.yaml.j2`

- [ ] **Step 1: Add provisioner block to `values.yaml`**

After the `decisionRecorder:` block, add:

```yaml
# ---------------------------------------------------------------------------
# Provisioner — member onboarding service
# ---------------------------------------------------------------------------
provisioner:
  enabled: true
  image: "ghcr.io/argocyte/iskander/provisioner:latest"
  # Loomio group key that new members are added to by default
  loomioDefaultGroupKey: ""          # set during first-boot wizard
  # Mattermost channel ID for welcome messages (must be restricted — not #general)
  welcomeChannelId: ""               # set during first-boot wizard
  logLevel: "INFO"
  postgresql:
    password: ""                     # populated by install script
  resources:
    requests:
      memory: "64Mi"
      cpu: "50m"
    limits:
      memory: "128Mi"
      cpu: "200m"
```

- [ ] **Step 2: Create `infra/helm/iskander/templates/provisioner.yaml`**

Follow the exact pattern of `decision-recorder.yaml`. Key differences:
- Component label: `app.kubernetes.io/component: provisioner`
- Port: 3001
- Secret includes: `authentik-token`, `loomio-api-key`, `mattermost-bot-token`, `loomio-default-group-key`, `welcome-channel-id`, `postgresql-password`, `internal-service-token`
- NetworkPolicy ingress: allow from `openclaw` only (port 3001). Provisioner is never called directly from Traefik — it's Clerk-only.
- Condition: `{{- if .Values.provisioner.enabled }}`

The full template follows the same Secret + ConfigMap + Deployment + Service + NetworkPolicy structure as `decision-recorder.yaml`.

- [ ] **Step 3: Update `install/roles/secrets/templates/generated-values.yaml.j2`**

Add to the generated values:

```jinja2
provisioner:
  loomioDefaultGroupKey: "{{ loomio_default_group_key }}"
  welcomeChannelId: "{{ provisioner_welcome_channel_id }}"
  postgresql:
    password: "{{ provisioner_db_password }}"
```

Add the corresponding prompts to the first-boot wizard section:
- `loomio_default_group_key`: "Enter the Loomio group key new members should be added to"
- `provisioner_welcome_channel_id`: "Enter the Mattermost channel ID for onboarding welcome messages (must be a restricted channel, not #general)"
- `provisioner_db_password`: auto-generated

- [ ] **Step 4: Commit**

```bash
git add infra/helm/iskander/templates/provisioner.yaml \
        infra/helm/iskander/values.yaml \
        install/roles/secrets/templates/generated-values.yaml.j2
git commit -m "feat(helm): provisioner Deployment + Service + NetworkPolicy + first-boot wizard prompts"
```

---

### Task 1.8: Operator documentation

**Files:**
- Create: `docs/operations/member-provisioning.md`

- [ ] **Step 1: Create the operator guide**

```markdown
# Member Provisioning — Operator Guide

The Iskander provisioner automates the technical steps of onboarding a new cooperative member.

## What provisioning does

When a member asks the Clerk to provision a new colleague, the following happens automatically:

1. **Authentik account created** — the new member gets a login in your Authentik instance
2. **Recovery link generated** — a single-use, time-limited link for the new member to set their own password
3. **Added to Loomio** — the new member joins your cooperative's default Loomio group
4. **Welcome message posted** — to the configured onboarding channel in Mattermost

The recovery link is single-use and expires. It is posted to a **restricted onboarding channel** — not `#general`. Configure `PROVISIONER_WELCOME_CHANNEL_ID` to a channel where only admins and the provisioner bot can post.

## Configuration

| Variable | Description | Set by |
|----------|-------------|--------|
| `AUTHENTIK_TOKEN` | Bootstrap token for Authentik admin API | First-boot wizard |
| `LOOMIO_DEFAULT_GROUP_KEY` | Loomio group key for new members | First-boot wizard |
| `PROVISIONER_WELCOME_CHANNEL_ID` | Mattermost channel ID for welcome messages | First-boot wizard |
| `PROVISIONER_WELCOME_CHANNEL_ID` | Must be a restricted channel, not world-readable | Admin setup |

## Security notes

- **`AUTHENTIK_TOKEN` is a superuser-scoped bootstrap token.** It can do anything in Authentik. Phase B should replace it with a scoped Authentik service account. Guard this secret carefully.
- **Welcome messages contain password recovery links.** The `PROVISIONER_WELCOME_CHANNEL_ID` channel should be readable only by admins and the new member.
- The provisioner is callable only from the Clerk (openclaw pod) via NetworkPolicy. It is not exposed via Traefik.

## Re-running if provisioning fails mid-way

If provisioning fails partway through (e.g., Loomio is down), the provisioner logs a partial record. Check status with:

```bash
curl http://provisioner:3001/members/{username}
```

If `authentik_exists: true` but `loomio_member: false`, the Authentik account was created but Loomio membership failed. Ask the Clerk to re-provision — the idempotency check (`409` on duplicate username) will fire. In that case, an operator must delete the existing provisioning record from the database and retry, or manually add the member to Loomio.

## Checking provisioning status

```bash
# Via Clerk (recommended — logged to Glass Box)
# Ask: "Check provisioning status for username alice"

# Directly (admin only)
curl http://provisioner:3001/members/alice
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/operations/member-provisioning.md
git commit -m "docs: member provisioning operator guide"
```

---

### Task 1.9: Open PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feature/membership-provisioning
gh pr create \
  --title "feat(C.9): member provisioning service — Authentik + Loomio + Mattermost" \
  --body "Closes C.9. Provisioner FastAPI service + Clerk provision_member tool + Helm chart + operator guide. See #53 for sprint context."
```

- [ ] **Step 2: Comment on tracking issue**

```bash
gh issue comment 53 --body "Session 2375b4e8: feature/membership-provisioning PR opened. Awaiting review."
```

---

## Chunk 2: feature/meeting-prep-clerk (#47)

**Prerequisite:** PR #49 (`feature/s3-governance-clerk`) merged. PR for Chunk 1 (membership provisioner) does NOT need to be merged first — these are independent Clerk tools.

**Files:**
| File | Action | Responsibility |
|------|--------|---------------|
| `src/IskanderOS/openclaw/agents/clerk/tools.py` | Modify | Add `prepare_meeting_agenda`, `list_recent_decisions`, `draft_meeting_notice` |
| `src/IskanderOS/openclaw/agents/clerk/SOUL.md` | Modify | Add meeting facilitation section |
| `src/IskanderOS/openclaw/agents/clerk/tests/test_meeting_tools.py` | Create | Unit tests for all three tools |
| `docs/operations/meeting-prep.md` | Create | Facilitator guide |
| `docs/templates/governance/meeting-agenda.md` | Create | Blank agenda template |

---

### Task 2.1: Meeting prep tools — tests first

**Files:**
- Create: `src/IskanderOS/openclaw/agents/clerk/tests/test_meeting_tools.py`

- [ ] **Step 1: Write the failing tests**

```python
# src/IskanderOS/openclaw/agents/clerk/tests/test_meeting_tools.py
import os
os.environ.setdefault("LOOMIO_URL", "http://loomio-test")
os.environ.setdefault("LOOMIO_API_KEY", "test-key")
os.environ.setdefault("MATTERMOST_URL", "http://mm-test")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-token")
os.environ.setdefault("GLASS_BOX_URL", "http://dr-test")
os.environ.setdefault("DECISION_RECORDER_URL", "http://dr-test")

from unittest.mock import MagicMock, patch
from agents.clerk.tools import draft_meeting_notice, list_recent_decisions


def test_draft_meeting_notice_contains_key_fields():
    result = draft_meeting_notice(
        circle_key="governance",
        date="2026-04-15",
        facilitator="Alice",
    )
    assert "2026-04-15" in result
    assert "Alice" in result
    assert "governance" in result
    assert "loomio" in result.lower() or "http" in result


def test_draft_meeting_notice_is_local_only():
    """draft_meeting_notice makes no HTTP calls."""
    import httpx
    with patch.object(httpx, "Client", side_effect=AssertionError("should not make HTTP calls")):
        result = draft_meeting_notice(circle_key="ops", date="2026-04-20", facilitator="Bob")
    assert result  # just needs to return something


def test_list_recent_decisions_calls_decision_recorder():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "total": 2,
        "decisions": [
            {"id": 1, "title": "Adopt S3 governance", "outcome": "Passed with consent", "decided_at": "2026-04-01T10:00:00+00:00"},
            {"id": 2, "title": "New member fee", "outcome": "Passed with consent", "decided_at": "2026-03-20T10:00:00+00:00"},
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    with patch("agents.clerk.tools._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
        result = list_recent_decisions(limit=2)
    assert len(result) == 2
    assert result[0]["title"] == "Adopt S3 governance"


def test_prepare_meeting_agenda_returns_markdown():
    """prepare_meeting_agenda assembles data from multiple sources into markdown."""
    mock_tensions_resp = MagicMock()
    mock_tensions_resp.json.return_value = {"tensions": [
        {"id": 1, "description": "Onboarding is slow", "domain": "governance", "status": "open"}
    ]}
    mock_tensions_resp.raise_for_status = MagicMock()

    mock_reviews_resp = MagicMock()
    mock_reviews_resp.json.return_value = {"reviews": [
        {"id": 10, "title": "Member fee policy", "review_date": "2026-04-12", "review_circle": "governance"}
    ]}
    mock_reviews_resp.raise_for_status = MagicMock()

    mock_decisions_resp = MagicMock()
    mock_decisions_resp.json.return_value = {"decisions": [
        {"id": 5, "title": "S3 governance adopted", "outcome": "Passed", "decided_at": "2026-04-01T00:00:00+00:00"}
    ]}
    mock_decisions_resp.raise_for_status = MagicMock()

    mock_proposals_resp = MagicMock()
    mock_proposals_resp.json.return_value = {"polls": []}
    mock_proposals_resp.raise_for_status = MagicMock()

    def side_effect_get(url, **kwargs):
        if "tensions" in url:
            return mock_tensions_resp
        if "reviews/due" in url:
            return mock_reviews_resp
        if "decisions" in url:
            return mock_decisions_resp
        return mock_proposals_resp

    with patch("agents.clerk.tools._http_client") as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = side_effect_get
        # Also mock loomio list_proposals path
        with patch("agents.clerk.tools.loomio_list_proposals", return_value=[]):
            from agents.clerk.tools import prepare_meeting_agenda
            result = prepare_meeting_agenda(circle_key="governance", meeting_type="circle")

    assert "## circle" in result.lower() or "circle" in result
    assert "Onboarding is slow" in result
    assert "Member fee policy" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/IskanderOS/openclaw
pytest agents/clerk/tests/test_meeting_tools.py -v
```
Expected: `ImportError: cannot import name 'prepare_meeting_agenda'` or similar

- [ ] **Step 3: Implement the three tools in `tools.py`**

Add after the `dr_set_review_date` function and before `TOOL_DEFINITIONS`:

```python
# ---------------------------------------------------------------------------
# Meeting preparation tools (all read-only — no Glass Box required)
# ---------------------------------------------------------------------------

def list_recent_decisions(
    group_key: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """
    Return the most recent recorded decisions in a meeting-friendly format.
    Useful as agenda context — shows what the circle has already decided.
    """
    params: dict = {"limit": limit}
    if group_key:
        params["group_key"] = group_key
    with _http_client() as client:
        resp = client.get(f"{DECISION_RECORDER_BASE}/decisions", params=params)
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "id": d["id"],
            "title": d["title"],
            "outcome": (d.get("outcome") or "")[:200],
            "decided_at": d.get("decided_at"),
        }
        for d in data.get("decisions", [])
    ]


def draft_meeting_notice(
    *,
    circle_key: str,
    date: str,
    facilitator: str,
) -> str:
    """
    Format a Mattermost-ready meeting announcement. Local formatting only — no API call.
    To post it: ask the Clerk to post it to a channel (requires Glass Box via mattermost_post_message).
    The Loomio group URL uses the pattern {LOOMIO_BASE}/g/{circle_key}.
    """
    loomio_url = f"{LOOMIO_BASE}/g/{circle_key}"
    return (
        f"📅 **Circle meeting — {date}**\n\n"
        f"**Facilitator:** {facilitator}\n"
        f"**Circle:** {circle_key}\n"
        f"**Loomio group:** {loomio_url}\n\n"
        f"To prepare the agenda, message the Clerk: "
        f'_"Prepare the agenda for the {circle_key} circle meeting on {date}"_'
    )


def prepare_meeting_agenda(
    *,
    circle_key: str,
    meeting_type: str = "circle",
) -> str:
    """
    Assemble a structured meeting agenda from live data sources.
    Pulls: open tensions, agreements due for review, closing proposals, recent decisions.
    Returns a markdown-formatted agenda ready to share with the circle.
    """
    from datetime import date as _date

    # Fetch all four sources (failures are non-fatal — show empty section with note)
    tensions: list[dict] = []
    try:
        with _http_client() as client:
            resp = client.get(
                f"{DECISION_RECORDER_BASE}/tensions",
                params={"status": "open", "domain": circle_key, "limit": 10},
            )
            resp.raise_for_status()
            tensions = resp.json().get("tensions", [])
    except Exception:
        logger.warning("Could not fetch tensions for agenda — showing empty section")

    due_reviews: list[dict] = []
    try:
        with _http_client() as client:
            resp = client.get(
                f"{DECISION_RECORDER_BASE}/decisions/reviews/due",
                params={"days_ahead": 14},
            )
            resp.raise_for_status()
            due_reviews = resp.json().get("reviews", [])
    except Exception:
        logger.warning("Could not fetch due reviews for agenda")

    proposals: list[dict] = []
    try:
        proposals = loomio_list_proposals(group_key=circle_key)
    except Exception:
        logger.warning("Could not fetch proposals for agenda")

    recent_decisions: list[dict] = []
    try:
        recent_decisions = list_recent_decisions(group_key=circle_key, limit=3)
    except Exception:
        logger.warning("Could not fetch recent decisions for agenda")

    today = _date.today().isoformat()

    lines = [
        f"## {meeting_type.title()} Meeting — {circle_key} — {today}",
        "",
        "### Check-in (10 min)",
        "",
        "### Administrative consent (5 min)",
        "- Approve previous minutes",
        "",
        "### Tensions to process",
    ]
    if tensions:
        for t in tensions:
            lines.append(f"- **#{t['id']}** {t['description']}")
    else:
        lines.append("_No open tensions logged for this circle._")

    lines += ["", "### Proposals for consent"]
    if proposals:
        for p in proposals:
            closing = p.get("closing_at", "")[:10]
            lines.append(f"- **{p['title']}** (closes {closing})")
    else:
        lines.append("_No open proposals._")

    lines += ["", "### Agreements due for review"]
    if due_reviews:
        for r in due_reviews:
            lines.append(f"- **{r['title']}** — review by {r['review_date']}")
    else:
        lines.append("_No agreements due for review in the next 14 days._")

    lines += ["", "### Recent decisions (context)"]
    if recent_decisions:
        for d in recent_decisions:
            decided = (d.get("decided_at") or "")[:10]
            lines.append(f"- {d['title']} ({decided})")
    else:
        lines.append("_No recent decisions recorded._")

    lines += ["", "### Any other business", "", "### Check-out (5 min)"]
    return "\n".join(lines)
```

Add to `TOOL_DEFINITIONS`:

```python
    {
        "name": "list_recent_decisions",
        "description": "List the most recent recorded cooperative decisions. Useful for meeting agenda context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_key": {"type": "string", "description": "Filter by Loomio group key (optional)"},
                "limit": {"type": "integer", "description": "Number of decisions to return (default 3, max 10)"},
            },
        },
    },
    {
        "name": "draft_meeting_notice",
        "description": "Format a Mattermost-ready meeting announcement. Local formatting only — no API call. To post it, ask the Clerk to use mattermost_post_message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "circle_key": {"type": "string", "description": "Loomio group key of the circle meeting"},
                "date": {"type": "string", "description": "Meeting date (YYYY-MM-DD)"},
                "facilitator": {"type": "string", "description": "Name of the facilitator"},
            },
            "required": ["circle_key", "date", "facilitator"],
        },
    },
    {
        "name": "prepare_meeting_agenda",
        "description": "Assemble a structured circle meeting agenda from live data — tensions, due reviews, open proposals, recent decisions. Returns markdown ready to share.",
        "input_schema": {
            "type": "object",
            "properties": {
                "circle_key": {"type": "string", "description": "Loomio group key identifying the circle"},
                "meeting_type": {"type": "string", "enum": ["circle", "agm", "board", "working_group"], "description": "Type of meeting (default: circle)"},
            },
            "required": ["circle_key"],
        },
    },
```

Add to `TOOL_REGISTRY`:

```python
    "list_recent_decisions": list_recent_decisions,
    "draft_meeting_notice": draft_meeting_notice,
    "prepare_meeting_agenda": prepare_meeting_agenda,
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest agents/clerk/tests/test_meeting_tools.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/IskanderOS/openclaw/agents/clerk/tools.py \
        src/IskanderOS/openclaw/agents/clerk/tests/test_meeting_tools.py
git commit -m "feat(clerk): meeting prep tools — prepare_meeting_agenda, draft_meeting_notice, list_recent_decisions"
```

---

### Task 2.2: SOUL.md meeting facilitation section

**Files:**
- Modify: `src/IskanderOS/openclaw/agents/clerk/SOUL.md`

- [ ] **Step 1: Add meeting facilitation section to SOUL.md**

Add after the "S3 governance facilitation" section:

```markdown
## Meeting facilitation

You help facilitators prepare — you do not chair meetings. A meeting is a member's space, not yours.

### Preparing an agenda
When asked to prepare an agenda for a circle meeting:
1. Ask for the `circle_key` (the Loomio group key) if not provided
2. Call `prepare_meeting_agenda` — it assembles live data from tensions, due reviews, proposals, and recent decisions
3. Present the agenda and offer to post it (using `mattermost_post_message`, which requires Glass Box)
4. Remind the facilitator: tensions without driver statements are harder to resolve — offer to help draft them

### Role rotation
If you are asked about facilitation roles and you have information about recent meeting history, note if the same person has facilitated the last 3 or more meetings. Suggest rotation — S3 encourages role diversity.

### Quorum
Consent decisions require participation from the whole circle. If a member asks about quorum, explain that in S3 consent governance, quorum is typically all members of the circle who are available — not a fixed number. A decision with absent members may need to be re-opened if those members object when they return.

### Meeting types
- **Circle:** regular governance meeting for a circle — tensions, proposals, reviews
- **AGM:** annual general meeting — accounts, elections, strategic direction
- **Board:** board-only session
- **Working group:** time-limited group with a specific mandate

### You must never
- Record meeting minutes as a formal document without a member reviewing and approving them
- Claim a decision was made that has not been recorded in Loomio
```

- [ ] **Step 2: Commit**

```bash
git add src/IskanderOS/openclaw/agents/clerk/SOUL.md
git commit -m "docs(clerk): meeting facilitation guidance in SOUL.md"
```

---

### Task 2.3: Documentation and templates

**Files:**
- Create: `docs/operations/meeting-prep.md`
- Create: `docs/templates/governance/meeting-agenda.md`

- [ ] **Step 1: Create `docs/operations/meeting-prep.md`**

```markdown
# Meeting Preparation — Facilitator Guide

The Clerk can assemble a structured meeting agenda on request, drawing live data
from the tension tracker, agreement review schedule, open Loomio proposals, and
recorded decision history.

## Requesting an agenda

In Mattermost, message the Clerk:

> "Prepare the agenda for the governance circle meeting on 2026-04-15"

The Clerk will:
1. Fetch open tensions for the circle
2. Check agreements due for review in the next 14 days
3. List open proposals closing in the next 7 days
4. Pull the 3 most recent decisions for context
5. Return a formatted markdown agenda

## Posting the agenda

After reviewing the agenda, ask the Clerk to post it to a channel:

> "Post that agenda to the #governance channel"

The Clerk will confirm before posting (Glass Box logged).

## Meeting types

| Type | Use for |
|------|---------|
| `circle` | Regular governance meeting |
| `agm` | Annual general meeting |
| `board` | Board-only session |
| `working_group` | Time-limited group with specific mandate |

## Meeting notice

To draft a meeting announcement:

> "Draft a meeting notice for the governance circle meeting on 2026-04-15, facilitated by Alice"

Returns a formatted Mattermost message ready to post.

## Role rotation

S3 encourages facilitator rotation. The Clerk will note if the same person has
facilitated the last 3 or more meetings and suggest rotation.
```

- [ ] **Step 2: Create `docs/templates/governance/meeting-agenda.md`**

```markdown
# Circle Meeting Agenda Template

Use this as a reference. The Clerk generates this automatically via `prepare_meeting_agenda`.

---

## [Meeting type] Meeting — [Circle name] — [Date]

**Facilitator:** [Name]  
**Note-taker:** [Name]  
**Members present:** [List]  
**Apologies:** [List]  

---

### Check-in (10 min)

_Each person shares one word or sentence about how they're arriving._

---

### Administrative consent (5 min)

- [ ] Approve previous minutes
- [ ] Any corrections to the record?

---

### Tensions to process

_Each tension is heard, driver statement clarified if needed, and either resolved or moved to a proposal._

1. [Tension description — logged by member]
2. …

---

### Proposals for consent

_Each proposal is read. Members check for paramount objections. No objection = consent._

1. [Proposal title] — closes [date]
2. …

---

### Agreements due for review

_Agreements past their review date. Circle decides: extend, amend, or drop._

1. [Agreement title] — due [date]
2. …

---

### Any other business

---

### Check-out (5 min)

_Each person shares one word or sentence about how they're leaving._

---

_Minutes recorded by: [name] | Next meeting: [date]_
```

- [ ] **Step 3: Commit**

```bash
git add docs/operations/meeting-prep.md docs/templates/governance/meeting-agenda.md
git commit -m "docs: meeting prep facilitator guide + agenda template"
```

---

### Task 2.4: Open PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feature/meeting-prep-clerk
gh pr create \
  --title "feat(#47): meeting prep Clerk tools — agenda assembly, meeting notice, recent decisions" \
  --body "Closes #47. Three new read-only Clerk tools + SOUL.md meeting facilitation guidance + facilitator guide + agenda template. See #53."
```

- [ ] **Step 2: Comment on tracking issue**

```bash
gh issue comment 53 --body "Session 2375b4e8: feature/meeting-prep-clerk PR opened."
```

---

## Chunk 3: feature/e2e-verification (C.10)

**Prerequisite:** Chunks 1 and 2 merged. All services deployed and healthy.

**Files:**
| File | Action | Responsibility |
|------|--------|---------------|
| `verify/verify.sh` | Create | End-to-end smoke test script (Tier 1: infra, Tier 2: health, Tier 3: journey) |
| `verify/generate-ci-secrets.sh` | Create | Generate deterministic CI-safe secrets for K3d |
| `verify/values-ci.yaml` | Create | Minimal Helm overrides for CI |
| `verify/README.md` | Create | Quick reference for contributors |
| `.github/workflows/verify.yml` | Create | GitHub Actions CI workflow |
| `docs/operations/verification.md` | Create | Operator guide for Debian VM verification |

---

### Task 3.1: Core verification script

**Files:**
- Create: `verify/verify.sh`

- [ ] **Step 1: Create the directory and stub**

```bash
mkdir -p verify
```

- [ ] **Step 2: Create `verify/verify.sh`**

```bash
#!/usr/bin/env bash
# Iskander end-to-end verification script
# Usage: ISKANDER_HOST=<host> bash verify/verify.sh
# Exit codes: 0=all pass, 1=infra fail, 2=service fail, 3=journey fail
set -euo pipefail

HOST="${ISKANDER_HOST:-localhost}"
NAMESPACE="${ISKANDER_NAMESPACE:-iskander}"
UUID="verify-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
PASS=0
FAIL=0

log_pass() { echo "::notice::✅ $1"; PASS=$((PASS + 1)); }
log_fail() { echo "::error::❌ $1"; FAIL=$((FAIL + 1)); }
log_info() { echo "ℹ️  $1"; }

# ---------------------------------------------------------------------------
# Tier 1 — Infrastructure
# ---------------------------------------------------------------------------
log_info "=== Tier 1: Infrastructure ==="

# K3s node ready
if kubectl get nodes --no-headers 2>/dev/null | grep -q " Ready"; then
  log_pass "K3s node Ready"
else
  log_fail "K3s node not Ready"
  echo "::error::Infrastructure not ready — aborting"
  exit 1
fi

# All expected pods running (no CrashLoopBackOff)
CRASH_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null \
  | grep -E "CrashLoopBackOff|Error|Pending" | awk '{print $1}') || true
if [[ -z "$CRASH_PODS" ]]; then
  log_pass "No CrashLoopBackOff pods"
else
  log_fail "Unhealthy pods: $CRASH_PODS"
  exit 1
fi

EXPECTED_DEPLOYMENTS="authentik loomio mattermost nextcloud postgresql redis ipfs decision-recorder openclaw provisioner"
for dep in $EXPECTED_DEPLOYMENTS; do
  if kubectl get deployment "$dep" -n "$NAMESPACE" &>/dev/null; then
    log_pass "Deployment $dep exists"
  else
    log_fail "Deployment $dep missing"
  fi
done

# ---------------------------------------------------------------------------
# Tier 2 — Service health
# ---------------------------------------------------------------------------
log_info "=== Tier 2: Service health ==="

check_health() {
  local name="$1" url="$2"
  if curl -sf --max-time 10 "$url" > /dev/null; then
    log_pass "$name health OK"
  else
    log_fail "$name health FAILED ($url)"
  fi
}

BASE="http://${HOST}"
check_health "decision-recorder" "${BASE}:3000/health"
check_health "openclaw"          "${BASE}:8080/health"
check_health "provisioner"       "${BASE}:3001/health"
check_health "authentik"         "${BASE}/api/v3/-/"
check_health "mattermost"        "${BASE}:8065/api/v4/system/ping"
check_health "nextcloud"         "${BASE}/nextcloud/status.php"
check_health "ipfs"              "${BASE}:5001/api/v0/id"
# Loomio: authenticated ping (spec: GET /api/v1/groups)
LOOMIO_API_KEY="${LOOMIO_API_KEY:-}"
if [[ -n "$LOOMIO_API_KEY" ]]; then
  if curl -sf --max-time 10 -H "Authorization: Token ${LOOMIO_API_KEY}" "${BASE}/api/v1/groups" > /dev/null; then
    log_pass "loomio health OK"
  else
    log_fail "loomio health FAILED"
  fi
else
  log_info "LOOMIO_API_KEY not set — skipping Loomio authenticated health check"
fi

if [[ $FAIL -gt 0 ]]; then
  echo "::error::${FAIL} service(s) unhealthy — Tier 2 FAILED"
  exit 2
fi

# ---------------------------------------------------------------------------
# Tier 3 — Journey smoke test
# ---------------------------------------------------------------------------
log_info "=== Tier 3: Journey smoke test (UUID: ${UUID}) ==="

PROVISIONER_URL="${BASE}:3001"
DR_URL="${BASE}:3000"
LOOMIO_WEBHOOK_SECRET="${LOOMIO_WEBHOOK_SECRET:-changeme}"

cleanup() {
  log_info "Cleaning up test resources (${UUID})..."
  # In CI the entire K3d cluster is torn down — cleanup here handles Debian VM runs.
  # The provisioner has no DELETE endpoint; we call Authentik admin API directly.
  # Loomio membership is cascade-deleted when the Authentik user is removed.
  AUTHENTIK_URL="${AUTHENTIK_URL:-http://authentik:9000}"
  AUTHENTIK_TOKEN="${AUTHENTIK_TOKEN:-}"
  if [[ -n "$AUTHENTIK_TOKEN" ]]; then
    AUTHENTIK_USER_ID=$(curl -sf \
      -H "Authorization: Bearer ${AUTHENTIK_TOKEN}" \
      "${AUTHENTIK_URL}/api/v3/core/users/?username=${UUID}" \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['results'][0]['pk'] if d.get('results') else '')" 2>/dev/null || echo "")
    if [[ -n "$AUTHENTIK_USER_ID" ]]; then
      curl -sf -X DELETE \
        -H "Authorization: Bearer ${AUTHENTIK_TOKEN}" \
        "${AUTHENTIK_URL}/api/v3/core/users/${AUTHENTIK_USER_ID}/" 2>/dev/null || true
      log_info "Deleted Authentik user ${UUID} (pk=${AUTHENTIK_USER_ID})"
    fi
  else
    log_info "AUTHENTIK_TOKEN not set — skipping user cleanup (safe in CI where cluster is torn down)"
  fi
}
trap cleanup EXIT

# Step 1: Provision test member
log_info "Step 1: Provision test member ${UUID}"
PROVISION_RESP=$(curl -sf -X POST "${PROVISIONER_URL}/members" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"${UUID}\", \"email\": \"${UUID}@verify.test\", \"display_name\": \"Verify Test\"}")
if echo "$PROVISION_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('authentik_id')" 2>/dev/null; then
  log_pass "Member provisioned"
else
  log_fail "Member provisioning failed: $PROVISION_RESP"
fi

# Step 2: Check provisioning status
STATUS_RESP=$(curl -sf "${PROVISIONER_URL}/members/${UUID}")
LOOMIO_MEMBER=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('loomio_member', False))")
if [[ "$LOOMIO_MEMBER" == "True" ]]; then
  log_pass "Loomio membership confirmed via provisioner status"
else
  log_fail "Loomio membership not confirmed: $STATUS_RESP"
fi

# Step 3: Glass Box write + read
log_info "Step 3: Glass Box write/read"
GB_RESP=$(curl -sf -X POST "${DR_URL}/log" \
  -H "Content-Type: application/json" \
  -d "{\"actor\": \"${UUID}\", \"agent\": \"verify\", \"action\": \"smoke-test\", \"target\": \"verify-target\", \"reasoning\": \"e2e verification run\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}")
ENTRY_ID=$(echo "$GB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")
if [[ -n "$ENTRY_ID" ]]; then
  log_pass "Glass Box entry created (id=${ENTRY_ID})"
  # Verify readable and action field matches what we wrote
  READ_RESP=$(curl -sf "${DR_URL}/log?actor=${UUID}&limit=1")
  ENTRY_COUNT=$(echo "$READ_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total', 0))")
  ENTRY_ACTION=$(echo "$READ_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['entries'][0]['action'] if d.get('entries') else '')" 2>/dev/null || echo "")
  if [[ "$ENTRY_COUNT" -gt 0 && "$ENTRY_ACTION" == "smoke-test" ]]; then
    log_pass "Glass Box entry readable (action=smoke-test confirmed)"
  elif [[ "$ENTRY_COUNT" -gt 0 ]]; then
    log_fail "Glass Box entry readable but action field mismatch: got '${ENTRY_ACTION}', expected 'smoke-test'"
  else
    log_fail "Glass Box entry not readable after write"
  fi
else
  log_fail "Glass Box write failed: $GB_RESP"
fi

# Step 4: Decision recording (mock Loomio webhook)
log_info "Step 4: Decision recording via Loomio webhook"
PAYLOAD="{\"poll\": {\"id\": 99999, \"title\": \"${UUID} verify decision\", \"key\": \"verify-key\", \"status\": \"closed\", \"closed_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"stance_counts\": {\"agree\": 3}, \"group\": {\"key\": \"verify\"}}, \"outcome\": {\"statement\": \"Verified by ${UUID}\"}}"
SIG="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$LOOMIO_WEBHOOK_SECRET" | awk '{print $2}')"
WEBHOOK_RESP=$(curl -sf -X POST "${DR_URL}/webhook/loomio" \
  -H "Content-Type: application/json" \
  -H "X-Loomio-Signature: ${SIG}" \
  -d "$PAYLOAD")
DECISION_ID=$(echo "$WEBHOOK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('decision_id',''))" 2>/dev/null || echo "")
if [[ -n "$DECISION_ID" ]]; then
  log_pass "Decision recorded (id=${DECISION_ID})"
else
  log_fail "Decision webhook failed: $WEBHOOK_RESP"
fi

# Step 5: Clerk reachability
log_info "Step 5: Clerk (openclaw) reachability"
CLERK_RESP=$(curl -sf --max-time 15 -X POST "${BASE}:8080/webhook/mattermost" \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"${MATTERMOST_WEBHOOK_TOKEN:-verify-token}\", \"user_id\": \"${UUID}\", \"user_name\": \"verify\", \"text\": \"hello\", \"channel_id\": \"verify\"}" \
  2>/dev/null || echo "")
if [[ -n "$CLERK_RESP" ]]; then
  log_pass "Clerk responded to test message"
else
  log_fail "Clerk did not respond"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==================================="
echo "  VERIFICATION SUMMARY"
echo "  Passed: ${PASS}  Failed: ${FAIL}"
echo "==================================="

if [[ $FAIL -gt 0 ]]; then
  exit 3
fi
exit 0
```

- [ ] **Step 2: Make executable and smoke-test the script syntax**

```bash
chmod +x verify/verify.sh
bash -n verify/verify.sh
```
Expected: no syntax errors

- [ ] **Step 3: Commit**

```bash
git add verify/verify.sh
git commit -m "feat(verify): verify.sh — 3-tier smoke test (infra, health, journey)"
```

---

### Task 3.2: CI secrets generator and CI values

**Files:**
- Create: `verify/generate-ci-secrets.sh`
- Create: `verify/values-ci.yaml`

- [ ] **Step 1: Create `verify/generate-ci-secrets.sh`**

```bash
#!/usr/bin/env bash
# Generate deterministic-but-safe secrets for CI K3d runs.
# These are NOT production secrets. Never use these values outside CI.
set -euo pipefail

cat <<'EOF'
# AUTO-GENERATED CI SECRETS — NOT FOR PRODUCTION
# Generated by verify/generate-ci-secrets.sh

global:
  cooperative:
    name: "CI Cooperative"
    domain: "localhost"
  postgresql:
    auth:
      postgresPassword: "ci-postgres-pass"
      username: "iskander"
      password: "ci-iskander-pass"
  redis:
    auth:
      password: "ci-redis-pass"
EOF
```

- [ ] **Step 2: Create `verify/values-ci.yaml`**

```yaml
# CI Helm overrides — minimal resources, in-cluster services, CI-safe credentials.
# NOT for production. These values are committed — they contain no real secrets.

global:
  cooperative:
    name: "CI Cooperative"
    domain: "localhost"
  storageClass: "local-path"
  imagePullPolicy: IfNotPresent

postgresql:
  auth:
    postgresPassword: "ci-postgres-pass"
    username: "iskander"
    password: "ci-iskander-pass"
  primary:
    resources:
      requests: { memory: "128Mi", cpu: "50m" }
      limits: { memory: "256Mi", cpu: "200m" }

redis:
  auth:
    password: "ci-redis-pass"
  master:
    resources:
      requests: { memory: "32Mi", cpu: "20m" }
      limits: { memory: "64Mi", cpu: "100m" }

loomio:
  webhookSecret: "ci-loomio-secret"
  enabled: true

openclaw:
  enabled: true
  # ANTHROPIC_API_KEY is injected via GitHub Actions secret at deploy time

decisionRecorder:
  enabled: true
  postgresql:
    password: "ci-dr-pass"
  internalServiceToken: ""

provisioner:
  enabled: true
  loomioDefaultGroupKey: "ci-coop"
  welcomeChannelId: "ci-channel"
  postgresql:
    password: "ci-provisioner-pass"
```

- [ ] **Step 3: Commit**

```bash
git add verify/generate-ci-secrets.sh verify/values-ci.yaml
chmod +x verify/generate-ci-secrets.sh
git commit -m "feat(verify): CI secrets generator + values-ci.yaml"
```

---

### Task 3.3: GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/verify.yml`

- [ ] **Step 1: Create `.github/workflows/verify.yml`**

```yaml
name: End-to-end verification

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - name: Install K3d
        run: |
          curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
          k3d version

      - name: Install kubectl
        uses: azure/setup-kubectl@v4

      - name: Install Helm
        uses: azure/setup-helm@v3

      - name: Create K3d cluster
        run: |
          k3d cluster create iskander-ci \
            --agents 1 \
            --wait \
            --timeout 120s

      - name: Install Iskander chart
        run: |
          helm upgrade --install iskander ./infra/helm/iskander \
            -f verify/values-ci.yaml \
            --set openclaw.anthropicApiKey="${{ secrets.ANTHROPIC_API_KEY }}" \
            --namespace iskander \
            --create-namespace \
            --wait \
            --timeout 300s

      - name: Wait for all pods
        run: |
          kubectl wait --for=condition=ready pod \
            --all -n iskander \
            --timeout=300s

      - name: Run verification
        env:
          ISKANDER_HOST: localhost
          ISKANDER_NAMESPACE: iskander
          LOOMIO_WEBHOOK_SECRET: ci-loomio-secret
          MATTERMOST_WEBHOOK_TOKEN: ci-mm-token
          AUTHENTIK_TOKEN: ${{ secrets.CI_AUTHENTIK_TOKEN }}
        run: |
          bash verify/verify.sh 2>&1 | tee verify-output.log
          exit ${PIPESTATUS[0]}

      - name: Upload verification log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: verification-log-${{ github.run_id }}
          path: verify-output.log
          if-no-files-found: ignore

      - name: Delete K3d cluster
        if: always()
        run: k3d cluster delete iskander-ci
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/verify.yml
git commit -m "feat(ci): GitHub Actions verify workflow — K3d + Helm + verify.sh on every PR"
```

---

### Task 3.4: Documentation

**Files:**
- Create: `docs/operations/verification.md`
- Create: `verify/README.md`

- [ ] **Step 1: Create `docs/operations/verification.md`**

```markdown
# Verification — Operator Guide

`verify.sh` runs a three-tier smoke test against a live Iskander deployment.
It is the primary tool for validating a Debian VM installation.

## Running against your Debian VM

```bash
export ISKANDER_HOST=<your-vm-ip-or-hostname>
export ISKANDER_NAMESPACE=iskander
export LOOMIO_WEBHOOK_SECRET=<from your generated-values.yaml>
bash verify/verify.sh
```

## Exit codes

| Code | Meaning | First action |
|------|---------|-------------|
| 0 | All tiers passed | — |
| 1 | Infrastructure not ready | Check `kubectl get pods -n iskander` |
| 2 | One or more services unhealthy | Check that pod's logs: `kubectl logs -n iskander <pod>` |
| 3 | Journey smoke test failed | Check decision-recorder and provisioner logs |

## What each tier checks

### Tier 1 — Infrastructure
- K3s node in `Ready` state
- No pods in `CrashLoopBackOff`, `Error`, or long-`Pending`
- All expected Deployments present

### Tier 2 — Service health
Calls `/health` (or equivalent) on every service:
decision-recorder, openclaw, provisioner, authentik, mattermost, nextcloud, IPFS

### Tier 3 — Journey smoke test
1. Provisions a test member via the provisioner
2. Confirms Loomio membership
3. Writes and reads a Glass Box entry
4. Sends a signed mock webhook to the decision recorder
5. Tests Clerk reachability

All test resources are prefixed `verify-{UUID}` and cleaned up on exit.
```

- [ ] **Step 2: Create `verify/README.md`**

```markdown
# verify/

End-to-end verification for Iskander.

## Files

| File | Purpose |
|------|---------|
| `verify.sh` | Main smoke test script |
| `values-ci.yaml` | Helm overrides for K3d CI runs |
| `generate-ci-secrets.sh` | Print CI-safe secret values |

## Quick start

```bash
# Against a Debian VM:
ISKANDER_HOST=<ip> LOOMIO_WEBHOOK_SECRET=<secret> bash verify/verify.sh

# In CI (handled by .github/workflows/verify.yml automatically)
```

## Exit codes: 0=pass, 1=infra, 2=service, 3=journey
```

- [ ] **Step 3: Commit**

```bash
git add docs/operations/verification.md verify/README.md
git commit -m "docs: verification operator guide + verify/README.md"
```

---

### Task 3.5: Open PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feature/e2e-verification
gh pr create \
  --title "feat(C.10): end-to-end verification — verify.sh + GitHub Actions CI" \
  --body "Closes C.10. Three-tier smoke test targeting Debian VM + K3d CI workflow. See #53."
```

- [ ] **Step 2: Comment on tracking issue and close it**

```bash
gh issue comment 53 --body "Session 2375b4e8: All three PRs open. Phase C complete pending merges: membership-provisioning, meeting-prep-clerk, e2e-verification."
```

---

## Final checklist

- [ ] PR #49 (S3 governance) merged before starting any chunk
- [ ] Chunk 1 PR reviewed and merged
- [ ] Chunk 2 PR reviewed and merged  
- [ ] Chunk 3 PR reviewed and merged
- [ ] `verify.sh` runs green against the Debian VM
- [ ] GitHub Actions CI passing on `main`
- [ ] Issue #47 closed by Chunk 2 PR
- [ ] Issue #53 closed
