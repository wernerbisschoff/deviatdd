# Implementation Tasks: feat/adhoc/004-deviate-review-skill

## Phase 1: CLI Scaffold — review.py Module + Subcommand Registration
**Goal**: Create the `src/deviate/cli/review.py` Typer module with skeleton pre/post commands and register it as `deviate review` in the CLI tree (covers US-005-CLI_REGISTRATION).

### Tasks

- TSK-004-01: Create review.py module with pre/post stubs and register review subcommand
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `deviate review --help 2>&1 | grep -E "pre|post"`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/cli/review.py`
    - `src/deviate/cli/__init__.py`
  - **Rationale**: `review.py` is the primary architectural workstation for the review subcommand (US-005, AC-005-1/2). `__init__.py` requires a single `cli.add_typer(review_app, name="review")` line plus import. Both files must exist before any pre/post logic can be implemented.
  - **Details**:
    - **Implementation**: Create `src/deviate/cli/review.py` with `review_app = typer.Typer(no_args_is_help=True)`, empty `pre()` command returning `{"status": "READY"}` contract, and empty `post()` command printing `[green]OK[/] no-op`. Both commands use `typer.Option`/`typer.Argument` patterns consistent with existing `feature.py` and `adhoc.py`.
    - **Implementation**: Add `from deviate.cli.review import review_app` and `cli.add_typer(review_app, name="review")` to `src/deviate/cli/__init__.py` after the existing `feature_app` group.
    - **Edge Cases**: Ensure `review_app` uses `no_args_is_help=True` so bare `deviate review` shows help. Verify no circular import by running `python -c "from deviate.cli import cli"`.
    - **Acceptance**: `deviate review --help` prints `pre` and `post` subcommands. `deviate review pre` emits a JSON contract with `"status": "READY"`.

---

## Phase 2: Pre Command — Contract Emission, Git Diff, Constitution Detection
**Goal**: Implement `deviate review pre` with git state gathering, diff generation against merge-base with `main`, constitution discovery, and JSON contract emission (covers US-001-PRE_COMMAND scenarios 1, 2, 3, 9).

### Tasks

- TSK-004-02: Implement pre command core — contract emission, git diff, constitution path resolution
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_review.py::test_review_pre_emits_contract tests/test_cli/test_review.py::test_review_pre_finds_constitution tests/test_cli/test_review.py::test_review_pre_diff_against_main tests/test_cli/test_review.py::test_review_pre_empty_diff -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/review.py`
    - `tests/test_cli/test_review.py`
  - **Rationale**: `review.py` is the implementation workstation for all pre command logic (US-001, AC-001-1/2/3/9). `tests/test_cli/test_review.py` is the mandatory test file for all review unit tests, covering contract shape, constitution path, and diff computation.
  - **Details**:
    - **Red**: Write `test_review_pre_emits_contract()` asserting `deviate review pre` (via `runner.invoke`) produces valid JSON with `status`, `diff`, `constitution_path`, `prd_path`, `base_branch`, `report_exists`, `timestamp` keys. Mock git state using `tmp_git_repo` fixture and `_git_env()`.
    - **Red**: Write `test_review_pre_finds_constitution()` asserting contract `constitution_path` points to `.resolve()` of `specs/constitution.md`. Create a dummy `specs/constitution.md` in `tmp_git_repo`.
    - **Red**: Write `test_review_pre_diff_against_main()` asserting contract `diff` field contains unified diff of staged/unstaged changes against merge-base with `main`. Stage a change in `tmp_git_repo`, commit on a branch, verify diff present.
    - **Red**: Write `test_review_pre_empty_diff()` asserting contract emitted with `diff` empty string when branch has no changes versus merge-base with `main`.
    - **Green**: Implement `pre()` command in `review.py` using `subprocess.run(["git", "merge-base", "main", "HEAD"], cwd=repo, ...)` and `subprocess.run(["git", "diff", merge_base, "HEAD"], cwd=repo, ...)` with `capture_output=True, text=True`. Use `repo_path=Path.cwd()` default with optional override. Gather `constitution_path` by checking `specs/constitution.md` existence. Compute `diff` via `git diff {merge_base}..HEAD`.
    - **Green**: Implement contract emission as JSON dict with keys: `status: "READY"`, `diff` (str), `constitution_path` (str | None), `prd_path` (None for now), `base_branch: "main"`, `report_exists: False`, `timestamp` (ISO 8601).
    - **Refactor**: Extract `_compute_merge_base(commit_a, commit_b, repo)` and `_gather_diff(base, head, repo)` helpers from inline git calls. Use `_git_env()` from `deviate.core._shared` for all git subprocess calls.
    - **Edge Cases**: Handle `git merge-base` when `main` branch doesn't exist yet (fallback to `HEAD` diff). Handle missing `specs/constitution.md` gracefully (set `constitution_path` to `null`).
    - **Acceptance**: 4 unit tests passing. Contract always emitted even with empty diff. Constitution path resolved as absolute path when file exists.

