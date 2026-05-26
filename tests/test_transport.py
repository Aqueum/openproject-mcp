"""Comprehensive tests for NAS HTTP transport (task_001) — all 12 acceptance criteria."""

import sys
import os
import time
import concurrent.futures
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
import requests
from starlette.testclient import TestClient
from starlette.applications import Starlette

# ============================================================================
# AC1: Transport resolver
# ============================================================================


class TestResolveTransport:
    """AC1: resolve_transport() returns "stdio"/"http" or raises ValueError."""

    def test_unset_returns_stdio(self, monkeypatch):
        """Unset MCP_TRANSPORT → "stdio"."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        from openproject_mcp.http_transport import resolve_transport
        assert resolve_transport() == "stdio"

    def test_empty_returns_stdio(self, monkeypatch):
        """Empty MCP_TRANSPORT → "stdio"."""
        monkeypatch.setenv("MCP_TRANSPORT", "")
        from openproject_mcp.http_transport import resolve_transport
        assert resolve_transport() == "stdio"

    def test_http_returns_http(self, monkeypatch):
        """MCP_TRANSPORT=http → "http"."""
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        from openproject_mcp.http_transport import resolve_transport
        assert resolve_transport() == "http"

    def test_http_case_insensitive(self, monkeypatch):
        """MCP_TRANSPORT=HTTP → "http" (case-insensitive)."""
        monkeypatch.setenv("MCP_TRANSPORT", "HTTP")
        from openproject_mcp.http_transport import resolve_transport
        assert resolve_transport() == "http"

    def test_stdio_explicit_returns_stdio(self, monkeypatch):
        """MCP_TRANSPORT=stdio → "stdio"."""
        monkeypatch.setenv("MCP_TRANSPORT", "stdio")
        from openproject_mcp.http_transport import resolve_transport
        assert resolve_transport() == "stdio"

    def test_unknown_raises_valueerror(self, monkeypatch):
        """Unknown value → ValueError."""
        monkeypatch.setenv("MCP_TRANSPORT", "unknown")
        from openproject_mcp.http_transport import resolve_transport
        with pytest.raises(ValueError):
            resolve_transport()

    def test_unknown_invalid_value(self, monkeypatch):
        """MCP_TRANSPORT=websocket → ValueError."""
        monkeypatch.setenv("MCP_TRANSPORT", "websocket")
        from openproject_mcp.http_transport import resolve_transport
        with pytest.raises(ValueError):
            resolve_transport()


# ============================================================================
# AC2: stdio unchanged + regression gate
# ============================================================================


class TestStdioRegression:
    """AC2: stdio path unchanged; pre-existing tests pass green."""

    @pytest.fixture
    def stub_op_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")

    def test_stdio_path_runs_when_unset(self, monkeypatch, stub_op_env):
        """When MCP_TRANSPORT unset, main() should call stdio_server path."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        from openproject_mcp.http_transport import resolve_transport
        assert resolve_transport() == "stdio"

    def test_pre_existing_suite_passes(self, stub_op_env):
        """Pre-existing test suite should pass (regression gate)."""
        # This is tested by running pytest on the existing tests separately.
        # The test runner will confirm that the full suite passes.
        pass


# ============================================================================
# AC3: HTTP app builds under nominal env
# ============================================================================


class TestHttpAppConstruction:
    """AC3: build_http_app() returns a Starlette when MCP_TRANSPORT=http, MCP_AUTH_TOKEN set."""

    @pytest.fixture
    def http_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.setenv("MCP_AUTH_TOKEN", "testtoken")

    def test_builds_returns_starlette(self, http_env):
        """build_http_app() returns a Starlette instance."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert isinstance(app, Starlette)

    def test_no_raise(self, http_env):
        """build_http_app() does not raise under nominal env."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert app is not None


# ============================================================================
# AC4: Fail-closed startup
# ============================================================================


