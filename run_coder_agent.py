#!/usr/bin/env python3
"""
Run the Cursor agent in the project directory, capture session logs to sessions/,
post-process to transcripts/, then run a summarizer agent to update memory_bank/state.md.
Config via .env (required: PROJECT_ROOT). See .env.sample.
Uses its own memory bank (memory_bank/), sessions (sessions/), and transcripts (transcripts/).
"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_runner_lib import AgentConfig, main

CODER_CONFIG = AgentConfig(
    default_prompt_file="prompts/agent_prompt.md",
    prompt_file_env_key="PROMPT_FILE",
    default_sessions_dir="sessions",
    sessions_dir_env_key="SESSIONS_DIR",
    default_transcripts_dir="transcripts",
    transcripts_dir_env_key="TRANSCRIPTS_DIR",
    default_memory_bank_dir="memory_bank",
    memory_bank_dir_env_key="MEMORY_BANK_DIR",
)

if __name__ == "__main__":
    sys.exit(
        main(
            CODER_CONFIG,
            "Run Cursor coder agent and optional summarizer.",
            script_root_path=Path(__file__).resolve().parent,
        )
    )
