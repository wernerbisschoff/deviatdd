# Implementation Tasks: feat/002-deviatdd-gap-analysis/004-governance-inspection

## Phase 1: Constitution Seed Placeholder Audit & Patch
**Goal**: Implement `validate_placeholders()` in `core/constitution.py` that audits all 6 `${VARIABLE}` tokens in the seed template, and patch the 4 missing placeholders into `constitution_seed.md`. This phase establishes the compliance gate for placeholder coverage that is wired into `deviate init`.

### Tasks

- TSK-004-01: Constitution Seed Placeholder Audit — validate_placeholders() + Seed Patch
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_constitution.py -v --no-header -q`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/core/constitution.py`
    - `src/deviate/prompts/constitution_seed.md`
    - `tests/test_core/test_constitution.py`
  - **Rationale**: US-005 (FR-014) requires `validate_placeholders()` to audit all 6 `${VARIABLE}` tokens in `constitution_seed.md`. Currently only 2 of 6 exist (PROJECT_NAME, REPO_ROOT). The function returns a `PlaceholderAuditResult` with `all_present`, `variables`, and `missing`. The seed template gets patched with TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM plus surrounding context. Tests cover all 3 acceptance scenarios: all present, missing detected, FileNotFoundError.
  - **Details**:
    - **Red**: Write `test_validate_placeholders_all_present()` — create a seed file with all 6 `${VARIABLE}` tokens, call `validate_placeholders()`, assert `result.all_present is True` and `result.variables` contains all 6 names. Write `test_validate_placeholders_missing_variable()` — create seed missing one variable, assert `all_present is False` and `result.missing` lists the absent one. Write `test_validate_placeholders_file_not_found()` — pass a non-existent path, assert `FileNotFoundError`.
    - **Green**: Implement `PlaceholderAuditResult` dataclass with `all_present: bool`, `variables: list[str]`, `missing: list[str]`. Implement `validate_placeholders(seed_path: Path) -> PlaceholderAuditResult` — read file, regex-find all `${...}` tokens, compare against the canonical 6, compute `missing`. Patch `constitution_seed.md` by adding the 4 missing placeholders with surrounding markdown context in the metadata section.
    - **Refactor**: Extract `_REQUIRED_PLACEHOLDERS` as a module-level frozenset. Use `re.findall(r'\$\{(\w+)\}', content)` for extraction. Keep comparison logic in a pure helper.
    - **Edge Cases**: Seed file with extra (non-required) variables → not an error. Seed file with malformed placeholders (`$VAR` without braces) → not detected (only `${VAR}` pattern). Whitespace inside braces → trim. Empty file → `missing` = all 6.
    - **Acceptance**: AC-014-01 passes. `result.missing` lists only actually absent variables. All 6 canonical names match PRD §FR-014: PROJECT_NAME, REPO_ROOT, TARGET_BACKEND_FRAMEWORK, TARGET_PACKAGE_MANAGER, TARGET_TEST_RUNNER, TARGET_COVERAGE_MINIMUM.

## Phase 2: Constitution CLI — Pre/Post Commands
**Goal**: Create `deviate constitution pre` (validate constitution, extract test/lint/typecheck commands, emit JSON contract) and `deviate constitution post <manifest>` (validate sections, commit). This phase depends on the existing `validate_constitution()` and `extract_commands()` in `core/constitution.py`.

### Tasks

