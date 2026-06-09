# Implementation Tasks: feat/001-deviate-cli-python/007-macro-meso-parity-backward-compatibility

## Phase 1: Macro Contract Infrastructure & Explore/Research Enhancement
**Goal**: Build shared macro contract builder with auto-resolved repository context (repo_root, git_branch, constitution_path, test/lint/type_check commands, epic_id, is_greenfield, timestamp) and apply to explore pre and research pre commands so their JSON contracts match bash field parity.

### Tasks

- [x] T001: Enhance macro contract infrastructure and apply to explore/research pre
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_macro_contracts.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/test_cli/test_macro_contracts.py`
  - **Rationale**: `macro.py` is the sole file emitting explore/research pre contracts; currently emits only 3-5 fields vs bash's 15-18. This task builds the shared contract builder that auto-resolves repo context (repo_root, git_branch, constitution_path, commands, epic_id, is_greenfield, timestamp) via `find_repo_root()`, `gather_git_state()`, and constitution scanning, then wires it into explore pre and research pre. Ties to US-001 and US-002 (FR-007-CONTRACT).
  - **Details**:
    - **Red**: Write failing test `test_explore_pre_contract_has_all_fields()` asserting the emitted JSON contains `repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `epic_id`, `is_greenfield`, `timestamp`, `status`, `phase`, `issue_id`, `feature_bucket`, `feature_dir`, `explore_path`. Write `test_research_pre_contract_has_all_fields()` asserting `repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `is_greenfield`, `timestamp`, `status`, `phase`, `issue_id`, `feature_bucket`, `explore_path`, `design_target`, `data_model_target`.
    - **Green**: Refactor `_emit_contract()` in `macro.py` to accept a `ContractBuilder` dataclass or accept structured kwargs that auto-resolve context from the session and repo. For explore pre, add calls to `find_repo_root()`, `gather_git_state()`, read constitution for test/lint/type_check commands, resolve epic_id from the feature slug, and set is_greenfield based on spec directory existence. Apply same pattern to research pre.
    - **Refactor**: Extract `_resolve_repo_context()` and `_resolve_constitution_commands()` helper functions from the builder to keep `_emit_contract()` focused on serialization only. Ensure `--dry-run` does not create directories or mutate state.
    - **Edge Cases**: Handle missing constitution by emitting empty strings for commands; handle detached HEAD by emitting `"detached"` for git_branch; handle missing spec directory by setting `is_greenfield: true`.
    - **Acceptance**: `pytest tests/test_cli/test_macro_contracts.py -v` passes; manual `deviate explore pre "test" --dry-run` emits a contract with at least 15 fields matching bash output.

## Phase 2: PRD & Shard Contract Enhancement
**Goal**: Extend the enhanced macro contract infrastructure to prd pre and shard pre commands, bringing their JSON contract field sets to parity with the bash originals.

### Tasks

- [x] T002: Extend enhanced contract to prd and shard pre commands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_macro_contracts.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T001
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/test_cli/test_macro_contracts.py`
  - **Rationale**: Shares the same `_emit_contract()` helper and `_resolve_repo_context()` from T001 in `macro.py`. PRD pre currently emits 2 fields vs bash's 17; shard pre emits 4 vs bash's 17. Ties to US-003 and US-004 (FR-007-CONTRACT). Depends on T001 for the shared infrastructure.
  - **Details**:
    - **Red**: Write `test_prd_pre_contract_has_all_fields()` asserting `repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `timestamp`, `status`, `phase`, `issue_id`, `feature_bucket`, `design_path`, `data_model_path`. Write `test_shard_pre_contract_has_all_fields()` asserting `repo_root`, `git_branch`, `constitution_path`, `issues_dir`, `plan_target`, `dry_run`, `timestamp`, `status`, `phase`, `issue_id`, `prd_path`, `shard_count`.
    - **Green**: Wire `_resolve_repo_context()` into prd pre's `_emit_contract()` call: add `design_path`, `data_model_path` from the epic directory, `issue_id` from session, and the standard repo context fields. For shard pre, add `issues_dir` (resolved from the epic's issues/ directory), `plan_target`, `dry_run` flag, `prd_path`, and `shard_count` (count of files in issues dir).
    - **Refactor**: Extract `_resolve_epic_paths()` helper for the design/data-model/PRD path resolution pattern shared between prd and shard. Consolidate duplicate `Path(EPIC_DIR)` constructions.
    - **Edge Cases**: Handle missing design.md/data-model.md by emitting empty strings; handle empty issues directory with `shard_count: 0`.
    - **Acceptance**: `pytest tests/test_cli/test_macro_contracts.py -v` passes; manual `deviate prd pre --dry-run` emits 17+ fields; `deviate shard pre --dry-run` emits 17+ fields.

## Phase 3: Tasks & PR Full Contract Emission
**Goal**: Create full JSON contract emission for tasks pre and pr pre commands, which currently emit no contract at all. These commands must match the contract format used by bash for downstream tooling compatibility.

### Tasks

- [x] T003: Implement full JSON contract emission for tasks pre and pr pre
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_meso_contracts.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_cli/test_meso_contracts.py`
  - **Rationale**: `meso.py` has a detailed `_emit_contract()` for specify but tasks pre and pr pre currently emit no contract. This is the biggest gap identified in the parity audit. Must produce contracts matching the bash task/PR workflow formats for downstream tooling (GitHub PR creation, task execution). Ties to US-005 and US-006 (FR-007-CONTRACT).
  - **Details**:
    - **Red**: Write `test_tasks_pre_contract_has_required_fields()` asserting the emitted JSON is a valid object containing `issue_id`, `spec_path`, `worktree_full`, `constitution_path`, `constitution_test_command`, `constitution_lint_command`, `timestamp`, `status`, and `phase`. Write `test_pr_pre_contract_has_required_fields()` asserting `branch_name`, `base_branch`, `pr_title`, `pr_body`, `git_state`, `timestamp`, `status`, and `phase`.
    - **Green**: Implement `_tasks_pre()` in `meso.py` to resolve the current spec from the branch/worktree, gather constitution commands, and emit a contract mirroring `_emit_contract()` from specify. Implement `_pr_pre()` to gather branch info from git, derive PR title from the issue ledger, collect git state via `gather_git_state()`, and emit the contract. Add the `--dry-run` flag to both (flag exists but no-op).
    - **Refactor**: Extract `_resolve_constitution_commands()` as a shared helper (also used by specify pre) to avoid duplication. Extract `_derive_pr_metadata()` into a pure function taking branch_name + issue_id and returning title/body.
    - **Edge Cases**: Handle missing spec.md by emitting `spec_path: ""` and `status: "SPEC_NOT_FOUND"`; handle uncommitted git state by including dirty files in `git_state`; handle detached HEAD for pr pre.
    - **Acceptance**: `pytest tests/test_cli/test_meso_contracts.py -v` passes; `deviate tasks pre --dry-run` emits valid JSON with all 9 required fields; `deviate pr pre --dry-run` emits valid JSON with all 8 required fields.

