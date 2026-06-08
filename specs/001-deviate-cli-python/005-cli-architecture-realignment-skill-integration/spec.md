# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/005-cli-architecture-realignment-skill-integration/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/005-cli-architecture-realignment-skill-integration/spec.md`
- **Workstation Paths**:
  - `src/deviate/core/` — Shared core modules (`repo.py`, `ledger.py`, `contract.py`, `commit.py`, `constitution.py`, `epic.py`, `validation.py`, `worktree.py`, `issues.py`, `prd.py`, `skills.py`)
  - `src/deviate/cli/` — Macro and meso subcommand groups
  - `src/deviate/state/` — Session and config persistence (`session.py`, `config.py`)
  - `src/deviate/prompts/skills/` — SKILL.md storage vault (skill templates)
  - `specs/issues.jsonl` — Global issue ledger (data model fixes target)
  - `prompts/` — Legacy `.sh` orchestrator scripts (removal target)
  - `AGENTS.md` — Agent governance documentation (update target)
  - `.mise.toml` — Task runner configuration (cleanup target)
  - `tests/test_core/` — Unit tests for core modules
  - `tests/test_integration/test_macro_layer.py` — Macro layer integration tests
  - `tests/test_integration/test_meso_layer.py` — Meso layer integration tests
  - `tests/test_integration/test_skill_installation.py` — Skill installation integration tests

## THE_PROBLEM_CONTRACT

As a maintainer of the DeviaTDD orchestrator, I need to replace all 15 bash orchestrator scripts (~8,000 lines) with Python CLI `deviate <subcommand> pre/post` commands, fix critical data model bugs (malformed JSONL, mismatched `IssueRecord` schema), implement 11 core shared modules, and install/rewrite SKILL.md files into agent directories, so that the architecture is unified under a single Python dependency and the bash dependency is fully eliminated.

## SCOPE_BOUNDARIES

### Hard Inclusions

