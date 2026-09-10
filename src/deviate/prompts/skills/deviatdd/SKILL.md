---
name: deviatdd
description: Drive deviate run until this issue is happy/converged (meso if needed, micro drain, optional Converge tail). Inspect and triage failures. Optional review argument pauses after a successful run for a human look. Walkthrough, review, and PR stay outside the until-happy loop.
category: deviatdd-tooling
version: 3.1.0
---

# deviatdd — Until-happy `deviate run` driver

This skill drives **`deviate run`** until this issue is happy. Do **not** explicitly chain `deviate meso run` then `deviate micro run`. `deviate run` already prepares Meso when needed, drains Micro, and — when the `converge` pack is installed or the operator passed `--converge` — continues into Converge. If Converge appends tasks, `deviate run` drains Micro again until Converge is clean. Stop when the output is **CONVERGED**, or **NO_PENDING** / empty queue after a clean Converge (`tasks.md` byte-unchanged). When a failure escapes that loop, point at the canonical slash command (see **Dispatch to slash commands** below) — do not act inline.

**Default invoke** (no skill argument): run `deviate run` (add `--converge` when the operator asked or the converge pack is installed). If the output is `CONVERGE_READY`, run `/deviate-converge` (`deviate converge pre` → assess → `deviate converge post`), then re-invoke `deviate run` if tasks were appended. If `CONVERGED` or `NO_PENDING` after a clean Converge, stop happy. **Review invoke** when `$ARGUMENTS` contains the token `review`, or the operator said `/deviatdd review` / "deviatdd with review": after a successful until-happy `deviate run`, STOP for a human look. Never pass `--review` or `--all` to the runner — this skill's `review` argument is an agent loop policy, not a CLI flag. Walkthrough, `/deviate-review`, and `/deviate-pr` stay **outside** this until-happy loop.


## First action: drive `deviate run` until happy

Run this command first (worktree / issue discovery included):

```bash
deviate run
```

If the operator selected the converge pack or asked for Converge, use:

```bash
deviate run --converge
```

Set the bash tool's `timeout` parameter. A cold run may spawn Meso (Plan + Tasks, each up to `timeout_seconds`, default 1800s) plus Micro cycles, so use **`timeout: 9000`** unless the slice is already prepared.

`deviate run` owns Meso (issue discovery, Specify, Plan, Tasks, resume) and Micro drain. Do not inspect `plan.md` or `tasks.md` manually before this command. Do not chain Meso then Micro as two separate commands.

Meso inside `deviate run` is idempotent inside an existing feature worktree:

- Missing `plan.md` and `tasks.md`: run Plan, then Tasks.
- Valid `plan.md` with no `tasks.md`: skip Plan and resume at Tasks.
- Valid `plan.md` and non-empty `tasks.md`: emit `MESO_ALREADY_COMPLETE`.
- Invalid existing Plan or empty Tasks: stop without overwriting the artifact (`MESO_PLAN_INVALID` / `MESO_TASKS_INVALID`).

From `main` or `master`, the run claims the next issue and creates its linked worktree. Use that worktree for follow-up commands. Inside a linked `feat/...` worktree, Meso skips Specify and resumes there.

Stop if `deviate run` exits non-zero (other than a documented handoff you will continue). Report the exact token (`MESO_PLAN_INVALID`, `TASK_FAILED`, `CONVERGE_NOT_READY`, …).

Skip pre-run code exploration — meso owns preparation.
Micro owns RED, GREEN, JUDGE, and REFACTOR.
Converge (opt-in pack) assesses this issue after drain and may append Convergence tasks.

## Code change policy
 
This skill drives the micro runner. It does not normally own project code or specification changes.
 
The only permitted changes are:
 
- Fixes to the deviatdd harness itself (`src/deviate/**`) when a reproducible harness bug blocks a task.
- Skill or prompt template edits under `src/deviate/prompts/**` when a prompt misroutes a task.
- Small unblocking fixes in the active worktree when the task log shows the runner cannot proceed without them. Keep each fix operational. Do not implement the task.
- **Explicit operator-requested scope corrections:** when the operator identifies a contradiction in `tasks.md`, `plan.md`, or issue specifications, edit the affected specification artifacts, commit the correction, and retry Meso or Micro as requested. Do not modify implementation code or tests during this correction.
 
