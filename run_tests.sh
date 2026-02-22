#!/usr/bin/env bash
# Run tests with coverage; fail if below 85%.
set -e
cd "$(dirname "$0")"
uv run pytest tests/ -v --cov=agent_runner_lib --cov=run_agent --cov-report=term-missing --cov-fail-under=85
