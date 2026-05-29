"""
Structured logging + CloudWatch Metrics emission for each Converse API call.
Register `log_event` and/or `emit_cloudwatch_metrics` as observers on BedrockConverseClient.
"""

import json
import logging
from datetime import UTC, datetime

import boto3

from bedrock_client import ObservabilityEvent

logger = logging.getLogger(__name__)

NAMESPACE = "gainsAI/BedrockConverse"


def log_event(event: ObservabilityEvent) -> None:
    """Emit a structured JSON log line (CloudWatch Logs Insights friendly)."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": event.request_id,
        "model_id": event.model_id,
        "task_type": event.task_type,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "total_tokens": event.input_tokens + event.output_tokens,
        "latency_ms": round(event.latency_ms, 2),
        "fallback_used": event.fallback_used,
        "error": event.error,
    }
    logger.info(json.dumps(record))


def emit_cloudwatch_metrics(event: ObservabilityEvent) -> None:
    """
    Push custom metrics to CloudWatch.
    In Lambda, prefer EMF (aws_embedded_metrics) instead for lower overhead.
    """
    cw = boto3.client("cloudwatch")
    dimensions = [
        {"Name": "ModelId", "Value": event.model_id},
        {"Name": "TaskType", "Value": event.task_type},
    ]

    metric_data = [
        {
            "MetricName": "InputTokens",
            "Dimensions": dimensions,
            "Value": event.input_tokens,
            "Unit": "Count",
        },
        {
            "MetricName": "OutputTokens",
            "Dimensions": dimensions,
            "Value": event.output_tokens,
            "Unit": "Count",
        },
        {
            "MetricName": "LatencyMs",
            "Dimensions": dimensions,
            "Value": event.latency_ms,
            "Unit": "Milliseconds",
        },
        {
            "MetricName": "FallbackUsed",
            "Dimensions": dimensions,
            "Value": 1 if event.fallback_used else 0,
            "Unit": "Count",
        },
    ]

    try:
        cw.put_metric_data(Namespace=NAMESPACE, MetricData=metric_data)
    except Exception:
        logger.exception("Failed to emit CloudWatch metrics for request %s", event.request_id)
