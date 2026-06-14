# Implementation Tasks: feat/001-deviate-cli-python/008-meso-macro-automated-orchestration

## Phase 1: Slim Prompt Templates & Assembly Service
**Goal**: Create the 6 slim prompt template files and the assembly service that loads them, injects constitution/CLAUDE.md, and produces ready-to-send prompts for the agent backends.

### Tasks

- TSK-008-01: Create slim prompt templates for all six meso/macro phases
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `ls src/deviate/prompts/auto/explore.md src/deviate/prompts/auto/research.md src/deviate/prompts/auto/prd.md src/deviate/prompts/auto/shard.md src/deviate/prompts/auto/specify.md src/deviate/prompts/auto/tasks.md`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/auto/explore.md`
    - `src/deviate/prompts/auto/research.md`
    - `src/deviate/prompts/auto/prd.md`
    - `src/deviate/prompts/auto/shard.md`
    - `src/deviate/prompts/auto/specify.md`
    - `src/deviate/prompts/auto/tasks.md`
  - **Rationale**: US-003 requires six slim prompt templates in `src/deviate/prompts/auto/`. Each template must follow the static-prefix + dynamic-suffix KV-cacheable pattern. These files are consumed by the assembly service (TSK-008-02) and by both meso and macro pipelines.
  - **Judge Feedback**: Fix inject_constitution() in src/deviate/prompts/assembly.py:
    - **Judge Feedback**: 
    - **Judge Feedback**: 1. Wrap constitution_path.read_text() in try/except (FileNotFoundError,
    - **Judge Feedback**:    PermissionError, OSError) — log a warning via logger.warning() with
    - **Judge Feedback**:    the message "CONSTITUTION_MISSING: {path}: {error}", then continue
    - **Judge Feedback**:    without appending constitution content.
    - **Judge Feedback**: 
    - **Judge Feedback**: 2. Match existing pattern: CLAUDE.md uses .exists() as a guard (line 33);
    - **Judge Feedback**:    apply the same defensive guard or equivalent try/except for
    - **Judge Feedback**:    constitution_path.
    - **Judge Feedback**: 
    - **Judge Feedback**: 3. Verify both missing CLAUDE.md and missing constitution work
    - **Judge Feedback**:    independently and together (constitution missing + claude present,
    - **Judge Feedback**:    both missing, both present).
    - **Judge Feedback**: 
    - **Judge Feedback**: Expected behavior:
    - **Judge Feedback**: - constitution missing → warning logged, prompt assembled without it
    - **Judge Feedback**: - constitution unreadable → warning logged, prompt assembled without it
    - **Judge Feedback**: - CLAUDE.md missing → silent skip (already works)
    - **Judge Feedback**: - Neither exists → raw template returned unchanged
    - **Judge Feedback**: - Both exist → both prepended with \n\n separators (already works)
  - **Details**:
    - **Implementation**: Create `explore.md` — instructs agent to scan codebase and produce explore.md with problem context and repo structure.
    - **Implementation**: Create `research.md` — instructs agent to consume explore.md and produce design.md + data-model.md with trade-off analysis.
    - **Implementation**: Create `prd.md` — instructs agent to consume design.md + data-model.md and produce prd.md with FR requirements and Gherkin ACs.
    - **Implementation**: Create `shard.md` — instructs agent to consume prd.md and produce shard issue files with dependency topology.
    - **Implementation**: Create `specify.md` — instructs agent to consume issue body + PRD reqs and produce spec.md with Gherkin blocks.
    - **Implementation**: Create `tasks.md` — instructs agent to consume spec.md and produce tasks.md with TDD task decomposition.
    - **Acceptance**: Each file exists, is non-empty markdown, and follows the static-prefix (role constraints) + dynamic-suffix (`<context>`) structure matching ISS-001-004 slim prompts.

- TSK-008-02: Implement prompt assembly service with constitution injection
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_meso/test_prompt_assembly.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: TSK-008-01
  - **Files**:
    - `src/deviate/prompts/assembly.py`
    - `tests/test_meso/test_prompt_assembly.py`
  - **Rationale**: US-004 requires constitution and CLAUDE.md injection into every automated prompt. US-003 AC-3 requires `TEMPLATE_MISSING` error for missing templates. This module provides `load_template(template_name)`, `inject_constitution(prompt, const_path, claude_path)`, and `assemble_prompt(template_name, context_vars)` functions consumed by both meso and macro pipelines.
  - **Details**:
    - **Red**: Write `test_load_template_success()` — asserts `load_template("specify")` returns non-empty string matching expected static prefix pattern.
    - **Red**: Write `test_load_template_missing_raises()` — asserts `load_template("nonexistent")` raises `FileNotFoundError`.
    - **Red**: Write `test_inject_constitution_appends_content()` — asserts `inject_constitution()` prepends constitution content before the dynamic suffix marker.
    - **Red**: Write `test_inject_constitution_missing_claude_skips()` — asserts `inject_constitution()` skips CLAUDE.md injection silently when file is absent, returning the prompt unchanged.
    - **Green**: Implement `load_template(template_name: str) -> str` in `assembly.py` — reads template via `importlib.resources.files("deviate.prompts.auto")`, raises `FileNotFoundError` if missing.
    - **Green**: Implement `inject_constitution(prompt: str, constitution_path: Path, claude_path: Path) -> str` — reads both files, prepends content as KV-cacheable prefix region. Skips missing claude.md silently.
    - **Green**: Implement `assemble_prompt(template_name: str, context: dict, constitution_path: Path, claude_path: Path) -> str` — chains `load_template` + `inject_constitution`, interpolates `${PLACEHOLDER}` vars from context dict.
    - **Refactor**: Extract `_resolve_template_path()` helper for testability. Use `importlib.resources.as_file` for platform-safe resource resolution.
    - **Edge Cases**: Handle empty template files (return empty string + emit warning). Handle binary/unreadable constitution (catch `PermissionError`, emit warning, continue).
    - **Acceptance**: All prompt assembly functions are unit-tested. `load_template` resolves from both user override paths and package defaults.

---

## Phase 2: Automated Pipeline Commands
**Goal**: Implement `deviate meso` (specify→tasks) and `deviate macro` (explore→research→prd→shard) as full automated pipeline commands.

### Tasks

- TSK-008-03: Implement `deviate meso` automated pipeline command
  - **Judge Feedback**: The _meso_run() function must call the existing pre/post functions
    - **Judge Feedback**: in the correct order:
    - **Judge Feedback**: 
    - **Judge Feedback**: 1. Call _specify_pre(issue_id=..., force=force, dry_run=dry_run)
    - **Judge Feedback**:    before the SPECIFY agent invocation to set up worktree and session.
    - **Judge Feedback**: 
    - **Judge Feedback**: 2. After SPECIFY agent invocation with manifest.status == "PASS",
    - **Judge Feedback**:    call _specify_post(force=force) to validate spec.md Gherkin syntax,
    - **Judge Feedback**:    commit the artifact, and advance session to TASKS.
    - **Judge Feedback**: 
    - **Judge Feedback**: 3. Call _tasks_pre(force=force, dry_run=dry_run) before the TASKS
    - **Judge Feedback**:    agent invocation (already done).
    - **Judge Feedback**: 
    - **Judge Feedback**: 4. After TASKS agent invocation with manifest.status == "PASS",
    - **Judge Feedback**:    call _tasks_post(force=force, issue_id=issue_id) to validate tasks.md
    - **Judge Feedback**:    content, commit the artifact, and advance session to IDLE.
    - **Judge Feedback**: 
    - **Judge Feedback**: 5. Add blocking-dependency validation for explicit --issue targets
    - **Judge Feedback**:    (currently only auto-discovery filters blocked issues).
    - **Judge Feedback**: 
    - **Judge Feedback**: 6. Update tests to assert the call sequence — mock/patch _specify_pre,
    - **Judge Feedback**:    _specify_post, _tasks_post and verify they are called with correct
    - **Judge Feedback**:    arguments. Each test must assert the full pre→agent→post sequence,
    - **Judge Feedback**:    not just final session state.
    - **Judge Feedback**: 
    - **Judge Feedback**: 7. Add tests for:
    - **Judge Feedback**:    - Blocking dependency rejection with --issue
    - **Judge Feedback**:    - NO_UNBLOCKED_ISSUES error (auto-discovery path)
    - **Judge Feedback**:    - --force guard bypass in meso pipeline context
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_meso/test_meso_orchestration.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: TSK-008-02
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_meso/test_meso_orchestration.py`
  - **Rationale**: US-001 requires `deviate meso` to sequence _specify_pre → agent (slim prompt) → _specify_post → _tasks_pre → agent (slim prompt) → _tasks_post. US-005 (recovery) requires resuming at interrupted phase. US-006 (dry-run) requires stdout-only emission. US-007 (force) requires bypassing pre-flight guards. These are all additions to `src/deviate/cli/meso.py`.
  - **Details**:
    - **Red**: Write `test_meso_full_pipeline_success()` — mocks `_invoke_agent`, asserts pipeline calls pre→agent→post in correct order, session ends in IDLE.
    - **Red**: Write `test_meso_specific_issue()` — asserts `deviate meso --issue ISS-001-004` targets specific issue, skipping discovery.
    - **Red**: Write `test_meso_issue_progress_reset()` — asserts PROGRESS issue resets to SPECIFY and re-runs, discarding stale artifacts.
    - **Red**: Write `test_meso_completed_issue_aborts()` — asserts COMPLETED issue emits `ISSUE_COMPLETED` and exits non-zero.
    - **Red**: Write `test_meso_dry_run_no_side_effects()` — asserts `--dry-run` emits contract+prompts to stdout, does not create worktree or advance session.
    - **Red**: Write `test_meso_recovery_skip_specify()` — asserts existing spec.md causes SPECIFY skip, pipeline resumes at TASKS.
    - **Red**: Write `test_meso_agent_failure_aborts()` — asserts agent non-zero exit aborts pipeline with phase-context error.
    - **Green**: Implement `meso_typer` app with `callee` subcommand (or inline `_meso_run()`) that sequences pre→agent→post using existing `_specify_pre`, `_specify_post`, `_tasks_pre`, `_tasks_post`. Accept `--issue`, `--dry-run`, `--force`.
    - **Green**: Add `_build_slim_prompt(phase: str, contract: dict) -> str` helper that loads template via `assembly.assemble_prompt()` and injects contract context.
    - **Green**: Add `_meso_discover_and_sequence()` — discovers unblocked BACKLOG, loops candidates, calls `_meso_run_single_issue()` for first successful claim.
    - **Refactor**: Extract `_meso_phase_runner(phase_fn, post_fn, prompt_template, session)` to reduce duplication between SPECIFY and TASKS phases.
    - **Edge Cases**: Handle no unblocked issues (`NO_UNBLOCKED_ISSUES`). Handle blocked-by dependency check. Handle `--force` on push failure for claim.
    - **Acceptance**: Full meso pipeline executes end-to-end with mocked agent. Dry-run produces zero side effects. Interrupted runs resume correctly. All error paths exit with specific error codes.

