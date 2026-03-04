"""Tests for the OpenProjectClient base layer."""

import pytest
import requests
import responses

from openproject_mcp.client import OpenProjectClient

BASE_URL = "http://test.openproject.local"
API_KEY = "test-api-key"


def _url(path):
    return f"{BASE_URL}/api/v3/{path.lstrip('/')}"


def test_client_requires_url(monkeypatch):
    monkeypatch.delenv("OPENPROJECT_URL", raising=False)
    with pytest.raises(ValueError, match="OPENPROJECT_URL"):
        OpenProjectClient(base_url="", api_key=API_KEY)


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENPROJECT_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENPROJECT_API_KEY"):
        OpenProjectClient(base_url=BASE_URL, api_key="")


@responses.activate
def test_get_all_single_page():
    responses.add(responses.GET, _url("items"), json={
        "_embedded": {"elements": [{"id": 1}, {"id": 2}]},
        "total": 2,
    })
    client = OpenProjectClient(base_url=BASE_URL, api_key=API_KEY)
    result = client.get_all("items")

    assert result == [{"id": 1}, {"id": 2}]
    assert len(responses.calls) == 1


@responses.activate
def test_get_all_paginates():
    responses.add(responses.GET, _url("items"), json={
        "_embedded": {"elements": [{"id": 1}]},
        "total": 2,
    })
    responses.add(responses.GET, _url("items"), json={
        "_embedded": {"elements": [{"id": 2}]},
        "total": 2,
    })
    client = OpenProjectClient(base_url=BASE_URL, api_key=API_KEY)
    result = client.get_all("items")

    assert [r["id"] for r in result] == [1, 2]
    assert len(responses.calls) == 2


@responses.activate
def test_get_raises_on_http_error():
    responses.add(responses.GET, _url("work_packages/999"), status=404)
    client = OpenProjectClient(base_url=BASE_URL, api_key=API_KEY)

    with pytest.raises(requests.HTTPError):
        client.get("work_packages/999")


