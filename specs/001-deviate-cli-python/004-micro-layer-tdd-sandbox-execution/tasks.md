# Implementation Tasks: feat/001-deviate-cli-python/004-micro-layer-tdd-sandbox-execution

## Phase 1: Core Infrastructure
**Goal**: Establish the foundational components — agent backend abstraction, Tamper Guard, and slim prompt templates — that all micro-layer phases depend on.

### Tasks

- [x] T001: Agent backend with heredoc-pipe subprocess invocation, YAML handover parsing, timeout/retry, and AgentConfig model
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_agent.py -v`
  - **Estimated Time**: 75 minutes
  - **Files**:
    - `src/deviate/core/agent.py`
    - `src/deviate/state/config.py`
    - `tests/test_core/test_agent.py`
  - **Rationale**: US-004-1 requires an `AgentBackend` class with heredoc-pipe subprocess invocation, YAML manifest parsing, configurable timeout with retry-once-30s-backoff, and structured error handling (AgentTimeoutError, AgentSubprocessError, MalformedHandoverManifestError). US-004-10 requires the `AgentConfig` Pydantic model (backend, timeout fields) within `DeviateConfig` and a `--agent` CLI override flag. Both stories tie to FR-004-AGENT.
  - **Details**:
    - **Red**: Write `test_agent_successful_invocation` — mock subprocess to return stdout with valid YAML handover manifest, assert `AgentBackend.invoke()` returns parsed `HandoverManifest` with `phase`, `status`, `test_file`, `verification_command` fields. Write `test_agent_timeout_retry` — mock subprocess to sleep past timeout, assert first call raises `AgentTimeoutError`, 30s backoff occurs, retry fires; second timeout raises final `AgentTimeoutError`. Write `test_agent_malformed_yaml` — mock subprocess to return non-YAML output, assert `MalformedHandoverManifestError` with diagnostic. Write `test_agent_nonzero_exit` — mock exit code 1 with stderr, assert `AgentSubprocessError` captures message. Write `test_agent_backend_parses_yellow_handover` — mock YAML containing `yellow_trigger: true`, assert the manifest flags yellow condition.
    - **Green**: Implement `AgentBackend` class in `src/deviate/core/agent.py` with `invoke(prompt: str, backend: str | None = None, timeout: int | None = None) -> HandoverManifest`. Use `subprocess.Popen` with heredoc pipe (`echo "$PROMPT" | <agent_cmd>`). Parse stdout with `yaml.safe_load`. Add retry-once logic: on `AgentTimeoutError`, wait 30s (`time.sleep(30)`) then retry; second failure propagates. Implement `AgentConfig` model in `src/deviate/state/config.py` extending `DeviateConfig` with `backend: Literal["opencode", "claude", "droid"] = "opencode"` and `timeout: int = Field(default=600, gt=0)`. Wire `--agent` flag in `micro.py` to override config.
    - **Refactor**: Extract YAML schema validation into `HandoverManifest` Pydantic model. Centralize backend command mapping in a `BACKEND_COMMANDS: dict[str, str]` constant. Add type narrowing for backends.
    - **Edge Cases**: Handle `FileNotFoundError` when agent command is not on PATH (surface `AgentBinaryNotFoundError`). Handle empty stdout (raise `EmptyOutputError`). Handle YAML with missing required keys (raise `MalformedHandoverManifestError` with key list).
    - **Acceptance**: `AgentBackend` can invoke opencode, claude, and droid via heredoc. Timeout applies per backend. YAML manifest is parsed into typed model. Yellow handover trigger is detected. All scenarios from US-004-1 and US-004-10 pass.

- [x] T002: Tamper Guard — git diff evaluation and git restore rollback
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_core/test_tamper.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/tamper.py`
    - `tests/test_core/test_tamper.py`
  - **Rationale**: US-004-4 (FR-004-TAMPER) requires Tamper Guard to evaluate `git diff --name-only` after each agent invocation and reject unauthorized modifications to `tests/`, `specs/`, or config files. US-004-4 Scenario 4.2 requires detection and rollback; Scenario 4.4 requires pass-through for authorized changes. This is a foundational safety component that all GREEN/JUDGE phases depend on.
  - **Details**:
    - **Red**: Write `test_tamper_detects_test_modification` — create a tmp git repo, commit a test file, write unauthorized content to it via Python, call `TamperGuard.evaluate()`, assert `TAMPER_DETECTED` is returned and the original file content is restored. Write `test_tamper_passes_src_only_changes` — commit a test and src file, modify only the src file, call `TamperGuard.evaluate()`, assert `TAMPER_PASS` and file content is NOT restored. Write `test_tamper_detects_spec_modification` — modify a `specs/` file, assert detection. Write `test_tamper_detects_config_modification` — modify `.deviate/config.toml`, assert detection. Write `test_tamper_ignores_expected_red_test_creation` — assert test file creation (not modification) in RED context passes. Write `test_tamper_accepts_yellow_approved_changes` — pass an approval manifest, assert modification passes.
    - **Green**: Implement `TamperGuard` class with `evaluate(context: TamperContext) -> TamperVerdict`. Use `git diff --name-only` to get changed files (accept `repo_path` param defaulting to `Path.cwd()`). Compare against allow-list: RED phase allows test file creation; GREEN phase allows src-only changes unless YELLOW-approved manifest is provided. If violation: `git restore <file>` and return `TAMPER_DETECTED`. Context enum: `RED_TEST_CREATION`, `GREEN_IMPLEMENTATION`, `YELLOW_AMENDMENT`. Expose `check(repo_path=None, context=..., approved_mods=None)`.
    - **Refactor**: Extract file category matching into `_is_test_file()`, `_is_spec_file()`, `_is_config_file()` predicates. Replace string `startswith` with `PurePath` pattern matching.
    - **Edge Cases**: Handle empty diff (no changes) as clean pass. Handle binary files in diff by filtering. Handle `git diff` returning file renames. Handle repo with no commits yet (initial diff behavior).
    - **Acceptance**: Tamper Guard detects unauthorized test/spec/config modifications, rolls them back, and surfaces `TAMPER_DETECTED`. Authorized modifications (src-only, RED test creation, YELLOW-approved) pass through. All scenarios from US-004-4 pass.

