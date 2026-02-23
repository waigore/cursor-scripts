"""
Shared logic for running Cursor agent scripts (run_coder_agent, run_reviewer_agent, etc.).
All agents share sessions/, transcripts/, and memory_bank/; per-agent files are named with dir_prefix.
"""

from __future__ import annotations

import argparse
import logging
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
except ImportError:
    load_dotenv = None  # type: ignore[assignment]

# Daemon: set when SIGINT/SIGTERM received so loop can exit cleanly
_shutdown_requested = False
# Subprocess we're waiting on; signal handler terminates it for immediate exit
_current_process: subprocess.Popen | None = None


def _on_shutdown_signal(_signum: int, _frame: object) -> None:
    global _shutdown_requested, _current_process
    _shutdown_requested = True
    if _current_process is not None:
        try:
            _current_process.terminate()
        except OSError:
            pass


# Shared defaults (overridden by .env or per-agent config)
DEFAULT_AGENT_CMD = "agent -p --force --model auto --approve-mcps --output-format stream-json"
DEFAULT_SUMMARIZE_PROMPT_FILE = "prompts/summarize_prompt.md"
DEFAULT_BASE_BRANCH = "dev"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_DAEMON_INTERVAL_SEC = 60
TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"
PROMPT_FILE_THRESHOLD = 100_000


@dataclass(frozen=True)
class AgentConfig:
    """Per-agent config: project root, prompt file, and dir prefix for sessions/transcripts/memory_bank."""

    project_root: str
    default_prompt_file: str
    dir_prefix: str = ""
    daemon_interval_sec: int | None = None
    use_summarizer: bool = False


def script_root(caller_file: str) -> Path:
    return Path(caller_file).resolve().parent


