---
name: deviate-merge
description: Squash-merge a feature branch into main with a conventional-commit message, then update the ledger with a full IssueRecord.
category: deviatdd-meso-layer
version: 2.0.0
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

**Step A — Detect emoji convention**. Read `CONTRIBUTING.md` and `.commit-convention.md` for emoji references; if neither exists, sample the last 10 commit subjects for Unicode emoji characters. If any emoji is found, the project uses emoji-prefixed commits.

Default type→emoji mapping (gitmoji standard):
```
feat → ✨     fix → 🐛     docs → 📚     style → 🎨
refactor → ♻️  perf → 🚀    test → ✅     build → 📦
ci → 👷       chore → 🔧    revert → ⏪
```

**Step B — Title format** (consistent with `deviate pr`):

```
{emoji} {type}({ISSUE_ID}): {description}
```

Omit the emoji when the repo does not use emoji-prefixed commits.

- **type**: `feature → feat`, `bug → fix`, `chore → chore`, `refactor → refactor`, `docs → docs`, default → `feat`
- **emoji**: look up in the type→emoji mapping above (only when repo uses emojis)
- **description**: the ledger issue title with any bracketed prefix (e.g. `[FR-NNN]`) stripped. If no ledger title is available, synthesise from commit history.
- Max 72 characters, imperative mood, no period.
- Final examples (emoji-using repo): `✨ feat(ISS-001): add user authentication` / `🐛 fix(ISS-002): handle null pointer`
- Final examples (no emoji): `feat(ISS-001): add user authentication` / `fix(ISS-002): handle null pointer`

**Step C — Description body** (2-4 paragraphs):

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
  {emoji}{commit_type}({ISSUE_ID}): {description}

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

4. **Commit everything together** — a single commit containing both the feature
   changes and the ledger update:

   ```bash
   git commit -m "$(cat <<'EOF'
   {emoji}{commit_type}({ISSUE_ID}): {description}

   {summary paragraph}

   ## Changes
   - {change 1}
   - {change 2}

   Closes {ISSUE_ID}
   EOF
   )"
   ```

5. **Push to remote**:
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
