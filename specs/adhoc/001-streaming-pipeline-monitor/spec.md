# FEATURE_SPECIFICATION: specs/adhoc/001-streaming-pipeline-monitor/spec.md

## SYSTEM_TOPOLOGY_MAPPING
- **Epic Domain**: `adhoc`
- **Issue ID**: `ISS-ADH-001`
- **Issue Slug**: `001-streaming-pipeline-monitor`
- **Upstream PRD**: `specs/adhoc/prd.md`
- **Branch**: `feat/adhoc/001-streaming-pipeline-monitor`
- **Primary Workstation Paths**:
  - `src/deviate/ui/monitor.py` — `OrchestrationMonitor` class owning the Rich `Live` display
  - `src/deviate/ui/render.py` — Task table, agent output buffer, and status bar renderers
  - `src/deviate/cli/micro.py` — Integration wiring for agent subprocess stdout/stderr into monitor
  - `src/deviate/ui/__init__.py` — Package init for the ui subpackage
  - `tests/test_ui/test_monitor.py` — Unit tests for monitor state machine and event handling
  - `tests/test_ui/test_render.py` — Unit tests for render functions and TTY detection
  - `tests/test_cli/test_micro.py::test_run_all_with_live_display` — Integration test for full loop
- **Downstream Dependency Graph**:
  ```
  FR-ADHOC-001 (Streaming Pipeline Monitor)
       └─► US-001-DISP (Live display lifecycle and Rich integration)
       └─► US-002-TASK (Task list with completion markers)
       └─► US-003-BUFF (Rolling agent output buffer)
       └─► US-004-PHAS (Phase status bar)
       └─► US-005-TTY (TTY detection and JSONL fallback)
       └─► US-006-ERR (Agent failure handling in display)
  ```

## THE_PROBLEM_CONTRACT
When users run `deviate run --all` in automated mode, they currently see only terse `console.print()` phase labels with no visibility into what the agent is doing, which tasks are complete, or what phase the orchestrator is in. Operators need a live-updating dashboard that exposes a task checklist with progress markers, a 5-line rolling buffer of agent stdout/stderr, and a current-phase status bar — all rendered via Rich's `Live` context manager (already a dependency). When stdout is not a TTY (piped, redirected, or CI), the display must degrade gracefully to plain JSONL event emission.

## SCOPE_BOUNDARIES
### Hard Inclusions
- `OrchestrationMonitor` class in `src/deviate/ui/monitor.py` that owns the Rich `Live` display lifecycle and accepts status events via a typed event API.
- Task rendering function in `src/deviate/ui/render.py` that formats:
  - A Rich `Table` with task ID, description, and status marker columns
  - A rolling agent output buffer section showing the last 5 lines
  - A status bar showing current phase (RED/GREEN/JUDGE/REFACTOR/COMPLETED/FAILED)
- Integration into `deviate run --all` (`src/deviate/cli/micro.py`) wiring agent subprocess stdout/stderr into the monitor in real-time.
- TTY detection: Rich `Live` display for interactive terminals; plain JSONL event emission for pipes, redirects, and CI.
- Event types for monitor state transitions: `task_started`, `task_completed`, `task_failed`, `agent_output`, `phase_change`, `pipeline_complete`.
- `--json` flag on `deviate run --all` that forces JSONL output regardless of TTY status.
- `src/deviate/ui/__init__.py` package init marking the subpackage as public API.

### Defensive Exclusions
- No TUI framework (Textual, blessed, curses) — Rich `Live` only.
- No file-watching daemon, background process, or persistent server — the display exists only for the duration of `deviate run --all`.
- No new dependencies beyond what is already declared in `pyproject.toml` (Rich is already a dependency).
- No modification to `spec.md`, `tasks.md`, `CLAUDE.md`, `AGENTS.md`, or non-`src/deviate/` paths as part of this change.
- No modification to the task execution engine in `micro.py` beyond wiring display events — the TDD cycle logic (`_run_tdd_cycle`, `_dispatch_task`, `_run_all`) is unchanged.
- No persistent logging or replay capability — the display is ephemeral.
- No concurrent task execution display (tasks run sequentially in `_run_all`).

