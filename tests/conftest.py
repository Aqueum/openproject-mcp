"""Shared fixtures and helpers for all tests."""

import pytest
from openproject_mcp.client import OpenProjectClient

BASE_URL = "http://test.openproject.local"
API_KEY = "test-api-key"
_API_BASE = f"{BASE_URL}/api/v3"


@pytest.fixture
def client():
    return OpenProjectClient(base_url=BASE_URL, api_key=API_KEY)


@pytest.fixture
def api_url():
    """Return a helper that builds a full API URL."""
    def _f(path: str) -> str:
        return f"{_API_BASE}/{path.lstrip('/')}"
    return _f


@pytest.fixture
def collection():
    """Return a helper that wraps a list into a HAL collection payload."""
    def _f(elements: list, total: int | None = None) -> dict:
        n = len(elements)
        return {
            "_embedded": {"elements": elements},
            "total": total if total is not None else n,
            "count": n,
        }
    return _f


@pytest.fixture
def wp_factory():
    """Return a factory that builds realistic work package API payloads."""
    def _f(
        id: int = 1,
        subject: str = "Test WP",
        status: str = "New",
        type_: str = "Task",
        lock_version: int = 0,
        parent_href: str = "",
    ) -> dict:
        return {
            "id": id,
            "subject": subject,
            "description": {"raw": "Some description", "format": "markdown"},
            "percentageDone": 25,
            "estimatedTime": "PT2H0M",
            "remainingTime": "PT1H0M",
            "spentTime": "PT0H30M",
            "startDate": "2024-01-01",
            "dueDate": "2024-01-31",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
            "lockVersion": lock_version,
            "_links": {
                "status": {"title": status, "href": "/api/v3/statuses/1"},
                "type": {"title": type_, "href": "/api/v3/types/1"},
                "priority": {"title": "Normal", "href": "/api/v3/priorities/2"},
                "assignee": {"title": "Alice", "href": "/api/v3/users/5"},
                "author": {"title": "Bob", "href": "/api/v3/users/3"},
                "project": {"title": "My Project", "href": "/api/v3/projects/1"},
                "parent": {"href": parent_href},
            },
        }
    return _f
