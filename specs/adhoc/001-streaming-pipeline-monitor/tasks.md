# Implementation Tasks: feat/adhoc/001-streaming-pipeline-monitor

## Phase 1: Monitor Core State Machine
**Goal**: Deliver the `OrchestrationMonitor` class with display lifecycle management, task marker state machine, and failure handling (covers US-001-DISP, US-002-TASK, US-006-ERR).

### Tasks

- TSK-001-01: Implement OrchestrationMonitor with State Machine, Task Markers, and Failure Handling
  - **Judge Feedback**: The next GREEN attempt must add:
    - **Judge Feedback**: 1. A render() method on OrchestrationMonitor that serves as a stub delegation
    - **Judge Feedback**:    point for Phase 2 render functions. It should accept no required args and
    - **Judge Feedback**:    can be a no-op or call a placeholder, but the method MUST exist so the
    - **Judge Feedback**:    integration layer (Phase 3) has a stable API to call. Example:
    - **Judge Feedback**:      def render(self) -> None:
    - **Judge Feedback**:          """Delegate to render functions. Stub for Phase 2 integration."""
    - **Judge Feedback**:          pass
    - **Judge Feedback**: 2. A 6th unit test — the acceptance criteria explicitly requires "6+ unit
    - **Judge Feedback**:    tests passing". Add a test for an edge case from the task details, e.g.,
    - **Judge Feedback**:    test_monitor_task_completed_without_started() asserting graceful creation
    - **Judge Feedback**:    when task_completed arrives without prior task_started.
    - **Judge Feedback**: 3. Extract a TaskStatus dataclass (or TypedDict/NamedTuple) to replace the
    - **Judge Feedback**:    raw dict[str, dict] internal storage. The refactor step is explicit:
    - **Judge Feedback**:    "Extract TaskStatus dataclass for type safety". Even a simple dataclass
    - **Judge Feedback**:    with fields: id, description, marker, phase, error_reason.
    - **Judge Feedback**: 4. Consider extracting _validate_event() for event type dispatch instead of
    - **Judge Feedback**:    the current if/elif chain.
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_ui/test_monitor.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/ui/__init__.py`
    - `src/deviate/ui/monitor.py`
    - `tests/test_ui/test_monitor.py`
  - **Rationale**: Creates the UI subpackage and the core `OrchestrationMonitor` class. `__init__.py` establishes the package boundary. `monitor.py` is the primary workstation for US-001-DISP (display lifecycle), US-002-TASK (task markers), and US-006-ERR (failure handling). `test_monitor.py` validates all three stories with Sociable_Unit tests against the state machine and event API.
  - **Details**:
    - **Red**: Write `test_monitor_display_starts_stopped()` asserting `not monitor.display_active` before `__enter__`.
    - **Red**: Write `test_monitor_updates_task_marker()` asserting task markers transition `[ ] → [/] → [X]` on `task_started`, `phase_change`, `task_completed` events.
    - **Red**: Write `test_monitor_task_started_creates_row()` asserting a new task row appears in internal state on `task_started` event.
    - **Red**: Write `test_monitor_pipeline_complete_clears()` asserting display cleanup and `display_active=False` after `pipeline_complete`.
    - **Red**: Write `test_monitor_task_failure_marker()` asserting `[✗]` marker and error reason capture on `task_failed` event.
    - **Red**: Write `test_monitor_keyboard_interrupt()` asserting `INTERRUPTED` status bar and task marker `[✗]` via `signal_keyboard_interrupt()` method.
    - **Green**: Implement `OrchestrationMonitor` class with `__init__(console, *, json_mode=False)`, `__enter__`, `__exit__`, `push_event(event_type, **data)`, and `signal_keyboard_interrupt()`. Internal state tracks tasks as `dict[str, dict]` with `marker`, `id`, `description`, `phase`, `error_reason`.
    - **Green**: Implement `MarkdownStatus` enum with `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED` and corresponding marker strings `[ ]`, `[/]`, `[X]`, `[✗]`.
    - **Green**: Implement event dispatch: `task_started` creates or updates task row, `phase_change` updates phase column, `task_completed` sets `COMPLETED`, `task_failed` sets `FAILED` with error reason. `pipeline_complete` triggers `__exit__` cleanup.
    - **Green**: Implement `render()` method that delegates to render functions (stub calls for Phase 2).
    - **Refactor**: Extract `TaskStatus` dataclass for type safety, extract event validation into `_validate_event()` method.
    - **Edge Cases**: Handle `task_started` for already-known task ID (idempotent update), handle `task_completed` without prior `task_started` (graceful creation), handle double `__exit__` call.
    - **Acceptance**: 6+ unit tests passing. All marker transitions verified. KeyboardInterrupt captured without exception leak.

---

## Phase 2: Render Functions with Buffer, Status Bar, and TTY Detection
**Goal**: Deliver the rendering layer including Rich `Table` task formatting, rolling 5-line agent output buffer, phase status bar, TTY detection, and JSONL event fallback (covers US-003-BUFF, US-004-PHAS, US-005-TTY).

### Tasks

- TSK-001-02: Implement Render Functions — Task Table, Agent Output Buffer, Status Bar, TTY Detection, JSONL Emitter
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_ui/test_render.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/ui/render.py`
    - `tests/test_ui/test_render.py`
  - **Rationale**: `render.py` is the sole rendering workstation for three user stories: US-003-BUFF (rolling buffer rendering), US-004-PHAS (status bar), and US-005-TTY (TTY detection + JSONL fallback). `test_render.py` validates all three. Keeping buffer, status bar, and TTY logic in one file ensures cohesive layout context (the display layout is a single Rich `Renderable` composition).
  - **Details**:
    - **Red**: Write `test_render_task_list()` asserting `build_task_table()` returns a Rich `Table` with columns `Marker`, `ID`, `Description` and rows matching input task data.
    - **Red**: Write `test_render_agent_buffer()` asserting `render_agent_buffer()` returns a `Panel` containing exactly N lines (N <= 5) with newest at bottom.
    - **Red**: Write `test_render_agent_buffer_eviction()` asserting adding 6 lines evicts the oldest, buffer contains exactly 5.
    - **Red**: Write `test_render_agent_buffer_truncation()` asserting lines exceeding terminal width are truncated with `…`.
    - **Red**: Write `test_render_status_bar()` asserting `render_status_bar(3, 5, "GREEN")` returns a string or Rich renderable containing `"Task 3 of 5"` and `"Phase: GREEN"`.
    - **Red**: Write `test_render_no_tty_fallback()` asserting `emit_jsonl(event_type, data)` writes a single JSON line to stdout when `sys.stdout.isatty()` is `False`.
    - **Red**: Write `test_render_jsonl_event_fields()` asserting emitted JSON contains keys `event`, `task_id`, `phase`, `line` (for agent_output), and `timestamp`.
    - **Red**: Write `test_render_jsonl_agent_output_event()` asserting `emit_jsonl("agent_output", {"task_id": "T1", "phase": "RED", "line": "test"})` produces valid JSON with correct field values.
    - **Green**: Implement `build_task_table(tasks: list[TaskStatus]) -> Table` creating Rich `Table` with columns `Marker`, `ID`, `Description`. Uses `Panel` wrapper if total elements > 1.
    - **Green**: Implement `render_agent_buffer() -> Panel` using `collections.deque(maxlen=5)` for rolling storage, returning a Rich `Panel` with `Syntax` or `Text` renderables. Each line is a `Text` truncated to `shutil.get_terminal_size().columns`.
    - **Green**: Implement `render_status_bar(current: int, total: int, phase: str) -> str` returning formatted string like `"Task 2 of 5 — Phase: GREEN"`.
    - **Green**: Implement `emit_jsonl(event: str, **fields) -> None` that constructs a `dict` with `event`, `timestamp` (ISO-8601), plus keyword fields, serializes to JSON, writes to `sys.stdout`, and calls `sys.stdout.flush()`.
    - **Green**: Implement `is_interactive() -> bool` using `os.isatty(sys.stdout.fileno())` and `os.environ.get("CI")` check.
    - **Green**: Implement `compose_display(tasks, buffer_lines, current, total, phase) -> Group` composing task table + buffer panel + status bar into a Rich `Group` renderable.
    - **Refactor**: Extract line truncation to `_truncate_line(line: str, width: int) -> str`, extract timestamp generation to `_now_iso()`.
    - **Edge Cases**: Empty task list (table with header row only), empty buffer (panel with `"(awaiting output)"` placeholder), zero-width terminal (fallback to 80 cols), CI env vars detected.
    - **Acceptance**: 8+ render unit tests passing. Buffer eviction and truncation verified. JSONL schema matches spec ATDD scenarios.

