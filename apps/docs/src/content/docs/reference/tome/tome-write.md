---
title: "deviate tome write"
description: "Reference for `deviate tome write` — the fan-out CLI that dispatches `/tome-write-*` invocations across the rows of a `/tome-classify` report, sourced from src/deviate/cli/tome.py."
doc_type: reference
status: draft
last_verified_at: 2026-07-01
verified_sha: 36b6a8b
related_issues:
  - ISS-ADH-011
prev: false
next: false
---

`deviate tome write` parses a `/tome-classify` markdown report, filters to actionable rows, pre-loads the per-doc-type writer skill bodies, and dispatches each row as a subprocess against the configured agent backend (default `opencode`). The command is defined at `src/deviate/cli/tome.py:93`; fan-out orchestration lives in `src/deviate/tome/batch.py`.

## Synopsis

```
deviate tome write --from-report <path> [--workers N] [--timeout S] [--backend NAME]
                   [--actions create,update,...] [--no-resume] [--log <path>] [--dry-run]
```

## Flags

| Name | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `--from-report` | `path` | (required) | exists, readable | Path to a `/tome-classify` markdown report; rejected by Typer when missing or unreadable. |
| `--workers` / `-w` | `int` | `4` | `1 ≤ N ≤ 32` | Parallel writer invocations; bounds the `ThreadPoolExecutor` in `run_batch`. |
| `--timeout` / `-t` | `int` | `600` | `N ≥ 10` | Per-writer timeout in seconds; applied to `subprocess.communicate(input=prompt, timeout=...)`. |
| `--backend` | `enum` | `null` | `opencode \| claude \| droid \| pi \| stub` | Override the agent backend; falls back to config, then `opencode`. |
| `--actions` | `string` | `"create,update"` | comma-separated list | Actions to process; the set is parsed via `{a.strip() for a in actions.split(",") if a.strip()}`. |
| `--no-resume` | `bool` | `false` | — | Re-run rows whose `target_file` already exists; default is to skip them. |
| `--log` | `path` | `.deviate/tome-batch.log` | empty string disables | Per-row log file; each line is flushed immediately so interrupted runs leave a usable trail. |
| `--dry-run` | `bool` | `false` | — | Print the dispatch plan as a Rich `Table` and exit; no subprocesses are spawned. |

## Backend Resolution

The effective backend is resolved by `_resolve_backend(override)` at `src/deviate/cli/tome.py:51`.

| Order | Source | Value |
|---|---|---|
| 1 | `--backend` CLI flag | the override value |
| 2 | `.deviate/config.toml` `[agent].backend` | the configured backend string |
| 3 | hardcoded default | `opencode` |

A malformed `config.toml` is tolerated (the resolver swallows `tomllib` exceptions and falls through to the default); the user can override per-run with `--backend`.

## Backend Command Tokens

`src/deviate/tome/dispatch.py::BACKEND_COMMANDS` maps each backend name to the headless command tokens used by `dispatch_writer`. The writer prompt is fed via stdin in all non-stub cases.

| Backend | Command | Mode |
|---|---|---|
| `opencode` | `opencode run` | headless `run`, stdin prompt |
| `claude` | `claude -p --permission-mode auto` | headless `-p` with auto permissions |
| `droid` | `droid exec` | headless `exec`, stdin prompt |
| `pi` | `pi -p` | headless `-p`, stdin prompt |
| `stub` | `echo` | test fallback — echoes the prompt to stdout, writes nothing |

## Action Filter

`src/deviate/tome/parser.py::filter_actionable_rows(rows, actions)` restricts the dispatch set.

| Aspect | Behaviour |
|---|---|
| Default `actions` | `{"create", "update"}` (matches `BatchConfig.actions` default) |
| Excluded by default | `setup-required`, `human-review`, `no-change` |
| Override | pass `--actions create,no-change` to include other actions |
| Unknown action in row | Row is skipped silently (not a member of the set) |

## Resume Policy

`src/deviate/tome/batch.py::should_skip_row(row, cwd, resume)` decides whether each actionable row is dispatched.

| `resume` | `target_file` empty | `target_file` exists on disk | Skip? |
|---|---|---|---|
| `True` (default) | any | any | No (agent gets to decide) |
| `True` | non-empty | missing | No |
| `True` | non-empty | present | Yes |
| `False` (`--no-resume`) | any | any | No |

The disk-existence check is `(cwd / row.target_file).exists()`; pass `--no-resume` to force a full re-run after fixing errors in the underlying code.

## BatchConfig (library use)

`run_batch(config)` in `src/deviate/tome/batch.py` accepts a `BatchConfig` dataclass for direct library invocation (bypassing the CLI).

| Field | Type | Default | Description |
|---|---|---|---|
| `report_path` | `Path` | (required) | Path to the `/tome-classify` markdown report. |
| `workers` | `int` | `4` | Bound on the `ThreadPoolExecutor` fan-out. |
| `timeout` | `int` | `600` | Per-subprocess timeout in seconds. |
| `backend` | `str` | `"opencode"` | One of the `BACKEND_COMMANDS` keys. |
| `actions` | `set[str]` | `{"create", "update"}` | Filter set passed to `filter_actionable_rows`. |
| `resume` | `bool` | `True` | Skip rows whose target file already exists. |
| `log_path` | `Path \| None` | `None` | If set, append per-row `[STATUS]` lines; flushed each row. |
| `cwd` | `Path` | `Path.cwd()` | Working directory for subprocesses and `target_file` resolution. |

