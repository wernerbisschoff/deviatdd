When running `deviate run --all`, users previously saw only terse phase labels with no task progress or agent output visibility. This PR adds a live-updating Rich `Live` dashboard that displays a task checklist with completion markers, a 5-line rolling buffer of agent stdout/stderr, and a current-phase status bar — with graceful JSONL fallback for non-TTY environments.

**UI subpackage**: Added `src/deviate/ui/` with `OrchestrationMonitor` (display lifecycle, task state machine, event ingestion), `render.py` (Rich table formatting, buffer management, status bar, TTY detection, JSONL emitter), and package init.

**Integration**: Wired the monitor into `deviate run --all` (`src/deviate/cli/micro.py`) with agent subprocess output streaming, `--json` flag, `phase_change` events, and `KeyboardInterrupt` handling.

**Tests**: Unit tests for monitor state machine (6+ tests) and render functions (8+ tests), plus integration tests for the full `_run_all` loop with mocked agents.
