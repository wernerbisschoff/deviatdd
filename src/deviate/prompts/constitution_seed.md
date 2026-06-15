# Project Constitution

[CONSTITUTION_VERSION]: 0.1.0

---

## [1_ARCHITECTURAL_PRINCIPLES]

- **Three-Layer Architecture**: Macro (feature scoping), Meso (issue engineering), Micro (TDD sandbox). Each layer has strict phase gates — no layer may be skipped.
- **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten. Canonical state is derived by sequential ledger parsing.
- **Git Isolation Principle**: Every task loop executes on a clean git branch or worktree. Commits are automatic at each phase boundary.
- **Tamper Guard & Micro-Sandboxing**: GREEN phase resets test directories to post-RED commit state before evaluation. Micro-layer LLM execution is strictly sandboxed: write access is granted **only** to files matching `src/**/*.py`. All `tests/`, `specs/`, and configuration files are strictly read-only during Micro-layer execution. Any mutation outside this allow-list triggers an immediate rollback.
- **Human-in-the-Loop (HITL)**: Three mandatory gates (Design Approval, Contract Sign-Off, Final Merge Audit) prevent autonomous drift. No gate may be programmatically bypassed.
- **Session Continuity**: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases. Model switching mid-task is prohibited.
- **Model Tiering**: V4 Flash for high-frequency phases (RED, GREEN, REFACTOR, `/explore`); V4 Pro for compliance (JUDGE, YELLOW); Qwen 3.7+ for architecture (`/research`, `/prd`, `/shard`).

## [2_TECH_STACK_STANDARDS]

### [2_1_BACKEND]
- Project: ${PROJECT_NAME}
- Repository root: ${REPO_ROOT}
- Python 3.13
- Target: CLI application (`deviate`)
- Framework: Typer (CLI entry points) with Rich for terminal I/O
- Backend framework: ${TARGET_BACKEND_FRAMEWORK}

### [2_2_FRONTEND]
- None (CLI-only application; no web or GUI frontend)

### [2_3_DATABASE]
- No persistent database runtime (all state tracked in JSONL ledgers and TOML config)
- Session state: JSON files under `.deviate/`
- Issue ledger: `specs/issues.jsonl` (append-only JSONL)
- Task ledger: `specs/**/tasks.jsonl` (append-only JSONL)
- Config: TOML via `.deviate/config.toml`

### [2_4_INFRASTRUCTURE]
- Micro-sandbox: Aider Python API (`aider.coders.Coder`) as LLM execution substrate
- Version control: Git (all phase commits, lock branches for concurrency)
- No containerization required (local execution on host)

### [2_5_TOOLING]
- Package manager: `uv`
- Package manager identifier: ${TARGET_PACKAGE_MANAGER}
- Test runner: `pytest`
- Test runner identifier: ${TARGET_TEST_RUNNER}
- Linter: `ruff` (lint + format)
- E2E testing: `bats` (Bash automated test system)
- Task runner: `mise` (see `mise.toml` for all tasks)
- Code quality gate: `mise run check`

## [3_TESTING_PROTOCOLS]

### [3_1_FRAMEWORK]
- `TEST_FRAMEWORK`: pytest
- `TEST_ROOT`: tests
- `TEST_EXT`: .py
- `TEST_COMMAND`: pytest tests/ -v
- `LINT_COMMAND`: ruff check .
- `TYPE_CHECK_COMMAND`: (none — mypy is not yet configured)
- `E2E_COMMAND`: bats tests/e2e/

### [3_2_COVERAGE]
- Coverage target: >= 80% (configurable via `.deviate/config.toml`)
- Coverage minimum threshold: ${TARGET_COVERAGE_MINIMUM}
- RED phase tests must fail with `AssertionError` or `NotImplementedError` — syntax crashes are rejected
- GREEN phase must pass all tests; Tamper Guard resets unauthorized test edits
- REFACTOR phase runs regression gate: tests must re-pass after polish

## [4_DEVELOPMENT_WORKFLOW]

### [4_1_BRANCH_STRATEGY]
- Feature branches follow: `feat/<epic-slug>/<issue-slug>`
- Hotfix branches follow: `fix/<short-description>`
- All commits must be signed and reference the task ID

### [4_2_COMMIT_CONVENTION]
- Format: `<type>(<scope>): <description>`
- Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`
- Scope is the task ID (e.g., `T001`)
- Body wraps at 72 characters

### [4_3_REVIEW_PROCESS]
- All code must pass `mise run check` before merge
- HITL Gate 3 (Final Merge Audit) is mandatory for all feature work
- PR descriptions must reference the spec.md acceptance criteria

## [5_DEFINITION_OF_DONE]
- [ ] Code implemented (satisfies acceptance criteria from `spec.md`)
- [ ] Tests passing (pytest with clean exit code 0)
- [ ] Lint passing (ruff check with no violations)
- [ ] Judge phase passed (git diff validated against `spec.md` invariants)
- [ ] E2E tests passing (if applicable; bats for CLI integration)
- [ ] Documentation updated (`spec.md` and `design.md` reflect final implementation)
- [ ] No governance violations (constitution rules upheld, no HITL gates bypassed)
- [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)

## [6_VERSION_HISTORY]
- 0.1.0 — Initial constitution generation for DeviaTDD Python CLI

## [SEMANTIC_ANCHORS]
- `CONSTITUTION_VERSION`
- `ARCHITECTURAL_PRINCIPLES`
- `TECH_STACK_STANDARDS`
- `TESTING_PROTOCOLS`
- `DEVELOPMENT_WORKFLOW`
- `DEFINITION_OF_DONE`
- `VERSION_HISTORY`
- File paths: `specs/constitution.md`, `specs/issues.jsonl`, `.deviate/config.toml`
- Framework names: pytest, ruff, uv, rich, typer, bats, aider
