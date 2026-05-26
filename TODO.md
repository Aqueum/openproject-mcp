# TODO

## Open

- [ ] **NAS HTTP transport — live bring-up + verification (manual, on the NAS).** The
  code, deploy artefacts and tests are merged (see CHANGELOG 2026-05-26, task_001);
  what remains can only be done on the NAS and is not harness-verifiable. Steps (full
  detail in design doc §B):
  - Build the image (on the Mac: `docker buildx --platform linux/amd64` → `docker save`
    → scp → `docker load`, if the Synology can't build it) and `docker compose -p
    openproject-mcp up -d`.
  - Set `MCP_ALLOWED_HOSTS` to include `openproject-mcp.<tailnet>.ts.net` — the
    DNS-rebinding default 421s real Tailscale traffic (the #1 first-boot failure).
  - Write-test the OP hop: create+delete a throwaway WP through the MCP to prove
    POST/DELETE survive internal `http://web:8080` under `OPENPROJECT_HTTPS=true`;
    fall back to the external URL if not.
  - Client header spike: confirm Desktop / Claude Code / iOS can each attach the
    bearer; set `MCP_REQUIRE_BEARER` per client.
  - Observe over a few days: zombie-SSE session count / container RSS (mobile
    resilience); switch to stateless mode if it drifts.
