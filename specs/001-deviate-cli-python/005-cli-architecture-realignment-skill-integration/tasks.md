# Implementation Tasks: feat/001-deviate-cli-python/005-cli-architecture-realignment-skill-integration

## Phase 1: Data Model Fixes and Core Foundation
**Goal**: Fix critical IssueRecord schema bugs, implement shared core infrastructure and domain modules

### Tasks

- [x] T001: Fix IssueRecord Schema, Malformed JSONL Recovery, and Key Lookup Mismatches
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test -- tests/test_core/test_ledger.py tests/test_state/test_ledger.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/test_core/test_ledger.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: `ledger.py` contains the broken `IssueRecord` Pydantic model with wrong field names (`id` instead of `issue_id`, missing `type`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp`) and a key-lookup bug in `resolve_issue_record`. US-001-DATA Scenarios 1-3 require: malformed-line skip-warn recovery, schema realignment, and key fix.
  - **Details**:
    - **Red**: Write test `test_issue_record_schema_realignment()` asserting `IssueRecord` accepts fields `issue_id`, `type`, `status`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp` and rejects unknown fields via `extra="forbid"`. Write `test_malformed_jsonl_skip_with_warning()` asserting `_read_ledger` returns valid records while emitting `UserWarning` for unparseable lines. Write `test_resolve_issue_record_by_issue_id()` asserting lookup on `issue_id` (not `id`).
    - **Green**: Add `BACKLOG` to `IssueRecord.status` Literal. Replace `id: str` with `issue_id: str`. Add `type: str`, `source_file: str`, `blocked_by: list[str] = []`, `coordinates_with: list[str] = []`, `timestamp: datetime` fields. Remove `epic_slug` and `issue_slug` (replaced by `source_file`). Update `resolve_issue_record` to match on `data.get("issue_id")` instead of `data.get("id")`. Update `append_issue_record` idempotency check to use `issue_id`.
    - **Refactor**: Align `_read_ledger` warning message to include line number context. Remove unused `fcntl` import if no longer needed after consolidation.
    - **Edge Cases**: Handle lines where `issue_id` is missing (skip with warning). Handle `coordinates_with` as optional empty list when absent.
    - **Acceptance**: `python -c "import json; [json.loads(l) for l in open('specs/issues.jsonl')]"` succeeds without exception. All existing `test_ledger.py` tests pass after schema migration.

- [x] T002: Implement Core Infrastructure Modules (repo, contract, commit, constitution, validation, worktree)
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test -- tests/test_core/test_repo.py tests/test_core/test_contract.py tests/test_core/test_commit.py tests/test_core/test_constitution.py tests/test_core/test_validation.py tests/test_core/test_worktree.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `tests/conftest.py` (shared `tmp_git_repo` fixture — create first)
    - `src/deviate/core/repo.py`
    - `src/deviate/core/contract.py`
    - `src/deviate/core/commit.py`
    - `src/deviate/core/constitution.py`
    - `src/deviate/core/validation.py`
    - `src/deviate/core/worktree.py`
    - `tests/test_core/test_repo.py`
    - `tests/test_core/test_contract.py`
    - `tests/test_core/test_commit.py`
    - `tests/test_core/test_constitution.py`
    - `tests/test_core/test_validation.py`
    - `tests/test_core/test_worktree.py`
  - **Rationale**: US-002-CORE Scenarios 1, 3, 4 require repo root detection, git state gathering, JSON contract round-trip, stage-and-commit workflows, constitution command extraction, spec validation, and worktree management. These 6 modules form the infrastructure foundation all downstream layers depend on.
  - **Git Isolation**: Per `Universal API Design Constraint`, all git-interacting functions accept `repo_path` parameter. Tests use `tmp_git_repo` conftest fixture. No test references the real repo's `.git`.
  - **Details**:
    - **Red**: Write `test_find_repo_root_from_subdir(tmp_git_repo)` asserting repo root is the `.git` parent; `test_contract_round_trip()` asserting emit/load preserves all keys; `test_stage_and_commit_creates_commit(tmp_git_repo)` asserting a file is committed and SHA returned; `test_extract_test_command_from_constitution()` asserting `constitution.md` section body is extracted; `test_validate_gherkin_syntax_valid_block()` asserting Given/When/Then detection; `test_create_worktree_returns_path(tmp_git_repo)` asserting worktree creation on new branch.
    - **Green**: Create `tests/conftest.py` with shared `tmp_git_repo` fixture (calls `git init` inside `tmp_path`, configures `runner@test.local` / `Test Runner` as test user, creates initial commit). Every `git` subprocess call MUST pass BOTH `cwd=tmp_path` AND `env=_git_env()` (a helper that strips `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` from environment — otherwise pre-commit hooks will leak the real repo). Implement `find_repo_root(start_at: Path | None = None)` via upward `.git` directory walk and `gather_git_state(repo: Path | None = None)` via `git status --porcelain`. Implement `emit_contract(data: dict) -> Path` and `load_contract(path: Path) -> dict` with JSON round-trip. Implement `stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str` and `commit_artifact(path: Path, message: str, repo: Path | None = None) -> str` via subprocess `git add`/`git commit`. Implement `resolve_constitution() -> Path` finding `specs/constitution.md`, `validate_constitution(path: Path) -> bool`, and `extract_commands() -> dict[str, str]`. Implement `extract_section_body(content: str, header: str) -> str` and `validate_gherkin_syntax(content: str) -> list[str]`. Implement `create_worktree(branch: str, path: Path, repo: Path | None = None) -> Path`, `detect_worktree(repo: Path | None = None) -> dict`, and `validate_worktree(path: Path) -> bool`.
    - **Refactor**: Use `shlex.quote` for all git subprocess calls. Ensure all path operations return `Path` objects, not strings.
    - **Edge Cases**: Handle detached HEAD in `gather_git_state`; handle missing `.git` directory (not a repo); handle `constitution.md` not found; handle empty spec sections; handle worktree path already in use.
    - **Acceptance**: All 6 test files pass independently. `commit_artifact` creates a real git commit visible in `git log`.

- [x] T003: Implement Core Domain Modules (issues, epic, prd, skills) and Fix macro.py Artifact Check
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test -- tests/test_core/test_issues.py tests/test_core/test_epic.py tests/test_core/test_prd.py tests/test_core/test_skills.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/core/issues.py`
    - `src/deviate/core/epic.py`
    - `src/deviate/core/prd.py`
    - `src/deviate/core/skills.py`
    - `tests/test_core/test_issues.py`
    - `tests/test_core/test_epic.py`
    - `tests/test_core/test_prd.py`
    - `tests/test_core/test_skills.py`
    - `src/deviate/cli/macro.py`
  - **Rationale**: US-002-CORE Scenarios 2, 5 cover issue resolution/claim/body-reading/completion-check, epic discovery/bucket allocation, PRD requirement extraction/traceability validation, and skill discovery/resolution. US-001-DATA Scenario 4 requires fixing `macro.py:prd` artifact check from `research.md` to `design.md` + `data-model.md`.
  - **Details**:
    - **Red**: Write `test_resolve_issue_returns_record()` asserting issue lookup by ID from JSONL; `test_claim_issue_updates_ledger()` asserting ledger append; `test_discover_epic_returns_slug()` asserting epic slug extraction from directory structure; `test_extract_prd_requirements_returns_fr_list()` asserting FR-NNN extraction from PRD markdown; `test_discover_skills_lists_directories()` asserting skill directory enumeration from package resources.
    - **Green**: Implement `resolve_issue(issue_id: str) -> IssueRecord`, `claim_issue(issue_id: str) -> bool`, `read_issue_body(issue_id: str) -> str`, and `is_issue_completed(issue_id: str) -> bool` in `issues.py`. Implement `discover_epic() -> str`, `allocate_feature_bucket(slug: str) -> Path`, and `resolve_active_feature() -> str` in `epic.py`. Implement `extract_prd_requirements(prd_path: Path) -> list[str]` and `validate_traceability(issue_body: str, prd_reqs: list[str]) -> dict` in `prd.py`. Implement `discover_skills() -> list[str]`, `resolve_skill(name: str) -> Path`, and `install_skill(name: str, target_dir: Path) -> bool` in `skills.py`.
    - **Green (macro.py fix)**: Change `_run_command("PRD", epic_slug, ["explore.md", "research.md"])` to check for `["design.md", "data-model.md"]` per US-001-DATA Scenario 4. Also update `_run_command("RESEARCH", epic_slug, ["explore.md"])` — ensure no accidental regression.
    - **Refactor**: Extract common JSONL reading patterns into shared helper. Use type hints consistently across all new modules.
    - **Edge Cases**: Handle missing `specs/` directory; handle empty `prd.md` (no FR lines); handle skill directory with no `SKILL.md` file; handle nested epic directories.
    - **Acceptance**: All 4 test files pass. `macro.py:prd` artifact check now gates on `design.md` + `data-model.md`. Skills discoverable from `src/deviate/prompts/skills/`.

---

## Phase 2: CLI Layer Implementation
**Goal**: Replace bash orchestrator behavior with Python pre/post subcommands for macro and meso layers

### Tasks

- [x] T004: Implement Macro Layer Pre/Post Subcommands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `mise run test -- tests/test_integration/test_macro_layer.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: T003
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/test_integration/test_macro_layer.py`
  - **Git Isolation**: Per `Universal API Design Constraint`, all functions called by macro CLI commands accept `repo_path`. Tests use `tmp_git_repo` fixture (which also sets up `.deviate/` and `specs/` dirs). The `mock_workspace` fixture can be extended to call `git init` in `tmp_path`.
  - **Rationale**: US-004-MACRO Scenarios 1-4 require full macro cycle: explore pre (constitution validation, feature bucket allocation, ledger scratch entry), explore post (content validation, commit), research pre (explore.md gate, constitution re-validation), research post (constitutional violation scan, commit), prd pre (epic slug discovery, upstream artifact resolution), prd post (manifest validation, commit), shard pre (PRD resolution, next_issue_id), shard post (shard validation, ledger registration).
  - **Details**:
    - **Red**: Write `test_explore_pre_allocates_bucket()` asserting new feature bucket directory created with registered `IssueRecord`; `test_research_pre_gates_on_explore_md()` asserting exit on missing `explore.md`; `test_prd_post_validates_manifest()` asserting manifest content validation before commit; `test_shard_post_registers_backlog_issues()` asserting issues appended to ledger with `BACKLOG` status and session resets to `IDLE`.
    - **Green**: Refactor `macro.py` from simple phase-transition stubs into full pre/post subcommands. Implement `explore_pre(problem: str, slug: str)` calling `allocate_feature_bucket`, `register_issue`, emitting JSON contract. Implement `explore_post()` validating `explore.md` content and committing via `commit_artifact`. Implement `research_pre()` calling `resolve_active_feature`, `validate_constitution`, gating on `explore.md`. Implement `research_post()` scanning for constitutional violations, committing `design.md` + `data-model.md`. Implement `prd_pre()` discovering epic slug, resolving upstream artifacts. Implement `prd_post(manifest: Path)` reading manifest, validating PRD, committing. Implement `shard_pre()` discovering epic, resolving PRD, computing `next_issue_id`. Implement `shard_post(manifest: Path)` validating shard output, registering each issue as `BACKLOG` in ledger, resetting session.
    - **Refactor**: Consolidate common pre/post patterns (artifact validation, commit, ledger update) into shared helpers in `cli/_common.py`. Align Typer commands with `app.add_typer()` pattern per design.md.
    - **Edge Cases**: Handle greenfield projects with no existing epic buckets; handle constitution not found; handle `explore.md` content validation failure; handle shard with zero issues.
    - **Acceptance**: `test_macro_layer.py` passes with coverage of all 4 macro subcommand families (explore, research, prd, shard) each testing pre and post paths.

- [/] T005: Implement Meso Layer Pre/Post Subcommands
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `mise run test -- tests/test_integration/test_meso_layer.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: T003
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `tests/test_integration/test_meso_layer.py`
  - **Git Isolation**: Per `Universal API Design Constraint`, all functions called by meso CLI commands accept `repo_path`. Tests use `tmp_git_repo` fixture. PR tests (`test_pr_run_creates_pr`) must mock `gh pr create` within `tmp_path` context — no real GitHub API calls and no real repo branches.
  - **Rationale**: US-003-MESO Scenarios 1-4 require: specify pre (auto-select next unblocked BACKLOG, worktree creation, ledger claim, spec target resolution), specify post (content validation, commit, ledger update), tasks pre (worktree detection, spec discovery, artifact discovery), tasks post (content validation, commit), pr pre (worktree validation, body gathering), pr run (PR creation, merge, COMPLETED event).
  - **Details**:
    - **Red**: Write `test_specify_pre_auto_selects_unblocked_issue()` asserting oldest unblocked `BACKLOG` issue is selected and worktree created; `test_specify_post_validates_and_commits()` asserting Gherkin validation + commit on valid spec; `test_tasks_pre_detects_worktree()` asserting existing worktree discovered without new creation; `test_pr_run_creates_pr()` asserting GitHub PR created and `COMPLETED` event appended to ledger.
    - **Green**: Refactor `meso.py` from simple stubs into full pre/post subcommands. Implement `specify_pre(issue_id: str | None, force: bool)` calling `select_next_unblocked_issue` (when no explicit ID), `create_worktree`, `claim_issue`, resolving `spec_target`, emitting JSON contract. Implement `specify_post(force: bool)` validating spec content via `validate_gherkin_syntax`, committing via `commit_artifact`, updating ledger. Implement `tasks_pre()` calling `detect_worktree`, `validate_worktree`, discovering `spec.md`, resolving artifact paths. Implement `tasks_post(force: bool)` validating tasks.md content, committing. Implement `pr_pre()` validating worktree, discovering issue, gathering body content. Implement `pr_run(body_file: Path, merge: bool, auto_merge: bool)` creating PR via `gh pr create`, optionally merging, appending `COMPLETED` status event.
    - **Refactor**: Move `_resolve_and_validate_issue` into `core/issues.py` as `resolve_issue`. Consolidate commit patterns with Phase 1 macro analogs.
    - **Edge Cases**: Handle case where no `BACKLOG` issues exist (specify pre should error gracefully); handle worktree path conflict; handle `gh` CLI not available for PR creation; handle merge conflict during auto-merge.
    - **Acceptance**: `test_meso_layer.py` passes with coverage of specify, tasks, and pr subcommand families, each testing pre and post paths.

---

## Phase 3: Skills, Init, and Session
**Goal**: Migrate skills, remove bash dependency, enhance init, and implement dual-mode session state

### Tasks

- [ ] T006: Migrate SKILL.md Files, Rewrite Invocations, and Remove Bash Scripts
  - **Type**: Migration
  - **Mode**: IMMEDIATE
  - **Verification**: `find prompts -name "*.sh" | wc -l | xargs test 0 -eq && ls src/deviate/prompts/skills/deviate-specify/SKILL.md`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T003
  - **Files**:
    - `src/deviate/prompts/skills/*/SKILL.md`
    - `prompts/**/*.sh`
    - `prompts/deviate-cycle/`
    - `.mise.toml`
    - `AGENTS.md`
  - **Rationale**: US-005-SKILLS Scenarios 1, 5, 6 require: moving SKILL.md from `prompts/<name>/SKILL.md` to `src/deviate/prompts/skills/<name>/SKILL.md`, rewriting `<SKILL_DIR>/deviate-*.sh` references to `deviate <subcommand>`, removing all `.sh` files, removing `deviate-cycle` skill, updating `.mise.toml` and `AGENTS.md`.
  - **Details**:
    - **Implementation**: For each skill directory under `prompts/` (excluding `deviate-cycle`): copy `SKILL.md` to `src/deviate/prompts/skills/<name>/SKILL.md`. Rewrite each SKILL.md to replace all `<SKILL_DIR>/deviate-*.sh` with `deviate <subcommand>` (e.g., `<SKILL_DIR>/deviate-specify.sh pre` → `deviate specify pre`). Update `[SYSTEM_TOPOLOGY_MAPPING]` sections to reference the new package path.
    - **Implementation**: Delete all `.sh` files under `prompts/`. Remove the `deviate-cycle` directory entirely. Update `.mise.toml` to remove any `.sh`-based task definitions and reference only `mise run` tasks. Update `AGENTS.md` to reflect the Python-only architecture.
    - **Refactor**: Ensure `src/deviate/prompts/skills/` directory structure mirrors the original `prompts/` layout for consistency.
    - **Edge Cases**: Handle skills with no `SKILL.md` (skip). Handle skills already partially migrated. Preserve any non-`.sh` files in skill directories.
    - **Acceptance**: `find prompts -name "*.sh"` returns zero results. All SKILL.md files in `src/deviate/prompts/skills/` reference `deviate <subcommand>` instead of shell scripts. `deviate-cycle` directory no longer exists.

- [ ] T007: Wire Agent Detection, Skill Installation, and Contract Handoff into deviate init
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `mise run test -- tests/test_integration/test_skill_installation.py tests/test_cli/test_init.py -v`
  - **Estimated Time**: 75 minutes
  - **Dependency**: T006
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `src/deviate/core/skills.py`
    - `tests/test_integration/test_skill_installation.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: US-005-SKILLS Scenarios 2-4 require init-triggered skill installation with content-hash idempotency. US-006-INIT Scenarios 1-4 require: auto-detect agents from cwd (`.claude/`, `.opencode/`, `.factory/`), `--agent` flag override, interactive fallback, and `.deviate/session.json` as default contract handoff with `.gitignore` entry.
  - **Details**:
    - **Red**: Write `test_init_installs_skills_to_agent_dirs()` asserting SKILL.md copied to detected agent paths; `test_skill_idempotency_skip_identical()` asserting skip when content hash matches; `test_skill_idempotency_overwrite_stale()` asserting overwrite when content differs; `test_auto_detect_agents_from_cwd()` asserting detection of `.claude/`, `.opencode/`, `.factory/`; `test_agent_flag_overrides_detection()` asserting `--agent opencode` ignores auto-detected agents; `test_contract_handoff_defaults_to_session_json()` asserting contract written to `.deviate/session.json` with `.gitignore` entry.
    - **Green**: In `cli/__init__.py`: extend `deviate init` to scan cwd for agent directories; add `--agent` Typer option for override; implement interactive fallback via `typer.prompt` when no agents detected. Wire `core/skills.py` `install_skill()` to copy SKILL.md files from package resources to agent-specific paths. Implement content-hash comparison using `hashlib.sha256` to determine skip vs overwrite. Set contract handoff default to `.deviate/session.json` and ensure `.gitignore` includes `.deviate/session.json`.
    - **Refactor**: Extract agent detection logic into `core/skills.py` as `detect_agents() -> list[str]`. Ensure idempotency guarantees from existing init tests are preserved.
    - **Edge Cases**: Handle agent directories that exist but are empty; handle `~/.config/opencode/skills/` directory creation when missing; handle permissions errors on skill copy; handle `--agent` with invalid agent name.
    - **Acceptance**: `test_skill_installation.py` passes all idempotency and detection scenarios. `test_cli/test_init.py` existing tests continue passing. `deviate init` installs skills without shell script dependency.

- [ ] T008: Implement Dual-Mode Session State with Divergence Detection and Worktree Reconstruction
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test -- tests/test_state/test_session.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: T003
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/test_state/test_session.py`
  - **Git Isolation**: Per `Universal API Design Constraint`, worktree detection functions accept `repo_path`. Use `tmp_git_repo` fixture for `test_session_reconstruction_from_worktree()`. No reference to the real repo's `.git`.
  - **Rationale**: US-007-SESSION Scenarios 1-4 require: dual-mode session state enforcing strict phase ordering across Macro and Meso layers, filesystem state validation detecting missing artifacts, worktree-based session reconstruction on `.deviate/session.json` loss, and task ID format normalization (accepting both `T{NNN}` and `T{NNN}:`).
  - **Details**:
    - **Red**: Write `test_strict_phase_ordering_rejects_skip()` asserting `IDLE` → `SPECIFY` is rejected per meso entry rules; `test_filesystem_divergence_detected_on_missing_artifact()` asserting `explore.md` deletion triggers clean error; `test_session_reconstruction_from_worktree()` asserting reconstitution of `SessionState` from worktree artifacts after `session.json` deletion; `test_task_id_normalization()` asserting both `T005:` and `T005` accepted.
    - **Green**: Extend `SessionState.transition_to()` with dual-mode validation: check both phase ordering (`_TRANSITION_MAP`) AND filesystem state (validate expected artifacts exist for target phase). Add `validate_filesystem_state(phase: str, epic_slug: str | None) -> list[str]` returning missing artifacts list. Add `reconstruct_from_worktree(worktree_path: Path) -> SessionState` scanning for `spec.md` and `tasks.md` to infer current phase and active issue. Add `normalize_task_id(ref: str) -> str` accepting both formats.
    - **Refactor**: Keep `SessionState` in `config.py` (maintain existing test compatibility). Add filesystem validation as a separate concern callable from CLI commands. Ensure `transition_to()` signature is backward-compatible for existing callers.
    - **Edge Cases**: Handle worktree with no recognizable artifacts; handle corrupted `session.json` (fall through to reconstruction); handle concurrent worktree detection; handle phase validation when no epic is active.
    - **Acceptance**: `test_state/test_session.py` passes all new scenarios. Existing session tests continue passing without modification. `IDLE` → `SPECIFY` correctly rejected. Task ID `T005` and `T005:` both normalize to same internal representation.

---

## Phase 4: E2E Verification
**Goal**: End-to-end validation of full macro + meso cycles and skill installation

### Tasks

- [ ] T009: End-to-End Integration Verification of Full Macro/Meso Cycles and Skill Installation
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test -- tests/test_integration/test_macro_layer.py tests/test_integration/test_meso_layer.py tests/test_integration/test_skill_installation.py tests/test_integration/test_macro_full_cycle.py tests/test_integration/test_meso_task_ledger.py tests/test_integration/test_init_export_cycle.py -v`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T004, T005, T007, T008
  - **Files**:
    - `tests/test_integration/test_macro_layer.py`
    - `tests/test_integration/test_meso_layer.py`
    - `tests/test_integration/test_skill_installation.py`
    - `tests/test_integration/test_macro_full_cycle.py`
    - `tests/test_integration/test_meso_task_ledger.py`
    - `tests/test_integration/test_init_export_cycle.py`
  - **Rationale**: Terminal E2E verification validates that all prior phases compose correctly. Ensures macro cycle (explore → research → prd → shard), meso cycle (specify → tasks), skill installation idempotency, init export cycle, and performance constraints all pass as an integrated whole.
  - **Details**:
    - **Implementation**: Run the full integration test suite. Verify that `test_macro_full_cycle.py` exercises the complete macro workflow from idle to shard completion. Verify `test_meso_task_ledger.py` exercises specify → tasks with real JSONL files. Verify `test_skill_installation.py` covers idempotent install, content-diff overwrite, and agent detection. Verify `test_init_export_cycle.py` still passes with init performance gate (L_max <= 500ms).
    - **Implementation**: Fix any test failures caused by integration points between phases. Ensure no test mock assumptions were broken by schema changes in T001 or CLI refactoring in T004/T005.
    - **Refactor**: Clean up any test fixtures that became stale during refactoring. Remove duplicate test helpers consolidated into conftest.py.
    - **Acceptance**: Full `mise run test` passes with zero failures. All performance gates satisfied: init <= 500ms, per-agent export <= 200ms, pre command <= 500ms.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use the shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **GIT_DIR Isolation**: `cwd=tmp_path` is NOT sufficient when subprocesses run inside a pre-commit hook. Git sets `$GIT_DIR`, `$GIT_WORK_TREE`, `$GIT_INDEX_FILE` which override `cwd`. EVERY `subprocess.run(["git", ...])` call MUST strip `GIT_*` environment variables via `env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}`. This applies to both test fixtures AND production code.
- **Conftest Creation**: The first task that needs `tmp_git_repo` (T002) MUST create `tests/conftest.py` with the fixture. Downstream tasks (T004, T005, T008) depend on its existence — they MUST NOT re-create it.
- **Verification**: After running a test that uses `tmp_git_repo`, verify `git config user.name` inside the temp repo shows `Test Runner` (not the real user). If the real user's name appears, the test is leaking into the real repo — fix the `cwd=` flag. Also verify that `echo "$GIT_DIR"` inside the test context is empty — if it's set, the test is leaking into the real repo.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules (`repo.py`, `commit.py`, `worktree.py`) MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the **sole enabler** of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
import os

def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

# DO: accept repo_path, default to cwd; strip GIT_* env vars
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    subprocess.run(["git", "add", ...], cwd=repo, env=_git_env(), check=True)

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def find_repo_root() -> Path:  # BAD — untestable
    ...
```

