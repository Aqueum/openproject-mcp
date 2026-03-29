"""Tests for meta tools (statuses, types, priorities)."""

import responses

from openproject_mcp.tools.meta import list_statuses, list_types, list_priorities


@responses.activate
def test_list_statuses(client, api_url, collection):
    payload = [
        {"id": 1, "name": "New", "isClosed": False, "isDefault": True},
        {"id": 5, "name": "Closed", "isClosed": True, "isDefault": False},
    ]
    responses.add(responses.GET, api_url("statuses"), json=collection(payload))

    result = list_statuses(client)

    assert result == [
        {"id": 1, "name": "New", "is_closed": False, "is_default": True},
        {"id": 5, "name": "Closed", "is_closed": True, "is_default": False},
    ]


@responses.activate
def test_list_statuses_missing_optional_fields(client, api_url, collection):
    responses.add(responses.GET, api_url("statuses"), json=collection([{"id": 1, "name": "New"}]))

    result = list_statuses(client)

    assert result[0]["is_closed"] is False
    assert result[0]["is_default"] is False


@responses.activate
def test_list_types_global(client, api_url, collection):
    payload = [{"id": 1, "name": "Task", "color": "#0000FF", "isMilestone": False}]
    responses.add(responses.GET, api_url("types"), json=collection(payload))

    result = list_types(client)

    assert result == [{"id": 1, "name": "Task", "color": "#0000FF", "is_milestone": False}]


@responses.activate
def test_list_types_scoped_to_project(client, api_url, collection):
    responses.add(responses.GET, api_url("projects/42/types"), json=collection([
        {"id": 2, "name": "Bug", "color": "#FF0000", "isMilestone": False}
    ]))

    result = list_types(client, project_id=42)

    assert result[0]["name"] == "Bug"


@responses.activate
def test_list_priorities(client, api_url, collection):
    payload = [
        {"id": 1, "name": "Low", "isDefault": False},
        {"id": 2, "name": "Normal", "isDefault": True},
    ]
    responses.add(responses.GET, api_url("priorities"), json=collection(payload))

    result = list_priorities(client)

    assert len(result) == 2
    assert result[1] == {"id": 2, "name": "Normal", "is_default": True}
