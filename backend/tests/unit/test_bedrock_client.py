"""Unit tests for BedrockConverseClient."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from bedrock_client import (
    MODEL_FALLBACK,
    MODEL_PRIMARY,
    BedrockConverseClient,
    ConverseRequest,
    Message,
)


def _bedrock_response(text: str = "OK", input_tokens: int = 10, output_tokens: int = 20) -> dict:
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": input_tokens, "outputTokens": output_tokens},
    }


@pytest.fixture
def client(monkeypatch):
    mock_boto = MagicMock()
    monkeypatch.setattr("bedrock_client.boto3.client", lambda *a, **kw: mock_boto)
    c = BedrockConverseClient(region="us-east-1")
    return c, mock_boto


def test_routes_reasoning_to_primary(client):
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response()
    req = ConverseRequest(
        messages=[Message(role="user", content="explain Lambda cold starts")],
        task_type="reasoning",
    )
    c.converse(req)
    assert mock_boto.converse.call_args.kwargs["modelId"] == MODEL_PRIMARY


def test_routes_summarization_to_fallback(client):
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response()
    req = ConverseRequest(
        messages=[Message(role="user", content="summarize this text")],
        task_type="summarization",
    )
    c.converse(req)
    assert mock_boto.converse.call_args.kwargs["modelId"] == MODEL_FALLBACK


def test_fallback_on_client_error(client):
    c, mock_boto = client
    mock_boto.converse.side_effect = [
        ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}, "Converse"
        ),
        _bedrock_response("fallback response"),
    ]
    req = ConverseRequest(
        messages=[Message(role="user", content="hello")],
        task_type="default",
    )
    resp = c.converse(req)
    assert resp.fallback_used is True
    assert resp.model_id == MODEL_FALLBACK


def test_observer_called_once(client):
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response()
    observer = MagicMock()
    c.add_observer(observer)
    c.converse(ConverseRequest(messages=[Message(role="user", content="test")]))
    observer.assert_called_once()


def test_system_prompt_passed_to_api(client):
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response()
    req = ConverseRequest(
        messages=[Message(role="user", content="hello")],
        system_prompt="You are a helpful assistant.",
    )
    c.converse(req)
    assert "system" in mock_boto.converse.call_args.kwargs


def test_token_counts_returned(client):
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response(input_tokens=42, output_tokens=99)
    req = ConverseRequest(messages=[Message(role="user", content="hi")])
    resp = c.converse(req)
    assert resp.input_tokens == 42
    assert resp.output_tokens == 99


def test_temperature_omitted_for_reasoning_model(client):
    """Opus 4.x rejects temperature; the client must not include it for those models."""
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response()
    req = ConverseRequest(
        messages=[Message(role="user", content="explain")],
        task_type="reasoning",
        temperature=0.7,
    )
    c.converse(req)
    inference = mock_boto.converse.call_args.kwargs["inferenceConfig"]
    assert "temperature" not in inference
    assert inference["maxTokens"] == req.max_tokens


def test_temperature_included_for_non_reasoning_model(client):
    c, mock_boto = client
    mock_boto.converse.return_value = _bedrock_response()
    req = ConverseRequest(
        messages=[Message(role="user", content="summarize")],
        task_type="summarization",
        temperature=0.3,
    )
    c.converse(req)
    inference = mock_boto.converse.call_args.kwargs["inferenceConfig"]
    assert inference["temperature"] == 0.3