- **Data Model Fixes (FR-005-DATA)**: Repair malformed JSON on `specs/issues.jsonl` line 10; rewrite `IssueRecord` Pydantic model to match actual JSONL schema (`issue_id`, `type`, `status`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp`); fix `resolve_issue_record` key mismatch (`id` → `issue_id`); fix `macro.py:prd` artifact check (`research.md` → `design.md` + `data-model.md`). Malformed JSONL lines encountered during reads are skipped with a warning log — no in-place auto-rewrite.
- **Core Shared Modules (FR-005-CORE)**: Implement `repo.py` (find_repo_root, gather_git_state), `ledger.py` (full rewrite: read/append JSONL, get_issue_by_id, select_next_unblocked_issue, check_ledger_dirty, next_issue_id, register_issue), `contract.py` (emit/persist/load JSON contracts), `commit.py` (stage_and_commit, commit_artifact), `constitution.py` (resolve, validate, extract commands), `epic.py` (discover_epic, allocate_feature_bucket, resolve_active_feature), `validation.py` (extract_spec_sections, extract_section_body, validate_gherkin_syntax), `worktree.py` (create/detect/validate worktrees, branch checks), `issues.py` (resolve_issue, claim_issue, read_issue_body, is_issue_completed), `prd.py` (extract_prd_requirements, validate_traceability), `skills.py` (install/discover/resolve skills).
- **Meso Layer CLI (FR-005-MESO)**: `deviate specify pre [--issue <id>] [--force]` (auto-select next unblocked BACKLOG, worktree creation, ledger claim, spec target resolution), `deviate specify post [--force]` (content validation, commit, ledger update), `deviate tasks pre` (worktree detection, spec discovery, artifact discovery), `deviate tasks post [--force]` (content validation, commit), `deviate pr pre` (worktree validation, issue discovery, body gathering), `deviate pr run --body-file <path> [--merge] [--auto-merge]` (PR creation, merge, COMPLETED event).
- **Macro Layer CLI (FR-005-MACRO)**: `deviate explore pre "<problem>" [--slug <slug>]` (repo discovery, constitution validation, feature bucket allocation, ledger scratch entry), `deviate explore post` (content validation, commit), `deviate research pre [<epic>]` (active feature resolution, constitution re-validation, explore.md gate), `deviate research post` (content validation, constitutional violation scan, commit), `deviate prd pre` (epic slug discovery, upstream artifact resolution), `deviate prd post <manifest>` (manifest reading, PRD validation, staging, commit), `deviate shard pre` (epic discovery, PRD resolution, issues dir, next_issue_id), `deviate shard post <manifest>` (shard validation, ledger registration, commit).
- **Skill Installation & Bash Removal (FR-005-SKILLS)**: Move SKILL.md files from `prompts/` to `src/deviate/prompts/skills/<name>/SKILL.md`; rewrite all SKILL.md `[SYSTEM_TOPOLOGY_MAPPING]` and invocation instructions to reference `deviate <subcommand>` instead of `<SKILL_DIR>/deviate-*.sh`; wire skill installation into `deviate init`; remove all `.sh` files from `prompts/`; remove `deviate-cycle` skill; update `.mise.toml` and `AGENTS.md` to reflect new Python-only architecture. SKILL.md idempotency: skip if content matches; overwrite if content differs (content-hash based).
- **Init Integration (FR-005-INIT)**: `deviate init` gains agent auto-detection (scan cwd for `.claude/`, `.opencode/`, `.factory/` directories) with flag overrides (`--agent <name>`) and interactive fallback when no agent is detected; contract handoff defaults to `.deviate/session.json` with optional temp-file mode.
- **Session State Dual-Mode (FR-005-SESSION)**: Dual-mode session tracking for both Macro and Meso layers — enforces strict phase ordering AND validates filesystem state against expected artifacts; detects divergence when user alters filesystem or undoes commits. Divergence recovery: reconstruct minimal session state from worktree artifacts (scan for spec/tasks files); emit warning on reconstitution.
- **Task ID Format**: Accept both `T{NNN}` and `T{NNN}:` patterns in task references.

### Defensive Exclusions

- Micro-layer TDD sandbox execution (`execute`, `red`, `green`, `refactor`, `e2e`, `prune`, `hotfix`, `YELLOW`, `JUDGE`) — covered by ISS-004.
- Direct LLM sandbox or Tamper Guard implementation.
- OS-level file locking for JSONL ledgers.
- Dynamic LLM-driven content generation (the CLI orchestrates workflows; content generation is delegated to agent skills).

## PERFORMANCE_CONSTRAINTS

- `L_max <= 500ms` for `deviate init` full cycle (including skill installation and agent detection).
- `L_max <= 200ms` per agent platform export during `deviate init`.
- `L_max <= 50ms` for offline constitution variable resolution.
- `L_max <= 500ms` for `deviate specify pre` and `deviate tasks pre` command execution.
- `L_max <= 50ms` per JSONL append operation.
- `L_max <= 10ms` per Pydantic model validation (any model).
- All `pre` commands must complete within `L_max <= 500ms` (excluding external git push network latency).

## TEST_ISOLATION_CONSTRAINTS

### Git Isolation (Test Level)
Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, push) MUST operate on a temporary directory initialized as a fresh git repo via `tmp_path` (pytest) or `tempfile.TemporaryDirectory`. Tests MUST NOT run git commands in the real repository's working tree. This prevents accidental commits, branch creation, or state mutation in the actual project repo during TDD cycles.

### API Injection Pattern (Production Code Level)
All git-interacting functions in core modules (`repo.py`, `commit.py`, `worktree.py`) MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, the function defaults to `Path.cwd()`. This enables tests to inject a `tmp_path`-based repo without relying on `chdir` side effects or process-wide working directory changes.

Pattern:
```python
def find_repo_root(start_at: Path | None = None) -> Path:
    start_at = start_at or Path.cwd()

def stage_and_commit(message: str, files: list[Path], repo: Path | None = None) -> str:
    repo = repo or Path.cwd()
    subprocess.run(["git", "add", ...], cwd=repo, ...)
```

### Reusable Conftest Fixture
Provide a shared `tmp_git_repo` fixture in `tests/conftest.py` to eliminate repeated `git init` boilerplate:

```python
@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "runner@test.local"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "initial"],
        cwd=tmp_path,
        check=True,
    )
    yield tmp_path
```

Tests use the fixture instead of reaching into the real repo:
```python
def test_find_repo_root_from_subdir(tmp_git_repo: Path):
    subdir = tmp_git_repo / "subdir"
    subdir.mkdir()
    assert find_repo_root(start_at=subdir) == tmp_git_repo
