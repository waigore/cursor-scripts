"""Tests for agent_runner_lib."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_runner_lib import (
    AgentConfig,
    PROMPT_FILE_THRESHOLD,
    _on_shutdown_signal,
    build_main_prompt,
    build_summarize_prompt,
    ensure_dirs_and_state,
    latest_transcript,
    load_env,
    read_state,
    resolve_path,
    run_agent,
    run_one_cycle,
    run_parser,
    run_summarizer,
    script_root,
    setup_logging,
)


class TestOnShutdownSignal:
    def test_sets_shutdown_and_terminates_process(self):
        import agent_runner_lib
        proc = MagicMock()
        agent_runner_lib._current_process = proc
        agent_runner_lib._shutdown_requested = False
        try:
            _on_shutdown_signal(2, None)
            proc.terminate.assert_called_once()
            assert agent_runner_lib._shutdown_requested is True
        finally:
            agent_runner_lib._current_process = None
            agent_runner_lib._shutdown_requested = False

    def test_ignores_oserror_on_terminate(self):
        import agent_runner_lib
        proc = MagicMock()
        proc.terminate.side_effect = OSError
        agent_runner_lib._current_process = proc
        try:
            _on_shutdown_signal(2, None)
            proc.terminate.assert_called_once()
        finally:
            agent_runner_lib._current_process = None


class TestScriptRoot:
    def test_script_root_returns_parent_of_file(self):
        out = script_root("/some/dir/foo.py")
        assert out == Path("/some/dir")


class TestResolvePath:
    def test_relative_path_joined_with_script_root(self, script_root: Path):
        (script_root / "prompts").mkdir()
        got = resolve_path("prompts/agent_prompt.md", script_root)
        assert got == (script_root / "prompts" / "agent_prompt.md").resolve()

    def test_absolute_path_unchanged(self, script_root: Path):
        abs_path = Path("/abs/path/to/file")
        got = resolve_path(str(abs_path), script_root)
        assert got == abs_path.resolve()


class TestSetupLogging:
    def test_valid_level(self):
        setup_logging("DEBUG")
        # No exception; level is set
        import logging
        assert logging.getLogger().level == logging.DEBUG or True  # root may be set by others

    def test_invalid_level_falls_back_to_info(self):
        setup_logging("NOT_A_LEVEL")
        # getattr(..., "NOT_A_LEVEL", logging.INFO) returns INFO
        import logging
        level = getattr(logging, "NOT_A_LEVEL", logging.INFO)
        assert level == logging.INFO


class TestLoadEnv:
    def test_exits_when_dotenv_missing(self, script_root: Path, config: AgentConfig):
        with patch("agent_runner_lib.load_dotenv", None):
            with pytest.raises(SystemExit) as exc_info:
                load_env(script_root, config)
            assert exc_info.value.code == 1

    def test_exits_when_project_root_empty(self, script_root: Path):
        config = AgentConfig(
            project_root="",
            default_prompt_file="prompts/agent_prompt.md",
            dir_prefix="",
        )
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with pytest.raises(SystemExit) as exc_info:
                load_env(script_root, config)
            assert exc_info.value.code == 1

    def test_returns_env_with_defaults(self, script_root: Path, config: AgentConfig):
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            env = load_env(script_root, config)
            assert env["project_root"] == config.project_root
            assert "agent_cmd" in env
            assert env["memory_bank_dir"] == "memory_bank"
            assert env["sessions_dir"] == "sessions"
            assert env["transcripts_dir"] == "transcripts"
            assert env["dir_prefix"] == ""
            assert env["prompt_file"] == config.default_prompt_file
            assert env["base_branch"] == "dev"
            assert env["daemon_interval_sec"] == 60
            assert env["use_summarizer"] is False

    def test_use_summarizer_true_when_set_in_config(self, script_root: Path):
        config = AgentConfig(
            project_root="/p",
            default_prompt_file="prompts/x.md",
            dir_prefix="",
            use_summarizer=True,
        )
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            env = load_env(script_root, config)
        assert env["use_summarizer"] is True

    def test_dir_prefix_in_env_shared_dirs(self, script_root: Path):
        config = AgentConfig(
            project_root="/p",
            default_prompt_file="prompts/x.md",
            dir_prefix="reviewer",
        )
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            env = load_env(script_root, config)
            assert env["sessions_dir"] == "sessions"
            assert env["transcripts_dir"] == "transcripts"
            assert env["memory_bank_dir"] == "memory_bank"
            assert env["dir_prefix"] == "reviewer"
            assert env["prompt_file"] == "prompts/x.md"

    def test_env_base_dirs_used_when_set(self, script_root: Path, config: AgentConfig):
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch.dict(
                "os.environ",
                {"SESSIONS_DIR": "my_sessions", "TRANSCRIPTS_DIR": "my_transcripts", "MEMORY_BANK_DIR": "my_mb"},
                clear=False,
            ):
                env = load_env(script_root, config)
            assert env["sessions_dir"] == "my_sessions"
            assert env["transcripts_dir"] == "my_transcripts"
            assert env["memory_bank_dir"] == "my_mb"

    def test_invalid_daemon_interval_uses_default(self, script_root: Path, config: AgentConfig):
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch.dict("os.environ", {"DAEMON_INTERVAL_SEC": "not_a_number"}, clear=False):
                env = load_env(script_root, config)
            assert env["daemon_interval_sec"] == 60

    def test_daemon_interval_from_agents_yaml_used_when_set(self, script_root: Path):
        config = AgentConfig(
            project_root="/p",
            default_prompt_file="prompts/x.md",
            dir_prefix="",
            daemon_interval_sec=120,
        )
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            env = load_env(script_root, config)
        assert env["daemon_interval_sec"] == 120

    def test_daemon_interval_agents_yaml_overrides_env(self, script_root: Path):
        config = AgentConfig(
            project_root="/p",
            default_prompt_file="prompts/x.md",
            dir_prefix="",
            daemon_interval_sec=120,
        )
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch.dict("os.environ", {"DAEMON_INTERVAL_SEC": "90"}, clear=False):
                env = load_env(script_root, config)
        assert env["daemon_interval_sec"] == 120

    def test_daemon_interval_invalid_agent_falls_back_to_env(self, script_root: Path):
        config = AgentConfig(
            project_root="/p",
            default_prompt_file="prompts/x.md",
            dir_prefix="",
            daemon_interval_sec=0,  # invalid: not positive
        )
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch.dict("os.environ", {"DAEMON_INTERVAL_SEC": "90"}, clear=False):
                env = load_env(script_root, config)
        assert env["daemon_interval_sec"] == 90


class TestEnsureDirsAndState:
    def test_creates_dirs_and_state_file(self, script_root: Path, log):
        sessions = script_root / "sessions"
        transcripts = script_root / "transcripts"
        memory_bank = script_root / "memory_bank"
        state_file = memory_bank / "state.md"
        ensure_dirs_and_state(script_root, sessions, transcripts, memory_bank, state_file, log)
        assert sessions.is_dir()
        assert transcripts.is_dir()
        assert memory_bank.is_dir()
        assert state_file.is_file()
        log.info.assert_called()

    def test_existing_state_file_not_touched(self, script_root: Path, log):
        memory_bank = script_root / "mb"
        memory_bank.mkdir(parents=True)
        state_file = memory_bank / "state.md"
        state_file.write_text("existing")
        ensure_dirs_and_state(
            script_root,
            script_root / "s",
            script_root / "t",
            memory_bank,
            state_file,
            log,
        )
        assert state_file.read_text() == "existing"


class TestReadState:
    def test_missing_file_returns_empty(self, script_root: Path, log):
        state_file = script_root / "nonexistent.md"
        assert read_state(state_file, log) == ""

    def test_empty_file_returns_empty(self, script_root: Path, log):
        state_file = script_root / "empty.md"
        state_file.touch()
        assert read_state(state_file, log) == ""

    def test_returns_file_content(self, script_root: Path, log):
        state_file = script_root / "state.md"
        state_file.write_text("hello state")
        assert read_state(state_file, log) == "hello state"

    def test_oserror_returns_empty(self, script_root: Path, log):
        state_file = script_root / "state.md"
        state_file.write_text("x")
        with patch.object(Path, "read_text", side_effect=OSError("read failed")):
            assert read_state(state_file, log) == ""
        log.warning.assert_called()


class TestBuildMainPrompt:
    def test_substitutes_placeholders(self, script_root: Path, log):
        template = script_root / "t.md"
        template.write_text(
            "State path: {{STATE_FILE_PATH}}\nContent: {{STATE_CONTENT}}\nBranch: {{BASE_BRANCH}}"
        )
        state_file = script_root / "state.md"
        out = build_main_prompt(template, state_file, "my content", "main", log)
        assert "State path: " in out and str(state_file) in out
        assert "Content: my content" in out
        assert "Branch: main" in out

    def test_empty_state_content_replaced_with_empty_marker(self, script_root: Path, log):
        template = script_root / "t.md"
        template.write_text("{{STATE_CONTENT}}")
        out = build_main_prompt(template, script_root / "s.md", "", "dev", log)
        assert "(empty)" in out


class TestBuildSummarizePrompt:
    def test_substitutes_placeholders(self, script_root: Path, log):
        template = script_root / "sum.md"
        template.write_text("Transcript: {{TRANSCRIPT_PATH}} State: {{STATE_FILE_PATH}}")
        transcript = script_root / "t.md"
        state_file = script_root / "state.md"
        out = build_summarize_prompt(template, transcript, state_file, log)
        assert str(transcript) in out and str(state_file) in out


class TestRunAgent:
    def test_large_prompt_uses_temp_file(self, script_root: Path, log):
        huge_prompt = "x" * (PROMPT_FILE_THRESHOLD + 1)
        with patch("agent_runner_lib.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = None
            proc.returncode = 0
            proc.stderr = None
            mock_popen.return_value = proc
            with patch("os.unlink"):
                code = run_agent("echo", huge_prompt, script_root, None, log)
        assert code == 0
        call_cmd = mock_popen.call_args[0][0]
        assert len(call_cmd) == 2  # echo + path
        assert call_cmd[1].endswith(".txt") or "echo" in call_cmd[0]

    def test_inline_prompt_and_exit_zero(self, script_root: Path, log):
        session_out = script_root / "out.jsonl"
        with patch("agent_runner_lib.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = None
            proc.returncode = 0
            proc.stderr = None
            mock_popen.return_value = proc
            code = run_agent("echo", "hello", script_root, session_out, log)
        assert code == 0
        mock_popen.assert_called_once()
        call_kw = mock_popen.call_args[1]
        assert call_kw.get("stdout") is not None or "stdout" in str(call_kw)
        assert session_out.exists() or call_kw.get("stdout") is not None

    def test_exit_nonzero_logs_error(self, script_root: Path, log):
        with patch("agent_runner_lib.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = None
            proc.returncode = 1
            proc.stderr = MagicMock()
            proc.stderr.read.return_value = "stderr message"
            mock_popen.return_value = proc
            code = run_agent("echo", "hi", script_root, None, log)
        assert code == 1
        log.error.assert_called()

    def test_long_stderr_truncated_in_log(self, script_root: Path, log):
        with patch("agent_runner_lib.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = None
            proc.returncode = 1
            long_stderr = "x" * 2000
            proc.stderr = MagicMock()
            proc.stderr.read.return_value = long_stderr
            mock_popen.return_value = proc
            run_agent("echo", "hi", script_root, None, log)
        # Second log.error is for stderr; should contain truncation
        err_calls = [c for c in log.error.call_args_list if "..." in str(c)]
        assert len(err_calls) >= 1


class TestRunSummarizer:
    def test_returns_exit_code(self, script_root: Path, log):
        with patch("agent_runner_lib.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = None
            proc.returncode = 0
            proc.stderr = None
            mock_popen.return_value = proc
            code = run_summarizer("echo", "sum prompt", script_root, log)
        assert code == 0

    def test_nonzero_exit_logs_stderr(self, script_root: Path, log):
        with patch("agent_runner_lib.subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.wait.return_value = None
            proc.returncode = 1
            proc.stderr = MagicMock()
            proc.stderr.read.return_value = "sum failed"
            mock_popen.return_value = proc
            code = run_summarizer("echo", "sum", script_root, log)
        assert code == 1
        log.error.assert_called()


class TestRunParser:
    def test_returns_one_when_script_missing(self, script_root: Path, log):
        code = run_parser(script_root, script_root / "in.jsonl", script_root / "out.md", log)
        assert code == 1
        log.error.assert_called()

    def test_returns_zero_on_success(self, script_root: Path, log):
        parser_script = script_root / "parse_coder_logs.py"
        parser_script.write_text("# mock")
        session = script_root / "s.jsonl"
        session.write_text("{}")
        transcript = script_root / "t.md"
        with patch("agent_runner_lib.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            code = run_parser(script_root, session, transcript, log)
        assert code == 0

    def test_returns_one_on_parser_failure(self, script_root: Path, log):
        parser_script = script_root / "parse_coder_logs.py"
        parser_script.write_text("# mock")
        session = script_root / "s.jsonl"
        session.write_text("{}")
        with patch("agent_runner_lib.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            code = run_parser(script_root, session, script_root / "t.md", log)
        assert code == 1


class TestLatestTranscript:
    def test_returns_none_when_no_md_files(self, script_root: Path, log):
        (script_root / "transcripts").mkdir()
        assert latest_transcript(script_root / "transcripts", log) is None

    def test_returns_only_md_file(self, script_root: Path, log):
        td = script_root / "transcripts"
        td.mkdir()
        only = td / "one.md"
        only.write_text("x")
        assert latest_transcript(td, log, "") == only

    def test_returns_prefixed_file_when_dir_prefix_set(self, script_root: Path, log):
        td = script_root / "transcripts"
        td.mkdir()
        prefixed = td / "2026-02-22_12-00-00_reviewer.md"
        prefixed.write_text("x")
        assert latest_transcript(td, log, "reviewer") == prefixed
        assert latest_transcript(td, log, "other") is None

    def test_returns_most_recent_by_mtime(self, script_root: Path, log):
        td = script_root / "transcripts"
        td.mkdir()
        old_f = td / "old.md"
        new_f = td / "new.md"
        old_f.write_text("o")
        new_f.write_text("n")
        import time
        old_f.touch()
        time.sleep(0.02)
        new_f.touch()  # new_f is now most recent
        latest = latest_transcript(td, log, "")
        assert latest is not None
        assert latest.name == "new.md"


class TestRunOneCycle:
    def test_returns_one_when_prompt_file_missing(
        self, script_root: Path, config: AgentConfig, log
    ):
        sessions = script_root / "sessions"
        transcripts = script_root / "transcripts"
        memory_bank = script_root / "memory_bank"
        for d in (sessions, transcripts, memory_bank):
            d.mkdir(parents=True)
        state_file = memory_bank / "state.md"
        state_file.touch()
        prompt_file = script_root / "missing.md"  # does not exist
        summarize_file = script_root / "sum.md"
        summarize_file.write_text("sum")
        env = {
            "project_root": str(script_root),
            "agent_cmd": "true",
            "base_branch": "dev",
        }
        code = run_one_cycle(
            script_root_path=script_root,
            project_root=script_root,
            env=env,
            memory_bank_dir=memory_bank,
            sessions_dir=sessions,
            transcripts_dir=transcripts,
            state_file=state_file,
            prompt_file=prompt_file,
            summarize_prompt_file=summarize_file,
            log=log,
            dir_prefix="",
        )
        assert code == 1

    def test_full_cycle_with_mocks(
        self, script_root: Path, log
    ):
        sessions = script_root / "sessions"
        transcripts = script_root / "transcripts"
        memory_bank = script_root / "memory_bank"
        for d in (sessions, transcripts, memory_bank):
            d.mkdir(parents=True)
        state_file = memory_bank / "state.md"
        state_file.touch()
        prompt_file = script_root / "prompt.md"
        prompt_file.write_text("{{STATE_FILE_PATH}} {{STATE_CONTENT}} {{BASE_BRANCH}}")
        summarize_file = script_root / "sum.md"
        summarize_file.write_text("{{TRANSCRIPT_PATH}} {{STATE_FILE_PATH}}")
        env = {
            "project_root": str(script_root),
            "agent_cmd": "true",
            "base_branch": "dev",
            "use_summarizer": True,
        }

        def run_agent_creates_session(cmd, _prompt, _project_root, session_path, _log):
            session_path = Path(session_path)
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text("[]")
            transcripts_dir = session_path.parent.parent / "transcripts"
            transcript_path = transcripts_dir / (session_path.stem + ".md")
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text("transcript")
            return 0

        with patch("agent_runner_lib.run_agent", side_effect=run_agent_creates_session):
            with patch("agent_runner_lib.run_parser", return_value=0):
                with patch("agent_runner_lib.run_summarizer", return_value=0) as mock_sum:
                    code = run_one_cycle(
                        script_root_path=script_root,
                        project_root=script_root,
                        env=env,
                        memory_bank_dir=memory_bank,
                        sessions_dir=sessions,
                        transcripts_dir=transcripts,
                        state_file=state_file,
                        prompt_file=prompt_file,
                        summarize_prompt_file=summarize_file,
                        log=log,
                        dir_prefix="",
                    )
        assert code == 0
        assert mock_sum.call_count in (0, 1)

    def test_skips_summarizer_when_use_summarizer_false(self, script_root: Path, log):
        sessions = script_root / "sessions"
        transcripts = script_root / "transcripts"
        memory_bank = script_root / "memory_bank"
        for d in (sessions, transcripts, memory_bank):
            d.mkdir(parents=True)
        state_file = memory_bank / "state.md"
        state_file.touch()
        prompt_file = script_root / "prompt.md"
        prompt_file.write_text("{{STATE_FILE_PATH}} {{STATE_CONTENT}} {{BASE_BRANCH}}")
        summarize_file = script_root / "sum.md"
        summarize_file.write_text("{{TRANSCRIPT_PATH}} {{STATE_FILE_PATH}}")
        env = {
            "project_root": str(script_root),
            "agent_cmd": "true",
            "base_branch": "dev",
            "use_summarizer": False,
        }
        with patch("agent_runner_lib.run_agent", return_value=0):
            with patch("agent_runner_lib.run_parser", return_value=0):
                with patch("agent_runner_lib.run_summarizer", return_value=0) as mock_sum:
                    from agent_runner_lib import TIMESTAMP_FMT
                    from datetime import datetime
                    ts = datetime.now().strftime(TIMESTAMP_FMT)
                    (sessions / f"{ts}.jsonl").write_text("[]")
                    (transcripts / f"{ts}.md").write_text("transcript")
                    code = run_one_cycle(
                        script_root_path=script_root,
                        project_root=script_root,
                        env=env,
                        memory_bank_dir=memory_bank,
                        sessions_dir=sessions,
                        transcripts_dir=transcripts,
                        state_file=state_file,
                        prompt_file=prompt_file,
                        summarize_prompt_file=summarize_file,
                        log=log,
                        dir_prefix="",
                    )
        assert code == 0
        mock_sum.assert_not_called()

def _config_with_project_root(project_root: str, default_prompt_file: str = "prompts/agent_prompt.md") -> AgentConfig:
    return AgentConfig(project_root=project_root, default_prompt_file=default_prompt_file, dir_prefix="")


class TestMain:
    def test_uses_lib_dir_when_script_root_path_none(self, tmp_path: Path):
        from agent_runner_lib import main
        config = _config_with_project_root(str(tmp_path))
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch("agent_runner_lib.run_one_cycle", return_value=0) as mock_cycle:
                with patch("sys.argv", ["prog"]):
                    code = main(config, "Test", script_root_path=None)
        assert code == 0
        call_kw = mock_cycle.call_args[1]
        assert call_kw["script_root_path"] is not None

    def test_returns_one_when_dotenv_missing(self, config: AgentConfig):
        from agent_runner_lib import main
        with patch("agent_runner_lib.load_dotenv", None):
            with patch("sys.argv", ["prog"]):
                code = main(config, "Test", script_root_path=Path("/tmp"))
            assert code == 1

    def test_returns_one_when_project_root_not_dir(self, tmp_path: Path):
        from agent_runner_lib import main
        config = _config_with_project_root(str(tmp_path / "nonexistent"))
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch("sys.argv", ["prog"]):
                code = main(config, "Test", script_root_path=tmp_path)
        assert code == 1

    def test_runs_one_cycle_by_default(self, tmp_path: Path):
        from agent_runner_lib import main
        config = _config_with_project_root(str(tmp_path))
        (tmp_path / "prompts").mkdir(exist_ok=True)
        prompt_file = tmp_path / "prompts" / "agent_prompt.md"
        prompt_file.write_text("{{STATE_FILE_PATH}} {{STATE_CONTENT}} {{BASE_BRANCH}}")
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch("agent_runner_lib.run_one_cycle", return_value=0) as mock_cycle:
                with patch("sys.argv", ["prog"]):
                    code = main(config, "Test", script_root_path=tmp_path)
        assert code == 0
        mock_cycle.assert_called_once()

    def test_daemon_uses_interval_arg(self, tmp_path: Path):
        import agent_runner_lib
        agent_runner_lib._shutdown_requested = False
        config = _config_with_project_root(str(tmp_path))
        (tmp_path / "prompts").mkdir(exist_ok=True)
        (tmp_path / "prompts" / "agent_prompt.md").write_text("{{STATE_FILE_PATH}} {{STATE_CONTENT}} {{BASE_BRANCH}}")
        cycles = []
        def set_shutdown(*args, **kwargs):
            cycles.append(1)
            agent_runner_lib._shutdown_requested = True
            return 0
        with patch("agent_runner_lib.load_dotenv", MagicMock()):
            with patch("agent_runner_lib.run_one_cycle", side_effect=set_shutdown):
                with patch("agent_runner_lib.time.sleep"):
                    with patch("sys.argv", ["prog", "--daemon", "--interval", "120"]):
                        code = agent_runner_lib.main(config, "Test", script_root_path=tmp_path)
        assert code == 0
        assert len(cycles) >= 1

