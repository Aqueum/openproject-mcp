"""Time entry MCP tools."""

import json
from typing import Any

from openproject_mcp.client import OpenProjectClient


def _hours_to_iso8601(hours: float) -> str:
    """Convert decimal hours to ISO 8601 duration (e.g. 1.5 → PT1H30M)."""
    total_minutes = round(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    if m:
        return f"PT{h}H{m}M"
    return f"PT{h}H"


def list_activities(client: OpenProjectClient) -> list[dict]:
    """List all time entry activity types with id, name, and href."""
    data = client.get("time_entries/activities")
    activities = data.get("_embedded", {}).get("elements", [])
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "href": a.get("_links", {}).get("self", {}).get("href", f"/api/v3/time_entries/activities/{a['id']}"),
        }
        for a in activities
    ]


def create_time_entry(
    client: OpenProjectClient,
    work_package_id: int,
    hours: float,
    spent_on: str,
    activity_id: int,
    comment: str = "",
    user_id: int | None = None,
) -> dict:
    """
    Create a time entry for a work package.

    - hours: decimal hours, e.g. 1.5 for 1h 30m
    - spent_on: date string YYYY-MM-DD
    - activity_id: get valid IDs from list_activities()
    """
    data: dict[str, Any] = {
        "hours": _hours_to_iso8601(hours),
        "spentOn": spent_on,
        "_links": {
            "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"},
            "activity": {"href": f"/api/v3/time_entries/activities/{activity_id}"},
        },
    }
    if comment:
        data["comment"] = {"format": "plain", "raw": comment}
    if user_id is not None:
        data["_links"]["user"] = {"href": f"/api/v3/users/{user_id}"}

    result = client.post("time_entries", data)
    links = result.get("_links", {})
    return {
        "id": result["id"],
        "hours": result.get("hours"),
        "spentOn": result.get("spentOn"),
        "work_package_subject": links.get("workPackage", {}).get("title", ""),
    }


def list_time_entries(
    client: OpenProjectClient,
    work_package_id: int | None = None,
    limit: int = 25,
) -> list[dict]:
    """
    List time entries, optionally filtered by work package.

    - work_package_id: filter to a specific work package
    - limit: maximum entries to return (default 25)
    """
    params: dict[str, Any] = {"pageSize": limit}

    if work_package_id is not None:
        filters = [{"work_package": {"operator": "=", "values": [str(work_package_id)]}}]
        params["filters"] = json.dumps(filters)

    data = client.get("time_entries", params)
    entries = data.get("_embedded", {}).get("elements", [])

    return [
        {
            "id": e["id"],
            "hours": e.get("hours"),
            "spentOn": e.get("spentOn"),
            "activity": e.get("_links", {}).get("activity", {}).get("title", ""),
            "comment": e.get("comment", {}).get("raw", ""),
            "work_package_subject": e.get("_links", {}).get("workPackage", {}).get("title", ""),
        }
        for e in entries
    ]
