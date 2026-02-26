"""Project-related MCP tools."""

from openproject_mcp.client import OpenProjectClient


def list_projects(client: OpenProjectClient) -> list[dict]:
    """List all accessible projects."""
    projects = client.get_all("projects")
    return [
        {
            "id": p["id"],
            "identifier": p["identifier"],
            "name": p["name"],
            "description": p.get("description", {}).get("raw", ""),
            "status": p.get("status", ""),
            "active": p.get("active", True),
            "public": p.get("public", False),
        }
        for p in projects
    ]


def get_project(client: OpenProjectClient, id: str | int) -> dict:
    """Get details of a specific project by id or identifier."""
    p = client.get(f"projects/{id}")
    return {
        "id": p["id"],
        "identifier": p["identifier"],
        "name": p["name"],
        "description": p.get("description", {}).get("raw", ""),
        "status": p.get("status", ""),
        "active": p.get("active", True),
        "public": p.get("public", False),
        "created_at": p.get("createdAt", ""),
        "updated_at": p.get("updatedAt", ""),
    }
