# Cursor agent runner

Runs Cursor agents against a project: each agent has its own prompt, memory bank, and session/transcript dirs. Session logs are parsed to markdown. By default each agent updates its own memory state; you can enable a shared summarizer per agent in agents.yaml.

## Setup

1. **Dependencies** (Python 3.10+). Using [uv](https://docs.astral.sh/uv/):
   ```bash
   uv sync
   ```

2. **Config:**
   - Copy `.env.example` to `.env`. All vars there are optional (agent command, base branch, daemon interval, log level, shared base dirs).
   - Copy `agents.yaml.example` to `agents.yaml` and set **`project_root`** (and any other values) for each agent. `agents.yaml` is not shipped; the tool fails if it is missing.

## Usage

Single entrypoint: **`run_agent.py`**. Choose the agent with `--agent` / `-a`.

```bash
# List registered agents
uv run run_agent.py --list-agents

# Run one cycle (agent → parse log; summarizer only if use_summarizer: true for that agent)
uv run run_agent.py --agent coder
uv run run_agent.py -a reviewer

# Daemon: loop every N seconds (resolution: --interval > agents.yaml daemon_interval_sec > .env DAEMON_INTERVAL_SEC > 60)
uv run run_agent.py -a coder --daemon [--interval 60]
```

## Agent registry

Agents are defined in **`agents.yaml`** (create it by copying **`agents.yaml.example`**). Each entry has a unique **id** (used with `--agent`) and:

- **name** — display label
- **project_root** — (required) path to the repo where this agent runs
- **default_prompt_file** — main prompt (templated with `{{STATE_FILE_PATH}}`, `{{STATE_CONTENT}}`, `{{BASE_BRANCH}}`)
- **dir_prefix** — used for this agent's file names inside the shared `sessions/`, `transcripts/`, and `memory_bank/` dirs (e.g. `"reviewer"` → `state_reviewer.md`, `{timestamp}_reviewer.jsonl`)
- **daemon_interval_sec** — (optional) seconds between daemon cycles for this agent; overrides `.env` `DAEMON_INTERVAL_SEC`. Resolution order: CLI `--interval` → agents.yaml → .env → default 60.’s file names inside the shared `sessions/`, `transcripts/`, and `memory_bank/` dirs (e.g. `"reviewer"` → `state_reviewer.md`, `{timestamp}_reviewer.jsonl`)

By default agents update their own memory state. Set **use_summarizer: true** for an agent to use the shared **`prompts/summarize_prompt.md`**.

**Adding an agent:** add a prompt under `prompts/`, then add a new block under `agents:` in `agents.yaml` with the same field shape as `coder` or `reviewer`.

## Testing

Tests use pytest with coverage (uv):

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=agent_runner_lib --cov=run_agent --cov-report=term-missing --cov-fail-under=85
```

Coverage is enforced at 85%. Tests live in `tests/` and mock subprocess and I/O where needed.
