#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

echo "==> bandit"
bandit -r src/ -ll -q

echo "==> pip-audit"
pip-audit

echo "==> semgrep"
semgrep --config=auto src/ --error

echo "All security checks passed."
