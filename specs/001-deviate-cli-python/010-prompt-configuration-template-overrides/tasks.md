# Implementation Tasks: feat/001-deviate-cli-python/010-prompt-configuration-template-overrides

## Phase 1: Prompt Resolution Core Module
**Goal**: Create the prompt resolution layer (`prompts.py`) with override-chain resolution for both slim prompts and custom commands, placeholder interpolation, and override/default enumeration — the foundation for all downstream prompt customization.

### Tasks

- [/] T001: Prompt Resolution Core Module
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_prompts.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/core/prompts.py`
    - `tests/test_core/test_prompts.py`
  - **Rationale**: `prompts.py` is the central resolution engine for US-010-3 (override-first resolution), US-010-4 (silent fallback), US-010-5 (placeholder interpolation), and US-010-9 (override/default enumeration). These stories have non-trivial acceptance criteria requiring specific behavior for file existence, content comparison, and template variable substitution. Both `resolve_prompt()` (for slim automated prompts) and `resolve_command()` (for custom agent commands) follow the same override-chain pattern, so they share the same resolution logic.
  - **Details**:
    - **Red**: Write failing tests in `test_prompts.py`:
      - `test_resolve_prompt_override_before_default()` — assert `resolve_prompt("auto/red.md")` returns override content when `.deviate/prompts/auto/red.md` exists and differs from package default
      - `test_resolve_prompt_silent_fallback()` — assert `resolve_prompt("auto/red.md")` returns package default when override file is missing, no warning emitted
      - `test_resolve_prompt_not_found_raises()` — assert `FileNotFoundError` when neither override nor package default exists
      - `test_resolve_command_override_before_default()` — assert `resolve_command("deviate-red")` returns override content when `.deviate/prompts/commands/deviate-red.md` exists
      - `test_resolve_command_falls_back_to_package()` — assert `resolve_command()` returns package default when no override file exists
      - `test_interpolate_resolves_dynamic_variables()` — assert `${TASK_DESCRIPTION}` and `${TASK_ID}` replaced from variables dict
      - `test_list_overrides_returns_only_customized()` — assert only files with content differing from package default appear in result
      - `test_list_defaults_excludes_overrides()` — assert files with overrides excluded from defaults list
      - `test_resolve_prompt_partial_override_set()` — assert missing auto/ files fall through silently per HITL decision
    - **Green**: Implement `src/deviate/core/prompts.py`:
      - `resolve_prompt(name: str, overrides_root: Path | None = None, package_root: Path | None = None) -> str` — check `overrides_root/name` first, fall back to `package_root/name`, raise `FileNotFoundError` if neither exists. Accept optional `repo_path` for test isolation.
      - `resolve_command(name: str, overrides_root: Path | None = None, package_root: Path | None = None) -> str` — resolves `name.md` from `commands/` subdirectory, same override-chain pattern
      - `interpolate(template: str, variables: dict[str, str]) -> str` — regex replace `${VAR_NAME}` from variables dict, leave unresolved placeholders as-is
      - `list_overrides(overrides_root: Path, package_root: Path) -> list[str]` — walk override dir, compare content with package default, return names of differing or added files
      - `list_defaults(overrides_root: Path, package_root: Path) -> list[str]` — walk package dir, exclude names present in overrides list
      - Internal `_resolve_package_root()` using `importlib.resources.files("deviate.prompts")` for package default resolution
    - **Refactor**: Extract shared `_resolve_file(name, override_dir, fallback_dir)` helper to avoid duplication between `resolve_prompt` and `resolve_command`. Use `pathlib` consistently.
    - **Edge Cases**: Handle unreadable override files by logging and falling through to package default. Handle empty `variables` dict in `interpolate()` (return template unchanged). Handle `overrides_root` that doesn't exist.
    - **Acceptance**: All 9 test cases pass. `mise run check` passes. No `Path.cwd()` references — all paths accept optional `repo_path` or `overrides_root` parameters for test isolation.

- [ ] T002: Auto Prompt Template Files
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `ls src/deviate/prompts/auto/ | wc -l` (expect 11 files) && `pytest tests/test_core/test_prompts.py -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/auto/explore.md`
    - `src/deviate/prompts/auto/research.md`
    - `src/deviate/prompts/auto/prd.md`
    - `src/deviate/prompts/auto/shard.md`
    - `src/deviate/prompts/auto/specify.md`
    - `src/deviate/prompts/auto/tasks.md`
    - `src/deviate/prompts/auto/red.md`
    - `src/deviate/prompts/auto/green.md`
    - `src/deviate/prompts/auto/refactor.md`
    - `src/deviate/prompts/auto/judge.md`
    - `src/deviate/prompts/auto/yellow.md`
    - `src/deviate/prompts/__init__.py` (ensure auto/ is a package)
  - **Rationale**: These slim automated prompt templates are the package defaults that `deviate init` copies into `.deviate/prompts/auto/`. US-010-1 requires these files to exist with content matching what gets scaffolded. They're static boilerplate — no business logic, no tests needed beyond existence verification.
  - **Details**:
    - **Implementation**: Create `src/deviate/prompts/auto/` directory with 11 `.md` template files. Each template contains a Markdown structure with `${PLACEHOLDER}` variables matching the spec's interpolation table (`${CONSTITUTION}`, `${CLAUDE_MD}`, `${TASK_DESCRIPTION}`, `${TASK_ID}`, `${SPEC_EXCERPT}`, `${TEST_COMMAND}`, `${LINT_COMMAND}`, `${REPO_ROOT}`, `${FEATURE_SLUG}`, `${ISSUE_ID}`). Ensure `src/deviate/prompts/__init__.py` exists (already does) so `importlib.resources` can discover the `auto/` sub-package.
    - **Template structure**: Each file follows the spec format: `## [ROLE]`, `## [GOVERNANCE]` with `${CONSTITUTION}`, `## [AGENT_RULES]` with `${CLAUDE_MD}`, `## [TASK]`, `## [CONSTRAINTS]`, `## [OUTPUT]` with YAML manifest block.
    - **Refactor**: Ensure consistent template header format across all 11 files for model-based prefix caching.
    - **Acceptance**: 11 `.md` files exist under `src/deviate/prompts/auto/`. Each file contains at least 3 `${PLACEHOLDER}` variables. Template layout matches the spec's stated format.