- TSK-004-02: Constitution CLI — constitution pre + constitution post
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_constitution.py -v --no-header -q`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/constitution.py` (NEW)
    - `src/deviate/cli/__init__.py` (MODIFY)
    - `tests/test_cli/test_constitution.py` (NEW)
  - **Rationale**: US-001 (FR-005) requires `constitution pre` to validate `specs/constitution.md`, extract test/lint/typecheck commands, and emit a JSON contract — with FAILURE on missing file (AC-005-01) or missing sections (AC-005-02). US-002 (FR-005) requires `constitution post <manifest>` to validate section structure and commit (AC-005-03, AC-005-04). Registration in `cli/__init__.py` makes `deviate constitution` discoverable. Tests mock `Path.cwd()` and use `tmp_git_repo` for git commit operations.
  - **Details**:
    - **Red**: Write `test_constitution_pre_emits_commands()` — create `specs/constitution.md` with valid `## TESTING_PROTOCOLS` containing test/lint/typecheck commands, invoke `runner.invoke(app, ["constitution", "pre"])`, assert stdout contains valid JSON with keys `test_command`, `lint_command`, `typecheck_command` and exit 0. Write `test_constitution_pre_missing_file()` — no constitution file, invoke, assert JSON `status: FAILURE` and non-zero exit. Write `test_constitution_pre_missing_section()` — create constitution without `## TESTING_PROTOCOLS`, invoke, assert JSON `status: FAILURE` and `reason` lists missing section. Write `test_constitution_post_valid_manifest()` — mock git, invoke post with valid manifest, assert exit 0. Write `test_constitution_post_invalid_sections()` — invoke with manifest referencing missing section, assert non-zero exit.
    - **Green**: Create `constitution_app` Typer in `cli/constitution.py`. `pre` command: resolve `specs/constitution.md` via `resolve_constitution(Path.cwd())`, validate via `validate_constitution()`, extract commands via `extract_commands()`, emit JSON contract. If `validate_constitution()` returns False, emit `{"status": "FAILURE", "reason": "..."}`. Check for required sections (`## TESTING_PROTOCOLS`) — if absent, include in `reason`. `post` command: accept manifest path argument, validate section structure from manifest against actual constitution file, if valid call `commit_artifact()` to commit. Register in `cli/__init__.py` via `cli.add_typer(constitution_app, name="constitution")`.
    - **Refactor**: Use `with_json_quiet` from `_common.py` for `--json`/`--quiet` flag support on both commands. Extract JSON emission into a shared `_emit_contract()` helper. Match existing CLI error formatting patterns from `cli/context.py` or `cli/adhoc.py`.
    - **Edge Cases**: Constitution file exists but is empty → FAILURE (handled by `validate_constitution`). `constitution post` with non-existent manifest path → clear error. `constitution post` with no git changes → commit_artifact handles gracefully. Multiple `--json`/`--quiet` flag combinations follow FR-009 orthogonality.
    - **Acceptance**: AC-005-01, AC-005-02 pass. `constitution pre` emits correct JSON. Missing file → FAILURE with reason. Missing section → FAILURE with section listed. `constitution post` validates and commits. All pre-existing tests pass.

## Phase 3: Inspection CLI — Issues List + Tasks List
**Goal**: Create `deviate issues list` and `deviate tasks list` commands with Rich table rendering, `--json` mode, status/type filtering, and orphan claim detection for SPECIFIED issues. Add `filter_tasks()` query helper to `state/ledger.py`.

### Tasks

