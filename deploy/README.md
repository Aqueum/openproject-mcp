# NAS / container deployment

This directory contains artefacts for running `openproject-mcp` as an HTTP
server inside a container on a NAS (or any Docker host), fronted by a
Tailscale sidecar for identity-aware access control.

## Architecture

```
Claude Desktop / Claude Code (Mac)
  └─ Tailscale ──→ tailscale sidecar container
                       └─ injects Tailscale-User-Login header
                           └─ loopback ──→ openproject-mcp (HTTP)
                                              └─ HTTPS ──→ OpenProject
```

The Tailscale sidecar injects the authenticated caller's Tailscale login email
as the `Tailscale-User-Login` header. The MCP server validates that header
(plus an optional bearer token) before forwarding any request.

## Prerequisites

- Docker + Compose v2 (`docker compose`) on the NAS.
- A Tailscale auth key (`TS_AUTHKEY`) from <https://login.tailscale.com/admin/settings/keys>.
  Use an ephemeral, reusable key tagged for the node.
- An external Docker network named `compose_repo_backend` already created:
  `docker network create compose_repo_backend`
- OpenProject running separately (no changes to OP needed).

## Quickstart

```bash
cd deploy
cp .env.example .env
# Edit .env — fill in OPENPROJECT_URL (use the internal http://web:8080),
# OPENPROJECT_API_KEY, MCP_AUTH_TOKEN, TS_AUTHKEY, and — critically —
# MCP_ALLOWED_HOSTS (see gotcha below).
docker compose up -d
```

> **Gotcha — set `MCP_ALLOWED_HOSTS`.** The server has DNS-rebinding protection
> on, with the default allowlist `127.0.0.1,localhost`. Requests arriving over
> Tailscale carry the MagicDNS Host (`openproject-mcp.<tailnet>.ts.net`), so if
> you don't add it to `MCP_ALLOWED_HOSTS`, **every request returns 421**. The
> `tailscale-serve.json` in this directory (mounted into the sidecar) exposes
> HTTPS 443 → `127.0.0.1:8091`; it is required — don't delete it.

Check the health endpoint from within the Tailscale network:
```bash
curl https://<tailscale-hostname>/healthz
# expects: {"status": "ok"}
```

## Updating

Run `./deploy/update-mcp.sh` from the repo root, or `git pull && docker compose
up -d --build`. Note `update-mcp.sh` builds locally — fine if the host can build.
If the Synology can't (old Docker engine / low RAM), build on the Mac instead and
transfer the image: `docker buildx build --platform linux/amd64 -t openproject-mcp .`
→ `docker save openproject-mcp | gzip | ssh NAS 'gunzip | docker load'` → then
`docker compose up -d` on the NAS.

## Environment variables

See `.env.example` for the full list with descriptions. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENPROJECT_URL` | yes | Base URL of your OpenProject instance |
| `OPENPROJECT_API_KEY` | yes | OpenProject API key |
| `MCP_AUTH_TOKEN` | yes (if `MCP_REQUIRE_BEARER=true`) | Bearer secret |
| `TS_AUTHKEY` | yes | Tailscale auth key for the sidecar |
| `MCP_ALLOWED_LOGINS` | no | Comma-sep Tailscale logins; empty = any identity |
| `MCP_ALLOWED_HOSTS` | **effectively yes** | DNS-rebinding allowlist; must include the node's MagicDNS host or all requests 421 |
| `MCP_ALLOWED_ORIGINS` | no | Origin allowlist for browser-based callers |
| `MCP_PORT` | no | Default `8091` (must match `tailscale-serve.json` if changed) |

## Security notes

- The MCP server binds to loopback only; traffic reaches it exclusively via
  the Tailscale sidecar's network namespace.
- `MCP_REQUIRE_BEARER=true` (default) means every request must carry a valid
  `Authorization: Bearer <token>` header in addition to the Tailscale identity.
- Set `MCP_ALLOWED_LOGINS` to restrict access to specific Tailscale accounts.
