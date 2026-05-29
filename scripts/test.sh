#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../backend"

echo "==> pytest"
pytest

echo "All tests passed."
