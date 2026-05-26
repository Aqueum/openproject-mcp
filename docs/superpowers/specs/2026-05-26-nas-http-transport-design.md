# NAS HTTP-transport deployment — design (rev 2)

- **Date:** 2026-05-26
- **Branch:** `nas` (revert point: tag `stdio-baseline`)
- **Status:** draft rev 2, post independent spec-critic; pending user review → `/vs`
- **Supersedes:** rev 1 (single-port `:8443` + unconditional bearer). Changed after
  adversarial critique — see "Critique resolution log" at the end.

## Goal

Run `openproject-mcp` as a long-running container on the Synology NAS, exposed
over Tailscale, reachable from Claude Desktop, Claude Code, **and the iOS app**,
all tailnet-only. The existing local-stdio mode stays the default and unchanged,
so it remains the zero-risk fallback.

## Why this is more than relocation

The server speaks **stdio** only today (`stdio_server()`, `server.py:402`). A
stdio process is spawned by its client over stdin/stdout; one sitting on the NAS
is reachable by nobody. So "MCP on the NAS" couples three changes: **transport**
(add streamable-HTTP), **deployment** (subprocess → container), **auth** (a
network-exposed server needs its own front door).

## Current topology (observed; placeholders keep machine identifiers out of git)

- Stock OpenProject Compose stack, project `compose_repo`: `web`/`worker`/`cron`
  (`openproject/openproject:17`), `db` (postgres:17), `cache` (memcached),
  `proxy` (`openproject/proxy`), `hocuspocus`, `autoheal`.
- Networks `compose_repo_frontend`, `compose_repo_backend`, `compose_repo_default`.
  Per the live compose: **`web` is on both `frontend` and `backend`**; `hocuspocus`
  on both; `proxy` on `frontend` only.
- `proxy` publishes `127.0.0.1:8090:80`; OP is exposed by
  `tailscale serve --bg http://localhost:8090` → `https://<nas-host>.<tailnet>.ts.net`,
  tailnet-only, auto-HTTPS.
- `hocuspocus` already reaches OP at `http://web:8080`;
  `OPENPROJECT_ADDITIONAL__HOST__NAMES: web` whitelists that Host header.
- `OPENPROJECT_HTTPS=true` is set on OP (relevant to the internal hop — see §3).
- OP's own secrets verified **not** the insecure compose defaults. Out of scope.
- The user's iPhone is a tailnet member.

## Locked decisions (after critique)

- **(a) Exposure: dedicated Tailscale sidecar.** The MCP container gets its own
  tailnet node `mcp-op.<tailnet>.ts.net` on standard **443** via a
  `tailscale/tailscale` sidecar in userspace-networking mode. OP's `serve` config
  is never touched (truly zero risk to live OP), standard port avoids connector
  quirks. Cost: one sidecar container + a Tailscale auth key + a state volume.
- **(b) Auth: Tailscale identity is the floor; bearer is hardening where the
  client supports it.** `tailscale serve` injects spoof-proof `Tailscale-User-*`
  headers (and strips client-supplied ones). The MCP requires a valid identity
  header on every request (the guaranteed gate, works for *all* clients incl iOS);
  if `MCP_AUTH_TOKEN` is set it *additionally* requires a matching bearer. A
  per-deployment toggle controls whether a missing bearer is fatal, so a client
  that can't carry the header (possibly iOS) still works behind the identity floor.

## Design

### 1. Transport selector (core code change)

- `MCP_TRANSPORT` env var: `stdio` (default) | `http`.
- `stdio`: unchanged bootstrap. Existing Desktop config + all stdio tests keep
  working untouched.
- `http`: serve the same `Server` over **streamable-HTTP** via a Starlette ASGI
  app run by uvicorn (**single worker** — see §H/concurrency), binding
  `127.0.0.1:${MCP_PORT:-8091}` (loopback only inside the shared netns; the
  sidecar is the sole ingress — no host port publish).
- Pin transport security explicitly: construct the session manager with
  `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[...], allowed_origins=[...])`.
  (SDK default is **off** — confirmed in `mcp` source.)
- New deps: `starlette`, `uvicorn`. Bump `mcp` floor to a version that ships
  `StreamableHTTPSessionManager` + `TransportSecuritySettings` (≥ 1.8; pin tested).

### 2. Auth middleware (http mode only)

- **Floor (always):** reject any request lacking `Tailscale-User-Login`
  (injected only by the sidecar's `tailscale serve`; absent ⇒ not via Tailscale ⇒
  reject). Optional `MCP_ALLOWED_LOGINS` allowlist pins to the user's login(s).
- **Hardening (optional):** if `MCP_AUTH_TOKEN` set, also require
  `Authorization: Bearer <token>`, constant-time compare. `MCP_REQUIRE_BEARER`
  (default true) governs whether a *missing* bearer is fatal; set false for a
  client that can't attach the header so it falls back to the identity floor.
- **Header attachment is applied to every request type** (the SSE GET *and* the
  JSON-RPC POSTs), since streamable-HTTP keeps a long-lived stream open.