- TSK-008-04: Implement `deviate macro` automated pipeline command
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_macro/test_macro_orchestration.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: TSK-008-02
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/test_macro/test_macro_orchestration.py`
  - **Rationale**: US-002 requires `deviate macro` to sequence explore_pre→agent→explore_post→research_pre→agent→research_post→prd_pre→agent→prd_post→shard_pre→agent→shard_post. US-005 (resume via `--from`) and US-006 (dry-run) are macro-specific behaviors. All additions target `src/deviate/cli/macro.py`.
  - **Details**:
    - **Red**: Write `test_macro_full_pipeline_success()` — mocks agent, asserts all four phases run in order: explore→research→prd→shard, session ends in IDLE, shard issues registered in ledger.
    - **Red**: Write `test_macro_from_prd_resume()` — asserts `--from prd` skips explore and research, generates prd.md via agent, and proceeds through shard.
    - **Red**: Write `test_macro_invalid_from_phase()` — asserts `--from invalid_phase` emits `INVALID_PHASE` with valid options.
    - **Red**: Write `test_macro_bucket_not_found()` — asserts `--target nonexistent-slug` emits `BUCKET_NOT_FOUND`.
    - **Red**: Write `test_macro_dry_run_no_artifacts()` — asserts `--dry-run` emits contracts/prompts to stdout, no files created, no ledger mutations.
    - **Red**: Write `test_macro_upstream_missing_aborts()` — asserts missing explore.md at RESEARCH phase boundary emits `UPSTREAM_MISSING` and aborts.
    - **Green**: Implement `macro_typer` app with `callee` subcommand (or inline `_macro_run()`) that sequences all four phases. Accept `--target`, `--from`, `--dry-run`, `--force`.
    - **Green**: Implement `_macro_discover_bucket()` — resolves `--target` slug, validates bucket exists. If no `--target`, uses `discover_latest_epic()`.
    - **Green**: Implement `_macro_phase_sequencer()` — walks from the first required phase (or `--from` phase) through the remaining phases, calling pre→agent→post for each with appropriate slim prompt templates.
    - **Refactor**: Extract `_macro_prompt_map` dict mapping phase names to template names, and `_macro_phase_order` list for sequencing.
    - **Edge Cases**: Handle missing constitution (non-fatal warn, continue). Handle re-run with partial artifacts (session state check, skip completed phases). Handle all four phases failing independently.
    - **Acceptance**: Full macro pipeline executes end-to-end with mocked agent. `--from` resume skips completed phases. Dry-run produces zero side effects. Missing upstream artifacts halt with specific error.

---

## Phase 3: CLI Registration & Integration Verification
**Goal**: Wire the new meso and macro commands into the CLI tree and verify the full integration cycle.

### Tasks

- TSK-008-05: Register `meso` and `macro` commands in CLI tree and run integration verification
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_integration/test_meso_orchestration.py tests/test_integration/test_macro_orchestration.py -v`
  - **Estimated Time**: 30 minutes
  - **Dependency**: TSK-008-03, TSK-008-04
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/test_integration/test_meso_orchestration.py`
    - `tests/test_integration/test_macro_orchestration.py`
  - **Rationale**: US-001 through US-007 all require the `meso` and `macro` commands to be accessible via `deviate meso` and `deviate macro`. Registration in `__init__.py` is the final wiring step. Integration tests validate the full cycle with mocked agents and real session state transitions.
  - **Details**:
    - **Implementation**: Import `meso_app` and `macro_app` from respective modules and register via `cli.add_typer(meso_app, name="meso")` and `cli.add_typer(macro_app, name="macro")` in `src/deviate/cli/__init__.py`.
    - **Implementation**: Write `test_meso_integration_full_pipeline()` — uses `CliRunner` to invoke `deviate meso --dry-run`, asserts correct stdout contract format and zero side effects.
    - **Implementation**: Write `test_macro_integration_full_pipeline()` — uses `CliRunner` to invoke `deviate macro --target my-feature --dry-run`, asserts correct stdout contract format.
    - **Implementation**: Write `test_meso_integration_no_unblocked_issues()` — sets up empty ledger, asserts `NO_UNBLOCKED_ISSUES` error.
    - **Implementation**: Write `test_macro_integration_bucket_not_found()` — invokes with nonexistent slug, asserts `BUCKET_NOT_FOUND` error.
    - **Acceptance**: Both commands visible in `deviate --help`. Integration tests pass with mocked agent. All CLI flags accepted and validated.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (Templates + Assembly) → Phase 2 (Meso + Macro) → Phase 3 (Registration + E2E)

**Critical Dependency Chains**:
- TSK-008-01 (Templates) → TSK-008-02 (Assembly)
- TSK-008-02 (Assembly) → TSK-008-03 (Meso) and TSK-008-04 (Macro)
- TSK-008-03 + TSK-008-04 → TSK-008-05 (Registration)

**Risk Hotspots**:
- Assembly service must match the resource loading pattern used by `_read_seed` in `cli/__init__.py` — use `importlib.resources.files("deviate.prompts.auto")` for consistency
- `deviate meso` must handle the case where `_specify_pre` already created the worktree — avoid double-creation
- `deviate macro --from` must map phase names to correct pre/post functions — a mis-mapping would skip artifact validation
- Agent invocation uses `AgentBackend.invoke()` from `src/deviate/core/agent.py` — all pipeline tasks must mock this in tests

**Merge Conflict Boundaries**:
- `src/deviate/cli/__init__.py` — touched by TSK-008-05 only (registration at bottom of file)
- `src/deviate/cli/meso.py` — touched by TSK-008-03 only (adds `meso_typer` app, no changes to existing functions)
- `src/deviate/cli/macro.py` — touched by TSK-008-04 only (adds `macro_typer` app, no changes to existing functions)
- `src/deviate/prompts/auto/` — touched by TSK-008-01 only (new template files)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Mock Agent Invocations**: All pipeline tests MUST mock `deviate.core.agent.AgentBackend.invoke` to avoid real subprocess calls. Use:
  ```python
  from unittest.mock import patch, MagicMock
  mock_invoke = patch("deviate.core.agent.AgentBackend.invoke", return_value=MagicMock(status="PASS"))
  ```
- **Mock `_run_pytest`**: Pipeline tests that trigger post-command validation MUST NOT call `_run_pytest` (which triggers the full test suite). Mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value.
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
