---
name: deviate-merge
description: Squash-merge a feature branch into main with a conventional-commit message, then update the ledger with a full IssueRecord.
category: deviatdd-meso-layer
version: 2.1.0
aliases:
  - merge
  - /deviate-merge
  - tools:merge
---

<system_instructions>

This is the final gate in the DeviaTDD meso workflow. It performs a **squash merge** of a completed feature branch into `main`, generates a conventional-commit message synthesised from the branch's full commit history, and writes a **full IssueRecord** (not a bare transition) — with the ledger update folded into the same commit as the feature code.

Key invariant — single commit, end-to-end:
1. **Does the git merge**: squash-merge the feature branch into main
2. **Generates the commit message**: synthesised from branch history, following DeviaTDD conventional-commit format
3. **Stages the ledger entry**: calls ``deviate merge --stage-only`` to write a full Pydantic-validated IssueRecord
4. **Single commit**: ``git commit`` bundles both the feature changes and the ledger update

The ledger is never written by hand — it always goes through the CLI (``deviate merge --stage-only``), which uses ``append_issue_transition`` + ``resolve_issue_record`` to produce correct, Pydantic-validated records.
</system_instructions>

<execution_sequence>

<step id="branch_validation">

Validate preconditions:

1. **Detached HEAD check**: `git branch --show-current` — if empty, halt with `Failure_State: Detached_HEAD`
2. **Clean working tree**: `git status --porcelain` — if non-empty, halt with `Failure_State: Working_Tree_Not_Clean`

3. **Resolve the feature branch** (first-match wins):
   - From `<user_input>` if explicitly provided (branch name or fragment)
   - From the session's `active_issue_id` → branch pattern `feat/{bucket}/{slug}`
   - From the current branch (if not `main`)

4. **Resolve the issue ID** (first-match wins):
   - From `--issue` argument in `<user_input>` (e.g. `--issue ISS-003`)
   - From the session's `active_issue_id` (read via `deviate session` or `.deviate/session.json`)

5. **Branch resolution check**: If the resolved feature branch is empty or still points to `main`, halt with `Failure_State: No_Feature_Branch_Specified`

</step>

<step id="context_gathering">

Capture the full change context from the feature branch:

```bash
git log main..{FEATURE_BRANCH} --oneline --no-decorate
git log main..{FEATURE_BRANCH} --format="%H|%s|%an" --no-decorate
git diff main...{FEATURE_BRANCH} --stat
git diff main...{FEATURE_BRANCH} --diff-filter=AM --name-only
```

Analyse:
- Number of commits and their subjects
- Files changed by category (src, tests, docs, config)
- Total change magnitude (insertions/deletions)

If the ledger entry exists, also read the issue record's `title` and `type` to inform commit message generation:
```bash
jq -R 'fromjson?' specs/issues.jsonl 2>/dev/null \
  | jq -s '[group_by(.issue_id) | map(last)[]] | .[] | select(.issue_id == "{ISSUE_ID}") | {title, type, source_file, flow_refs}'
```

</step>

<step id="commit_message_generation">

Generate a conventional-commit title and multi-paragraph description synthesised from the branch history.

**Step A — Title format** (consistent with `deviate pr`):

```
{type}({ISSUE_ID}): {description}
```

The ``deviate merge --message`` CLI applies the project's commit convention (emoji prefix if configured, no-op otherwise), so do NOT pre-pend an emoji here.

- **type**: `feature → feat`, `bug → fix`, `chore → chore`, `refactor → refactor`, `docs → docs`, default → `feat`
- **description**: the ledger issue title with any bracketed prefix (e.g. `[FR-NNN]`) stripped. If no ledger title is available, synthesise from commit history.
- Max 72 characters, imperative mood, no period.
- Example: `feat(ISS-001): add user authentication`

**Step B — Description body** (2-4 paragraphs):

```
{Summary — 2-4 sentences, problem-led}

## Changes
- {grouped by logical concern with file refs inline}
- {NEVER list every file individually — group by directory or concern}

## Technical Details
{optional — architectural decisions, non-obvious choices, migrations}

Closes {ISSUE_ID}
```

</step>

<step id="confirmation">

Present the full merge plan to the user:

```
Feature branch: {FEATURE_BRANCH}
Base:           main
Commits:        {N} commits
Files changed:  {N} files, {N}+ / {N}-

Commit:
  {commit_type}({ISSUE_ID}): {description}

Proceed with squash merge?
```

Use the `ask` tool with options: **Confirm** | **Edit commit message** | **Cancel**.

If the user chooses **Edit commit message**, collect the revised message and re-present confirmation.

</step>

<step id="execution">

1. **Switch to main**:
   ```bash
   git checkout main
   git pull --ff-only
   ```

