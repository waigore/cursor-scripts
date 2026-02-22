"""Tests for run_agent.py (registry and CLI)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import after potential sys.path tweaks so we load from project
import run_agent
from run_agent import load_registry, run


class TestLoadRegistry:
    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Registry not found"):
            load_registry(tmp_path / "missing.yaml")

    def test_empty_yaml_raises(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("")
        with pytest.raises(ValueError, match="agents"):
            load_registry(yaml_path)

    def test_no_agents_key_raises(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("other: []")
        with pytest.raises(ValueError, match="agents"):
            load_registry(yaml_path)

    def test_invalid_entry_not_dict_raises(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("agents:\n  foo: 42")
        with pytest.raises(ValueError, match="expected a mapping"):
            load_registry(yaml_path)

    def test_valid_registry_returns_config_and_name(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("""
agents:
  coder:
    name: Coder
    default_prompt_file: prompts/coder.md
    prompt_file_env_key: PROMPT_FILE
    default_sessions_dir: sessions
    sessions_dir_env_key: SESSIONS_DIR
    default_transcripts_dir: transcripts
    transcripts_dir_env_key: TRANSCRIPTS_DIR
    default_memory_bank_dir: memory_bank
    memory_bank_dir_env_key: MEMORY_BANK_DIR
""")
        registry = load_registry(yaml_path)
        assert "coder" in registry
        config, name = registry["coder"]
        assert name == "Coder"
        assert config.default_prompt_file == "prompts/coder.md"

    def test_name_optional_uses_agent_id(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("""
agents:
  no_name_agent:
    default_prompt_file: p.md
    prompt_file_env_key: P
    default_sessions_dir: s
    sessions_dir_env_key: S
    default_transcripts_dir: t
    transcripts_dir_env_key: T
    default_memory_bank_dir: m
    memory_bank_dir_env_key: M
""")
        registry = load_registry(yaml_path)
        _, name = registry["no_name_agent"]
        assert name == "no_name_agent"


class TestRunCLI:
    def test_list_agents_prints_and_returns_zero(self, tmp_path: Path, capsys):
        registry_yaml = tmp_path / "agents.yaml"
        registry_yaml.write_text("""
agents:
  coder:
    name: Coder
    default_prompt_file: p.md
    prompt_file_env_key: P
    default_sessions_dir: s
    sessions_dir_env_key: S
    default_transcripts_dir: t
    transcripts_dir_env_key: T
    default_memory_bank_dir: m
    memory_bank_dir_env_key: M
""")
        with patch.object(run_agent, "REGISTRY_PATH", registry_yaml):
            with patch("sys.argv", ["run_agent.py", "--list-agents"]):
                code = run()
        assert code == 0
        out, err = capsys.readouterr()
        assert "coder" in out or "Coder" in out

    def test_missing_agent_errors(self, tmp_path: Path):
        registry_yaml = tmp_path / "agents.yaml"
        registry_yaml.write_text("agents:\n  coder:\n    name: C\n    default_prompt_file: p\n    prompt_file_env_key: P\n    default_sessions_dir: s\n    sessions_dir_env_key: S\n    default_transcripts_dir: t\n    transcripts_dir_env_key: T\n    default_memory_bank_dir: m\n    memory_bank_dir_env_key: M\n")
        with patch.object(run_agent, "REGISTRY_PATH", registry_yaml):
            with patch("sys.argv", ["run_agent.py", "--agent", "nonexistent"]):
                code = run()
        assert code == 1

    def test_registry_not_found_returns_one(self, tmp_path: Path):
        with patch.object(run_agent, "REGISTRY_PATH", tmp_path / "missing.yaml"):
            with patch("sys.argv", ["run_agent.py", "--agent", "coder"]):
                code = run()
        assert code == 1

    def test_missing_agent_flag_parser_error(self, tmp_path: Path):
        registry_yaml = tmp_path / "agents.yaml"
        registry_yaml.write_text("agents:\n  coder:\n    name: C\n    default_prompt_file: p\n    prompt_file_env_key: P\n    default_sessions_dir: s\n    sessions_dir_env_key: S\n    default_transcripts_dir: t\n    transcripts_dir_env_key: T\n    default_memory_bank_dir: m\n    memory_bank_dir_env_key: M\n")
        with patch.object(run_agent, "REGISTRY_PATH", registry_yaml):
            with patch("sys.argv", ["run_agent.py"]):
                with pytest.raises(SystemExit):
                    run()

    def test_known_agent_calls_main(self, tmp_path: Path):
        registry_yaml = tmp_path / "agents.yaml"
        registry_yaml.write_text("""
agents:
  coder:
    name: Coder
    default_prompt_file: prompts/p.md
    prompt_file_env_key: PROMPT_FILE
    default_sessions_dir: sessions
    sessions_dir_env_key: SESSIONS_DIR
    default_transcripts_dir: transcripts
    transcripts_dir_env_key: TRANSCRIPTS_DIR
    default_memory_bank_dir: memory_bank
    memory_bank_dir_env_key: MEMORY_BANK_DIR
""")
        with patch.object(run_agent, "REGISTRY_PATH", registry_yaml):
            with patch("sys.argv", ["run_agent.py", "--agent", "coder"]):
                with patch("run_agent.main", return_value=0) as mock_main:
                    code = run()
        assert code == 0
        mock_main.assert_called_once()
        call_config = mock_main.call_args[0][0]
        assert call_config.default_prompt_file == "prompts/p.md"
        assert "Coder" in mock_main.call_args[0][1]