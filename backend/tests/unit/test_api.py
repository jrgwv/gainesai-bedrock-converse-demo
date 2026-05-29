"""Unit tests for the FastAPI application."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import api as api_module
from bedrock_client import ConverseResponse


@pytest.fixture(autouse=True)
def mock_client():
    mock = MagicMock()
    mock.converse.return_value = ConverseResponse(
        request_id="test-id",
        model_id="us.anthropic.claude-opus-4-8",
        content="Hello!",
        input_tokens=10,
        output_tokens=20,
        latency_ms=300.0,
        fallback_used=False,
    )
    api_module.client = mock
    return mock


@pytest.fixture
def http():
    return TestClient(api_module.app)


def test_health(http):
    resp = http.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_converse_success(http):
    resp = http.post("/converse", json={"messages": [{"role": "user", "content": "hello"}]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Hello!"
    assert data["model_id"] == "us.anthropic.claude-opus-4-8"
    assert data["fallback_used"] is False


def test_converse_invalid_role(http):
    resp = http.post("/converse", json={"messages": [{"role": "admin", "content": "hi"}]})
    assert resp.status_code == 422


def test_converse_with_task_type(http, mock_client):
    http.post(
        "/converse",
        json={"messages": [{"role": "user", "content": "hi"}], "task_type": "summarization"},
    )
    call_args = mock_client.converse.call_args
    assert call_args.args[0].task_type == "summarization"


def test_converse_upstream_error_returns_502(http, mock_client):
    mock_client.converse.side_effect = RuntimeError("Bedrock unavailable")
    resp = http.post("/converse", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 502
