#!/usr/bin/env bash
# the exact checks CI's gates job runs, so green here means green there
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --locked
uv run ruff format --check
uv run ruff check
uv run mypy
uv run pytest -m "not perf and not live" --cov --cov-report=term-missing
uv run vulture src --min-confidence 80
uv run bandit -q -r src

# the dependency audit needs the network, so it is opt-in locally
if [[ "${GATE_AUDIT:-0}" == "1" ]]; then
    uv run pip-audit
fi
