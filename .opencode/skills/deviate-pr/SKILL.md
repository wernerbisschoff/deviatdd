---
name: deviate-pr
description: Create a pull request from the current worktree branch and, upon successful merge, append a COMPLETED event to the issues ledger to unblock dependent issues
category: deviatdd-meso-layer
version: 1.0.0
aliases:
  - pr
  - /deviate-pr
  - tools:pr
---

## Universal Invariants

The following rules apply across ALL phases — macro layer (explore, research, prd, shard), meso layer (plan, tasks), and micro layer (red, green, refactor, yellow, judge), whether implemented via DeviaTDD or another TDD workflow:

1. **Automated Execution**: Execute all steps autonomously with zero user interaction. Do not ask questions, request confirmation, or prompt for decisions. This phase must be one-shot and deterministic. If any step requires a choice, silently apply the default or first enumerated option.

2. **Relative Path Normalization**: All paths written into output artifacts must be strictly relative to `repo_root`. Absolute machine-specific paths are forbidden.

3. **Verbatim Source Anchoring**: Every structural claim, architectural decision, or assertion must reference a verbatim source (≤10 line snippet anchored to a file path or contract field). Rows without source anchors are subject to post-script rejection.

4. **Output Format Discipline**: Present the final response exclusively in the format specified by the output schema for the current phase — human-readable Markdown for macro/meso documents and spec artifacts; valid YAML code blocks (all string values double-quoted) for micro-phase handover manifests. Do not include conversational preambles, XML wrapper tags, or explanatory content outside the specified output format.

5. **Pointer Convention**: Any natural language instruction or validation step referencing a structural tag, schema block name, or phase identifier must wrap that target in explicit markdown backticks (e.g., `tasks.md`, `spec.md`, `/research`).

6. **Positive Invariant Rule**: All procedural operational requirements are established as mandatory, active states. Do not formulate instructions via negations.

7. **Offline Documentation Mandate**: All agents MUST use `libref query <library> <topic>` as the primary documentation lookup mechanism. Run `libref list` first to discover available documentation packages. When documentation for a library is missing, use `libref add <source>` to register it. This replaces web fetching as the default — web fetch is a last-resort fallback only when `libref` is unavailable.

## KV Cache Preservation

Static role definitions, behavioral constraints, and formatting parameters sit at the head of this prompt. Volatile runtime attributes (task IDs, file paths, timestamps) are appended via the `<user_input>` container or injected as `${PLACEHOLDER}` values after this framework block. This separation secures optimal KV cache reuse across invocations.


<system_instructions>

This skill operates as the final gate in the Specify-Tasks-TDD meso workflow. It handles the pull request lifecycle:
1. Creates a PR from the current worktree branch
2. Optionally merges directly (if `--merge` is specified)
3. On successful PR creation, appends a COMPLETED event to `specs/issues.jsonl` — regardless of whether the PR was merged
4. This natively unblocks dependent issues via the existing `blocked_by` logic in the ledger

CRITICAL INVARIANTS:
1. **Ledger Update Rule**: Append COMPLETED event after PR is successfully created (not only after merge). The event format: `{"issue_id":"ISS-XXX","status":"COMPLETED","timestamp":"..."}`
2. **Worktree Context**: The script runs from within the worktree. Use `find_repo_root` to locate the main repo and ledger.
3. **Idempotency**: If the issue already has a COMPLETED event, do not append a duplicate.
4. **GitHub CLI Required**: Requires `gh` for PR operations. If unavailable, surface clear error.

</system_instructions>


<execution_sequence>
1. Run the pre-script to validate the worktree state, discover the issue ID, and emit a JSON contract:
   ```
   deviate pr pre
   ```
   The contract on stdout contains: `issue_id`, `branch_name`, `worktree_path`, `repo_root`, `pr_url` (if PR exists), `ledger_path`, `can_merge` (boolean), plus body generation data: `commit_titles` (pipe-separated), `changed_files` (comma-separated), `diff_summary`, `issue_title`, `base_branch`.

