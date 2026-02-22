#!/usr/bin/env python3
"""
Run the Cursor agent in the project directory, capture session logs to sessions/,
post-process to transcripts/, then run a summarizer agent to update memory_bank/state.md.
Config via .env (required: PROJECT_ROOT). See .env.example.
"""

from __future__ import annotations

import argparse
import logging
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Load .env before using os.environ (required: pip install python-dotenv)
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
except ImportError:
    load_dotenv = None  # type: ignore[assignment]

# Defaults (overridden by .env)
DEFAULT_AGENT_CMD = "agent -p --force --model auto --approve-mcps --output-format stream-json"
DEFAULT_MEMORY_BANK_DIR = "memory_bank"
DEFAULT_SESSIONS_DIR = "sessions"
DEFAULT_TRANSCRIPTS_DIR = "transcripts"
DEFAULT_PROMPT_FILE = "prompts/agent_prompt.md"
DEFAULT_SUMMARIZE_PROMPT_FILE = "prompts/summarize_prompt.md"
DEFAULT_BASE_BRANCH = "dev"
DEFAULT_LOG_LEVEL = "INFO"
TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"

# Prompt longer than this (chars) is written to a temp file and path is passed to agent
PROMPT_FILE_THRESHOLD = 100_000


def _script_root() -> Path:
    return Path(__file__).resolve().parent


