---
title: "Streaming Pipeline Monitor with Live Task Status & Agent Output Display"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: ["ISS-001-004"]
issue_id: ISS-ADH-001
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/009-streaming-pipeline-monitor.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `src/deviate/ui/` (new)

## [THE_PROBLEM_CONTRACT]
When users run `deviate run --all` in automated mode, they currently see only terse `console.print()` phase labels with no visibility into what the agent is doing, which tasks are complete, or what phase the orchestrator is in. They need a live-updating dashboard that shows a task checklist, a 5-line rolling buffer of agent stdout/stderr, and a current-phase status bar — all rendered via Rich's `Live` context manager (already a dependency).

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `OrchestrationMonitor` class in `src/deviate/ui/monitor.py` that owns the Rich `Live` display and accepts status events
- Task rendering function in `src/deviate/ui/render.py` that formats the task table, agent output buffer, and status bar
- Integration into `deviate run --all` (`src/deviate/cli/micro.py`) wiring agent subprocess stdout/stderr into the monitor
- TTY detection: `Live` display for interactive terminals, plain JSONL fallback for pipes/CI
- `--json` flag for machine-readable event output

### Defensive Exclusions
- No TUI framework (Textual, blessed, curses) — Rich `Live` only
- No file-watching daemon or background process — display only exists for duration of `deviate run --all`
- No new dependencies beyond what's already in `pyproject.toml`
- No modification to `spec.md`, `tasks.md`, or non-`src/deviate/` paths as part of this change

## [UPSTREAM_REQUIREMENT_TRACING]
- **Requirements Tokens**: `FR-ADHOC-001`
- **Acceptance Criteria Tokens**: `AC-ADHOC-001-01`, `AC-ADHOC-001-02`, `AC-ADHOC-001-03`, `AC-ADHOC-001-04`, `AC-ADHOC-001-05`
- **Data Model Entities**: `TaskRecord` (status field, id, description), `IssueRecord` (issue_id)

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Sandbox Targets**:
  - `tests/test_ui/test_monitor.py::test_monitor_updates_task_marker` — verify task markers update when receiving status events
  - `tests/test_ui/test_monitor.py::test_monitor_agent_output_buffer` — verify rolling 5-line buffer behavior
  - `tests/test_ui/test_monitor.py::test_monitor_status_bar_reflects_phase` — verify status bar phase string
  - `tests/test_ui/test_render.py::test_render_task_list` — verify Rich Table formatting
  - `tests/test_ui/test_render.py::test_render_no_tty_fallback` — verify plain output when not TTY
- **Integration Sandbox Targets**:
  - `tests/test_cli/test_micro.py::test_run_all_with_live_display` — integration test for full loop with monitor

## [DEMONSTRATION_PATH]
```bash
# Unit tests
pytest tests/test_ui/ -v

# Integration test (requires mock agent)
pytest tests/test_cli/test_micro.py::test_run_all_with_live_display -v

# Manual: observe Live display during a real run
deviate run --all
```