def resolve_path(value: str, script_root_path: Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = script_root_path / p
    return p.resolve()


def setup_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def load_env(script_root_path: Path, config: AgentConfig) -> dict[str, str | int]:
    if load_dotenv is None:
        logging.error("python-dotenv is not installed; run: uv sync")
        sys.exit(1)
    env_path = script_root_path / ".env"
    if not env_path.is_file():
        logging.warning(".env file not found at %s", env_path)
    else:
        load_dotenv(env_path)
    project_root = (config.project_root or "").strip()
    if not project_root:
        logging.error("project_root is required for this agent; set it in agents.yaml")
        sys.exit(1)
    # Resolution: agents.yaml daemon_interval_sec (if set and valid) -> .env DAEMON_INTERVAL_SEC -> default
    def _interval_from_env() -> int:
        raw = os.environ.get("DAEMON_INTERVAL_SEC", str(DEFAULT_DAEMON_INTERVAL_SEC)).strip()
        try:
            return int(raw)
        except ValueError:
            return DEFAULT_DAEMON_INTERVAL_SEC

    if config.daemon_interval_sec is not None:
        try:
            val = int(config.daemon_interval_sec)
            daemon_interval_sec = val if val > 0 else _interval_from_env()
        except (TypeError, ValueError):
            daemon_interval_sec = _interval_from_env()
    else:
        daemon_interval_sec = _interval_from_env()
    base_sessions = os.environ.get("SESSIONS_DIR", "sessions").strip() or "sessions"
    base_transcripts = os.environ.get("TRANSCRIPTS_DIR", "transcripts").strip() or "transcripts"
    base_memory_bank = os.environ.get("MEMORY_BANK_DIR", "memory_bank").strip() or "memory_bank"
    return {
        "project_root": project_root,
        "agent_cmd": os.environ.get("AGENT_CMD", DEFAULT_AGENT_CMD).strip() or DEFAULT_AGENT_CMD,
        "memory_bank_dir": base_memory_bank,
        "sessions_dir": base_sessions,
        "transcripts_dir": base_transcripts,
        "dir_prefix": config.dir_prefix,
        "prompt_file": config.default_prompt_file,
        "base_branch": os.environ.get("BASE_BRANCH", DEFAULT_BASE_BRANCH).strip() or DEFAULT_BASE_BRANCH,
        "log_level": os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip() or DEFAULT_LOG_LEVEL,
        "daemon_interval_sec": daemon_interval_sec,
        "use_summarizer": getattr(config, "use_summarizer", False),
    }


def ensure_dirs_and_state(
    script_root_path: Path,
    sessions_dir: Path,
    transcripts_dir: Path,
    memory_bank_dir: Path,
    state_file: Path,
    log: logging.Logger,
) -> None:
    for d in (sessions_dir, transcripts_dir, memory_bank_dir):
        d.mkdir(parents=True, exist_ok=True)
    if not state_file.exists():
        state_file.touch()
        log.info("Initialized empty state file at %s", state_file)


def read_state(state_file: Path, log: logging.Logger) -> str:
    if not state_file.exists() or state_file.stat().st_size == 0:
        log.info("No state file or empty; using empty state content")
        return ""
    try:
        content = state_file.read_text(encoding="utf-8")
        log.info("Loaded state from %s", state_file)
        log.debug("State file path passed to summarizer; length=%d", len(content))
        return content
    except OSError as e:
        log.warning("Could not read state file %s: %s", state_file, e)
        return ""


def build_main_prompt(
    template_path: Path,
    state_file_path: Path,
    state_content: str,
    base_branch: str,
    log: logging.Logger,
) -> str:
    log.info("Building main prompt")
    log.debug("Template path=%s, state file path=%s, state length=%d", template_path, state_file_path, len(state_content))
    template = template_path.read_text(encoding="utf-8")
    return (
        template.replace("{{STATE_FILE_PATH}}", str(state_file_path))
        .replace("{{STATE_CONTENT}}", state_content or "(empty)")
        .replace("{{BASE_BRANCH}}", base_branch)
    )


def build_summarize_prompt(
    template_path: Path,
    transcript_path: Path,
    state_file_path: Path,
    log: logging.Logger,
) -> str:
    log.info("Building summarizer prompt")
    log.debug("Transcript path=%s, state file path=%s", transcript_path, state_file_path)
    template = template_path.read_text(encoding="utf-8")
    return (
        template.replace("{{TRANSCRIPT_PATH}}", str(transcript_path)).replace(
            "{{STATE_FILE_PATH}}", str(state_file_path)
        )
    )


def run_agent(
    agent_cmd: str,
    prompt: str,
    cwd: Path,
    session_out_path: Path | None,
    log: logging.Logger,
) -> int:
    """Run the agent CLI with the given prompt and cwd. If session_out_path is set, capture stdout there. Returns exit code."""
    global _current_process
    use_temp_file = len(prompt) > PROMPT_FILE_THRESHOLD
    if use_temp_file:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
            f.write(prompt)
            prompt_arg = f.name
        log.debug("Prompt written to temp file %s (length=%d)", prompt_arg, len(prompt))
    else:
        prompt_arg = prompt
    try:
        parts = shlex.split(agent_cmd)
        cmd = parts + [prompt_arg]
        log.info("Starting main agent run: cwd=%s, session_out=%s", cwd, session_out_path)
        kwargs: dict = {"cwd": str(cwd), "env": {**os.environ}, "text": True}
        if session_out_path is not None:
            kwargs["stdout"] = open(session_out_path, "w", encoding="utf-8")  # noqa: SIM115
            kwargs["stderr"] = subprocess.PIPE
        stdout_handle = kwargs.get("stdout")
        try:
            proc = subprocess.Popen(cmd, **kwargs)
            _current_process = proc
            try:
                proc.wait()
            finally:
                _current_process = None
            returncode = proc.returncode
            stderr_output = proc.stderr.read() if proc.stderr else None
        finally:
            if stdout_handle is not None:
                stdout_handle.close()
        if returncode != 0:
            log.error("Agent exited with return code %s", returncode)
            if stderr_output:
                log.error("Stderr: %s", (stderr_output[:1000] + "...") if len(stderr_output) > 1000 else stderr_output)
        else:
            log.info("Agent process exited with return code 0")
        return returncode
    finally:
        if use_temp_file:
            try:
                os.unlink(prompt_arg)
            except OSError:
                pass


def run_summarizer(
    agent_cmd: str,
    prompt: str,
    cwd: Path,
    log: logging.Logger,
) -> int:
    """Run the agent with the summarizer prompt. Returns exit code."""
    global _current_process
    use_temp_file = len(prompt) > PROMPT_FILE_THRESHOLD
    if use_temp_file:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
            f.write(prompt)
            prompt_arg = f.name
    else:
        prompt_arg = prompt
    try:
        parts = shlex.split(agent_cmd)
        cmd = parts + [prompt_arg]
        log.info("Starting summarizer agent: cwd=%s", cwd)
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), env=os.environ, stderr=subprocess.PIPE, text=True
        )
        _current_process = proc
        try:
            proc.wait()
        finally:
            _current_process = None
        returncode = proc.returncode
        stderr_output = proc.stderr.read() if proc.stderr else None
        if returncode != 0:
            log.error("Summarizer agent exited with return code %s", returncode)
            if stderr_output:
                log.error("Stderr: %s", (stderr_output[:1000] + "...") if len(stderr_output) > 1000 else stderr_output)
        else:
            log.info("Summarizer agent process exited with return code 0")
        return returncode
    finally:
        if use_temp_file:
            try:
                os.unlink(prompt_arg)
            except OSError:
                pass


