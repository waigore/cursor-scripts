## Task

Read the transcript at **{{TRANSCRIPT_PATH}}**, then write/overwrite the state file at **{{STATE_FILE_PATH}}** with the following structured content. Use the absolute paths given; the state file is in the memory bank (outside the project).

## State file format

Write exactly one markdown file with these sections. Use project-relative paths for specs (e.g. `SPEC/...`).

- **## Outstanding tasks** — Bullet list of follow-up or unfinished work; reference specs by path (e.g. `SPEC/game/foo.md`) where relevant.
- **## Open PRs** — Bullet list: PR title, link, branch, status (open/merged).
- **## Refs to specs** — Bullet list of spec paths under the project that are relevant to current work (e.g. `SPEC/game/leader-bonuses.md`).
- **## Issues raised** — Bullet list of GitHub issue links that this agent opened (so they can be re-checked in a future run). Combine issue links from the current state file's Issues raised section with any new issue links reported in the transcript; deduplicate and list all that are still open. Use "(none)" if the transcript does not report any and the current state has none.
- **## Issues assigned to me** — Bullet list of GitHub issue links currently assigned to this agent. Use "(none)" if the transcript does not report any.

If a section has nothing to report, write the section header followed by “(none)” or a single “-” and a short note.

Do not add any text before or after the state file content; your reply should be the exact content to write to {{STATE_FILE_PATH}}, or clearly indicate that you have written the file at that path.
