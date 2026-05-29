"""
FastAPI application — deployable as a Lambda function via Mangum or as a container.
Exposes a single /converse endpoint that wraps BedrockConverseClient.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bedrock_client import BedrockConverseClient, ConverseRequest, Message
from config import settings
from observability import emit_cloudwatch_metrics, log_event

logging.basicConfig(level=logging.INFO)

client: BedrockConverseClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global client
    client = BedrockConverseClient(region=settings.aws_region)
    client.add_observer(log_event)
    client.add_observer(emit_cloudwatch_metrics)
    yield


app = FastAPI(
    title="Bedrock Converse API — gainsAI Demo",
    version="1.0.0",
    lifespan=lifespan,
)


class MessageSchema(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ConversePayload(BaseModel):
    messages: list[MessageSchema]
    task_type: str = "default"
    max_tokens: int = Field(default=4096, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    system_prompt: str | None = None


class ConverseResult(BaseModel):
    request_id: str
    model_id: str
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    fallback_used: bool


@app.post("/converse", response_model=ConverseResult)
def converse(payload: ConversePayload) -> ConverseResult:
    """
    Unified multi-model inference endpoint.
    The modelId is resolved internally based on task_type — callers never
    reference a specific model. Swapping models requires no client changes.
    """
    try:
        request = ConverseRequest(
            messages=[Message(role=m.role, content=m.content) for m in payload.messages],
            task_type=payload.task_type,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
            system_prompt=payload.system_prompt,
        )
        response = client.converse(request)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ConverseResult(
        request_id=response.request_id,
        model_id=response.model_id,
        content=response.content,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        latency_ms=response.latency_ms,
        fallback_used=response.fallback_used,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


try:
    from mangum import Mangum

    handler = Mangum(app, lifespan="on")
except ImportError:
    pass
