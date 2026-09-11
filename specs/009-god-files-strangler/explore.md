## Problem Definition
**Statement**: Split god-files and god-nodes in the DeviaTDD repo to make the codebase manageable via a strangler pattern.
**Scope**: Structural inventory of oversized modules, their dependents, and the test/entry-point configuration that constrains a strangler split.
**Exclusions**: No design decisions, no refactoring steps, no implementation work.

## Discovery Audit Results
### Verified Dependencies
- `pyproject.toml` declares `dependencies = ["typer>=0.12", "rich>=13.0", "pydantic>=2.0", "pyyaml>=6.0.3"]` with `requires-python = ">=3.13"`.
- `pyproject.toml` declares dev extras `pytest>=8.0`, `ruff>=0.4`, `pytest-testmon>=2.2` plus dependency-group `pytest>=9.0.3`, `pytest-timeout>=2.4`, `typer>=0.26.7`, `evalplus>=0.3.1`.
- `mise.toml` declares tools `python = "3.13"` and `uv = "latest"`.
- Entry point `deviate = "deviate.main:app"` is declared in `pyproject.toml`.

### Ghost Dependencies
- None observed in this scan (manifest imports match `src/deviate` tree walk; full import-to-manifest cross-check deferred to `/research`).

### Manifest Files Observed
- `pyproject.toml` (project metadata, entry point, ruff/pytest config).
- `mise.toml` (task runner: test, lint, format-check, check, setup, e2e).
- `.deviate/config.toml` (phase-model routing, agent backend selection).
- `specs/constitution.md` (version 0.12.0, three-layer architecture, testing protocols).
- `uv.lock` (pinned dependency lockfile).

### Test Runner Configuration
- pytest root `tests/` with markers `behavioral`, `spy`, `impl`, `ac` declared in `pyproject.toml`.
- Test command `pytest tests/ -v` per constitution; `mise.toml` task `test` runs `uv run pytest --testmon-noselect tests/ -v`.
- Lint `ruff check .` via `mise run lint`; quality gate `mise run check` runs `lint` + `format-check`.
- E2E `bats tests/e2e/` via `mise run test-e2e`. Type check task prints `No type checker configured`.

### Manifest-Constitution Divergence
- None observed. `pyproject.toml` pytest/ruff settings match constitution `Testing Protocols`; `mise.toml` tasks match constitution `Tooling` entries.

## Constitution Quotes
- **Architectural Principles**: "Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)."
- **Tech Stack Standards**: "Python 3.13" / "Framework: Typer (CLI entry points) with Rich for terminal I/O" / "Package manager: `uv`" / "Test runner: `pytest`" / "Linter: `ruff` (lint + format)".
- **Testing Protocols**: "Test framework: pytest" / "Test root: `tests/`" / "Test command: `pytest tests/ -v`" / "Lint command: `ruff check .`" / "E2E command: `bats tests/e2e/`".
- **Definition of Done**: "Tests passing (pytest with clean exit code 0)" / "Lint passing (ruff check with no violations)" / "Judge phase passed (git diff validated against the authoritative plan acceptance contract)".

## Architectural Baselines
- **Existing Architectural Patterns**
  - CLI entry `src/deviate/main.py` loads a Typer app; layer routing lives in `src/deviate/cli/` (`macro.py`, `meso.py`, `micro.py`) with prompt templates under `src/deviate/prompts/commands/`.
  - Micro-layer TDD loop phases RED → GREEN → JUDGE → REFACTOR plus direct EXECUTE path for refactors with existing coverage.
  - Append-only JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`) with sequential-parse canonical state.
- **Infrastructure & Operations**
  - Task runner `mise.toml`; git hooks in `.githooks/`; no containerization per constitution ("local execution on host").
  - LLM execution substrate `src/deviate/core/agent.py::AgentBackend` with backends `opencode`, `claude`, `droid`, `pi`, `omp`, `codex`; `pi` is the default.
- **Data & State Management**
  - No persistent database; session state JSON files under `.deviate/`; config TOML via `.deviate/config.toml`.
- **Quality, Safety & Observability**
  - pytest suite under `tests/` (unit, micro, meso, macro, integration, e2e dirs); ruff lint+format; run logger `src/deviate/core/run_logger.py`; judge evidence/policy modules.
- **External Integrations**
  - Agent CLI backends invoked as subprocesses (see `src/deviate/core/agent.py`); PyPI publish via `uv publish` in `mise.toml` publish task.

## Sibling Flow Inventory
| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed | n/a |
| lock vs reserve | none observed | n/a |
| Vendor call | none observed | n/a |
| Idempotency | none observed | n/a |
| Destination shape | none observed | n/a |

None observed — the repo is a CLI orchestration framework with no payment/vendor user flow.

## Ecosystem Research
- **Best Practices**
  - Strangler-fig pattern for legacy replacement (Fowler): new behavior behind an interface, old path removed after parity. Source: https://martinfowler.com/bliki/StranglerFigApplication.html
  - Characterization tests lock existing behavior before restructuring (Feathers, Working Effectively with Legacy Code).
- **Common Use Cases & Pitfalls**
  - God-file splits fail when behavior changes mix with moves in one commit; move-verbatim first, deduplicate second.
  - Oversized Python CLI modules commonly split by phase/command with a thin dispatcher _init_ re-exporting the public surface.
- **Standard Tooling**
  - Python stdlib `ast` / `tree-sitter` for node-size inventory; `ruff` for lint/format gate; `pytest-testmon` for affected-test selection.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/micro.py` | source (9440 lines) | Micro-layer TDD loop | `from __future__ import annotations` / `import importlib.resources` / `import html` / `import json` |
