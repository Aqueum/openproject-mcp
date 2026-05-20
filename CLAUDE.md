# openproject-mcp — context for Claude sessions

## Deployment topology

This MCP server runs as a **local subprocess of the MCP client** (Claude Desktop on the user's Mac). It is launched by `claude_desktop_config.json` and talks to OpenProject over HTTPS. The OpenProject server itself is a separate service on a different host (typically a NAS).

```
Claude Desktop (Mac)
  └─ openproject-mcp subprocess (this repo, Mac venv)
      └─ HTTPS ──→ OpenProject server (NAS or wherever)
```

**Do not tell the user to restart anything on the NAS.** The MCP code does not live there. The OpenProject server lives there, but restarting OP does not reload MCP tool code.

To pick up new MCP tool code, the user needs to:

1. `git pull` in their Mac-side checkout of this repo.
2. Quit and reopen Claude Desktop. That respawns the MCP subprocess against the updated code.

That is the only path. No NAS restart, no OP restart, no Docker, no systemd.

## Where the code actually lives

- GitHub: `Aqueum/openproject-mcp` (origin in this checkout).
- Mac checkout: path is whatever the user has in `claude_desktop_config.json` under `mcpServers.openproject.command` (the `venv/bin/python` path's parent directory).
- Container checkout (if working inside vibe): `/workspace`.

If you need to inspect the running config, point the user at `~/Library/Application Support/Claude/claude_desktop_config.json`. Don't guess the path.

## What is NOT in this repo

- No Dockerfile, no docker-compose.yml.
- No CI/CD (no GitHub Actions, no deploy hooks).
- No systemd unit.
- No NAS sync.

If a future session feels tempted to write any of the above as part of a "deployment" task — stop and confirm with the user. The current model is intentionally a local Python subprocess; productionising it would be a separate, explicit decision.

## Adding a new tool — minimum checklist

When asked to add a new MCP tool:

1. Write the tool function in the appropriate `src/openproject_mcp/tools/*.py` module.
2. Register the schema in `src/openproject_mcp/server.py` `list_tools()`.
3. Add the dispatch case in `call_tool()`, including any int/float casts (MCP arguments arrive as strings — see existing cases for the pattern).
4. Write unit tests in `tests/test_*.py` using `MagicMock` clients (see `test_work_packages.py` for the request-shape-assertion pattern).
5. Run `python3 -m pytest tests/` and confirm green before committing.

Don't skip the dispatch-cast step — it is the most common omission and causes silent type errors at runtime.

## Lock versions

OpenProject's PATCH endpoints (work packages, relations) require a `lockVersion` field. Always fetch the resource first, read `lockVersion`, include it in the PATCH body. See `update_work_package` and `update_relation` for the pattern.
