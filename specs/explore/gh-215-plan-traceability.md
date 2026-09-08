## Problem Definition
**Statement**: `deviate plan pre` returns READY for issues that lack the traceability fields the PLAN prompt requires. Source: gh issue 215, "Validate issue traceability before PLAN starts and support legacy issue repair" (https://github.com/wernerbisschoff/deviatdd/issues/215, state OPEN, deviate 2.28.0).
**Scope**: Meso `plan pre` validation path, PLAN prompt traceability contract, issue-file generation templates (shard, adhoc), legacy issue repair path.
**Exclusions**: Micro RED/GREEN/JUDGE behavior changes, product-pack artifacts, release scaffolding.

## Discovery Audit Results
### Verified Dependencies
- The manifest declares `typer>=0.12`, `rich>=13.0`, `pydantic>=2.0`, `pyyaml>=6.0.3`. The CLI entry point is `deviate = "deviate.main:app"`.
- The task runner is `mise` via `mise.toml`. Test task runs `uv run pytest --testmon-noselect tests/ -v`. Lint task runs `uv run ruff check`.
### Ghost Dependencies
- None observed. No code import lacks a manifest entry in the scanned surface.
### Manifest Files Observed
- `pyproject.toml` declares project metadata, dependencies, and the `deviate` entry point.
- `mise.toml` declares test, lint, format, and e2e tasks.
- `specs/constitution.md` carries version 0.11.0 governance.
### Test Runner Configuration
- The test root is `tests/`. The runner is `pytest`. E2E runs via `bats tests/e2e/`.
### Manifest-Constitution Divergence
- None observed. The manifest declares Python 3.13, Typer, Rich, pytest, ruff, bats. The constitution requires the same stack.

## Constitution Quotes
- **Architectural Principles**: "Macro PRD/shard/adhoc artifacts carry User Stories plus ATDD acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract."
- **Tech Stack Standards**: "Target: CLI application (`deviate`) - Framework: Typer (CLI entry points) with Rich for terminal I/O"
- **Testing Protocols**: "Test framework: pytest - Test root: `tests/` - Test extension: `.py` - Test command: `pytest tests/ -v`"
- **Definition of Done**: "Judge phase passed (git diff validated against the authoritative plan acceptance contract)"

## Architectural Baselines
- **Existing Architectural Patterns**: Typer CLI entry in `src/deviate/main.py` dispatches to layer modules. Meso commands live in `src/deviate/cli/meso.py`. Prompt templates live in `src/deviate/prompts/auto/` and `src/deviate/prompts/commands/`.
- **Infrastructure & Operations**: Git phase commits via pre/post scripts. Task runner is `mise.toml`. No containerization required.
- **Data & State Management**: Append-only JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`). Session state holds JSON files under `.deviate/`. Config holds TOML via `.deviate/config.toml`.
- **Quality, Safety & Observability**: pytest suite under `tests/` with `tests/test_meso/` and `tests/test_cli/test_meso_contracts.py` for meso contracts. Lint via ruff.
- **External Integrations**: GitHub issue 215 is the source request. No new third-party client exists for this scope.

## Sibling Flow Inventory
Nearest sibling: meso `plan pre` issue resolution with branch fallback (`deviate.cli._common.resolve_issue_id_from_branch`).

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed | src/deviate/cli/meso.py |
| Lock vs reserve | none observed | src/deviate/cli/meso.py |
| Vendor call | none observed | src/deviate/cli/meso.py |
| Idempotency | none observed | src/deviate/cli/meso.py |
| Destination shape | typed JSON contract with `issue_id`, `status`, `phase` | src/deviate/cli/meso.py |

Traceability contract facts (no recommendation): PLAN requires `**Upstream Traceability**: US-NNN-NN, FR-NNN-ID, AC-NNN-ID-NN` drawn from the issue (`src/deviate/prompts/auto/plan.md`). Shard and adhoc issues must carry `## User Stories Ledger` plus `## Acceptance Outline` (`src/deviate/prompts/auto/shard.md`, `src/deviate/prompts/commands/deviate-adhoc.md`).

## Ecosystem Research
- **Best Practices**: Validate inputs at the earliest gate. Fail fast with a named diagnostic lists the missing field and the repair step.
- **Common Use Cases & Pitfalls**: Late validation shifts cost to the agent pass. Silent READY on invalid input invites fabricated identifiers to satisfy a syntax check.
- **Standard Tooling**: Pydantic models plus pre-flight contract checks in Typer commands. pytest pins each gate with positive and negative cases.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| pyproject.toml | manifest | Declares dependencies and entry point | `name = "deviatdd"` / `version = "2.28.0"` / `requires-python = ">=3.13"` / `typer>=0.12` / `deviate = "deviate.main:app"` |
| mise.toml | task runner | Declares test and lint tasks | `run = "uv run pytest --testmon-noselect tests/ -v"` / `run = "uv run ruff check"` |
| specs/constitution.md | governance | Declares layers, gates, and done criteria | `Version: 0.11.0` / `Macro PRD/shard/adhoc artifacts carry User Stories plus ATDD acceptance outlines` |
| src/deviate/cli/meso.py | source | Implements plan/tasks pre/post contracts | `All meso resolution sites (plan pre/post, tasks pre/post) now receive the same branch-derived fallback` (CHANGELOG record of this file) |
| src/deviate/prompts/auto/plan.md | prompt | Declares PLAN traceability contract | `**Upstream Traceability** — **Upstream Traceability**: US-NNN-NN, FR-NNN-ID, AC-NNN-ID-NN. At minimum one US-, one FR-, and one AC- token` |
| src/deviate/prompts/auto/shard.md | prompt | Requires stories plus ATDD on shard issues | `Every shard issue MUST encode the user-visible job as ## User Stories Ledger (US-NNN-NN) plus ATDD` |
| src/deviate/prompts/commands/deviate-adhoc.md | prompt | Requires stories plus ATDD on adhoc issues | `The file must contain ## User Stories Ledger, ## Acceptance Outline, ## Edge Cases and Boundaries` |
| tests/test_cli/test_meso_contracts.py | test | Pins meso contract resolution | `test_tasks_pre_resolves_issue_from_branch` |
| specs/005-acceptance-gates/issues/002-task-acceptance-traceability.md | issue | Example issue with ledger and tracing sections | `## Upstream Requirement Tracing` / `## User Stories Ledger` / `US-005-03 (parent FR-005-02)` |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 4 — src/deviate/cli/meso.py, src/deviate/prompts/auto/plan.md, tests/test_meso/*, CHANGELOG.md |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | PLAN prompt contract plus shard/adhoc issue templates must agree on required identifiers |
| Rationale | The change adds a validation gate plus repair guidance. It touches one command path and its contract tests. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | gh-215-plan-traceability |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/gh-215-plan-traceability.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) or `/deviate-research` (High complexity) — see `## Scope Sizing` |