---

## Phase 3: Integration into `deviate run --all`
**Goal**: Wire the `OrchestrationMonitor` into the existing `_run_all` pipeline and wire agent subprocess output into the display (covers all US stories at integration level).

### Tasks

- TSK-001-03: Wire OrchestrationMonitor into `deviate run --all` with Agent Output Streaming and `--json` Flag
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_micro.py::test_run_all_with_live_display -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-001-02
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_cli/test_micro.py`
  - **Rationale**: `micro.py` is where `_run_all()` and `_invoke_agent()` live — the exact integration boundary where agent subprocess output is available and where the `run` Typer command accepts flags. `test_micro.py` already has orchestration tests; adding `test_run_all_with_live_display` validates the full vertical slice end-to-end with mocked agents. No changes to task execution logic (per spec defensive exclusion).
  - **Details**:
    - **Red**: Write `test_run_all_with_live_display()` using `runner.invoke(cli, ["run", "--all"])` with mocked `_run_pytest` and mocked agent subprocess that emits 5 stdout lines. Assert `Live` render is active during execution and exits cleanly. Mock `sys.stdout.isatty()` to return `True`.
    - **Red**: Write `test_run_all_json_flag()` using `runner.invoke(cli, ["run", "--all", "--json"])`. Assert `Live` is NOT entered, JSONL lines are emitted to stdout. Mock `_run_pytest` and agent output.
    - **Red**: Write `test_run_all_non_tty()` piping stdout. Assert JSONL events emitted without `--json` flag.
    - **Red**: Write `test_run_all_interrupt()` sending `SIGINT` during execution. Assert `INTERRUPTED` status in JSONL or display.
    - **Green**: In `_run_all()`, instantiate `OrchestrationMonitor` before the task loop, using `console` from `micro.py` and `--json` CLI flag state. Wrap the task processing in the monitor's context manager (`with monitor:`).
    - **Green**: Emit `task_started` event at the beginning of each task dispatch, `phase_change` at each phase transition, `task_completed` on successful completion, `task_failed` on `PhaseFailedError`.
    - **Green**: Pass a stream-capture callback to `_invoke_agent()` (or wrap the existing output handler) that forwards each stdout/stderr line to `monitor.push_event("agent_output", task_id=..., phase=..., line=...)`.
    - **Green**: Add `--json` flag to the `run` Typer command. Pass it through to `_run_all()` as `json_mode: bool`. When `True`, set `monitor.json_mode = True` and skip Rich `Live` init.
    - **Green**: Handle `KeyboardInterrupt` in `_run_all()` by calling `monitor.signal_keyboard_interrupt()` and re-raising.
    - **Green**: Wire `_run_all` to use `is_interactive()` from render module for automatic TTY detection.
    - **Refactor**: Extract display lifecycle from `_run_all()` into `_with_live_display(monitor, tasks, ...)` helper to reduce `_run_all` complexity.
    - **Edge Cases**: Zero pending tasks (display shows empty table + exits immediately), single task (display shows 1 row), all tasks fail (display shows all `[✗]` + non-zero exit), `--json` + pipe stdout (single JSONL emission, no double output).
    - **Acceptance**: Integration test passes with mocked agent. Performance `L_max <= 200ms` for 5-task run overhead. KeyboardInterrupt display tests pass.

---

## Phase 4: End-to-End Verification
**Goal**: Validate the complete streaming pipeline monitor works end-to-end with real agent output behavior.

### Tasks

- TSK-001-04: E2E — Full Pipeline Monitor Verification with Real Agent Output
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_micro.py::test_run_all_with_live_display_agent_output -v`
  - **Estimated Time**: 30 minutes
  - **Dependency**: TSK-001-03
  - **Files**:
    - `tests/test_cli/test_micro.py`
    - `specs/adhoc/001-streaming-pipeline-monitor/spec.md`
  - **Rationale**: Final validation that all pieces work together. The E2E test exercises the full `_run_all` → `OrchestrationMonitor` → render → agent output → JSONL fallback chain with a simulated multi-task run. `spec.md` is read-only reference for assertions. No production code changes.
  - **Details**:
    - **Red**: Write `test_run_all_with_live_display_agent_output()` using `runner.invoke()` with a multi-task scenario (3 tasks, RED→GREEN→REFACTOR each). Mock `_run_pytest` and agent subprocess to emit realistic output lines. Assert: (1) all 3 tasks complete, (2) display emits expected JSONL events in correct order, (3) no crash on exit.
    - **Red**: Write test asserting agent output lines appear in JSONL `agent_output` events in FIFO order matching agent emission.
    - **Red**: Write test with failing task (mock agent exit code 1). Assert `task_failed` event emitted with `[✗]` marker, remaining tasks continue, final status bar shows failure count.
    - **Green**: Ensure integration code from TSK-001-03 and modules from TSK-001-01 and TSK-001-02 work together correctly.
    - **Refactor**: No refactor for E2E.
    - **Edge Cases**: Mixed pass/fail scenario, empty agent output, agent output exactly 5 lines (no eviction), agent output with very long lines.
    - **Acceptance**: All integration + unit tests pass. E2E test validates multi-task lifecycle end-to-end.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (Monitor Core) -> Phase 2 (Render Functions) -> Phase 3 (Integration) -> Phase 4 (E2E)

