<!-- MANAGED_BY: tools:init -->

## ⚙️ Project Execution Contract

- **Repository**: single-language (Python)
- **Execution Mode**: TDD (Red-Green-Refactor via deviate cycle)
- **Performance**: L_max ≤ 500ms init, ≤ 200ms per agent export, full test suite < 30s
- **Authority**: `git` commits · `specs/constitution.md` · `specs/DeviaTDD-api.md` + `DeviaTDD-architecture.md`

## ⚡ Fast-Lane Execution

Use `mise run <task>`. All task definitions live in `.mise.toml`; git hooks in `.githooks/`.

| Task | Purpose |
|------|---------|
| `mise run test` / `test-e2e` | Unit / E2E tests |
| `mise run lint` / `lint-fix` / `format` / `format-check` | Style |
| `mise run check-types` / `check` / `fix` | Validation bundles |
| `mise run setup` / `clean` / `help` | Lifecycle |

## 🔐 Commit Authority

Commit after each verified loop. Never `--no-verify`. Preserve all semantic anchors.

## 🧪 Git Isolation (pointer — see source)

Tests: `tests/conftest.py` (`_git_env`, `tmp_git_repo`). Every test git call: `cwd=<tmp_git_repo>` + `env=_git_env()`.
Production: `src/deviate/core/_shared.py::git_env` is the canonical helper. Branch creation lives in `src/deviate/cli/feature.py::_create_feature_branch`; micro-layer agents must never run branch-mutating git commands.

## ⚡ Test Performance (pointer — see source)

`src/deviate/cli/micro.py::_run_pytest` invokes pytest as a subprocess (~5s). Tests calling CLI commands that hit this function MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture to keep the full suite under 30s.

## 📐 Spec Alignment

`specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` are authoritative. CLI commands, phase workflows, model routing, file structure, and HITL gates MUST be reflected in both in the same commit as the implementation change.

## 📝 CHANGELOG Discipline

User-visible changes MUST append a bullet to `CHANGELOG.md` under `[Unreleased]` in the same commit as the implementation change. "User-visible" means: new commands/flags/subcommands, behavior changes, user-affecting bug fixes, breaking changes, and new user-visible dependencies. Exempt: docs-only, test-only, CI/tooling, and internal refactors with no behavior change. `specs/constitution.md` §5 mirrors this in the Definition of Done; the PR template's CHANGELOG checkbox enforces it at review.

## 🛠 DeviaTDD Phase Architecture

### Three-Layer Model

| Layer | Phases | Output Artifact |
|-------|--------|-----------------|
| **Macro** | explore → research → prd → shard | spec-enriched issue files |
| **Meso** | (HITL Gate 2) → plan → tasks → review | `plan.md`, `tasks.md` |
| **Micro** | red → green → judge → refactor | passing test + ledger entry |

### HITL Gates (no programmatic bypass)

- **Gate 1**: after `/research`, before `/prd` — design + data-model approval
- **Gate 2**: after `/shard`, before `/plan` — spec-enriched issue sign-off
- **Gate 3**: after all tasks — final merge audit

### Model Tiering

| Tier | Phases |
|------|--------|
| V4 Flash (low-cost) | explore, red, green, refactor |
| V4 Pro (cached/compliance) | plan, tasks, judge |
| Qwen 3.7+ [Thinking] | research, prd, shard, adhoc |

Per-phase overrides: `.deviate/config.toml` → `[models]` → `default` + phase keys. Resolution: `src/deviate/state/config.py::resolve_phase_model`.

### Append-Only Ledger Protocol

`specs/issues.jsonl`, `specs/**/tasks.jsonl`, and `specs/_product/flows.jsonl` are append-only. Canonical state is derived by sequential ledger parsing.

### Git Isolation Principle

Every task loop runs on a clean branch/worktree. Commits happen at phase boundaries. **Never delete a branch unless the user explicitly requests it.**


### Session Continuity

Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR (no model switches). JUDGE runs in an isolated V4 Pro session.
## 🐍 Python-Only Architecture

Slash commands are package resources under `src/deviate/prompts/commands/<name>.md`, invoked via `deviate <subcommand>` and installed to `<workdir>/.<agent>/commands/<name>.md` by `deviate setup`. No `.sh` files in `prompts/`. Layer routing: `src/deviate/prompts/assembly.py::_LAYER_MAP`. All task execution runs through `uv run` (`.mise.toml`).

## 📚 Offline Documentation (libref)

Prefer `libref query <lib> "<topic>"` over web fetching. Workflow: `libref list` → `libref query` → `libref add <git-url>` (register a missing source) → web fetch (last resort).
## 🔧 Quick-Start Workflow

`deviate explore` → `research` → `prd` → `shard` → (Gate 2) → `plan` → `tasks` → run each task via RED → GREEN → REFACTOR → `deviate e2e`.

## 📝 Prompt Edit Discipline

Edit skill/prompt templates in `src/deviate/prompts/` only. `~/.config/opencode/skills/` is a read-only install mirror.

## 🌳 Graphite (when `graphite = true` in `.deviate/config.toml`)

`gt create -am "msg"` (or `-m` if tree clean) → `gt submit --stack` → `gt sync`. Never mix `git checkout -b` with `gt`, never `gh pr create` when Graphite is on.
