# openproject-mcp

An MCP (Model Context Protocol) server for [OpenProject](https://www.openproject.org/), enabling Claude and other AI agents to read and manage projects, work packages, users, and more via the OpenProject REST API v3.

## Features

- List and get projects
- List, get, create, and update work packages (with subtask support)
- Add comments to work packages
- List users, statuses, types, and priorities
- Filter work packages by assignee, status, type, or staleness

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

### 4. Verify the server starts

```bash
python -m openproject_mcp
# Should start without errors (waiting for MCP client)
```

## Running tests

The test suite uses [`pytest`](https://pytest.org) and [`responses`](https://github.com/getsentry/responses) to mock HTTP calls — no live OpenProject instance is required.

```bash
# Install dev dependencies (once)
pip install -e "src/[dev]"

# Run all tests
pytest

# With coverage report
pytest --cov=openproject_mcp --cov-report=term-missing
```

Tests are also run automatically by GitHub Actions on every push and pull request.

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
| `update_work_package` | Update status, assignee, progress, etc. |
| `add_comment` | Post a comment to a work package |
| `list_users` | All users including AI agents |
| `list_statuses` | Valid statuses with IDs |
| `list_types` | Work package types |
| `list_priorities` | Priority levels |
