"""Tests for user tools."""

import responses

from openproject_mcp.tools.users import list_users


@responses.activate
def test_list_users(client, api_url, collection):
    payload = [
        {"id": 1, "login": "alice", "name": "Alice Smith",
         "email": "alice@example.com", "status": "active", "avatar": ""},
        {"id": 2, "login": "bot", "name": "AI Agent",
         "email": "", "status": "active", "avatar": ""},
    ]
    responses.add(responses.GET, api_url("users"), json=collection(payload))

    result = list_users(client)

    assert len(result) == 2
    assert result[0] == {
        "id": 1, "login": "alice", "name": "Alice Smith",
        "email": "alice@example.com", "status": "active", "avatar": "",
    }


@responses.activate
def test_list_users_empty(client, api_url, collection):
    responses.add(responses.GET, api_url("users"), json=collection([]))
    assert list_users(client) == []


@responses.activate
def test_list_users_missing_optional_fields(client, api_url, collection):
    responses.add(responses.GET, api_url("users"), json=collection([{"id": 3}]))

    result = list_users(client)

    u = result[0]
    assert u["login"] == ""
    assert u["name"] == ""
    assert u["email"] == ""
    assert u["status"] == ""
    assert u["avatar"] == ""