## Phase 4: Content Validation Engine for Post-Commands
**Goal**: Build section-level content validation in `validation.py` and integrate into all macro/meso post-commands (explore, research, shard, tasks post) so they validate specific required sections instead of only checking non-empty.

### Tasks

- [x] T004: Implement content validation engine and wire into post-commands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_validation.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/core/validation.py`
    - `src/deviate/cli/macro.py`
    - `src/deviate/cli/meso.py`
    - `tests/test_core/test_validation.py`
  - **Rationale**: `validation.py` currently has only `extract_section_body()` and `validate_gherkin_syntax()`. No contract validation or markdown section validation exists. The spec requires post-commands to validate specific sections (US-007 through US-010, FR-007-VALIDATE). Each command validates different artifacts: explore validates 5 sections in explore.md, research validates 9+6 in design.md+data-model.md, shard validates NNN-*.md YAML frontmatter, tasks validates T{NNN} format and checkboxes.
  - **Details**:
    - **Red**: Write `test_validate_explore_sections_detects_missing()` asserting that an explore.md missing `PROBLEM_DEFINITION` returns non-zero with diagnostic. Write `test_validate_research_artifacts_detects_missing()` asserting design.md missing 1 of 9 sections fails. Write `test_validate_shard_frontmatter_validates_yaml()` asserting a shard file with invalid YAML frontmatter fails. Write `test_validate_task_ids_accepts_both_TNNN_and_TSK()` asserting that both `T001` and `TSK-007-01` pass validation. Write `test_validate_task_ids_rejects_malformed()` asserting `TASK_1` or `TSK001` fail.
    - **Green**: Add `validate_sections(content: str, required: list[str]) -> list[str]` returning missing sections. Add `validate_yaml_frontmatter(content: str) -> bool` for shard validation. Add `validate_task_id(task_id: str) -> bool` accepting both `T{NNN}` (regex `^T\d{3}$`) and `TSK-{issue_number}-{NN}` (regex `^TSK-\d{3}-\d{2}$`) formats. In `macro.py`, wire explore post to call `validate_sections()` with `[PROBLEM_DEFINITION, DISCOVERY_AUDIT_RESULTS, CONSTITUTION_QUOTES, FILE_REGISTRY, STATUS_SUMMARY]`. Wire research post to validate design.md (9 sections) + data-model.md (6 sections) + constitutional alignment audit. Wire shard post to iterate `NNN-*.md` files and validate YAML frontmatter. In `meso.py`, wire tasks post to call `validate_task_id()` and checkbox validation on every task entry.
    - **Refactor**: Extract a `PostValidator` class or module-level registry mapping artifact types to their required sections, so adding new validators doesn't require editing individual post-command functions. Use a `ValidationResult` namedtuple with `.passed`, `.errors`, `.warnings`.
    - **Edge Cases**: Handle empty files (no sections found = all missing); handle missing artifact file (emit FILE_NOT_FOUND error); handle files with only whitespace or comments (treated as empty).
    - **Acceptance**: `pytest tests/test_core/test_validation.py -v` passes; `deviate explore post` on a minimal explore.md fails with specific missing section names; `deviate shard post` validates YAML frontmatter not spec.md/tasks.md.

## Phase 5: Dry-Run and Issue-ID CLI Flags
**Goal**: Add `--dry-run` flag to prd, shard, tasks, and pr commands (currently only on specify), and add `--issue-id` option to tasks post for explicit spec resolution.

### Tasks

- [x] T005: Add dry-run flag to remaining commands and issue-id to tasks post
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_macro_contracts.py tests/test_cli/test_meso_contracts.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: T002, T003
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `src/deviate/cli/macro.py`
    - `src/deviate/cli/meso.py`
    - `tests/test_cli/test_macro_contracts.py`
    - `tests/test_cli/test_meso_contracts.py`
  - **Rationale**: `--dry-run` currently works only on specify. The remaining commands (prd, shard, tasks, pr) need it for safe contract inspection without side effects. `--issue-id` on tasks post allows explicit spec resolution matching bash behavior. These are CLI wiring changes in `__init__.py` and per-command files. Ties to US-011 and US-012 (FR-007-FEATURES). Depends on T002/T003 because the contract fields must exist before dry-run can demonstrate them.
  - **Details**:
    - **Red**: Write `test_prd_pre_dry_run_does_not_create_artifacts()` asserting that after `--dry-run`, no explore.md/design.md files exist in the expected bucket. Write `test_shard_pre_dry_run_does_not_create_issues()` asserting the issues ledger is unchanged. Write `test_tasks_pre_dry_run_does_not_append_ledger()` asserting no new task records appear. Write `test_tasks_post_issue_id_resolves_correct_spec()` asserting that `--issue-id ISS-006` validates the correct tasks.md.
    - **Green**: In `macro.py`, add `dry_run: bool = False` parameter to prd pre and shard pre command functions. When True, skip all filesystem mutations (file writes, directory creation, ledger appends) but still emit contract. In `meso.py`, add `dry_run` to tasks pre and pr pre with same semantics. Add `issue_id: Optional[str] = None` to tasks post; when provided, resolve spec from the issue ledger's `source_file` instead of deriving from git branch.
    - **Refactor**: Extract a `_guard_dry_run(session, session_path, dry_run)` helper that wraps the filesystem mutation check, returning early True if dry-run is active. This eliminates the repeated `if dry_run: return` pattern across multiple functions.
    - **Edge Cases**: Dry-run on prd pre should not create the feature bucket directory at all; dry-run on shard pre should not append to issues.jsonl; invalid `--issue-id` should exit non-zero with `INVALID_ISSUE_ID` error.
    - **Acceptance**: `pytest tests/test_cli/test_macro_contracts.py -v` and `tests/test_cli/test_meso_contracts.py -v` pass; `deviate prd pre --dry-run` shows contract but no files created; `deviate tasks post --issue-id ISS-999` exits with `INVALID_ISSUE_ID`.

## Phase 6: Pre-Commit, Mise Setup, and E2E Verification
**Goal**: Add pre-commit hook execution in post-phase commands, mise setup in new worktrees, and an end-to-end parity verification task.

### Tasks

- [x] T006: Add pre-commit hook execution and mise setup in post-phases and worktrees
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_integration/test_parity.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T004
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `src/deviate/cli/meso.py`
  - **Rationale**: US-013 requires post-phases to trigger pre-commit hooks when `.githooks/` is configured; US-014 requires mise setup in new worktrees. Both are procedural wrappers around existing bash logic (detect config, run if present). No new test files needed — the behavior is verified by the existing integration test suite. Depends on T004 because validation runs in post-phase before commit.
  - **Details**:
    - **Implementation**: In each post-phase function (`explore_post`, `research_post`, `prd_post`, `shard_post`, `tasks_post`), add a `_run_pre_commit_hooks()` call between validation and git commit. This function checks for `.githooks/` dir and `core.hooksPath` git config, then runs `git commit` without `--no-verify` (or with explicit hook path). In worktree creation logic (in meso.py's `_specify_pre`), add a `_setup_mise()` call that detects mise availability, runs `mise trust && mise install && mise run setup`, and gracefully skips if mise is not on PATH.
    - **Refactor**: Extract `_run_pre_commit_hooks(worktree_path)` helper used by all post-phases. Extract `_setup_mise(worktree_path)` helper used by worktree creation.
    - **Edge Cases**: If `.githooks/` does not exist, skip silently (emit info-level log). If mise is missing, emit warning and continue. If pre-commit hooks fail the commit, the post-phase fails with the hook output.
    - **Acceptance**: `mise run check` passes; new worktrees created via `deviate specify pre` have `mise trust` applied; `deviate explore post` runs pre-commit hooks if configured.

## Phase 7: Deviate Run Dispatcher Command
**Goal**: Implement `deviate run` that reads a task's `execution_mode` field and routes to either the TDD cycle (RED → GREEN → REFACTOR for `TDD` tasks) or the execute phase (direct implementation for `IMMEDIATE` tasks). Also implement `deviate run --all` for batch iteration. Note: `deviate execute` from the old bash skill still exists as a separate command for direct non-TDD execution.

### Tasks

- [x] T007: Implement deviate run dispatcher with TDD/execute routing
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_micro/test_run.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/test_micro/test_run.py`
  - **Rationale**: US-015 (FR-007-FEATURES) requires `deviate run` as a dispatcher that reads task `execution_mode` (TDD or IMMEDIATE) and routes accordingly. `deviate execute` remains available for direct IMMEDIATE task execution (legacy bash behavior). The dispatcher must accept both legacy `T{NNN}` and new `TSK-{issue_number}-{NN}` task ID formats. This is an independent orchestration capability in the micro layer.
  - **Details**:
    - **Red**: Write `test_run_dispatches_tdd_task_to_rgr()` using a mock task ledger with a TDD-mode task in CREATED status. Assert that `deviate run TSK-007-01` produces a failing test (RED), then implementation (GREEN), then polish (REFACTOR), ending in COMPLETED. Write `test_run_dispatches_immediate_task_to_execute()` with an IMMEDIATE-mode task, asserting that RED is skipped and implementation starts directly. Write `test_run_all_iterates_mixed_modes()` with a ledger containing both TDD and IMMEDIATE tasks, asserting all reach COMPLETED. Write `test_run_accepts_legacy_TNNN_format()` asserting `deviate run T001` resolves correctly.
    - **Green**: In `micro.py`, implement the `run` command with positional `task_id` arg and optional `--all` flag. Implement `_run_single_task(task_id)` that: (1) reads the task record from the ledger, (2) checks `execution_mode` — `TDD` routes to RED → GREEN → REFACTOR, `IMMEDIATE` routes to execute phase (verify → commit), (3) appends status updates to the ledger after each phase. Implement `--all` to iterate all CREATED tasks. The `task_id` resolver must accept both `T{NNN}` and `TSK-{issue_number}-{NN}` by normalizing to a canonical lookup key.
    - **Refactor**: Extract `_resolve_task(ledger, task_id: str)` that handles both ID formats. Extract `_run_tdd_cycle(task_id)` and `_run_execute_phase(task_id)` as separate dispatch targets. Keep the `run` command itself thin — just resolves, dispatches, and reports.
    - **Edge Cases**: Unknown task ID exits with `TASK_NOT_FOUND`. Already-COMPLETED task is skipped with `TASK_ALREADY_DONE` warning. Mixed-mode `--all` continues to next task if one fails (recording FAILED status). Both ID formats must resolve to the same canonical task.
    - **Acceptance**: `pytest tests/test_micro/test_run.py -v` passes; `deviate run T001` dispatches correctly; `deviate run TSK-007-01` dispatches correctly; `deviate run --all` processes all tasks.