## PERFORMANCE_CONSTRAINTS
- **`L_max <= 50ms`** for `OrchestrationMonitor.__init__` and display start (wall-clock from instantiation to first render).
- **`L_max <= 10ms`** per individual event ingestion (`push_event` or equivalent method call).
- **`L_max <= 200ms`** for full `deviate run --all` with 5 tasks including display rendering (monitor overhead only, excludes agent subprocess execution time).
- **`L_max <= 5ms`** per render cycle refresh (Rich `Live` update call).
- Display refresh rate must not exceed 10 Hz (100ms minimum between refreshes) to avoid excessive terminal I/O.
- JSONL fallback output must not buffer — each event is flushed immediately to stdout.

## MULTI_TIERED_VERIFICATION_TARGETS
- **Unit Tests (Monitor Model)**: `tests/test_ui/test_monitor.py` — validates `OrchestrationMonitor` state transitions, event ingestion, buffer management, and render triggers.
  - `test_monitor_updates_task_marker` — verify task markers update when receiving status events
  - `test_monitor_agent_output_buffer` — verify rolling 5-line buffer eviction behavior
  - `test_monitor_status_bar_reflects_phase` — verify status bar phase string matches latest event
  - `test_monitor_task_started_creates_row` — verify task rows appear on `task_started` event
  - `test_monitor_pipeline_complete_clears` — verify display cleanup on completion
- **Unit Tests (Render Functions)**: `tests/test_ui/test_render.py` — validates Rich table formatting, agent output rendering, and TTY detection.
  - `test_render_task_list` — verify Rich `Table` formatting from task records
  - `test_render_no_tty_fallback` — verify JSONL emission when not a TTY or `--json` flag active
  - `test_render_agent_buffer` — verify rolling buffer renders with newest-last ordering
  - `test_render_status_bar` — verify status bar text and styling
- **Integration Tests**: `tests/test_cli/test_micro.py::test_run_all_with_live_display` — validates full `deviate run --all` loop with mocked agent producing stdout/stderr and verifies monitor output.
- **Demonstration Path**:
  ```bash
  pytest tests/test_ui/ -v
  pytest tests/test_cli/test_micro.py::test_run_all_with_live_display -v
  ```

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-DISP: Live Display Lifecycle and Rich Integration
* **Upstream Requirement Traceability**: FR-ADHOC-001
* **Description**: The `OrchestrationMonitor` class manages the Rich `Live` display lifecycle: instantiation, context-manager entry/exit, and cleanup. The display starts when `deviate run --all` begins and terminates cleanly when all tasks complete or the pipeline is aborted.
* **Scenario — Display Starts on Pipeline Begin**:
  - **Given**: `deviate run --all` is executed in an interactive terminal with 5 pending tasks in the ledger.
  - **When**: The pipeline begins processing the first task.
  - **Then**: A Rich `Live` display is rendered showing a task table with 5 rows, status bar showing `"Running: RED → phase"`, and an empty agent output section. All within `L_max <= 50ms` of pipeline start.
* **Scenario — Display Terminates Cleanly on Completion**:
  - **Given**: The task pipeline completes successfully (all tasks reach `COMPLETED` status).
  - **When**: The pipeline exits the `_run_all` function.
  - **Then**: The Rich `Live` display is stopped, the terminal cursor is restored, and the final rendered state is printed to stdout before exit.
* **Scenario — Display Terminates on KeyboardInterrupt**:
  - **Given**: An active display is rendering during task execution.
  - **When**: The user presses Ctrl+C.
  - **Then**: The display shows `"INTERRUPTED"` in the status bar, the currently executing task marker changes to `[✗]`, the Live context manager exits cleanly, and the terminal is restored to a usable state without artifacts.

### US-002-TASK: Task List with Completion Markers
* **Upstream Requirement Traceability**: FR-ADHOC-001
* **Description**: The live display renders a task checklist where each task row shows a status marker, task ID, and description. Markers update in real-time as tasks progress through the TDD cycle.
* **Scenario — Pending Task Markers at Pipeline Start**:
  - **Given**: The pipeline has 3 pending tasks (`TSK-001-01`, `TSK-001-02`, `TSK-001-03`).
  - **When**: The display initializes.
  - **Then**: Each task row shows a `[ ]` pending marker, the task ID, and the description string from the ledger record.