By default, do not edit the project's `src/`, `tests/`, `specs/`, or other files touched by the active task. The explicit scope-correction exception overrides that default only for the named specification artifacts.

## Until-happy stepping loop

Drive **`deviate run`** — never invent a second top-level runner. **Default invoke** (no argument) **loops until happy/converged**: re-invoke `deviate run` after Converge appends tasks; stop on `CONVERGED` or `NO_PENDING` after a clean Converge. Walkthrough / review / PR are not part of this loop.

### Source of truth: `tasks.md` (NOT the ledger)

The micro runner reads from two distinct artifacts, and the right one differs by purpose:

- **`specs/<EPIC>/<ISSUE>/tasks.md`** — the **human-authored decomposition**. This is the queue. The runner scans it for unchecked `[ ]` tasks (implementation lives at `src/deviate/cli/micro.py::_find_all_pending_tasks`, which `glob`s `specs/**/tasks.md`). Use `deviate micro run` (bare) to consume the next unchecked task.
- **`specs/<EPIC>/<ISSUE>/tasks.jsonl`** — the **append-only event ledger**. Each row is a phase transition (PENDING, RED, GREEN, JUDGE, REFACTOR, COMPLETED, FAILED). The ledger only knows about tasks that have already been started. Do NOT use `deviate inspect tasks list --status PENDING` to discover the queue — that reads the ledger and returns `[]` while unchecked tasks in `tasks.md` still exist. The ledger is for inspecting the history and current status of already-started tasks; it is NOT the source of truth for "what's next".

```bash
# Canonical loop — one command. Meso if needed, Micro drain, optional Converge tail.
deviate run

# Force the Converge tail even if the pack was not detected in this worktree:
deviate run --converge

# If the operator pinned a specific leftover task (triage only, not the happy path):
deviate micro run <TASK_ID>
```

Flags you may need:
- `--no-refactor` — skip REFACTOR phase (e.g. for doc-only slices)
- `--no-judge` — skip JUDGE phase (careful — bypasses compliance check)
- `--profile fast` — RED → GREEN only, no JUDGE / REFACTOR. **Use only for very simple tasks** (a one-line change, a fixture file, a config edit). Default profile is `full`; switch to `fast` only when the slice is small enough to read in one screen and there is no compliance surface JUDGE would catch.
- `--model <name>` — override model for this task
- `--dry-run` — preview before executing


Set a **decent timeout** on the bash invocation of `deviate micro run`, sized for the **whole cycle**: full profile → **`timeout: 9000`**, fast profile (RED, GREEN only) → **`timeout: 5400`**. The shell binaries `timeout`/`gtimeout` are NOT installed here — use the bash tool's own `timeout` parameter, never a shell-level wrapper.

If the timeout fires, the task is still in the ledger; the next repeat invocation picks it up from the same phase state.

### Step 2: Check the result

Exit code 0 has two valid outcomes. Read the output before you decide:

- `CONVERGED` or `NO_PENDING` after a clean Converge: the issue is happy. Stop.
- `CONVERGE_READY`: run `/deviate-converge`, then **MUST re-invoke** `deviate run` if `post` appended tasks. If `post` reports CONVERGED, stop happy.
- `NO_PENDING_TASKS` / empty queue and Converge is not in this run: the queue is empty. Stop (pack not installed).
- A task completed inside a pinned `deviate micro run` triage: **Default invoke:** **Do NOT stop here** — **MUST re-invoke** `deviate run` (or the pinned micro command if still unblocking). **Review invoke:** show the task ID and commits, then wait for the human.

If the command exits non-zero, inspect the per-task transcript before
deciding how to proceed:

```bash
cat .deviate/logs/<ISSUE_ID>/<TASK_ID>.log | tail -30
```


Key signals:

| Signal | What it means |
|---|---|
| `TASK_FAILED` with `error=` | Top-level cycle failure — read this first. |
| `PHASE_DECISION` `decision=CYCLE_COMPLETE` | Task finished successfully (should not be here if exit was non-zero). |
| `PHASE_DECISION` `decision=JUDGE_REJECTED` | JUDGE found compliance issues. |
| `AGENT_RESULT` `status=error` | Agent subprocess error (timeout, crash, etc.). |
| `POST_CMD_FAILURE` | Post-phase commit/lint hook failed. |
| `JUDGE_REJECTED` with `head_sha`/`reset_to`/`recovery_ref` | Rolled-back tree — `git show <head_sha>` or `git switch <recovery_ref>` inspects it (never `git stash`). |
| `LOOP_DETECTED` / `CYCLE_END` | Repeated JUDGE rejects (`blast=`, `streak=`) / task left the cycle — read `.verdicts.jsonl`. |
| `FEEDBACK_COMMIT_FAILED` | Auto-GREEN feedback-marker commit failed; train boundary degraded. |