```

> **WARNING**: The `cwd=tmp_path` flag on every `subprocess.run(["git", ...])` call is the **sole boundary** keeping these operations inside the temp repo. Omitting `cwd=` means git auto-discovers the nearest `.git` by walking up the directory tree — which will find the **real project repo**. Every git subprocess call in tests and production code MUST pass `cwd=<repo_path>` or the equivalent `repo=` parameter. Never rely on ambient working directory.

### GIT_DIR Environment Variable Isolation (CRITICAL)

When any git subprocess runs inside a **pre-commit hook** (e.g., `.githooks/pre-commit` runs `mise run check`), git sets the `GIT_DIR`, `GIT_WORK_TREE`, and `GIT_INDEX_FILE` environment variables. These override the `cwd=` parameter entirely — meaning `subprocess.run(["git", ...], cwd=tmp_path)` will still operate on the **real repo** if `$GIT_DIR` is set.

**Fix**: Every `subprocess.run(["git", ...])` call MUST strip `GIT_*` environment variables:

```python
import os

def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

# In every subprocess.run(["git", ...]) call:
subprocess.run(["git", "init"], cwd=tmp_path, env=_git_env(), check=True)
subprocess.run(["git", "status", "--porcelain"], cwd=repo, env=_git_env(), check=True)
```

This applies to:
- The `tests/conftest.py` fixture (all `git init`, `git config`, `git commit` calls)
- `src/deviate/core/repo.py` (`git status --porcelain` call)
- `src/deviate/core/commit.py` (`git add`, `git commit`, `git rev-parse` calls)
- `src/deviate/core/worktree.py` (`git branch`, `git worktree add`, `git branch --show-current`, `git rev-parse --show-toplevel` calls)

Without this fix, running tests via the pre-commit hook (or any git hook) will corrupt the real repository, creating "initial" commits, staged files, and branching in the real project.

## MULTI_TIERED_VERIFICATION_TARGETS

| Tier | Target | Description |
|------|--------|-------------|
| Unit | `tests/test_core/test_ledger.py` | JSONL read/append, malformed line recovery, IssueRecord schema alignment |
| Unit | `tests/test_core/test_repo.py` | Repository root detection, git state gathering |
| Unit | `tests/test_core/test_contract.py` | JSON contract emit/persist/load round-trip |
| Unit | `tests/test_core/test_commit.py` | Stage-and-commit workflow, artifact commit |
| Unit | `tests/test_core/test_constitution.py` | Constitution resolution, validation, command extraction |
| Unit | `tests/test_core/test_epic.py` | Epic discovery, feature bucket allocation |
| Unit | `tests/test_core/test_validation.py` | Spec section extraction, Gherkin syntax validation |
| Unit | `tests/test_core/test_worktree.py` | Worktree creation, detection, validation |
| Unit | `tests/test_core/test_issues.py` | Issue resolution, claim, body reading, completion check |
| Unit | `tests/test_core/test_prd.py` | PRD requirement extraction, traceability validation |
| Unit | `tests/test_core/test_skills.py` | Skill installation, discovery, resolution |
| Integration | `tests/test_integration/test_macro_layer.py` | Full macro cycle (explore → research → prd → shard) via Python CLI |
| Integration | `tests/test_integration/test_meso_layer.py` | Full meso cycle (specify → tasks) via Python CLI |
| Integration | `tests/test_integration/test_skill_installation.py` | SKILL.md installation idempotency, content-diff detection |
| Data | `python -c "import json; [json.loads(l) for l in open('specs/issues.jsonl')]"` | All JSONL lines parse without exception |

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-DATA: Critical Data Model Fixes and Schema Realignment

- **Upstream Requirement Traceability**: FR-005
- **Description**: Fix malformed JSONL entries, realign the `IssueRecord` Pydantic model with the actual JSONL schema, fix key mismatches in `resolve_issue_record`, and correct artifact validation paths in `macro.py:prd`. Malformed lines are skipped with a warning; no auto-rewrite of broken data.

**Scenario 1: All JSONL lines parse successfully after schema fix**

- **Given**: `specs/issues.jsonl` exists with prior malformed entries (including known corruption on line 10)
- **When**: The JSONL file is loaded via the corrected `IssueRecord` Pydantic model
- **Then**: All well-formed lines parse into valid `IssueRecord` instances; malformed lines are skipped with a `UserWarning` containing the line number and reason

**Scenario 2: IssueRecord model matches actual JSONL schema**

- **Given**: A JSONL line with fields `issue_id`, `type`, `status`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp`
- **When**: The `IssueRecord` model validates this line
- **Then**: All fields are correctly deserialized; `extra="forbid"` rejects unknown fields; the `issue_id` field (not `id`) is the primary key

