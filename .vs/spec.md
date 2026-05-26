# /vs sprint contract — NAS HTTP transport (task_001) — rev 2 (post spec-critic)

## Task summary

Add a streamable-HTTP transport to `openproject-mcp` so it can run as a container
on the NAS, while keeping stdio the default and unchanged. Selected by
`MCP_TRANSPORT`. HTTP mode runs a Starlette+uvicorn app with DNS-rebinding
protection on, a Tailscale-identity auth floor plus optional bearer token, an
unauthenticated `/healthz`, and a concurrency-safe OpenProject client. Plus the
deploy artefacts (Dockerfile, compose with a Tailscale sidecar, env example,
README) and tests. Full design + rationale: `docs/superpowers/specs/2026-05-26-nas-http-transport-design.md`.

This contract covers **code + artefacts + tests only**. Live NAS bring-up is out
of scope (see below) — do not fake or simulate it.

## Env-var contract (authoritative — Generator and Tester both bind to this)

http mode reads ONLY these; all have the defaults shown:

| Var | Default | Meaning |
|-----|---------|---------|
| `MCP_TRANSPORT` | `stdio` | `stdio` \| `http`; anything else → error |
| `MCP_PORT` | `8091` | uvicorn bind port (loopback) |
| `MCP_AUTH_TOKEN` | (unset) | bearer secret; if set, bearer checks active |
| `MCP_REQUIRE_BEARER` | `true` | whether a *missing* bearer is fatal to a request |
| `MCP_ALLOWED_LOGINS` | (empty) | comma-sep tailnet logins; empty = any authenticated identity |
| `MCP_ALLOWED_HOSTS` | `127.0.0.1,localhost` | feeds `TransportSecuritySettings.allowed_hosts` |
| `MCP_ALLOWED_ORIGINS` | `http://127.0.0.1,http://localhost` | feeds `allowed_origins` |
| `MCP_MAX_WORKERS` | `8` | upper bound on the sync-call thread pool |

Boolean env vars (`MCP_REQUIRE_BEARER`) are truthy for `true`/`1`/`yes`
(case-insensitive); all other values including empty string are falsy — matching
the existing `OPENPROJECT_ALLOW_DELETE` convention in `server.py`.

Identity header (injected by `tailscale serve`, trusted): `Tailscale-User-Login`.

**Auth decision order** (http mode, applied per request, BEFORE the MCP handler):
1. `GET /healthz` → 200 `{"status":"ok"}`, no auth, no tool data.
2. Missing/empty `Tailscale-User-Login` → **401**.
3. `MCP_ALLOWED_LOGINS` non-empty and header value not in it → **403**.
4. `MCP_AUTH_TOKEN` set and `MCP_REQUIRE_BEARER` true and `Authorization: Bearer
   <token>` header absent or not matching (constant-time compare) → **403**.
   (When `MCP_REQUIRE_BEARER=false`, the bearer check is skipped entirely.)
5. Otherwise → allowed (request proceeds to the MCP handler).

A token presented ONLY as a query-string param (`?access_token=`/`?token=`) with
no `Authorization` header is treated as "no bearer" (header-only acceptance).

## Implementation constraints (binding)

- **No import-time side effects for http mode.** `MCP_TRANSPORT`, `MCP_AUTH_TOKEN`,
  etc. are read only inside the app factory or `main()` — never at module import.
  The Starlette app is produced by a **callable factory** (e.g.
  `build_http_app() -> Starlette`), not constructed at module top level. (The
  existing module-level `server`/`client` in `server.py` may stay as-is.)
- **Auth is a standalone Starlette middleware / ASGI wrapper**, independently
  testable by mounting it over a trivial route that returns 200 — so auth tests
  never touch the streamable-HTTP/SSE machinery.
- **Fail-closed** raises `RuntimeError` (pinned type) with a message naming
  `MCP_AUTH_TOKEN`.
