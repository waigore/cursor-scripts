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
        project_root="/my/project",
        default_prompt_file="prompts/agent_prompt.md",
        dir_prefix="",
        file_list=None,
    )


@pytest.fixture
def log():
    """A mock logger."""
    return MagicMock()