- [x] T003: Full auto prompt templates for RED, GREEN, REFACTOR, JUDGE, and YELLOW phases
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `for f in red green refactor judge yellow; do test -f "src/deviate/prompts/auto/$f.md" || { echo "MISSING: $f.md"; exit 1; }; done && for f in red green refactor judge yellow; do wc -w "src/deviate/prompts/auto/$f.md"; done && echo "All templates present"`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/prompts/auto/red.md`
    - `src/deviate/prompts/auto/green.md`
    - `src/deviate/prompts/auto/refactor.md`
    - `src/deviate/prompts/auto/judge.md`
    - `src/deviate/prompts/auto/yellow.md`
  - **Rationale**: FR-004-AUTO-PROMPTS requires each auto prompt template to be the full original skill prompt from `.opencode/skills/deviate-<phase>/SKILL.md`, adapted for automated ingestion: CLI calls (`deviate <phase> pre/post`) are removed since the orchestrator handles those internally; constitution reads are replaced by the orchestrator appending `<constitution>...</constitution>` at runtime. The manual skills in `.opencode/skills/` retain their CLI calls for human-driven use, powered by T004-T006.
  - **Details**:
    - **Implementation**: Create each `.md` file under `src/deviate/prompts/auto/` by extracting the full content from the corresponding `.opencode/skills/deviate-<phase>/SKILL.md` and: (a) removing frontmatter (`---` delimited blocks), (b) removing all `deviate <phase> pre` / `deviate <phase> post` CLI command blocks from execution sequences, (c) removing steps that explicitly `read specs/constitution.md` (the orchestrator appends it), (d) removing the `<context><user_input>$ARGUMENTS</user_input></context>` footer. All XML structure, role definitions, traceability mandates, few-shot examples, output schemas, and edge-case tables are preserved. Templates with no corresponding skill file (judge, yellow) are written using the phase descriptions from T005 and T007 as specification. No word limits are enforced — comprehensiveness is the goal. The orchestrator pipeline will append `<constitution>[contents of specs/constitution.md]</constitution>` after the auto prompt text before sending to the agent.
    - **Refactor**: No refactor needed — these are new static files.
    - **Acceptance**: Each template exists at the correct path. Content matches the corresponding skill originals minus CLI calls and constitution reads. YAML handover output schema is documented in each template. No `{constitution_excerpt}` or `{claudemd_excerpt}` placeholders remain.

---

## Phase 2: Manual Phase Commands
**Goal**: Implement the individual `deviate red/green/yellow/judge/refactor/execute/e2e/hotfix pre/post` commands so each micro-layer phase can be stepped through manually.

### Tasks

- [x] T004: RED and GREEN phase manual pre/post commands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_micro/test_red.py tests/test_micro/test_green.py -v`
  - **Dependency**: T001, T003
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_red.py`
    - `tests/test_micro/test_green.py`
  - **Rationale**: US-004-3 (FR-004-RED) requires `deviate red pre` (emit JSON contract with task context, test command) and `deviate red post` (validate test fails with AssertionError/NotImplementedError, reject syntax errors, commit). US-004-4 (FR-004-GREEN) requires `deviate green pre` (load RED task, emit contract) and `deviate green post` (validate tests pass, run Tamper Guard, check for YELLOW trigger, commit). Both depend on T001 (AgentBackend for agent subprocess calls) and T003 (slim prompt templates for agent instructions).
  - **Details**:
    - **Red**: Write `test_red_pre_emits_contract` — run `deviate red pre` in temp env with PENDING task, assert JSON contract on stdout contains `task_id`, `test_command`, `lint_command`, `spec_dir`. Write `test_red_post_validates_test_fails` — create a temp git repo with a test that fails with `AssertionError`, run `deviate red post`, assert exit 0 and commit exists. Write `test_red_post_rejects_passing_test` — create passing test, run post, assert exit non-zero with `RedMustPassError`. Write `test_red_post_rejects_syntax_error` — create test with syntax error, run post, assert `SyntaxCrashRejected`. Write `test_green_pre_loads_red_task` — set up a task in RED state with failing test, run `deviate green pre`, assert contract contains `test_file` and `implementation_targets`. Write `test_green_post_validates_tests_pass` — implement code to pass RED test, run `deviate green post`, assert exit 0 and commit. Write `test_green_post_tamper_detection` — modify test file during GREEN, run post, assert Tamper Guard triggers rollback. Write `test_green_post_yellow_handover` — mock agent output with YELLOW trigger, assert post detects trigger and prints `YELLOW_TRIGGERED`.
    - **Green**: Implement `micro.py` with CLI entry points: `deviate red pre [--task <id>]` — find PENDING task, emit JSON with task context, test command, lint command, spec_dir. `deviate red post` — validate test file exists, run `pytest <file> -v`, assert exit non-zero with `AssertionError` (not syntax/import error), stage and commit test file. `deviate green pre [--task <id>]` — load active RED task from session, emit JSON with task context, test file path. `deviate green post` — run `pytest <file> -v`, assert exit 0, run `TamperGuard.evaluate(context=GREEN_IMPLEMENTATION)`, check agent manifest for `yellow_trigger`, stage and commit implementation files. Use Typer subcommands under `deviate` app router. Use `_tasks_jsonl` path from spec config.
    - **Refactor**: Extract common pre-flight logic (task resolution, session loading) into `_resolve_task_context()` helper. Extract common post-commit logic (stage, verify hook, commit) into `_commit_phase()`.
    - **Edge Cases**: Handle no PENDING tasks (print `NO_PENDING_TASKS`, exit 1). Handle missing test file after RED agent (print `TEST_NOT_FOUND`). Handle `test_command` as list of files (run all, assert any fail). Handle empty RED task (no failing test committed) in GREEN pre. Handle post-commit hook failure gracefully.
    - **Acceptance**: `deviate red pre/post` completes full RED cycle: task transitions from PENDING to RED, failing test committed, passing/syntax-error tests rejected. `deviate green pre/post` completes full GREEN cycle: task transitions from RED to GREEN, passing implementation committed, Tamper Guard active, YELLOW trigger detectable. All scenarios from US-004-3 and US-004-4 pass.

- [/] T005: YELLOW, JUDGE, and REFACTOR phase manual pre/post commands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_micro/test_yellow.py tests/test_micro/test_judge.py tests/test_micro/test_refactor.py -v`
  - **Dependency**: T004
  - **Estimated Time**: 75 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_yellow.py`
    - `tests/test_micro/test_judge.py`
    - `tests/test_micro/test_refactor.py`
  - **Rationale**: US-004-5 (FR-004-YELLOW) requires YELLOW pre/post commands to handle conditional test amendment protocol — emit contract describing proposed test changes, validate/commit amendments, or revert on rejection. US-004-6 (FR-004-JUDGE) requires JUDGE pre (evaluate `git diff` against `spec.md`, emit compliance report) — no post needed as it's advisory. US-004-7 (FR-004-REFACTOR) requires REFACTOR pre/post to polish implementation and validate test invariance. All three depend on T004 (RED/GREEN commands) because they run after GREEN completes.
  - **Details**:
    - **Red**: **Git isolation mandatory (see Universal Test Constraints). All tests that invoke git operations (add, commit, diff, restore, log) MUST use the `tmp_git_repo` fixture from `tests/conftest.py` and operate via `with chdir(tmp_git_repo):`.** Write `test_yellow_pre_emits_contract` — use `tmp_path`, set up task with YELLOW trigger manifest, run `deviate yellow pre`, assert contract contains `proposed_changes`, `rationale`, `test_files`. Write `test_yellow_post_accept_amendments` — use `tmp_git_repo`, commit a failing test file and implementation, mock approved YELLOW justification, run post, assert test changes committed and session returns to GREEN. Write `test_yellow_post_reject_amendments` — use `tmp_git_repo`, commit a test file, introduce changes, mock rejected justification, run post, assert `git restore` reverts test changes. Write `test_judge_pre_clean_diff` — use `tmp_git_repo`, commit baseline files with only expected changes, run `deviate judge pre`, assert `COMPLIANCE_PASS` verdict in contract. Write `test_judge_pre_violation` — use `tmp_git_repo`, commit baseline, then introduce spec-violating changes (e.g., modified protected module), run pre, assert `COMPLIANCE_VIOLATION` with details. Write `test_refactor_pre_emits_contract` — use `tmp_path`, set up GREEN task, run pre, assert contract has `files_to_refactor`. Write `test_refactor_post_test_invariance` — use `tmp_git_repo`, commit working implementation and passing tests, refactor code without changing behavior, run post, assert tests pass and commit exists. Write `test_refactor_post_regression_rollback` — use `tmp_git_repo`, commit passing implementation, make change that breaks test, run post, assert rollback with `RefactorRegressionError`. All git-interacting functions must receive `repo_path=tmp_git_repo` — never rely on `Path.cwd()` or the real repo root.
    - **Green**: Implement YELLOW pre: detect YELLOW trigger from session/git state, emit contract with `proposed_changes`, `rationale`, affected test files. YELLOW post: invoke JUDGE to evaluate amendment justification; if approved, commit changes and transition session back to GREEN; if rejected, `git restore` test files and re-enter GREEN without changes. Implement JUDGE pre: run `git diff` against last GREEN commit, parse `spec.md` for protected module/interface definitions, compare diff for structural violations, emit compliance verdict (PASS or VIOLATION with details). Implement REFACTOR pre: load active GREEN task, emit contract with `files_to_refactor`. REFACTOR post: run `pytest tests/ -v` before and after refactor; assert identical test results (invariance); if regression detected, `git restore` and raise `RefactorRegressionError`; otherwise commit.
    - **Refactor**: Extract YELLOW amend/revert logic into `_yellow_amend()` / `_yellow_revert()`. Extract JUDGE diff-analysis into reusable `_analyze_diff()` for potential use in automated orchestration. Extract REFACTOR invariance check into `_assert_test_invariance()`.
    - **Edge Cases**: YELLOW with no proposed changes (print `NO_CHANGES_PROPOSED`, exit). JUDGE with no diff (print `NO_DIFF`, exit cleanly). REFACTOR with no files to refactor (print `NOTHING_TO_REFACTOR`, skip). REFACTOR invariance check with empty test suite (skip, not fail).
    - **Acceptance**: YELLOW pre/post handles amendment protocol end-to-end — accept committed, reject reverted. JUDGE pre returns accurate compliance verdict. REFACTOR pre/post polishes code while maintaining test invariance. All scenarios from US-004-5, US-004-6, US-004-7 pass.

- [ ] T006: EXECUTE, E2E, and HOTFIX phase manual pre/post commands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_micro/test_execute.py tests/test_micro/test_e2e.py tests/test_micro/test_hotfix.py -v`
  - **Dependency**: T005
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_execute.py`
    - `tests/test_micro/test_e2e.py`
    - `tests/test_micro/test_hotfix.py`
  - **Rationale**: US-004-9 requires auxiliary phase commands for non-TDD workflows. FR-004-EXECUTE: `deviate execute pre/post` for DIRECT-mode tasks that bypass RED/GREEN/REFACTOR. FR-004-E2E: `deviate e2e pre/post` for end-to-end verification after all tasks complete. FR-004-HOTFIX: `deviate hotfix pre/post` for bug fixes that skip RED. These are independent phase commands added to the micro.py CLI surface. Dependencies: all three expect core agent (T001) and Tamper Guard (T002) infrastructure.
  - **Details**:
    - **Red**: **Git isolation mandatory (see Universal Test Constraints). All tests that invoke git operations MUST use `tmp_git_repo` fixture + `with chdir(tmp_git_repo):`.** Write `test_execute_pre_discovers_direct_task` — use `tmp_path`, set up task with `execution_mode=DIRECT`, run `deviate execute pre`, assert contract contains `workflow_context` and `completion_criteria`. Write `test_execute_post_commits_result` — use `tmp_git_repo`, run `deviate execute post <manifest>`, assert commit created and task marked COMPLETED. Write `test_e2e_pre_verifies_all_tasks_complete` — use `tmp_git_repo`, set up all tasks COMPLETED, run pre, assert contract with E2E test paths. Write `test_e2e_pre_rejects_incomplete_tasks` — use `tmp_git_repo`, leave one task PENDING, run pre, assert `INCOMPLETE_TASKS` error. Write `test_e2e_post_commits_results` — use `tmp_git_repo`, run post after E2E execution, assert commit. Write `test_hotfix_pre_discovers_bug_context` — use `tmp_path`, set up bug report issue, run `deviate hotfix pre`, assert contract with bug context, bypasses RED. Write `test_hotfix_post_commits_without_red` — use `tmp_git_repo`, run post, assert commit without RED phase.
    - **Green**: Implement EXECUTE pre: find task with `execution_mode=DIRECT`, emit contract with task description, workflow context, completion criteria. EXECUTE post: accept manifest file, validate completion criteria, stage and commit, mark COMPLETED in ledger. E2E pre: verify all tasks for active issue are COMPLETED (query ledger), discover E2E test files (glob `tests/e2e/` + `tests/**/test_e2e*.py`), emit contract with test paths. E2E post: run discovered E2E tests via `bats` or `pytest`, capture results, commit results file. HOTFIX pre: discover bug context from issue body, emit contract without requiring RED test. HOTFIX post: validate fix, stage and commit.
    - **Refactor**: Extract manifest validation into reusable `_validate_manifest()` across all three post-commands. Extract "all tasks complete" check into `_all_tasks_complete()` for E2E reuse.
    - **Edge Cases**: EXECUTE with `execution_mode=TDD` (refuse with `NOT_DIRECT_MODE`). E2E with empty test suite (warn `NO_E2E_TESTS`, still commit). HOTFIX with no issue body (emit minimal contract without context). HOTFIX post with failing tests (warn but still commit — hotfixes are urgent).
    - **Acceptance**: EXECUTE pre/post handles DIRECT-mode tasks end-to-end. E2E pre/post runs verification and commits results. HOTFIX pre/post bypasses RED and commits fix. All scenarios from US-004-9 pass.

---

## Phase 3: Automated Orchestration
**Goal**: Implement the fully automated `deviate micro` pipeline that orchestrates all phases (RED→GREEN→YELLOW→JUDGE→REFACTOR) in a single command with session state tracking, ledger updates, and `--all` multi-task support.

### Tasks

- [ ] T007: Automated `deviate micro` orchestration with session state, ledger updates, and `--all` multi-task pipeline
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_orchestration.py tests/test_integration/test_micro_orchestration.py -v`
  - **Dependency**: T006
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_orchestration.py`
    - `tests/test_integration/test_micro_orchestration.py`
  - **Rationale**: US-004-8 (FR-004-MICRO-ORCHESTRATION) requires `deviate micro <TASK_ID>` to run a single task through the full RED→GREEN→JUDGE→REFACTOR cycle, and `deviate micro --all` to process all PENDING tasks sequentially with retry-once-then-abort semantics. The CLI handles all admin (state transitions, git commits, validation, agent invocation); the agent receives the full auto prompt (from T003) with `<constitution>...</constitution>` and task context appended. Session state must track active TaskRecord and current micro phase. Ledger updates must append TaskRecord status transitions after each phase commit. Dependencies: all phase commands (T004-T006), agent backend (T001), Tamper Guard (T002), and prompt templates (T003).
    - **Details**:
      - **Red**: **Git isolation mandatory (see Universal Test Constraints). All tests that invoke git operations MUST use `tmp_git_repo` fixture + `with chdir(tmp_git_repo):`. Pass `repo_path=tmp_git_repo` to all git-interacting functions.** Write `test_micro_single_task_full_cycle` — use `tmp_git_repo`, set up a PENDING task in a temp git repo with all phase command stubs, run `deviate micro T001`, assert task transitions PENDING→RED→GREEN→JUDGE→REFACTOR→COMPLETED, assert commits exist for each phase, assert ledger `tasks.jsonl` contains status transitions. Write `test_micro_all_processes_all_pending` — use `tmp_git_repo`, create 2 PENDING tasks, run `deviate micro --all`, assert both complete. Write `test_micro_all_retry_once_then_abort` — use `tmp_git_repo`, make first task fail on RED twice, run `--all`, assert first task FAILED, assert second task never started (abort). Write `test_micro_session_tracks_active_phase` — use `tmp_git_repo`, run `deviate micro` up to GREEN, assert session file contains `active_task_id`, `current_phase: "GREEN"`, `last_commit_hash`. Write `test_micro_ledger_updates_on_each_phase` — use `tmp_git_repo`, after each phase commit, assert `tasks.jsonl` has matching status record. Write `test_micro_no_judge_flag` — use `tmp_git_repo`, run with `--no-judge`, assert JUDGE skipped. Write `test_micro_no_refactor_flag` — use `tmp_git_repo`, run with `--no-refactor`, assert REFACTOR skipped. Write `test_micro_agent_flag` — use `tmp_git_repo`, run with `--agent droid`, assert AgentBackend uses droid backend.
      - **Green**: Implement `deviate micro <TASK_ID>` in `micro.py` as a Typer command. Internally: 1) Load task from ledger, transition session to active. 2) RED: load auto prompt from `src/deviate/prompts/auto/red.md`, append `<constitution>[contents of specs/constitution.md]</constitution>`, append task context, send full message to AgentBackend, verify test file exists and test FAILS, stage test, commit, append task RED status to ledger, update session. 3) GREEN: load `auto/green.md`, append `<constitution>...</constitution>` + task context, invoke agent, verify tests PASS, run TamperGuard (GREEN_IMPLEMENTATION context), detect YELLOW trigger in manifest, if triggered invoke YELLOW phase, stage implementation, commit, append GREEN status. 4) JUDGE: evaluate diff against spec.md invariants, if violation abort with COMPLIANCE_VIOLATION. 5) REFACTOR: load `auto/refactor.md`, append constitution + task context, invoke agent, verify tests still PASS, commit, append COMPLETED. 6) Mark COMPLETED in ledger, transition session to IDLE. Implement `--all` flag: load all PENDING tasks, for each run the full cycle, on failure retry once then abort. Implement `--no-judge` and `--no-refactor` to skip respective phases. Implement `--agent` to override backend. For constitution injection: read `specs/constitution.md` at start of `deviate micro`, cache in memory, wrap in `<constitution>...</constitution>` tags, append after each auto prompt before sending to agent. No placeholders or template substitution needed — each auto prompt is self-contained; constitution is appended as a trailing contextual block.
      - **Refactor**: Extract the phase pipeline orchestration from CLI handler into `_run_micro_pipeline(task_id, flags)` for testability. Extract constitution caching into `_load_governance_context()`. Extract phase dispatch logic into a phase map: `{ "RED": _run_red, "GREEN": _run_green, ... }`. Extract `--all` iteration into `_run_micro_batch()`.
      - **Edge Cases**: `deviate micro` with no PENDING tasks (print `NO_PENDING_TASKS`, exit 0). `deviate micro` with unknown task ID (exit 1 with `TASK_NOT_FOUND`). Constitution file missing (warn but continue without injection, not fatal). `--all` with zero PENDING tasks (print `ALL_TASKS_COMPLETE`, exit 0). Subprocess agent command not found (surface `AgentBinaryNotFoundError`, abort phase). Agent returns empty or unparseable handover manifest (surface `MalformedHandoverManifestError`, abort phase with diagnostic).
      - **Acceptance**: `deviate micro <TASK_ID>` runs the full automated pipeline — RED creates failing test, GREEN creates passing code with Tamper Guard, JUDGE validates compliance, REFACTOR polishes. Task ends COMPLETED with ledger appended. `--all` processes all PENDING tasks sequentially. `--no-judge` and `--no-refactor` skip gates. `--agent` overrides backend. Session state accurately tracks progress. All scenarios from US-004-8 pass.
    - **Acceptance**: Each template exists at the correct path. RED/GREEN/REFACTOR match skill originals minus CLI calls, constitution reads, and user_input footer. JUDGE/YELLOW contain full role definition, execution sequence, output schema, and edge cases. No `{constitution_excerpt}`, `{claudemd_excerpt}`, or CLI command blocks remain. Pipeline can append `<constitution>...</constitution>` after any template without template substitution.

---

## Implementation Strategy

**Execution Order**:
1. Phase 1 (Core Infrastructure) → Phase 2 (Manual Phase Commands) → Phase 3 (Automated Orchestration)

**Critical Dependency Chains**:
- T001 (Agent Backend) → T004 (RED+GREEN) → T005 (YELLOW+JUDGE+REFACTOR) → T006 (EXECUTE+E2E+HOTFIX) → T007 (Automated Orchestration)
- T002 (Tamper Guard) → T004 (RED+GREEN)
- T003 (Prompt Templates) → T004 (RED+GREEN)

**Risk Hotspots**:
- T007 (Automated Orchestration) has the highest integration surface — depends on all prior tasks being correct. Integration tests in `tests/test_integration/test_micro_orchestration.py` must exercise the full pipeline end-to-end.
- T001 (Agent Backend) subprocess invocation is platform-dependent (heredoc pipe behavior differs on Windows/Darwin). Tests must mock subprocess to ensure determinism.
- T002 (Tamper Guard) operates on real git state — git isolation in tests is mandatory (use `tmp_git_repo` fixture). Incorrect diff parsing could cause false positives/negatives.

**Merge Conflict Boundaries**:
- `src/deviate/cli/micro.py` — touched by T004, T005, T006, T007 (sequential, no conflict if ordered)
- `src/deviate/state/config.py` — touched only by T001 (no conflict)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    subprocess.run(["git", "add", ...], cwd=repo, check=True)

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```

**Consequence**: Every per-task Git Isolation block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that runs git commands, that function **must** accept `repo_path`.
