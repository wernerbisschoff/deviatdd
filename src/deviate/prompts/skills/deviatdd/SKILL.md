---
name: deviatdd
description: Run deviate micro run (bare) on repeat until NO_PENDING_TASKS; tasks come from tasks.md not the ledger; inspect each result, triage failures, file harness issues; allow git revert to retry tasks
category: deviatdd-tooling
version: 2.0.0
---

# deviatdd — Per-task micro orchestrator

This skill runs `deviate micro run` (bare, no task ID) on repeat. The runner picks the next unchecked task from `tasks.md` and runs it; the agent re-invokes the same command on each iteration. **Do NOT use `deviate micro run --all`** — that flag is intentionally off-limits here so the agent can stop and react on each failure. The loop terminates when the runner exits with `NO_PENDING_TASKS`. When a failure escapes micro's scope, the skill points you at the canonical slash command (see **Dispatch to slash commands** below) — it does not act inline.

The default posture is **repeat stepping**: the agent runs the bare `deviate micro run` on repeat, with the bash tool's `timeout` parameter set (see **Step 1: Run the next task**). Each invocation consumes one unchecked task from `tasks.md`; the loop terminates when the runner exits with `NO_PENDING_TASKS`. A single task boundary keeps the queue inspectable and prevents one bad task from cascading into the next.

## First action: just run it

This skill is "just run micro" — the very first action is `deviate micro run` (bare, no task ID). The runner picks the next unchecked task from `tasks.md`; the agent does NOT pre-select an ID, run `--dry-run`, or query the ledger. The agent:

1. Runs `deviate micro run` with the bash tool's `timeout` parameter set (see **Step 1** for the per-profile budget). The runner picks the next task and runs it.
2. Inspects the exit code (see **Step 2**). Exit 0 → task completed, re-invoke to continue. Exit 1 with `NO_PENDING_TASKS` → queue is drained, stop. Exit non-zero otherwise → triage via **Step 3**.

Do NOT waste turns on pre-run exploration. The runner owns RED + GREEN + JUDGE + REFACTOR; the skill's job is to feed it work and react to exits. If a task fails because the spec is wrong or the harness is broken, that is a **Step 3** action (Dispatch / clean-slate retry / deviatdd issue), not a pre-run investigation.

## Code change policy

This skill drives the micro runner; it does **not** own code changes in the project being worked on. The only code changes permitted are:

- Fixes to the deviatdd harness itself (`src/deviate/**`) when a reproducible harness bug is blocking a task.
- Skill / prompt template edits under `src/deviate/prompts/**` when the prompt misroutes a task.

Do NOT edit the project's `src/`, `tests/`, `specs/`, or any other code the active issue is touching. If a task needs a code change, the runner's RED/GREEN/JUDGE loop produces it — the skill does not pre-empt that loop. If the loop is broken, the failure is a harness bug and the **Filing deviatdd issues** path applies.

## Per-task stepping loop

Instead of `--all`, run tasks one at a time and **loop until the queue is empty**. The canonical command is the **bare** `deviate micro run` (no task ID) — the runner resolves the next unchecked task from `tasks.md` and runs it. Re-invoke the same command; it picks the next task each time. The loop terminates when the runner exits with `NO_PENDING_TASKS` (exit 1). An exit-0 from `deviate micro run` only means ONE task completed — it does NOT mean the queue is drained. The agent stops inspecting only when a task fails, behaves unexpectedly, or the runner emits `NO_PENDING_TASKS`.

### Source of truth: `tasks.md` (NOT the ledger)

The micro runner reads from two distinct artifacts, and the right one differs by purpose:

- **`specs/<EPIC>/<ISSUE>/tasks.md`** — the **human-authored decomposition**. This is the queue. The runner scans it for unchecked `[ ]` tasks (implementation lives at `src/deviate/cli/micro.py::_find_all_pending_tasks`, which `glob`s `specs/**/tasks.md`). Use `deviate micro run` (bare) to consume the next unchecked task.
- **`specs/<EPIC>/<ISSUE>/tasks.jsonl`** — the **append-only event ledger**. Each row is a phase transition (PENDING, RED, GREEN, JUDGE, REFACTOR, COMPLETED, FAILED). The ledger only knows about tasks that have already been started. Do NOT use `deviate inspect tasks list --status PENDING` to discover the queue — that reads the ledger and returns `[]` while unchecked tasks in `tasks.md` still exist. The ledger is for inspecting the history and current status of already-started tasks; it is NOT the source of truth for "what's next".

