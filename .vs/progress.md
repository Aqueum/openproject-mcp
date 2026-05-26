# /vs progress log

## task_001 — NAS HTTP transport

- 2026-05-26 — Planner: simplicity gate passed (multi-file, verifiable criteria,
  no mid-flow user decisions). Grounded against repo: stdio bootstrap at
  `server.py:402`, module-level `client = OpenProjectClient()` at `server.py:13`,
  tests in `tests/` (48 passing baseline). Resolved a critical environment blocker
  — system python had no pip/ensurepip and `sudo apt` is unavailable; bootstrapped
  an isolated `./venv` via `python3 -m venv --without-pip` + get-pip.py (PyPI
  reachable). Confirmed `mcp 1.27.1` exposes `StreamableHTTPSessionManager` +
  `TransportSecuritySettings`. Drafted spec.md (11 ACs, budget 3 cycles).
- 2026-05-26 — Spec Critic: **pass after 3 iterations** (concern count 12 → 7 → 0
  blocking). Iter-1 fixed SSE-hang/status-code/exception/concurrency-evasion traps;
  iter-2 fixed call-site/return-type/truthy-value ambiguities. Contract locked
  pending user approval.
- 2026-05-26 — Two post-pass additions folded in (bounded `ThreadPoolExecutor` via
  `MCP_MAX_WORKERS` + AC12; `deploy/update-mcp.sh`; mobile-resilience config as
  constraint/manual-note) after external review (Gemini) flagged zombie-SSE
  resource risk + update-path friction. Spec Critic **iteration 4: pass** on the
  deltas. `update-mcp.sh` static check tightened to pinned grep tokens.

### Cycle 1
- Generator: implemented across `http_transport.py` (new), `client.py` (per-thread
  Session), `server.py` (transport branch + `await uvicorn_server.serve()`),
  requirements, deploy artefacts, docs.
- Tester: 114 tests (66 new + 48 baseline), all pass, no regressions.
- **Evaluator: FAIL.** Tests green but the HTTP transport is non-functional at
  runtime. In `build_http_app()` the `lifespan` that calls `session_manager.run()`
  is attached to the inner `routes_app`, while uvicorn serves the `outer` app;
  Starlette does not propagate lifespan through `Mount`, so the session-manager
  task group never starts. Empirically confirmed: `with TestClient(build_http_app())`
  + POST `/mcp/` with valid auth → `RuntimeError: Task group is not initialized.`
  The test suite could not catch this because the spec scoped the live MCP handshake
  out (manual NAS check) — caught by Evaluator review + empirical probe. All other
  code correct. Fix: attach `lifespan` to the outermost served app. → cycle 2.

### Cycle 2
- Generator: minimal fix — moved `lifespan` from the inner `routes_app` to `outer`
  (the app uvicorn serves). No other files touched for the fix.
- Tester: re-ran the frozen 114 (unchanged — `test_transport.py` still 66 tests) and
  added `tests/test_http_lifespan.py` (runtime lifespan smoke). 115 passed, no regressions.
- **Evaluator: PASS.** Independently re-verified: full suite 115 green; strict repro
  now default-host → 421 (`Invalid Host header` — DNS-rebinding guard firing AND task
  group running, no RuntimeError), missing-identity → 401 through the real served app,
  allowed-host initialize → 200. Immutability held; no scope creep. Task complete.

### Post-/vs (pre-commit review, primary agent)
- Hygiene scan: no real tailnet name / NAS IP / hostnames leaked; secrets are
  placeholders. Clean.
- Caught two deploy blockers the spec ACs didn't cover (so /vs correctly passed):
  (1) `deploy/tailscale-serve.json` was missing though the compose mounts it →
  created it (HTTPS 443 → 127.0.0.1:8091). (2) `MCP_ALLOWED_HOSTS`/`MCP_ALLOWED_ORIGINS`
  weren't surfaced → added to compose + `.env.example` with the 421 gotcha; default
  allowlist would have 421'd all real Tailscale traffic. Also defaulted
  `OPENPROJECT_URL` to internal `http://web:8080` and documented the Mac-build path.
- Folded the two Gemini refinements + these fixes into the design doc (rev 3).
  Tests still 115 green. Committed to `nas`.
