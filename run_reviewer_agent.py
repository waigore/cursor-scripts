#!/usr/bin/env python3
"""
Run the Cursor reviewer agent in the project directory, capture session logs to sessions_reviewer/,
post-process to transcripts_reviewer/, then run a summarizer agent to update memory_bank_reviewer/state.md.
Config via .env (required: PROJECT_ROOT). See .env.example.
Uses its own memory bank (memory_bank_reviewer/), sessions (sessions_reviewer/), and transcripts (transcripts_reviewer/).
"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_runner_lib import AgentConfig, main

REVIEWER_CONFIG = AgentConfig(
    default_prompt_file="prompts/reviewer_prompt.md",
    prompt_file_env_key="REVIEWER_PROMPT_FILE",
    default_sessions_dir="sessions_reviewer",
    sessions_dir_env_key="REVIEWER_SESSIONS_DIR",
    default_transcripts_dir="transcripts_reviewer",
    transcripts_dir_env_key="REVIEWER_TRANSCRIPTS_DIR",
    default_memory_bank_dir="memory_bank_reviewer",
    memory_bank_dir_env_key="REVIEWER_MEMORY_BANK_DIR",
)

if __name__ == "__main__":
    sys.exit(
        main(
            REVIEWER_CONFIG,
            "Run Cursor reviewer agent and optional summarizer.",
            script_root_path=Path(__file__).resolve().parent,
        )
    )
