# Implementation Tasks: feat/adhoc/002-aider-agent-backend-integration

## Phase 1: AiderConfig Model & AgentBackend Implementation
**Goal**: Add AiderConfig Pydantic model, extend AgentConfig to support the new backend, and implement the full AiderBackend class with invocation, parsing, context injection, and post-guard.

### Tasks

- TSK-002-01: Add AiderConfig model and extend AgentConfig wiring
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_core/test_agent.py -v -k "aider_config or aider_model or agent_config_aider" tests/test_state/test_config.py -v -k "aider"`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/test_core/test_agent.py`
  - **Rationale**: US-002 requires AiderConfig Pydantic model with all fields (model, auto_commits, suggest_shell_commands, yes_mode, read_files, extra="forbid"). It also requires extending `AgentConfig.backend` Literal to include "aider" and adding `AgentConfig.aider` field. These changes are in `config.py` — the agent backend code in `agent.py` depends on them being present.
  - **Details**:
    - **Implementation**: Add `AiderConfig` Pydantic model with fields: `model: str = "claude-sonnet-4-20250514"`, `auto_commits: bool = False`, `suggest_shell_commands: bool = False`, `yes_mode: bool = True`, `read_files: list[str] = Field(default_factory=...)`, `extra = "forbid"`.
    - **Implementation**: Extend `AgentConfig.backend` Literal from `Literal["opencode", "claude", "droid"]` to `Literal["opencode", "claude", "droid", "aider"]`.
    - **Implementation**: Add `AgentConfig.aider: AiderConfig = Field(default_factory=AiderConfig)` field to `AgentConfig`.
    - **Implementation**: Add regression tests for AiderConfig defaults, extra field rejection, TOML round-trip, AgentConfig backend="aider" without sub-config (defaults applied), and nested DeviateConfig TOML serialization.
    - **Refactor**: Ensure AiderConfig defines `model_config = {"extra": "forbid"}` to prevent silent field injection.
    - **Acceptance**: `AiderConfig` validates, serializes/deserializes, rejects extra fields, and nests correctly under `AgentConfig.aider` in `DeviateConfig`. The Literal `"aider"` is accepted for `AgentConfig.backend`.