2. **Generate PR Body**. Using the pre-phase data, write a PR body following `<pr_body_format>`.
   - Read `spec.md` and `tasks.md` from the spec directory (if they exist) for richer context
   - The body MUST serve dual purpose: good PR description AND good squash-merge commit body
   - The script will write the body to `pr_descriptions/<branch>.md`, commit, and push it

3. **HITL: Confirm PR creation/merge**. Present the PR details AND generated body to the stakeholder:
    - If no PR exists: "Create PR for issue {issue_id} on branch {branch_name}?" — show the generated body
    - If PR exists: "PR #{number} exists. Merge and mark issue COMPLETED?"
    Use the AskUser tool to present options.

4. Run the main script to create/merge PR and update ledger:
    ```
    deviate pr run --body-file <path> [--merge] [--auto-merge]
    ```
    Options:
    - `--body-file <path>`: Path to the PR body file generated in step 2 (required when creating a new PR)
    - `--merge`: Merge the PR after creation (requires merge permissions)
    - `--auto-merge`: Enable auto-merge on GitHub (PR merges when checks pass)
    - Without merge flags: Only create the PR, do not merge

5. The script will:
    - Create PR using the provided body file (or auto-generate if --body-file omitted)
    - Merge PR if `--merge` or `--auto-merge` specified
    - On successful merge, append COMPLETED event to ledger
    - Emit final status JSON

</execution_sequence>

<output_format_schemas>
<format_contract>
The script emits JSON on stdout with the following structure:

Pre-phase contract:
{
  "status": "READY|FAILURE",
  "phase": "pr",
  "issue_id": "ISS-XXX",
  "branch_name": "feat/...",
  "worktree_path": "/absolute/path/to/worktree",
  "repo_root": "/absolute/path/to/repo",
  "pr_url": "https://github.com/.../pull/123",
  "pr_number": 123,
  "ledger_path": "/absolute/path/to/specs/issues.jsonl",
  "can_merge": true,
  "commit_titles": "feat: add X|fix: resolve Y",
  "changed_files": "src/a.ts,src/b.ts,docs/c.md",
  "diff_summary": "5 files changed, 100 insertions(+), 50 deletions(-)",
  "issue_title": "Issue title from ledger",
  "base_branch": "main",
  "timestamp": "2026-06-06T12:00:00Z"
}

Run-phase contract (on success):
{
  "status": "SUCCESS",
  "phase": "pr",
  "issue_id": "ISS-XXX",
  "pr_number": 123,
  "pr_url": "https://github.com/.../pull/123",
  "merged": true,
  "ledger_updated": true,
  "next_action": "Run /deviate-tasks for next unblocked issue",
  "timestamp": "2026-06-06T12:00:00Z"
}
</format_contract>
</output_format_schemas>

<pr_title_format>
PR title is generated by the deviate CLI as a conventional commit:

`{type}({issue_id}): {description}`

- **type**: mapped from the issue record's `type` field: `feature → feat`, `bug → fix`, `chore → chore`, `refactor → refactor`, `docs → docs`, default → `feat`
- **issue_id**: e.g. `ISS-001-005`
- **description**: the raw issue title with any bracketed prefix (e.g. `[FR-NNN]`) stripped

Examples:
- `feat(ISS-001-005): CLI Architecture Realignment & Skill Integration`
- `chore(ISS-002-002): close ISS-002-002 and remove deviate-context skill`
- `fix(ISS-003-001): handle null pointer in user lookup`

This format ensures the squash-merge commit reads cleanly as a conventional commit subject.
</pr_title_format>

<pr_body_format>
The PR body MUST serve dual purpose: a good PR description AND a good squash-merge commit body.
Use the same structure as tools-pr:

```markdown
{SUMMARY}

{CHANGES}

{CLOSES}
```

Summary: 2-4 sentences. Problem-led: what problem does this solve and why.
Synthesize from commit titles, issue context, and spec — do NOT just concatenate commit messages.
Changes: grouped by logical concern with file refs inline (e.g., "Migration: removed all `.tex` files and `awesome-cv.cls`").
NEVER list every file individually — group by directory or concern.
Closes: `Closes #N` footer when issue number is known. Omit entirely if no issue.
Omit empty sections. No decorative headers or horizontal rules.
</pr_body_format>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>