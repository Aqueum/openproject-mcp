"""Tests for env-gated tool registration."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import asyncio
import pytest


@pytest.fixture
def stub_op_env(monkeypatch):
    monkeypatch.setenv("OPENPROJECT_URL", "http://example.invalid")
    monkeypatch.setenv("OPENPROJECT_API_KEY", "k")


def _tool_names(stub_op_env_required):  # fixture name kept for clarity
    from openproject_mcp import server
    tools = asyncio.run(server.list_tools())
    return {t.name for t in tools}


class TestDeleteWorkPackageRegistration:
    def test_not_registered_when_env_unset(self, stub_op_env, monkeypatch):
        monkeypatch.delenv("OPENPROJECT_ALLOW_DELETE", raising=False)
        assert "delete_work_package" not in _tool_names(stub_op_env)

    def test_not_registered_when_env_false(self, stub_op_env, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_ALLOW_DELETE", "false")
        assert "delete_work_package" not in _tool_names(stub_op_env)

    def test_registered_when_env_true(self, stub_op_env, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_ALLOW_DELETE", "true")
        assert "delete_work_package" in _tool_names(stub_op_env)

    def test_registered_when_env_1(self, stub_op_env, monkeypatch):
        monkeypatch.setenv("OPENPROJECT_ALLOW_DELETE", "1")
        assert "delete_work_package" in _tool_names(stub_op_env)