A missing writer skill for any row's `doc_type` raises `RuntimeError` at pre-flight (before any subprocess is spawned), so partial output never reaches the log.

## DispatchResult (per-row record)

`src/deviate/tome/dispatch.py::DispatchResult` captures one row's outcome; `status` is the coarse label used for logging and exit-code computation.

| Field | Type | Default | Description |
|---|---|---|---|
| `returncode` | `int` | — | Process exit code; `-1` on binary-not-found or dispatch error. |
| `file_exists` | `bool` | — | True iff `(cwd / target_file).exists()` after the subprocess exits. |
| `target_file` | `str` | — | The declared target path from the capability row. |
| `stdout_tail` | `str` | `""` | Last 1000 chars of stdout; bounded for memory at scale. |
| `stderr_tail` | `str` | `""` | Last 1000 chars of stderr; printed under "Failures" when non-empty. |
| `duration_seconds` | `float` | `0.0` | Wall-clock seconds from `Popen` to `communicate()` return. |
| `timed_out` | `bool` | `False` | True when `subprocess.TimeoutExpired` fired; subprocess was killed. |

| `returncode` | `file_exists` | `timed_out` | `status` |
|---|---|---|---|
| `0` | `True` | `False` | `DONE` |
| `0` | `False` | `False` | `MISSING` (returned 0 but never wrote the file) |
| `≠ 0` | any | `False` | `FAIL` |
| any | any | `True` | `TIMEOUT` |

## Exit Codes

`BatchSummary.exit_code` (at `src/deviate/tome/batch.py:90`) maps the run's outcome to a POSIX-style code.

| Condition | Exit code | Source |
|---|---|---|
| All rows `DONE` | `0` | `failed == 0` |
| Any row non-`DONE` (excluding `SKIP`) | `1` | `failed > 0` |
| SIGINT received (Ctrl+C) | `130` | `interrupted is True` (POSIX convention) |

The CLI raises `typer.Exit(<code>)` after the summary table is printed, so shell scripts and CI runners can distinguish interrupted runs from normal failures.

## SIGINT Handling

Ctrl+C is plumbed through `src/deviate/tome/batch.py::_sigint_handler` rather than via `KeyboardInterrupt`, so the dispatch loop can drain in-flight results before exiting.

| Step | Behaviour |
|---|---|
| 1 | Signal handler sets `_INTERRUPTED` event and calls `kill_all_running_procs()` from `dispatch.py`. |
| 2 | Dispatch loop checks `_INTERRUPTED` between `as_completed` iterations and breaks out. |
| 3 | `ex.shutdown(wait=True, cancel_futures=True)` drains completed threads and cancels pending futures. |
| 4 | `BatchSummary.interrupted = True` triggers exit code `130` and the yellow "INTERRUPTED" banner. |

The handler is installed for the duration of `run_batch` and restored in the `finally` block.

## Per-row Log Format

When `--log` is set, each completed row writes one line to the log file (flushed per row so an interrupted run preserves partial state).

| Field | Width | Example |
|---|---|---|
| `status` | 7 chars, left-aligned | `DONE`, `FAIL`, `TIMEOUT`, `MISSING` |
| `action` | 5 chars, left-aligned | `create`, `update` |
| `doc_type` | 11 chars, left-aligned | `reference`, `tutorial`, `how-to`, `explanation` |
| `target_file` | rest of line | `apps/docs/src/content/docs/reference/tome/tome-write.md` |
| `duration` | trailing `({seconds:.1f}s)` | `(12.3s)` |

A row with non-empty `stderr_tail` and `status != "DONE"` gets an indented second line:

```
           stderr: <last 1000 chars of stderr>
```

## Examples

Inspect the dispatch plan before running (no subprocesses spawned):

```
deviate tome write --from-report tome-report.md --dry-run
```

Re-run every actionable row with eight workers and a 15-minute per-row timeout:

```
deviate tome write --from-report tome-report.md --workers 8 --timeout 900 --no-resume
```

Force a particular backend regardless of `.deviate/config.toml`:

```
deviate tome write --from-report tome-report.md --backend claude
```

Skip the log file entirely (useful in CI where stdout is captured):

```
deviate tome write --from-report tome-report.md --log ''
```

## See Also

- [Reference: deviate tome list](./tome-list) — sibling inspector for the `/tome-classify` report this command consumes
- [Reference index](/reference/index) — quadrant navigation pivot for the `reference/tome/` family
- [Tutorial: a guided first run](/tutorials/starter-first-run) — exercises the pipeline that produces the reports `tome write` consumes
- [Starter architecture overview](/explanation/architecture/starter-architecture) — grounding for the macro/meso/micro layer split the Tome pipeline records against

[INDEX-MISMATCH] the classifier report omitted the IA-extended fields (`layer_order`, `parent`, `next`, `group`); `prev` and `next` are emitted as `null` and the next `/tome-classify` re-run should wire the in-family reading order (likely `tome-list` → `tome-write`).