**Scenario 3: resolve_issue_record uses correct key**

- **Given**: An `IssueRecord` exists in the ledger with `issue_id: "ISS-001"`
- **When**: `resolve_issue_record("ISS-001")` is called
- **Then**: The record is returned successfully (no KeyError from mismatched `id` vs `issue_id` key lookup)

**Scenario 4: macro.py:prd checks correct artifact names**

- **Given**: A feature bucket directory contains `design.md` and `data-model.md` but NOT `research.md`
- **When**: The `deviate prd` pre-phase validates upstream artifacts
- **Then**: The gate passes (checking for `design.md` + `data-model.md` instead of the old `research.md` filename)

### US-002-CORE: Core Shared Module Implementation

- **Upstream Requirement Traceability**: FR-005
- **Description**: Implement all 11 core shared modules (`repo`, `ledger`, `contract`, `commit`, `constitution`, `epic`, `validation`, `worktree`, `issues`, `prd`, `skills`) with full API coverage as defined in the scope boundaries.

**Scenario 1: repo.py resolves repository root and git state**

- **Given**: The current working directory is anywhere inside a git repository
- **When**: `find_repo_root()` and `gather_git_state()` are called
- **Then**: `find_repo_root()` returns the absolute path to the `.git` parent directory; `gather_git_state()` returns a dict with `staged_files`, `unstaged_files`, `untracked_files`, and their counts

**Scenario 2: ledger.py supports full JSONL lifecycle**

- **Given**: `specs/issues.jsonl` exists with well-formed records
- **When**: `get_issue_by_id`, `select_next_unblocked_issue`, `check_ledger_dirty`, `next_issue_id`, and `register_issue` are called in sequence
- **Then**: Each function returns correct results; `select_next_unblocked_issue` returns the oldest `BACKLOG` issue; `register_issue` appends a new line with a unique timestamp

**Scenario 3: contract.py round-trips JSON contracts**

- **Given**: A JSON contract dict with keys `issue_id`, `branch_name`, `spec_target`, `prd_requirements`
- **When**: The contract is emitted (persisted) and then loaded back
- **Then**: All keys and values match exactly; no fields are lost or altered

**Scenario 4: constitution.py extracts test and lint commands**

- **Given**: `specs/constitution.md` contains `## [TEST_COMMAND]` and `## [LINT_COMMAND]` sections with populated values
- **When**: `extract_commands()` is called
- **Then**: A dict with `test_command` and `lint_command` is returned containing the section body content

**Scenario 5: skills.py discovers and resolves skill directories**

- **Given**: `src/deviate/prompts/skills/` contains subdirectories each with a `SKILL.md`
- **When**: `discover_skills()` is called
- **Then**: A list of skill names (directory names) is returned; `resolve_skill("deviate-specify")` returns the absolute path to `SKILL.md`

### US-003-MESO: Meso Layer CLI Subcommands

- **Upstream Requirement Traceability**: FR-005
- **Description**: Implement `deviate specify` (pre/post), `deviate tasks` (pre/post), and `deviate pr` (pre/run) subcommands with worktree management, ledger state transitions, and content validation hooks.

**Scenario 1: deviate specify pre auto-selects next unblocked BACKLOG issue**

- **Given**: `specs/issues.jsonl` contains multiple `BACKLOG` issues, one of which has no `blocked_by` entries and is the oldest
- **When**: `deviate specify pre` is invoked without `--issue`
- **Then**: The oldest unblocked `BACKLOG` issue is selected, a worktree is created on a new branch, the issue is claimed in the ledger, and a JSON contract is emitted with `spec_target` resolved

**Scenario 2: deviate specify post validates and commits spec content**

- **Given**: A `spec.md` exists at the resolved `spec_target` path with valid sections, Gherkin blocks, and FR traceability
- **When**: `deviate specify post` is invoked
- **Then**: Content passes validation, the file is staged and committed via `commit_artifact`, and the ledger is updated

**Scenario 3: deviate tasks pre detects existing worktree claim**

- **Given**: A worktree exists at the expected path from a prior `deviate specify pre` run
- **When**: `deviate tasks pre` is invoked
- **Then**: The worktree is detected and validated, the `spec.md` is discovered, and a JSON contract with artifact paths is emitted without creating a new worktree