## Phase 8: End-to-End Parity Verification
**Goal**: Verify the complete macro/meso parity implementation against the bash originals and confirm backward compatibility.

### Tasks

- [/] T008: End-to-end parity verification suite
  - **Type**: Infra_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_integration/test_parity.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: T001, T002, T003, T004, T005, T006
  - **Files**:
    - `tests/test_integration/test_parity.py`
  - **Rationale**: Spec requires verification that (a) all Python contracts match bash field sets, (b) bash scripts remain functional, (c) backward compatibility is maintained. This E2E task runs both CLIs and compares outputs. Depends on all prior tasks completing because parity can only be verified once all contracts are enhanced.
  - **Details**:
    - **Red**: Write `test_explore_python_matches_bash_fields()` that runs `python -m deviate explore pre "test" --dry-run` and `bash ~/.claude/skills/deviate-explore.sh pre --dry-run`, parses both JSON contracts, and asserts all bash fields are present in the Python output. Write `test_bash_skills_still_parse()` that runs each bash script with `--help` or `--dry-run` and asserts exit code 0.
    - **Green**: No production code changes needed — this task writes the integration tests that validate all prior tasks. The test file invokes both Python CLI and bash CLI subprocesses, compares contract field sets, and reports mismatches.
    - **Refactor**: Extract `_run_python_contract(cmd, args)` and `_run_bash_contract(script_path, args)` helper functions. Extract `_assert_field_parity(python_json, bash_json, required_fields)` that checks subset/superset relationships.
    - **Edge Cases**: Handle bash scripts that don't accept `--dry-run` by running without it (and cleaning up). Handle missing bash scripts by skipping that comparison with WARN log. Handle JSON parse failures on either side with clear error messages.
    - **Acceptance**: `pytest tests/test_integration/test_parity.py -v` passes; all bash scripts `~/.claude/skills/deviate-*.sh` execute without error; Python contract field sets are supersets of bash field sets.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (T001) -> Phase 2 (T002) -> Phase 5 (T005)
