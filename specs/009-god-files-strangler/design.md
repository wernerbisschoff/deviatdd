## Recommended Architecture

**Summary**: The repo splits four god-files through a package-per-phase strangler. Each god-file keeps its import path as a thin dispatcher. New submodules hold the moved code. The dispatcher re-exports the public surface. Callers keep working during the split. The old code leaves only after parity checks pass.

`src/deviate/main.py` keeps loading the Typer app. `src/deviate/cli/` keeps layer routing in `macro.py`, `meso.py`, and `micro.py`. Prompt templates stay under `src/deviate/prompts/commands/`. No behavior changes mix with moves. Each move ships verbatim first, then deduplicates.

**Module_Surface**: Add new subpackages: `src/deviate/cli/micro/` (RED, GREEN, JUDGE, REFACTOR, EXECUTE units), `src/deviate/cli/meso/` (plan, tasks, review units), `src/deviate/cli/macro/` (explore, research, prd, shard units), `src/deviate/cli/shared/` (dispatcher helpers shared by the three layers). Modify four files only: `src/deviate/cli/micro.py`, `src/deviate/cli/meso.py`, `src/deviate/cli/__init__.py`, `src/deviate/cli/macro.py` — each becomes a re-export shim under 100 lines. Touch `src/deviate/html_templates/__init__.py` (1268 lines) and `src/deviate/core/agent.py` (965 lines) only if the inventory proves a shared import; default is no touch. Integration seams: Typer command registration in `src/deviate/main.py`, `AgentBackend` subprocess calls in `src/deviate/core/agent.py`, ledger sequential-parse in `src/deviate/state/ledger.py`, test suite under `tests/`, quality gate `mise run check`.

**Rationale**: The floor matches sibling conventions and constitution gates. The constitution mandates three layers with strict phase gates and no skipped layer. A package-per-phase split preserves those gates as module boundaries. The explore brief records 9440 lines in `micro.py` with 307 functions and 15k lines across the top four CLI files. A phase/command split follows the ecosystem row that directs oversized CLI modules to split by phase/command with a thin dispatcher _init_ re-export. The append-only ledger protocol constrains state-module moves, so `ledger.py` (558 lines) stays untouched. The `mise run check` gate constrains every split, so each extraction keeps `pytest tests/ -v` and `ruff check .` green.

## Options Matrix

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Option A: package-per-phase strangler with thin dispatcher re-exports | M | H | Aligned | Easy | Local | Recommended |
| Option B: flat size-based chunking (arbitrary ~500-line files) | M | M | Tension | Easy | Module | Rejected |
| Option C: shared-service extraction first (`core/` helpers before phase split) | H | M | Aligned | Hard | System | Rejected |
| Option D: big-bang rewrite into new package layout | H | L | Violation | Hard | System | Rejected |

## Rejected Options

- Option B: flat size-based chunking breaks the three-layer gate boundary ("Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)") and hurt review; size is not a boundary.
- Option C: shared-service extraction first widens blast radius to `src/deviate/core/agent.py::AgentBackend` and `src/deviate/state/ledger.py` before characterization tests lock behavior; it risks behavior edits mixed with moves, which the ecosystem row forbids ("move-verbatim first, deduplicate second").
- Option D: big-bang rewrite skips phase gates ("The three layers have strict phase gates — no layer may be skipped") and breaks Git Isolation ("Every task loop executes on a clean git branch or worktree"); it also voids the characterization-test lock from Feathers cited in explore.

## Design Trade-Offs

| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| Thin dispatcher shims keep old import paths | Stable imports vs. extra indirection layer | Stability wins; `src/deviate/main.py` loads `deviate = "deviate.main:app"` per `pyproject.toml`, so the entry path must not break (explore `## File Registry`, `pyproject.toml` row). |
| Move-verbatim first, deduplicate second | Slower cleanup vs. safe review | Safety wins; ecosystem pitfall row warns splits fail when behavior changes mix with moves (explore `## Ecosystem Research`). |
| Characterization tests before each extraction | Upfront test cost vs. silent drift | Tests win; Feathers characterization-test row plus constitution coverage target (>= 80%) require locked behavior (explore `## Ecosystem Research`; constitution §3). |
| Per-phase packages, not per-size chunks | More design work vs. meaningful boundaries | Boundaries win; constitution three-layer gates map to packages; size chunks map to nothing (constitution §1). |
| Leave `ledger.py`, `config.py`, `agent.py` untouched by default | Missed sharing vs. narrow blast radius | Narrow wins; ledger append-only protocol and `AgentBackend` contract constrain moves (explore `## Scope Sizing`, Upstream row; constitution §1). |

## Contrarian Viewpoints