2. **Squash merge the feature branch** — stages feature changes to the index:
   ```bash
   git merge --squash {FEATURE_BRANCH}
   ```

3. **Stage the ledger update** — writes a full IssueRecord to ``specs/issues.jsonl``
   and ``git add``-s it, but does NOT commit.  The ledger change will be folded
   into the squash-merge commit below.

   ```bash
   deviate merge --issue {ISSUE_ID} --stage-only
   ```

4. **Verify staging captured everything** — `git merge --squash` plus
   `deviate merge --stage-only` should leave the index non-empty and the
   working tree clean (everything in the index is staged, nothing
   unstaged or untracked). Run:
   ```bash
   git status --porcelain
   ```
   If the porcelain output is non-empty **or** the staged tree is empty
   (`git diff --cached --quiet` exits 1 with no diff), halt with
   `Failure_State: Unstaged_Files_Post_Merge` before the final commit
   runs. The diagnostic is **dual-channel** so the operator sees it
   regardless of how the framework renders failure states:

   1. **stderr** — `git status --porcelain` output is printed to stderr verbatim
      (line-for-line, no truncation, no reformatting) before halting.
   2. **`Failure_State` message body** — the same porcelain dump is embedded
      inside the Failure_State string itself, prefixed with a one-line cause
      (e.g. `Failure_State: Unstaged_Files_Post_Merge — porcelain non-empty
      after squash + ledger staging: <full porcelain output here>`). This
      guarantees the dump reaches the operator even if the framework only
      renders the label.

   Do NOT silently `git add` stray files and do NOT `--amend` anything —
   the operator decides whether to investigate, drop, or commit strays.
5. **Commit everything together** — a single commit containing both the feature
   changes and the ledger update. The ``deviate merge --message`` CLI applies
   the project's commit convention (emoji prefix if configured, no-op otherwise):

   ```bash
   deviate merge --issue {ISSUE_ID} \
     -m "{commit_type}({ISSUE_ID}): {description}" \
     -m "{summary paragraph}" \
     -m "## Changes
   - {change 1}
   - {change 2}" \
     -m "Closes {ISSUE_ID}"
   ```

6. **Push to remote**:
   ```bash
   git push
   ```

</step>

<step id="cleanup">

The ledger is already up-to-date from step 3 — the issue is now COMPLETED.
Run ``deviate merge`` again with cleanup flags; it will see ``ALREADY_COMPLETED``,
skip the write, and only handle branch/worktree deletion + session reset:

```bash
deviate merge --issue {ISSUE_ID} --delete-branch [--delete-worktree]
```

This resets the session to IDLE and cleans up the local feature branch.

</step>
</execution_sequence>

<edge_cases>

| State | Action |
|-------|--------|
| Detached HEAD | Fail with `Failure_State: Detached_HEAD` |
| Dirty working tree | Fail with `Failure_State: Working_Tree_Not_Clean` |
| On main, no branch specified | Fail with `Failure_State: No_Feature_Branch_Specified` |
| No commits to merge (`git merge --squash` outputs "Already up to date") | Checkout main + pull, then run `deviate merge --issue {ISSUE_ID} --delete-branch` — it will write the COMPLETED record, commit it, and clean up |
| Unstaged files after squash + ledger staging (post-step 3 porcelain non-empty, or staged tree empty) | Fail with `Failure_State: Unstaged_Files_Post_Merge`. Dual-channel diagnostic: print `git status --porcelain` to stderr verbatim AND embed the same dump in the `Failure_State` message body (`Failure_State: Unstaged_Files_Post_Merge — porcelain non-empty after squash + ledger staging: <porcelain dump>`) so the operator sees it regardless of how the framework renders failures. Do NOT silently `git add` or `--amend` — operator decides whether to investigate, drop, or commit strays |
| Merge conflict during `git merge --squash` | Surface the conflict to the user, halt — do NOT force-resolve or skip. |
| Issue not found in ledger | Proceed with merge anyway (the branch may have been created outside DeviaTDD). Pass `deviate merge --issue {ISSUE_ID}` — it will fail cleanly with `ISSUE_NOT_FOUND` |
| Issue already COMPLETED | The ledger step is idempotent — `deviate merge` exits cleanly with `ALREADY_COMPLETED` |
| `git push` fails (diverged / rejected) | Halt, surface the reason. Do NOT update ledger until push succeeds |
| No remote configured | Skip push with a warning, proceed with ledger update |

</edge_cases>

<output_contract>

On success, output a structured handoff:

```
phase: "MERGE"
status: "SUCCESS"
issue_id: "{ISSUE_ID}"
branch: "{FEATURE_BRANCH}"
commit: "{commit_hash}"
ledger_updated: true
next_action: "Run /deviate-tasks for the next unblocked issue"
```

On failure, output the specific `Failure_State` with context for the user.

</output_contract>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