- **Spike first (implementation step 0):** confirm whether Desktop, Claude Code,
  and the iOS app can each attach a static `Authorization` header to the
  streamable-HTTP connection. Result decides per-client `MCP_REQUIRE_BEARER`.
- Hygiene: token accepted in header only (never query string); uvicorn access
  logging scrubbed/disabled so the header never lands in logs; rejection logs
  never echo the presented token; MCP `.env` is `chmod 600`.
- stdio path ignores all of the above (no network surface).
- **`/healthz`** route bypasses auth (200, no tool exposure) for the container
  healthcheck.

### 3. Reaching OpenProject (the load-bearing hop)

- The sidecar joins `compose_repo_backend` (declared **external**); the app uses
  `network_mode: "service:tailscale"` so it shares the sidecar's netns and DNS.
  Thus the app resolves and reaches `http://web:8080` (web is on `backend`), and
  `tailscale serve` forwards 443 → `127.0.0.1:8091` in that same netns.
- `OPENPROJECT_URL=http://web:8080`; Host `web` is whitelisted.
- **RISK (must verify on NAS before trusting — §B):** `OPENPROJECT_HTTPS=true`
  can 301-redirect plain-HTTP `api/v3` calls; reads may survive while
  POST/PATCH/DELETE (our write tools) break. Verification exercises a **write**
  (create + delete a throwaway WP), not just a read. Fallback if it breaks
  (config-only, no code change): point `OPENPROJECT_URL` at the proxy path the
  working tailnet client already uses.

### 4. Tailscale sidecar exposure

- `tailscale/tailscale` sidecar, `TS_USERSPACE=true` (Synology has no TUN by
  default), `TS_AUTHKEY` from the MCP `.env`, persistent `tailscale` state volume,
  `TS_SERVE_CONFIG` (or an entrypoint running `tailscale serve --bg https / → http://127.0.0.1:8091`).
- Result: `https://mcp-op.<tailnet>.ts.net` on 443, tailnet-only, auto-HTTPS,
  completely independent of OP's node and serve config.

### 5. Secrets (separate `.env`, per Q4)

- MCP's own `.env` (never OP's): `OPENPROJECT_URL`, `OPENPROJECT_API_KEY`
  (a token minted in OP for the MCP), `MCP_AUTH_TOKEN`, `TS_AUTHKEY`, optional
  `MCP_PORT` / `MCP_ALLOWED_LOGINS` / `MCP_REQUIRE_BEARER`.

### 6. Deploy as a separate compose project (decoupled from OP)

- Ships in this repo as `deploy/docker-compose.yml` (project `openproject-mcp`),
  **not** an override merged into OP's stack — so OP's `update.sh`/recreate never
  touches it, and however the OP stack is invoked (bare `up`, explicit `-f`,
  DSM/Portainer) is irrelevant. References `compose_repo_backend` as an external
  network.
- Two services: `tailscale` (sidecar) and `openproject-mcp` (app,
  `network_mode: service:tailscale`).
- `restart: unless-stopped`; `healthcheck` against `/healthz`;
  `logging` json-file with `max-size`/`max-file` (NAS is space-constrained).
- `OPENPROJECT_ALLOW_DELETE` **unset** by default — the hard-delete tool
  (`delete_work_package`) is now network-reachable; keep its blast radius closed
  unless explicitly enabled.

### 7. Image build (no registry, per repo stance)

- Recommended: build on the **Mac** with `docker buildx build --platform linux/amd64`,
  `docker save | gzip`, `scp` to NAS, `docker load`. Avoids Synology Docker's
  old-engine / low-RAM / no-BuildKit pitfalls and stays registry-free.
- Alternative: build on the NAS *iff* a pre-flight (`docker version`, free RAM,
  `docker compose` v2, wheels-only `pip`) passes.
- `requirements.txt` pinned so `pip` installs **wheels** (no `cryptography`/
  `pydantic-core` sdist compile).

### 8. Concurrency model

- HTTP mode is multi-client by design. uvicorn runs **single worker**; sync
  `requests` calls are offloaded to a thread pool. The shared `requests.Session`
  is replaced with a per-request (or thread-safe pooled) client so overlapping
  tool calls from two sessions don't race. A concurrency test exercises two
  overlapping calls. (If we instead accept serialized throughput, that's stated
  as a deliberate limit — fine for a personal tool, but written down.)

### 9. Tests + docs

- Unit (mechanical, via `/vs` after a Linux venv rebuild — see §A): transport
  selection; fail-closed; auth floor + bearer matrix; DNS-rebinding settings
  present; concurrency.
- README NAS section; CHANGELOG entry (same commit as code, per repo convention).

## Acceptance criteria

### A. Harness-verifiable (in-container, by `/vs`)

> Precondition: rebuild the Linux venv (`bash scripts/setup-venv.sh`) — the
> in-repo venv is a broken Mac venv and won't run under Linux as-is.

