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
        with pytest.raises(FileNotFoundError, match="agents.yaml not found"):
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
    project_root: /my/project
    default_prompt_file: prompts/coder.md
    dir_prefix: ""
""")
        registry = load_registry(yaml_path)
        assert "coder" in registry
        config, name = registry["coder"]
        assert name == "Coder"
        assert config.default_prompt_file == "prompts/coder.md"
        assert config.project_root == "/my/project"
        # command is optional and should default to None when not provided
        assert getattr(config, "command", None) is None

    def test_registry_loads_daemon_interval_sec_from_yaml(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("""
agents:
  coder:
    name: Coder
    project_root: /my/project
    default_prompt_file: prompts/coder.md
    dir_prefix: ""
    daemon_interval_sec: 120
""")
        registry = load_registry(yaml_path)
        config, _ = registry["coder"]
        assert config.daemon_interval_sec == 120

    def test_registry_loads_command_field_when_present(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("""
agents:
  coder:
    name: Coder
    project_root: /my/project
    default_prompt_file: prompts/coder.md
    dir_prefix: ""
    command: custom
""")
        registry = load_registry(yaml_path)
        config, _ = registry["coder"]
        assert config.command == "custom"

    def test_name_optional_uses_agent_id(self, tmp_path: Path):
        yaml_path = tmp_path / "agents.yaml"
        yaml_path.write_text("""
agents:
  no_name_agent:
    project_root: /p
    default_prompt_file: p.md
    dir_prefix: ""
    file_list: |
      foo.md
      bar/baz.md
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
    project_root: /p
    default_prompt_file: p.md
    dir_prefix: ""
""")
        with patch.object(run_agent, "REGISTRY_PATH", registry_yaml):
            with patch("sys.argv", ["run_agent.py", "--list-agents"]):
                code = run()
        assert code == 0
        out, err = capsys.readouterr()
        assert "coder" in out or "Coder" in out

    def test_missing_agent_errors(self, tmp_path: Path):
        registry_yaml = tmp_path / "agents.yaml"
        registry_yaml.write_text("agents:\n  coder:\n    name: C\n    project_root: /p\n    default_prompt_file: p\n    dir_prefix: \"\"\n")
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
        registry_yaml.write_text("agents:\n  coder:\n    name: C\n    project_root: /p\n    default_prompt_file: p\n    dir_prefix: \"\"\n")
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
    project_root: /my/project
    default_prompt_file: prompts/p.md
    dir_prefix: ""
""")
        with patch.object(run_agent, "REGISTRY_PATH", registry_yaml):
            with patch("sys.argv", ["run_agent.py", "--agent", "coder"]):
                with patch("run_agent.main", return_value=0) as mock_main:
                    code = run()
        assert code == 0
        mock_main.assert_called_once()
        call_config = mock_main.call_args[0][0]
        assert call_config.default_prompt_file == "prompts/p.md"
        assert call_config.project_root == "/my/project"
        assert "Coder" in mock_main.call_args[0][1]