- **Bounded resources (mobile-resilience defence).** The sync-call thread pool is a
  `concurrent.futures.ThreadPoolExecutor(max_workers=MCP_MAX_WORKERS)` exposed at
  `app.state.executor`. uvicorn is run with a finite keep-alive timeout, and the
  streamable-HTTP session manager must release session state on the ASGI
  `disconnect` event so a dropped mobile SSE stream is reclaimed, not leaked.
  (Behaviour under *silent* TCP drops is a manual NAS observation — see Out of
  scope — not unit-tested.)

## Acceptance criteria

1. **Transport resolver.** An importable function (e.g. `resolve_transport()`)
   returns `"stdio"` when `MCP_TRANSPORT` unset, `"http"` when set to `http`, and
   raises `ValueError` (pinned) on an unrecognised value.
2. **stdio unchanged + regression gate.** The stdio entrypoint still runs the
   existing `stdio_server()` path when `MCP_TRANSPORT` is unset, and the
   pre-existing `tests/` suite passes green (baseline ~48 tests, all currently
   passing — assert green, not a hard count).
3. **HTTP app builds.** The factory returns a `Starlette` instance under env
   `MCP_TRANSPORT=http`, `MCP_AUTH_TOKEN=testtoken` (allowlists at their defaults)
   without raising.
4. **Fail-closed startup.** Calling the factory `build_http_app()` with
   `MCP_REQUIRE_BEARER` default (true) and `MCP_AUTH_TOKEN` unset raises
   **`RuntimeError`** (pinned call site = the factory) whose message mentions
   `MCP_AUTH_TOKEN`. (`pytest.raises(RuntimeError)`.)
