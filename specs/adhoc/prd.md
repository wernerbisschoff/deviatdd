# ADHOC_REQUIREMENTS_LEDGER
> Append-only. Managed automatically by /deviate-adhoc. Do not edit manually.

## FR-ADHOC-001: Streaming Pipeline Monitor with Task Status Display

- **Description**: Implement a live-updating task status dashboard that renders during automated `deviate run --all` execution, showing task list with completion markers, a 5-line rolling agent output buffer, and current phase/status indicator.
- **Preconditions**: At least one task exists in `specs/**/tasks.jsonl`. Rich is installed (already a dependency). Terminal is interactive (TTY) or `--json` fallback is active.
- **Inputs/Outputs**: Input: JSONL task ledger, agent subprocess stdout/stderr. Output: Rich `Live` display with formatted task table, agent output buffer, and status bar.

### Acceptance Criteria
1. **AC-ADHOC-001-01**: Given `deviate run --all` with 5 tasks, When tasks are processed sequentially through RED→GREEN→REFACTOR, Then the display shows `[X]` for completed, `[/]` for in-progress, `[ ]` for pending tasks, updated in real-time.
2. **AC-ADHOC-001-02**: Given an agent is executing a phase, When the agent emits stdout/stderr lines, Then the last 5 lines are displayed in a rolling buffer section below the task list, each truncated to one terminal-width line, with newest at the bottom.
3. **AC-ADHOC-001-03**: Given the agent completes a phase transition, When the task record is updated in the ledger, Then the display refreshes the task marker and the status bar reflects the new phase (RED→GREEN→REFACTOR→COMPLETED) within one render cycle.
4. **AC-ADHOC-001-04**: Given stdout is not a TTY (piped or redirected), When `deviate run --all` executes, Then the Live display is disabled and plain-status JSONL events are emitted instead.
5. **AC-ADHOC-001-05**: Given the agent subprocess exits with a non-zero code, When the failure is detected, Then the task marker changes to `[✗]` with the error reason appended, the agent output buffer preserves the failing output, and remaining tasks continue processing.