```bash
# Canonical loop — bare command, no task ID. Resolves the next unchecked task from tasks.md.
deviate micro run

# If the operator pinned a specific task:
deviate micro run <TASK_ID>
```

Flags you may need:
- `--no-refactor` — skip REFACTOR phase (e.g. for doc-only slices)
- `--no-judge` — skip JUDGE phase (careful — bypasses compliance check)
- `--profile fast` — RED → GREEN only, no JUDGE / REFACTOR. **Use only for very simple tasks** (a one-line change, a fixture file, a config edit). Default profile is `full`; switch to `fast` only when the slice is small enough to read in one screen and there is no compliance surface JUDGE would catch.
- `--model <name>` — override model for this task
- `--dry-run` — preview before executing

Do NOT use `--all`. The skill is built around per-task stepping; `--all` defeats the per-task inspection loop and is reserved for the `deviate run` meso driver.

Set a **decent timeout** on the bash invocation of `deviate micro run`. The CLI has no end-to-end deadline (`src/deviate/cli/micro.py::run_command` does not bound the subprocess); the only timeout it self-applies is `_resolve_test_timeout_seconds` (default 1800s) on the *test command*, not the whole cycle. **Use the bash tool's own `timeout` parameter** (e.g. `timeout: 1830` on the bash call) — the shell binary `timeout` and `gtimeout` are NOT installed in this environment. Do NOT wrap the command in a shell-level `timeout` invocation; rely on the harness. Full profile: 1800s. Fast profile: 900s. Add a 30s buffer so the runner can finish gracefully.

If the timeout fires, the task is still in the ledger; the next repeat invocation picks it up from the same phase state. Do NOT bypass with `kill -9` unless the runner left session state corrupted (then run the **Clean-slate retry** gate).
### Step 2: Check the result

If the command exits successfully (exit code 0), this task COMPLETED. **Do NOT stop the loop here** — re-invoke `deviate micro run` to consume the next unchecked task. The loop terminates only when the runner exits with `NO_PENDING_TASKS` (exit 1).

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

### Step 3: Decide what to do next

| After-task state | Next action |
|---|---|
| Exited 0 (COMPLETED) | **Step 4** — re-invoke `deviate micro run` to consume the next unchecked task. Do NOT stop here. |
| Task FAILED (test/code issue) | Inspect the log. Retry the same task once, or skip and fix manually via `/deviate-red`/`/deviate-green`. |
| Task FAILED (harness/git/ledger issue) | This is a deviatdd bug. See **Filing deviatdd issues** below before retrying. |
| Agent timeout / model rate-limit | Retry once with the same task ID. |
| Worktree / session corruption | Run the **Clean-slate retry** gate below. |
| Task produced a bad commit that needs rolling back | `git revert <SHA>` to create a new commit that undoes the bad changes, then re-run the task. `git revert` is the safe retry path — it preserves history and is non-destructive. Do NOT use `git reset` for this (that is the destructive path covered by the clean-slate gate). |



### Step 4: Loop until the queue is empty

After every successful task (or after Step 3 decides to retry), re-invoke `deviate micro run`. The loop terminates only when the runner exits with `NO_PENDING_TASKS` (exit 1):

```bash
# Termination check — the runner emits NO_PENDING_TASKS when tasks.md has no unchecked `[ ]` tasks.
deviate micro run
# Exit code 1, output: [red]NO_PENDING_TASKS[/]
```

- If the runner exits with `NO_PENDING_TASKS` (exit 1), the queue is drained — emit the skill's output contract and stop.
- If the runner exits 0, the task completed — re-invoke `deviate micro run` to consume the next unchecked task. Repeat indefinitely.

