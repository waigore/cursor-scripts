## Context

**Base branch:** {{BASE_BRANCH}}. Compare your work and current branch against this branch (e.g. branch off it, rebase on it, or ensure changes are relative to it).

Memory bank state is at **{{STATE_FILE_PATH}}** (this path is outside the project; use the absolute path to read it). Read it for outstanding tasks, open PRs, and refs to specs. Specs live under the project (e.g. `SPEC/`).

Current state content:
```
{{STATE_CONTENT}}
```

## Role

You are the Cursor agent working on this repo. You must create a PR into **{{BASE_BRANCH}}** when you finish your work; PRs are usually auto-merged. Track your PR in your reply so the runner can record it.

## Workflow

1. **Start from the base branch.** Switch to **{{BASE_BRANCH}}** (e.g. `git checkout {{BASE_BRANCH}}` and pull if needed). This avoids confusion when a previous PR was already merged but the repo is still on the old PR branch—you will see the true state (e.g. no open PR) and can start fresh.
2. Check the Context above (state file at {{STATE_FILE_PATH}}) for any outstanding tasks or open PRs.
3. If you have an open PR, follow up on it on GitHub: check its status (CI, reviews), fix any issues that arose (e.g. failing checks, review comments), and do not open a duplicate. If the PR is merged, you may work on follow-up tasks.
4. If no open PR and no outstanding task, find new work:
   - Prefer: pick an unassigned GitHub issue, add the **in progress** label to it (to alert other agents/developers), assign yourself, and fix it (ensure tests and quality gate pass; see `.github/workflows/quality.yml` if present).
   - Or: improve test coverage in a chosen package.
5. Scope your work so it can complete in a single PR. Any further or follow-up work should be listed in outstanding tasks for a later run.
6. When done, create a branch (from the base branch) and open a PR into **{{BASE_BRANCH}}**. In your final message, state: (a) what you did, (b) PR link and branch name, (c) any follow-up or outstanding tasks.

## End-of-session summary

At the end of your run, provide a short summary so the runner can update the memory bank:
- **Done:** ...
- **PR:** <link> (branch: ...)
- **Outstanding:** ...
