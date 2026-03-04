"""Tests for work package tools."""

import json
from urllib.parse import urlparse, parse_qs

import responses

from openproject_mcp.tools.work_packages import (
    list_work_packages,
    get_work_package,
    create_work_package,
    update_work_package,
    add_comment,
    get_comments,
)


# ---------------------------------------------------------------------------
# list_work_packages
# ---------------------------------------------------------------------------

@responses.activate
def test_list_work_packages_no_filter(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("work_packages"), json=collection([wp_factory()]))
    result = list_work_packages(client)
    assert len(result) == 1
    assert result[0]["subject"] == "Test WP"


@responses.activate
def test_list_work_packages_scoped_to_project(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("projects/42/work_packages"), json=collection([wp_factory()]))
    result = list_work_packages(client, project_id=42)
    assert len(result) == 1


@responses.activate
def test_list_work_packages_filter_assignee(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("work_packages"), json=collection([wp_factory()]))
    list_work_packages(client, assignee_id=7)

    params = parse_qs(urlparse(responses.calls[0].request.url).query)
    filters = json.loads(params["filters"][0])
    assert {"assignee": {"operator": "=", "values": ["7"]}} in filters


@responses.activate
def test_list_work_packages_filter_status_named(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("work_packages"), json=collection([wp_factory()]))
    list_work_packages(client, status="Closed")

    params = parse_qs(urlparse(responses.calls[0].request.url).query)
    filters = json.loads(params["filters"][0])
    assert {"status": {"operator": "=", "values": ["Closed"]}} in filters


@responses.activate
def test_list_work_packages_formats_fields(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("work_packages"), json=collection([wp_factory(id=5, subject="My task")]))
    wp = list_work_packages(client)[0]

    assert wp["id"] == 5
    assert wp["subject"] == "My task"
    assert wp["status"] == "New"
    assert wp["type"] == "Task"
    assert wp["priority"] == "Normal"
    assert wp["assignee"] == "Alice"
    assert wp["author"] == "Bob"
    assert wp["project"] == "My Project"
    assert wp["percent_done"] == 25
    assert wp["parent_id"] is None


@responses.activate
def test_list_work_packages_extracts_parent_id(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("work_packages"), json=collection([
        wp_factory(parent_href="/api/v3/work_packages/10")
    ]))
    assert list_work_packages(client)[0]["parent_id"] == 10


# ---------------------------------------------------------------------------
# get_work_package
# ---------------------------------------------------------------------------

@responses.activate
def test_get_work_package_with_children_and_comments(client, api_url, collection, wp_factory):
    child = {"id": 2, "subject": "Child task", "_links": {"status": {"title": "In progress"}}}
    activity = {
        "id": 99, "comment": {"raw": "Looks good"}, "createdAt": "2024-01-05T00:00:00Z",
        "_links": {"user": {"title": "Alice"}},
    }
    responses.add(responses.GET, api_url("work_packages/1"), json=wp_factory(id=1))
    responses.add(responses.GET, api_url("work_packages/1/children"), json=collection([child]))
    responses.add(responses.GET, api_url("work_packages/1/activities"), json=collection([activity]))

    result = get_work_package(client, 1)

    assert result["id"] == 1
    assert result["children"] == [{"id": 2, "subject": "Child task", "status": "In progress"}]
    assert len(result["comments"]) == 1
    assert result["comments"][0]["comment"] == "Looks good"
    assert result["comments"][0]["author"] == "Alice"


@responses.activate
def test_get_work_package_children_error_is_handled(client, api_url, collection, wp_factory):
    responses.add(responses.GET, api_url("work_packages/1"), json=wp_factory(id=1))
    responses.add(responses.GET, api_url("work_packages/1/children"), status=403)
    responses.add(responses.GET, api_url("work_packages/1/activities"), json=collection([]))

    result = get_work_package(client, 1)

    assert result["children"] == []
    assert "children_error" in result


@responses.activate
def test_get_work_package_filters_empty_comment_activities(client, api_url, collection, wp_factory):
    activities = [
        {"id": 1, "comment": {"raw": ""}, "createdAt": "T1", "_links": {"user": {"title": "A"}}},
        {"id": 2, "comment": {"raw": "Real comment"}, "createdAt": "T2", "_links": {"user": {"title": "B"}}},
        {"id": 3, "createdAt": "T3", "_links": {"user": {"title": "C"}}},  # no comment key
    ]
    responses.add(responses.GET, api_url("work_packages/1"), json=wp_factory(id=1))
    responses.add(responses.GET, api_url("work_packages/1/children"), json=collection([]))
    responses.add(responses.GET, api_url("work_packages/1/activities"), json=collection(activities))

    result = get_work_package(client, 1)

    assert len(result["comments"]) == 1
    assert result["comments"][0]["comment"] == "Real comment"


# ---------------------------------------------------------------------------
# create_work_package
# ---------------------------------------------------------------------------

