"""Work package MCP tools — the core of agentic project management."""

from datetime import datetime, timezone
from typing import Any

from openproject_mcp.client import OpenProjectClient


def _format_wp(wp: dict) -> dict:
    """Extract the most useful fields from a work package API response."""
    links = wp.get("_links", {})
    return {
        "id": wp["id"],
        "subject": wp["subject"],
        "description": wp.get("description", {}).get("raw", ""),
        "status": links.get("status", {}).get("title", ""),
        "type": links.get("type", {}).get("title", ""),
        "priority": links.get("priority", {}).get("title", ""),
        "assignee": links.get("assignee", {}).get("title", ""),
        "author": links.get("author", {}).get("title", ""),
        "project": links.get("project", {}).get("title", ""),
        "parent_id": _extract_id(links.get("parent", {}).get("href", "")),
        "category_id": _extract_id(links.get("category", {}).get("href", "")),
        "category": links.get("category", {}).get("title", ""),
        "percent_done": wp.get("percentageDone", 0),
        "estimated_hours": wp.get("estimatedTime"),
        "remaining_hours": wp.get("remainingTime"),
        "spent_hours": wp.get("spentTime"),
        "start_date": wp.get("startDate", ""),
        "due_date": wp.get("dueDate", ""),
        "created_at": wp.get("createdAt", ""),
        "updated_at": wp.get("updatedAt", ""),
    }


def _extract_id(href: str) -> int | None:
    """Extract numeric ID from an API href like /api/v3/work_packages/42."""
    if href:
        parts = href.rstrip("/").split("/")
        try:
            return int(parts[-1])
        except ValueError:
            pass
    return None


def list_work_packages(
    client: OpenProjectClient,
    project_id: str | int | None = None,
    assignee_id: str | int | None = None,
    status: str | None = None,
    type_name: str | None = None,
    stale_days: int | None = None,
) -> list[dict]:
    """
    List work packages with optional filters.

    - project_id: filter to a specific project
    - assignee_id: filter by assignee user ID (use 'me' for current user)
    - status: filter by status name (e.g. 'New', 'In progress', 'Closed')
    - type_name: filter by type name (e.g. 'Task', 'Bug', 'Feature')
    - stale_days: only return WPs not updated in this many days
    """
    filters = []

    if assignee_id:
        filters.append({"assignee": {"operator": "=", "values": [str(assignee_id)]}})

    if status:
        filters.append({"status": {"operator": "=", "values": [status]}})

    if type_name:
        filters.append({"type": {"operator": "=", "values": [type_name]}})

    if stale_days:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        filters.append({"updatedAt": {"operator": "<>d", "values": [cutoff, ""]}})

    params: dict[str, Any] = {}
    if filters:
        import json
        params["filters"] = json.dumps(filters)

    path = f"projects/{project_id}/work_packages" if project_id else "work_packages"
    wps = client.get_all(path, params)
    return [_format_wp(wp) for wp in wps]


def get_work_package(client: OpenProjectClient, id: int) -> dict:
    """Get full details of a work package including subtasks and comments."""
    wp = client.get(f"work_packages/{id}")
    result = _format_wp(wp)

    # Fetch children (subtasks)
    try:
        children_data = client.get(f"work_packages/{id}/children")
        children = children_data.get("_embedded", {}).get("elements", [])
        result["children"] = [
            {"id": c["id"], "subject": c["subject"], "status": c.get("_links", {}).get("status", {}).get("title", "")}
            for c in children
        ]
    except Exception as e:
        result["children"] = []
        result["children_error"] = str(e)

    # Fetch activities (comments + history)
    try:
        result["comments"] = _fetch_comments(client, id)
    except Exception as e:
        result["comments"] = []
        result["comments_error"] = str(e)

    return result


def _fetch_comments(client: OpenProjectClient, id: int) -> list[dict]:
    """Fetch comments (non-empty activities) for a work package."""
    activities_data = client.get(f"work_packages/{id}/activities")
    activities = activities_data.get("_embedded", {}).get("elements", [])
    return [
        {
            "id": a["id"],
            "author": a.get("_links", {}).get("user", {}).get("title", ""),
            "comment": a.get("comment", {}).get("raw", ""),
            "created_at": a.get("createdAt", ""),
        }
        for a in activities
        if a.get("comment", {}).get("raw")
    ]


