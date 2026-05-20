# openproject-mcp

An MCP (Model Context Protocol) server for [OpenProject](https://www.openproject.org/), enabling Claude and other AI agents to read and manage projects, work packages, users, and more via the OpenProject REST API v3.

## Features

- List and get projects
- List, get, create, and update work packages (with subtask support)
- Add comments to work packages
- List users, statuses, types, and priorities
- Filter work packages by assignee, status, type, or staleness
- Create, update, and delete work package relations (blocks, follows, etc.)
- Log and list time entries

## How it runs

This MCP server runs **locally on the same machine as your MCP client** (e.g. Claude Desktop on your Mac). The client launches `python -m openproject_mcp` as a subprocess via `claude_desktop_config.json`, and that subprocess talks to your OpenProject instance over HTTPS.

```
Claude Desktop (your Mac)
  └─ openproject-mcp subprocess (this repo's code, in a local venv)
      └─ HTTPS ──→ OpenProject server (separate host, e.g. NAS)
```

The OpenProject server itself is a separate service — typically on a NAS, VPS, or wherever you host OP. This MCP server does **not** run on the OP host and changes to MCP tool code do **not** require touching the OP host.

**To reload new MCP tool code:** quit and reopen your MCP client (Claude Desktop). That respawns the subprocess against the updated code. Restarting OpenProject or the NAS achieves nothing for MCP code — they're unrelated services.

## Setup

### 1. Create an API key in OpenProject

Admin → My Account → Access Tokens → API → Generate

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your URL and API key
```

### 3. Create venv and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e src/
```

### 4. Test

```bash
python -m openproject_mcp
# Should start without errors (waiting for MCP client)
```

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openproject": {
      "command": "/path/to/openproject-mcp/venv/bin/python",
      "args": ["-m", "openproject_mcp"],
      "env": {
        "OPENPROJECT_URL": "https://your-instance.ts.net",
        "OPENPROJECT_API_KEY": "your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop — the OpenProject tools will appear automatically.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all projects |
| `get_project` | Get project by ID or identifier |
| `list_work_packages` | List/filter work packages |
| `get_work_package` | Full details including subtasks and comments |
| `create_work_package` | Create task or subtask |
| `update_work_package` | Update status, assignee, priority, progress, dates, etc. |
| `get_comments` | List comments on a work package |
| `add_comment` | Post a comment to a work package |
| `list_users` | All users including AI agents |
| `list_statuses` | Valid statuses with IDs |
| `list_types` | Work package types |
| `list_priorities` | Priority levels |
| `get_work_package_relations` | Read relations (blocks, follows, etc.) |
| `create_relation` | Create a relation between two work packages |
| `update_relation` | Update a relation's description or type |
| `delete_relation` | Delete a relation by ID |
| `get_work_package_attachments` | List attachments on a work package |
| `get_attachment_content` | Fetch text content of an attachment |
| `list_activities` | Time entry activity types |
| `create_time_entry` | Log time against a work package |
| `list_time_entries` | List time entries with optional filter |