def _resolve_path(value: str, script_root: Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = script_root / p
    return p.resolve()


def _setup_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def _load_env(script_root: Path) -> dict[str, str]:
    if load_dotenv is None:
        logging.error("python-dotenv is not installed; pip install python-dotenv")
        sys.exit(1)
    env_path = script_root / ".env"
    if not env_path.is_file():
        logging.warning(".env file not found at %s", env_path)
    else:
        load_dotenv(env_path)
    project_root = os.environ.get("PROJECT_ROOT", "").strip()
    if not project_root:
        logging.error("PROJECT_ROOT is required; set it in .env (see .env.example)")
        sys.exit(1)
    return {
        "project_root": project_root,
        "agent_cmd": os.environ.get("AGENT_CMD", DEFAULT_AGENT_CMD).strip() or DEFAULT_AGENT_CMD,
        "memory_bank_dir": os.environ.get("MEMORY_BANK_DIR", DEFAULT_MEMORY_BANK_DIR).strip() or DEFAULT_MEMORY_BANK_DIR,
        "sessions_dir": os.environ.get("SESSIONS_DIR", DEFAULT_SESSIONS_DIR).strip() or DEFAULT_SESSIONS_DIR,
        "transcripts_dir": os.environ.get("TRANSCRIPTS_DIR", DEFAULT_TRANSCRIPTS_DIR).strip() or DEFAULT_TRANSCRIPTS_DIR,
        "prompt_file": os.environ.get("PROMPT_FILE", DEFAULT_PROMPT_FILE).strip() or DEFAULT_PROMPT_FILE,
        "base_branch": os.environ.get("BASE_BRANCH", DEFAULT_BASE_BRANCH).strip() or DEFAULT_BASE_BRANCH,
        "log_level": os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip() or DEFAULT_LOG_LEVEL,
    }


def _ensure_dirs_and_state(
    script_root: Path,
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


def _read_state(state_file: Path, log: logging.Logger) -> str:
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


def _build_main_prompt(
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


def _build_summarize_prompt(
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


def _run_agent(
    agent_cmd: str,
    prompt: str,
    cwd: Path,
    session_out_path: Path | None,
    log: logging.Logger,
) -> int:
    """Run the agent CLI with the given prompt and cwd. If session_out_path is set, capture stdout there. Returns exit code."""
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
        kwargs: dict = {"cwd": str(cwd), "env": {**os.environ}}
        if session_out_path is not None:
            kwargs["stdout"] = open(session_out_path, "w", encoding="utf-8")  # noqa: SIM115
            kwargs["stderr"] = subprocess.PIPE
            kwargs["text"] = True
        try:
            result = subprocess.run(cmd, **kwargs)
        finally:
            if session_out_path is not None and "stdout" in kwargs and kwargs["stdout"] is not None:
                kwargs["stdout"].close()
        if result.returncode != 0:
            log.error("Agent exited with return code %s", result.returncode)
            if result.stderr:
                log.error("Stderr: %s", (result.stderr[:1000] + "...") if len(result.stderr) > 1000 else result.stderr)
        else:
            log.info("Agent process exited with return code 0")
        return result.returncode
    finally:
        if use_temp_file:
            try:
                os.unlink(prompt_arg)
            except OSError:
                pass


def _run_summarizer(
    agent_cmd: str,
    prompt: str,
    cwd: Path,
    log: logging.Logger,
) -> int:
    """Run the agent with the summarizer prompt. Returns exit code."""
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
        result = subprocess.run(cmd, cwd=str(cwd), env=os.environ, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            log.error("Summarizer agent exited with return code %s", result.returncode)
            if result.stderr:
                log.error("Stderr: %s", (result.stderr[:1000] + "...") if len(result.stderr) > 1000 else result.stderr)
        else:
            log.info("Summarizer agent process exited with return code 0")
        return result.returncode
    finally:
        if use_temp_file:
            try:
                os.unlink(prompt_arg)
            except OSError:
                pass


def _run_parser(script_root: Path, session_path: Path, transcript_path: Path, log: logging.Logger) -> int:
    parser_script = script_root / "parse_coder_logs.py"
    if not parser_script.is_file():
        log.error("parse_coder_logs.py not found at %s", parser_script)
        return 1
    log.info("Running parse_coder_logs: input=%s, output=%s", session_path, transcript_path)
    result = subprocess.run(
        [sys.executable, str(parser_script), str(session_path), "-o", str(transcript_path)],
        cwd=str(script_root),
    )
    if result.returncode != 0:
        log.error("parse_coder_logs exited with return code %s", result.returncode)
        return result.returncode
    log.info("parse_coder_logs completed successfully")
    return 0


def _latest_transcript(transcripts_dir: Path, log: logging.Logger) -> Path | None:
    """Return the path to the most recently modified .md file in transcripts_dir, or None."""
    md_files = list(transcripts_dir.glob("*.md"))
    if not md_files:
        return None
    latest = max(md_files, key=lambda p: p.stat().st_mtime)
    log.info("Using latest transcript: %s", latest)
    return latest


def main() -> int:
    script_root = _script_root()
    # Load env early to get LOG_LEVEL and PROJECT_ROOT
    if load_dotenv is None:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
        logging.error("python-dotenv is not installed; pip install python-dotenv")
        return 1
    load_dotenv(script_root / ".env")
    log_level = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip() or DEFAULT_LOG_LEVEL
    _setup_logging(log_level)
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Run Cursor agent and optional summarizer.")
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Skip main agent; run summarizer on an existing transcript only.",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=None,
        metavar="PATH",
        help="Transcript file for --summarize-only (default: latest in transcripts dir).",
    )
    args = parser.parse_args()

    env = _load_env(script_root)
    project_root = Path(env["project_root"]).resolve()
    if not project_root.is_dir():
        log.error("PROJECT_ROOT is not a directory: %s", project_root)
        return 1

    memory_bank_dir = _resolve_path(env["memory_bank_dir"], script_root)
    sessions_dir = _resolve_path(env["sessions_dir"], script_root)
    transcripts_dir = _resolve_path(env["transcripts_dir"], script_root)
    state_file = memory_bank_dir / "state.md"
    prompt_file = _resolve_path(env["prompt_file"], script_root)
    summarize_prompt_file = _resolve_path(DEFAULT_SUMMARIZE_PROMPT_FILE, script_root)

    log.info(
        "Script root=%s, project_root=%s, sessions=%s, transcripts=%s, memory_bank=%s, state_file=%s",
        script_root,
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

    _ensure_dirs_and_state(script_root, sessions_dir, transcripts_dir, memory_bank_dir, state_file, log)

    if args.summarize_only:
        transcript_path = args.transcript
        if transcript_path is not None:
            transcript_path = _resolve_path(str(transcript_path), script_root) if not transcript_path.is_absolute() else transcript_path
            if not transcript_path.is_file():
                log.error("Transcript file not found: %s", transcript_path)
                return 1
        else:
            transcript_path = _latest_transcript(transcripts_dir, log)
            if transcript_path is None:
                log.error("No transcript found in %s; specify --transcript PATH", transcripts_dir)
                return 1
        if not summarize_prompt_file.is_file():
            log.error("Summarizer prompt file not found: %s", summarize_prompt_file)
            return 1
        summarizer_prompt = _build_summarize_prompt(summarize_prompt_file, transcript_path, state_file, log)
        log.info("Summarizer only: transcript=%s, state=%s", transcript_path, state_file)
        return _run_summarizer(env["agent_cmd"], summarizer_prompt, script_root, log)

    state_content = _read_state(state_file, log)

    if not prompt_file.is_file():
        log.error("Prompt file not found: %s", prompt_file)
        return 1

    main_prompt = _build_main_prompt(prompt_file, state_file, state_content, env["base_branch"], log)
    timestamp = datetime.now().strftime(TIMESTAMP_FMT)
    session_path = sessions_dir / f"{timestamp}.jsonl"
    transcript_path = transcripts_dir / f"{timestamp}.md"

    exit_code = _run_agent(env["agent_cmd"], main_prompt, project_root, session_path, log)
    if exit_code != 0:
        log.warning("Main agent run failed; continuing to parse and summarizer anyway")

    if not session_path.is_file():
        log.error("Session log was not created at %s; cannot run parser", session_path)
        return 1
    parser_exit = _run_parser(script_root, session_path, transcript_path, log)
    if parser_exit != 0:
        log.error("Parser failed; skipping summarizer run")
        return parser_exit

    if not summarize_prompt_file.is_file():
        log.warning("Summarizer prompt file not found at %s; skipping summarizer run", summarize_prompt_file)
        return 0

    summarizer_prompt = _build_summarize_prompt(summarize_prompt_file, transcript_path, state_file, log)
    log.info("Summarizer: transcript=%s, state=%s", transcript_path, state_file)
    _run_summarizer(env["agent_cmd"], summarizer_prompt, script_root, log)

    return 0 if exit_code == 0 else exit_code


if __name__ == "__main__":
    sys.exit(main())
