# Project Constitution

Version: 0.11.0

---

## 1. Architectural Principles

- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Macro PRD/shard/adhoc artifacts carry User Stories plus ATDD acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract. The three layers have strict phase gates — no layer may be skipped. (Gate 2 was removed: there is no human-approval step between Tasks and Micro — the system auto-advances.)
- **Optional Product Layer**: An opt-in `product` pack (`/deviate-flows`, `/deviate-architecture`, `/deviate-release`) authors standalone planning artifacts under `specs/_product/` for greenfield scope tracking. It never gates execution, writes no ledger, and defines no `flow_refs` contract — FLOW-NN IDs are prose anchors within product artifacts only. No Macro/Meso/Micro phase reads `specs/_product/` or emits flow pointers.
- **User Scenarios Are the Flow**: RED must encode the issue's user scenarios (User Stories + ATDD on the shard issue) as failing tests before GREEN. GREEN still cannot edit tests. After COMPLETED, those tests *are* the flow.
- **Append-Only Ledger Protocol**: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten. Canonical state is derived by sequential ledger parsing. Issue ids follow a per-epic format: new issues in a numbered epic bucket (`001-…`, `002-…`) emit `<epic-prefix>-<ordinal>` (e.g. `002-001`), where `<epic-prefix>` is the leading 3-digit segment of the epic bucket dir; the adhoc bucket and bootstrap contexts fall back to the legacy global-counter `ISS-NNN`. Legacy `ISS-NNN` rows in `specs/issues.jsonl` resolve unchanged — the resolve layer is format-agnostic, only uniqueness matters.
- **Git Isolation Principle**: Every task loop executes on a clean git branch or worktree. Commits are automatic at each phase boundary.
- **Micro-Layer Scope**: GREEN phase writes only to `src/` and permitted implementation paths. Any mutation outside this allow-list is flagged by the JUDGE phase as a scope violation.
- **Human-in-the-Loop (HITL)**: Two remaining mandatory gates (Design Approval after research, Final Merge Audit after micro) prevent autonomous drift. Gate 2 (post-Tasks approval) was removed — the system never blocks on human approval; `deviate run` chains meso into micro end-to-end. No remaining gate may be programmatically bypassed.
- **Session Continuity**: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases. Model switching mid-task is prohibited.
- **Model Tiering**: V4 Flash for high-frequency phases (RED, GREEN, REFACTOR, `/explore`); V4 Pro for compliance and planning (JUDGE, `/plan`); Qwen 3.7+ for architecture (`/research`, `/prd`, `/shard`). This tiering is enforced via `.deviate/config.toml` `[models]` section — the `default` key sets the fallback model, and per-phase keys override it.
- **Config-Driven Model Routing**: Phase→model assignments are declared in `.deviate/config.toml` under `[models]`. The `default` key sets the model for all phases without an explicit entry. Any other key (e.g., `judge`, `plan`, `red`) is treated as a phase name. Resolution order: phase-specific key → `default` key → no model flag (backend-native default). `opencode`, `droid`, `pi`, `omp`, and `codex` backends support `--model`; `claude` backend ignores model config silently. Codex setup seeds `[models].default = "gpt-5.6-luna"` and `[agent].reasoning_effort = "high"` when those keys are missing/empty; spawned `codex exec` receives `-c model_reasoning_effort=<value>` from that field (official values `minimal|low|medium|high|xhigh`).

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

- [ ] Code implemented (satisfies assigned `AC-PLAN-NNN` scenarios from `plan.md`)
- [ ] Tests passing (pytest with clean exit code 0)
- [ ] Lint passing (ruff check with no violations)
- [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)
- [ ] E2E tests passing (if applicable; bats for CLI integration)
- [ ] Documentation updated (`plan.md` Acceptance Contract, `spec.md`, and `design.md` reflect final implementation; `explore.md` lives at `specs/{NNN}-<slug>/explore.md` after `deviate research pre`, alongside design and data-model artifacts)
- [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies); docs-only, test-only, CI/tooling, and behavior-preserving refactors are exempt
- [ ] No governance violations (constitution rules upheld, no remaining HITL gates bypassed; Gate 2 was removed)
- [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)

## 6. Version History

- 0.11.0 — Reintroduced the Product layer as an optional `product` pack (`/deviate-flows`, `/deviate-architecture`, `/deviate-release`) authoring standalone `specs/_product/` planning artifacts for greenfield scope tracking. No ledger, no `flows.jsonl`, no `flow_refs` contract, no downstream reads — FLOW-NN IDs are prose anchors only.
- 0.10.0 — Removed the Product layer. Three layers remain: Macro, Meso, Micro. Dropped `flows.jsonl` from the append-only protocol and Database sections. User Stories + ATDD stay on the shard issue; RED encodes those user scenarios as failing tests. No replacement catalog, `_product/` folder, or `flow_refs` pointer.
- 0.9.0 — Cut v2.15.0 release. Records the release of accumulated micro-layer hardening, doc/code drift fixes, and Product-layer discipline additions since v2.4.0 (2026-07-04).
- 0.8.0 — Removed HITL Gate 2 (post-Tasks `deviate meso approve` approval) entirely. The system never blocks on human approval; `deviate run` chains meso into micro end-to-end. Two HITL gates remain: Gate 1 (Design Approval after research) and Gate 3 (Final Merge Audit after micro). §1 Architectural Principles (Four-Layer Architecture, HITL principle) and §5 Definition of Done updated to reflect the removal.
- 0.7.0 — Added `specs/_product/flows.jsonl` to the append-only ledger protocol (§1); enumerated alongside `issues.jsonl` / `tasks.jsonl` in §2 *Database*; seeded via `deviate explore post` with `FlowRecord` identity rows + `FlowEvent` append-only event rows. Cross-branch merge safety extends via `merge=union` in `.gitattributes`. Derivation of `FlowCoverage` (drift-flag taxonomy) is emit-only and never persisted; canonical state is derived by sequential ledger parsing per §1
- 0.6.0 — Promoted the Product layer (Flows → Architecture → Release) into §1 Architectural Principles as an optional fourth layer above Macro; updated the principle count from three to four layers; aligned GREEN-scope enforcement language with v2.2.0 (JUDGE performs scope verification against `src/` + permitted paths — no separate TamperGuard)
- 0.5.0 — Added CHANGELOG discipline: §5 Definition of Done now requires `CHANGELOG.md` `[Unreleased]` updates for user-visible changes; mirrored in `AGENTS.md` as a cross-cutting rule, and as a checkbox in the PR template
- 0.4.0 — Added cross-branch merge strategy for append-only JSONL ledgers via `merge=union` in `.gitattributes`; provisioned by `deviate setup`/`deviate init` to prevent line-level conflicts when concurrent feature branches both append to `specs/issues.jsonl`; semantic-duplicate records still resolved by sequential-parse canonical-state per §1

- 0.2.0 — Added `[models]` config section for per-phase model routing; documented resolution order and backend support matrix
- 0.1.0 — Initial constitution generation for DeviaTDD Python CLI