- [ ] T002b: Command Template Files (Skills→Commands Conversion)
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `ls src/deviate/prompts/commands/ | wc -l` (expect 18 files) && each file has a valid command frontmatter format
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-adhoc.md`
    - `src/deviate/prompts/commands/deviate-constitution.md`
    - `src/deviate/prompts/commands/deviate-context.md`
    - `src/deviate/prompts/commands/deviate-e2e.md`
    - `src/deviate/prompts/commands/deviate-execute.md`
    - `src/deviate/prompts/commands/deviate-explore.md`
    - `src/deviate/prompts/commands/deviate-green.md`
    - `src/deviate/prompts/commands/deviate-hotfix.md`
    - `src/deviate/prompts/commands/deviate-pr.md`
    - `src/deviate/prompts/commands/deviate-prd.md`
    - `src/deviate/prompts/commands/deviate-prune.md`
    - `src/deviate/prompts/commands/deviate-red.md`
    - `src/deviate/prompts/commands/deviate-refactor.md`
    - `src/deviate/prompts/commands/deviate-research.md`
    - `src/deviate/prompts/commands/deviate-shard.md`
    - `src/deviate/prompts/commands/deviate-specify.md`
    - `src/deviate/prompts/commands/deviate-tasks.md`
    - `src/deviate/prompts/commands/deviate-triage.md`
    - (deleted) `src/deviate/prompts/skills/` — entire directory tree
  - **Rationale**: The existing skills/ directory with 18 SKILL.md files (each nested in a subdirectory) must be converted to flat command files. Instead of `deviate-red/SKILL.md`, use `commands/deviate-red.md` — a single flat `.md` per command. This aligns with the user's direction to use custom commands instead of skills. The command templates will be copied to `.deviate/prompts/commands/` by T003 for override editing, and installed to agent `.opencode/commands/` directories by T004.
  - **Details**:
    - **Implementation**: 
      1. Delete `src/deviate/prompts/skills/` directory tree entirely
      2. Create `src/deviate/prompts/commands/` directory
      3. For each of the 18 skill directories, extract the SKILL.md content and create a flat `commands/<skill-name>.md` file
      4. Each command file should have consistent frontmatter (name, description) and the same body content as the original SKILL.md, adapted for command format (no nested subdirectory assumptions)
      5. Add `__init__.py` to `commands/` so `importlib.resources` can discover it
    - **Refactor**: Ensure consistent frontmatter format across all 18 command files. Remove any references to `SKILL.md` or nested directory structure from the template bodies.
    - **Acceptance**: 18 `.md` files under `src/deviate/prompts/commands/`. No `skills/` directory remains. Each file contains the original SKILL.md content adapted for flat command format. `importlib.resources.files("deviate.prompts").joinpath("commands")` resolves correctly.

---

## Phase 2: Init Scaffolding & Refresh
**Goal**: Extend `deviate init` to bootstrap `.deviate/prompts/` with copies of package defaults for both auto/ and commands/, enforce idempotency, and implement the `--refresh-prompts` flag with interactive backup confirmation.

### Tasks

- [ ] T003: Init Prompt Scaffolding and --refresh-prompts
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_init.py -v -k prompt`
  - **Estimated Time**: 90 minutes
  - **Dependency**: T002, T002b
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: US-010-1 (scaffolding creates override directories), US-010-2 (idempotent skip on re-init), and US-010-6 (`--refresh-prompts` with backup prompt) all modify CLI behavior in `__init__.py`. The existing `test_init.py` already covers dotfile scaffolding — this extends the same test module with prompt-specific assertions, keeping related tests together. The CliRunner-based Integration test strategy matches the existing pattern in the test suite.
  - **Details**:
    - **Red**: Write failing tests in `test_init.py`:
      - `test_init_prompt_scaffolding_creates_auto_dir()` — assert `deviate init` creates `.deviate/prompts/auto/` with files matching package `auto/`
      - `test_init_prompt_scaffolding_creates_commands_dir()` — assert `.deviate/prompts/commands/` created with `.md` files for all 18 commands
      - `test_init_prompt_scaffolding_idempotent()` — assert second `deviate init` does not modify existing `.deviate/prompts/` files
      - `test_init_prompt_scaffolding_skip_message()` — assert console output contains `"prompts/ already exists, skipping"` on re-run
      - `test_init_refresh_prompts_prompts_backup()` — assert `--refresh-prompts` prompts `"Back up existing overrides? [y/N]"`
      - `test_init_refresh_prompts_with_backup()` — assert `"y"` response creates `.deviate/prompts.bak/<timestamp>/` with backup
      - `test_init_refresh_prompts_no_backup()` — assert `"N"` response skips backup and overwrites directly
      - `test_init_refresh_prompts_no_flag_does_not_overwrite()` — assert without `--refresh-prompts`, existing files survive
      - `test_init_scaffolding_within_performance_budget()` — assert scaffolding completes in <= 500ms
    - **Green**: Implement CLI additions in `src/deviate/cli/__init__.py`:
      - Add `refresh_prompts: bool = typer.Option(False, "--refresh-prompts", ...)` to the `init()` command signature
      - Add `_scaffold_prompts(workdir: Path, refresh: bool)` function:
        - If `.deviate/prompts/` exists and `refresh` is False: print skip message, return
        - If `.deviate/prompts/` exists and `refresh` is True: prompt user for backup confirmation via `rich.prompt.Confirm.ask()`
        - If backup confirmed: create `.deviate/prompts.bak/<timestamp>/` via `shutil.copytree()`
        - Copy package `auto/` templates to `.deviate/prompts/auto/` via `shutil.copytree()`
        - Copy package `commands/` templates to `.deviate/prompts/commands/` via `shutil.copytree()`
      - Integrate `_scaffold_prompts()` into the `init()` sequence after `_scaffold_dotfiles()` and before `_apply_governance()`
      - Use `importlib.resources.files("deviate.prompts")` to resolve package template root
    - **Refactor**: Extract `_copy_package_prompts(source_root, target_root)` helper from `_scaffold_prompts` for reuse. Keep `_scaffold_dotfiles` pattern consistent with new `_scaffold_prompts`.
    - **Edge Cases**: Handle missing `auto/` or `commands/` directory in package (log warning, skip). Handle partial `.deviate/prompts/` (e.g., only `auto/` exists but not `commands/`). Handle `shutil.copytree` failing on existing directories (use `dirs_exist_ok=True`).
    - **Acceptance**: All 9 test cases pass. `deviate init` on clean project creates `.deviate/prompts/auto/` and `.deviate/prompts/commands/` with copies from package. Re-run idempotent. `--refresh-prompts` with `"y"` creates timestamped backup.

