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
    estimated_hours: float | None = None,
    priority_id: int | None = None,
    start_date: str | None = None,
    due_date: str | None = None,
) -> dict:
    """
    Create a new work package (task, subtask, bug, etc.).

    - parent_id: set to make this a subtask of another work package
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
    percent_done: int | None = None,
    estimated_hours: float | None = None,
    remaining_hours: float | None = None,
    due_date: str | None = None,
) -> dict:
    """
    Update a work package. Only provided fields are changed.

    - status_id: get valid IDs from list_statuses()
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


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

RELATION_TYPES = (
    "relates",
    "duplicates",
    "duplicated",
    "blocks",
    "blocked",
    "precedes",
    "follows",
    "includes",
    "partof",
    "requires",
    "required",
)


def _format_relation(rel: dict) -> dict:
    links = rel.get("_links", {})
    return {
        "id": rel["id"],
        "type": rel.get("type", ""),
        "reverse_type": rel.get("reverseType", ""),
        "description": rel.get("description", ""),
        "lag": rel.get("lag", 0),
        "from_id": _extract_id(links.get("from", {}).get("href", "")),
        "from_subject": links.get("from", {}).get("title", ""),
        "to_id": _extract_id(links.get("to", {}).get("href", "")),
        "to_subject": links.get("to", {}).get("title", ""),
    }


def list_relations(
    client: OpenProjectClient,
    from_id: int | None = None,
    to_id: int | None = None,
    involved_id: int | None = None,
    relation_type: str | None = None,
    sort_by: str | None = None,
) -> list[dict]:
    """
    List relations with optional filters.

    - from_id: filter by the work package from which the relation emanates
    - to_id: filter by the work package to which the relation points
    - involved_id: filter by a WP that is either from or to
    - relation_type: filter by type, e.g. 'blocks', 'precedes', 'relates'
    - sort_by: JSON sort spec, e.g. '[["type","asc"]]'
    """
    import json

    filters = []
    if from_id is not None:
        filters.append({"from": {"operator": "=", "values": [str(from_id)]}})
    if to_id is not None:
        filters.append({"to": {"operator": "=", "values": [str(to_id)]}})
    if involved_id is not None:
        filters.append({"involved": {"operator": "=", "values": [str(involved_id)]}})
    if relation_type is not None:
        filters.append({"type": {"operator": "=", "values": [relation_type]}})

    params: dict[str, Any] = {}
    if filters:
        params["filters"] = json.dumps(filters)
    if sort_by:
        params["sortBy"] = sort_by

    rels = client.get_all("relations", params)
    return [_format_relation(r) for r in rels]


def create_relation(
    client: OpenProjectClient,
    from_id: int,
    to_id: int,
    relation_type: str,
    description: str = "",
    lag: int = 0,
) -> dict:
    """
    Create a relation between two work packages.

    - relation_type: one of relates, duplicates, duplicated, blocks, blocked,
                     precedes, follows, includes, partof, requires, required
    - lag: days between the closure of `from` and the start of `to` (precedes/follows)
    """
    data: dict[str, Any] = {
        "type": relation_type,
        "description": description,
        "lag": lag,
        "_links": {
            "from": {"href": f"/api/v3/work_packages/{from_id}"},
            "to": {"href": f"/api/v3/work_packages/{to_id}"},
        },
    }
    result = client.post(f"work_packages/{from_id}/relations", data)
    return _format_relation(result)


def update_relation(
    client: OpenProjectClient,
    relation_id: int,
    relation_type: str | None = None,
    description: str | None = None,
    lag: int | None = None,
) -> dict:
    """
    Update an existing relation. Only provided fields are changed.

    - relation_type: new type, e.g. 'blocks'
    - lag: new lag in days
    """
    data: dict[str, Any] = {}
    if relation_type is not None:
        data["type"] = relation_type
    if description is not None:
        data["description"] = description
    if lag is not None:
        data["lag"] = lag

    result = client.patch(f"relations/{relation_id}", data)
    return _format_relation(result)


def delete_relation(client: OpenProjectClient, relation_id: int) -> dict:
    """Delete a relation by its ID."""
    client.delete(f"relations/{relation_id}")
    return {"deleted": True, "relation_id": relation_id}