* **Scenario — In-Progress Task Marker During Execution**:
  - **Given**: The pipeline is processing `TSK-001-01` through the RED phase.
  - **When**: The RED phase begins.
  - **Then**: The task row for `TSK-001-01` changes its marker from `[ ]` to `[/]`.
* **Scenario — Completed Task Marker After Phase**:
  - **Given**: Task `TSK-001-01` has completed the RED phase and the phase transition is recorded in the ledger.
  - **When**: The monitor receives the `task_completed` event for RED.
  - **Then**: The task row for `TSK-001-01` shows `[X]` for the completed phase column, and the display refreshes within one render cycle.
* **Scenario — Multiple Tasks, Sequential Markers**:
  - **Given**: 3 tasks are pending, and `TSK-001-01` has reached `COMPLETED` while `TSK-001-02` is in GREEN.
  - **When**: The display refreshes.
  - **Then**: `TSK-001-01` shows `[X]` (COMPLETED), `TSK-001-02` shows `[/]` (in GREEN), and `TSK-001-03` shows `[ ]` (PENDING).

### US-003-BUFF: Rolling Agent Output Buffer
* **Upstream Requirement Traceability**: FR-ADHOC-001
* **Description**: A section of the display shows the last 5 lines of agent stdout/stderr, updated in real-time as the agent emits output. Lines are truncated to fit the terminal width, newest lines appear at the bottom.
* **Scenario — Output Lines Accumulate in Buffer**:
  - **Given**: An agent subprocess is executing and emitting stdout lines.
  - **When**: The monitor receives 3 lines of agent output via `agent_output` events.
  - **Then**: The buffer section displays all 3 lines, each on its own row, with the oldest at the top and newest at the bottom.
* **Scenario — Buffer Eviction Beyond 5 Lines**:
  - **Given**: The buffer contains 5 lines of agent output.
  - **When**: A 6th line is emitted.
  - **Then**: The oldest line is evicted, the buffer now contains lines 2–6, and the display shows exactly 5 lines with the newest (line 6) at the bottom.
* **Scenario — Line Truncation to Terminal Width**:
  - **Given**: An agent emits a line longer than the current terminal width (e.g., 200 characters in an 80-char terminal).
  - **When**: The line is added to the buffer.
  - **Then**: The displayed line is truncated to terminal width with an ellipsis suffix (e.g., `"very long line..."`) to prevent horizontal scroll or layout breakage.
* **Scenario — Buffer Clear on Task Transition**:
  - **Given**: The buffer contains output from the previous task's agent.
  - **When**: A new task begins processing and the first `agent_output` event arrives for the new task.
  - **Then**: The buffer is cleared before appending the new task's output lines (previous task's output is not interleaved with new task output in the display).

### US-004-PHAS: Phase Status Bar
* **Upstream Requirement Traceability**: FR-ADHOC-001
* **Description**: The display includes a status bar section showing the current TDD phase of the executing task, the overall pipeline progress (task N of M), and the current task ID.
* **Scenario — Status Bar on Pipeline Start**:
  - **Given**: The pipeline begins with 5 total tasks.
  - **When**: The display initializes.
  - **Then**: The status bar shows `"Task 1 of 5"` and `"Phase: PENDING"`.
* **Scenario — Status Bar Reflects Phase Transitions**:
  - **Given**: Task 1 of 5 is currently executing the GREEN phase.
  - **When**: The monitor receives a `phase_change` event with `phase="GREEN"`.
  - **Then**: The status bar updates to show `"Task 1 of 5"` and `"Phase: GREEN"` within one render cycle.
* **Scenario — Status Bar on Task Completion**:
  - **Given**: Task 2 of 5 reaches `COMPLETED` status.
  - **When**: The pipeline advances to Task 3.
  - **Then**: The status bar updates to `"Task 3 of 5"` and `"Phase: PENDING"`, reflecting the new current task before any phase has started for it.
* **Scenario — Status Bar on Pipeline Finish**:
  - **Given**: All 5 tasks are complete.
  - **When**: The pipeline exits.
  - **Then**: The final status bar shows `"All 5 tasks complete"` and `"Phase: COMPLETED"`, then the display terminates.