---

## Phase 3: Custom Command Installation
**Goal**: Replace the skill installation system with custom command installation. Convert `src/deviate/core/skills.py` to a command-based module that installs `.md` command files to agent `.opencode/commands/` directories, resolving through the override chain.

### Tasks

- [ ] T004: Convert Skill Installation to Custom Command Installation
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_core/test_skills.py -v`
  - **Estimated Time**: 90 minutes
  - **Dependency**: T001, T002b
  - **Files**:
    - `src/deviate/core/skills.py` (rewrite)
    - `tests/test_core/test_skills.py` (rewrite)
  - **Rationale**: The existing `install_skill()` mechanism copies `SKILL.md` from nested subdirectories to `.opencode/skills/`. Per the user's decision, we replace this with custom commands: flat `.md` files installed to `.opencode/commands/`. The rewrite touches the same files (skills.py + test) but fundamentally changes behavior: (1) resolves `.md` commands instead of `SKILL.md`, (2) targets `commands/` instead of `skills/`, (3) uses the override chain from `prompts.py`. US-010-7 requires this resolution-chain integration.
  - **Details**:
    - **Red**: Write failing tests in `test_skills.py`:
      - `test_install_command_resolves_from_override()` — given override content in `.deviate/prompts/commands/deviate-red.md`, assert `install_command("deviate-red", target_dir)` writes the override content
      - `test_install_command_falls_back_to_package()` — given no override file, assert `install_command()` writes the package default content
      - `test_install_command_skip_when_identical()` — assert returns `False` when target already matches resolved content
      - `test_install_command_overwrite_when_stale()` — assert returns `True` when target content differs
      - `test_install_command_targets_commands_dir()` — assert file is written to `target_dir/commands/deviate-red.md` not `target_dir/skills/deviate-red/SKILL.md`
      - `test_detect_agents_still_works()` — assert the agent detection function (unchanged behavior) still finds `.claude/`, `.opencode/`, `.factory/` directories
    - **Green**: Rewrite `src/deviate/core/skills.py`:
      - Rename `install_skill()` to `install_command(name: str, target_dir: Path, repo_path: Path | None = None) -> bool`:
        - Call `prompts.resolve_command(name, overrides_root=repo_path/.deviate/prompts/commands/, package_root=package_commands_root)` to get content
        - Write to `target_dir / "commands" / f"{name}.md"`
        - Compare content, skip if identical, copy if different
        - Return `True` if file was written, `False` if skipped
      - Remove `resolve_skill()` (no longer needed — replaced by `prompts.resolve_command()`)
      - Keep `discover_skills()` but repurpose as `discover_commands(root: Path | None = None) -> list[str]` — scan for `.md` files in `commands/` directories instead of SKILL.md nested dirs
      - Keep `detect_agents()` unchanged
      - Make `_resolve_skills_root()` a private helper for backward compat only, or remove it
      - Add `install_skill()` as a deprecated compatibility wrapper that calls `install_command()` internally
    - **Refactor**: Remove all references to `SKILL.md` and nested subdirectory traversal. Simplify to flat `.md` file enumeration. Update all internal helper function names to use `command` terminology.
    - **Edge Cases**: Handle missing `commands/` directory in package (log warning, return False). Handle case where `prompts.py` not yet imported (try/except ImportError with fallback to direct read from package).
    - **Acceptance**: All 6 test cases pass. `install_command("deviate-red", target_dir)` writes `.opencode/commands/deviate-red.md` with override content when override exists, falls through to package default otherwise.

- [ ] T004b: Update CLI Init for Command Installation
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `pytest tests/test_cli/test_init.py -v -k command`
  - **Estimated Time**: 45 minutes
  - **Dependency**: T004
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/test_cli/test_init.py`
  - **Rationale**: US-010-7 requires that `deviate init` installs commands (not skills) to agent directories. The existing `_install_skills_to_agents()` must be updated to call `install_command()` instead of `install_skill()` and target `commands/` subdirectories. The agent directory resolution in `_get_agent_skill_dir()` must be updated from `skills/` to `commands/`.
  - **Details**:
    - **Red**: Write failing tests in `test_init.py`:
      - `test_init_installs_commands_to_agent_commands_dir()` — assert `deviate init` creates `.opencode/commands/deviate-red.md`
      - `test_init_command_idempotency_skip_identical()` — assert re-running `deviate init` does not rewrite identical command files
      - `test_init_command_idempotency_overwrite_stale()` — assert re-running `deviate init` overwrites stale command files
      - `test_init_old_skill_install_still_works_as_deprecated()` — if backward-compat `install_skill` retained, ensure it routes to `install_command`
    - **Green**: Update `src/deviate/cli/__init__.py`:
      - Rename `_install_skills_to_agents()` to `_install_commands_to_agents()`:
        - Call `install_command()` instead of `install_skill()`
        - Update console output from `SKILL` to `COMMAND`
      - Rename `_get_agent_skill_dir()` to `_get_agent_command_dir()`:
        - Return `workdir / ".opencode" / "commands"` instead of `... / "skills"`
      - Update `init()` command to call `_install_commands_to_agents()` instead of `_install_skills_to_agents()`
    - **Refactor**: Keep old `_install_skills_to_agents` as private deprecated alias if backward compat needed. Update all console messages to say `COMMAND`/`command` instead of `SKILL`/`skill`.
    - **Edge Cases**: Handle agent directories that don't exist yet (create `commands/` subdirectory). Handle agents with no `commands/` directory (skip with message). Handle `install_command()` returning False (already up to date — log as skip).
    - **Acceptance**: All 4 test cases pass. `deviate init` writes command files to `.opencode/commands/`. Re-run skips identical files, overwrites stale ones.