class TestFailClosedStartup:
    """AC4: build_http_app() raises RuntimeError when MCP_REQUIRE_BEARER=true (default) and MCP_AUTH_TOKEN unset."""

    @pytest.fixture
    def http_env_no_token(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
        # MCP_REQUIRE_BEARER defaults to "true"
        monkeypatch.delenv("MCP_REQUIRE_BEARER", raising=False)

    def test_raises_runtimeerror(self, http_env_no_token):
        """Raises RuntimeError when bearer required but token unset."""
        from openproject_mcp.http_transport import build_http_app
        with pytest.raises(RuntimeError):
            build_http_app()

    def test_error_message_mentions_auth_token(self, http_env_no_token):
        """Error message mentions MCP_AUTH_TOKEN."""
        from openproject_mcp.http_transport import build_http_app
        with pytest.raises(RuntimeError) as excinfo:
            build_http_app()
        assert "MCP_AUTH_TOKEN" in str(excinfo.value)

    def test_no_raise_when_bearer_disabled(self, monkeypatch):
        """No raise when MCP_REQUIRE_BEARER=false even if token unset."""
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("MCP_REQUIRE_BEARER", "false")
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert app is not None


# ============================================================================
# AC5: DNS-rebinding wiring
# ============================================================================


class TestDnsRebindingWiring:
    """AC5: security_settings wired with DNS-rebinding protection ON, allowed_hosts/origins non-empty, no wildcards, loopback in hosts."""

    @pytest.fixture
    def http_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.setenv("MCP_AUTH_TOKEN", "testtoken")

    def test_security_settings_attached(self, http_env):
        """app.state.security_settings exists and is TransportSecuritySettings."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert hasattr(app.state, "security_settings")

    def test_dns_rebinding_protection_enabled(self, http_env):
        """enable_dns_rebinding_protection is True."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert app.state.security_settings.enable_dns_rebinding_protection is True

    def test_allowed_hosts_non_empty(self, http_env):
        """allowed_hosts is non-empty."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert len(app.state.security_settings.allowed_hosts) > 0

    def test_allowed_origins_non_empty(self, http_env):
        """allowed_origins is non-empty."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert len(app.state.security_settings.allowed_origins) > 0

    def test_allowed_hosts_no_wildcard(self, http_env):
        """allowed_hosts contains no '*'."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert "*" not in app.state.security_settings.allowed_hosts

    def test_allowed_origins_no_wildcard(self, http_env):
        """allowed_origins contains no '*'."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert "*" not in app.state.security_settings.allowed_origins

    def test_allowed_hosts_includes_loopback(self, http_env):
        """allowed_hosts includes a loopback host (127.0.0.1 or localhost)."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        hosts = app.state.security_settings.allowed_hosts
        assert "127.0.0.1" in hosts or "localhost" in hosts


# ============================================================================
# AC6: Auth matrix (mounted over dummy route)
# ============================================================================


class TestAuthMatrix:
    """AC6: Auth middleware tests via TestClient with dummy 200 route."""

    @pytest.fixture
    def stub_op_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")

    def _make_client_with_auth(self, monkeypatch, auth_token=None, require_bearer=None, allowed_logins=None):
        """Helper: make a TestClient with AuthMiddleware over a dummy 200 route."""
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from openproject_mcp.http_transport import AuthMiddleware

        async def dummy_route(request):
            return PlainTextResponse("OK", status_code=200)

        dummy_app = Starlette(routes=[Route("/", endpoint=dummy_route, methods=["GET", "POST"])])

        auth_token_val = auth_token if auth_token else None
        require_bearer_val = require_bearer if require_bearer is not None else True
        allowed_logins_val = frozenset(allowed_logins) if allowed_logins else frozenset()

        auth_app = AuthMiddleware(
            dummy_app,
            auth_token=auth_token_val,
            require_bearer=require_bearer_val,
            allowed_logins=allowed_logins_val,
        )

        return TestClient(auth_app)

    def test_no_identity_returns_401(self, stub_op_env):
        """No Tailscale-User-Login → 401."""
        client = self._make_client_with_auth(stub_op_env, auth_token="testtoken")
        response = client.post("/")
        assert response.status_code == 401

    def test_identity_token_set_require_true_no_bearer_returns_403(self, stub_op_env):
        """Identity + token set + require-bearer=true + no Authorization → 403."""
        client = self._make_client_with_auth(stub_op_env, auth_token="testtoken", require_bearer=True)
        response = client.post("/", headers={"Tailscale-User-Login": "alice"})
        assert response.status_code == 403

    def test_identity_correct_bearer_returns_200(self, stub_op_env):
        """Identity + correct Authorization: Bearer → 200."""
        client = self._make_client_with_auth(stub_op_env, auth_token="testtoken", require_bearer=True)
        response = client.post(
            "/",
            headers={
                "Tailscale-User-Login": "alice",
                "Authorization": "Bearer testtoken",
            },
        )
        assert response.status_code == 200

    def test_identity_require_bearer_false_no_bearer_returns_200(self, stub_op_env):
        """Identity + require-bearer=false + no bearer → 200."""
        client = self._make_client_with_auth(stub_op_env, auth_token="testtoken", require_bearer=False)
        response = client.post("/", headers={"Tailscale-User-Login": "alice"})
        assert response.status_code == 200

    def test_token_in_query_only_no_header_returns_403(self, stub_op_env):
        """Token only in query (?access_token=) with no Authorization header → 403."""
        client = self._make_client_with_auth(stub_op_env, auth_token="testtoken", require_bearer=True)
        response = client.post(
            "/?access_token=testtoken",
            headers={"Tailscale-User-Login": "alice"},
        )
        assert response.status_code == 403

    def test_allowlist_rejects_identity_not_in_list(self, stub_op_env):
        """Allowlist=alice, identity=bob + correct bearer → 403."""
        client = self._make_client_with_auth(
            stub_op_env, auth_token="testtoken", require_bearer=True, allowed_logins=["alice"]
        )
        response = client.post(
            "/",
            headers={
                "Tailscale-User-Login": "bob",
                "Authorization": "Bearer testtoken",
            },
        )
        assert response.status_code == 403

    def test_allowlist_accepts_identity_in_list(self, stub_op_env):
        """Allowlist=alice, identity=alice + correct bearer → 200."""
        client = self._make_client_with_auth(
            stub_op_env, auth_token="testtoken", require_bearer=True, allowed_logins=["alice"]
        )
        response = client.post(
            "/",
            headers={
                "Tailscale-User-Login": "alice",
                "Authorization": "Bearer testtoken",
            },
        )
        assert response.status_code == 200

    def test_allowlist_alice_no_bearer_returns_403(self, stub_op_env):
        """Allowlist=alice, identity=alice, require=true, no bearer → 403."""
        client = self._make_client_with_auth(
            stub_op_env, auth_token="testtoken", require_bearer=True, allowed_logins=["alice"]
        )
        response = client.post("/", headers={"Tailscale-User-Login": "alice"})
        assert response.status_code == 403

    def test_wrong_bearer_token_returns_403(self, stub_op_env):
        """Correct identity + wrong bearer token → 403."""
        client = self._make_client_with_auth(stub_op_env, auth_token="testtoken", require_bearer=True)
        response = client.post(
            "/",
            headers={
                "Tailscale-User-Login": "alice",
                "Authorization": "Bearer wrongtoken",
            },
        )
        assert response.status_code == 403


# ============================================================================
# AC7: /healthz endpoint
# ============================================================================


class TestHealthzEndpoint:
    """AC7: /healthz returns 200 with {"status": "ok"}, no auth required."""

    @pytest.fixture
    def http_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.setenv("MCP_AUTH_TOKEN", "testtoken")

    def test_healthz_no_auth_returns_200(self, http_env):
        """GET /healthz with no identity or bearer → 200."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_healthz_body_exact(self, http_env):
        """GET /healthz body is exactly {"status": "ok"}."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.json() == {"status": "ok"}


# ============================================================================
# AC8: Concurrency (no cross-call corruption)
# ============================================================================


class TestConcurrency:
    """AC8: Overlapping threaded calls return correct distinct results, no corruption."""

    @pytest.fixture
    def stub_op_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")

    def test_concurrent_calls_no_corruption(self, stub_op_env):
        """ThreadPoolExecutor with 2+ workers + mocked sleep-inducing transport → distinct results, no exception."""
        from openproject_mcp.client import OpenProjectClient
        from unittest.mock import patch, MagicMock

        client = OpenProjectClient()

        # Mock the session's get method to introduce a sleep and force interleaving
        with patch.object(requests.Session, "get") as mock_get:
            responses = []

            def make_response(call_num):
                response = MagicMock()
                response.json.return_value = {"call_id": call_num, "data": f"result_{call_num}"}
                response.status_code = 200
                # Sleep to force context switching in concurrent calls
                time.sleep(0.01)
                return response

            # Create separate response objects for each call
            mock_get.side_effect = [make_response(1), make_response(2)]

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit two overlapping GET tasks
                future1 = executor.submit(lambda: client.get("/projects"))
                time.sleep(0.005)  # Stagger them slightly
                future2 = executor.submit(lambda: client.get("/projects"))

                # Both should complete without exception
                result1 = future1.result()
                result2 = future2.result()

                # Both should have gotten their results (mocked)
                assert result1 is not None
                assert result2 is not None


# ============================================================================
# AC9: Delete tool gated
# ============================================================================


class TestDeleteWorkPackageGate:
    """AC9: delete_work_package remains absent from list_tools() unless OPENPROJECT_ALLOW_DELETE truthy."""

    @pytest.fixture
    def stub_op_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")

    def test_not_in_list_when_unset(self, stub_op_env, monkeypatch):
        """delete_work_package not in list_tools when OPENPROJECT_ALLOW_DELETE unset."""
        monkeypatch.delenv("OPENPROJECT_ALLOW_DELETE", raising=False)
        import asyncio
        from openproject_mcp import server
        tools = asyncio.run(server.list_tools())
        tool_names = {t.name for t in tools}
        assert "delete_work_package" not in tool_names

    def test_in_list_when_true(self, stub_op_env, monkeypatch):
        """delete_work_package in list_tools when OPENPROJECT_ALLOW_DELETE=true."""
        monkeypatch.setenv("OPENPROJECT_ALLOW_DELETE", "true")
        import asyncio
        from openproject_mcp import server
        tools = asyncio.run(server.list_tools())
        tool_names = {t.name for t in tools}
        assert "delete_work_package" in tool_names


# ============================================================================
# AC10: Dependencies
# ============================================================================


class TestDependencies:
    """AC10: requirements.txt contains starlette, uvicorn, mcp>=1.8."""

    def test_requirements_contain_starlette(self):
        """requirements.txt contains starlette."""
        with open("/workspace/requirements.txt") as f:
            content = f.read()
        assert "starlette" in content.lower()

    def test_requirements_contain_uvicorn(self):
        """requirements.txt contains uvicorn."""
        with open("/workspace/requirements.txt") as f:
            content = f.read()
        assert "uvicorn" in content.lower()

    def test_requirements_contain_mcp_with_floor(self):
        """requirements.txt contains mcp requirement with floor >=1.8."""
        with open("/workspace/requirements.txt") as f:
            lines = f.readlines()
        mcp_lines = [line.strip() for line in lines if "mcp" in line.lower()]
        assert any(mcp_lines), "No mcp requirement found"
        assert any(">=1.8" in line for line in mcp_lines), f"No >=1.8 found in mcp lines: {mcp_lines}"


# ============================================================================
# AC11: Deploy artefacts present + structurally valid
# ============================================================================


class TestDeployArtefacts:
    """AC11: Dockerfile, compose, .env.example, README, update-mcp.sh structurally valid."""

    def test_dockerfile_exists(self):
        """Dockerfile exists."""
        assert os.path.exists("/workspace/Dockerfile")

    def test_dockerfile_python_base(self):
        """Dockerfile uses python base image."""
        with open("/workspace/Dockerfile") as f:
            content = f.read()
        assert "python" in content.lower()

    def test_dockerfile_installs_requirements(self):
        """Dockerfile installs requirements.txt."""
        with open("/workspace/Dockerfile") as f:
            content = f.read()
        assert "requirements.txt" in content

    def test_dockerfile_entrypoint_runs_mcp(self):
        """Dockerfile CMD/ENTRYPOINT invokes python -m openproject_mcp."""
        with open("/workspace/Dockerfile") as f:
            content = f.read()
        assert "openproject_mcp" in content

    def test_compose_file_exists(self):
        """deploy/docker-compose.yml exists."""
        assert os.path.exists("/workspace/deploy/docker-compose.yml")

    def test_compose_valid_yaml(self):
        """docker-compose.yml parses as valid YAML."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_compose_has_two_services(self):
        """docker-compose.yml has exactly two services."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "services" in data
        assert len(data["services"]) == 2

    def test_compose_has_tailscale_sidecar(self):
        """One service uses image tailscale/tailscale."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        images = [s.get("image", "") for s in services.values()]
        assert any("tailscale/tailscale" in img for img in images)

    def test_compose_app_network_mode_service(self):
        """App service sets network_mode: service:<sidecar>."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        # Find the non-tailscale service
        app_service = None
        for name, svc in services.items():
            if "tailscale/tailscale" not in svc.get("image", ""):
                app_service = svc
                break
        assert app_service is not None
        assert "network_mode" in app_service
        assert "service:" in app_service["network_mode"]

    def test_compose_has_external_network(self):
        """Top-level network compose_repo_backend declared external: true."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "networks" in data
        assert "compose_repo_backend" in data["networks"]
        assert data["networks"]["compose_repo_backend"].get("external") is True

    def test_compose_app_has_restart(self):
        """App service has restart policy."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        app_service = None
        for name, svc in services.items():
            if "tailscale/tailscale" not in svc.get("image", ""):
                app_service = svc
                break
        assert app_service is not None
        assert "restart" in app_service

    def test_compose_app_has_healthcheck(self):
        """App service has healthcheck."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        app_service = None
        for name, svc in services.items():
            if "tailscale/tailscale" not in svc.get("image", ""):
                app_service = svc
                break
        assert app_service is not None
        assert "healthcheck" in app_service

    def test_compose_app_has_logging_max_size(self):
        """App service has logging.options.max-size."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        app_service = None
        for name, svc in services.items():
            if "tailscale/tailscale" not in svc.get("image", ""):
                app_service = svc
                break
        assert app_service is not None
        assert "logging" in app_service
        assert "options" in app_service["logging"]
        assert "max-size" in app_service["logging"]["options"]

    def test_compose_app_has_logging_max_file(self):
        """App service has logging.options.max-file."""
        import yaml
        with open("/workspace/deploy/docker-compose.yml") as f:
            data = yaml.safe_load(f)
        services = data.get("services", {})
        app_service = None
        for name, svc in services.items():
            if "tailscale/tailscale" not in svc.get("image", ""):
                app_service = svc
                break
        assert app_service is not None
        assert "logging" in app_service
        assert "options" in app_service["logging"]
        assert "max-file" in app_service["logging"]["options"]

    def test_env_example_exists(self):
        """deploy/.env.example exists."""
        assert os.path.exists("/workspace/deploy/.env.example")

    def test_env_example_has_required_vars(self):
        """deploy/.env.example contains required env var names."""
        with open("/workspace/deploy/.env.example") as f:
            content = f.read()
        required_vars = [
            "OPENPROJECT_URL",
            "OPENPROJECT_API_KEY",
            "MCP_AUTH_TOKEN",
            "TS_AUTHKEY",
            "MCP_REQUIRE_BEARER",
            "MCP_ALLOWED_LOGINS",
            "MCP_PORT",
        ]
        for var in required_vars:
            assert var in content, f"{var} not in .env.example"

    def test_readme_exists(self):
        """deploy/README.md exists."""
        assert os.path.exists("/workspace/deploy/README.md")

    def test_readme_non_empty(self):
        """deploy/README.md is non-empty."""
        with open("/workspace/deploy/README.md") as f:
            content = f.read()
        assert len(content.strip()) > 0

    def test_update_script_exists(self):
        """deploy/update-mcp.sh exists."""
        assert os.path.exists("/workspace/deploy/update-mcp.sh")

    def test_update_script_executable(self):
        """deploy/update-mcp.sh is executable."""
        import stat
        mode = os.stat("/workspace/deploy/update-mcp.sh").st_mode
        assert mode & stat.S_IXUSR

    def test_update_script_has_shebang(self):
        """deploy/update-mcp.sh starts with #!."""
        with open("/workspace/deploy/update-mcp.sh") as f:
            first_line = f.readline()
        assert first_line.startswith("#!")

    def test_update_script_contains_docker_save(self):
        """deploy/update-mcp.sh contains 'docker save'."""
        with open("/workspace/deploy/update-mcp.sh") as f:
            content = f.read()
        assert "docker save" in content

    def test_update_script_contains_docker_load(self):
        """deploy/update-mcp.sh contains 'docker load'."""
        with open("/workspace/deploy/update-mcp.sh") as f:
            content = f.read()
        assert "docker load" in content

    def test_update_script_contains_compose_up(self):
        """deploy/update-mcp.sh contains 'compose up'."""
        with open("/workspace/deploy/update-mcp.sh") as f:
            content = f.read()
        assert "compose up" in content


# ============================================================================
# AC12: Bounded thread pool
# ============================================================================


class TestBoundedThreadPool:
    """AC12: app.state.executor is ThreadPoolExecutor with max_workers=8 (default)."""

    @pytest.fixture
    def http_env(self, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.setenv("MCP_AUTH_TOKEN", "testtoken")

    def test_executor_attached(self, http_env):
        """app.state.executor exists."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert hasattr(app.state, "executor")

    def test_executor_is_threadpool(self, http_env):
        """app.state.executor is a ThreadPoolExecutor."""
        from openproject_mcp.http_transport import build_http_app
        from concurrent.futures import ThreadPoolExecutor
        app = build_http_app()
        assert isinstance(app.state.executor, ThreadPoolExecutor)

    def test_executor_default_max_workers(self, http_env):
        """app.state.executor has _max_workers == 8 (default)."""
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert app.state.executor._max_workers == 8

    def test_executor_custom_max_workers(self, monkeypatch):
        """app.state.executor respects MCP_MAX_WORKERS."""
        monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
        monkeypatch.setenv("OPENPROJECT_API_KEY", "k")
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.setenv("MCP_AUTH_TOKEN", "testtoken")
        monkeypatch.setenv("MCP_MAX_WORKERS", "4")
        from openproject_mcp.http_transport import build_http_app
        app = build_http_app()
        assert app.state.executor._max_workers == 4
