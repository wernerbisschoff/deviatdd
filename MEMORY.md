# MEMORY

## 2026-06-13: GREEN timeout recovery + pre-commit fix

### Completed changes to `src/deviate/cli/micro.py` (on `main`)

| Change | What | Status |
|--------|------|--------|
| `_run_pytest` in `green_post` | Already in main, confirmed no-op | ✅ Done |
| `_commit_phase` | Detects commit failure (was silently `check=False` → `return True`) | ✅ Done |
| `green_post` message | `YELLOW_TRIGGERED (nothing to commit or commit failed)` | ✅ Done |
| `_invoke_agent` return type | `HandoverManifest \| None` → `tuple[HandoverManifest \| None, str]` | ✅ Done |
| 5 callers (`_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`, `_run_yellow_phase`) | Updated to unpack `manifest, _ = ...` | ✅ Done |
| `_summarize_timeout_context` | Calls agent backend (30s timeout) to condense partial stdout → ~200 words | ✅ Done |
| `_run_green_phase` timeout wiring | On `AgentTimeoutError`: summarize → store as `session.train_feedback` → raise `PhaseFailedError` → retry cycle picks it up via existing mechanism | ✅ Done |

### Worktree fixes (`feat/002-deviatdd-gap-analysis/002-context-pipeline`)

- `tests/test_cli/test_context.py:test_context_post_commit` — `_git_env()` helper + `env=_git_env()` on `subprocess.run`. Fixes `GIT_DIR` env leak.

### RESOLVED: 11 tests fail due to missing agent mock

**Failing tests:** 8 in `test_micro/test_orchestration.py` + 5 in `test_micro/test_run.py`

**Root cause:**
Commit 6a2e436 changed `_invoke_agent` to raise `PhaseFailedError` when the agent returns `None` (instead of silently continuing). In the test environment, `opencode` can't run in temp directories, so `_invoke_agent` returns `None`, causing all TDD orchestration tests to fail with:
```
PhaseFailedError: RED phase agent error for TSK-XXX-XX: agent returned no manifest
```

**Why the error message was misleading:**
The CliRunner wrapped the exception as `ValueError('too many values to unpack (expected 2)')` during error formatting, not from actual tuple unpacking. The real exception was `PhaseFailedError`.

**Solution:**
Added `@patch("deviate.cli.micro._invoke_agent")` decorator to 13 tests that invoke the TDD cycle. The mock returns a valid `HandoverManifest` with `status="SUCCESS"`, allowing tests to verify orchestration logic without requiring a real agent.

**Files changed:**
- `tests/test_micro/test_orchestration.py`: Added `_mock_invoke_agent` helper + 8 decorators
- `tests/test_micro/test_run.py`: Added `_mock_invoke_agent` helper + 5 decorators
- `src/deviate/cli/micro.py`: Removed unused `task_marker` variable (lint fix)

**Lesson learned:**
When tests that previously passed start failing after a change that makes error handling stricter, the tests likely need mocks for external dependencies (like agent backends) that can't run in the test environment.
