---
name: deviate-merge
description: Squash-merge a feature branch into main with a conventional-commit message, then update the ledger with a full IssueRecord.
category: deviatdd-meso-layer
version: 2.3.0
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

**Step 0 — Honour the repository's commit convention** (mandatory before drafting the title):

1. **Read the project convention file first** so the commit matches what the project actually uses:
   ```bash
   test -f CONTRIBUTING.md && head -120 CONTRIBUTING.md
   test -f .commit-convention.md && cat .commit-convention.md
   ```
2. **Confirm the convention in your head**:
   - **Emoji prefix?** Look for any gitmoji-style character (e.g. `✨ feat:`, `🐛 fix:`) in either file. If found, the project expects an emoji prefix on every commit; the ``deviate merge --message`` CLI will apply it automatically (see Step A). If neither file exists or neither contains emoji, default to no prefix — but state that conclusion explicitly in the confirmation step so the operator can override.
   - **Types** allowed: `feat`, `fix`, `test`, `refactor`, `docs`, `chore` (the DeviaTDD constitution set; honour it unless CONTRIBUTING.md overrides).
   - **Scope** is the issue ID (e.g. `ISS-001`) unless CONTRIBUTING.md says otherwise.
3. **Do NOT bypass the CLI** by calling `git commit` directly with your own subject — that drops the emoji prefix on emoji-convention repos. Always go through ``deviate merge --message`` (Step 5 below) so the CLI's ``format_commit_message`` helper applies the prefix from CONTRIBUTING.md.

**Step A — Title format** (consistent with `deviate pr`):

```
{type}({ISSUE_ID}): {description}
```

The ``deviate merge --message`` CLI applies the project's emoji convention (read from CONTRIBUTING.md / .commit-convention.md / git history by ``format_commit_message``), so do NOT pre-pend an emoji here — the CLI will. If neither CONTRIBUTING.md nor `.commit-convention.md` declares an emoji convention and git history has no emoji either, the CLI leaves the subject unchanged.

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
   `deviate merge --stage-only` should leave the **index** non-empty and the
   **working tree** clean (no unstaged changes, no untracked files).
   ``git status --porcelain`` shows staged changes too, so a successful
   squash-merge naturally produces non-empty porcelain output — that is NOT a
   failure.  Use the three-command check below to distinguish staged-only
   from genuinely-unstaged strays:

   ```bash
   # Staged tree must contain something (the squash + ledger)
   if git diff --cached --quiet; then
     halt "Failure_State: Nothing_To_Stage"
   fi
   # Working tree must have NO unstaged changes
   if ! git diff --quiet; then
     halt "Failure_State: Unstaged_Files_Post_Merge"   # embed `git status --porcelain` body
   fi
   # No untracked files should remain either
   if [ -n "$(git ls-files --others --exclude-standard)" ]; then
     halt "Failure_State: Untracked_Files_Post_Merge"  # embed `git status --porcelain` body
   fi
   ```

   The diagnostic is **dual-channel** so the operator sees it regardless of
   how the framework renders failure states:

   1. **stderr** — ``git status --porcelain`` output is printed to stderr
      verbatim (line-for-line, no truncation, no reformatting) before halting.
   2. **`Failure_State` message body** — the same porcelain dump is embedded
      inside the ``Failure_State`` string itself, prefixed with a one-line
      cause. This guarantees the dump reaches the operator even if the
      framework only renders the label.
   Do NOT silently ``git add`` stray files and do NOT ``--amend`` anything —
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
Run ``deviate merge`` again with cleanup flags.  The CLI is idempotent on the
ledger transition (it prints ``LEDGER_IDEMPOTENT`` if the COMPLETED line is
already present) and owns the full branch / worktree / remote lifecycle when
``--delete-branch`` is passed.

```bash
deviate merge --issue {ISSUE_ID} --delete-branch [--delete-worktree]
```

``--delete-branch`` triggers the full post-merge lifecycle in this order:

1. **Archive tag** — creates ``archive/{ISSUE_ID}/{YYYY-MM-DD}`` pointing at
   the branch tip (UTC date). The pre-squash commit history is preserved on
   the tag because ``git merge --squash`` collapses every feature commit into
   one main commit; the tag is the only way back to the per-commit graph.
   Prints ``ARCHIVE_TAG`` on success, ``ARCHIVE_TAG_SKIP`` if the branch is
   already gone.
2. **Tag push (best-effort)** — ``git push origin <tag>``. Skipped silently
   when ``origin`` is not configured; surfaces ``PUSH_WARN`` and continues
   when the remote is unreachable.
3. **Worktree cleanup** — if the branch is still checked out in a worktree
   (e.g. the pre-squash worktree at ``.worktrees/feat-*``), the worktree is
   ``git worktree remove --force``-ed first so ``git branch -D`` does not
   fail with ``branch … used by worktree``. ``--delete-worktree`` adds an
   independent removal of the worktree at ``cwd`` (useful when ``cwd`` is a
   linked worktree for the issue itself).
4. **Remote branch delete (best-effort)** — ``git push origin --delete
   <branch>``. Skipped silently when ``origin`` is not configured; surfaces
   ``PUSH_WARN`` and continues when the remote is unreachable. Prints
   ``REMOTE_BRANCH_DELETED`` on success and ``REMOTE_BRANCH_SKIP`` if origin
   reports the branch is already gone (the expected post-merge state).
5. **Local branch delete** — ``git branch -D <branch>``. ``--delete-branch``
   implicitly handles this; pairing with ``--delete-worktree`` runs the
   worktree cleanup first.

Tag push and remote branch delete are **best-effort by design** — the user
asked for ``--delete-branch`` to also remove the worktree and the branch
locally and on origin, so the local cleanup completes even when the remote
is briefly unreachable. Surface ``PUSH_WARN`` from each step so the operator
can retry manually.

Session is reset to IDLE once cleanup completes (whether or not the remote
operations succeeded).

</step>

</execution_sequence>

<edge_cases>

| State | Action |
|-------|--------|
| Detached HEAD | Fail with `Failure_State: Detached_HEAD` |
| Dirty working tree | Fail with `Failure_State: Working_Tree_Not_Clean` |
| On main, no branch specified | Fail with `Failure_State: No_Feature_Branch_Specified` |
| Unstaged files after squash + ledger staging (`git diff --quiet` reports changes; staged tree empty via `git diff --cached --quiet`; untracked files via `git ls-files --others --exclude-standard`) | Fail with `Failure_State: Unstaged_Files_Post_Merge`, `Nothing_To_Stage`, or `Untracked_Files_Post_Merge` respectively. Dual-channel diagnostic: print `git status --porcelain` to stderr verbatim AND embed the same dump in the `Failure_State` message body so the operator sees it regardless of how the framework renders failures. Do NOT silently `git add` or `--amend` — operator decides whether to investigate, drop, or commit strays |
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