| `src/deviate/cli/meso.py` | source (2729 lines) | Meso plan/tasks commands | `from __future__ import annotations` / `import json` / `import logging` / `import re` |
| `src/deviate/cli/__init__.py` | source (1891 lines) | CLI dispatcher surface | `from __future__ import annotations` / `import importlib.resources` / `import re` / `import shutil` |
| `src/deviate/cli/macro.py` | source (1324 lines) | Macro explore/research/prd/shard | `from __future__ import annotations` / `import importlib.resources` / `import json` / `import shutil` / `import subprocess` |
| `src/deviate/html_templates/__init__.py` | source (1268 lines) | HTML starter scaffolds | `"""Per-phase HTML starter scaffolds for the ``deviate html`` command.` |
| `src/deviate/core/agent.py` | source (965 lines) | Agent backend substrate | `from __future__ import annotations` / `import re` / `import subprocess` / `import threading` |
| `src/deviate/cli/init.py` | source (907 lines) | Setup/init command | `from __future__ import annotations` (head verified) |
| `src/deviate/main.py` | entry point | Typer app entry | `"""CLI entry point for the ``deviate`` script.` |
| `src/deviate/state/ledger.py` | source (558 lines) | Ledger sequential-parse state | `from __future__ import annotations` / `import json` / `import re` / `import warnings` |
| `src/deviate/state/config.py` | source (505 lines) | Phase-model/backend config | `AgentConfig` selects the backend; `pi` is the default (constitution §2). |
| `src/deviate/prompts/commands/` | prompts (26 files) | Per-phase agent contracts | `deviate-red.md`, `deviate-green.md`, `deviate-judge.md`, `deviate-refactor.md`, `deviate-execute.md` present. |
| `tests/` | tests (28 dirs/files) | pytest suite | `test_micro`, `test_meso`, `test_macro`, `test_core`, `test_cli`, `test_integration`, `e2e` present. |
| `pyproject.toml` | manifest | Metadata, entry point, tool config | `name = "deviatdd"` / `deviate = "deviate.main:app"` / `requires-python = ">=3.13"` |
| `mise.toml` | task runner | Test/lint/e2e/check tasks | `run = "uv run pytest --testmon-noselect tests/ -v"` |
| `specs/constitution.md` | governance | Version 0.12.0 spec authority | `# Project Constitution` / `Version: 0.12.0` |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | High |
| Files Likely Modified | 4 key files: `src/deviate/cli/micro.py`, `src/deviate/cli/meso.py`, `src/deviate/cli/__init__.py`, `src/deviate/cli/macro.py` |
| New Modules Required | Yes |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Test suite under `tests/` plus `mise run check` gate constrain every split; ledger append-only protocol constrains state-module moves |
| Rationale | `micro.py` holds 9440 of 27783 source lines with 307 function definitions; the top 4 CLI files hold ~15k lines. |

## Related Epic Candidates

- `001` micro-layer split: `src/deviate/cli/micro.py` (9440 lines, 307 function definitions).
- `002` meso/CLI dispatcher split: `src/deviate/cli/meso.py` (2729 lines), `src/deviate/cli/__init__.py` (1891 lines), `src/deviate/cli/macro.py` (1324 lines).

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | god-files-strangler |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/god-files-strangler.md |
| NEXT_ACTION | Run `/deviate-research` (High complexity) — see `## Scope Sizing` |
