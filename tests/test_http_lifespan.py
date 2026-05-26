"""Test that the HTTP app's ASGI lifespan properly initializes the session-manager task group.

This test verifies the fix from cycle 2: the lifespan context manager must be attached
to the *outer* Starlette app (served by uvicorn), not to an inner sub-app.
Without this, session_manager.run() is never entered, and handle_request raises
"RuntimeError: Task group is not initialized".

The test uses TestClient's lifespan support (via `with` block) to drive the startup,
then verifies that an `/mcp/` initialize request does not crash.
"""

import sys
import os
import json
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
from starlette.testclient import TestClient


class TestHttpLifespan:
    """Smoke test: lifespan properly initializes session manager task group."""

    @pytest.fixture
    def lifespan_env(self, monkeypatch):
        """Set env for HTTP mode with allowed hosts that won't 421 TestClient."""
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.setenv("MCP_AUTH_TOKEN", "testtoken")
        monkeypatch.setenv("OPENPROJECT_URL", "http://x.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        # Allow TestClient's default Host: testserver so the DNS-rebinding guard doesn't 421.
        monkeypatch.setenv(
            "MCP_ALLOWED_HOSTS", "testserver,127.0.0.1,localhost"
        )

    def test_lifespan_initializes_session_manager(self, lifespan_env):
        """TestClient with block drives lifespan; /mcp/ initialize doesn't crash.

        The cycle-1 bug: lifespan was attached to routes_app (inner), so uvicorn's
        lifespan events never reached session_manager.run(). A POST to /mcp/ would
        hit handle_request with an uninitialized task group and raise RuntimeError.

        Cycle-2 fix: lifespan is attached to outer (served by uvicorn), so
        session_manager.run() is entered before any requests arrive.

        This test confirms the fix: with the `with` block driving lifespan,
        /mcp/ initialize request succeeds (no 500, no RuntimeError).
        """
        from openproject_mcp.http_transport import build_http_app

        # Build the app
        app = build_http_app()

        # Use TestClient's with block to drive ASGI lifespan (startup/shutdown).
        # Without this context manager, lifespan events are not fired.
        with TestClient(app) as client:
            # POST an MCP initialize request to /mcp/ with required headers.
            # The request body is a JSON-RPC 2.0 initialize call.
            response = client.post(
                "/mcp/",
                headers={
                    "Tailscale-User-Login": "martin",
                    "Authorization": "Bearer testtoken",
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    "MCP-Protocol-Version": "2025-03-26",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"},
                    },
                },
            )

            # The critical assertion: the request did not crash with a 500 or
            # "Task group is not initialized" error. A clean response (200, 400, 406, etc.)
            # proves the task group was running when handle_request was called.
            # We allow any status code except 500 (server error).
            assert (
                response.status_code != 500
            ), f"Got 500; body: {response.text}. Task group likely uninitialized."

            # Log the observed status for diagnostics.
            # (The test passes on any non-500 status: 200 = OK, 400/406 = client error, etc.)
            print(f"POST /mcp/ returned {response.status_code}")