**Critical Dependency Chains**:
- TSK-001-01 (Monitor state machine) must precede TSK-001-02 (Render depends on TaskStatus type)
- TSK-001-02 (Render) must precede TSK-001-03 (Integration imports both)
- TSK-001-03 (Integration) must precede TSK-001-04 (E2E validates full stack)

**Risk Hotspots**:
- `OrchestrationMonitor` state machine must exactly match event types expected by render layer — any mismatch between the internal `TaskStatus` dataclass in `monitor.py` and the `build_task_table()` signature in `render.py` will cause integration test failures.
- Rich `Live` context manager has subtle interaction with `KeyboardInterrupt` — the `__exit__` must flush the display even on exception paths.
- Performance constraint `L_max <= 200ms` for 5-task run may be tight — monitor overhead per event must stay under `10ms`.

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` (touched by TSK-001-03, may conflict with concurrent issues)
- `tests/test_cli/test_micro.py` (extended by TSK-001-03 and TSK-001-04)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.
- **Performance Mocking**: Tests that invoke `_run_all` (or any command calling `_run_pytest`) MUST mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value. This prevents tests from triggering the full pytest suite as a subprocess (~5s per invocation).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```

**Consequence**: Every per-task Git Isolation block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that runs git commands, that function **must** accept `repo_path`.
