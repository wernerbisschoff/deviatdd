# Implementation Tasks: feat/002-deviatdd-gap-analysis/003-fast-path-commands

## Phase 1: Complexity Gate & Adhoc Record Model
**Goal**: Foundational data model and classification engine for the adhoc fast-path. `ComplexityGate.classify()` provides the Tier-1 gate that routes tasks to DIRECT or TDD execution modes. `AdhocRecord` provides the append-only persistence schema.

### Tasks

- TSK-003-01: ComplexityGate classification engine + AdhocRecord Pydantic model
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_complexity.py tests/test_state/test_ledger.py -v --no-header -q`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/complexity.py` (NEW)
    - `src/deviate/state/ledger.py` (MODIFY)
    - `tests/test_core/test_complexity.py` (NEW)
    - `tests/test_state/test_ledger.py` (MODIFY)
  - **Rationale**: `ComplexityGate.classify()` is the core classification engine for US-001 through US-004. `AdhocRecord` is the data schema for persisting adhoc task records used by US-005 and US-006. Both are foundational — the CLI layer in Phase 2 depends on them.
  - **Details**:
    - **Red**: Write `test_complexity_gate_classify_low` — assert `ComplexityGate.classify("Fix typo", _stub="LOW")` returns `ClassificationResult(level="LOW", execution_mode="DIRECT")`. Write `test_complexity_gate_classify_medium` — assert `execution_mode="DIRECT"`, `level="MEDIUM"`. Write `test_complexity_gate_classify_high` — assert `execution_mode="TDD"`, `level="HIGH"`. Write `test_adhoc_record_schema` — assert `AdhocRecord(issue_id="adhoc-001", description="Fix typo").execution_mode == "DIRECT"` with proper defaults. Write `test_adhoc_record_status_transitions` — assert valid status values and Pydantic `ValidationError` for invalid.
    - **Green**: Implement `ComplexityGate.classify(description: str, _stub: str | None = None) -> ClassificationResult` — return dataclass with `level` and `execution_mode`. Stub bypasses LLM for deterministic testing. Implement `AdhocRecord(BaseModel)` with fields: `issue_id`, `description` (`min_length=1`), `execution_mode` (`Literal["DIRECT", "TDD"]`), `status` (`Literal["PENDING", "COMPLETED"]`), `timestamp` (auto `datetime.now`).
    - **Refactor**: Match existing `IssueRecord`/`TaskRecord` conventions — `model_config = {"extra": "forbid"}`, field ordering, `datetime` defaults with `timezone.utc`.
    - **Edge Cases**: Unknown `_stub` value raises `ValueError`. Empty `description` rejected by Pydantic. `issue_id` must be non-empty string.
    - **Acceptance**: 5 tests pass. Classification stub covers all 3 tiers. AdhocRecord validates, serializes, and round-trips through JSON correctly. Zero lint violations.

## Phase 2: Adhoc CLI Commands
**Goal**: User-facing `deviate adhoc pre` and `deviate adhoc post` commands that consume ComplexityGate and AdhocRecord. `pre` classifies, gates, and records. `post` transitions and commits.

### Tasks

