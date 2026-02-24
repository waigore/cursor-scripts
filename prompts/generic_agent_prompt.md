## Context

**Base branch:** {{BASE_BRANCH}}.

Memory bank state is at **{{STATE_FILE_PATH}}** (outside the project; use the absolute path). It tracks outstanding tasks, open PRs, and refs to specs (usually under `SPEC/`).

Here are the **context files** for this run (paths are relative to `project_root`):

```
{{FILE_LIST}}
```

Read the state when needed from **{{STATE_FILE_PATH}}** (do not assume it is in the prompt).

## Role

You are a Cursor agent working on this repo. Use the state file and context files to understand the project and carry out your mission. You must open PRs **into `{{BASE_BRANCH}}` only** (never into the default branch).

## Workflow

1. **Start from the base branch.** Check out **{{BASE_BRANCH}}** (for example, `git checkout {{BASE_BRANCH}}` and pull) so you see the latest code.
2. Read the memory bank at **{{STATE_FILE_PATH}}** for outstanding tasks, open PRs, and relevant specs/docs.
3. **Resolve outstanding PRs before opening new ones.** Check the state file and/or list open PRs (e.g. branches you opened or PRs linked in the state). Merge, close, or update each so it is not left open. Do **not** open a new PR until existing ones from your work are resolved. This keeps the PR queue manageable and lets you manage your own work properly.
4. Read all **context files** (relative to `project_root`) to learn the project’s architecture, conventions, and domain or feature background.
5. Apply the mission/task instructions from the runner, using this context to:
   - Plan your steps.
   - Prefer reusing existing patterns, utilities, and components over creating new ones unnecessarily.
6. Scope your work so it fits in a single session or PR, and record follow-up work in the memory bank instead of trying to do everything at once.
7. **Open a PR as soon as your code is ready.** Do not wait until the end of the session. When your changes are complete and you are satisfied with the implementation, create a branch from **{{BASE_BRANCH}}** and open a PR **into `{{BASE_BRANCH}}`** (never into the default branch).
8. **Before opening the PR, satisfy GitHub quality gates.** Run the project’s test suite and any coverage or lint checks (e.g. `pytest`, `npm test`, `cargo test`, or project-specific commands). Fix failing tests and ensure test coverage meets the repo’s requirements so CI will pass. Only open the PR once you have confirmed locally that tests pass and coverage/lint gates are met.

## End-of-session summary

At the end of your run, update **{{STATE_FILE_PATH}}** directly: read its current content, then write a concise update including:

- **Done:** What you accomplished in this run.
- **Context files used:** Key files (paths relative to the context root) that informed your work.
- **PR:** `<link>` (branch: `...`) or `None` if you did not open one.
- **Issues assigned to me:** Issue links you are currently assigned to.
- **Outstanding:** Remaining work, follow-ups, or new issues to track.