---

## Phase 4: End-to-End Verification
**Goal**: Validate the full prompt + command override flow — from `deviate init` scaffolding through resolution to agent command installation — as a single deterministic integration test.

### Tasks

- [ ] T005: Prompt Override E2E Integration Tests
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `pytest tests/test_integration/test_prompt_overrides.py -v`
  - **Estimated Time**: 60 minutes
  - **Dependency**: T003, T004b
  - **Files**:
    - `tests/test_integration/test_prompt_overrides.py`
  - **Rationale**: US-010-8 (pipeline resolves slim prompts from override chain) requires end-to-end verification that user edits to `.deviate/prompts/auto/` propagate through resolution to prompt consumption. No production code changes — this is purely a test coordination file that validates the integration of T001-T004b. Existing integration tests follow the same pattern (e.g., `test_init_export_cycle.py`).
  - **Details**:
    - **Implementation**: Create `tests/test_integration/test_prompt_overrides.py` with:
      - `test_prompt_override_full_cycle()` — full flow: scaffold via `deviate init` → write custom override in `.deviate/prompts/auto/` → resolve via `resolve_prompt()` → assert custom content returned
      - `test_prompt_override_fallback_cycle()` — scaffold → delete override file → resolve → assert package default returned
      - `test_command_override_full_cycle()` — scaffold → write custom command override in `.deviate/prompts/commands/` → resolve via `resolve_command()` → assert custom content returned
      - `test_command_agent_installation()` — scaffold → write custom command override → run `deviate init` → assert agent `.opencode/commands/deviate-red.md` contains override content
      - `test_prompt_interpolation_with_overrides()` — scaffold + override → resolve → interpolate with variables → assert resolved placeholders
      - `test_refresh_prompts_resets_overrides()` — scaffold → customize → `--refresh-prompts` → assert overrides reset to package defaults
      - Use `tmp_path` fixture for isolation (no real repo mutation). Use `CliRunner` to invoke `deviate init`. Use `importlib.resources` to locate package defaults.
    - **Refactor**: Extract shared setup helper `_init_project(tmp_path)` that runs `deviate init` in a temp dir and returns the project root path.
    - **Edge Cases**: Test with only partial override sets (some files overridden, some falling through). Test with empty `.deviate/prompts/auto/` directory. Test with `--refresh-prompts` to verify reset.
    - **Acceptance**: All 7 test cases pass. `mise run check` passes.

