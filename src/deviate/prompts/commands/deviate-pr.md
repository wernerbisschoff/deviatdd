---
name: deviate-pr
description: Create a pull request from the current worktree branch and, upon successful merge, append a COMPLETED event to the issues ledger to unblock dependent issues
---

## [ROLE_DEFINITION]
This skill operates as the final gate in the Specify-Tasks-TDD meso workflow. It handles the pull request lifecycle: creates a PR from the current worktree branch, optionally waits for merge, and upon successful merge appends a COMPLETED event to `specs/issues.jsonl`.

## [GOVERNANCE]
${CONSTITUTION}

## [AGENT_RULES]
${CLAUDE_MD}

## [TASK]
- **ID**: ${TASK_ID}
- **Description**: ${TASK_DESCRIPTION}
- **Issue ID**: ${ISSUE_ID}

## [CONSTRAINTS]
- Ledger update only after PR is merged (not just opened)
- Requires `gh` for GitHub PR operations
- Idempotent: skip COMPLETED event if already present
- PR body serves dual purpose: description AND squash-merge commit body
- HITL confirmation required before PR creation/merge

## [OUTPUT]
JSON contract with issue_id, branch_name, pr_url, pr_number, merged status, ledger_updated, and next_action.
