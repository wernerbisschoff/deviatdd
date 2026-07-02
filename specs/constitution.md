# Project Constitution

Version: 0.5.0

---

## 1. Architectural Principles

- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped.
- **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten. Canonical state is derived by sequential ledger parsing.
- **Git Isolation Principle**: Every task loop executes on a clean git branch or worktree. Commits are automatic at each phase boundary.
- **Micro-Layer Scope**: GREEN phase writes only to `src/` and permitted implementation paths. Any mutation outside this allow-list is flagged by the JUDGE phase as a scope violation.
- **Human-in-the-Loop (HITL)**: Three mandatory gates (Design Approval after research, Contract Sign-Off after shard, Final Merge Audit after micro) prevent autonomous drift. No gate may be programmatically bypassed.
- **Session Continuity**: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases. Model switching mid-task is prohibited.
- **Model Tiering**: V4 Flash for high-frequency phases (RED, GREEN, REFACTOR, `/explore`); V4 Pro for compliance and planning (JUDGE, `/plan`); Qwen 3.7+ for architecture (`/research`, `/prd`, `/shard`). This tiering is enforced via `.deviate/config.toml` `[models]` section — the `default` key sets the fallback model, and per-phase keys override it.
- **Config-Driven Model Routing**: Phase→model assignments are declared in `.deviate/config.toml` under `[models]`. The `default` key sets the model for all phases without an explicit entry. Any other key (e.g., `judge`, `plan`, `red`) is treated as a phase name. Resolution order: phase-specific key → `default` key → no model flag (backend-native default). Both `opencode` and `droid` backends support `--model`; `claude` backend ignores model config silently.

## 2. Tech Stack Standards

### Backend
- Python 3.13
- Target: CLI application (`deviate`)
- Framework: Typer (CLI entry points) with Rich for terminal I/O

### Frontend
- None (CLI-only application; no web or GUI frontend)

### Database
- No persistent database runtime (all state tracked in JSONL ledgers and TOML config)
- Session state: JSON files under `.deviate/`
- Issue ledger: `specs/issues.jsonl` (append-only JSONL)
- Task ledger: `specs/**/tasks.jsonl` (append-only JSONL)
- Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment

### Infrastructure
- Micro-sandbox: Aider Python API (`aider.coders.Coder`) as LLM execution substrate
- Version control: Git (all phase commits, lock branches for concurrency)
- No containerization required (local execution on host)

### Tooling
- Package manager: `uv`
- Test runner: `pytest`
- Linter: `ruff` (lint + format)
- E2E testing: `bats` (Bash automated test system)
- Task runner: `mise` (see `mise.toml` for all tasks)
- Code quality gate: `mise run check`

## 3. Testing Protocols

### Framework
- Test framework: pytest
- Test root: `tests/`
- Test extension: `.py`
- Test command: `pytest tests/ -v`
- Lint command: `ruff check .`
- E2E command: `bats tests/e2e/`

### Coverage
- Coverage target: >= 80%
- GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files
- REFACTOR phase runs regression gate: tests must re-pass after polish

## 4. Development Workflow

### Branch Strategy
- Feature branches follow: `feat/<epic-slug>/<issue-slug>`
- Hotfix branches follow: `fix/<short-description>`
- All commits must reference the task ID

### Commit Convention
- Format: `<type>(<scope>): <description>`
- Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`
- Scope is the task ID (e.g., `T001`)
- Body wraps at 72 characters

### Review Process
- All code must pass `mise run check` before merge
- HITL Gate 3 (Final Merge Audit) is mandatory for all feature work
- PR descriptions must reference the spec.md acceptance criteria

## 5. Definition of Done

- [ ] Code implemented (satisfies acceptance criteria from `spec.md`)
- [ ] Tests passing (pytest with clean exit code 0)
- [ ] Lint passing (ruff check with no violations)
- [ ] Judge phase passed (git diff validated against `spec.md` invariants)
- [ ] E2E tests passing (if applicable; bats for CLI integration)
- [ ] Documentation updated (`spec.md` and `design.md` reflect final implementation)
- [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies); docs-only, test-only, CI/tooling, and behavior-preserving refactors are exempt
- [ ] No governance violations (constitution rules upheld, no HITL gates bypassed)
- [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)

## 6. Version History
- 0.5.0 — Added CHANGELOG discipline: §5 Definition of Done now requires `CHANGELOG.md` `[Unreleased]` updates for user-visible changes; mirrored in `AGENTS.md` as a cross-cutting rule, and as a checkbox in the PR template
- 0.4.0 — Added cross-branch merge strategy for append-only JSONL ledgers via `merge=union` in `.gitattributes`; provisioned by `deviate setup`/`deviate init` to prevent line-level conflicts when concurrent feature branches both append to `specs/issues.jsonl`; semantic-duplicate records still resolved by sequential-parse canonical-state per §1

- 0.2.0 — Added `[models]` config section for per-phase model routing; documented resolution order and backend support matrix
- 0.1.0 — Initial constitution generation for DeviaTDD Python CLI
