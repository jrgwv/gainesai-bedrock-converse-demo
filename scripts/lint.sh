#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(dirname "$0")/.."

# ── Python ────────────────────────────────────────────────────────────────────
echo "==> [python] ruff format"
(cd "$REPO_ROOT/backend" && ruff format src/ tests/)

echo "==> [python] ruff lint"
(cd "$REPO_ROOT/backend" && ruff check src/ tests/ --fix)

echo "==> [python] mypy"
(cd "$REPO_ROOT/backend" && mypy src/)

# ── Infra (CDK / TypeScript) ──────────────────────────────────────────────────
echo "==> [infra] prettier"
(cd "$REPO_ROOT/infra" && npx prettier --check '**/*.ts')

echo "==> [infra] eslint"
(cd "$REPO_ROOT/infra" && npx eslint . --max-warnings 0)

echo "All lint checks passed."
