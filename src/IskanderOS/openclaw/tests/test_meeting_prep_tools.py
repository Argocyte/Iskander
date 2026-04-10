"""
Tests for meeting prep tools: list_recent_decisions, list_due_reviews,
list_tensions, prepare_meeting_agenda.

TDD sprint — Task 2.1
"""
import os

# Set required env vars before any imports from the agents package
os.environ.setdefault("LOOMIO_URL", "https://loomio.example.coop")
os.environ.setdefault("LOOMIO_API_KEY", "test-key")
os.environ.setdefault("MATTERMOST_URL", "https://mm.example.coop")
os.environ.setdefault("MATTERMOST_BOT_TOKEN", "test-bot")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic")

from unittest.mock import MagicMock, patch

import pytest

import agents.clerk.tools as tools
import agents.clerk.agent as agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# list_recent_decisions
# ---------------------------------------------------------------------------

class TestListRecentDecisions:
    def test_calls_glass_box_decisions_endpoint(self):
        """Verify the URL contains /decisions and the decisions list is returned."""
        mock_decisions = [
            {
                "id": 1,
                "title": "Adopt new financial policy",
                "status": "closed",
                "outcome": "Approved by consensus",
                "ipfs_cid": "QmABC",
                "loomio_url": "https://loomio.example.coop/p/abc",
                "decided_at": "2026-03-01T12:00:00+00:00",
                "recorded_at": "2026-03-01T12:05:00+00:00",
            }
        ]
        mock_json = {"total": 1, "decisions": mock_decisions}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            result = tools.list_recent_decisions()

        # URL must contain /decisions
        call_args = mock_client.get.call_args
        assert "/decisions" in call_args[0][0]
        # Returns the decisions list directly
        assert result == mock_decisions

    def test_passes_group_key_param(self):
        """group_key must be passed as a query param when provided."""
        mock_json = {"total": 0, "decisions": []}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            tools.list_recent_decisions(group_key="my-coop", limit=5)

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("group_key") == "my-coop"
        assert params.get("limit") == 5

    def test_omits_group_key_when_none(self):
        """group_key must NOT appear in params when it is None."""
        mock_json = {"total": 0, "decisions": []}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            tools.list_recent_decisions()

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert "group_key" not in params


# ---------------------------------------------------------------------------
# list_due_reviews
# ---------------------------------------------------------------------------

class TestListDueReviews:
    def test_returns_reviews_list(self):
        """Returns the reviews list from the JSON response."""
        mock_reviews = [
            {
                "id": 2,
                "title": "Data retention policy",
                "outcome": "Retain for 2 years",
                "review_due_at": "2026-04-15",
            }
        ]
        mock_json = {"count": 1, "reviews": mock_reviews}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            result = tools.list_due_reviews()

        assert result == mock_reviews

    def test_calls_reviews_due_endpoint(self):
        """URL must contain /decisions/reviews/due."""
        mock_json = {"count": 0, "reviews": []}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            tools.list_due_reviews()

        call_url = mock_client.get.call_args[0][0]
        assert "/decisions/reviews/due" in call_url


# ---------------------------------------------------------------------------
# list_tensions
# ---------------------------------------------------------------------------

class TestListTensions:
    def test_returns_tensions_list(self):
        """Returns the tensions list from the JSON response."""
        mock_tensions = [
            {
                "id": 3,
                "title": "Lack of onboarding docs",
                "driver": "New members struggle to find documentation",
                "status": "open",
                "created_at": "2026-03-20T08:00:00+00:00",
            }
        ]
        mock_json = {"total": 1, "tensions": mock_tensions}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            result = tools.list_tensions(limit=10)

        assert result == mock_tensions

    def test_passes_limit_param(self):
        """limit param must be forwarded to the API."""
        mock_json = {"total": 0, "tensions": []}

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _mock_response(mock_json)

            tools.list_tensions(limit=7)

        call_kwargs = mock_client.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("limit") == 7


# ---------------------------------------------------------------------------
# prepare_meeting_agenda
# ---------------------------------------------------------------------------

class TestPrepareMeetingAgenda:
    def _patch_all(self, decisions=None, reviews=None, tensions=None):
        """Return a context manager that patches all three helper functions."""
        decisions = decisions or []
        reviews = reviews or []
        tensions = tensions or []
        return (
            patch.object(tools, "list_recent_decisions", return_value=decisions),
            patch.object(tools, "list_due_reviews", return_value=reviews),
            patch.object(tools, "list_tensions", return_value=tensions),
        )

    def test_returns_markdown_with_expected_sections(self):
        """Agenda must contain the four expected headings."""
        decisions = [
            {
                "id": 1,
                "title": "Policy change",
                "status": "closed",
                "decided_at": "2026-03-01",
                "recorded_at": "2026-03-01",
            }
        ]
        reviews = [
            {"id": 2, "title": "Data retention", "outcome": "ok", "review_due_at": "2026-04-15"}
        ]
        tensions = [
            {"id": 3, "title": "Onboarding", "driver": "Members need docs", "status": "open", "created_at": "2026-03-20"}
        ]

        p_decisions, p_reviews, p_tensions = self._patch_all(decisions, reviews, tensions)
        with p_decisions, p_reviews, p_tensions:
            result = tools.prepare_meeting_agenda()

        assert "Meeting Agenda" in result
        assert "Agreements due for review" in result
        assert "Open tensions" in result
        assert "Recent decisions" in result

    def test_empty_state_shows_placeholder_messages(self):
        """When all lists are empty, appropriate 'none' messages must appear."""
        p_decisions, p_reviews, p_tensions = self._patch_all()
        with p_decisions, p_reviews, p_tensions:
            result = tools.prepare_meeting_agenda()

        assert "No agreements are due" in result
        assert "No open tensions" in result

    def test_group_key_forwarded_to_decisions(self):
        """group_key must be passed through to list_recent_decisions."""
        p_decisions, p_reviews, p_tensions = self._patch_all()
        with p_decisions as mock_d, p_reviews, p_tensions:
            tools.prepare_meeting_agenda(group_key="tech-circle")

        mock_d.assert_called_once_with(group_key="tech-circle", limit=5)


# ---------------------------------------------------------------------------
# Guard: new tools must NOT be write tools
# ---------------------------------------------------------------------------

class TestMeetingToolsNotInWriteTools:
    def test_none_of_the_new_tools_are_write_tools(self):
        new_tools = {
            "list_recent_decisions",
            "list_due_reviews",
            "list_tensions",
            "prepare_meeting_agenda",
        }
        intersection = new_tools & agent._WRITE_TOOLS
        assert intersection == set(), (
            f"These new tools must NOT be in _WRITE_TOOLS: {intersection}"
        )