- Viewpoint: the dispatcher shim layer becomes permanent cruft and hides the new layout. Keep shims only until all callers migrate, then delete each shim in its own commit with `mise run check` green. Source: `src/deviate/cli/__init__.py` (1891 lines) dispatcher row in explore `## File Registry`.
- Viewpoint: characterization tests on 9440-line `micro.py` cost more than the split saves. Scope the lock to the extracted unit's public functions only, not the whole file; `pytest-testmon` selects affected tests per run. Source: `mise.toml` row (`uv run pytest --testmon-noselect tests/ -v`) in explore `## File Registry`.

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation | Scope Status | Owner | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | Circular imports between new submodules and dispatcher shims | M | H | Enforce one-way imports (submodules never import the shim); check with `ruff check .` plus an import-lint test in `tests/test_cli/` | Required | cli/shared | `src/deviate/cli/__init__.py` (1891 lines) — explore `## File Registry` |
| RSK-002 | Behavior drift during verbatim moves | M | H | Lock each unit with characterization tests before the move; run `pytest tests/ -v` before and after; diff behavior, not style | Required | micro/meso/macro | Ecosystem row "Characterization tests lock existing behavior" — explore `## Ecosystem Research` |
| RSK-003 | Ledger parse break from state-module moves | L | H | Forbid moves in `src/deviate/state/ledger.py` (558 lines) during this epic; sequential-parse stays canonical | Required | state/ledger | Constitution "Canonical state is derived by sequential ledger parsing" (§1) |
| RSK-004 | Test-suite time exceeds gate budget during large moves | M | M | Use `pytest-testmon` affected-test selection per extraction; full suite runs at epic boundary via `mise run check` | Recommended | tests/ | `mise.toml` row in explore `## File Registry` |
| RSK-005 | Public Typer surface changes break `deviate` entry point | L | H | Assert command list parity (`deviate --help` snapshot test) before shim deletion | Required | main.py | `deviate = "deviate.main:app"` — explore `## Discovery Audit Results` |
| RSK-006 | Duplicate helpers diverge after split (micro vs meso copies) | M | M | Allow one duplication pass; consolidate only proven duplicates into `cli/shared/` in a follow-up task | Deferred | cli/shared | Ecosystem row "deduplicate second" — explore `## Ecosystem Research` |

## Deferred

- Shared-helper consolidation into `cli/shared/` beyond proven duplicates.
- `html_templates/__init__.py` (1268 lines) split; include only if a CLI extraction proves a hard import.
- `core/agent.py` (965 lines) backend split; out of scope for the CLI-layer epic.
- Automated import-graph metrics (`ast` / `tree-sitter` inventory dashboards); use one-shot scripts, not checked-in tooling.
- Alert or metric hooks on module size; no owner requests them.

## Constitutional Alignment Audit

| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| "Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)." | Package-per-phase split mirrors the three layers | Aligned | explore `## Architectural Baselines`, CLI routing row |
| "The three layers have strict phase gates — no layer may be skipped." | Each extraction preserves its gate as a package boundary | Aligned | No gate logic moves across layers |
| "All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only." | `ledger.py` excluded from moves by default | Aligned | explore `## Scope Sizing`, Upstream row |
| "GREEN phase writes only to `src/` and permitted implementation paths." | Moves stay inside `src/deviate/cli/`; tests stay in `tests/` | Aligned | Floor file list; no test edits with moves |
| "Every task loop executes on a clean git branch or worktree." | One extraction per branch (`feat/<epic-slug>/<issue-slug>`) | Aligned | Constitution §4 Branch Strategy |
| "Test framework: pytest" / "Test command: `pytest tests/ -v`" / "Lint command: `ruff check .`" | Characterization tests + `mise run check` gate each move | Aligned | explore `## Discovery Audit Results`, Test Runner Configuration |
| "Coverage target: >= 80%" | No extraction lowers coverage; parity tests hold the line | Aligned | Constitution §3 Coverage |
| "Two remaining mandatory gates (Design Approval after research, Final Merge Audit after micro)" | This design goes through Gate 1; each extraction lands only after Gate 3 review | Aligned | No gate bypassed |

## Pending HITL Decisions

<!-- HITL_DECISIONS -->

| Decision ID | Question | Context | Impact | Recommended Resolution | Status |
|---|---|---|---|---|---|

## Source Registry

| ID | Type | Source / Path | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-01 | Explore_MD | specs/009-god-files-strangler/explore.md | File registry, baselines, ecosystem rows feed the floor |
| SRC-02 | Constitution | specs/constitution.md | Three-layer gates, ledger protocol, test commands bind the design |
| SRC-03 | Codebase_File | src/deviate/cli/micro.py | 9440-line primary god-file; first extraction target |
| SRC-04 | Codebase_File | src/deviate/cli/meso.py | 2729-line second extraction target |
| SRC-05 | Codebase_File | src/deviate/cli/__init__.py | 1891-line dispatcher surface; shim owner |
| SRC-06 | Codebase_File | src/deviate/cli/macro.py | 1324-line macro extraction target |
| SRC-07 | Codebase_File | src/deviate/main.py | Typer entry point; parity seam |
| SRC-08 | Codebase_File | src/deviate/state/ledger.py | Append-only parse; excluded from moves |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 009-god-files-strangler |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the prd skill |