2. Phase 3 (T003) -> Phase 5 (T005)
3. Phase 4 (T004) -> Phase 6 (T006)
4. Phase 7 (T007) independent — micro layer, no dependency on macro/meso contracts
5. Phase 8 (T008) requires all previous phases

**Critical Dependency Chains**:
- T001 -> T002 -> T005 (macro infrastructure chain)
- T003 -> T005 (meso contract chain, but T005 also needs T002)
- T004 -> T006 (validation chain)
- T001, T002, T003, T004, T005, T006 -> T008 (E2E verification depends on all)

**Risk Hotspots**:
- T001/T002 scope overlap: Ensure the shared `_resolve_repo_context()` is truly shared and not duplicated per-command to avoid the "junk drawer" anti-pattern in macro.py.
- T005 flag wiring: `--dry-run` and `--issue-id` require Typer option annotations; forgetting to add them to the function signatures will cause silent flag omission.
- T007 dispatcher: The `TDD` → RED/GREEN/REFACTOR dispatch path must call micro-layer phase functions that may not exist yet; stub them with error logging and clear TODO markers. The dual-format task ID resolver (`T{NNN}` + `TSK-{issue_number}-{NN}`) must normalize to a single canonical lookup key to avoid duplicate execution.

**Merge Conflict Boundaries**:
- `src/deviate/cli/macro.py`: Touched by T001, T002, T004, T005, T006 — high contention
- `src/deviate/cli/meso.py`: Touched by T003, T004, T005, T006 — high contention
- `tests/test_cli/test_macro_contracts.py`: Touched by T001, T002, T005

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