# User-level systemd services for Cursor agents

These units run the coder and reviewer agent daemons as **user** services (no root). Each service uses the single entrypoint `run_agent.py --agent <id> --daemon`.

## Path and folder access

- **WorkingDirectory** in each unit is set to `%h/cursor-scripts` (your home + `cursor-scripts`). The scripts resolve all repo paths (`.env`, `prompts/`, `agents.yaml`, `sessions/`, `transcripts/`, `memory_bank/`) from this directory. If your repo lives elsewhere, edit `WorkingDirectory` in the unit (or use a drop-in) so it points to the directory that contains `run_agent.py` and `.env`.
- **PROJECT_ROOT** in `.env` is the project the agent operates on; it can be any path your user can read/write. When the service runs, it uses your user account, so access is the same as when you run the script by hand.

## Logs

- **Coder:** `~/.local/log/cursor-agent/coder-agent.log`
- **Reviewer:** `~/.local/log/cursor-agent/reviewer-agent.log`

The directory is created automatically when the service starts. You can tail logs with:

```bash
tail -f ~/.local/log/cursor-agent/coder-agent.log
tail -f ~/.local/log/cursor-agent/reviewer-agent.log
```

User journal (if you use it):

```bash
journalctl --user -u coder-agent.service -f
journalctl --user -u reviewer-agent.service -f
```

## Install

```bash
mkdir -p ~/.config/systemd/user
cp "$(pwd)/systemd/user/coder-agent.service" ~/.config/systemd/user/
cp "$(pwd)/systemd/user/reviewer-agent.service" ~/.config/systemd/user/

# If cursor-scripts is not in ~/cursor-scripts, edit WorkingDirectory in each file:
#   WorkingDirectory=/absolute/path/to/cursor-scripts

systemctl --user daemon-reload
systemctl --user enable coder-agent.service reviewer-agent.service
systemctl --user start coder-agent.service reviewer-agent.service
```

## Using uv

The service files expect a project virtualenv at `WorkingDirectory/.venv` (e.g. after `uv sync` in the cursor-scripts repo). If cursor-scripts is not in `~/cursor-scripts`, use a drop-in to set both `WorkingDirectory` and `ExecStart` to your path:

```bash
mkdir -p ~/.config/systemd/user/coder-agent.service.d
cat > ~/.config/systemd/user/coder-agent.service.d/override.conf << 'EOF'
[Service]
WorkingDirectory=/absolute/path/to/cursor-scripts
ExecStart=/absolute/path/to/cursor-scripts/.venv/bin/python run_agent.py --agent coder --daemon
EOF
systemctl --user daemon-reload
systemctl --user restart coder-agent.service
```

Do the same for `reviewer-agent.service.d` with `--agent reviewer` if needed. To use system Python instead of uv’s venv, point `ExecStart` at your system `python3` and ensure dependencies are installed (e.g. `uv pip install -r requirements.txt` elsewhere or use a system package).
