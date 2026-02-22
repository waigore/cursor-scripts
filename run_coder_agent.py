#!/usr/bin/env python3
"""
Run the Cursor coder agent. Uses config from agents.yaml (project_root, prompt, dir_prefix).
Global options in .env. Session/transcript/memory_bank dirs are shared base + dir_prefix.
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
        print(f"run_coder_agent: {e}", file=sys.stderr)
        sys.exit(1)
    if "coder" not in registry:
        print("run_coder_agent: no 'coder' agent in registry", file=sys.stderr)
        sys.exit(1)
    config, name = registry["coder"]
    sys.exit(
        main(
            config,
            f"Run Cursor {name} agent and optional summarizer.",
            script_root_path=SCRIPT_ROOT,
        )
    )
