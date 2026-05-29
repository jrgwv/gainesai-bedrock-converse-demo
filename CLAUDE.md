# CLAUDE.md — bedrock-converse-demo

This file instructs Claude Code on project conventions, tooling, branch strategy,
and quality gates. Follow these rules on every task unless explicitly overridden.

---

## Project Overview

A portable multi-model inference platform built on the Amazon Bedrock Converse API.
- **Backend:** Python 3.13 (FastAPI, boto3)
- **Infrastructure:** AWS CDK v2 in TypeScript 5.x
- **Runtime targets:** AWS Lambda (Mangum adapter) + optional ECS Fargate
- **Primary model:** `us.anthropic.claude-opus-4-8` with automatic fallback

---

## Repository Layout

```
bedrock-converse-demo/
├── CLAUDE.md
├── .github/
│   └── workflows/
│       ├── ci.yml          # lint + test + security on every PR
│       └── deploy.yml      # CDK deploy on merge to main
├── backend/                # Python FastAPI application
│   ├── src/
│   │   ├── bedrock_client.py
│   │   ├── observability.py
│   │   └── api.py
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── pyproject.toml
│   └── Dockerfile
├── infra/                  # CDK TypeScript
│   ├── bin/
│   │   └── app.ts
│   ├── lib/
│   │   ├── bedrock-stack.ts
│   │   └── pipeline-stack.ts
│   ├── test/
│   │   └── bedrock-stack.test.ts
│   ├── cdk.json
│   └── package.json
└── scripts/
    ├── lint.sh
    ├── security.sh
    └── test.sh
```

---

## Branch Strategy

Use **GitHub Flow** with short-lived feature branches.

| Branch pattern | Purpose | Merges into |
|---|---|---|
| `main` | Production-ready, protected | — |
| `develop` | Integration branch | `main` via PR |
| `feature/<ticket>-<slug>` | New features | `develop` |
| `fix/<ticket>-<slug>` | Bug fixes | `develop` |
| `hotfix/<slug>` | Critical prod fixes | `main` + `develop` |
| `chore/<slug>` | Tooling, deps, docs | `develop` |

Rules:
- `main` and `develop` are protected — no direct pushes.
- Every PR requires: CI passing + 1 approval + no unresolved comments.
- Squash merge into `develop`; merge commit into `main` for traceability.
- Delete feature branches after merge.
- Tag releases on `main` with semver: `v1.2.3`.

---

## Python — Backend

### Version & Tooling

- **Python:** 3.13 (pin in `.python-version` and `pyproject.toml`)
- **Package manager:** `uv` (preferred) or `pip` with `pip-tools`
- **Formatter:** `ruff format` (replaces Black)
- **Linter:** `ruff check` (replaces Flake8/isort/pyupgrade)
- **Type checker:** `mypy --strict`
- **Security scanner:** `bandit -r src/ -ll` + `semgrep --config=auto`
- **Dependency audit:** `pip-audit`
- **Test runner:** `pytest` with `pytest-cov`

### pyproject.toml (key sections)

```toml
[project]
requires-python = ">=3.13"

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "S", "B", "C4", "PIE", "RET", "SIM", "TCH"]
ignore = ["S101"]  # allow assert in tests

[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = false

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=85"

[tool.bandit]
skips = ["B101"]
```

### Key Dependencies (keep current)

```toml
[project.dependencies]
boto3 = ">=1.38"
fastapi = ">=0.115"
pydantic = ">=2.11"
uvicorn = {extras = ["standard"], version = ">=0.34"}
mangum = ">=0.19"
structlog = ">=24.4"

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-cov>=6.1",
    "pytest-asyncio>=0.25",
    "moto[bedrock]>=5.1",
    "httpx>=0.28",           # async test client for FastAPI
    "ruff>=0.9",
    "mypy>=1.14",
    "bandit>=1.8",
    "pip-audit>=2.8",
    "semgrep>=1.100",
]
```

---

## Infrastructure — CDK TypeScript

### Version & Tooling

- **Node:** 22 LTS (pin in `.nvmrc`: `22`)
- **TypeScript:** 5.x (`"strict": true` in tsconfig)
- **CDK:** `aws-cdk-lib` v2 latest (`>=2.180`)
- **Linter:** ESLint + `@typescript-eslint`
- **Formatter:** Prettier
- **Security:** `cdk-nag` (AwsSolutionsChecks) + `npm audit --audit-level=moderate`
- **Tests:** Jest with `aws-cdk-lib/assertions`

### cdk.json

```json
{
  "app": "npx ts-node --prefer-ts-exts bin/app.ts",
  "context": {
    "@aws-cdk/aws-apigateway:usagePlanKeyOrderInsensitiveId": true,
    "@aws-cdk/aws-lambda:recognizeLayerVersion": true,
    "@aws-cdk/aws-iam:minimizePolicies": true
  }
}
```

### CDK Stack Requirements

Every stack must:
1. Apply `cdk-nag` `AwsSolutionsChecks` — suppress nothing without a documented reason.
2. Enable `RemovalPolicy.RETAIN` on stateful resources in prod.
3. Use `aws_lambda.Architecture.ARM_64` for all Lambda functions.
4. Set `reservedConcurrentExecutions` on critical Lambda functions.
5. Enable X-Ray tracing on Lambda and API Gateway.
6. Enforce VPC placement for Lambda functions accessing Bedrock.
7. Use `aws_logs.RetentionDays.ONE_YEAR` minimum for CloudWatch log groups.
8. Tag all resources with `Project`, `Env`, `Owner`.

### package.json scripts (infra/)

