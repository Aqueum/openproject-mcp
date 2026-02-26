"""User-related MCP tools."""

from openproject_mcp.client import OpenProjectClient


def list_users(client: OpenProjectClient) -> list[dict]:
    """List all users (humans and AI agents)."""
    users = client.get_all("users")
    return [
        {
            "id": u["id"],
            "login": u.get("login", ""),
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "status": u.get("status", ""),
            "avatar": u.get("avatar", ""),
        }
        for u in users
    ]