def get_comments(client: OpenProjectClient, work_package_id: int) -> list[dict]:
    """Get all comments on a work package."""
    return _fetch_comments(client, work_package_id)


def create_work_package(
    client: OpenProjectClient,
    project_id: str | int,
    subject: str,
    type_id: int,
    description: str = "",
    assignee_id: int | None = None,
    parent_id: int | None = None,
    category_id: int | None = None,
    estimated_hours: float | None = None,
    priority_id: int | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
) -> dict:
    """
    Create a new work package (task, subtask, bug, etc.).

    - parent_id: set to make this a subtask of another work package
    - category_id: get valid IDs from list_categories()
    - type_id: get valid IDs from list_types()
    - estimated_hours: e.g. 2.5 for 2h 30m
    """
    data: dict[str, Any] = {
        "subject": subject,
        "description": {"format": "markdown", "raw": description},
        "_links": {
            "project": {"href": f"/api/v3/projects/{project_id}"},
            "type": {"href": f"/api/v3/types/{type_id}"},
        },
    }

    if assignee_id:
        data["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
    if parent_id:
        data["_links"]["parent"] = {"href": f"/api/v3/work_packages/{parent_id}"}
    if category_id:
        data["_links"]["category"] = {"href": f"/api/v3/categories/{category_id}"}
    if priority_id:
        data["_links"]["priority"] = {"href": f"/api/v3/priorities/{priority_id}"}
    if estimated_hours is not None:
        data["estimatedTime"] = f"PT{int(estimated_hours)}H{int((estimated_hours % 1) * 60)}M"
    if start_date:
        data["startDate"] = start_date
    if due_date:
        data["dueDate"] = due_date

    wp = client.post("work_packages", data)
    return _format_wp(wp)


def update_work_package(
    client: OpenProjectClient,
    id: int,
    subject: str | None = None,
    description: str | None = None,
    status_id: int | None = None,
    assignee_id: int | None = None,
    category_id: int | None = None,
    percent_done: int | None = None,
    estimated_hours: float | None = None,
    remaining_hours: float | None = None,
    due_date: str | None = None,
) -> dict:
    """
    Update a work package. Only provided fields are changed.

    - status_id: get valid IDs from list_statuses()
    - category_id: get valid IDs from list_categories()
    - percent_done: 0-100
    """
    # Must include lockVersion to avoid conflict errors
    current = client.get(f"work_packages/{id}")
    data: dict[str, Any] = {"lockVersion": current["lockVersion"], "_links": {}}

    if subject is not None:
        data["subject"] = subject
    if description is not None:
        data["description"] = {"format": "markdown", "raw": description}
    if status_id is not None:
        data["_links"]["status"] = {"href": f"/api/v3/statuses/{status_id}"}
    if assignee_id is not None:
        data["_links"]["assignee"] = {"href": f"/api/v3/users/{assignee_id}"}
    if category_id is not None:
        data["_links"]["category"] = {"href": f"/api/v3/categories/{category_id}"}
    if percent_done is not None:
        data["percentageDone"] = percent_done
    if estimated_hours is not None:
        data["estimatedTime"] = f"PT{int(estimated_hours)}H{int((estimated_hours % 1) * 60)}M"
    if remaining_hours is not None:
        data["remainingTime"] = f"PT{int(remaining_hours)}H{int((remaining_hours % 1) * 60)}M"
    if due_date is not None:
        data["dueDate"] = due_date

    wp = client.patch(f"work_packages/{id}", data)
    return _format_wp(wp)


def add_comment(client: OpenProjectClient, work_package_id: int, comment: str) -> dict:
    """Add a comment to a work package."""
    data = {"comment": {"format": "markdown", "raw": comment}}
    result = client.post(f"work_packages/{work_package_id}/activities", data)
    return {
        "id": result["id"],
        "comment": result.get("comment", {}).get("raw", ""),
        "created_at": result.get("createdAt", ""),
    }
