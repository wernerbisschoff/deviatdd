# Implementation Tasks: `feat/adhoc/029-ponytail-pruning-in-review`

## Phase 1: Fold ponytail ladder into review prompt
**Goal**: Review scan cites the ponytail ladder with no new command file

### Tasks

- TSK-029-01: Fold ponytail pre-write ladder into deviate-review Pragmatism domain
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_meso/test_auto_prompt_templates.py -q`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-review.md`
    - `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Rationale**: `US-029-01` pruning lives in the review prompt fold target; `AC-PLAN-001` needs ladder text present and headings absent, `AC-PLAN-002` needs the keep-tests-green no-helper disposition pinned in the same template test
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_meso/test_auto_prompt_templates.py` only — forbid `tests/integration` / e2e in this RED. Assert ladder text present on the drift line, no `deviate-ponytail` file reference, no Minimality heading, and no shared-helper promotion
    - **Green**: Extend the drift line at `src/deviate/prompts/commands/deviate-review.md:82` with the explicit pre-write ladder; keep heading set unchanged
    - **Refactor**: Align ladder wording with existing prompt idioms per constitution §1
    - **Edge Cases**: Handle ladder text drifting into a new heading by pinning heading absence; reject malformed titles via negative pins
    - **Acceptance**: Ladder cited by findings, prompt pins pass, heading set unchanged

---

The next GREEN attempt must: extend the Cross-task over-engineering drift line in src/deviate/prompts/commands/deviate-review.md with the ponytail pre-write ladder (YAGNI, stdlib, platform feature, already-installed dep, one line, minimum that works); add no new heading and no deviate-ponytail file reference; then run uv run pytest tests/unit/test_meso/test_auto_prompt_templates.py -q until the ladder test passes.
  - **Judge Feedback**: COMPLIANCE_VIOLATION: GREEN is empty while the RED test genuinely fails, so the required behavior is missing.
  - **Judge Feedback**: The next GREEN attempt must: extend the existing drift line at src/deviate/prompts/commands/deviate-review.md line 82 so it cites every ladder rung (yagni, stdlib, platform feature, already-installed, one line, minimum that works) on that same line. Keep the heading set unchanged, keep Cross-task over-engineering text, add no Minimality/Constraints heading and no deviate-ponytail reference. Then run uv run pytest tests/unit/test_meso/test_auto_prompt_templates.py -q -k Ponytail with behavioral markers enabled; the no-collect in RED was marker filtering, not a passing suite.
  - **Judge Feedback**: The next GREEN attempt must: extend the Cross-task over-engineering drift line in src/deviate/prompts/commands/deviate-review.md with the ponytail pre-write ladder (YAGNI, stdlib, platform feature, already-installed dep, one line, minimum that works); add no new heading and no deviate-ponytail file reference; then run uv run pytest tests/unit/test_meso/test_auto_prompt_templates.py -q until the ladder test passes.
## Phase 2: PR title and body squash-merge compliance
**Goal**: Compound-prefix titles squash-merge as valid conventional commits on both platforms

### Tasks

- TSK-029-02: Fix compound-prefix PR title strip and pin body push options
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_meso.py tests/unit/test_meso/test_pr_platform.py -q`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/unit/test_meso/test_pr_platform.py`
    - `tests/unit/test_cli/test_meso.py`
  - **Rationale**: `US-029-02` squash-merge lives in `_pr_title` and the platform push paths; `AC-PLAN-003` needs compound-prefix title form plus body-as-commit-body on GitHub and GitLab paths
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_meso/test_pr_platform.py` and `tests/unit/test_cli/test_meso.py` only — forbid `tests/integration` / e2e in this RED. Assert compound-prefix titles strip to conventional form, body file passes through `gh` unchanged, and empty body omits the GitLab description option; mock `deviate.cli.micro._run_pytest` on CLI paths that spawn it
    - **Green**: Widen `_pr_title` prefix-strip in `src/deviate/cli/meso.py` to cover compound prefixes; keep `_gitlab_push_options` and `_run_gh_pr_create` transport paths unchanged
    - **Refactor**: Reuse `commit_scope` helper verbatim; no new dependencies
    - **Edge Cases**: Handle empty body by omitting description option; keep existing adhoc and numbered scope pins green
    - **Acceptance**: Title matches conventional-commit form on both paths, body serves as squash-merge body, all scope pins pass
  - **Dependency**: TSK-029-01

---

## Phase 3: Mirror specs and changelog
**Goal**: Spec mirror and changelog record the folded pruning in the same commit

### Tasks

- TSK-029-03: Document folded pruning and squash behavior in specs and changelog
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Test Strategy**: unit
  - **Verification**: `mise run check`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: Constitution §5 requires spec and changelog mirrors for user-visible changes; `AC-PLAN-001` through `AC-PLAN-003` change review and PR behavior the specs describe
  - **Details**:
    - **Implementation**: Record folded pruning in review contract sections; record verified squash-convention title and body behavior in PR sections; add one `[Unreleased]` bullet covering review pruning and any title fix
    - **Refactor**: Keep body format stable; change prose only, no contract reshaping
    - **Edge Cases**: Handle contract gap by updating `deviate-pr.md` reference only if verification exposes one
    - **Acceptance**: Specs describe folded pruning, changelog bullet present, `mise run check` passes
  - **Dependency**: TSK-029-02

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 (Logical dependency order)

**Critical Dependency Chains**:
- TSK-029-01 must precede TSK-029-02
- TSK-029-02 must precede TSK-029-03

**Risk Hotspots**:
- Ladder text drifts into a new heading; pin heading absence in the template test
- Title fix breaks existing scope pins; keep existing scope tests green while adding compound-prefix cases

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none (each phase owns disjoint files)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
