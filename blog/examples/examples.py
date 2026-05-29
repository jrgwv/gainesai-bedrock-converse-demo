"""
Runnable examples for the blog post — paste these into the post as code blocks.
Run directly: python examples.py
Requires: boto3, AWS credentials with bedrock:InvokeModel permission
"""

import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


# ---------------------------------------------------------------------------
# Example 1: Basic single-turn call
# ---------------------------------------------------------------------------
def example_basic():
    print("=== Example 1: Basic Converse call ===")

    response = bedrock.converse(
        modelId="us.anthropic.claude-opus-4-8",
        messages=[
            {
                "role": "user",
                "content": [{"text": "What are the key tradeoffs between synchronous and async Lambda invocation?"}],
            }
        ],
        inferenceConfig={"maxTokens": 1024},
    )

    print(response["output"]["message"]["content"][0]["text"])
    print(f"\nTokens — in: {response['usage']['inputTokens']}, out: {response['usage']['outputTokens']}")


# ---------------------------------------------------------------------------
# Example 2: Multi-turn conversation
# Identical structure works for any Bedrock model — swap modelId, nothing else
# ---------------------------------------------------------------------------
def example_multi_turn():
    print("\n=== Example 2: Multi-turn conversation ===")

    conversation = [
        {"role": "user", "content": [{"text": "I'm designing a RAG pipeline on AWS. Where should I start?"}]},
        {"role": "assistant", "content": [{"text": "Start with your retrieval strategy. Are you using structured or unstructured data?"}]},
        {"role": "user", "content": [{"text": "Unstructured — PDFs and internal wikis."}]},
    ]

    response = bedrock.converse(
        modelId="us.anthropic.claude-opus-4-8",
        messages=conversation,
        system=[{"text": "You are an AWS solutions architect. Be concise and opinionated."}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0.5},
    )

    print(response["output"]["message"]["content"][0]["text"])


# ---------------------------------------------------------------------------
# Example 3: Model routing — same API call, different modelId
# In production this logic lives in bedrock_client.py; shown here for clarity
# ---------------------------------------------------------------------------
def route_model(task_type: str) -> str:
    routing = {
        "reasoning":      "us.anthropic.claude-opus-4-8",
        "coding":         "us.anthropic.claude-opus-4-8",
        "analysis":       "us.anthropic.claude-opus-4-8",
        "summarization":  "us.anthropic.claude-haiku-4-5-20251001",
        "classification": "us.anthropic.claude-haiku-4-5-20251001",
    }
    return routing.get(task_type, "us.anthropic.claude-opus-4-8")


def example_routing():
    print("\n=== Example 3: Task-based model routing ===")

    tasks = [
        ("Design a multi-region failover strategy for DynamoDB Global Tables.", "reasoning"),
        ("Summarize this paragraph in one sentence: AWS Lambda is a serverless compute...", "summarization"),
    ]

    for text, task_type in tasks:
        model_id = route_model(task_type)
        print(f"\nTask type: {task_type} → {model_id}")

        response = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": text}]}],
            inferenceConfig={"maxTokens": 512},
        )
        print(response["output"]["message"]["content"][0]["text"][:200], "...")


# ---------------------------------------------------------------------------
# Example 4: Fallback pattern
# ---------------------------------------------------------------------------
def converse_with_fallback(text: str, primary: str, fallback: str) -> dict:
    for model_id in [primary, fallback]:
        try:
            response = bedrock.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": text}]}],
                inferenceConfig={"maxTokens": 1024},
            )
            used_fallback = model_id == fallback
            return {
                "model_id": model_id,
                "content": response["output"]["message"]["content"][0]["text"],
                "fallback_used": used_fallback,
            }
        except Exception as e:
            if model_id == fallback:
                raise
            print(f"Primary model failed ({e}), trying fallback...")

    raise RuntimeError("All models failed")


def example_fallback():
    print("\n=== Example 4: Fallback pattern ===")

    result = converse_with_fallback(
        text="Explain cross-region replication latency tradeoffs.",
        primary="us.anthropic.claude-opus-4-8",
        fallback="us.anthropic.claude-haiku-4-5-20251001",
    )

    print(f"Served by: {result['model_id']} (fallback={result['fallback_used']})")
    print(result["content"][:300], "...")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    example_basic()
    example_multi_turn()
    example_routing()
    example_fallback()
