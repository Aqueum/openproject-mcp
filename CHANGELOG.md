# Changelog

Reverse-chronological log of shipped changes. Open backlog and parked items live in `TODO.md` (which doesn't exist yet — create on first parked item).

## 2026-05-20

[x] **`delete_work_package` with env + confirm gate** — `849c6bd`. New tool that permanently deletes a work package. Two locks: `OPENPROJECT_ALLOW_DELETE=true` must be set in the MCP server env (without it, the tool isn't registered at all), and `confirm=true` must be passed at the call site (raises `ValueError` otherwise). Dormant by default. Tests cover both gates.

[x] **Fix `update_relation` — relations don't have lockVersion** — `cc7c312`. Live testing revealed that OpenProject's `/api/v3/relations/{id}` PATCH doesn't take or require `lockVersion`; only work packages are version-locked. The previous implementation mirrored the WP update pattern (GET then PATCH with lockVersion), which raised `KeyError: 'lockVersion'` on every call because the GET response had no such field. Fix: drop the GET, PATCH directly with provided fields, add `ValueError` guard when neither `description` nor `relation_type` is given.

[x] **Add HTTP timeouts to OpenProject client** — `fa5a447`. Every `requests` call was missing a timeout argument, so a hung OP server / Tailscale path caused tools to wait for the OS-level TCP timeout (effectively forever). Claude Desktop's 4-minute cutoff fired first, producing opaque "no result received" errors. Default: 10s connect / 60s read. Overridable via `OPENPROJECT_CONNECT_TIMEOUT` and `OPENPROJECT_READ_TIMEOUT` env vars. Hangs now surface as proper `ConnectTimeout` / `ReadTimeout` errors within ~60s.

[x] **Add `scripts/setup-venv.sh` for one-shot venv rebuild** — `42a5e0c`. Mac venvs break silently when their base Python (Homebrew or python.org) moves or upgrades — the venv ends up pointing at a stale or missing interpreter and pip silently installs into the wrong place. The script auto-detects any Python 3.10+ on the Mac and rebuilds the venv from scratch, idempotently. Closes the recurring "the venv died, walk me through fixing it" copy-paste loop into a single command.

[x] **Document deployment topology** — `d66a619`. Added a "How it runs" section to README and a CLAUDE.md spelling out that the MCP server runs on the Mac as a Claude-Desktop subprocess, NOT on the NAS (where OpenProject itself lives). Future Claude sessions should stop directing the user to restart things on the NAS. Also: README config example now uses `python3` not `python`, since Apple's Python stub doesn't ship a `python` alias and the venv inherits that limitation when built against system Python.

[x] **Add `priority_id` to `update_work_package` and relation write tools** — `e42d570`. `update_work_package` now accepts `priority_id` (PATCHes `_links.priority`). New tools: `create_relation(from, to, relation_type)`, `delete_relation(id)`. New `OpenProjectClient.delete()` for `DELETE /api/v3/relations/{id}`. Tests cover request shape, lockVersion handling on WP update, and dispatch paths.
