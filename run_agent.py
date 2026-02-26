#!/usr/bin/env python3
"""
Single CLI entrypoint for Cursor agents. Select agent by name via --agent.
Registry: agents.yaml (project_root, prompt, dir_prefix, optional command per agent).
Global config in .env; optional shared command registry in commands.yaml.
Summarizer uses shared prompts/summarize_prompt.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from agent_runner_lib import AgentConfig, main

SCRIPT_ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = SCRIPT_ROOT / "agents.yaml"


def load_registry(path: Path) -> dict[str, tuple[AgentConfig, str]]:
    """Load agents.yaml; return id -> (AgentConfig, display_name)."""
    if not path.is_file():
        raise FileNotFoundError(
            f"agents.yaml not found at {path}. "
            "Copy agents.yaml.example to agents.yaml and set project_root for each agent."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw or "agents" not in raw:
        raise ValueError("agents.yaml must contain an 'agents' mapping")
    result: dict[str, tuple[AgentConfig, str]] = {}
    for agent_id, entry in raw["agents"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"agents.{agent_id}: expected a mapping")
        entry = dict(entry)
        name = entry.pop("name", agent_id)
        config = AgentConfig(**entry)
        result[agent_id] = (config, name)
    return result


def run() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a Cursor agent by name (coder, reviewer, etc.). Registry: agents.yaml.",
    )
    parser.add_argument(
        "-a",
        "--agent",
        metavar="ID",
        help="Agent id from registry (e.g. coder, reviewer). Use --list-agents to see ids.",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List registered agent ids and exit.",
    )
    args, unknown = parser.parse_known_args()

    try:
        registry = load_registry(REGISTRY_PATH)
    except (FileNotFoundError, ValueError) as e:
        print(f"run_agent: {e}", file=sys.stderr)
        return 1

    if args.list_agents:
        print("Registered agents:")
        for aid, (_, name) in registry.items():
            print(f"  {aid}  ({name})")
        return 0

    if not args.agent:
        parser.error("--agent ID is required (or use --list-agents)")
    agent_id = args.agent.strip().lower()
    if agent_id not in registry:
        print(f"run_agent: unknown agent '{args.agent}'. Use --list-agents.", file=sys.stderr)
        return 1

    config, name = registry[agent_id]
    sys.argv = [sys.argv[0]] + unknown
    return main(
        config,
        f"Run Cursor {name} agent and optional summarizer.",
        script_root_path=SCRIPT_ROOT,
    )


if __name__ == "__main__":
    sys.exit(run())
