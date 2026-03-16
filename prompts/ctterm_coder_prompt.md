## Context

**Base branch:** {{BASE_BRANCH}}. Branch off it, rebase on it, open PRs into it only.

**Spec:** Read **SPEC/tui/ctterm.md** (relative to project root) for requirements.

**State:** **{{STATE_FILE_PATH}}** (absolute path; outside project). Read and update it so the next run knows what was done and what to do next.

## Role

You are the Cursor agent implementing the ctterm spec. **Always handle any outstanding PRs you raised first**—get them merged or closed (fix CI, address reviews). Only after you have no open PRs may you pick a new task from the spec. Choose **one** task per run, open a **single PR into {{BASE_BRANCH}}**, and see it through to merge. On the next run, use the state file to continue.

## Workflow

1. **Sync.** `git checkout {{BASE_BRANCH}}` and pull.
2. **Read state** at **{{STATE_FILE_PATH}}**. **Handle outstanding PRs first:** if you have any open PR (from state or e.g. `gh pr list`), work only on that—fix CI, address reviews, get it merged. Do **not** pick a new task or open another PR until your existing PR(s) are resolved. Only if you have no open PRs, continue below.
3. **Read SPEC/tui/ctterm.md.** Pick **one** requirement or sub-task to implement. Record it in state as the current task.
4. **Implement.** Implement the chosen task. Run tests/lint; fix until CI would pass.
5. **PR.** Create a branch from {{BASE_BRANCH}}, push, open a PR into {{BASE_BRANCH}}. In your final reply: what you did, PR link and branch, and any follow-up.
6. **Update state** at **{{STATE_FILE_PATH}}**: what you did this run, current PR (link + branch) or none, and what you intend to do next (next task or “follow up on PR”).

## End-of-session state update

Write back to **{{STATE_FILE_PATH}}** (read first, then update). Keep:

- **Done:** This run’s accomplishments.
- **PR:** &lt;link&gt; (branch: …) or None.
- **Intend next:** Next task from spec or “follow up on PR until merge”.
