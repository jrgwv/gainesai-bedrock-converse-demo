"""
Integration tests — require real AWS credentials with bedrock:InvokeModel permission.
Skipped unless RUN_INTEGRATION_TESTS=1 is set. Run only in develop/main CI pipelines.
"""
import os
import pytest

from bedrock_client import BedrockConverseClient, ConverseRequest, Message

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


def test_basic_converse():
    client = BedrockConverseClient(region=os.environ.get("AWS_REGION", "us-east-1"))
    req = ConverseRequest(
        messages=[Message(role="user", content="Reply with exactly the word 'hello'.")],
        task_type="default",
        max_tokens=10,
    )
    resp = client.converse(req)
    assert resp.content
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0
    assert resp.latency_ms > 0
    assert resp.fallback_used is False


def test_fallback_model_works():
    client = BedrockConverseClient(region=os.environ.get("AWS_REGION", "us-east-1"))
    req = ConverseRequest(
        messages=[Message(role="user", content="Reply with exactly the word 'hello'.")],
        task_type="summarization",
        max_tokens=10,
    )
    resp = client.converse(req)
    assert resp.content
    assert "haiku" in resp.model_id
