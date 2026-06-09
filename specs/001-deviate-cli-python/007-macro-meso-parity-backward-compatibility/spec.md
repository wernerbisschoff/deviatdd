# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/007-macro-meso-parity-backward-compatibility/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: `001-deviate-cli-python`
- **Issue ID**: ISS-007
- **Issue Title**: `[FR-007] Macro/Meso Parity & Backward Compatibility`
- **Workstation Paths**:
  - `src/deviate/cli/macro.py` — explore, research, prd, shard contracts & validation
  - `src/deviate/cli/meso.py` — tasks, pr contracts & validation
  - `src/deviate/cli/__init__.py` — CLI wiring (`--dry-run` flags, new options)
  - `src/deviate/core/validation.py` — content validation for post-phases
  - `src/deviate/state/` — session, config updates for new features
  - `~/.claude/skills/deviate-*.sh` — bash scripts (must remain functional)
- **Spec Source**: ISS-007 issue body supersedes the PRD for FR-007 definitions (PRD lacks FR-007 — noted as `[NEEDS_CLARIFICATION]` pending PRD update)

## THE_PROBLEM_CONTRACT

As a developer migrating from bash to Python CLI, I need the macro (`explore`, `research`, `prd`, `shard`) and meso (`tasks`, `pr`) commands to emit complete JSON contracts with all fields present in the bash originals, enforce rigorous content validation in post-phases, and support all features like `--dry-run`, `--issue-id`, and pre-commit hooks — all while maintaining backward compatibility with the existing bash skill workflow — so that no information is lost in the transition and both systems can coexist during the cutover.

## SCOPE_BOUNDARIES

### Hard Inclusions

