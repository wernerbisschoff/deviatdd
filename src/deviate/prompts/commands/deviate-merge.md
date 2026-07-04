---
name: deviate-merge
description: Mark an issue COMPLETED in the ledger after an external merge (e.g. squash-merge). Writes a full IssueRecord, not a bare transition.
category: deviatdd-meso-layer
version: 1.0.0
aliases:
  - merge
  - /deviate-merge
  - tools:merge
---

<system_instructions>

This skill marks an issue COMPLETED in the DeviaTDD ledger after a merge has
already happened externally (e.g. via the /squash-merge skill or manual GitHub
merge). It writes a **full IssueRecord** to `specs/issues.jsonl` — unlike bare
`{issue_id, status, timestamp}` transitions, this record always passes Pydantic
validation and is correctly resolved by `resolve_issue_record`.

USE THIS INSTEAD OF writing bare COMPLETED entries to the ledger.

CRITICAL INVARIANTS:
1. **Full Record**: The COMPLETED transition preserves `type`, `title`,
   `source_file`, `blocked_by`, `coordinates_with`, and `flow_refs` from the
   existing record. Only `status` and `timestamp` are updated.
2. **Idempotent**: If the issue is already COMPLETED, the command exits cleanly
   without writing a duplicate.
3. **Worktree Context**: Run from the main repo or a linked worktree. The
   command resolves the ledger from `specs/issues.jsonl` relative to cwd.
4. **No merge logic**: This command does NOT merge branches or PRs. It only
   updates the ledger. Merge first, then run this.

</system_instructions>


<execution_sequence>

1. Verify the merge has happened. Check that the PR for the current branch is
   merged (via `gh pr view --json state` or equivalent). If not merged, warn
   the user and stop.

2. Run the merge command from the **main repo** (not the worktree):
   ```
   deviate merge [--issue ISS-XXX] [--delete-branch] [--delete-worktree]
   ```
   - `--issue`: Override the issue ID (defaults to session's `active_issue_id`)
   - `--delete-branch`: Delete the local feature branch after completion
   - `--delete-worktree`: Remove the worktree directory after completion

3. The command will:
   - Read the full IssueRecord from the ledger
   - Write a COMPLETED transition with all fields preserved
   - Commit the ledger change
   - Optionally clean up branch/worktree
   - Reset the session to IDLE

</execution_sequence>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