```json
{
  "scripts": {
    "build": "tsc",
    "lint": "eslint . --ext .ts",
    "format:check": "prettier --check '**/*.ts'",
    "test": "jest --coverage",
    "cdk:synth": "cdk synth",
    "cdk:diff": "cdk diff",
    "cdk:deploy:dev": "cdk deploy --context env=dev",
    "cdk:deploy:prod": "cdk deploy --context env=prod --require-approval broadening",
    "audit": "npm audit --audit-level=moderate"
  }
}
```

---

## Pre-Commit Quality Gates

All of these must pass before any commit is allowed.
Claude Code must run them before declaring a task complete.

### Python (run from `backend/`)

```bash
# Format
ruff format src/ tests/

# Lint
ruff check src/ tests/ --fix

# Type check
mypy src/

# Security
bandit -r src/ -ll -q
semgrep --config=auto src/ --error

# Dependency audit
pip-audit

# Tests
pytest
```

### Infrastructure (run from `infra/`)

```bash
# Format check
npx prettier --check '**/*.ts'

# Lint
npx eslint . --ext .ts --max-warnings 0

# CDK synth (catches type errors + cdk-nag)
npm run cdk:synth

# Dependency audit
npm audit --audit-level=moderate

# Unit tests
npm test -- --coverage
```

### Combined gate (scripts/lint.sh + scripts/security.sh)

Claude Code should run `scripts/lint.sh` and `scripts/security.sh` and fix all
findings before marking any task done.

---

## Testing Standards

### Python

| Layer | Tool | Location | Minimum coverage |
|---|---|---|---|
| Unit | pytest + moto | `tests/unit/` | 85% |
| Integration | pytest + real Bedrock (dev account) | `tests/integration/` | Key flows |
| Contract | pact (if consumed by frontend) | `tests/contract/` | All endpoints |

- Mock Bedrock with `moto` in unit tests — never call real AWS in CI.
- Use `pytest-asyncio` for async FastAPI routes.
- Integration tests run only on the `develop` and `main` CI pipelines (not on every PR push).
- Every new feature needs unit tests before the PR is opened.

### CDK / Infrastructure

- Use `aws-cdk-lib/assertions` `Template.fromStack()` for all resource assertions.
- Assert on resource counts, properties, and IAM policies.
- Test every cdk-nag suppression has a corresponding assertion.

---

## Secrets & Environment Variables

- **Never hardcode** AWS account IDs, region, or model IDs as string literals in application code.
- Use `os.environ` + Pydantic `BaseSettings` for all config.
- Store secrets in AWS Secrets Manager; reference via CDK `secretsmanager.Secret.fromSecretNameV2`.
- `.env` files are `.gitignore`'d. Provide `.env.example` with placeholder values.

```python
# backend/src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    primary_model_id: str = "us.anthropic.claude-opus-4-8"
    fallback_model_id: str = "us.anthropic.claude-haiku-4-5-20251001"
    log_level: str = "INFO"
    latency_threshold_ms: int = 30_000

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Logging & Observability

- Use `structlog` for all application logging (JSON output in Lambda/ECS, dev-friendly in local).
- Log level controlled by `LOG_LEVEL` env var.
- Every Bedrock call emits a structured event with: `request_id`, `model_id`, `task_type`, `input_tokens`, `output_tokens`, `latency_ms`, `fallback_used`.
- CloudWatch custom metrics namespace: `gainsAI/BedrockConverse`.
- X-Ray segments on all Lambda handlers and Bedrock client calls.
- Never log PII or full message content — log token counts and metadata only.

---

## Docker

- Use `public.ecr.aws/lambda/python:3.13` as the Lambda base image.
- Multi-stage build: `builder` stage installs deps, `runtime` stage copies only what's needed.
- Run as non-root user in container.
- Scan image with `docker scout cves` or `trivy image` before pushing.

---

## CI/CD (GitHub Actions)

### ci.yml — runs on every PR to `develop` or `main`

Steps in order:
1. Checkout + setup Python 3.13 + Node 22
2. Install deps (`uv sync --frozen` / `npm ci`)
3. Python: ruff format check → ruff lint → mypy → bandit → semgrep → pip-audit → pytest
4. CDK: prettier check → eslint → cdk synth → npm audit → jest
5. Upload coverage reports to Codecov

### deploy.yml — runs on merge to `main`

1. CI steps (above)
2. `cdk diff` — post diff as PR comment
3. `cdk deploy` to prod with `--require-approval never` (approvals happen in PR)
4. Smoke test: hit `/health` endpoint post-deploy

---

## Code Style Rules

- **No `Any` types** in Python without a `# type: ignore[assignment]` comment explaining why.
- **No bare `except:`** — always catch specific exceptions.
- **No `print()`** in application code — use `structlog`.
- **No unused imports** — ruff catches these.
- All public functions and classes must have docstrings.
- Pydantic models for all API request/response shapes — no raw dicts across boundaries.
- CDK constructs: use L2 constructs wherever available; L1 (`Cfn*`) only with a comment explaining why.

---

## Claude Code Workflow

When starting a new task:
1. Confirm the target branch (`feature/<slug>` off `develop` unless it's a hotfix).
2. Read this file and the relevant source files before writing any code.
3. Run `scripts/lint.sh` after every meaningful code change.
4. Run `scripts/security.sh` before marking a task complete.
5. Run the full test suite (`pytest` + `npm test`) before marking a task complete.
6. Summarize what changed, what tests cover it, and what security checks passed.

When creating new AWS resources via CDK:
1. Add cdk-nag suppression only if there is a clear documented reason.
2. Assert the resource exists in the Jest test for that stack.
3. Tag the resource with the stack's default tags.