- TSK-002-02: Implement full AiderBackend class with invocation, parsing, context injection, and post-guard
  - **Judge Feedback**: Fix the following issues in order:
    - **Judge Feedback**: 
    - **Judge Feedback**: 1. **Restore AiderParseError for malformed output (US-003-AIDER-PARSE AC4)**: 
    - **Judge Feedback**:    parse_output() must raise AiderParseError when output is empty or unparseable per spec. 
    - **Judge Feedback**:    In invoke(), wrap self.parse_output() in try/except AiderParseError → instead of propagating 
    - **Judge Feedback**:    the exception, return a HandoverManifest with status="PASS", verification_result="UNKNOWN" 
    - **Judge Feedback**:    so the pipeline doesn't hard-abort and falls through to the post-guard.
    - **Judge Feedback**: 
    - **Judge Feedback**: 2. **Add verification_result="FAIL" on parse failure (US-003-AIDER-PARSE AC2)**:
    - **Judge Feedback**:    When "Tests:" and "failed" are detected, return HandoverManifest with 
    - **Judge Feedback**:    verification_result="FAIL" alongside the existing status="FAIL" and error_details.
    - **Judge Feedback**: 
    - **Judge Feedback**: 3. **Use self.config.timeout instead of hardcoded 180 (US-001-AIDER-BACKEND)**:
    - **Judge Feedback**:    The timeout in invoke() should be self.config.timeout (default 600 from AgentConfig), 
    - **Judge Feedback**:    not a hardcoded 180. Pass effective_timeout to both subprocess.run calls and the 
    - **Judge Feedback**:    AgentTimeoutError message.
    - **Judge Feedback**: 
    - **Judge Feedback**: 4. **Fix test_aider_invoke_timeout_retry**:
    - **Judge Feedback**:    The test mocks subprocess.run with only 2 side_effect elements, but invoke() calls 
    - **Judge Feedback**:    subprocess.run 3 times (aider, retry-aider, post-guard). The test needs a 3rd element 
    - **Judge Feedback**:    for the guard result (MagicMock with returncode=0, stdout="1 passed"), and 
    - **Judge Feedback**:    call_count assertion needs updating to 3.
    - **Judge Feedback**: 
    - **Judge Feedback**: 5. **Ensure test_aider_output_parse_malformed passes**:
    - **Judge Feedback**:    After fixing #1, this existing test (from TSK-002-01) will pass again.
    - **Judge Feedback**: 
    - **Judge Feedback**: Verification command: mise run test -k "TestAiderBackend" -v
  - **Judge Feedback**: The AiderBackend class correctly handles invocation, constitution checks, post-guard,
    - **Judge Feedback**: and AiderParseError fallthrough. However, the following spec requirements were missed:
    - **Judge Feedback**: 
    - **Judge Feedback**: 1. **US-003-AC2 — error_details in FAIL case**:
    - **Judge Feedback**:    In `AiderBackend.parse_output()`, when `status == "FAIL"`, the HandoverManifest
    - **Judge Feedback**:    MUST include `error_details` with the failure context. Currently only `status`,
    - **Judge Feedback**:    `verification_result`, and `files_touched` are returned. Add extraction of error
    - **Judge Feedback**:    context (e.g., failing test names, error messages) from the stdout and pass it
    - **Judge Feedback**:    as `error_details`.
    - **Judge Feedback**: 
    - **Judge Feedback**: 2. **Output parsing — "N tests passed" regex**:
    - **Judge Feedback**:    The spec requires parsing for `"N tests passed"` (e.g., "3 tests passed",
    - **Judge Feedback**:    "10 tests passed"). Currently only `"All tests passed"` is matched. Add a
    - **Judge Feedback**:    regex pattern for `r"\d+\s+tests?\s+passed"` and treat it as PASS/PASS.
    - **Judge Feedback**: 
    - **Judge Feedback**: 3. **Timeout retry**:
    - **Judge Feedback**:    The spec requires "Invoke via subprocess.Popen() with configured timeout and
    - **Judge Feedback**:    timeout retry." The current implementation uses `subprocess.run()` with a
    - **Judge Feedback**:    timeout parameter but does NOT catch `subprocess.TimeoutExpired` and retry.
    - **Judge Feedback**:    Wrap the subprocess.run() call to catch TimeoutExpired, sleep 30s, and retry
    - **Judge Feedback**:    once (matching the parent class pattern).
    - **Judge Feedback**: 
    - **Judge Feedback**: 4. **Error messages and stack traces**:
    - **Judge Feedback**:    The spec requires parsing aider output for "error messages and stack traces."
    - **Judge Feedback**:    Currently `parse_output()` only extracts test status and file paths. Extract
    - **Judge Feedback**:    error details from aider's chat output and include them in the HandoverManifest
    - **Judge Feedback**:    (either via `error_details` or `rationale` field).
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_agent.py -v -k "aider"`
  - **Estimated Time**: 90 minutes
  - **Dependency**: TSK-002-01
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/test_core/test_agent.py`
  - **Rationale**: US-001 (AC 1-6) requires AiderBackend invocation with all flag variants, AIDER_NOT_FOUND handling, and flag building from AiderConfig. US-003 (AC 1-4) requires output parsing from aider chat-style output to HandoverManifest. US-004 (AC 1-4) requires constitution/CLAUDE.md injection via --read flags with abort on missing constitution. US-005 (AC 1-3) requires post-invocation mise run test guard. All these are implemented in `src/deviate/core/agent.py` — the single authoritative location for agent backend abstraction from ISS-001-004.
  - **Details**:
    - **Red**: Write `test_aider_backend_invocation_default_flags()` — mock subprocess.Popen, assert the command list starts with `["aider", "--message", ...]` and includes `--yes`, `--no-suggest-shell-commands`, `--no-auto-commits`, `--model claude-sonnet-4-20250514`.
    - **Red**: Write `test_aider_backend_custom_model()` — assert `AiderConfig(model="deepseek")` produces `--model deepseek`.
    - **Red**: Write `test_aider_backend_auto_commits_true_omits_flag()` — assert `AiderConfig(auto_commits=True)` omits `--no-auto-commits`.
    - **Red**: Write `test_aider_backend_not_found()` — mock `subprocess.Popen` to raise `FileNotFoundError`, assert `AIDER_NOT_FOUND` error raised.
    - **Red**: Write `test_aider_backend_context_read_both_exist()` — assert `--read specs/constitution.md --read CLAUDE.md` in args when both files exist.
    - **Red**: Write `test_aider_backend_context_constitution_missing_aborts()` — assert `CONSTITUTION_MISSING` error when constitution is absent.
    - **Red**: Write `test_aider_backend_context_claude_missing_skips()` — assert no `--read CLAUDE.md` when file missing.
    - **Red**: Write `test_aider_output_parse_all_tests_passed()` — create sample aider stdout with "All tests passed" and file paths, assert `HandoverManifest(status="PASS", ...)` is returned.
    - **Red**: Write `test_aider_output_parse_tests_failed()` — create sample with "1 failed" / "FAILED", assert `HandoverManifest(status="FAIL", ...)` with `error_details` containing failure context.
    - **Red**: Write `test_aider_output_parse_ambiguous()` — create sample without pass/fail indicators, assert optimistic `status="PASS"` with `verification_result="UNKNOWN"`.
    - **Red**: Write `test_aider_output_parse_malformed()` — create unparseable output, assert `AIDER_PARSE_ERROR` raised with raw output in message.
    - **Red**: Write `test_aider_post_guard_runs_mise_check()` — mock `subprocess.run` for aider success with "All tests passed", assert `mise run test` is called afterwards.
    - **Red**: Write `test_aider_post_guard_catches_false_positive()` — mock aider success output but mise run test returning non-zero, assert phase marked failed with `POST_GUARD_FAILED`.
    - **Red**: Write `test_aider_nonzero_exit_aborts_immediately()` — mock aider with returncode=1, assert abort without post-guard.
    - **Green**: Add `"aider": "aider"` to `BACKEND_COMMANDS` dict in `agent.py`.
    - **Green**: Implement `_build_aider_command(prompt: str, aider_cfg: AiderConfig, repo_root: Path) -> list[str]` in `agent.py` — builds args list with conditional flags based on config, validates constitution path existence (aborts if missing), adds `--read` for constitution and CLAUDE.md as applicable.
    - **Green**: Override `invoke()` in `AiderBackend` — use `subprocess.run(args + [prompt])` with timeout. **MUST catch `subprocess.TimeoutExpired` and retry once after 30s backoff** (matching parent class pattern).
    - **Green**: Implement `parse_aider_output(stdout: str) -> dict` — regex search for "All tests passed", **`r"\d+\s+tests?\s+passed"`** (for "N tests passed"), "N failed", "FAILED". Parse file paths from aider log lines. **MUST extract error messages and stack traces from failing output.** Return structured dict with `status`, `files_touched`, `verification_result`, `error_details`.
    - **Green**: Implement `_run_post_guard() -> bool` — runs `subprocess.run(["mise", "run", "test"])`, returns True if exit 0.
    - **Refactor**: Extract `_build_aider_flag_list()` and `_resolve_context_read_files()` helpers for testability. Align AiderBackend with existing error hierarchy (AgentSubprocessError, AgentTimeoutError, AgentBinaryNotFoundError).
    - **Edge Cases**: Empty aider output (treat as ambiguous parse). Aider exits 0 but empty stdout (post-guard provides verification). Unicode in aider output. Very long output (>100k chars).
    - **Acceptance**: All AiderBackend methods tested. Invocation builds correct flag combinations from config. Output parsing handles success, failure, ambiguous, and malformed cases. Post-guard runs unconditionally after successful aider exit. Missing constitution is a hard abort.