### Step 3: Unblock or escalate

Use this bounded ladder. Do not use repeated retries as diagnosis.

| Condition | Action | Retry limit |
|---|---|---|
| Transient agent timeout or model rate-limit; worktree and ledgers are clean | Re-run the same task ID. | Once. Escalate if the same signal returns. |
| Hook, lint, format, missing import, or typo blocks a commit | Apply only the minimum operational fix. Do not implement task behavior. Report the edit, then re-run the same task ID. | Once after the fix. |
| Deterministic RED, GREEN, or JUDGE task failure | Re-run `deviate micro run <TASK_ID>` once — the runner resumes at the failed phase. If the same phase fails again, drive it inline yourself by following `src/deviate/prompts/commands/deviate-<phase>.md` (run `deviate <phase> pre`, do the phase work, run `deviate <phase> post`). Never output `/deviate-green` as an instruction for the operator. | One retry, then one inline drive. |
| Worktree or session corruption | Use the **Clean-slate retry** gate. It requires explicit approval before destructive commands. | One approved recovery. |
| Git, ledger, rollback, or internal `src/deviate/...` failure | Treat it as a harness bug. Preserve logs, check for an open issue, then escalate. | No retry unless a documented workaround exists. |
| Failure ownership is unclear, evidence conflicts, or recovery can lose data | Stop and ask the operator. Include the task ID, command, last error, dirty-file list, and recommended slash command. | No retry. |

Escalation triggers are the approval, dirty-ledger, and repeat-failure rows above. Escalate when the same harness signature affects two tasks instead of retrying each one. Do not skip a task by editing `tasks.jsonl`; it is append-only.

If a bad task commit needs rollback, use `git revert <SHA>`, then re-run the task. Do not use `git reset` outside the clean-slate gate.



### Step 4: Loop until happy / converged

**Default invoke only.** After every successful `deviate run` (or after Step 3 decides to retry), continue until the issue is happy:

```bash
# Termination — deviate run emitted CONVERGED, or NO_PENDING after a clean Converge.
deviate run
# Happy: CONVERGED  |  NO_PENDING after converge post left tasks.md byte-unchanged
```

- If the runner emits `CONVERGED`, or `NO_PENDING` after Converge reported clean, stop — emit the skill's output contract.
- If the runner emits `CONVERGE_READY`, run `/deviate-converge` then re-invoke `deviate run` when tasks were appended.
- If the runner exits 0 after a Micro-only drain (pack not installed, no `--converge`), stop. Do not invent Converge.

**Review invoke skips this step after a success** — resume here only when the human continues or Step 3 ordered a retry. Never start `/deviate-walkthrough`, `/deviate-review`, or `/deviate-pr` inside this loop.

---
---

## Troubleshooting failed runs

Before guessing at a fix, read the logs. `deviate micro run` writes
events to two sinks under `.deviate/logs/` via the dispatcher in
`src/deviate/core/run_logger.py`:

- **Per-task transcript** — `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`,
  append-mode, history across retries of one task. Created only when
  `_execute_task_with_retry` resolves both `issue_id` and a known
  `task_id`. Tasks missing either land only in the per-run log.
- **Per-run chronological log** — `.deviate/logs/run_<UTC>.log`,
  one file per invocation, always written. Use this when the failing
  task is unknown, the per-task file does not exist, or you need a
  cross-task view of one multi-task run.
- **Per-task JUDGE postmortem** — `.deviate/logs/<ISSUE_ID>/<TASK_ID>.verdicts.jsonl`.
  One JSON object per JUDGE application (pass and reject), plus a
  final `cycle_end` object when `_run_tdd_cycle` leaves. JSONL, not
  the `[<UTC iso>] EVENT` transcript format. Read this first when
  asking why JUDGE failed RED or GREEN. A reject that rolled back
  carries `head_sha` / `reset_to` / `recovery_ref` — `git show
  <head_sha>` or `git switch <recovery_ref>` inspects the discarded
  tree. The same three fields are on the post-reset `tasks.jsonl` row.
