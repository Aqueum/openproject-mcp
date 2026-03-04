"""Tests for project tools."""

import responses

from openproject_mcp.tools.projects import list_projects, get_project


@responses.activate
def test_list_projects_formats_all_fields(client, api_url, collection):
    payload = [{
        "id": 1, "identifier": "my-project", "name": "My Project",
        "description": {"raw": "A project"}, "status": "active",
        "active": True, "public": False,
    }]
    responses.add(responses.GET, api_url("projects"), json=collection(payload))

    result = list_projects(client)

    assert len(result) == 1
    p = result[0]
    assert p == {
        "id": 1, "identifier": "my-project", "name": "My Project",
        "description": "A project", "status": "active",
        "active": True, "public": False,
    }


@responses.activate
def test_list_projects_empty(client, api_url, collection):
    responses.add(responses.GET, api_url("projects"), json=collection([]))
    assert list_projects(client) == []


@responses.activate
def test_list_projects_missing_optional_fields(client, api_url, collection):
    responses.add(responses.GET, api_url("projects"), json=collection([
        {"id": 2, "identifier": "p2", "name": "P2"}
    ]))

    result = list_projects(client)

    p = result[0]
    assert p["description"] == ""
    assert p["status"] == ""
    assert p["active"] is True
    assert p["public"] is False


@responses.activate
def test_get_project_formats_all_fields(client, api_url):
    payload = {
        "id": 1, "identifier": "my-project", "name": "My Project",
        "description": {"raw": "Desc"}, "status": "active",
        "active": True, "public": True,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-02T00:00:00Z",
    }
    responses.add(responses.GET, api_url("projects/1"), json=payload)

    result = get_project(client, 1)

    assert result["id"] == 1
    assert result["description"] == "Desc"
    assert result["public"] is True
    assert result["created_at"] == "2024-01-01T00:00:00Z"
    assert result["updated_at"] == "2024-01-02T00:00:00Z"


@responses.activate
def test_get_project_by_string_identifier(client, api_url):
    payload = {
        "id": 3, "identifier": "ops", "name": "Ops",
        "active": True, "public": False,
    }
    responses.add(responses.GET, api_url("projects/ops"), json=payload)

    result = get_project(client, "ops")

    assert result["identifier"] == "ops"
