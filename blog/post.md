# Building a Multi-Model Inference Platform on AWS Bedrock Converse API

> **Status:** Draft — targeting publication on [platform TBD]

## Overview

The Bedrock Converse API provides a single, unified interface for calling any supported
foundation model. This post walks through building a production-grade inference platform on
top of it — with task-based model routing, automatic fallback, structured observability, and
a one-command CDK deployment.

**What you'll build:**
- A `BedrockConverseClient` that routes requests to the right model tier by task complexity
- A FastAPI wrapper deployable as a Lambda function via Mangum, or as a container on ECS
- Structured logging and CloudWatch metrics emitted from every API call
- CDK stacks for Lambda + API Gateway with VPC, ARM64, X-Ray, and cdk-nag compliance

**Prerequisites:** AWS account with Bedrock model access enabled, Python 3.13, Node 22, AWS CDK v2.

---

## 1. Why the Converse API?

Before Converse, switching between Bedrock models meant rewriting request/response shapes —
Anthropic's `messages` API, Titan's `inputText`, Llama's `prompt`, etc. Converse normalises
all of that into one shape. You pick a `modelId`; the API handles the rest.

The result: you can swap `us.anthropic.claude-opus-4-8` for any other supported model by
changing a single string. No client rewrites.

[TODO: before/after code comparison]

---

## 2. The Bedrock Client

`bedrock_client.py` wraps `boto3.client("bedrock-runtime").converse()` and adds three things:

**Task-based model routing** — map task complexity to a model tier once, centrally:

```python
ROUTING_TABLE: dict[str, str] = {
    "reasoning":      MODEL_PRIMARY,   # claude-opus-4-8
    "coding":         MODEL_PRIMARY,
    "analysis":       MODEL_PRIMARY,
    "summarization":  MODEL_FALLBACK,  # claude-haiku-4-5
    "classification": MODEL_FALLBACK,
    "default":        MODEL_PRIMARY,
}
```

Callers pass a `task_type`; they never reference a model ID directly. Changing tiers later
is a one-line config change.

**Automatic fallback** — if the primary model throws a `ClientError` or breaches the
latency threshold (30 s), the client retries with the fallback model and sets
`fallback_used=True` on the response.

**Observer pattern** — pluggable callbacks receive an `ObservabilityEvent` after every call,
making logging and metrics opt-in rather than coupled to the client.

[Full bedrock_client.py — see examples/examples.py and src/bedrock_client.py]

---

## 3. Example 1 — Basic Converse Call

```python
# examples/examples.py
response = bedrock.converse(
    modelId="us.anthropic.claude-opus-4-8",
    messages=[
        {
            "role": "user",
            "content": [{"text": "What are the key tradeoffs between sync and async Lambda invocation?"}],
        }
    ],
    inferenceConfig={"maxTokens": 1024},
)
print(response["output"]["message"]["content"][0]["text"])
print(f"Tokens — in: {response['usage']['inputTokens']}, out: {response['usage']['outputTokens']}")
```

---

## 4. Example 2 — Multi-Turn Conversation

The same structure handles multi-turn with no extra plumbing — just append to the
`messages` list:

```python
conversation = [
    {"role": "user",      "content": [{"text": "I'm designing a RAG pipeline on AWS. Where should I start?"}]},
    {"role": "assistant", "content": [{"text": "Start with your retrieval strategy. Structured or unstructured data?"}]},
    {"role": "user",      "content": [{"text": "Unstructured — PDFs and internal wikis."}]},
]

response = bedrock.converse(
    modelId="us.anthropic.claude-opus-4-8",
    messages=conversation,
    system=[{"text": "You are an AWS solutions architect. Be concise and opinionated."}],
    inferenceConfig={"maxTokens": 2048, "temperature": 0.5},
)
```

---

## 5. Example 3 — Task-Based Model Routing

```python
def route_model(task_type: str) -> str:
    routing = {
        "reasoning":      "us.anthropic.claude-opus-4-8",
        "summarization":  "us.anthropic.claude-haiku-4-5-20251001",
        "classification": "us.anthropic.claude-haiku-4-5-20251001",
    }
    return routing.get(task_type, "us.anthropic.claude-opus-4-8")
```

In the production client this logic lives in `ROUTING_TABLE` — the caller only passes
`task_type`, never a model string.

---

## 6. Example 4 — Fallback Pattern

```python
def converse_with_fallback(text: str, primary: str, fallback: str) -> dict:
    for model_id in [primary, fallback]:
        try:
            response = bedrock.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": text}]}],
                inferenceConfig={"maxTokens": 1024},
            )
            return {
                "model_id": model_id,
                "content": response["output"]["message"]["content"][0]["text"],
                "fallback_used": model_id == fallback,
            }
        except Exception as e:
            if model_id == fallback:
                raise
            print(f"Primary failed ({e}), trying fallback...")
    raise RuntimeError("All models failed")
```

---

## 7. Observability

Every Bedrock call emits a structured JSON log line via `log_event()` — searchable in
CloudWatch Logs Insights — and CloudWatch custom metrics via `emit_cloudwatch_metrics()`.

Metrics to watch:
- **LatencyMs P95** — spikes indicate cold starts or capacity issues
- **FallbackUsed** — alert if non-zero in production
- **OutputTokens / InputTokens by ModelId** — cost visibility

[Full observability.py listing]

---

## 8. FastAPI + Lambda via Mangum

The FastAPI app runs locally with uvicorn and in Lambda via Mangum with zero code changes:

```python
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="on")
except ImportError:
    pass  # local dev with uvicorn
```

```bash
# local dev
cd backend && PYTHONPATH=src uvicorn api:app --reload

# Lambda — CDK packages src/ into the function code asset
```

---

## 9. CDK Stack

[TODO: architecture diagram — VPC → Lambda (ARM64) → API Gateway → CloudWatch]

Key CDK decisions and why:

| Decision | Reason |
|---|---|
| `Architecture.ARM_64` | ~20% cost reduction, same performance |
| VPC placement | Required for Bedrock VPC endpoints in a private subnet |
| `reservedConcurrentExecutions` | Prevents runaway token spend on a hot endpoint |
| `cdk-nag AwsSolutionsChecks` | Catches IAM wildcards, missing encryption, insecure defaults |
| `RetentionDays.ONE_YEAR` | Regulatory baseline; easy to increase |

```bash
cd infra
npm ci
npm run cdk:deploy:dev
```

---

## 10. Running the Demo

```bash
# 1. Backend (local)
cd backend
pip install -e ".[dev]"
PYTHONPATH=src uvicorn api:app --reload

# 2. Frontend
open frontend/index.html
# Set API URL to http://localhost:8000, pick a task type, send a message

# 3. Deploy to AWS
cd infra && npm ci && npm run cdk:deploy:dev
```

Select different task types in the UI to see the routing in action — `summarization` hits
Haiku, `reasoning` hits Opus.

---

## Conclusion

[TODO: wrap up — key takeaways, link to repo, what to try next]

Key points:
- The Converse API is the right abstraction for building model-agnostic inference layers
- Routing and fallback logic belongs in one place, not scattered across callers
- Structured observability from day one saves pain later
- CDK + cdk-nag is the fastest path to a compliant deployment