### US-005-TTY: TTY Detection and JSONL Fallback
* **Upstream Requirement Traceability**: FR-ADHOC-001
* **Description**: When stdout is not a TTY (piped, redirected, or CI environment), the Rich `Live` display is suppressed and plain JSONL events are emitted to stdout instead. The `--json` flag forces JSONL output regardless of TTY status.
* **Scenario — JSONL Emission When Not a TTY**:
  - **Given**: `deviate run --all` is executed with stdout piped (e.g., `deviate run --all | tee output.log`).
  - **When**: The pipeline executes all phases for all tasks.
  - **Then**: Each monitor event (`task_started`, `task_completed`, `agent_output`, `phase_change`, `pipeline_complete`) is emitted as a single JSON line on stdout. No Rich formatting or ANSI escape codes are present in the output.
* **Scenario — JSONL Emission With `--json` Flag**:
  - **Given**: `deviate run --all --json` is executed in an interactive terminal.
  - **When**: The pipeline executes.
  - **Then**: Rich `Live` display is disabled. JSONL events are emitted to stdout exactly as in the non-TTY scenario.
* **Scenario — JSONL Event for `agent_output` Includes Metadata**:
  - **Given**: An agent emits a line `"Running tests..."` during the GREEN phase.
  - **When**: The JSONL event is emitted.
  - **Then**: The JSON object contains fields `event: "agent_output"`, `task_id`, `phase`, `line: "Running tests..."`, and a `timestamp` in ISO-8601 format.
* **Scenario — JSONL Event for `task_completed` Includes Status**:
  - **Given**: Task `TSK-001-01` completes the RED phase.
  - **When**: The `task_completed` event is emitted.
  - **Then**: The JSON object contains fields `event: "task_completed"`, `task_id: "TSK-001-01"`, `phase: "RED"`, `status: "completed"`, and a `timestamp`.
* **Scenario — JSONL Events Are Flushed Immediately**:
  - **Given**: A series of events are emitted during pipeline execution.
  - **When**: Each event is written to stdout.
  - **Then**: `sys.stdout.flush()` is called after each event line, ensuring no line-buffering delay in CI or pipe consumers.

### US-006-ERR: Agent Failure Handling in Display
* **Upstream Requirement Traceability**: FR-ADHOC-001
* **Description**: When an agent subprocess exits with a non-zero code (task failure), the monitor reflects the failure state in the task marker, preserves the failing agent's output in the buffer, and allows remaining tasks to continue processing.
* **Scenario — Task Failure Marker on Non-Zero Exit**:
  - **Given**: An agent subprocess for `TSK-001-02` exits with return code 1.
  - **When**: The monitor receives a `task_failed` event.
  - **Then**: The task marker for `TSK-001-02` changes to `[✗]`, the status bar shows `"FAILED"`, and the error reason (e.g., `"Agent returned non-zero exit code 1"`) is appended to the task description in the display.
* **Scenario — Failing Agent Output Preserved in Buffer**:
  - **Given**: An agent fails after emitting 3 lines of output (the last being an error trace).
  - **When**: The `task_failed` event is received.
  - **Then**: The buffer retains those 3 lines (not cleared), the error trace line is visible, and remaining output from subsequent task agents is appended to the buffer (line 4+ evicts oldest).
* **Scenario — Remaining Tasks Continue After Failure**:
  - **Given**: `TSK-001-02` has failed and is marked `[✗]` in the display.
  - **When**: The pipeline continues to `TSK-001-03`.
  - **Then**: The display advances to `TSK-001-03` (marker shows `[/]` for in-progress), the status bar updates to `"Task 3 of 5"`, and the pipeline processes normally. Failed task row remains visible with `[✗]`.
* **Scenario — Display on Complete Pipeline Failure**:
  - **Given**: All 3 tasks have failed.
  - **When**: The pipeline exits after exhausting all tasks.
  - **Then**: The display shows all 3 tasks with `[✗]` markers, the status bar shows `"3 failures"`, and the display terminates with non-zero exit code propagated.

## SYSTEM_STATUS_SUMMARY
| Parameter | Value |
|-----------|-------|
| STATUS | SPECIFIED |
| EPIC_SLUG | adhoc |
| BRANCH_NAME | feat/adhoc/001-streaming-pipeline-monitor |
| SPEC_PATH | specs/adhoc/001-streaming-pipeline-monitor/spec.md |
| ISSUE_ID | ISS-ADH-001 |
| NEXT_ACTION | Run post-script to validate, commit, and transition to TASKS phase |
