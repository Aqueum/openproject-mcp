"""Streamable-HTTP transport for openproject-mcp.

Provides:
  resolve_transport()  — reads MCP_TRANSPORT, returns "stdio" or "http", raises ValueError.
  build_http_app()     — factory that returns a configured Starlette ASGI app.
  AuthMiddleware       — standalone ASGI middleware enforcing Tailscale-identity + bearer auth.

No env vars are read at module-import time (only inside the factory / middleware __init__).
"""

from __future__ import annotations

import contextlib
import concurrent.futures
import hmac
import os
from collections.abc import AsyncIterator

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send


# ---------------------------------------------------------------------------
# Transport resolver (AC1)
# ---------------------------------------------------------------------------

def resolve_transport() -> str:
    """Return the selected transport mode.

    Returns:
        "stdio" when MCP_TRANSPORT is unset or empty.
        "http"  when MCP_TRANSPORT=http.

    Raises:
        ValueError: for any other non-empty value.
    """
    val = os.environ.get("MCP_TRANSPORT", "").strip().lower()
    if val in ("", "stdio"):
        return "stdio"
    if val == "http":
        return "http"
    raise ValueError(
        f"Unknown MCP_TRANSPORT value {val!r}. Supported values: stdio, http."
    )


# ---------------------------------------------------------------------------
# Boolean env helper (matches existing _delete_enabled convention)
# ---------------------------------------------------------------------------

def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Auth middleware (AC5, AC6)
# ---------------------------------------------------------------------------

class AuthMiddleware:
    """ASGI middleware enforcing the auth decision order from the spec.

    Auth decision order:
      1. GET /healthz → pass immediately (no auth).
      2. Missing/empty Tailscale-User-Login → 401.
      3. MCP_ALLOWED_LOGINS non-empty and header not in the set → 403.
      4. MCP_AUTH_TOKEN set AND MCP_REQUIRE_BEARER true AND bearer
         absent or wrong (constant-time compare) → 403.
         Query-string-only token counts as "no bearer".
      5. Otherwise → pass through.

    Independently mountable: wrap any ASGI app for testing without SSE machinery.
    """

    def __init__(
        self,
        app: ASGIApp,
        auth_token: str | None = None,
        require_bearer: bool = True,
        allowed_logins: frozenset[str] = frozenset(),
    ) -> None:
        self.app = app
        self.auth_token = auth_token if auth_token else None  # normalise "" → None
        self.require_bearer = require_bearer
        self.allowed_logins = allowed_logins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Step 1: healthz bypass
        if scope.get("path") == "/healthz" and request.method == "GET":
            await self.app(scope, receive, send)
            return

        # Step 2: Tailscale identity required
        identity = request.headers.get("tailscale-user-login", "").strip()
        if not identity:
            response = JSONResponse({"error": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        # Step 3: Allowlist check (if configured)
        if self.allowed_logins and identity not in self.allowed_logins:
            response = JSONResponse({"error": "Forbidden"}, status_code=403)
            await response(scope, receive, send)
            return

        # Step 4: Bearer check — header-only; query-string tokens are rejected
        if self.auth_token and self.require_bearer:
            auth_header = request.headers.get("authorization", "")
            bearer = ""
            if auth_header.lower().startswith("bearer "):
                bearer = auth_header[7:].strip()
            if not bearer or not hmac.compare_digest(bearer, self.auth_token):
                response = JSONResponse({"error": "Forbidden"}, status_code=403)
                await response(scope, receive, send)
                return

        # Step 5: pass through
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# HTTP app factory (AC3, AC4, AC5, AC7, AC12)
# ---------------------------------------------------------------------------

def build_http_app() -> Starlette:
    """Construct and return a configured Starlette ASGI application.

    All env vars are read here (inside the factory) — never at module import.

    Raises:
        RuntimeError: if MCP_REQUIRE_BEARER is truthy and MCP_AUTH_TOKEN is unset/empty.
    """
    # Fail-closed check (AC4)
    require_bearer = _bool_env("MCP_REQUIRE_BEARER", default="true")
    auth_token = os.getenv("MCP_AUTH_TOKEN", "").strip() or None
    if require_bearer and not auth_token:
        raise RuntimeError(
            "MCP_REQUIRE_BEARER is enabled but MCP_AUTH_TOKEN is not set. "
            "Set MCP_AUTH_TOKEN to a secret bearer token, or set "
            "MCP_REQUIRE_BEARER=false to disable bearer enforcement."
        )

    # Parse env vars
    allowed_logins_raw = os.getenv("MCP_ALLOWED_LOGINS", "").strip()
    allowed_logins: frozenset[str] = (
        frozenset(x.strip() for x in allowed_logins_raw.split(",") if x.strip())
        if allowed_logins_raw
        else frozenset()
    )

    allowed_hosts_raw = os.getenv("MCP_ALLOWED_HOSTS", "127.0.0.1,localhost").strip()
    allowed_hosts = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]

    allowed_origins_raw = os.getenv(
        "MCP_ALLOWED_ORIGINS", "http://127.0.0.1,http://localhost"
    ).strip()
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

    max_workers = int(os.getenv("MCP_MAX_WORKERS", "8"))

    # Import here to avoid import-time side effects in the stdio path
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from mcp.server.transport_security import TransportSecuritySettings

    # Lazy import of the MCP server singleton (created at module level in server.py)
    from openproject_mcp.server import server as mcp_server

    security_settings = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        stateless=False,
        security_settings=security_settings,
        session_idle_timeout=1800,  # 30 min — mobile resilience
    )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    # /healthz route (AC7) — unauthenticated, no MCP data
    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # MCP endpoint — ASGI callable delegating to the session manager
    async def mcp_asgi(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    # Lifespan: run session manager task group inside the ASGI lifespan
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    # Inner routes app: healthz + MCP endpoint (no lifespan here — see below)
    routes_app = Starlette(
        routes=[
            Route("/healthz", endpoint=healthz, methods=["GET"]),
            Mount("/mcp", app=mcp_asgi),
        ],
    )

    # Auth middleware wraps the inner routes app
    auth_app = AuthMiddleware(
        routes_app,
        auth_token=auth_token,
        require_bearer=require_bearer,
        allowed_logins=allowed_logins,
    )

    # Return a Starlette instance that delegates all traffic to auth_app
    # and exposes state attributes the tests read.
    # lifespan is attached to *outer* (the app uvicorn actually serves) so that
    # uvicorn's lifespan events reach session_manager.run().  Starlette does NOT
    # propagate lifespan events through Mount to sub-apps, so attaching it only
    # to routes_app (as in cycle 1) meant session_manager.run() was never entered
    # and handle_request raised "Task group is not initialized".
    outer = Starlette(routes=[Mount("/", app=auth_app)], lifespan=lifespan)
    outer.state.security_settings = security_settings
    outer.state.executor = executor

    return outer