@responses.activate
def test_create_work_package_minimal(client, api_url, wp_factory):
    responses.add(responses.POST, api_url("work_packages"), json=wp_factory(id=10, subject="New task"))

    result = create_work_package(client, project_id=1, subject="New task", type_id=3)

    assert result["id"] == 10
    body = json.loads(responses.calls[0].request.body)
    assert body["subject"] == "New task"
    assert body["_links"]["project"]["href"] == "/api/v3/projects/1"
    assert body["_links"]["type"]["href"] == "/api/v3/types/3"
    assert "assignee" not in body["_links"]
    assert "parent" not in body["_links"]


@responses.activate
def test_create_work_package_with_optional_fields(client, api_url, wp_factory):
    responses.add(responses.POST, api_url("work_packages"), json=wp_factory())

    create_work_package(
        client, project_id=1, subject="Full task", type_id=3,
        assignee_id=5, parent_id=2, priority_id=4,
        estimated_hours=1.5, start_date="2024-02-01", due_date="2024-02-28",
    )

    body = json.loads(responses.calls[0].request.body)
    assert body["_links"]["assignee"]["href"] == "/api/v3/users/5"
    assert body["_links"]["parent"]["href"] == "/api/v3/work_packages/2"
    assert body["_links"]["priority"]["href"] == "/api/v3/priorities/4"
    assert body["estimatedTime"] == "PT1H30M"
    assert body["startDate"] == "2024-02-01"
    assert body["dueDate"] == "2024-02-28"


@responses.activate
def test_create_work_package_estimated_hours_whole_number(client, api_url, wp_factory):
    responses.add(responses.POST, api_url("work_packages"), json=wp_factory())

    create_work_package(client, project_id=1, subject="X", type_id=1, estimated_hours=3.0)

    body = json.loads(responses.calls[0].request.body)
    assert body["estimatedTime"] == "PT3H0M"


# ---------------------------------------------------------------------------
# update_work_package
# ---------------------------------------------------------------------------

@responses.activate
def test_update_work_package_fetches_lock_version(client, api_url, wp_factory):
    responses.add(responses.GET, api_url("work_packages/1"), json=wp_factory(id=1, lock_version=5))
    responses.add(responses.PATCH, api_url("work_packages/1"), json=wp_factory(id=1))

    update_work_package(client, id=1, subject="Updated")

    body = json.loads(responses.calls[1].request.body)
    assert body["lockVersion"] == 5
    assert body["subject"] == "Updated"


@responses.activate
def test_update_work_package_only_sends_provided_fields(client, api_url, wp_factory):
    responses.add(responses.GET, api_url("work_packages/1"), json=wp_factory(lock_version=0))
    responses.add(responses.PATCH, api_url("work_packages/1"), json=wp_factory())

    update_work_package(client, id=1, status_id=3)

    body = json.loads(responses.calls[1].request.body)
    assert "subject" not in body
    assert body["_links"]["status"]["href"] == "/api/v3/statuses/3"


@responses.activate
def test_update_work_package_percent_done(client, api_url, wp_factory):
    responses.add(responses.GET, api_url("work_packages/1"), json=wp_factory(lock_version=0))
    responses.add(responses.PATCH, api_url("work_packages/1"), json=wp_factory())

    update_work_package(client, id=1, percent_done=75)

    body = json.loads(responses.calls[1].request.body)
    assert body["percentageDone"] == 75


# ---------------------------------------------------------------------------
# add_comment / get_comments
# ---------------------------------------------------------------------------

@responses.activate
def test_add_comment(client, api_url):
    responses.add(responses.POST, api_url("work_packages/1/activities"), json={
        "id": 42, "comment": {"raw": "Hello world"}, "createdAt": "2024-01-10T00:00:00Z",
    })

    result = add_comment(client, work_package_id=1, comment="Hello world")

    assert result == {"id": 42, "comment": "Hello world", "created_at": "2024-01-10T00:00:00Z"}
    body = json.loads(responses.calls[0].request.body)
    assert body["comment"] == {"format": "markdown", "raw": "Hello world"}


@responses.activate
def test_get_comments_filters_empty_and_missing(client, api_url):
    activities = {
        "_embedded": {"elements": [
            {"id": 1, "comment": {"raw": ""}, "createdAt": "T1", "_links": {"user": {"title": "A"}}},
            {"id": 2, "comment": {"raw": "Keep this"}, "createdAt": "T2", "_links": {"user": {"title": "B"}}},
            {"id": 3, "createdAt": "T3", "_links": {"user": {"title": "C"}}},
        ]},
        "total": 3,
    }
    responses.add(responses.GET, api_url("work_packages/7/activities"), json=activities)

    result = get_comments(client, 7)

    assert len(result) == 1
    assert result[0]["id"] == 2
    assert result[0]["comment"] == "Keep this"
    assert result[0]["author"] == "B"
