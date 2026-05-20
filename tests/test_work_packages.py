"""Unit tests for work package tools (update priority, relations write)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from unittest.mock import MagicMock

from openproject_mcp.tools.work_packages import (
    update_work_package,
    create_relation,
    update_relation,
    delete_relation,
)


def _wp_response(wp_id: int = 1, lock: int = 3) -> dict:
    return {
        "id": wp_id,
        "subject": "S",
        "description": {"raw": ""},
        "lockVersion": lock,
        "percentageDone": 0,
        "_links": {},
    }


# ---------------------------------------------------------------------------
# update_work_package — priority_id
# ---------------------------------------------------------------------------

class TestUpdateWorkPackagePriority:
    def test_priority_link_set_when_priority_id_provided(self):
        client = MagicMock()
        client.get.return_value = _wp_response()
        client.patch.return_value = _wp_response()

        update_work_package(client, id=1, priority_id=7)

        body = client.patch.call_args[0][1]
        assert body["_links"]["priority"] == {"href": "/api/v3/priorities/7"}

    def test_priority_link_omitted_when_not_provided(self):
        client = MagicMock()
        client.get.return_value = _wp_response()
        client.patch.return_value = _wp_response()

        update_work_package(client, id=1, subject="hi")

        body = client.patch.call_args[0][1]
        assert "priority" not in body["_links"]

    def test_lock_version_included(self):
        client = MagicMock()
        client.get.return_value = _wp_response(lock=9)
        client.patch.return_value = _wp_response()

        update_work_package(client, id=1, priority_id=2)

        body = client.patch.call_args[0][1]
        assert body["lockVersion"] == 9


# ---------------------------------------------------------------------------
# create_relation
# ---------------------------------------------------------------------------

def _relation_response(rel_id: int = 100, rel_type: str = "blocks") -> dict:
    return {
        "id": rel_id,
        "type": rel_type,
        "description": "",
        "delay": None,
        "_links": {
            "from": {"href": "/api/v3/work_packages/86", "title": "From WP"},
            "to": {"href": "/api/v3/work_packages/155", "title": "To WP"},
        },
    }


class TestCreateRelation:
    def test_posts_to_relations_endpoint_for_from_wp(self):
        client = MagicMock()
        client.post.return_value = _relation_response()

        create_relation(client, from_work_package_id=86, to_work_package_id=155, relation_type="blocks")

        path = client.post.call_args[0][0]
        assert path == "work_packages/86/relations"

    def test_request_body_uses_links_and_type(self):
        client = MagicMock()
        client.post.return_value = _relation_response()

        create_relation(client, from_work_package_id=86, to_work_package_id=155, relation_type="blocks")

        body = client.post.call_args[0][1]
        assert body["type"] == "blocks"
        assert body["_links"]["to"] == {"href": "/api/v3/work_packages/155"}

    def test_returns_flattened_relation(self):
        client = MagicMock()
        client.post.return_value = _relation_response(rel_id=100, rel_type="blocks")

        result = create_relation(client, from_work_package_id=86, to_work_package_id=155, relation_type="blocks")

        assert result["id"] == 100
        assert result["type"] == "blocks"
        assert result["from_id"] == 86
        assert result["to_id"] == 155


# ---------------------------------------------------------------------------
# update_relation
# ---------------------------------------------------------------------------

class TestUpdateRelation:
    def _current(self, lock: int = 4) -> dict:
        return {
            "id": 42,
            "type": "blocks",
            "description": "old",
            "lockVersion": lock,
            "_links": {
                "from": {"href": "/api/v3/work_packages/1", "title": "A"},
                "to": {"href": "/api/v3/work_packages/2", "title": "B"},
            },
        }

    def test_patches_relations_path(self):
        client = MagicMock()
        client.get.return_value = self._current()
        client.patch.return_value = self._current()

        update_relation(client, relation_id=42, description="new note")

        path = client.patch.call_args[0][0]
        assert path == "relations/42"

    def test_includes_lock_version(self):
        client = MagicMock()
        client.get.return_value = self._current(lock=11)
        client.patch.return_value = self._current()

        update_relation(client, relation_id=42, description="new note")

        body = client.patch.call_args[0][1]
        assert body["lockVersion"] == 11

    def test_description_sent_when_provided(self):
        client = MagicMock()
        client.get.return_value = self._current()
        client.patch.return_value = self._current()

        update_relation(client, relation_id=42, description="new note")

        body = client.patch.call_args[0][1]
        assert body["description"] == "new note"
        assert "type" not in body

    def test_type_sent_when_provided(self):
        client = MagicMock()
        client.get.return_value = self._current()
        client.patch.return_value = self._current()

        update_relation(client, relation_id=42, relation_type="follows")

        body = client.patch.call_args[0][1]
        assert body["type"] == "follows"
        assert "description" not in body


# ---------------------------------------------------------------------------
# delete_relation
# ---------------------------------------------------------------------------

class TestDeleteRelation:
    def test_calls_client_delete_on_relations_path(self):
        client = MagicMock()
        client.delete.return_value = None

        delete_relation(client, relation_id=42)

        client.delete.assert_called_once_with("relations/42")

    def test_returns_deletion_receipt(self):
        client = MagicMock()
        client.delete.return_value = None

        result = delete_relation(client, relation_id=42)

        assert result == {"deleted": True, "relation_id": 42}
