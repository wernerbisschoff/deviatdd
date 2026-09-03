# Implementation Tasks: `feat/adhoc/037-setup-pack-tui-multiselect`

## Phase 1: TTY checklist pin plus changelog
**Goal**: Pin the TTY checkbox pack picker with mocked-TUI tests and record the user-visible change

### Tasks

- TSK-037-01: Pin TTY empty-confirm and product plus pr picks with mocked-TUI unit tests
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_setup.py tests/unit/test_ui/test_checkbox.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_cli/test_setup.py`
    - `src/deviate/cli/__init__.py`
    - `src/deviate/ui/checkbox.py`
  - **Rationale**: `tests/unit/test_cli/test_setup.py` pins `US-037-01` via `AC-PLAN-001` (empty confirm installs default layers only) and `AC-PLAN-002` (product plus pr picks install those two packs only); `src/deviate/cli/__init__.py` owns the TTY routing under test (`_ask_optional_pack_picks`, `_packs_from_selector_picks`, `_prompt_pack_selection`); `src/deviate/ui/checkbox.py` owns the `checkbox_select` loop contract, adjusted only if a defect surfaces
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/` only — forbid `tests/integration` and `tests/e2e` in this RED. Mock `deviate.cli._ask_optional_pack_picks` to return `[]` and assert setup installs macro plus meso plus micro commands with no optional pack files (`AC-PLAN-001`); mock it to return `product` plus `pr` picks and assert setup installs the product pack commands plus `deviate-pr` only and writes no pack selection into `config.toml` (`AC-PLAN-002`); assert existing `parse_optional_packs` cases (`pr,review`, `all-optional`, `none`, unknown fails closed) and non-TTY omitted-packs default-only still pass as regression (`AC-PLAN-003`, `AC-PLAN-004`); assert invocation plus installed files only, never rendered glyphs or help strings
    - **Green**: Keep `checkbox_select` as the sole TTY picker in `src/deviate/ui/checkbox.py`; keep omitted-`--packs` on a TTY routed through it in `src/deviate/cli/__init__.py`; implement the minimum wiring fix only if a RED case exposes a defect — GREEN never edits tests
    - **Refactor**: Align touched lines with ruff format and existing prompt-helper idioms; no new dependencies, no Textual, stay on Typer plus Rich
    - **Edge Cases**: Handle unknown `--packs` names by failing closed; handle non-TTY omitted `--packs` by installing default-only without blocking on key input; handle leftover Enter by flushing pending input before the checkbox loop
    - **Acceptance**: `uv run pytest tests/unit/test_cli/test_setup.py tests/unit/test_ui/test_checkbox.py -v` passes; no slash-separated `Prompt.ask` remains on the pack path

- TSK-037-02: Record TTY picker change under CHANGELOG Unreleased
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `grep -A5 Unreleased CHANGELOG.md && mise run check`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `CHANGELOG.md`
    - `specs/adhoc/037-setup-pack-tui-multiselect/plan.md`
  - **Rationale**: `CHANGELOG.md` records the user-visible TTY picker change for `US-037-01` via `AC-PLAN-002`; `specs/adhoc/037-setup-pack-tui-multiselect/plan.md` is the source of the entry wording (Implementation Strategy and Acceptance Contract), read for accuracy, not rewritten
  - **Details**:
    - **Implementation**: Append one bullet under `CHANGELOG.md` `[Unreleased]` stating setup on a TTY picks optional packs with a checkbox multi-select (Space toggles, Enter confirms) instead of a comma-separated prompt; keep the entry to one line tied to `AC-PLAN-002`
    - **Refactor**: Match surrounding bullet style and wrapping; touch no other sections
    - **Edge Cases**: Handle missing `[Unreleased]` heading by adding it; never duplicate an existing entry for this issue
    - **Acceptance**: `grep -A5 Unreleased CHANGELOG.md` shows the new bullet; `mise run check` passes
  - **Dependency**: TSK-037-01

- TSK-037-03: [E2E] Verify setup pack install surface end to end
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: e2e
  - **Verification**: `mise run test && mise run test-e2e`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `tests/e2e/test_setup_config_rework.bats`
    - `tests/e2e/test_derived_command_install.bats`
  - **Rationale**: `tests/e2e/test_setup_config_rework.bats` exercises the setup happy path (`US-037-02` script and non-TTY paths unchanged via `AC-PLAN-003` and `AC-PLAN-004`); `tests/e2e/test_derived_command_install.bats` proves installed command files land correctly after pack selection (`US-037-01` TTY picks via `AC-PLAN-001` and `AC-PLAN-002`)
  - **Details**:
    - **Implementation**: Run the existing e2e setup and command-install bats files unmodified; assert the happy path (default layers install, named packs install) plus one critical failure (unknown `--packs` name fails closed); write no new e2e files and create no test files outside `tests/e2e/`
    - **Refactor**: No production code changes in this task; report defects instead of fixing them here
    - **Edge Cases**: Handle non-TTY CI execution by asserting setup never blocks on key input
    - **Acceptance**: `mise run test` and `mise run test-e2e` both pass
  - **Dependency**: TSK-037-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 TSK-037-01 -> TSK-037-02 -> TSK-037-03 (linear dependency chain)

**Critical Dependency Chains**:
- TSK-037-01 must precede TSK-037-02
- TSK-037-02 must precede TSK-037-03

**Risk Hotspots**:
- Raw terminal mode leaves stdin altered on error — try-finally termios restore covers it
- Leftover Enter from a prior prompt confirms an empty checklist — input drain covers it

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none (each production file has one writer; TSK-037-02 reads `plan.md` without rewriting it)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