**Priority 1 — Contract Field Parity**
- **explore pre**: Add missing fields (`repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `epic_id`, `is_greenfield`, `timestamp`). Bash emits 15 fields; Python currently emits 5.
- **research pre**: Add missing fields (`repo_root`, `git_branch`, `constitution_path`, all commands, `is_greenfield`, timestamps). Bash emits 18+ fields; Python currently emits 3.
- **prd pre**: Add missing fields (`repo_root`, `git_branch`, `constitution_path`, `test/lint/type_check cmds`, timestamps). Bash emits 17 fields; Python currently emits 2.
- **shard pre**: Add missing fields (`repo_root`, `git_branch`, `constitution_path`, `issues_dir`, `plan_target`, `dry_run`). Bash emits 17 fields; Python currently emits 4.
- **tasks pre**: Emit a full JSON contract with `issue_id`, `spec_path`, `worktree`, constitution commands. Currently emits no contract at all.
- **pr pre**: Emit a full JSON contract with branch info, PR metadata, git state. Currently emits no contract at all.

**Priority 2 — Content Validation**
- **explore post**: Validate 5 required sections (`PROBLEM_DEFINITION`, `DISCOVERY_AUDIT_RESULTS`, `CONSTITUTION_QUOTES`, `FILE_REGISTRY`, `STATUS_SUMMARY`). Currently only checks non-empty.
- **research post**: Validate 9 `design.md` sections + 6 `data-model.md` sections + constitutional alignment audit. Currently only checks non-empty.
- **shard post**: Validate individual `NNN-*.md` shard files with YAML frontmatter. Currently validates wrong files (`spec.md` + `tasks.md`).
- **tasks post**: Validate `T{NNN}` format, checkboxes, verification commands. Currently only checks non-empty.

**Priority 3 — Missing Features**
- `--dry-run` flag on `prd`, `shard`, `tasks`, `pr` commands (currently only on `specify`).
- `--issue-id` option on `tasks post` (bash derives spec from explicit issue ID).
- `deviate run --all` dispatcher command: reads task `execution_mode` and routes to TDD cycle or execute phase accordingly.
- Pre-commit hooks in post-phase (bash runs pre-commit if config exists).
- Mise setup in new worktrees (bash installs dependencies).

**Cross-Cutting — Dual Task ID Format Support**
- **Legacy format**: `T{NNN}` (e.g., `T001`, `T002`) — must be readable/parseable by all validation and dispatch logic.
- **New format**: `TSK-{issue_number}-{NN}` (e.g., `TSK-007-01`) — primary format for new task creation going forward.
- **Validation**: `tasks post` must accept both formats, and `tasks pre` must generate new tasks using `TSK-{issue_number}-{NN}`, aligning with `DeviaTDD-architecture.md` §5.1.
- **Dispatch**: `deviate run` must recognize both formats when resolving a task ID.

### Defensive Exclusions

- Micro-layer TDD sandbox execution (red, green, refactor, execute, e2e, prune, hotfix, YELLOW, JUDGE) — covered by ISS-004.
- State persistence & concurrency safety (fcntl locking, atomic writes) — covered by ISS-006.
- Core module business logic (repo, contract, constitution, epic, issues, commit, prd, skills) — covered by ISS-005.
- CLI initialization & governance provisioning — covered by ISS-001.
- Macro-layer state & ledger management — covered by ISS-002.
- Meso-layer specification & task decomposition — covered by ISS-003.

**Backward Compatibility Constraint** (soft): All new Python code must coexist with old bash scripts in `~/.claude/skills/deviate-*.sh`. Bash skills must remain fully functional — no breaking changes to the contract handoff format they produce or consume. Python CLI must detect and work correctly alongside bash-managed worktrees, ledgers, and session state. No changes to the JSONL ledger schema or issue file format that would break bash tooling.

## PERFORMANCE_CONSTRAINTS

- `L_max <= 500ms` for `deviate init` command execution.
- `L_max <= 200ms` per agent export mapping operation.
- Offline deterministic context resolution must complete in `L_max <= 50ms`.
- Mitigation for Rich/Pydantic overhead: Lazy-load Rich components and defer non-critical Pydantic validation until state mutation boundaries.

## MULTI_TIERED_VERIFICATION_TARGETS

- **Unit Tests**: `tests/test_cli/test_macro_contracts.py`, `tests/test_cli/test_meso_contracts.py`, `tests/test_core/test_validation.py`
- **Integration Tests**: `tests/test_integration/test_parity.py` (runs both bash and Python CLI, compares contract outputs)
- **Verification Commands**:
  - `mise run test` — unit test suite
  - `mise run check` — all validation checks
  - `pytest tests/test_cli/test_macro_contracts.py -v`
  - `pytest tests/test_cli/test_meso_contracts.py -v`
  - `pytest tests/test_integration/test_parity.py -v`

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-CONTRACT-P1: Explore pre emits complete JSON contract
* **Upstream Requirement Traceability**: FR-007-CONTRACT [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Explore pre contract field parity**
  1. **Given** the Python `deviate explore pre` command is invoked with a feature description and `--dry-run`
  2. **When** it emits a JSON contract on stdout
  3. **Then** the contract MUST include all fields emitted by `bash ~/.claude/skills/deviate-explore.sh pre`: `repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `epic_id`, `is_greenfield`, `timestamp`, `status`, `phase`, `issue_id`, `feature_bucket`, `feature_dir`, `explore_path`

### US-002-CONTRACT-P1: Research pre emits complete JSON contract
* **Upstream Requirement Traceability**: FR-007-CONTRACT [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Research pre contract field parity**
  1. **Given** the Python `deviate research pre` command is invoked with `--dry-run`
  2. **When** it emits a JSON contract on stdout
  3. **Then** the contract MUST include all fields emitted by `bash ~/.claude/skills/deviate-research.sh pre`: `repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `is_greenfield`, `timestamp`, `status`, `phase`, `issue_id`, `feature_bucket`, `explore_path`, `design_target`, `data_model_target`

### US-003-CONTRACT-P1: PRD pre emits complete JSON contract
* **Upstream Requirement Traceability**: FR-007-CONTRACT [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: PRD pre contract field parity**
  1. **Given** the Python `deviate prd pre` command is invoked with `--dry-run`
  2. **When** it emits a JSON contract on stdout
  3. **Then** the contract MUST include all fields emitted by `bash ~/.claude/skills/deviate-prd.sh pre`: `repo_root`, `git_branch`, `constitution_path`, `test_cmd`, `lint_cmd`, `type_check_cmd`, `timestamp`, `status`, `phase`, `issue_id`, `feature_bucket`, `design_path`, `data_model_path`

### US-004-CONTRACT-P1: Shard pre emits complete JSON contract
* **Upstream Requirement Traceability**: FR-007-CONTRACT [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-002-MACRO
* **Scenario: Shard pre contract field parity**
  1. **Given** the Python `deviate shard pre` command is invoked with `--dry-run`
  2. **When** it emits a JSON contract on stdout
  3. **Then** the contract MUST include all fields emitted by `bash ~/.claude/skills/deviate-shard.sh pre`: `repo_root`, `git_branch`, `constitution_path`, `issues_dir`, `plan_target`, `dry_run`, `timestamp`, `status`, `phase`, `issue_id`, `prd_path`, `shard_count`

### US-005-CONTRACT-P1: Tasks pre emits a full JSON contract
* **Upstream Requirement Traceability**: FR-007-CONTRACT [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-003-MESO
* **Scenario: Tasks pre full JSON contract emission**
  1. **Given** the Python `deviate tasks pre` command is invoked with `--dry-run`
  2. **When** it emits output on stdout
  3. **Then** the output MUST be a valid JSON object containing `issue_id`, `spec_path`, `worktree_full`, `constitution_path`, `constitution_test_command`, `constitution_lint_command`, `timestamp`, `status`, and `phase`

### US-006-CONTRACT-P1: PR pre emits a full JSON contract
* **Upstream Requirement Traceability**: FR-007-CONTRACT [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-003-MESO
* **Scenario: PR pre full JSON contract emission**
  1. **Given** the Python `deviate pr pre` command is invoked with `--dry-run`
  2. **When** it emits output on stdout
  3. **Then** the output MUST be a valid JSON object containing `branch_name`, `base_branch`, `pr_title`, `pr_body`, `git_state`, `timestamp`, `status`, and `phase`

### US-007-VALIDATE-P2: Explore post validates 5 required sections
* **Upstream Requirement Traceability**: FR-007-VALIDATE [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Section-level validation for explore post**
  1. **Given** an `explore.md` file exists that is missing one or more required sections (`PROBLEM_DEFINITION`, `DISCOVERY_AUDIT_RESULTS`, `CONSTITUTION_QUOTES`, `FILE_REGISTRY`, `STATUS_SUMMARY`)
  2. **When** `deviate explore post` is executed
  3. **Then** it MUST exit with a non-zero code and emit a diagnostic listing each missing section

### US-008-VALIDATE-P2: Research post validates design.md and data-model.md sections
* **Upstream Requirement Traceability**: FR-007-VALIDATE [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Multi-artifact content validation for research post**
  1. **Given** a `design.md` file missing 1 or more of its 9 required sections OR a `data-model.md` file missing 1 or more of its 6 required sections
  2. **When** `deviate research post` is executed
  3. **Then** it MUST exit with a non-zero code and emit a diagnostic listing each missing section

### US-009-VALIDATE-P2: Shard post validates individual shard files with YAML frontmatter
* **Upstream Requirement Traceability**: FR-007-VALIDATE [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-002-MACRO
* **Scenario: Correct shard file validation targets**
  1. **Given** a shard output directory containing `NNN-*.md` shard files with YAML frontmatter
  2. **When** `deviate shard post` is executed
  3. **Then** it MUST validate each `NNN-*.md` file for valid YAML frontmatter, issue title, and FR mapping (NOT `spec.md` or `tasks.md`)

### US-010-VALIDATE-P2: Tasks post validates both T{NNN} and TSK formats with checkboxes
* **Upstream Requirement Traceability**: FR-007-VALIDATE [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-003-MESO
* **Scenario: Legacy T{NNN} format validation**
  1. **Given** a `tasks.md` file containing task entries with legacy `T{NNN}` format (e.g., `T001`, `T002`), checkboxes, and verification commands
  2. **When** `deviate tasks post` is executed
  3. **Then** it MUST validate each task entry for the correct `T{NNN}` format, present checkboxes, and non-empty verification commands
* **Scenario: New TSK format validation**
  1. **Given** a `tasks.md` file containing task entries with new `TSK-{issue_number}-{NN}` format (e.g., `TSK-007-01`)
  2. **When** `deviate tasks post` is executed
  3. **Then** it MUST validate each task entry for the correct `TSK-{issue_number}-{NN}` format, present checkboxes, and non-empty verification commands

### US-011-FEATURES-P3: Dry-run flag on remaining commands
* **Upstream Requirement Traceability**: FR-007-FEATURES [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Dry-run on prd pre**
  1. **Given** the Python `deviate prd pre` command
  2. **When** invoked with `--dry-run`
  3. **Then** it emits a JSON contract on stdout but does NOT create any artifacts or modify any files
* **Scenario: Dry-run on shard pre**
  1. **Given** the Python `deviate shard pre` command
  2. **When** invoked with `--dry-run`
  3. **Then** it emits a JSON contract on stdout but does NOT create any artifacts or modify any files
* **Scenario: Dry-run on tasks pre**
  1. **Given** the Python `deviate tasks pre` command
  2. **When** invoked with `--dry-run`
  3. **Then** it emits a JSON contract on stdout but does NOT append any task records to the ledger
* **Scenario: Dry-run on pr pre**
  1. **Given** the Python `deviate pr pre` command
  2. **When** invoked with `--dry-run`
  3. **Then** it emits a JSON contract on stdout but does NOT create a pull request

### US-012-FEATURES-P3: Issue-id option on tasks post
* **Upstream Requirement Traceability**: FR-007-FEATURES [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-003-MESO
* **Scenario: Explicit issue ID for tasks post**
  1. **Given** a task ledger directory with entries for `ISS-006`
  2. **When** `deviate tasks post --issue-id ISS-006` is executed
  3. **Then** it resolves the spec target from `ISS-006` and validates the corresponding `tasks.md`
* **Scenario: Invalid issue ID rejection**
  1. **Given** a task ledger that does not contain `ISS-999`
  2. **When** `deviate tasks post --issue-id ISS-999` is executed
  3. **Then** it exits with a non-zero code and emits an `INVALID_ISSUE_ID` error

### US-013-FEATURES-P3: Pre-commit hooks in post-phase
* **Upstream Requirement Traceability**: FR-007-FEATURES [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Pre-commit execution in post-phase**
  1. **Given** a repository with `.githooks/` configured and `core.hooksPath` set
  2. **When** any post-phase command (`explore post`, `research post`, `prd post`, `shard post`, `tasks post`) commits an artifact
  3. **Then** the commit MUST trigger the configured pre-commit hooks (or detect and warn if hooks are missing)
* **Scenario: Graceful pre-commit skip when missing**
  1. **Given** a repository without `.githooks/` directory or `core.hooksPath` configuration
  2. **When** any post-phase command commits an artifact
  3. **Then** it MUST proceed without error and emit an informational notice about missing hooks

### US-014-FEATURES-P3: Mise setup in new worktrees
* **Upstream Requirement Traceability**: FR-007-FEATURES [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-005-ARCHITECTURE
* **Scenario: Mise install in newly created worktree**
  1. **Given** a fresh worktree is created by any pre-phase command (`specify pre`, `tasks pre`)
  2. **When** mise is available on `PATH` and `.mise.toml` exists in the repo root
  3. **Then** the pre-phase MUST run `mise trust && mise install && mise run setup` inside the new worktree
* **Scenario: Graceful skip when mise unavailable**
  1. **Given** a fresh worktree is created but mise is NOT available on `PATH`
  2. **When** the pre-phase attempts mise setup
  3. **Then** it MUST proceed without error and emit a warning that mise setup was skipped

### US-015-FEATURES-P3: Deviate run dispatcher command
* **Upstream Requirement Traceability**: FR-007-FEATURES [NEEDS_CLARIFICATION — PRD lacks FR-007 entry]; closest PRD FR: FR-004-MICRO
* **Scenario: Run dispatches TDD task to RED-GREEN-REFACTOR**
  1. **Given** a task with `execution_mode: TDD` in `CREATED` status
  2. **When** `deviate run TSK-007-01` is invoked
  3. **Then** it enters the TDD cycle: RED (write failing test), GREEN (implement), REFACTOR (polish), and marks the task COMPLETED
* **Scenario: Run dispatches IMMEDIATE task to execute phase**
  1. **Given** a task with `execution_mode: IMMEDIATE` in `CREATED` status
  2. **When** `deviate run TSK-007-02` is invoked
  3. **Then** it enters the execute phase (no RED test generation) and proceeds directly to implementation and verification
* **Scenario: —all flag iterates all CREATED tasks**
  1. **Given** a task ledger with multiple CREATED task entries of mixed modes (TDD and IMMEDIATE)
  2. **When** `deviate run --all` is invoked
  3. **Then** it iterates through available tasks, dispatching each according to its `execution_mode`, until all are COMPLETED or a failure is encountered

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|----------|-------|
| **STATUS** | SPECIFY_IN_PROGRESS |
| **EPIC_SLUG** | 001-deviate-cli-python |
| **BRANCH_NAME** | feat/001-deviate-cli-python/007-macro-meso-parity-backward-compatibility |
| **SPEC_PATH** | specs/001-deviate-cli-python/007-macro-meso-parity-backward-compatibility/spec.md |
| **ISSUE_ID** | ISS-007 |
| **NEXT_ACTION** | POST_VALIDATE_AND_COMMIT |