def run_parser(script_root_path: Path, session_path: Path, transcript_path: Path, log: logging.Logger) -> int:
    parser_script = script_root_path / "parse_coder_logs.py"
    if not parser_script.is_file():
        log.error("parse_coder_logs.py not found at %s", parser_script)
        return 1
    log.info("Running parse_coder_logs: input=%s, output=%s", session_path, transcript_path)
    result = subprocess.run(
        [sys.executable, str(parser_script), str(session_path), "-o", str(transcript_path)],
        cwd=str(script_root_path),
    )
    if result.returncode != 0:
        log.error("parse_coder_logs exited with return code %s", result.returncode)
        return result.returncode
    log.info("parse_coder_logs completed successfully")
    return 0


def latest_transcript(
    transcripts_dir: Path, log: logging.Logger, dir_prefix: str = ""
) -> Path | None:
    """Return the path to the most recently modified .md file in transcripts_dir for this agent, or None."""
    pattern = f"*_{dir_prefix}.md" if dir_prefix else "*.md"
    md_files = list(transcripts_dir.glob(pattern))
    if not md_files:
        return None
    latest = max(md_files, key=lambda p: p.stat().st_mtime)
    log.info("Using latest transcript: %s", latest)
    return latest


def run_one_cycle(
    *,
    script_root_path: Path,
    project_root: Path,
    env: dict[str, str | int],
    memory_bank_dir: Path,
    sessions_dir: Path,
    transcripts_dir: Path,
    state_file: Path,
    prompt_file: Path,
    summarize_prompt_file: Path,
    log: logging.Logger,
    dir_prefix: str = "",
) -> int:
    """Run one full cycle: agent, parse session log, then summarizer. Returns exit code."""
    state_content = read_state(state_file, log)
    if not prompt_file.is_file():
        log.error("Prompt file not found: %s", prompt_file)
        return 1
    main_prompt = build_main_prompt(prompt_file, state_file, state_content, str(env["base_branch"]), log)
    timestamp = datetime.now().strftime(TIMESTAMP_FMT)
    session_suffix = f"{timestamp}_{dir_prefix}.jsonl" if dir_prefix else f"{timestamp}.jsonl"
    transcript_suffix = f"{timestamp}_{dir_prefix}.md" if dir_prefix else f"{timestamp}.md"
    session_path = sessions_dir / session_suffix
    transcript_path = transcripts_dir / transcript_suffix

    exit_code = run_agent(str(env["agent_cmd"]), main_prompt, project_root, session_path, log)
    if _shutdown_requested:
        return exit_code
    if exit_code != 0:
        log.warning("Main agent run failed; continuing to parse and summarizer anyway")

    if not session_path.is_file():
        log.error("Session log was not created at %s; cannot run parser", session_path)
        return 1
    parser_exit = run_parser(script_root_path, session_path, transcript_path, log)
    if _shutdown_requested:
        return parser_exit
    if parser_exit != 0:
        log.error("Parser failed; skipping summarizer run")
        return parser_exit

    if not env.get("use_summarizer", False):
        log.info("Summarizer disabled for this agent; skipping summarizer run")
        return 0 if exit_code == 0 else exit_code

    if not summarize_prompt_file.is_file():
        log.warning("Summarizer prompt file not found at %s; skipping summarizer run", summarize_prompt_file)
        return 0 if exit_code == 0 else exit_code

    # Optional shared summarizer (use_summarizer: true in agents.yaml); tested in test_full_cycle_with_mocks
    summarizer_prompt = build_summarize_prompt(summarize_prompt_file, transcript_path, state_file, log)  # pragma: no cover
    log.info("Summarizer: transcript=%s, state=%s", transcript_path, state_file)  # pragma: no cover
    run_summarizer(str(env["agent_cmd"]), summarizer_prompt, script_root_path, log)  # pragma: no cover
    return 0 if exit_code == 0 else exit_code


