"""Meta tools: statuses, types, priorities."""

from openproject_mcp.client import OpenProjectClient


def list_statuses(client: OpenProjectClient) -> list[dict]:
    """List all work package statuses."""
    statuses = client.get_all("statuses")
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "is_closed": s.get("isClosed", False),
            "is_default": s.get("isDefault", False),
        }
        for s in statuses
    ]


def list_types(client: OpenProjectClient, project_id: str | int | None = None) -> list[dict]:
    """List work package types, optionally scoped to a project."""
    path = f"projects/{project_id}/types" if project_id else "types"
    types = client.get_all(path)
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "color": t.get("color", ""),
            "is_milestone": t.get("isMilestone", False),
        }
        for t in types
    ]


def list_priorities(client: OpenProjectClient) -> list[dict]:
    """List all work package priorities."""
    priorities = client.get_all("priorities")
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "is_default": p.get("isDefault", False),
        }
        for p in priorities
    ]
