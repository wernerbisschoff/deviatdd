---
name: deviate-pr
description: Mark the issue COMPLETED, push the branch, and optionally open a GitHub PR or GitLab MR from the current worktree branch.
category: deviatdd-meso-layer
version: 2.0.0
aliases:
  - pr
  - /deviate-pr
  - tools:pr
---

<system_instructions>

This skill is the final gate in the DeviaTDD meso workflow. It opens a pull request (GitHub) or merge request (GitLab) from the feature branch, or pushes the branch without opening one if the operator so chooses.

Key invariants:

1. **Mark done first**: The ledger is updated to COMPLETED *before* the branch is pushed and before any PR/MR is opened. The `deviate pr run` CLI owns this ordering: it appends the COMPLETED event, commits the ledger, then pushes. The issue is never left BACKLOG once the branch is pushed.
2. **Optional PR/MR creation**: Opening a PR (GitHub) or MR (GitLab) is opt-in. The CLI never opens one unless the operator asks for it (`--merge`, `--auto-merge`, or a plain create). With `--no-pr`, the CLI marks the issue COMPLETED and pushes the branch but opens nothing.
3. **Platform detection**: The CLI detects GitHub vs GitLab from the `origin` remote hostname. GitHub uses `gh pr create`; GitLab uses `git push -o merge_request.create` push options (no extra CLI dependency). An explicit `--platform github|gitlab` overrides detection. There is no Graphite path.
4. **Ledger discipline**: The ledger is never written by hand — always through the CLI (`append_issue_transition`), which produces Pydantic-validated records. The append is idempotent: re-running on an already-COMPLETED issue prints `LEDGER_IDEMPOTENT`.
5. **Worktree context**: The script runs from inside the worktree on the feature branch. `resolve_issue_id_from_branch` recovers the issue ID when the session has no `active_issue_id`; `_resolve_specs_root` locates the ledger.

</system_instructions>

<execution_sequence>

<step id="precheck">Validate preconditions:
1. **Run the pre-script** to emit a JSON contract:
   ```
   deviate pr pre
   ```
   The contract on stdout contains: `status` (`READY`|`FAILURE`), `phase`, `issue_id`, `branch_name`, `base_branch`, `pr_title`, `issue_title`, `commit_titles` (pipe-separated), `changed_files` (comma-separated), `diff_summary`, `git_state`, `timestamp`.
2. **Active issue**: `issue_id` must resolve. If `NO_ACTIVE_ISSUE` or `ISSUE_NOT_FOUND`, halt and report; the issue must exist in `specs/issues.jsonl` before a PR can be opened.
3. **Worktree cleanliness**: `git status --porcelain` — the operative work must be committed on the branch before PR creation. If non-empty, halt with `Failure_State: Working_Tree_Not_Clean`.
</step>

<step id="body_generation">Generate the PR body using the pre-phase data. Read `spec.md` (or the spec-enriched issue file `specs/<EPIC>/<ISSUE>/`) and `tasks.md` when they exist for richer context. Follow `<pr_body_format>` below. The body must serve dual purpose: a good PR description AND a good squash-merge commit body.
</step>

<step id="confirmation">Present a confirmation to the stakeholder with the `ask` tool:
- **Open PR (GitHub)** — `deviate pr run --body-file <path>`
- **Open MR (GitLab)** — same command; the CLI detects GitLab and uses push options
- **Push only, no PR/MR** — `deviate pr run --no-pr`
- **Cancel**

Force a platform explicitly with `--platform github|gitlab` when the remote hostname is ambiguous. If the operator requests to merge after creation, add `--merge` (GitHub) or `--auto-merge` (GitHub). Merge flags have no effect on GitLab push options; the CLI warns and opens the MR for review instead.
</step>

<step id="execution">Run the main script:
```
deviate pr run --body-file <path> [--merge] [--auto-merge] [--no-pr] [--platform github|gitlab]
```
Flags:
- `--body-file <path>`: the generated PR body. Required when creating a PR/MR; optional for `--no-pr`.
- `--merge`: merge the PR after creation (GitHub only).
- `--auto-merge`: enable auto-merge so the PR merges when checks pass (GitHub only).
- `--no-pr`: mark issue COMPLETED and push the branch without opening a PR/MR.
- `--platform github|gitlab`: force the platform (default: detect from the `origin` remote).