- TSK-003-02: Adhoc CLI — pre (classification + record) and post (completion + validation)
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_adhoc.py -v --no-header -q`
  - **Estimated Time**: 90 minutes
  - **Dependency**: TSK-003-01
  - **Files**:
    - `src/deviate/cli/adhoc.py` (NEW)
    - `src/deviate/cli/__init__.py` (MODIFY)
    - `tests/test_cli/test_adhoc.py` (NEW)
  - **Rationale**: CLI commands are the user-facing interface for US-001 through US-006. `adhoc pre` implements US-001 (LOW→DIRECT), US-002 (MEDIUM→DIRECT), US-003 (HIGH rejection), US-004 (HIGH with `--skip-gates`). `adhoc post` implements US-005 (PENDING→COMPLETED) and US-006 (`MANIFEST_NOT_FOUND` error). Registration in `cli/__init__.py` makes `deviate adhoc` discoverable.
  - **Details**:
    - **Red**: Write `test_adhoc_pre_low_complexity` — `@patch("deviate.cli.adhoc.ComplexityGate.classify")` returns LOW, invoke `runner.invoke(cli, ["adhoc", "pre", "Fix typo"])`, assert stdout contains `DIRECT` and exit 0. Write `test_adhoc_pre_medium_complexity` — similar with MEDIUM. Write `test_adhoc_pre_high_complexity_rejected` — mock HIGH, no `--skip-gates`, assert non-zero exit + `COMPLEXITY_GATE_REJECTION`. Write `test_adhoc_pre_high_complexity_skip_gates` — mock HIGH, with `--skip-gates`, assert exit 0. Write `test_adhoc_post_completes_record` — pre-seed `specs/adhoc.jsonl` with PENDING record, invoke post with that ID, assert COMPLETED. Write `test_adhoc_post_missing_manifest` — invoke post with unknown ID, assert `MANIFEST_NOT_FOUND` + non-zero exit.
    - **Green**: Create `adhoc_app` Typer in `adhoc.py`. `pre` command: parse description string, call `ComplexityGate.classify()`, check gate rejection for HIGH without `--skip-gates`, append `AdhocRecord` to `specs/adhoc.jsonl` (auto-create file if missing), emit JSON contract to stdout. `post` command: read `specs/adhoc.jsonl`, find record by `issue_id`, transition to COMPLETED, write updated record, save session to IDLE. Register in `cli/__init__.py` via `cli.add_typer(adhoc_app, name="adhoc")`.
    - **Refactor**: Extract `_read_adhoc_ledger(path) -> list[AdhocRecord]` and `_append_adhoc_record(record, path)` helpers. Match existing CLI error formatting patterns from meso commands. Use `with_json_quiet` decorator pattern for JSON/quiet flag handling.
    - **Edge Cases**: `specs/adhoc.jsonl` missing on first `pre` call → auto-create file with directory. Session save on `post` fails → non-zero exit. Duplicate manifest IDs in ledger → match last occurrence.
    - **Acceptance**: All 6 test cases pass. LOW/MEDIUM→DIRECT. HIGH without flags→rejected. HIGH with `--skip-gates`→proceeds. Post completes valid records, errors on missing IDs. Lint clean.

## Phase 3: Feature Workspace Scaffold
**Goal**: `deviate feature create <title> [--slug]` command that creates directory structure, git branch, and session state for new feature development.

### Tasks

- TSK-003-03: Feature Create CLI — directory scaffold, branch creation, session update
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_feature.py -v --no-header -q`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/feature.py` (NEW)
    - `src/deviate/cli/__init__.py` (MODIFY)
    - `tests/test_cli/test_feature.py` (NEW)
  - **Rationale**: Feature workspace scaffold implements US-007 (new feature scaffold), US-008 (existing branch idempotency), and US-009 (explicit `--slug` override). Directory creation (`specs/{SLUG}/`), git branch (`feat/{SLUG}`), and session update are the three unit operations. Registration in `cli/__init__.py` makes `deviate feature create` discoverable.
  - **Details**:
    - **Red**: Write `test_feature_create_scaffold` — in `tmp_git_repo`, invoke `runner.invoke(cli, ["feature", "create", "auth overhaul"])`, assert `specs/auth-overhaul/` directory exists, branch `feat/auth-overhaul` exists (via `git branch --list` in `tmp_git_repo`), and session file contains updated state. Write `test_feature_create_existing_branch` — pre-create branch, invoke command again, assert idempotent (no error, exit 0). Write `test_feature_create_explicit_slug` — invoke `["feature", "create", "auth overhaul", "--slug", "user-auth"]`, assert `specs/user-auth/` exists, branch is `feat/user-auth`.
    - **Green**: Create `feature_app` Typer with `create` command accepting `<title>` argument and optional `--slug` option. Implement `_derive_slug(title: str) -> str`: lowercase, replace non-alphanumeric with hyphens, strip leading/trailing hyphens. Check branch existence via `git rev-parse --verify`. Create `specs/{SLUG}/` with `Path.mkdir(parents=True)`. Create branch via `git checkout -b feat/{SLUG}` (using `cwd=repo_path`). Update session via `SessionState.save()`. Register in `cli/__init__.py` via `cli.add_typer(feature_app, name="feature")`.
    - **Refactor**: Use `git_env()` from `src/deviate/core/_shared.py` for all git subprocess calls. Extract `_create_feature_branch(slug, repo_path)` and `_create_feature_directory(slug, repo_path)` helpers.
    - **Edge Cases**: Title with special characters (`"auth! overhaul?"`) → sanitized to `"auth-overhaul"`. `--slug` with leading hyphens → strip silently. Session write failure → non-zero exit with clear error. Branch creation failure (git error) → non-zero exit.
    - **Acceptance**: All 3 test cases pass. All git operations use `cwd=tmp_git_repo` for test isolation. Slug derivation matches URL-safe kebab-case. Existing branch is idempotent. Explicit `--slug` overrides derivation.

## Phase 4: Specify Pre Integration
**Goal**: Existing `deviate specify pre` automatically invokes feature creation when no active session exists, enabling the US-010 flow.

### Tasks

- TSK-003-04: Specify Pre — auto-invoke feature create when session absent
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_meso.py -v --no-header -q -k test_specify_pre_invokes_feature_create`
  - **Estimated Time**: 30 minutes
  - **Dependency**: TSK-003-03
  - **Files**:
    - `src/deviate/cli/meso.py` (MODIFY)
    - `tests/test_cli/test_meso.py` (MODIFY)
  - **Rationale**: US-010 requires `specify pre` to auto-scaffold a feature workspace when no session exists. This modifies the `_specify_pre` function in `meso.py` to add a conditional branch. Test validates the integration — `specify pre` without session should result in a feature workspace.
  - **Details**:
    - **Red**: Write `test_specify_pre_invokes_feature_create` — in `tmp_git_repo` with no session and pre-seeded issue ledger, invoke `runner.invoke(cli, ["specify", "pre", "--issue", issue_id])`, mock `_run_pytest` (to avoid subprocess), assert that a `specs/{SLUG}/` directory was created as a side effect of feature creation, and session file exists with updated phase.
    - **Green**: In `_specify_pre()`, at the start before worktree/claim logic, check if session exists via `SessionState.load(repo_path)`. If session is absent (no `.deviate/session.json` or `current_phase == "IDLE"` with no `active_issue_id`), import and call the feature creation flow. Pass through to normal specify pre logic after feature is created.
    - **Refactor**: Extract the "ensure session exists" logic into `_ensure_session_or_create_feature(repo_path, issue_data)` shared helper to avoid duplication between `specify pre` and standalone `feature create`.
    - **Edge Cases**: Feature creation succeeds but specify pre fails later → feature workspace exists, error is surfaced. Feature creation fails → specify pre exits non-zero with clear diagnostic. Session already exists → no-op (fall through to normal flow).
    - **Acceptance**: Test passes. `specify pre` without a session auto-scaffolds a feature workspace. Existing sessions are unaffected. NO changes to micro-layer TDD cycle (per Defensive Exclusions).

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (Complexity Gate + Model) → Phase 2 (Adhoc CLI)
2. Phase 3 (Feature Create) → Phase 4 (Specify Pre Integration)
3. Phases 1+2 and Phase 3 are independent and can be parallelized.

**Critical Dependency Chains**:
- TSK-003-02 (Adhoc CLI) → requires TSK-003-01 (Complexity Gate + Model)
- TSK-003-04 (Specify Pre) → requires TSK-003-03 (Feature Create)

**Risk Hotspots**:
- `src/deviate/cli/meso.py` modify touches existing production code — regression risk on existing specify pre behaviour. Ensure mock `_run_pytest` is used in tests.
- `specs/adhoc.jsonl` auto-creation path must be robust against missing parent directories.
- Git branch operations in feature create must use `_git_env()` to avoid GIT_* env contamination in tests.

**Merge Conflict Boundaries**:
- `src/deviate/cli/__init__.py` — modified by both Phase 2 and Phase 3 (appending different `add_typer` lines). Conflict is additive (no overlap) but needs sequential application.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use the shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `cwd=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **CLI Test Pattern**: Use `typer.testing.CliRunner` with `runner.invoke(cli, [...])` for CLI tests. Use `@patch` to mock `deviate.cli.micro._run_pytest` (and any external subprocess calls) to prevent real subprocess execution.
- **Performance**: Every test must mock `_run_pytest` when the CLI command calls it internally. Full test suite contribution must be < 5s total.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function must accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the sole enabler of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```
