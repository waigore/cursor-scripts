"""Shared pytest fixtures for cursor-scripts tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_runner_lib import AgentConfig


@pytest.fixture
def script_root(tmp_path: Path) -> Path:
    """A temporary directory as script root."""
    return tmp_path


@pytest.fixture
def config() -> AgentConfig:
    """Default agent config (coder-like)."""
    return AgentConfig(
        default_prompt_file="prompts/agent_prompt.md",
        prompt_file_env_key="PROMPT_FILE",
        default_sessions_dir="sessions",
        sessions_dir_env_key="SESSIONS_DIR",
        default_transcripts_dir="transcripts",
        transcripts_dir_env_key="TRANSCRIPTS_DIR",
        default_memory_bank_dir="memory_bank",
        memory_bank_dir_env_key="MEMORY_BANK_DIR",
    )


@pytest.fixture
def log():
    """A mock logger."""
    return MagicMock()