5. **DNS-rebinding wiring.** The `StreamableHTTPSessionManager` is constructed with
   a `TransportSecuritySettings` where `enable_dns_rebinding_protection is True`,
   and `allowed_hosts`/`allowed_origins` are non-empty, contain **no** `*`
   wildcard, and `allowed_hosts` includes a loopback host (`127.0.0.1` or
   `localhost`). The factory returns a `Starlette` instance (per AC3) and attaches
   the settings object to **`app.state.security_settings`**; the test reads that
   attribute. (No tuple return — AC3's return type wins.)
6. **Auth matrix** — tested by mounting the auth middleware over a trivial
   `200` route and sending **POST** requests via Starlette `TestClient` (never an
   SSE GET). Status codes per the Auth decision order above:
   - no `Tailscale-User-Login` → **401**;
   - identity present, token set, require-bearer true, no/wrong `Authorization`
     bearer → **403**;
   - identity present + correct bearer → **200** (reaches the dummy route);
   - identity present, `MCP_REQUIRE_BEARER=false`, no bearer → **200**;
   - identity present, correct token only as `?access_token=` query param, no
     `Authorization` header → **403** (header-only acceptance);
   - `MCP_ALLOWED_LOGINS=alice`, identity `bob` + correct bearer → **403**
     (allowlist rejects before the bearer check);
   - `MCP_ALLOWED_LOGINS=alice`, identity `alice`, `MCP_REQUIRE_BEARER=true`, no
     bearer → **403** (allowlist passes, bearer fails — keeps the two checks
     independently observable);
   - `MCP_ALLOWED_LOGINS=alice`, identity `alice` + correct bearer → **200**.
7. **/healthz.** Using the same factory env as AC3 (`MCP_AUTH_TOKEN=testtoken`),
   `GET /healthz` with neither identity nor bearer → **200** with body exactly
   `{"status": "ok"}` and no tool/MCP data. (Verifies route-level auth bypass, not
   factory construction.)
8. **Concurrency.** A test using `concurrent.futures.ThreadPoolExecutor` with ≥2
   workers issues overlapping calls through the client layer, where the mocked
   transport sleeps briefly (`time.sleep`) to force interleaving; both calls return
   their correct, distinct results with no exception and no cross-call corruption.
   The shared module-level `requests.Session` MUST be made per-request or
   thread-safe — the serialized single-worker escape hatch is **not** permitted;
   fix the client.
9. **Delete tool still gated.** `delete_work_package` remains absent from
   `list_tools()` unless `OPENPROJECT_ALLOW_DELETE` is truthy (regression).
10. **Dependencies.** `requirements.txt` contains `starlette`, `uvicorn`, and an
    `mcp` requirement with floor `>=1.8`. (Static file check; "wheels-only" is a
    deployment note in the design doc, not a test assertion.)
11. **Deploy artefacts present + structurally valid** (static checks; NOT executed):
    - `Dockerfile` — a `python` base image, installs `requirements.txt`, and its
      `CMD`/`ENTRYPOINT` invokes `python -m openproject_mcp`.
    - `deploy/docker-compose.yml` — parses as YAML; exactly two services where one
      uses image `tailscale/tailscale` (the sidecar) and the other (the app) sets
      `network_mode: "service:<sidecar-service-name>"`; a top-level network keyed
      `compose_repo_backend` declared `external: true`; the app service has
      `restart`, a `healthcheck`, and `logging.options.max-size` **and**
      `logging.options.max-file`.
    - `deploy/.env.example` — contains the names `OPENPROJECT_URL`,
      `OPENPROJECT_API_KEY`, `MCP_AUTH_TOKEN`, `TS_AUTHKEY`, `MCP_REQUIRE_BEARER`,
      `MCP_ALLOWED_LOGINS`, `MCP_PORT`.
    - `deploy/README.md` — exists, non-empty.
    - `deploy/update-mcp.sh` — one-shot patch/redeploy script; exists, non-empty,
      starts with a `#!` shebang, and contains the literal tokens `docker save`,
      `docker load`, and `compose up` (static grep; not executed).
12. **Bounded thread pool.** The factory exposes `app.state.executor`, a
    `concurrent.futures.ThreadPoolExecutor` whose `max_workers` equals
    `MCP_MAX_WORKERS` (default 8). Assert `app.state.executor._max_workers == 8`
    under default env.

## Out of scope (do NOT build or fake)

- Live NAS bring-up: running uvicorn against a real OpenProject, creating a real
  Tailscale node, connecting real Desktop/Code/iOS clients (design spec §B). Do
  not simulate or stub these as "passing".
- Building or running the Docker image / compose stack (write the files only).
- The end-to-end streamable-HTTP MCP session handshake against a live client
  (we verify auth, security wiring, app construction, `/healthz` — not full
  protocol round-trips).
- Rotating OpenProject's own secrets.
- Changing stdio's default behaviour or removing it.
- Mobile-network resilience under *silently* dropped SSE connections (zombie-session
  cleanup, memory drift over days). Defended by the bounded pool + disconnect
  teardown + keep-alive timeout + `restart: unless-stopped`, but the real-world
  behaviour is a manual NAS observation (watch session count / RSS), not a harness
  test. Stateless mode is the documented escape hatch if it proves necessary.

## Test location

`tests/` (repo convention). New tests in `tests/test_transport.py`; Tester may add
further `tests/test_*.py`. Existing tests are the regression baseline.

## Environment setup (both Generator and Tester MUST do this)

A working venv already exists at `./venv` (python 3.11). Run tests with it. If the
venv is missing/broken, rebuild WITHOUT sudo/apt (PEP 668 blocks system installs;
a venv avoids it):

```
rm -rf venv && python3 -m venv --without-pip venv
[ -f /tmp/get-pip.py ] || curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
venv/bin/python /tmp/get-pip.py
venv/bin/python -m pip install -r requirements.txt -e src/ pytest
```

Run the suite (stub env needed because `server.py` imports a client that requires
`OPENPROJECT_URL`/`OPENPROJECT_API_KEY` at import):

```
OPENPROJECT_URL=http://x.invalid OPENPROJECT_API_KEY=k venv/bin/python -m pytest tests/ -q
```

PyPI and files.pythonhosted.org are reachable from this container; `sudo`/`apt`
are not (no TTY).

## Proposed budget

**3 cycles.** Rationale: the auth matrix, streamable-HTTP/security wiring, and the
concurrency change each carry a real chance of a cycle-1 miss; 3 cycles allow
convergence without open-ended drift.