- TSK-004-03: Implement pre command advanced — PRD resolution, report_exists check, custom --base, self-contained --branch mode
  - **Judge Feedback**: The next GREEN attempt must address two issues:
    - **Judge Feedback**: 
    - **Judge Feedback**: 1. RESTORE micro.py: Revert the changes to `src/deviate/cli/micro.py`. The break, the `[red]Pipeline halted` print, and the `monitor.push_event("pipeline_halted", ...)` call must all be restored. The defensive exclusions in spec.md explicitly prohibit modifying the TDD cycle body in `micro.py`. If removing the pipeline halt is intentional, it must be a separate task with its own spec amendment.
    - **Judge Feedback**: 
    - **Judge Feedback**: 2. ADD constitution_warning field: In `_resolve_constitution_path` or in the contract construction at `pre()`, add a `constitution_warning` field set to `true` when `constitution_path` is `None`. The spec US-006-AC-2 requires: "When no specs/constitution.md is found, the contract's constitution_path is null and a constitution_warning: true field is emitted." Update the contract dict to include:
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_review.py::test_review_pre_resolves_prd_epic_first tests/test_cli/test_review.py::test_review_pre_falls_back_to_adhoc_prd tests/test_cli/test_review.py::test_review_pre_no_prd_warning tests/test_cli/test_review.py::test_review_pre_custom_base tests/test_cli/test_review.py::test_review_pre_existing_report_warning -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-004-02
  - **Files**:
    - `src/deviate/cli/review.py`
    - `tests/test_cli/test_review.py`
  - **Rationale**: Extends the pre command with PRD anchoring (US-001, AC-001-4/5/6), report existence detection (AC-001-7), custom base branch override (AC-001-8), and self-contained branch-targeted mode (US-006, AC-006-1/2). All logic lives in `review.py`; the test file extends with 5 additional test cases.
  - **Details**:
    - **Red**: Write `test_review_pre_resolves_prd_epic_first()` — create both `specs/{epic}/prd.md` and `specs/adhoc/prd.md` in `tmp_git_repo`, assert `prd_path` in contract points to epic PRD.
    - **Red**: Write `test_review_pre_falls_back_to_adhoc_prd()` — create only `specs/adhoc/prd.md` in `tmp_git_repo`, assert `prd_path` points to adhoc PRD.
    - **Red**: Write `test_review_pre_no_prd_warning()` — no PRD files in `tmp_git_repo`, assert `prd_warning: true` and `prd_path: null` with exit code 0.
    - **Red**: Write `test_review_pre_custom_base()` — invoke `deviate review pre --base develop`, assert diff computed against merge-base with `develop` instead of `main`.
    - **Red**: Write `test_review_pre_existing_report_warning()` — create `.deviate/review/reports/` directory with existing file in `tmp_git_repo`, assert `report_exists: true` in contract.
    - **Green**: Implement PRD resolution in `pre()`: check `specs/{epic_slug}/prd.md` first (resolve epic_slug from branch name `feat/{epic}/{slug}`), then check `specs/adhoc/prd.md`, set `prd_warning: true` if neither found.
    - **Green**: Implement `--base` Typer option: `base: str = typer.Option("main", "--base")`, pass to merge-base computation.
    - **Green**: Implement `--branch` Typer option for US-006: `branch: str | None = typer.Option(None, "--branch")` triggers diff of specified branch against its merge-base with `main`.
    - **Green**: Implement `report_exists` check: glob `.deviate/review/reports/*.md`, set `report_exists: True` if any match found.
    - **Refactor**: Extract `_resolve_prd(branch_name, repo)` function returning `(prd_path, prd_warning)`. Extract `_check_existing_reports(repo)` returning `bool`.
    - **Edge Cases**: Handle branch name without `feat/{epic}/{slug}` pattern (no epic derived — skip epic PRD check). Handle `--base` combined with `--branch` (use branch's merge-base against specified base).
    - **Acceptance**: 5 unit tests passing. All PRD resolution strategies verified. Custom base flag changes diff target. Report warning emitted without error.

---

## Phase 3: Post Command — Report Persistence to .deviate/review/reports/
**Goal**: Implement `deviate review post` with deterministic report file writing to `.deviate/review/reports/review-report-{timestamp}.md`, no-commit enforcement, and graceful handling of missing artifact (covers US-004-POST_COMMAND).

### Tasks

- TSK-004-04: Implement post command — report persistence with no-commit enforcement
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_cli/test_review.py::test_review_post_persists_report tests/test_cli/test_review.py::test_review_post_no_artifact tests/test_cli/test_review.py::test_review_post_no_commit -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-004-01
  - **Files**:
    - `src/deviate/cli/review.py`
    - `tests/test_cli/test_review.py`
  - **Rationale**: Post command is the second half of the review lifecycle (US-004, AC-004-1/2/3/4). `review.py` holds all post logic. `test_review.py` adds 3 tests for report writing, directory creation, no-commit enforcement, and graceful no-op.
  - **Details**:
    - **Red**: Write `test_review_post_persists_report()` — invoke `deviate review post` with report content, assert file written to `.deviate/review/reports/review-report-{timestamp}.md` with matching content.
    - **Red**: Write `test_review_post_no_artifact()` — invoke `deviate review post` with no report content, assert exit code 0 and graceful no-op message.
    - **Red**: Write `test_review_post_no_commit()` — invoke `deviate review post` with valid report, assert `git status --porcelain` shows no staged or committed changes (report is in `.deviate/` which should be gitignored or explicitly unstaged).
    - **Green**: Implement `post()` command accepting report content via `content: str = typer.Argument(None, help="Report markdown content")`. Generate timestamp with `datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")`.
    - **Green**: Create `.deviate/review/reports/` directory via `Path.mkdir(parents=True, exist_ok=True)`. Write report as `review-report-{timestamp}.md`.
    - **Green**: Implement no-op branch: when content is `None` or empty, print `[yellow]SKIP[/] no report content provided` and exit 0.
    - **Green**: After writing report, execute `git status --porcelain .deviate/review/reports/` and verify `.deviate/` is gitignored or not staged — do NOT run `git add`. Print warning if report appears in staged changes.
    - **Refactor**: Extract `_generate_timestamp()` and `_reports_dir(repo) -> Path` helpers. Use `Path` for all filesystem operations.
    - **Edge Cases**: Handle existing report directory gracefully (append, don't overwrite — timestamp ensures uniqueness). Handle `OSError` on write (permission denied) with clear error message.
    - **Acceptance**: 3 unit tests passing. Report written to correct path with timestamp. No git operations performed. Graceful no-op when no content.

---

## Phase 4: Review Prompt — SKILL.md with Domain Rubrics and Report Schema
**Goal**: Create the `deviate-review` skill prompt with all six domain rubrics (Security, Pragmatism, Idiomacy, Clean Code, Constitution, PRD), execution sequence, report output schema, and edge case handling (covers US-002-SKILL_PROMPT, US-003-REPORT_FORMAT).

### Tasks

- TSK-004-05: Create SKILL.md prompt with full domain rubrics and report schema
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `python -c "from deviate.core.skills import discover_skills; skills = discover_skills(); assert 'deviate-review' in skills, f'Skill not found: {skills}'; print('OK')"`
  - **Estimated Time**: 45 minutes
  - **Dependency**: TSK-004-01
  - **Files**:
    - `src/deviate/prompts/skills/deviate-review/SKILL.md`
  - **Rationale**: The SKILL.md is the execution prompt for the review agent (US-002, US-003). It must exist before `deviate init` can auto-discover it via `discover_skills()`. No code changes required — this is a pure prompt document following the same frontmatter convention as existing skills (e.g., `deviate-execute/SKILL.md`).
  - **Details**:
    - **Implementation**: Create `src/deviate/prompts/skills/deviate-review/SKILL.md` with YAML frontmatter (`name: deviate-review`, `description`, `category: deviattd-meso-layer`, `version: 1.0.0`, `aliases: [review, /deviate-review]`).
    - **Implementation**: Define `<system_instructions>` with `[ROLE_DEFINITION]` describing the review agent as a CODE_REVIEW_SPECIALIST operating in the DeviaTDD meso layer.
    - **Implementation**: Document execution sequence under `[EXECUTION_SEQUENCE]`: `deviate review pre` (read contract) → domain analysis → report generation → user selection → fix implementation → `deviate review post`.
    - **Implementation**: Define six domain rubrics under `[DOMAIN_RUBRICS]`: Security (injection, secrets, privilege escalation), Pragmatism (proportionality, YAGNI), Idiomacy (Python/Typer conventions per constitution §2), Clean Code (naming, cohesion, complexity), Constitution (validate against each invariant in `[1_ARCHITECTURAL_PRINCIPLES]` through `[5_APPENDIX]`), PRD (trace each code change to upstream FR).
    - **Implementation**: Define report output schema under `[OUTPUT_SCHEMA]`: `# Review Report: {issue_id}` → `## Files Reviewed` → `## Constitution Compliance` (PASS/WARN/FAIL per invariant) → `## PRD Traceability` → `## Domain Findings` (subsection per domain with verdict + evidence) → `## Fix Instructions` (numbered steps in code blocks) → `## Summary`.
    - **Implementation**: Add edge case handling (empty diff, no constitution, no PRD, external repo) matching the spec's `SELF_CONTAINED_MODE` user story.
    - **Implementation**: Add integration instructions documenting how `discover_skills()` auto-installs the skill into agent directories during `deviate init`.
    - **Acceptance**: `discover_skills()` returns `deviate-review` in its list. SKILL.md passes basic structural validation (has frontmatter, has `<system_instructions>`, has all 6 rubrics).

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (CLI Scaffold) → Phase 2 (Pre Command) → Phase 3 (Post Command) → Phase 4 (Review Prompt)

**Critical Dependency Chains**:
- TSK-004-01 (review.py shell + registration) must precede TSK-004-02 and TSK-004-03 (pre command logic)
- TSK-004-02 (pre core) must precede TSK-004-03 (pre advanced) — both share `review.py`
- TSK-004-01 must precede TSK-004-04 (post command) and TSK-004-05 (SKILL.md)

**Risk Hotspots**:
- Git subprocess calls in pre command must use `_git_env()` to strip ambient `GIT_*` env vars per constitution §1 Git Isolation Principle
- PRD resolution must handle branch names without `feat/{epic}/{slug}` structure (e.g., bare `main` or `develop`)
- Report files under `.deviate/` must be explicitly gitignored or never staged — any accidental commit would break the advisory-only contract

**Merge Conflict Boundaries**:
- `src/deviate/cli/review.py` — touched by TSK-004-01, TSK-004-02, TSK-004-03, TSK-004-04 (sequential execution avoids conflicts)
- `tests/test_cli/test_review.py` — touched by TSK-004-02, TSK-004-03, TSK-004-04 (sequential addition of test cases)

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push, merge-base, diff) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or the shared `tmp_git_repo` fixture from `tests/conftest.py`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use the `tmp_git_repo` fixture (which calls `git init` inside `tmp_path`, configures a test user, and returns the `Path`). Pass `cwd=tmp_git_repo` and `env=_git_env()` to all git subprocess calls. Import `_git_env` from `tests.conftest`. Never reference `Path.cwd()`, `os.getcwd()`, or the real repo root in tests.
- **Performance Mocking**: Never call `_run_pytest()` from `deviate.cli.micro` in tests. Tests that invoke CLI commands which internally call `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value. Full suite target < 18s.
- **Pre-script Pattern**: All tests that invoke `runner.invoke(cli, ["review", "pre"])` must do so from inside a test environment (using `CliRunner` from `typer.testing`), not by shelling out to the real CLI. The worktree discovery should be mocked when testing the pre command in isolation.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in `review.py` MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the sole enabler of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def _compute_merge_base(commit_a: str, commit_b: str, repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    result = subprocess.run(["git", "merge-base", commit_a, commit_b], cwd=repo, ...)

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def _compute_merge_base(commit_a, commit_b):  # BAD — untestable
    ...
```