def main(config: AgentConfig, description: str, script_root_path: Path | None = None) -> int:
    if script_root_path is None:
        script_root_path = Path(__file__).resolve().parent
    if load_dotenv is None:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
        logging.error("python-dotenv is not installed; run: uv sync")
        return 1
    load_dotenv(script_root_path / ".env")
    log_level = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip() or DEFAULT_LOG_LEVEL
    setup_logging(log_level)
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon: loop (agent run → parse → summarize) until SIGINT/SIGTERM.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        metavar="SEC",
        help="Seconds between daemon cycles (default: DAEMON_INTERVAL_SEC env or %d)." % DEFAULT_DAEMON_INTERVAL_SEC,
    )
    args = parser.parse_args()

    env = load_env(script_root_path, config)
    project_root = Path(str(env["project_root"])).resolve()
    if not project_root.is_dir():
        log.error("PROJECT_ROOT is not a directory: %s", project_root)
        return 1

    memory_bank_dir = resolve_path(str(env["memory_bank_dir"]), script_root_path)
    sessions_dir = resolve_path(str(env["sessions_dir"]), script_root_path)
    transcripts_dir = resolve_path(str(env["transcripts_dir"]), script_root_path)
    dir_prefix = str(env.get("dir_prefix", ""))
    state_file = memory_bank_dir / ("state.md" if not dir_prefix else f"state_{dir_prefix}.md")
    prompt_file = resolve_path(str(env["prompt_file"]), script_root_path)
    summarize_prompt_file = resolve_path(DEFAULT_SUMMARIZE_PROMPT_FILE, script_root_path)

    log.info(
        "Script root=%s, project_root=%s, sessions=%s, transcripts=%s, memory_bank=%s, state_file=%s",
        script_root_path,
        project_root,
        sessions_dir,
        transcripts_dir,
        memory_bank_dir,
        state_file,
    )
    if os.environ.get("AGENT_CMD"):
        log.debug("Using AGENT_CMD from env")
    else:
        log.debug("Using default AGENT_CMD")

    ensure_dirs_and_state(script_root_path, sessions_dir, transcripts_dir, memory_bank_dir, state_file, log)

    if args.daemon:
        interval_sec = args.interval if args.interval is not None else env["daemon_interval_sec"]
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _on_shutdown_signal)
            except (ValueError, OSError):
                pass
        log.info("Daemon mode: using interval=%s s (Ctrl+C or SIGTERM to stop)", interval_sec)
        cycle = 0
        while not _shutdown_requested:
            cycle += 1
            log.info("Daemon cycle %d starting", cycle)
            run_one_cycle(
                script_root_path=script_root_path,
                project_root=project_root,
                env=env,
                memory_bank_dir=memory_bank_dir,
                sessions_dir=sessions_dir,
                transcripts_dir=transcripts_dir,
                state_file=state_file,
                prompt_file=prompt_file,
                summarize_prompt_file=summarize_prompt_file,
                log=log,
                dir_prefix=dir_prefix,
            )
            if _shutdown_requested:
                break
            for _ in range(interval_sec):
                if _shutdown_requested:
                    break
                time.sleep(1)
        log.info("Daemon shutting down (signal received)")
        return 0

    return run_one_cycle(
        script_root_path=script_root_path,
        project_root=project_root,
        env=env,
        memory_bank_dir=memory_bank_dir,
        sessions_dir=sessions_dir,
        transcripts_dir=transcripts_dir,
        state_file=state_file,
        prompt_file=prompt_file,
        summarize_prompt_file=summarize_prompt_file,
        log=log,
        dir_prefix=dir_prefix,
    )