- TSK-002-03: Aider backend integration test with full pipeline wiring
  - **Judge Feedback**: TSK-002-03 violated the TDD cycle in two ways:
    - **Judge Feedback**: 
    - **Judge Feedback**: 1. PRE-COMMITTED TESTS: The file tests/test_integration/test_aider_backend.py was committed
    - **Judge Feedback**:    in commit 26b3f42 BEFORE the RED phase (19368f2). Red-phase commits MUST contain only
    - **Judge Feedback**:    failing tests — the test file must be committed as part of the RED phase, not before it.
    - **Judge Feedback**: 
    - **Judge Feedback**: 2. EMPTY GREEN: The GREEN commit (f8e0a4c) contains zero source/implementation changes.
    - **Judge Feedback**:    The GREEN phase MUST produce code (in src/ or tests/) that makes the RED-phase test pass.
    - **Judge Feedback**:    A GREEN commit that only updates tasks.jsonl is a no-op — it does not advance the
    - **Judge Feedback**:    implementation state.
    - **Judge Feedback**: 
    - **Judge Feedback**: For the next GREEN attempt:
    - **Judge Feedback**: - Ensure the RED phase creates a minimal failing test first (e.g., asserting that
    - **Judge Feedback**:   AiderBackend.invoke() returns a HandoverManifest — the test should fail because
    - **Judge Feedback**:   the method doesn't exist yet, or returns None).
    - **Judge Feedback**: - The GREEN phase must then implement the AiderBackend code that makes that test pass.
    - **Judge Feedback**: - Do NOT pre-commit test files outside the RED/GREEN cycle.
    - **Judge Feedback**: - Verify: `git log` should show RED commit introducing failing test, then GREEN commit
    - **Judge Feedback**:   introducing impl. Both commits should touch src/ or tests/, not just tasks.jsonl.
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_integration/test_aider_backend.py -v`
  - **Estimated Time**: 30 minutes
  - **Dependency**: TSK-002-02
  - **Files**:
    - `tests/test_integration/test_aider_backend.py`
  - **Rationale**: Integration tests validate the full aider backend lifecycle end-to-end — config loading, subprocess invocation, output parsing, and post-guard running. The spec.md's MULTI_TIERED_VERIFICATION_TARGETS section requires integration tests in this specific file.
  - **Details**:
    - **Implementation**: Write `test_aider_backend_integration_invoke()` — sets up `.deviate/config.toml` with `backend="aider"`, loads `DeviateConfig`, creates `AiderBackend`, mocks subprocess to return sample aider output, asserts `HandoverManifest` is returned with correct status and files_touched.
    - **Implementation**: Write `test_aider_backend_integration_post_guard()` — similar setup but mocks aider success, verifies `subprocess.run` is called for `mise run test` after aider invocation.
    - **Implementation**: Write `test_aider_backend_integration_not_found()` — sets up config, mocks subprocess missing, asserts `AIDER_NOT_FOUND` is raised.
    - **Implementation**: Write `test_aider_backend_integration_constitution_missing()` — removes constitution.md, asserts `CONSTITUTION_MISSING` error before any subprocess call.
    - **Refactor**: Use existing `tmp_git_repo` fixture for git isolation. Mock `subprocess.Popen`/`subprocess.run` for all external calls.
    - **Acceptance**: Integration tests run without real aider binary. All external calls are mocked. Tests validate the full AiderBackend lifecycle.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (Dependency order)

**Critical Dependency Chains**:
- TSK-002-01 (Config model) must precede TSK-002-02 (AiderBackend) — the backend code imports AiderConfig
- TSK-002-02 (AiderBackend) must precede TSK-002-03 (Integration) — integration tests exercise AiderBackend

**Risk Hotspots**:
- Aider uses `--message` (not stdin pipe) — the existing `_invoke_blocking`/`_invoke_streaming` pattern in agent.py uses stdin. AiderBackend needs a different invocation pathway (`subprocess.run` with `args + [prompt]` instead of `Popen` with `stdin.write`).
- Aider output format is chat-style and variable — parsing regex must be resilient to output format changes across aider versions.
- The post-guard runs `mise run test` which invokes the full pytest suite — ensure integration tests mock this to avoid 5s+ test execution during TDD cycles.

**Merge Conflict Boundaries**:
- `src/deviate/core/agent.py` — touched by TSK-002-02 only (adds AiderBackend class, BACKEND_COMMANDS entry)
- `src/deviate/state/config.py` — touched by TSK-002-01 only (adds AiderConfig, extends AgentConfig)
- `tests/test_core/test_agent.py` — touched by TSK-002-01 and TSK-002-02 (low conflict risk — TSK-002-01 adds config tests, TSK-002-02 adds invocation/parsing tests)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Mock Subprocess Calls**: All tests that invoke aider MUST mock `subprocess.Popen` or `subprocess.run` to prevent real binary execution. Use:
  ```python
  from unittest.mock import patch, MagicMock
  mock_run = patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="All tests passed", stderr=""))
  ```
- **Mock `mise run test`**: Post-guard tests MUST mock the `mise run test` subprocess call to avoid triggering the full pytest suite. Use `patch("subprocess.run")` with appropriate side_effect.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.