**Why this matters:** a single `deviate micro run` invocation runs ONE task's full cycle and exits 0 on success. That exit means only this task is done, not the queue. The agent MUST re-invoke the command, otherwise it will stop after one task while `tasks.md` still has unchecked work. The runner's `NO_PENDING_TASKS` exit is the only authoritative "no more work" signal — do NOT use `deviate inspect tasks list --status PENDING` to gate the loop (that reads the ledger, not `tasks.md`, and will give false negatives).

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

Each line is `[<UTC iso>] <EVENT>\n  <kwarg>: <value>\n` (multi-line
values are indented four-space under a `key:` header). The
`_log_run("<NAME>", ...)` calls in `src/deviate/cli/micro.py` are the
authoritative event inventory — refer to that file for the per-event
keyword schema rather than guessing fields. Event names that matter
for triage:

- `TASK_FAILED` — top-level post-cycle failure; carries `error=`.
  Read this first.
- `PHASE_START` / `PHASE_DECISION` — phase transitions. `PHASE_DECISION`
  is NOT necessarily terminal: the same event is emitted for
  intermediate JUDGE routing decisions and for the final CYCLE outcome.
  Use the `decision=` / `reroute=` / `action=` keywords plus the
  matching `phase=` to interpret it; do NOT assume `PHASE_DECISION`
  means "done".
- `INVOKE_AGENT` — names the `backend=` and `model=` actually invoked.
  Use this to verify model routing.
- `AGENT_RESULT` — carries `status=`, `verdict=`, and the full
  serialized `manifest=`. Read the manifest; do NOT assume top-level
  `files=` exists on the event itself (it lives inside the manifest
  JSON).
- `AGENT_RAW_OUTPUT` — carries the full stdout the agent's output
  callback collected, newline-joined into a single `raw_output=`
  field. Stderr is NOT captured by the logger; if the manifest is
  silent, this is your only fallback. Note: it is full stdout, not a
  tail.
- `JUDGE_REJECTED`, `JUDGE_AGENT_NO_FEEDBACK`, `JUDGE_REFACTOR_NOTE`
  — judge-specific. `JUDGE_REFACTOR_NOTE` carries `note=` (the
  refactor hint), not `note_preview=`.
- `POST_CMD_FAILURE` — `_execute_post_cmd` hook failure; carries
  `uncommitted_count=` and `files=` (the dirty files the hook refused),
  NOT `returncode=`/`stderr=`.
- `FEEDBACK_COMMIT_FAILED` — auto-GREEN's feedback-marker commit
  failed; the runner continues but the train boundary is degraded.

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

If the log points at a git / rollback / ledger anomaly, follow the
**Clean-slate retry** gate below. If it points at meso state or a
task that should never have been claimed, dispatch to the matching
slash command in the **Dispatch** table.

## Canonical invocation

```bash
# Default: bare command, on repeat. The runner picks the next unchecked task from tasks.md.
deviate micro run

# Fast profile: 15 minutes (no JUDGE / REFACTOR) — only for very simple slices.
deviate micro run --profile fast

# Pinned task: the operator gave a specific ID.
deviate micro run <TASK_ID>
```

The per-task stepping loop is the default mode. **Do NOT use `--all`** — it is reserved for the `deviate run` meso driver that chains meso into micro end-to-end. Here, every PENDING task gets its own invocation so the agent can inspect the result and decide whether to advance.

## Error triage table

Walk the rows in order. Each row names the failure class, the
diagnostic, and the next action.