---

## Implementation Strategy

**Execution Order**:
1. Phase 1 — T001 (prompts.py) + T002 (auto templates) + T002b (commands templates) in parallel
2. Phase 2 — T003 (init scaffolding) after T002 + T002b (needs templates to copy)
3. Phase 3 — T004 (command installation) after T001 + T002b; T004b (CLI wiring) after T004
4. Phase 4 — T005 (E2E tests) after T003 + T004b

**Critical Dependency Chains**:
- T002 (auto templates) + T002b (commands templates) must precede T003 (init scaffolding copies them)
- T001 (prompts.py) must precede T004 (command installation depends on resolve_command)
- T004 must precede T004b (CLI wiring needs install_command API)
- T003 + T004b must precede T005 (E2E test depends on all production code)

**Skills→Commands Architectural Decision**:
- All SKILL.md templates removed from `src/deviate/prompts/skills/`
- Replaced by flat `.md` command files in `src/deviate/prompts/commands/`
- Install target: `.opencode/commands/<name>.md` (not `.opencode/skills/<name>/SKILL.md`)
- Resolution: `resolve_command(name)` checks `.deviate/prompts/commands/` override, falls back to package `commands/`
- Core module: `install_command()` in `src/deviate/core/skills.py` (file kept, rewritten)
- This applies to all 18 commands (deviate-* phases: explore, research, prd, shard, adhoc, specify, tasks, red, green, refactor, judge, execute, e2e, prune, hotfix, triage, constitution, context, pr)

