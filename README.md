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
   - (Optional) Copy `commands.yaml.example` to `commands.yaml` to define reusable agent commands that agents can reference by id.

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
- **default_prompt_file** — main prompt (templated with `{{STATE_FILE_PATH}}`, `{{STATE_CONTENT}}`, `{{BASE_BRANCH}}`, and optionally `{{FILE_LIST}}` for agents that use an extra file list)
- **dir_prefix** — used for this agent's file names inside the shared `sessions/`, `transcripts/`, and `memory_bank` dirs (e.g. `"reviewer"` → `state_reviewer.md`, `{timestamp}_reviewer.jsonl`)
- **daemon_interval_sec** — (optional) seconds between daemon cycles for this agent; overrides `.env` `DAEMON_INTERVAL_SEC`. Resolution order: CLI `--interval` → agents.yaml → .env → default 60.
- **command** — (optional) id of the command to use from `commands.yaml` for this agent. When set, it overrides the global `AGENT_CMD` and the built-in default.
- **parse_json_logs** — (optional, default `true`) whether this agent's command produces JSON logs that should be parsed by `parse_coder_logs.py` into markdown transcripts. Set to `false` to skip parsing (and thereby skip the summarizer, which depends on parsed transcripts).

By default agents update their own memory state. Set **use_summarizer: true** for an agent to use the shared **`prompts/summarize_prompt.md`**.

**Adding an agent:** add a prompt under `prompts/`, then add a new block under `agents:` in `agents.yaml` with the same field shape as `coder` or `reviewer`.

For more generic roles, you can use `prompts/generic_agent_prompt.md` and a `generic` agent entry in `agents.yaml` that includes an optional `file_list` field. The `file_list` is a multi-line string of paths relative to `project_root`; it is substituted into the `{{FILE_LIST}}` placeholder in the generic prompt so the agent knows which files to read for additional context.

## Command resolution and prompt placement

The agent CLI command is resolved in this order:

- **Per-agent command id** — if an agent in `agents.yaml` specifies `command: <id>`, the runner looks up `<id>` under `commands:` in `commands.yaml` and uses that command line.
- **Global `AGENT_CMD`** — if set in `.env`, used for all agents that do not specify `command`.
- **Built-in default** — `agent -p --force --model auto --approve-mcps --output-format stream-json`.

In all cases, the generated prompt argument is passed to the underlying command. If the token `__PROMPT__` appears as a separate argument in the command string, it is replaced with the prompt argument in-place; otherwise the prompt argument is appended as the final argument.

## Testing

Tests use pytest with coverage (uv):

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=agent_runner_lib --cov=run_agent --cov-report=term-missing --cov-fail-under=85
```

Coverage is enforced at 85%. Tests live in `tests/` and mock subprocess and I/O where needed.