1. `MCP_TRANSPORT` unset/`stdio` → stdio bootstrap; existing tests green.
2. ASGI app constructs; a Starlette `TestClient` `initialize` handshake returns
   the MCP init result (no real port, no Docker).
3. `http` mode with no `MCP_AUTH_TOKEN` **and** `MCP_REQUIRE_BEARER=true` →
   process exits non-zero with a clear message (fail-closed).
4. Auth matrix via `TestClient`: no `Tailscale-User-Login` → 401; identity present,
   bearer required+absent → 401; identity present, bearer required+correct → ok;
   identity present, `MCP_REQUIRE_BEARER=false`, no bearer → ok.
5. Session manager is constructed with `enable_dns_rebinding_protection=True` and
   non-empty host/origin allowlists (assert on the wiring).
6. Two overlapping tool calls don't error (concurrency).
7. `python3 -m pytest tests/` green.

### B. Manual NAS verification (user — NOT harness-verifiable, and named so)

1. **Pre-build checks:** how the OP stack is launched (`restart.sh`/`update.sh`);
   `docker inspect compose_repo-web-1` confirms `web` answers on `backend:8080`;
   build capability if building on-NAS; `tailscale version` + userspace support.
2. Build/load the app image (Mac-build → save → scp → load recommended).
3. Create MCP `.env`; `docker compose -p openproject-mcp up -d`; both containers
   healthy.
4. **Write-test the OP hop:** through the MCP, create then delete a throwaway WP
   (proves POST/DELETE survive the internal `http://web:8080` hop under
   `OPENPROJECT_HTTPS=true`). If it fails, switch `OPENPROJECT_URL` to the proxy
   path and re-test.
5. `tailscale serve status` on the sidecar shows 443 → `127.0.0.1:8091`;
   `mcp-op.<tailnet>.ts.net` resolves on the tailnet.
6. **Client header spike:** confirm Desktop, Claude Code, and the iOS app can each
   attach the bearer; set per-client `MCP_REQUIRE_BEARER` accordingly.
7. Each client lists tools and runs a call over `https://mcp-op.<tailnet>.ts.net`.

## Out of scope

- Rotating OpenProject's own secrets (verified fine; belongs to the OP deploy).
- Any public (non-tailnet) exposure.
- CI/CD or registry publishing (image moved by save/load).
- Removing stdio — stays default + documented revert path.

## Revert path

`git checkout stdio-baseline`, or leave `MCP_TRANSPORT` unset. stdio mode is
untouched by any of the above. To remove the NAS deployment: `docker compose
-p openproject-mcp down` + delete the sidecar's tailnet node. OP is unaffected.

## Deliverables on `nas`

- `server.py`: transport selector, HTTP bootstrap (TransportSecuritySettings),
  auth middleware (identity floor + optional bearer), `/healthz`.
- per-request/thread-safe client change in `client.py` (or documented serialized limit).
- `requirements.txt`: add `starlette`, `uvicorn`; bump/pin `mcp`.
- `Dockerfile` (linux/amd64, wheels-only).
- `deploy/docker-compose.yml` (sidecar + app), `deploy/.env.example`,
  `deploy/README.md`.
- `tests/test_transport.py` (+ auth/concurrency).
- README NAS section; CHANGELOG entry.

## Critique resolution log (independent spec-critic)

- **C1 (bearer on SSE stream / iOS):** resolved by decision (b) — identity floor
  guarantees all clients; bearer is per-client via `MCP_REQUIRE_BEARER`; client
  spike is impl step 0 + AC B6. Header attached to GET *and* POST (§2).
- **C2 (DNS-rebinding off by default):** §1 explicitly enables
  `TransportSecuritySettings`; AC A5.
- **C3 (network reachability / override naming):** sidecar joins
  `compose_repo_backend` (external), app shares its netns (§3); separate compose
  project sidesteps override-merge naming (§6); pre-build inspect in B1.
- **H1 (OPENPROJECT_HTTPS redirect breaks writes):** §3 RISK + write-test AC B4 +
  config-only fallback.
- **H2 (NAS build constraints):** §7 Mac-build→save→load recommended.
- **H3 (shared requests.Session concurrency):** §8 single worker + per-request
  client + AC A6.
- **H4 (image-build ACs mis-filed as harness):** moved to §B; A2 reframed to
  TestClient; venv-rebuild precondition stated.
- **M1 (tailscale serve global-state clobber):** dissolved — sidecar is a
  separate node; OP's serve config untouched (decision a).
- **M2 (token log leakage):** §2 hygiene bullet.
- **M3 (healthcheck/restart/logs):** §6 + `/healthz` (§2).
- **M4 (override + update.sh coupling):** dissolved — separate compose project (§6).
- **S1 (`mcp>=1.0.0` floor too low):** §1 bump/pin.
- **S2 (sidecar / SSE alternatives):** sidecar adopted (decision a). Streamable-HTTP
  retained over SSE; if the spike shows a client only supports SSE, revisit (it's
  the same Starlette pattern).
- **S3 (`delete_work_package` now network-reachable):** §6 `OPENPROJECT_ALLOW_DELETE`
  unset by default.