**Risk Hotspots**:
- `importlib.resources.files()` resolution varies between Python 3.12 and 3.13 — test on both
- `shutil.copytree()` with `dirs_exist_ok=True` requires Python 3.13+
- `rich.prompt.Confirm.ask()` is blocking in tests — use monkeypatch or `CliRunner` input injection
- `Path.cwd()` leakage in tests — every path-interacting function must accept optional `repo_path`
- Backward compatibility: any code importing `install_skill` from `skills.py` will break — check all callers in `cli/` and `macro.py`/`meso.py`/`micro.py`

**Merge Conflict Boundaries**:
- T001 creates `prompts.py` — no conflicts
- T002 creates `auto/` directory — no conflicts
- T002b deletes `skills/` and creates `commands/` — may conflict if other branches reference skills paths
- T003 modifies `cli/__init__.py` — isolated from other tasks
- T004 rewrites `skills.py` — potential conflict with any branch touching skills.py
- T004b modifies `cli/__init__.py` — same file as T003, sequential execution avoids collision

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py` (which calls `git init` inside `tmp_path` and configures a test user). Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## Universal API Design Constraint (ALL CORE MODULES)

Every path-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`. This is the sole enabler of test isolation — without it, tests must use fragile `chdir` tricks or operate on the real repo.

```python
# DO: accept repo_path, default to cwd
def resolve_prompt(name: str, repo_path: Path | None = None) -> str:
    repo_path = repo_path or Path.cwd()

# DON'T: hard-code Path.cwd() or rely on ambient working directory
def resolve_prompt(name: str) -> str:  # BAD — untestable
    ...
```

**Consequence**: Every per-task Git Isolation block below is a specific instance of this universal constraint. If a task's `Green` section says to implement a function that interacts with the filesystem, that function **must** accept `repo_path`.