- **Raw agent sidecar** — `.deviate/logs/<ISSUE_ID>/<TASK_ID>.raw/<phase>-<n>.log`
  (optional `<phase>-<n>.prompt.log`). Verbatim stdout lives here so the
  main transcript stays scannable.

Each line is `[<UTC iso>] <EVENT>\n  <kwarg>: <value>\n` (multi-line values are indented four-space under a `key:` header).
Triage on these events: `TASK_FAILED` (start here), `PHASE_DECISION` (routing), `AGENT_RESULT` (agent output), `INVOKE_AGENT` (spawn record), `CYCLE_END` (cycle exit).


Quick lookup:

```bash
# Latest per-task transcript (most-recently-modified file):
ls -lt .deviate/logs/*/*.log | head -5
cat "$(ls -t .deviate/logs/*/*.log | head -1)"

# Latest chronological run log:
ls -t .deviate/logs/run_*.log | head -1 | xargs cat

# Triage a failed task — last 20 lines of its transcript:
cat .deviate/logs/<ISSUE_ID>/<TASK_ID>.log | tail -20
```


## Canonical invocation

This skill accepts an optional **skill argument** (not a CLI flag): `review` in `$ARGUMENTS` selects review mode.

```text
# Skill invoke — default (no argument): auto-continue after each success.
/deviatdd
# or: the skill with empty $ARGUMENTS

# Skill invoke — review: pause after each successful task for a human look.
/deviatdd review
# or: $ARGUMENTS contains the token `review`
# or: the operator said "deviatdd with review"
```

The spawned runner command is **`deviate run`** (plus `--converge` when the pack or operator requires it). **Do not pass `--review` or `--all` into the runner.** Pinned-task triage may use `deviate micro run <TASK_ID>` only after a failure.

```bash
# Default: until-happy driver.
deviate run

# Converge tail (pack installed or operator asked).
deviate run --converge

# Fast profile on a pinned leftover task (triage only).
# Set the bash tool's timeout per the budget in Until-happy stepping loop (timeout: 5400).
deviate micro run --profile fast
```

Re-invoke `deviate run` until CONVERGED or NO_PENDING after a clean Converge.

## Error triage table

Walk the rows in order. Each row names the failure class, the
diagnostic, and the next action.

