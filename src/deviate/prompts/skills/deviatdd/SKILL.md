---
name: deviatdd
description: Operate deviate micro run --all — triage failures, troubleshoot from logs, retry cleanly
category: deviatdd-tooling
version: 1.1.0
---

# deviatdd — Operating deviate micro run

This skill orchestrates `deviate micro run --all` and triages its failure
modes. It is **Micro-layer only**: meso orchestration is the job of
`/deviate-meso`, `/deviate-plan`, and `/deviate-tasks`. When a failure
escapes micro's scope, the skill points you at the canonical slash
command (see **Dispatch to slash commands** below) — it does not act
inline.

## When to use this skill

- The operator typed `/deviatdd` or asked "drain the queue", "run
  micro", "fix this failing micro run", or "why is the queue stuck".
- A micro run is mid-flight and stuck on a single task.
- The micro queue drained but the next task is in a wedged state.

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
  cross-task view of one `--all` run.

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
deviate micro run --all
```

That is the single command this skill runs. Everything else below is
triage or recovery around that command.

## Error triage table

Walk the rows in order. Each row names the failure class, the
diagnostic, and the next action.

| Failure class | Diagnostic | Next action |
|---|---|---|
| `NO_PENDING_TASKS` | micro emits `[yellow]NO_PENDING_TASKS[/]` and exits 0 | Nothing to do — the queue is empty. Stop. |
| Single task stuck in `FAILED` | micro prints `TASK_FAILED` for one task and exits non-zero | Inspect `.deviate/logs/<ISSUE_ID>/<TASK_ID>.log`. If a previous RED was rolled back, run `/deviate-red` (or `/deviate-green` / `/deviate-refactor`) on the task directly. |
| `MERGE_CONFLICT` during `deviate merge` between micro runs | git reports conflicts in `specs/issues.jsonl` / `specs/**/tasks.jsonl` | Do NOT resolve manually — the append-only ledgers are union-merged via `.gitattributes`. Surface the conflict to the operator and dispatch to `/deviate-merge` or `/squash-merge`. |
| Pre-commit hook failure | `git commit` exits non-zero with hook stderr | Read hook stderr verbatim. Fix the underlying issue (lint / format / type / test). Do NOT pass `--no-verify`. Retry the micro run. |
| Session state corruption | `.deviate/session.json` is missing, malformed, or points at a deleted worktree | Inspect via `/deviate-inspect`. If unrecoverable, run the four-step clean-slate retry below. |
| Dependency install drift | `uv sync` / `mise install` / `npm install` fails mid-micro | Re-run `mise run setup` (or the project's equivalent). Do NOT bypass with `--system`. Retry micro. |
| No `tasks.jsonl` entry found | micro emits `LEDGER_MISSING` / `TASK_NOT_FOUND` | Check the active issue via `/deviate-inspect`. If issue is missing entirely, escalate to `/deviate-meso`. |
| Uncommitted spec files | `git status --porcelain -- specs/` shows dirty entries | The deviatdd append-only ledger protocol commits specs at every phase post. Dirty specs mean a phase post was interrupted. Inspect, then dispatch to `/deviate-meso` for a clean rerun. |
| Detached HEAD | micro refuses to dispatch tasks | `git checkout <branch>` to the worktree's branch. If the branch is gone, the worktree is gone — run the clean-slate retry below. |
| Branch drift | the worktree branch has diverged from `origin/<base>` | Run `/deviate-merge` to land the diverged work, or rebase manually only if you have operator sign-off. |
| Judge stub-PASS loop | micro loops GREEN↔JUDGE indefinitely emitting `COMPLIANCE_PASS` with `NO_DIFF` | Inspect the latest task log; if GREEN is genuinely a no-op, dispatch `/deviate-execute` for the task to land it as DIRECT. |
| Agent subprocess timeout | micro prints `AGENT_TIMEOUT` after N seconds | Inspect the task log; if the model was rate-limited, retry once. If it persists, dispatch `/deviate-meso` to claim a fresh session. |

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

Then re-invoke:

```bash
deviate micro run --all
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

## Output contract

The skill emits a final status block at the end of every invocation:

```
{status: DRAINED | STUCK | BLOCKED,
 tasks_completed: N,
 tasks_remaining: M,
 retry_recommended: bool,
 next_action: <slash-command-name | "none">}
```

- `DRAINED` — queue empty, no errors.
- `STUCK` — one or more tasks failed; clean-slate retry may unstick.
- `BLOCKED` — failure mode escapes micro; dispatch to the slash command
  named in `next_action`.