# Cursor agent runner

Runs Cursor agents against a project: each agent has its own prompt, memory bank, and session/transcript dirs. Session logs are parsed to markdown; a shared summarizer updates the agent’s memory state.

## Setup

1. **Dependencies** (Python 3.10+). Using [uv](https://docs.astral.sh/uv/):
   ```bash
   uv sync
   ```

2. **Config:** copy `.env.example` to `.env` and set:
   - **`PROJECT_ROOT`** (required) — path to the repo where the agent runs (e.g. your app or codebase).

   Other vars are optional (agent command, dirs, base branch, log level, daemon interval). Per-agent dirs and prompt can be overridden in `.env` using the keys in `agents.yaml`.

## Usage

Single entrypoint: **`run_agent.py`**. Choose the agent with `--agent` / `-a`.

```bash
# List registered agents
uv run run_agent.py --list-agents

# Run one cycle (agent → parse log → summarizer)
uv run run_agent.py --agent coder
uv run run_agent.py -a reviewer

# Daemon: loop every N seconds (default: DAEMON_INTERVAL_SEC from .env)
uv run run_agent.py -a coder --daemon [--interval 3600]

# Only run summarizer on an existing transcript
uv run run_agent.py -a coder --summarize-only [--transcript path/to/transcript.md]
```

## Agent registry

Agents are defined in **`agents.yaml`**. Each entry has a unique **id** (used with `--agent`) and:

- **name** — display label
- **default_prompt_file** — main prompt (templated with `{{STATE_FILE_PATH}}`, `{{STATE_CONTENT}}`, `{{BASE_BRANCH}}`)
- **default_sessions_dir**, **default_transcripts_dir**, **default_memory_bank_dir** — dirs under this repo
- **\*_env_key** — env var names to override those dirs and the prompt file (see `.env.example`)

Summarization uses the shared **`prompts/summarize_prompt.md`** for all agents.

**Adding an agent:** add a prompt under `prompts/`, then add a new block under `agents:` in `agents.yaml` with the same field shape as `coder` or `reviewer`.

## Testing

Tests use pytest with coverage (uv):

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=agent_runner_lib --cov=run_agent --cov-report=term-missing --cov-fail-under=85
```

Coverage is enforced at 85%. Tests live in `tests/` and mock subprocess and I/O where needed.
