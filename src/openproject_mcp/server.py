"""MCP server — registers all OpenProject tools."""

import json
import os
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from openproject_mcp.client import OpenProjectClient
from openproject_mcp.tools import projects, work_packages, users, meta, time_entries

server = Server("openproject")
client = OpenProjectClient()


def ok(data) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


def err(e: Exception) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=f"Error: {e}")]


def _delete_enabled() -> bool:
    return os.getenv("OPENPROJECT_ALLOW_DELETE", "").lower() in ("true", "1", "yes")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = [
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
                    "priority_id": {"type": "integer", "description": "New priority ID (from list_priorities)"},
                    "percent_done": {"type": "integer", "description": "Completion percentage 0-100"},
                    "estimated_hours": {"type": "number"},
                    "remaining_hours": {"type": "number"},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD, or empty string to clear"},
                    "due_date": {"type": "string", "description": "Due date YYYY-MM-DD, or empty string to clear"},
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
            name="get_work_package_relations",
            description="Get all relations for a work package (blocks, follows, relates, duplicates, etc.).",
            inputSchema={
                "type": "object",
                "properties": {"work_package_id": {"type": "integer", "description": "Work package ID"}},
                "required": ["work_package_id"],
            },
        ),
        types.Tool(
            name="create_relation",
            description=(
                "Create a relation from one work package to another. "
                "relation_type is one of: relates, duplicates, duplicated, "
                "blocks, blocked, precedes, follows, includes, partof, "
                "requires, required."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_work_package_id": {"type": "integer", "description": "Source work package ID"},
                    "to_work_package_id": {"type": "integer", "description": "Target work package ID"},
                    "relation_type": {"type": "string", "description": "Relation type name"},
                },
                "required": ["from_work_package_id", "to_work_package_id", "relation_type"],
            },
        ),
        types.Tool(
            name="update_relation",
            description=(
                "Update a relation by ID. Provide description and/or "
                "relation_type — only provided fields are changed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "relation_id": {"type": "integer", "description": "Relation ID"},
                    "description": {"type": "string", "description": "New description"},
                    "relation_type": {"type": "string", "description": "New relation type (see create_relation)"},
                },
                "required": ["relation_id"],
            },
        ),
        types.Tool(
            name="delete_relation",
            description="Delete a work package relation by ID.",
            inputSchema={
                "type": "object",
                "properties": {"relation_id": {"type": "integer", "description": "Relation ID"}},
                "required": ["relation_id"],
            },
        ),
        types.Tool(
            name="get_work_package_attachments",
            description="Get all attachments for a work package (filename, download URL, file size, created_at).",
            inputSchema={
                "type": "object",
                "properties": {"work_package_id": {"type": "integer", "description": "Work package ID"}},
                "required": ["work_package_id"],
            },
        ),
        types.Tool(
            name="get_attachment_content",
            description=(
                "Fetch the content of an attachment by its ID. "
                "Returns decoded text for text-based files (plain, markdown, JSON, HTML, CSV). "
                "Returns a binary notice with filename and size for images, PDFs, and other binary formats."
            ),
            inputSchema={
                "type": "object",
                "properties": {"attachment_id": {"type": "integer", "description": "Attachment ID"}},
                "required": ["attachment_id"],
            },
        ),
        types.Tool(
            name="list_activities",
            description="List all time entry activity types (id, name, href). Use activity_id when creating time entries.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="create_time_entry",
            description="Log time against a work package. Use list_activities to get a valid activity_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "work_package_id": {"type": "string", "description": "Work package ID"},
                    "hours": {"type": "string", "description": "Decimal hours, e.g. 1.5 for 1h 30m"},
                    "spent_on": {"type": "string", "description": "Date YYYY-MM-DD"},
                    "activity_id": {"type": "string", "description": "Activity ID from list_activities"},
                    "comment": {"type": "string", "description": "Optional comment"},
                    "user_id": {"type": "string", "description": "User ID to log time on behalf of"},
                },
                "required": ["work_package_id", "hours", "spent_on"],
            },
        ),
        types.Tool(
            name="list_time_entries",
            description="List time entries, optionally filtered by work package.",
            inputSchema={
                "type": "object",
                "properties": {
                    "work_package_id": {"type": "string", "description": "Filter by work package ID"},
                    "limit": {"type": "string", "description": "Maximum entries to return (default 25)"},
                },
                "required": [],
            },
        ),
    ]
    if _delete_enabled():
        tools.append(types.Tool(
            name="delete_work_package",
            description=(
                "PERMANENTLY delete a work package by ID. Irreversible — no "
                "soft delete, no undo. Requires confirm=true at the call "
                "site; the tool is only registered when "
                "OPENPROJECT_ALLOW_DELETE=true in the MCP server environment."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Work package ID"},
                    "confirm": {"type": "boolean", "description": "Must be true to proceed"},
                },
                "required": ["id", "confirm"],
            },
        ))
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        match name:
            case "list_projects":
                return ok(projects.list_projects(client))
            case "get_project":
                return ok(projects.get_project(client, arguments["id"]))
            case "list_work_packages":
                args = dict(arguments)
                if "stale_days" in args:
                    args["stale_days"] = int(args["stale_days"])
                return ok(work_packages.list_work_packages(client, **args))
            case "get_work_package":
                return ok(work_packages.get_work_package(client, int(arguments["id"])))
            case "create_work_package":
                args = dict(arguments)
                args["type_id"] = int(args["type_id"])
                if "assignee_id" in args:
                    args["assignee_id"] = int(args["assignee_id"])
                if "parent_id" in args:
                    args["parent_id"] = int(args["parent_id"])
                if "estimated_hours" in args:
                    args["estimated_hours"] = float(args["estimated_hours"])
                if "priority_id" in args:
                    args["priority_id"] = int(args["priority_id"])
                return ok(work_packages.create_work_package(client, **args))
            case "update_work_package":
                args = dict(arguments)
                args["id"] = int(args["id"])
                if "status_id" in args:
                    args["status_id"] = int(args["status_id"])
                if "assignee_id" in args:
                    args["assignee_id"] = int(args["assignee_id"])
                if "priority_id" in args:
                    args["priority_id"] = int(args["priority_id"])
                if "percent_done" in args:
                    args["percent_done"] = int(args["percent_done"])
                if "estimated_hours" in args:
                    args["estimated_hours"] = float(args["estimated_hours"])
                if "remaining_hours" in args:
                    args["remaining_hours"] = float(args["remaining_hours"])
                return ok(work_packages.update_work_package(client, **args))
            case "get_comments":
                return ok(work_packages.get_comments(client, int(arguments["work_package_id"])))
            case "add_comment":
                return ok(work_packages.add_comment(client, int(arguments["work_package_id"]), arguments["comment"]))
            case "list_users":
                return ok(users.list_users(client))
            case "list_statuses":
                return ok(meta.list_statuses(client))
            case "list_types":
                return ok(meta.list_types(client, arguments.get("project_id")))
            case "list_priorities":
                return ok(meta.list_priorities(client))
            case "get_work_package_relations":
                return ok(work_packages.get_work_package_relations(client, int(arguments["work_package_id"])))
            case "create_relation":
                return ok(work_packages.create_relation(
                    client,
                    from_work_package_id=int(arguments["from_work_package_id"]),
                    to_work_package_id=int(arguments["to_work_package_id"]),
                    relation_type=arguments["relation_type"],
                ))
            case "update_relation":
                return ok(work_packages.update_relation(
                    client,
                    relation_id=int(arguments["relation_id"]),
                    description=arguments.get("description"),
                    relation_type=arguments.get("relation_type"),
                ))
            case "delete_relation":
                return ok(work_packages.delete_relation(client, int(arguments["relation_id"])))
            case "get_work_package_attachments":
                return ok(work_packages.get_work_package_attachments(client, int(arguments["work_package_id"])))
            case "get_attachment_content":
                return ok(work_packages.get_attachment_content(client, int(arguments["attachment_id"])))
            case "list_activities":
                return ok(time_entries.list_activities(client))
            case "create_time_entry":
                return ok(time_entries.create_time_entry(
                    client,
                    work_package_id=int(arguments["work_package_id"]),
                    hours=float(arguments["hours"]),
                    spent_on=arguments["spent_on"],
                    activity_id=int(arguments["activity_id"]) if arguments.get("activity_id") is not None else None,
                    comment=arguments.get("comment", ""),
                    user_id=int(arguments["user_id"]) if arguments.get("user_id") is not None else None,
                ))
            case "delete_work_package":
                if not _delete_enabled():
                    return err(RuntimeError(
                        "delete_work_package is disabled. Set OPENPROJECT_ALLOW_DELETE=true "
                        "in the MCP server environment to enable it."
                    ))
                return ok(work_packages.delete_work_package(
                    client,
                    id=int(arguments["id"]),
                    confirm=bool(arguments.get("confirm", False)),
                ))
            case "list_time_entries":
                return ok(time_entries.list_time_entries(
                    client,
                    work_package_id=int(arguments["work_package_id"]) if arguments.get("work_package_id") is not None else None,
                    limit=int(arguments.get("limit", 25)),
                ))
            case _:
                return err(ValueError(f"Unknown tool: {name}"))
    except Exception as e:
        return err(e)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