- TSK-004-03: Inspection CLI — Issues List, Tasks List, Orphan Detection
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_inspect.py tests/test_state/test_ledger.py -v --no-header -q`
  - **Estimated Time**: 90 minutes
  - **Dependency**: TSK-004-01 (uses `filter_tasks()` pattern)
  - **Files**:
    - `src/deviate/cli/inspect.py` (NEW)
    - `src/deviate/state/ledger.py` (MODIFY)
    - `src/deviate/cli/__init__.py` (MODIFY)
    - `tests/test_cli/test_inspect.py` (NEW)
    - `tests/test_state/test_ledger.py` (MODIFY)
  - **Rationale**: US-003 (FR-006) requires `issues list` to parse `specs/issues.jsonl` bottom-up with `--type`, `--status`, `--json` filters, and detect orphan claims on SPECIFIED issues via `git ls-remote --heads` (scenarios 1-7). US-004 (FR-006) requires `tasks list` to parse the active issue's `tasks.jsonl` with status derivation (scenarios 8-10). Both share the `_read_ledger_strict()` parser — `filter_tasks()` extends the ledger module for task filtering. Orphan claim detection adds `git ls-remote` integration with three outcomes: true (branch missing), false (branch exists), null (remote unreachable). Registration in `cli/__init__.py` makes both commands discoverable.
  - **Details**:
    - **Red**:
      *Issues list*: Write `test_issues_list_json()` — seed `specs/issues.jsonl` with 3 issues, invoke `runner.invoke(app, ["issues", "list", "--json"])`, assert valid JSON array. Write `test_issues_list_empty_ledger()` — no ledger file, invoke, assert `[]`. Write `test_issues_list_orphan_claim_detected()` — seed 1 SPECIFIED issue, mock `detect_remote()` returning `"origin"`, mock `subprocess.run` for `git ls-remote --heads` to return no match (branch absent), assert `"orphan_claim": true`. Write `test_issues_list_orphan_claim_branch_exists()` — same setup but `git ls-remote` returns the branch, assert `"orphan_claim": false`. Write `test_issues_list_orphan_claim_remote_unreachable()` — mock `subprocess.run` side effect with `CalledProcessError`, assert `"orphan_claim": null`. Write `test_issues_list_type_status_filter()` — seed mixed types/statuses, invoke with `--type feature --status BACKLOG`, assert filtered. Write `test_issues_list_malformed_jsonl_fails()` — seed malformed JSONL, invoke, assert non-zero exit.
      *Tasks list*: Write `test_tasks_list_status_filter()` — seed `tasks.jsonl` with PENDING/IN_PROGRESS/COMPLETED, invoke `runner.invoke(app, ["tasks", "list", "--status", "PENDING"])`, assert only PENDING in Rich table. Write `test_tasks_list_json()` — seed 3 tasks, invoke with `--json`, assert valid JSON array. Write `test_tasks_list_empty_ledger()` — no tasks.jsonl, invoke, assert empty result (not error).
      *Ledger helpers*: Write `test_filter_tasks_by_status()` — seed tasks.jsonl with mixed statuses, call `filter_tasks(ledger_path, LedgerFilter(status="PENDING"))`, assert only pending returned. Write `test_filter_tasks_empty()` — no ledger, assert empty list.
    - **Green**: Add `filter_tasks(ledger_path: Path, filter: LedgerFilter) -> list[TaskRecord]` to `state/ledger.py` — follows `filter_issues()` pattern using `_read_ledger_strict()`, deduplicates by `id`, applies `type`/`status` predicates. Add `_derive_issue_branch(source_file: str) -> str` helper that calls `_resolve_bucket_dir()` and `_source_stem()` from `meso.py` to construct `feat/<epic>/<issue>` branch name. Add `_check_orphan_claim(issue: IssueRecord, repo: Path) -> bool | None` — calls `detect_remote()` from `worktree.py`, runs `git ls-remote --heads <remote> <branch>` via `subprocess.run`; on success returns `True` (branch missing) or `False` (exists); on subprocess error returns `None`. Wire these into `issues list` command. Create `inspect_app` Typer in `cli/inspect.py`. `issues list` command: read ledger via `_read_ledger_strict()`, apply `LedgerFilter` dedup logic, for SPECIFIED issues call orphan check, render Rich table or JSON array. `tasks list` command: resolve active issue directory, read `tasks.jsonl`, apply `LedgerFilter` with `filter_tasks()`, render Rich table or JSON. Register `inspect_app` in `cli/__init__.py`.
    - **Refactor**: Extract Rich table rendering into `_render_issues_table(records)` and `_render_tasks_table(records)` helpers for testability. Extract `_build_orphan_field()` to centralize the True/False/Null logic for both Rich and JSON output modes. Reuse `_json_emit()` pattern from existing commands. Ensure `detect_remote()` is imported from `core/worktree.py` (not re-implemented).
    - **Edge Cases**: Ledger file missing → empty list (not error). SPECIFIED issue without `source_file` → skip orphan check (no crash). Remote unreachable via network error → `orphan_claim: null`, not crash. Multiple SPECIFIED issues → each checked independently. `git ls-remote` timeout → caught by subprocess timeout, returns `None` gracefully. `--json` with empty result → valid `[]` array. Malformed JSONL → fail on first malformed line per HITL decision.
    - **Acceptance**: AC-006-01 through AC-006-04 pass. `filter_tasks()` returns correct filtered results. Orphan claim produces three distinct states (true/false/null). Empty ledgers produce empty results. Malformed JSONL fails on first error. All pre-existing tests pass.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (Seed Audit) → Phase 2 (Constitution CLI) can start in parallel
2. Phase 3 (Inspection CLI) starts after Phase 1 provides `filter_tasks()` pattern
3. All phases can be parallelized since they touch distinct file sets

**Critical Dependency Chains**:
- TSK-004-03 (Inspection CLI) uses the `filter_tasks()` pattern enabled by `_read_ledger_strict()` which is already in the codebase; no strict dependency on TSK-004-01

**Risk Hotspots**:
- `git ls-remote --heads` in orphan claim detection introduces network dependency in tests — all calls must be mocked via `@patch("subprocess.run")`
- `cli/__init__.py` registration — both TSK-004-02 and TSK-004-03 add `add_typer` lines; additive only, no conflict
- `with_json_quiet` decorator from `_common.py` must be imported correctly in both new CLI modules
- Rich table rendering in tests requires `sys.stdout` capture rather than string assertion — prefer JSON mode for deterministic test assertions
- The `_read_ledger()` function currently skips malformed lines with warnings (line 310 in ledger.py); `issues list` must use `_read_ledger_strict()` instead to fail on first malformed line per HITL decision

**Merge Conflict Boundaries**:
- `src/deviate/cli/__init__.py` — touched by TSK-004-02 (constitution_app registration) and TSK-004-03 (inspect_app registration). Lines are additive with no overlap (`add_typer` calls appended at the bottom).
- `tests/test_state/test_ledger.py` — touched by TSK-004-01 (placeholder audit) and TSK-004-03 (filter_tasks). These add different test classes, no overlap.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use the shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `cwd=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **CLI Test Pattern**: Use `typer.testing.CliRunner` with `runner.invoke(cli, [...])` for CLI tests. Use `@patch` to mock external subprocess calls (git, pytest) to prevent real execution.
- **Performance**: Every test that would trigger `_run_pytest()` subprocess (not applicable to these tasks — no micro-layer commands) must mock it. Full test suite contribution < 5s total.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def detect_remote(repo: Path | None = None) -> str:
    repo = repo or Path.cwd()

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def detect_remote() -> str:  # BAD — untestable
    ...
```