**Scenario 4: deviate pr run creates PR and emits COMPLETED event**

- **Given**: A worktree branch with committed changes and a valid `--body-file` path
- **When**: `deviate pr run --body-file <path>` is invoked
- **Then**: A GitHub PR is created from the worktree branch, and upon successful creation, a `COMPLETED` status event is appended to the issue ledger

### US-004-MACRO: Macro Layer CLI Subcommands

- **Upstream Requirement Traceability**: FR-005
- **Description**: Implement `deviate explore` (pre/post), `deviate research` (pre/post), `deviate prd` (pre/post), and `deviate shard` (pre/post) subcommands with feature bucket allocation, upstream artifact gating, and constitutional validation at each gate.

**Scenario 1: deviate explore pre allocates feature bucket and registers scratch entry**

- **Given**: A repository with a valid constitution and no existing feature bucket for the given slug
- **When**: `deviate explore pre "problem description" --slug <slug>` is invoked
- **Then**: A feature bucket is allocated at `specs/<epic-slug>/`, a scratch `IssueRecord` is registered in the ledger, and a JSON contract is emitted

**Scenario 2: deviate research pre gates on explore.md existence**

- **Given**: A feature bucket exists with `explore.md` in the directory
- **When**: `deviate research pre` is invoked
- **Then**: The `explore.md` artifact is validated; execution proceeds; if `explore.md` is missing, the command exits with an error

**Scenario 3: deviate prd post validates PRD manifest**

- **Given**: A `prd.md` has been produced by the upstream HITL workflow
- **When**: `deviate prd post <manifest>` is invoked
- **Then**: The manifest is read and validated against the PRD schema; on success, the `prd.md` is staged and committed

**Scenario 4: deviate shard post registers all sharded issues in ledger**

- **Given**: A `shard.md` manifest containing references to generated issue files
- **When**: `deviate shard post <manifest>` is invoked
- **Then**: Each sharded issue is registered as an `IssueRecord` in `specs/issues.jsonl` with `status: "BACKLOG"` and the session phase transitions from `SHARD` to `IDLE`

### US-005-SKILLS: Skill Installation and Bash Dependency Removal

- **Upstream Requirement Traceability**: FR-005
- **Description**: Migrate all SKILL.md files from legacy `prompts/` locations into `src/deviate/prompts/skills/<name>/SKILL.md`, rewrite their internal references to use `deviate <subcommand>` invocations, remove all `.sh` orchestrator scripts, and clean up legacy configuration artifacts.

**Scenario 1: SKILL.md files are installed with correct content path and rewritten invocations**

- **Given**: An existing SKILL.md in `prompts/deviate-specify/SKILL.md` references `<SKILL_DIR>/deviate-specify.sh`
- **When**: The skill is migrated to `src/deviate/prompts/skills/deviate-specify/SKILL.md` and rewritten
- **Then**: The `SKILL.md` content replaces all `<SKILL_DIR>/deviate-*.sh` references with `deviate <subcommand>`; the file is readable via `importlib.resources` from the package

**Scenario 2: deviate init installs skills into detected agent directories**

- **Given**: The working directory contains `.claude/` and `.opencode/` directories
- **When**: `deviate init` is invoked
- **Then**: SKILL.md files are copied from `src/deviate/prompts/skills/<name>/SKILL.md` to agent-specific skill directories (e.g., `~/.config/opencode/skills/deviate-<name>/SKILL.md`)

**Scenario 3: SKILL.md idempotency — skip when content matches**

- **Given**: A SKILL.md already exists in the agent skill directory with content identical to the package source
- **When**: `deviate init` is invoked a second time
- **Then**: The SKILL.md is skipped (no file write); a log message indicates the skip

**Scenario 4: SKILL.md idempotency — overwrite when content differs**

- **Given**: A SKILL.md exists in the agent skill directory with content that differs from the package source (stale version)
- **When**: `deviate init` is invoked
- **Then**: The SKILL.md is overwritten with the updated package source content; a log message indicates the update

