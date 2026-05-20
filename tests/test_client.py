"""Unit tests for OpenProjectClient — timeout propagation and env config."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def stub_env(monkeypatch):
    monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
    monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
    monkeypatch.delenv("OPENPROJECT_CONNECT_TIMEOUT", raising=False)
    monkeypatch.delenv("OPENPROJECT_READ_TIMEOUT", raising=False)


def _patch_session(client, response_payload=None):
    """Replace client.session with a MagicMock; return it for assertions."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = response_payload or {}
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response
    mock_session.post.return_value = mock_response
    mock_session.patch.return_value = mock_response
    mock_session.delete.return_value = mock_response
    client.session = mock_session
    return mock_session


class TestDefaultTimeout:
    def test_default_timeout_is_10s_connect_60s_read(self, stub_env):
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        assert c.timeout == (10.0, 60.0)

    def test_env_overrides_timeouts(self, stub_env, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_CONNECT_TIMEOUT", "5")
        monkeypatch.setenv("OPENPROJECT_READ_TIMEOUT", "30")
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        assert c.timeout == (5.0, 30.0)


class TestTimeoutPassedToRequests:
    def test_get_passes_timeout(self, stub_env):
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        session = _patch_session(c)
        c.get("foo")
        assert session.get.call_args.kwargs["timeout"] == c.timeout

    def test_post_passes_timeout(self, stub_env):
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        session = _patch_session(c)
        c.post("foo", {})
        assert session.post.call_args.kwargs["timeout"] == c.timeout

    def test_patch_passes_timeout(self, stub_env):
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        session = _patch_session(c)
        c.patch("foo", {})
        assert session.patch.call_args.kwargs["timeout"] == c.timeout

    def test_delete_passes_timeout(self, stub_env):
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        session = _patch_session(c)
        c.delete("foo")
        assert session.delete.call_args.kwargs["timeout"] == c.timeout

    def test_get_raw_passes_timeout(self, stub_env):
        from openproject_mcp.client import OpenProjectClient
        c = OpenProjectClient()
        session = _patch_session(c)
        c.get_raw("foo")
        assert session.get.call_args.kwargs["timeout"] == c.timeout
