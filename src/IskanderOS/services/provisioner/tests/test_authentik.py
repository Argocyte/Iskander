"""
Tests for the Authentik admin client (provisioner/authentik.py).

Uses unittest.mock.patch to intercept httpx.Client.post — no real HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Ensure env vars are present before the module is imported
os.environ.setdefault("AUTHENTIK_URL", "https://auth.example.coop")
os.environ.setdefault("AUTHENTIK_API_TOKEN", "test-token")

from provisioner import authentik  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _error_response(status_code: int) -> MagicMock:
    """Build a mock that raises HTTPStatusError when raise_for_status() is called."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=MagicMock(status_code=status_code),
    )
    return resp


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    def test_create_user_returns_authentik_id(self):
        """A successful API call should return {'authentik_id': '<pk>'}."""
        mock_resp = _mock_response({"pk": "abc-123", "username": "alice"})

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            result = authentik.create_user(
                username="alice",
                email="alice@example.coop",
                display_name="Alice",
            )

        assert result == {"authentik_id": "abc-123"}

    def test_create_user_raises_on_api_error(self):
        """A 400-level API error should propagate as httpx.HTTPStatusError."""
        mock_resp = _error_response(400)

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                authentik.create_user(
                    username="alice",
                    email="alice@example.coop",
                    display_name="Alice",
                )


# ---------------------------------------------------------------------------
# get_recovery_link
# ---------------------------------------------------------------------------

class TestGetRecoveryLink:
    def test_get_recovery_link_returns_link(self):
        """A successful call should return the 'link' string from the response."""
        recovery_url = "https://auth.example.coop/recovery/xyz"
        mock_resp = _mock_response({"link": recovery_url})

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            result = authentik.get_recovery_link("abc-123")

        assert result == recovery_url

    def test_get_recovery_link_raises_on_api_error(self):
        """A 404 API error should propagate as httpx.HTTPStatusError."""
        mock_resp = _error_response(404)

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                authentik.get_recovery_link("nonexistent-id")
