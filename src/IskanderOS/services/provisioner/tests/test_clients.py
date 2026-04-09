"""
Tests for the Loomio and Mattermost HTTP clients (provisioner/loomio.py and
provisioner/mattermost.py).

Uses unittest.mock.patch to intercept httpx.Client — no real HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Ensure env vars are present before the modules are imported
os.environ.setdefault("LOOMIO_URL", "https://loomio.example.coop")
os.environ.setdefault("LOOMIO_API_KEY", "test-loomio-key")
os.environ.setdefault("MATTERMOST_URL", "https://chat.example.coop")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-bot-token")

from provisioner import loomio  # noqa: E402
from provisioner import mattermost  # noqa: E402


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
# Loomio tests
# ---------------------------------------------------------------------------

class TestLoomioAddMember:
    def test_loomio_add_member_returns_id(self):
        """A successful API call should return {'loomio_membership_id': 99}."""
        mock_resp = _mock_response({"memberships": [{"id": 99}]})

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            result = loomio.add_member(
                email="alice@example.coop",
                group_key="main-coop",
            )

        assert result == {"loomio_membership_id": 99}

    def test_loomio_add_member_raises_on_error(self):
        """A non-2xx response should propagate as httpx.HTTPStatusError."""
        mock_resp = _error_response(422)

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                loomio.add_member(
                    email="alice@example.coop",
                    group_key="main-coop",
                )


# ---------------------------------------------------------------------------
# Mattermost tests
# ---------------------------------------------------------------------------

class TestMattermostPostWelcome:
    def test_mattermost_post_welcome_returns_post_id(self):
        """A successful API call should return {'mattermost_post_id': 'post-xyz'}."""
        mock_resp = _mock_response({"id": "post-xyz"})

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            result = mattermost.post_welcome(
                username="alice",
                channel_id="onboarding-channel-id",
                display_name="Alice",
            )

        assert result == {"mattermost_post_id": "post-xyz"}

    def test_mattermost_post_welcome_raises_on_error(self):
        """A non-2xx response should propagate as httpx.HTTPStatusError."""
        mock_resp = _error_response(403)

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                mattermost.post_welcome(
                    username="alice",
                    channel_id="onboarding-channel-id",
                    display_name="Alice",
                )

    def test_mattermost_welcome_message_contains_username(self):
        """The message payload sent to the API must include the username."""
        mock_resp = _mock_response({"id": "post-abc"})

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value
            instance.post.return_value = mock_resp

            mattermost.post_welcome(
                username="bobsmith",
                channel_id="onboarding-channel-id",
                display_name="Bob Smith",
            )

            # Inspect the json kwarg passed to client.post
            call_kwargs = instance.post.call_args.kwargs
            assert "bobsmith" in call_kwargs["json"]["message"]
