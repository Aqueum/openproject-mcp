"""MCP server — registers all OpenProject tools."""

import json
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from openproject_mcp.client import OpenProjectClient
from openproject_mcp.tools import projects, work_packages, users, meta

server = Server("openproject")
client = OpenProjectClient()


def ok(data) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def err(e: Exception) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=f"Error: {e}")]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_projects",
            description="List all accessible OpenProject projects.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_project",
            description="Get details of a project by its ID or identifier string.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Project ID or identifier"}},
                "required": ["id"],
            },
        ),
        types.Tool(
            name="list_work_packages",
            description=(
                "List work packages with optional filters. Use stale_days to find tasks "
                "not updated recently. Use assignee_id='me' for current user's tasks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Filter by project ID or identifier"},
                    "assignee_id": {"type": "string", "description": "Filter by assignee user ID or 'me'"},
                    "status": {"type": "string", "description": "Filter by status name, e.g. 'New', 'In progress'"},
                    "type_name": {"type": "string", "description": "Filter by type name, e.g. 'Task', 'Bug'"},
                    "stale_days": {"type": "integer", "description": "Only return WPs not updated in N days"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_work_package",
            description="Get full details of a work package including subtasks and comments.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "integer", "description": "Work package ID"}},
                "required": ["id"],
            },
        ),
        types.Tool(
            name="create_work_package",
            description="Create a new work package. Set parent_id to create a subtask.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID or identifier"},
                    "subject": {"type": "string", "description": "Title of the work package"},
                    "type_id": {"type": "integer", "description": "Type ID (from list_types)"},
                    "description": {"type": "string", "description": "Markdown description"},
                    "assignee_id": {"type": "integer", "description": "User ID to assign to"},
                    "parent_id": {"type": "integer", "description": "Parent work package ID (for subtasks)"},
                    "estimated_hours": {"type": "number", "description": "Estimated hours, e.g. 2.5"},
                    "priority_id": {"type": "integer", "description": "Priority ID (from list_priorities)"},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "due_date": {"type": "string", "description": "Due date YYYY-MM-DD"},
                },
                "required": ["project_id", "subject", "type_id"],
            },
        ),
        types.Tool(
            name="update_work_package",
            description="Update a work package. Only provided fields are changed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Work package ID"},
                    "subject": {"type": "string"},
                    "description": {"type": "string", "description": "Markdown description"},
                    "status_id": {"type": "integer", "description": "New status ID (from list_statuses)"},
                    "assignee_id": {"type": "integer", "description": "New assignee user ID"},
                    "percent_done": {"type": "integer", "description": "Completion percentage 0-100"},
                    "estimated_hours": {"type": "number"},
                    "remaining_hours": {"type": "number"},
                    "due_date": {"type": "string", "description": "Due date YYYY-MM-DD"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="get_comments",
            description="Get all comments on a work package.",
            inputSchema={
                "type": "object",
                "properties": {"work_package_id": {"type": "integer", "description": "Work package ID"}},
                "required": ["work_package_id"],
            },
        ),
        types.Tool(
            name="add_comment",
            description="Add a markdown comment to a work package.",
            inputSchema={
                "type": "object",
                "properties": {
                    "work_package_id": {"type": "integer"},
                    "comment": {"type": "string", "description": "Markdown comment text"},
                },
                "required": ["work_package_id", "comment"],
            },
        ),
        types.Tool(
            name="list_users",
            description="List all users including AI agent accounts.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="list_statuses",
            description="List all valid work package statuses with their IDs.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="list_types",
            description="List work package types (Task, Bug, Feature, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Optionally scope to a project"}
                },
                "required": [],
            },
        ),
        types.Tool(
            name="list_priorities",
            description="List work package priorities (Low, Normal, High, Immediate).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="list_relations",
            description=(
                "List relations between work packages with optional filters. "
                "Use involved_id to get all relations of a given work package."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_id": {"type": "integer", "description": "Filter by the work package from which the relation emanates"},
                    "to_id": {"type": "integer", "description": "Filter by the work package to which the relation points"},
                    "involved_id": {"type": "integer", "description": "Filter by a WP that is either from or to"},
                    "relation_type": {
                        "type": "string",
                        "description": "Filter by relation type: relates, duplicates, duplicated, blocks, blocked, precedes, follows, includes, partof, requires, required",
                    },
                    "sort_by": {"type": "string", "description": 'Sort spec JSON, e.g. \'[["type","asc"]]\''},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="create_relation",
            description=(
                "Create a relation between two work packages. "
                "Supported types: relates, duplicates, duplicated, blocks, blocked, "
                "precedes, follows, includes, partof, requires, required."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_id": {"type": "integer", "description": "ID of the work package from which the relation emanates"},
                    "to_id": {"type": "integer", "description": "ID of the work package to which the relation points"},
                    "relation_type": {"type": "string", "description": "Type of relation, e.g. 'blocks', 'precedes', 'relates'"},
                    "description": {"type": "string", "description": "Optional description of the relation"},
                    "lag": {"type": "integer", "description": "Days between closure of `from` and start of `to` (for precedes/follows)"},
                },
                "required": ["from_id", "to_id", "relation_type"],
            },
        ),
        types.Tool(
            name="update_relation",
            description="Update an existing relation (type, description, or lag). Only provided fields are changed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "relation_id": {"type": "integer", "description": "ID of the relation to update"},
                    "relation_type": {"type": "string", "description": "New relation type"},
                    "description": {"type": "string", "description": "New description"},
                    "lag": {"type": "integer", "description": "New lag in days"},
                },
                "required": ["relation_id"],
            },
        ),
        types.Tool(
            name="delete_relation",
            description="Delete a relation between work packages by its relation ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "relation_id": {"type": "integer", "description": "ID of the relation to delete"},
                },
                "required": ["relation_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        match name:
            case "list_projects":
                return ok(projects.list_projects(client))
            case "get_project":
                return ok(projects.get_project(client, arguments["id"]))
            case "list_work_packages":
                return ok(work_packages.list_work_packages(client, **arguments))
            case "get_work_package":
                return ok(work_packages.get_work_package(client, arguments["id"]))
            case "create_work_package":
                return ok(work_packages.create_work_package(client, **arguments))
            case "update_work_package":
                return ok(work_packages.update_work_package(client, **arguments))
            case "get_comments":
                return ok(work_packages.get_comments(client, arguments["work_package_id"]))
            case "add_comment":
                return ok(work_packages.add_comment(client, **arguments))
            case "list_users":
                return ok(users.list_users(client))
            case "list_statuses":
                return ok(meta.list_statuses(client))
            case "list_types":
                return ok(meta.list_types(client, arguments.get("project_id")))
            case "list_priorities":
                return ok(meta.list_priorities(client))
            case "list_relations":
                return ok(work_packages.list_relations(client, **arguments))
            case "create_relation":
                return ok(work_packages.create_relation(client, **arguments))
            case "update_relation":
                return ok(work_packages.update_relation(client, **arguments))
            case "delete_relation":
                return ok(work_packages.delete_relation(client, arguments["relation_id"]))
            case _:
                return err(ValueError(f"Unknown tool: {name}"))
    except Exception as e:
        return err(e)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
