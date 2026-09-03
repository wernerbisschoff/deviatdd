# Implementation Tasks: `feat/adhoc/036-cli-help-readme-transparency`

## Phase 1: Help pinning plus README transparency token
**Goal**: Pin `micro run --help` wording with a failing-then-passing test and name `COVERAGE_INCOMPLETE` in the README review row plus a CHANGELOG bullet

### Tasks

- TSK-036-01: Pin fast-skip and review-pause wording in micro run help
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_cli/test_help.py`
    - `src/deviate/cli/micro.py`
  - **Rationale**: `US-036-02` plus `AC-PLAN-002` require `deviate micro run --help` to keep the pinned `Execution profile: full, fast` substring, state `fast` skips JUDGE and REFACTOR, and state `--review` is a TTY pause before the phase commit and not `/deviate-review`; the test file carries the RED and `micro.py` carries the GREEN (expected no-op).
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/` only — forbid `tests/test_integration` and `tests/e2e` in this RED. Assert `deviate micro run --help` output contains the `Execution profile: full, fast` substring, a `fast`-skips-JUDGE statement, and a `--review` pause-not-`/deviate-review` statement via Typer `CliRunner` against `deviate.cli:cli`
    - **Green**: Implement no production change if the current `--profile` and `--review` help strings already satisfy the assertions; change only the help strings in `src/deviate/cli/micro.py::run_command` if the test finds a gap. GREEN cannot edit tests.
    - **Refactor**: Align new test style with existing substring assertions in `test_help.py`; keep assertions wrapping-safe
    - **Edge Cases**: Handle Rich terminal wrapping by asserting short substrings rather than full lines
    - **Acceptance**: `mise unit` passes, including `tests/unit/test_core/test_profile.py::test_help_lists_only_full_and_fast`

- TSK-036-02: Name COVERAGE_INCOMPLETE in README review row and record CHANGELOG bullet
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise unit`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `README.md`
    - `CHANGELOG.md`
  - **Rationale**: `US-036-01` plus `AC-PLAN-001` and `US-036-03` plus `AC-PLAN-003` require the README phase-transparency review row to name `COVERAGE_INCOMPLETE` as the `review pre` fail-closed token while keeping comments-only default and not-a-merge-gate wording; `CHANGELOG.md` carries the user-visible docs entry.
  - **Details**:
    - **Implementation**: Add `COVERAGE_INCOMPLETE` to the README review row as the `review pre` fail-closed token; verify the transparency table still answers every fact the issue lists; append one bullet under `CHANGELOG.md` `[Unreleased]`; touch no other README rows and never open `src/deviate/cli/review.py`, `src/deviate/cli/walkthrough.py`, or sibling prompt files
    - **Refactor**: Keep table formatting and line width consistent with sibling rows
    - **Edge Cases**: Handle Quickstart pin test breakage by running `tests/unit/test_cli/test_setup.py::TestReadmeNewUserPath` before done
    - **Acceptance**: `mise unit` passes for `test_help.py`, `test_profile.py`, and `TestReadmeNewUserPath`; `mise run check` passes; no sibling review or walkthrough runtime file is modified
  - **Dependency**: TSK-036-01

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 executes TSK-036-01 then TSK-036-02 (test pin first, docs second)

**Critical Dependency Chains**:
- TSK-036-01 must precede TSK-036-02

**Risk Hotspots**:
- README edit breaks the Quickstart pin test; mitigated by running `TestReadmeNewUserPath` before done
- Help test brittleness across Rich wrapping; mitigated with substring assertions
- Accidental edits to sibling review or walkthrough runtime; mitigated by touching only the README review row

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