| Failure class | Diagnostic | Next action |
|---|---|---|
| `NO_PENDING_TASKS` | micro emits `[yellow]NO_PENDING_TASKS[/]` and exits 0 | Nothing to do — the queue is empty. Fail here gracefully. |
| Single task stuck in `FAILED` | micro prints `TASK_FAILED` for one task and exits non-zero | Inspect `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`. If a previous RED was rolled back, run `/deviate-red` (or `/deviate-green` / `/deviate-refactor`) on the task directly. If the failure looks like a deviatdd harness bug, file a deviatdd issue (see **Filing deviatdd issues** below). |
| `MERGE_CONFLICT` during `deviate merge` between micro runs | git reports conflicts in `specs/issues.jsonl` / `specs/**/tasks.jsonl` | Do NOT resolve manually — the append-only ledgers are union-merged via `.gitattributes`. Surface the conflict to the operator and dispatch to `/deviate-merge` or `/squash-merge`. |
| Pre-commit hook failure | `git commit` exits non-zero with hook stderr | Read hook stderr verbatim. Fix the underlying issue (lint / format / type / test). Do NOT pass `--no-verify`. Retry the task. |
| Session state corruption | `.deviate/session.json` is missing, malformed, or points at a deleted worktree | Inspect via `/deviate-inspect`. If unrecoverable, run the four-step clean-slate retry below. |
| Dependency install drift | `uv sync` / `mise install` / `npm install` fails mid-micro | Re-run `mise run setup` (or the project's equivalent). Do NOT bypass with `--system`. Retry the task. |
| No `tasks.jsonl` entry found | micro emits `LEDGER_MISSING` / `TASK_NOT_FOUND` | Check the active issue via `/deviate-inspect`. If issue is missing entirely, escalate to `/deviate-meso`. |
| Uncommitted spec files | `git status --porcelain -- specs/` shows dirty entries | The deviatdd append-only ledger protocol commits specs at every phase post. Dirty specs mean a phase post was interrupted. Inspect, then dispatch to `/deviate-meso` for a clean rerun. |
| Detached HEAD | micro refuses to dispatch tasks | `git checkout <branch>` to the worktree's branch. If the branch is gone, the worktree is gone — run the clean-slate retry below. |
| Branch drift | the worktree branch has diverged from `origin/<base>` | Run `/deviate-merge` to land the diverged work, or rebase manually only if you have operator sign-off. |
| Judge emits `COMPLIANCE_PASS` on a slice whose diff is intrinsically empty (e.g. RED-only deliverable, fixture file, generated types, doc-only slice) | micro routes the JUDGE verdict to `next_action: proceed_to_refactor_no_diff` and enters REFACTOR regardless of `--no-refactor`; the GREEN-empty branch never enters the rejection cascade. Inspect the task log to confirm the GREEN diff is genuinely empty | No operator action — REFACTOR commits the empty-diff sign-off and marks the task COMPLETED. If REFACTOR runs but the task doesn't progress (legacy runner without the discriminator), dispatch `/deviate-execute` for the task to land it as DIRECT. |
| Agent subprocess timeout | micro prints `AGENT_TIMEOUT` after N seconds | Inspect the task log; if the model was rate-limited, retry once. If it persists, dispatch `/deviate-meso` to claim a fresh session. |
| Pattern: repeated harness failures across different tasks | Multiple tasks fail with similar git/ledger/agent errors | **Do not retry**. File a deviatdd issue (see below). The harness has a bug, not the task. |

## Filing deviatdd issues

When a task failure reveals a bug in the deviatdd harness itself
(not in the task being executed), file an issue on the deviatdd
repository so the root cause is tracked and fixed.

### Indicators of a harness bug

These are signals that the task itself is probably fine but the
orchestration layer is broken:

- Git operations fail in ways the task could not cause (e.g. detached
  HEAD in a freshly-created worktree, `git commit` even though the task
  ran correctly).
- Ledger corruption or ledger write failures that leave tasks in
  an unprocessable state.
- Session state corruption visible across multiple tasks.
- Error messages that reference internal deviatdd code paths
  (`src/deviate/...`) with stack traces.
- `POST_CMD_FAILURE` that is not a lint/format issue (e.g. `git`
  misconfiguration, hook script itself crashing).
- Agent backend issues that persist across retries (same error,
  different tasks).
- Rollback logic fails or leaves the worktree in a dirty state
  that the clean-slate retry cannot recover.

### How to file a deviatdd issue

When you identify a harness bug, file an issue in the deviatdd
repository. The deviatdd repo is the current working directory
(`/Users/werner/Projects/tools/deviatdd`).

```bash
# Capture the evidence first — copy the relevant log:
TASK_LOG=".deviate/logs/$(ls -t .deviate/logs/*/*.log 2>/dev/null | head -1)"
TASK_LOG_CONTENT=$(cat "$TASK_LOG" 2>/dev/null)

# Create a GitHub issue for deviatdd:
gh issue create \
  --repo werner/deviatdd \
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

If the log is very large, truncate to the relevant section and note
that the full log is available at the path shown.

After filing the issue, decide whether to:

1. **Continue** — if the bug is isolated to one task, skip that task
   via the ledgers and proceed to the next.
2. **Stop** — if the harness is fundamentally broken (session state,
   git isolation), halt and surface the issue to the operator with a
   `next_action: /deviate-meso` recommendation.
3. **Workaround** — if there is a known workaround (e.g. clean-slate
   retry), apply it and note the issue reference in the status output.

---

## Clean-slate retry

Run this four-step gate **before** any `git reset --hard` or
`git clean -fd`. AGENTS.md forbids destructive ops without explicit
human confirmation; the gate enforces that.

### 1. Ledger sanity

```bash
git status --porcelain -- specs/issues.jsonl specs/**/tasks.jsonl specs/_product/flows.jsonl
```

MUST be empty. The Append-Only Ledger Protocol (constitution §1) and the
`<phase> post` scripts guarantee these are committed post-post-script.

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
- `.deviate/`, `.mise/`, `.venv/`, `__pycache__/`, `.worktrees/` →
  explicitly preserved by `_execute_rollback`'s `git clean -fd`
  contract; do nothing with them.

### 3. Confirmation gate

Surface the workspace inventory + the exact command pair
(`git reset --hard HEAD && git clean -fd`) to the user with a numbered
list of every file that would be discarded, and require an unambiguous
affirmation: "yes", "do it", "reset", "ship it". **Silence is NOT
sign-off** — same convention as `/deviate-flows` and
`/deviate-architecture` sign-off.

### 4. The reset

Only after step 3 affirmatively clears:

```bash
git reset --hard HEAD
git clean -fd    # WITHOUT -x: preserves .deviate/, .mise/, .venv/, __pycache__/, .worktrees/
```

Then re-invoke for the next pending task:

```bash
# Inside the worktree:
deviate micro run <TASK_ID>
```

What `git clean -fd` deliberately does NOT touch (`-x` excluded):
`.deviate/`, `.mise.toml`, `.venv/`, `__pycache__/`, `.worktrees/`,
anything in `.gitignore`. This matches the existing rollback discipline
at `src/deviate/cli/micro.py::_execute_rollback`.

## Dispatch to slash commands (when micro alone is not enough)

When the failure mode escapes micro's scope, point the operator (or
yourself) at the canonical slash command. Each entry lists the command
and a one-line "use this when..." description.

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
| `/deviate-pr` | The branch is merged locally and you need to open / merge the PR. |
| `/deviate-execute` | A non-TDD task is blocking the queue and needs DIRECT execution. |
| `/deviate-hotfix` | A production-grade bug needs a one-shot fix outside the normal task flow. |
| `/deviate-prune` | You suspect a stale test in `tests/` is causing false REDs. |
| `/deviate-inspect` | You need a read-only query of the ledger / session / tasks. |

This skill never invokes these on its own — it tells the operator which
slash command to run and why, then stops. Each command's pre/post-script
contract stays intact and individually testable.

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
- Never wrap `/deviate-meso` in this skill — meso has its own
  orchestrator with its own safety gates; duplicating it here would
  bypass them.
- Never file a deviatdd issue for a task-level failure (lint, test
  logic, formatting, missing implementation). Harness issues are
  git/ledger/session/agent errors that repeat across tasks — not
  per-task code quality problems.
- Never file a deviatdd issue for `TASK_FAILED` errors whose root
  cause is the task's own RED/GREEN/JUDGE logic. Verify the triage
  table first.

## Output contract

The skill emits a final status block at the end of every invocation:

```
{status: DRAINED | STUCK | BLOCKED | DEVIATDD_BUG,
 tasks_completed: N,
 tasks_remaining: M,
 retry_recommended: bool,
 next_action: <slash-command-name | "none">,
 deviatdd_issue_filed: <issue-url | null>}
```

- `DRAINED` — queue empty, no errors.
- `STUCK` — one or more tasks failed; clean-slate retry may unstick.
- `BLOCKED` — failure mode escapes micro; dispatch to the slash command
  named in `next_action`.
- `DEVIATDD_BUG` — harness failure identified; deviatdd issue filed at
  `deviatdd_issue_filed`.
