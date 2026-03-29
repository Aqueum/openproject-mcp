"""Unit tests for time entry tools."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import pytest
from unittest.mock import MagicMock

from openproject_mcp.tools.time_entries import (
    _hours_to_iso8601,
    list_activities,
    create_time_entry,
    list_time_entries,
)


# ---------------------------------------------------------------------------
# _hours_to_iso8601
# ---------------------------------------------------------------------------

class TestHoursToIso8601:
    def test_whole_hours(self):
        assert _hours_to_iso8601(2.0) == "PT2H"

    def test_half_hour(self):
        assert _hours_to_iso8601(1.5) == "PT1H30M"

    def test_quarter_hour(self):
        assert _hours_to_iso8601(0.25) == "PT0H15M"

    def test_minutes_only(self):
        assert _hours_to_iso8601(0.5) == "PT0H30M"

    def test_fractional_rounding(self):
        # 1 hour 6 minutes = 1.1 hours
        assert _hours_to_iso8601(1.1) == "PT1H6M"


# ---------------------------------------------------------------------------
# list_activities
# ---------------------------------------------------------------------------

def _make_client_with_get(return_value):
    client = MagicMock()
    client.get.return_value = return_value
    return client


class TestListActivities:
    def test_returns_activities(self):
        client = _make_client_with_get({
            "_embedded": {
                "elements": [
                    {"id": 1, "name": "Development", "_links": {"self": {"href": "/api/v3/time_entries/activities/1"}}},
                    {"id": 2, "name": "Testing", "_links": {"self": {"href": "/api/v3/time_entries/activities/2"}}},
                ]
            }
        })
        result = list_activities(client)
        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "Development", "href": "/api/v3/time_entries/activities/1"}
        assert result[1] == {"id": 2, "name": "Testing", "href": "/api/v3/time_entries/activities/2"}
        client.get.assert_called_once_with("time_entries/activities")

    def test_empty_collection(self):
        client = _make_client_with_get({"_embedded": {"elements": []}})
        assert list_activities(client) == []

    def test_fallback_href_when_no_self_link(self):
        client = _make_client_with_get({
            "_embedded": {"elements": [{"id": 5, "name": "Other", "_links": {}}]}
        })
        result = list_activities(client)
        assert result[0]["href"] == "/api/v3/time_entries/activities/5"


# ---------------------------------------------------------------------------
# create_time_entry
# ---------------------------------------------------------------------------

class TestCreateTimeEntry:
    def _make_post_response(self):
        return {
            "id": 42,
            "hours": "PT1H30M",
            "spentOn": "2026-03-28",
            "_links": {
                "workPackage": {"href": "/api/v3/work_packages/7", "title": "Fix login bug"},
                "activity": {"href": "/api/v3/time_entries/activities/1", "title": "Development"},
            },
        }

    def test_creates_entry_with_required_fields(self):
        client = MagicMock()
        client.post.return_value = self._make_post_response()

        result = create_time_entry(client, work_package_id=7, hours=1.5, spent_on="2026-03-28", activity_id=1)

        assert result["id"] == 42
        assert result["hours"] == "PT1H30M"
        assert result["spentOn"] == "2026-03-28"
        assert result["work_package_subject"] == "Fix login bug"

    def test_request_body_uses_links_format(self):
        client = MagicMock()
        client.post.return_value = self._make_post_response()

        create_time_entry(client, work_package_id=7, hours=1.5, spent_on="2026-03-28", activity_id=1)

        call_args = client.post.call_args
        path, body = call_args[0]
        assert path == "time_entries"
        assert body["hours"] == "PT1H30M"
        assert body["_links"]["workPackage"]["href"] == "/api/v3/work_packages/7"
        assert body["_links"]["activity"]["href"] == "/api/v3/time_entries/activities/1"

    def test_comment_is_included_when_provided(self):
        client = MagicMock()
        client.post.return_value = self._make_post_response()

        create_time_entry(client, work_package_id=7, hours=1.0, spent_on="2026-03-28", activity_id=1, comment="Design review")

        body = client.post.call_args[0][1]
        assert body["comment"] == {"format": "plain", "raw": "Design review"}

    def test_no_comment_key_when_empty(self):
        client = MagicMock()
        client.post.return_value = self._make_post_response()

        create_time_entry(client, work_package_id=7, hours=1.0, spent_on="2026-03-28", activity_id=1)

        body = client.post.call_args[0][1]
        assert "comment" not in body

    def test_user_link_included_when_user_id_provided(self):
        client = MagicMock()
        client.post.return_value = self._make_post_response()

        create_time_entry(client, work_package_id=7, hours=1.0, spent_on="2026-03-28", activity_id=1, user_id=42)

        body = client.post.call_args[0][1]
        assert body["_links"]["user"] == {"href": "/api/v3/users/42"}


# ---------------------------------------------------------------------------
# list_time_entries
# ---------------------------------------------------------------------------

class TestListTimeEntries:
    def _make_response(self):
        return {
            "_embedded": {
                "elements": [
                    {
                        "id": 10,
                        "hours": "PT2H",
                        "spentOn": "2026-03-27",
                        "comment": {"raw": "Implemented feature"},
                        "_links": {
                            "activity": {"title": "Development"},
                            "workPackage": {"title": "Add login"},
                        },
                    }
                ]
            }
        }

    def test_returns_entries(self):
        client = _make_client_with_get(self._make_response())
        result = list_time_entries(client)

        assert len(result) == 1
        entry = result[0]
        assert entry["id"] == 10
        assert entry["hours"] == "PT2H"
        assert entry["spentOn"] == "2026-03-27"
        assert entry["activity"] == "Development"
        assert entry["comment"] == "Implemented feature"
        assert entry["work_package_subject"] == "Add login"

    def test_no_filter_when_no_work_package_id(self):
        client = _make_client_with_get({"_embedded": {"elements": []}})
        list_time_entries(client)

        call_params = client.get.call_args[0][1]
        assert "filters" not in call_params

    def test_filter_applied_when_work_package_id_given(self):
        client = _make_client_with_get({"_embedded": {"elements": []}})
        list_time_entries(client, work_package_id=99)

        call_params = client.get.call_args[0][1]
        filters = json.loads(call_params["filters"])
        assert filters[0]["work_package"]["operator"] == "="
        assert filters[0]["work_package"]["values"] == ["99"]

    def test_default_limit_is_25(self):
        client = _make_client_with_get({"_embedded": {"elements": []}})
        list_time_entries(client)

        call_params = client.get.call_args[0][1]
        assert call_params["pageSize"] == 25

    def test_custom_limit(self):
        client = _make_client_with_get({"_embedded": {"elements": []}})
        list_time_entries(client, limit=10)

        call_params = client.get.call_args[0][1]
        assert call_params["pageSize"] == 10
