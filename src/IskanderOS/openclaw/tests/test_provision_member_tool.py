"""
Unit tests for the provision_member tool — Task 1.6 TDD sprint.

Tests:
  1. provision_member POSTs to the provisioner API correctly
  2. provision_member sends Authorization header when INTERNAL_SERVICE_TOKEN is set
  3. provision_member is in agent._WRITE_TOOLS
  4. _execute_tool does NOT inject actor_user_id into provision_member kwargs
"""
import os
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Required env vars before importing any Clerk modules
os.environ.setdefault("LOOMIO_URL", "https://loomio.example.coop")
os.environ.setdefault("LOOMIO_API_KEY", "test-key")
os.environ.setdefault("MATTERMOST_URL", "https://mm.example.coop")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-bot")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic")

import importlib
import sys


def _reload_tools_with_env(extra_env: dict | None = None):
    """Re-import tools module to pick up env var changes."""
    # Remove cached modules so env vars are re-read at module level
    for mod_name in list(sys.modules):
        if "openclaw.agents.clerk" in mod_name:
            del sys.modules[mod_name]

    if extra_env:
        for k, v in extra_env.items():
            os.environ[k] = v

    from src.IskanderOS.openclaw.agents.clerk import tools
    return tools


# ---------------------------------------------------------------------------
# Test 1 — provision_member calls the provisioner API with correct body
# ---------------------------------------------------------------------------

def test_provision_member_calls_provisioner_api():
    # Clear any leftover token
    os.environ.pop("INTERNAL_SERVICE_TOKEN", None)
    tools = _reload_tools_with_env()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "member_id": "abc123",
        "password_reset_url": "https://auth.example.coop/reset/abc123",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post = MagicMock(return_value=mock_response)

    with patch.object(tools, "_http_client", return_value=mock_client):
        result = tools.provision_member(
            username="alice",
            email="alice@example.coop",
            display_name="Alice Cooper",
        )

    mock_client.post.assert_called_once_with(
        "http://provisioner:3001/members",
        json={
            "username": "alice",
            "email": "alice@example.coop",
            "display_name": "Alice Cooper",
        },
        headers={},
    )
    assert result["member_id"] == "abc123"
    assert "password_reset_url" in result


# ---------------------------------------------------------------------------
# Test 2 — Authorization header is sent when INTERNAL_SERVICE_TOKEN is set
# ---------------------------------------------------------------------------

def test_provision_member_with_service_token():
    tools = _reload_tools_with_env({"INTERNAL_SERVICE_TOKEN": "test-secret"})

    mock_response = MagicMock()
    mock_response.json.return_value = {"member_id": "xyz789", "password_reset_url": "https://auth.example.coop/reset/xyz789"}
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post = MagicMock(return_value=mock_response)

    with patch.object(tools, "_http_client", return_value=mock_client):
        tools.provision_member(
            username="bob",
            email="bob@example.coop",
        )

    _, call_kwargs = mock_client.post.call_args
    assert call_kwargs["headers"] == {"Authorization": "Bearer test-secret"}

    # Clean up
    os.environ.pop("INTERNAL_SERVICE_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 3 — provision_member is in _WRITE_TOOLS
# ---------------------------------------------------------------------------

def test_provision_member_in_write_tools():
    # Clear cached modules so we get fresh imports
    for mod_name in list(sys.modules):
        if "openclaw.agents.clerk" in mod_name:
            del sys.modules[mod_name]

    from src.IskanderOS.openclaw.agents.clerk import agent
    assert "provision_member" in agent._WRITE_TOOLS


# ---------------------------------------------------------------------------
# Test 4 — _execute_tool does NOT inject actor_user_id into provision_member
# ---------------------------------------------------------------------------

def test_provision_member_not_in_actor_injection():
    """
    provision_member does not accept actor_user_id; passing it would cause TypeError.
    Verify _execute_tool does not inject it.
    """
    # Clear cached modules
    for mod_name in list(sys.modules):
        if "openclaw.agents.clerk" in mod_name:
            del sys.modules[mod_name]

    from src.IskanderOS.openclaw.agents.clerk import agent

    # Build a fake tool_use block
    block = SimpleNamespace(
        type="tool_use",
        name="provision_member",
        id="tu_test_001",
        input={
            "username": "carol",
            "email": "carol@example.coop",
        },
    )

    captured_kwargs = {}

    def fake_provision_member(**kwargs):
        captured_kwargs.update(kwargs)
        return {"member_id": "carol_id", "password_reset_url": "https://auth.example.coop/reset/carol"}

    with patch.dict(agent.TOOL_REGISTRY, {"provision_member": fake_provision_member}):
        result = agent._execute_tool(block, user_id="user_mattermost_123")

    assert "actor_user_id" not in captured_kwargs, (
        f"actor_user_id must NOT be injected into provision_member, "
        f"but got kwargs: {captured_kwargs}"
    )
    assert captured_kwargs["username"] == "carol"
    assert captured_kwargs["email"] == "carol@example.coop"
    # Result should be a valid tool_result dict
    assert result["type"] == "tool_result"