**Consequence**: Every per-task "Git Isolation" block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that runs git commands, that function **must** accept `repo_path`.

## Implementation Strategy
**Execution Order**:
1. Phase 1 (T001 → T002 → T003): Foundation — data model fixes and core modules
2. Phase 2 (T004, T005): CLI layer — can run in parallel after T003
3. Phase 3 (T006 → T007, T008): Skills/init/session — T007 depends on T006; T008 is independent after T003
4. Phase 4 (T009): E2E verification — requires all prior phases complete

**Critical Dependency Chains**:
- T001 (Schema fix) → T003 (PRD artifact check fix in macro.py)
- T003 (Core domain modules) → T004 (Macro CLI) and T005 (Meso CLI)
- T003 (Skills module) → T006 (SKILL.md migration)
- T006 (Skills migrated) → T007 (Init skill installation)
- T004, T005, T007, T008 → T009 (E2E verification)

**Risk Hotspots**:
- `src/deviate/state/ledger.py` — Schema migration in T001 affects all downstream consumers (macro.py, meso.py); existing tests must be updated
- `src/deviate/state/config.py` — Session state dual-mode extension in T008 must preserve backward compatibility with existing `transition_to()` callers
- `src/deviate/cli/macro.py` — Refactored in both T003 (artifact check fix) and T004 (full pre/post rewrite); sequential execution required
- `prompts/` — Bash script removal in T006 is irreversible; verify all SKILL.md rewrites before deletion

**Merge Conflict Boundaries**:
- Files touched by multiple phases:
  - `src/deviate/cli/macro.py` — T003 (artifact fix) + T004 (full rewrite)
  - `src/deviate/cli/meso.py` — T005 (full rewrite)
  - `src/deviate/state/ledger.py` — T001 (schema fix)
  - `src/deviate/state/config.py` — T008 (session extension)
  - `tests/test_state/test_session.py` — T008 (new divergence tests)
  - `tests/test_state/test_ledger.py` — T001 (schema tests)
  - `tests/test_integration/test_macro_layer.py` — T004 (new) + T009 (verification)
  - `tests/test_integration/test_meso_layer.py` — T005 (new) + T009 (verification)