| Failure class | Diagnostic | Next action |
|---|---|---|
| `NO_PENDING_TASKS` / `CONVERGED` | run or micro emits empty-queue / CONVERGED and exits 0 | Happy if Converge was clean or the pack is off. If `CONVERGE_READY`, run `/deviate-converge` first. |
| Single task stuck in `FAILED` | micro prints `TASK_FAILED` for one task and exits non-zero | Inspect `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`. If a previous RED was rolled back, run `/deviate-red` (or `/deviate-green` / `/deviate-refactor`) on the task directly. If the failure looks like a deviatdd harness bug, file a deviatdd issue (see **Filing deviatdd issues** below). |
| `MERGE_CONFLICT` during `deviate merge` between micro runs | git reports conflicts in `specs/issues.jsonl` / `specs/**/tasks.jsonl` | Do NOT resolve manually — the append-only ledgers are union-merged via `.gitattributes`. Surface the conflict to the operator and dispatch to `/deviate-merge` or `/squash-merge`. |
| Pre-commit hook failure | `git commit` exits non-zero with hook stderr | Read hook stderr verbatim. Fix the underlying issue (lint / format / type / test). Do NOT pass `--no-verify`. Retry the task. |
| Session state corruption | `.deviate/session.json` is missing, malformed, or points at a deleted worktree | Inspect via `/deviate-inspect`. If unrecoverable, run the four-step clean-slate retry below. |
| Dependency install drift | `uv sync` / `mise install` / `npm install` fails mid-micro | Re-run `mise run setup` (or the project's equivalent). Do NOT bypass with `--system`. Retry the task. |
| No `tasks.jsonl` entry found | micro emits `LEDGER_MISSING` / `TASK_NOT_FOUND` | Check the active issue via `/deviate-inspect`. If issue is missing entirely, escalate to `/deviate-meso`. |
| Uncommitted spec files | `git status --porcelain -- specs/` shows dirty entries | The deviatdd append-only ledger protocol commits specs at every phase post. Dirty specs mean a phase post was interrupted. Inspect, then dispatch to `/deviate-meso` for a clean rerun. |
| Detached HEAD | micro refuses to dispatch tasks | `git checkout <branch>` to the worktree's branch. If the branch is gone, the worktree is gone — run the clean-slate retry below. |
| Branch drift | the worktree branch has diverged from `origin/<base>` | Run `/deviate-merge` to land the diverged work, or rebase manually only if you have operator sign-off. |
| Judge emits `COMPLIANCE_PASS` on an intrinsically empty diff (RED-only deliverable, fixture, generated types, doc-only slice) | micro routes the verdict to `next_action: proceed_to_refactor_no_diff` and enters REFACTOR regardless of `--no-refactor` | No action — REFACTOR commits the empty-diff sign-off and marks COMPLETED. |
| Agent subprocess timeout | micro prints `AGENT_TIMEOUT` after N seconds | Inspect the task log; if the model was rate-limited, retry once. If it persists, dispatch `/deviate-meso` to claim a fresh session. |
| Pattern: repeated harness failures across different tasks | Multiple tasks fail with similar git/ledger/agent errors | **Do not retry**. File a deviatdd issue (see below). The harness has a bug, not the task. |

## Filing deviatdd issues


File an issue only when the triage table classifies the failure as a harness bug — git, ledger, session, or agent errors repeating across tasks. Never file for task-level failures (lint, test logic, formatting, missing implementation).

Typical harness signals: operations the task could not cause (detached HEAD in a fresh worktree, `src/deviate/...` stack traces, non-lint `POST_CMD_FAILURE`), ledger or session corruption across tasks, rollback leaving a dirty tree.

### How to file a deviatdd issue

When you identify a harness bug, check for an existing OPEN issue
BEFORE creating a new one. Search the deviatdd repo's own issue
tracker `wernerbisschoff/deviatdd` for a match on the same failure:

```bash
# Search open issues for the same harness failure:
gh issue list --repo wernerbisschoff/deviatdd --state open --search "<short description>"
```

If an open issue already matches, do NOT create a duplicate. Comment
the new evidence and task context on the existing issue instead:

```bash
# Comment the new evidence on the matching issue (use its number):
gh issue comment <ISSUE_NUMBER> --repo wernerbisschoff/deviatdd --body "<evidence + task context>"
```

Only when no open issue matches do you create a new one. The repo is the current working directory.

```bash
# Capture the evidence first — copy the relevant log:
TASK_LOG=".deviate/logs/$(ls -t .deviate/logs/*/*.log 2>/dev/null | head -1)"
TASK_LOG_CONTENT=$(cat "$TASK_LOG" 2>/dev/null)

# Create a GitHub issue for deviatdd (only after the search above finds no match):
gh issue create \
  --repo wernerbisschoff/deviatdd \
  --title "bug: <short description of the harness failure>" \
  --label bug \
  --body "## Description
  <What went wrong in 1-2 sentences>

  ## Evidence
  \`\`\`
  $TASK_LOG_CONTENT
  \`\`\`

  ## Task context
  - Task ID: <TSK-NNN-NN>
  - Issue ID: <ISS-NNN-NNN>
  - Command run: \`deviate micro run <TASK_ID>\`
  - DeviatDD version: \`uv run deviate --version\`

  ## Suspected root cause
  <Your analysis — what in the harness appears to be the issue>
"
```


After filing (or commenting), follow Step 3: continue past an isolated task, stop on fundamental breakage, or apply a documented workaround.

---

## Clean-slate retry

Run this four-step gate **before** any `git reset --hard` or
`git clean -fd`. AGENTS.md forbids destructive ops without explicit
human confirmation; the gate enforces that.

### 1. Ledger sanity

```bash
git status --porcelain -- specs/issues.jsonl specs/**/tasks.jsonl
```

MUST be empty.

If any are dirty → STOP. A micro task may be mid-flight and the user
must resolve that first (do NOT reset through uncommitted ledger writes).

### 2. Workspace inventory

```bash
git status --porcelain
```

Classify each entry:

- Modified tracked files under `src/`, `tests/`, `specs/` → almost
  certainly mid-task WIP; halt and surface to user.
- Untracked files / directories → back them up to
  `/tmp/deviatdd-cleanup-<UTC>/` via `mv` (NOT delete), then proceed.
- `.deviate/`, `.mise/`, `.venv/`, `__pycache__/`, `.worktrees/`, `wt/` →
  explicitly preserved by `_execute_rollback`'s `git clean -fd`
  contract; do nothing with them.

### 3. Confirmation gate

Surface the workspace inventory + the exact command pair
(`git reset --hard HEAD && git clean -fd`) to the user with a numbered
list of every file that would be discarded, and require an unambiguous
affirmation: "yes", "do it", "reset", "ship it". **Silence is NOT
sign-off**.

### 4. The reset

Only after step 3 affirmatively clears:

```bash
git reset --hard HEAD
git clean -fd    # WITHOUT -x: preserves .deviate/, .mise/, .venv/, __pycache__/, .worktrees/, wt/
```

Then re-invoke for the next pending task:

```bash
# Inside the worktree:
deviate micro run <TASK_ID>
```

## Dispatch to slash commands (when micro alone is not enough)


| Slash command | Use this when... |
|---|---|
| `/deviate-meso` | Meso orchestration broke and you need to re-enter plan → tasks → micro. |
| `/deviate-plan` | You only need to re-run plan for the active issue. |
| `/deviate-tasks` | You only need to re-decompose tasks for the active issue. |
| `/deviate-red` | You need to drive the RED phase by hand (e.g. RED was rolled back and you want to retry). |
| `/deviate-green` | You need to drive the GREEN phase by hand (e.g. GREEN was rolled back and you want to retry). |
| `/deviate-refactor` | You need to drive the REFACTOR phase by hand. |
| `/deviate-judge` | You need to drive the JUDGE phase by hand (e.g. confirm a previously rolled-back judge). |
| `/deviate-merge` | The micro queue is drained and you need to land the worktree branch. |
| `/deviate-converge` | After Micro drain, assess this issue vs brief/plan/tasks and append gap tasks or report CONVERGED. Opt-in pack. Inside the until-happy loop when `CONVERGE_READY`. |
| `/deviate-pr` | The branch is merged locally and you need to open / merge the PR. |
| `/deviate-execute` | A non-TDD task is blocking the queue and needs DIRECT execution. |
| `/deviate-hotfix` | A production-grade bug needs a one-shot fix outside the normal task flow. |
| `/deviate-prune` | Manual honeycomb pass: classify and thin spy/impl tests for one issue. Never auto-run after COMPLETED, `--all`, or this skill's success loop. Does not delete plan.md / tasks.md. |
| `/deviate-inspect` | You need a read-only query of the ledger / session / tasks. |

The table below names inline procedures this agent executes itself. Prefer `deviate micro run <TASK_ID>` (runner resumes at the failed phase). Read the phase prompt file and run its pre/work/post sequence only when the retry fails twice. Never stop and tell the operator to run a slash command.

## What NOT to do

- Never `git reset --hard` without running the four-step clean-slate
  gate above.
- Never `git clean -fd` with `-x` (would destroy `.deviate/rollback.jsonl`
  and session state).
- Never `git clean -fd` to recover from a "cd into worktree and re-run
  plan/tasks" mistake — partial ledger writes violate constitution §1.
  Escalate to `/deviate-meso` for a clean rerun.
- Never delete a feature branch (AGENTS.md forbids without explicit
  request).
- Never `git push --force`.
- Never `--no-verify` on commits.
- Never auto-run `/deviate-prune` after a success — prune is a manual,
  one-issue pass, never part of this skill's loop.
- Never wrap `/deviate-meso` or `/deviate-micro` as the happy path —
  drive `deviate run` until happy/converged instead.
- Never start `/deviate-walkthrough`, `/deviate-review`, or `/deviate-pr`
  inside the until-happy loop.

## Output contract


```
{status: DRAINED | STUCK | BLOCKED | DEVIATDD_BUG,
 tasks_completed: N,
 tasks_remaining: M,
 retry_recommended: bool,
 next_action: <slash-command-name | "none">,
 deviatdd_issue_filed: <issue-url | null>}
```

- `DRAINED` — queue empty and Converge clean (or pack not installed), no errors.
- `STUCK` — one or more tasks failed; clean-slate retry may unstick.
- `BLOCKED` — failure mode escapes micro; dispatch to the slash command
  named in `next_action`.
- `DEVIATDD_BUG` — harness failure identified; deviatdd issue filed at
  `deviatdd_issue_filed`.