The CLI performs these steps, in order:
1. Append the COMPLETED transition to the ledger (idempotent).
2. Stage the ledger and (when present) the body file, and commit them together on the branch.
3. Push the branch to `origin`. For GitLab, the push carries `merge_request.create`, `merge_request.target`, `merge_request.title`, and (when a body exists) `merge_request.description` push options, so the push itself opens the MR.
4. Open the PR via `gh pr create` (GitHub) unless `--no-pr`, or report `PR_SKIPPED` / `MR_CREATED` / `BRANCH_PUSHED` accordingly.
5. Emit a final status handoff.
</step>

</execution_sequence>

<output_format_schemas>
<format_contract>
The CLI emits JSON on stdout:
Pre-phase contract:
{
  "status": "READY|FAILURE",
  "phase": "pr_pre",
  "issue_id": "002-001",
  "branch_name": "feat/...",
  "base_branch": "main",
  "pr_title": "feat(002-001): ...",
  "git_state": "...",
  "issue_title": "Issue title from ledger",
  "commit_titles": "feat: add X|fix: resolve Y",
  "changed_files": "src/a.py,src/b.py",
  "diff_summary": "5 files changed, 100 insertions(+)...",
  "timestamp": "2026-06-06T12:00:00Z"
}

Run-phase (on success): the CLI prints banner markers — `COMPLETED`, `LEDGER_COMMITTED`, `BRANCH_PUSHED`, then one of `PR_CREATED <url>` (GitHub), `MR_CREATED` (GitLab), or `PR_SKIPPED` (`--no-pr`). The session resets to TASKS.
</format_contract>
</output_format_schemas>

<pr_title_format>
PR title is generated by the deviate CLI as a conventional commit:
`{type}({commit_scope}): {description}`
- **type**: mapped from the issue record's `type` field: `feature → feat`, `bug → fix`, `chore → chore`, `refactor → refactor`, `docs → docs`, default → `feat`.
- **commit_scope**: the canonical issue ID. Use `002-001` for numbered work or `ADH-001` for ad-hoc work. Never use the legacy `ISS-` prefix.
- **description**: the raw issue title with any bracketed prefix (e.g. `[FR-NNN]`) stripped.
</pr_title_format>

<pr_body_format>
The PR body MUST serve dual purpose: a good PR description AND a good squash-merge commit body.

```markdown
{SUMMARY}

{CHANGES}

{CLOSES}
```

- Summary: 2-4 sentences, problem-led: what problem does this solve and why.
- Changes: grouped by logical concern with file refs inline. NEVER list every file individually — group by directory or concern.
- Closes: `Closes #N` footer for GitHub when the issue number is known; `Closes {ISSUE_ID}` for GitLab. Omit entirely if no issue.
- Omit empty sections. No decorative headers or horizontal rules.
</pr_body_format>

<edge_cases>
| State | Action |
|-------|--------|
| No active issue / issue not found | Halt with `NO_ACTIVE_ISSUE` / `ISSUE_NOT_FOUND`. The issue must exist in the ledger. |
| Detached HEAD | Halt with `Failure_State: Detached_HEAD`. A PR needs a named branch. |
| Body file missing (PR/MR create) | Halt with `MISSING_BODY_FILE` (requires `--body-file`) or `BODY_FILE_NOT_FOUND`. |
| `--no-pr` with no body file | Allowed — marks COMPLETED and pushes without opening a PR/MR. |
| Issue already COMPLETED | Ledger append is idempotent; prints `LEDGER_IDEMPOTENT` and proceeds. |
| GitLab + `--merge` / `--auto-merge` | Warning `GITLAB_MERGE_FLAGS_IGNORED`; the MR is opened for review, not merged. |
| Unknown remote host | Defaults to GitHub (`gh`). |
| `gh` / git not installed or auth fails | `PR_CREATE_FAILED` with stderr; the operator resolves and retries. |
| Push fails (diverged / rejected) | `PUSH_WARN` (or the branch is already gone → `BRANCH_DELETED`). Ledger is already COMPLETED and committed; only the remote push is blocked. |
</edge_cases>

<output_contract>
On success, output a structured handoff:
```
phase: "PR"
status: "SUCCESS"
issue_id: "{ISSUE_ID}"
branch: "{BRANCH}"
platform: "github" | "gitlab"
pr_opened: true | false
ledger_updated: true
next_action: "Run /deviate-tasks for the next unblocked issue"
```
On failure, output the specific `Failure_State` with context.
</output_contract>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>