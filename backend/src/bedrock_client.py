"""
Thin wrapper around the Bedrock Converse API.
Handles retries, fallback model, and emits structured observability events.
"""

import time
import uuid
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model registry — values read from env vars at import time.
# Override: PRIMARY_MODEL_ID / FALLBACK_MODEL_ID in the environment or .env
# ---------------------------------------------------------------------------
MODEL_PRIMARY = settings.primary_model_id
MODEL_FALLBACK = settings.fallback_model_id

# Task complexity → model routing table
ROUTING_TABLE: dict[str, str] = {
    "reasoning":      MODEL_PRIMARY,
    "coding":         MODEL_PRIMARY,
    "analysis":       MODEL_PRIMARY,
    "summarization":  MODEL_FALLBACK,
    "classification": MODEL_FALLBACK,
    "default":        MODEL_PRIMARY,
}

LATENCY_THRESHOLD_MS = settings.latency_threshold_ms


@dataclass
class Message:
    role: str       # "user" | "assistant"
    content: str


@dataclass
class ConverseRequest:
    messages: list[Message]
    task_type: str = "default"
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: Optional[str] = None


@dataclass
class ConverseResponse:
    request_id: str
    model_id: str
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    fallback_used: bool = False


@dataclass
class ObservabilityEvent:
    request_id: str
    model_id: str
    task_type: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    fallback_used: bool
    error: Optional[str] = None


class BedrockConverseClient:
    """Wrapper around Bedrock Converse with model routing, fallback, and observability hooks."""

    def __init__(self, region: str = "us-east-1"):
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._observers: list[Callable[[ObservabilityEvent], None]] = []

    def add_observer(self, fn: Callable[[ObservabilityEvent], None]) -> None:
        """Register a callback that receives ObservabilityEvent after each call."""
        self._observers.append(fn)

    def converse(self, request: ConverseRequest) -> ConverseResponse:
        """Route request to the appropriate model, falling back on error or latency breach."""
        request_id = str(uuid.uuid4())
        model_id = ROUTING_TABLE.get(request.task_type, MODEL_PRIMARY)

        try:
            response = self._call(model_id, request, request_id)
        except (ClientError, TimeoutError) as primary_err:
            logger.warning(
                "Primary model %s failed (%s), falling back to %s",
                model_id, primary_err, MODEL_FALLBACK,
            )
            response = self._call(MODEL_FALLBACK, request, request_id)
            response.fallback_used = True

        self._emit(request, response)
        return response

    def _call(
        self,
        model_id: str,
        request: ConverseRequest,
        request_id: str,
    ) -> ConverseResponse:
        kwargs: dict = {
            "modelId": model_id,
            "messages": [
                {
                    "role": m.role,
                    "content": [{"text": m.content}],
                }
                for m in request.messages
            ],
            "inferenceConfig": {
                "maxTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }

        if request.system_prompt:
            kwargs["system"] = [{"text": request.system_prompt}]

        t0 = time.monotonic()
        raw = self._client.converse(**kwargs)
        latency_ms = (time.monotonic() - t0) * 1000

        if latency_ms > LATENCY_THRESHOLD_MS and model_id == MODEL_PRIMARY:
            raise TimeoutError(f"Primary model latency {latency_ms:.0f} ms exceeded threshold")

        usage = raw.get("usage", {})
        content = raw["output"]["message"]["content"][0]["text"]

        return ConverseResponse(
            request_id=request_id,
            model_id=model_id,
            content=content,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            latency_ms=latency_ms,
        )

    def _emit(self, request: ConverseRequest, response: ConverseResponse):
        event = ObservabilityEvent(
            request_id=response.request_id,
            model_id=response.model_id,
            task_type=request.task_type,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
            fallback_used=response.fallback_used,
        )
        for fn in self._observers:
            try:
                fn(event)
            except Exception:
                logger.exception("Observer error")
