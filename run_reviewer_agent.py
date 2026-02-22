#!/usr/bin/env python3
"""
Run the Cursor reviewer agent. Uses config from agents.yaml (project_root, prompt, dir_prefix).
Global options in .env. All agents share sessions/, transcripts/, memory_bank/; files are named with dir_prefix.
"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_runner_lib import main
from run_agent import REGISTRY_PATH, load_registry

SCRIPT_ROOT = Path(__file__).resolve().parent


if __name__ == "__main__":
    try:
        registry = load_registry(REGISTRY_PATH)
    except (FileNotFoundError, ValueError) as e:
        print(f"run_reviewer_agent: {e}", file=sys.stderr)
        sys.exit(1)
    if "reviewer" not in registry:
        print("run_reviewer_agent: no 'reviewer' agent in registry", file=sys.stderr)
        sys.exit(1)
    config, name = registry["reviewer"]
    sys.exit(
        main(
            config,
            f"Run Cursor {name} agent and optional summarizer.",
            script_root_path=SCRIPT_ROOT,
        )
    )