**Scenario 5: All legacy .sh files are removed from prompts/**

- **Given**: `prompts/` contains `.sh` orchestrator scripts
- **When**: The cleanup phase of `deviate init` or a dedicated `deviate cleanup` runs
- **Then**: All `.sh` files under `prompts/` are deleted; no `.sh` files remain in the repository

**Scenario 6: deviate-cycle skill is removed**

- **Given**: The `deviate-cycle` skill directory exists under the skills path
- **When**: Skill cleanup runs
- **Then**: The `deviate-cycle` skill entry is removed; it is no longer discoverable or installable

### US-006-INIT: Init Integration for Agent Detection and Contract Handoff

- **Upstream Requirement Traceability**: FR-005
- **Description**: Extend `deviate init` with automatic agent detection (scanning for `.claude/`, `.opencode/`, `.factory/`), flag-based agent overrides (`--agent`), interactive fallback when no agent is detected, and configurable contract handoff between `.deviate/session.json` and temp files.

**Scenario 1: Auto-detect agents from cwd directories**

- **Given**: The working directory contains `.claude/` and `.factory/` subdirectories
- **When**: `deviate init` is invoked without `--agent`
- **Then**: Both Claude and Droid agents are detected; command files are exported to `.claude/commands/` and `.factory/commands/` respectively

**Scenario 2: --agent flag overrides auto-detection**

- **Given**: The working directory contains `.claude/` but the user specifies `--agent opencode`
- **When**: `deviate init --agent opencode` is invoked
- **Then**: Only the OpenCode agent receives command exports, regardless of auto-detected agents

**Scenario 3: Interactive fallback when no agent is detected**

- **Given**: The working directory contains no recognizable agent directories
- **When**: `deviate init` is invoked
- **Then**: The CLI prompts the user interactively to select from supported agent platforms; on selection, commands are exported to the chosen agent's directory

**Scenario 4: Contract handoff defaults to .deviate/session.json**

- **Given**: `deviate init` has been run and `.deviate/session.json` exists
- **When**: A meso-layer `pre` command (e.g., `deviate specify pre`) writes contract state
- **Then**: The contract is persisted to `.deviate/session.json` (not a temp file) by default; `.deviate/session.json` is listed in `.gitignore`

### US-007-SESSION: Dual-Mode Session State with Divergence Detection

- **Upstream Requirement Traceability**: FR-005
- **Description**: Implement dual-mode session state that enforces strict phase ordering across both Macro and Meso layers while also validating filesystem state against expected artifacts. Detect and recover from divergence when the user tampers with filesystem state or git history.

**Scenario 1: Strict phase ordering enforced across layers**

- **Given**: `SessionState.current_phase` is `IDLE`
- **When**: A transition to `SPECIFY` is attempted (skipping `EXPLORE`, `RESEARCH`, `PRD`, `SHARD`)
- **Then**: The transition is rejected with a `TransitionViolationError` because `IDLE` → `SPECIFY` is not a valid meso-layer entry point (must enter via `SHARD` → `SPECIFY`)

**Scenario 2: Filesystem state validation detects missing artifacts**

- **Given**: `SessionState.current_phase` is `RESEARCH` but `explore.md` has been manually deleted from the feature bucket
- **When**: `deviate research pre` is invoked
- **Then**: The divergence is detected; a warning is emitted indicating `explore.md` is missing; the command exits with a non-zero code

**Scenario 3: State reconstruction from worktree on session.json loss**

- **Given**: `.deviate/session.json` has been deleted while a worktree still exists at the expected path with `spec.md` in the bucket directory
- **When**: `deviate specify post` is invoked
- **Then**: The system reconstructs minimal session state by scanning the worktree for `spec.md` and related artifacts; a warning about state reconstitution is emitted; the post-phase completes successfully

**Scenario 4: Task ID accepts both T{NNN} and T{NNN}: formats**

- **Given**: A task reference string `T005:` or `T005` is provided as input
- **When**: The task ID parser validates the reference
- **Then**: Both formats are accepted and normalized to the same internal representation

## SYSTEM_STATUS_SUMMARY

| Parameter | Value |
|-----------|-------|
| STATUS | SPECIFIED |
| EPIC_SLUG | 001-deviate-cli-python |
| BRANCH_NAME | feat/001-deviate-cli-python/005-cli-architecture-realignment-skill-integration |
| SPEC_PATH | specs/001-deviate-cli-python/005-cli-architecture-realignment-skill-integration/spec.md |
| ISSUE_ID | ISS-005 |
| NEXT_ACTION | Run `/deviate-tasks` to decompose this spec into TDD-cycle tasks |
