---
title: "Macro phase package extraction with parity gate"
labels: ["epic:009-god-files-strangler", "layer:micro"]
source_file: "specs/009-god-files-strangler/issues/004-macro-extraction.md"
blocked_by: ["009-003"]
coordinates_with: []
issue_id: "009-004"
---

## System Topology Mapping

- **Epic Domain**: `009-god-files-strangler`
- **Local File Path**: `specs/009-god-files-strangler/issues/004-macro-extraction.md`
- **Workstation Paths**:
  - `src/deviate/cli/macro.py` (1324 lines; source of the move)
  - `src/deviate/cli/macro/` (new phase package; verbatim move target)
  - `src/deviate/cli/__init__.py` (dispatcher surface; must sit at `PARITY_VERIFIED`)
  - `src/deviate/main.py` (Typer app load path; consumer of the surface)
  - `src/deviate/state/ledger.py` (append-only writes; stays untouched)
  - `tests/` (characterization lock plus parity coverage)
- **Application Layers Touched**: orchestration (macro dispatch: explore, research, prd, shard), contract assembly (phase routing), persistence (ledger appends), verification (tests plus gates). Four layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I run any `deviate explore`, `research`, `prd`, or `shard` command after the split so it routes through `src/deviate/cli/macro/` with identical behavior, while the old `src/deviate/cli/macro.py` path keeps resolving through a shim under 100 lines.

## Scope Boundaries

- **Hard Inclusions**:
  - Characterization tests for macro public functions land under `tests/` before the move.
  - Verbatim move of macro command logic into `src/deviate/cli/macro/` with no behavior edits.
  - Old `macro.py` becomes a re-export shim under 100 lines holding no logic.
  - Parity gate passes: `pytest tests/ -v`, `ruff check .`, `deviate --help` snapshot match.
  - Shim deletion in its own commit after zero shim imports remain; parity re-passes.
  - One-way imports: no submodule imports the shim.
- **Defensive Exclusions**:
  - Micro split (belongs to `009-001`).
  - Meso split (belongs to `009-002`).
  - Dispatcher conversion (belongs to `009-003`).
  - Shared-helper consolidation beyond proven duplicates (belongs to `009-005`).
  - Behavior edits, refactors, or deduplication in the move commit.
  - Moves inside `src/deviate/state/ledger.py`.

## Upstream Requirement Tracing

- **Included**: `FR-004` (macro extraction), `FR-005` (characterization lock for macro), `FR-006` (parity gate for macro), `FR-007` (macro shim deletion).
- **Excluded**: `FR-001`, `FR-002`, `FR-003` (done in `009-001` … `009-003`); `FR-008` (shared consolidation runs last).
- **Source**: `specs/009-god-files-strangler/prd.md` (`FR-004`, `FR-005`, `FR-006`, `FR-007`; `AO-001`, `AO-002`, `AO-003`, `AO-005`, `AO-006`, `AO-007`).

## User Stories Ledger

- `US-009-09`: As an operator, I invoke `deviate explore`, `research`, `prd`, and `shard` commands after the split so each command runs with behavior identical to before the move.
- `US-009-10`: As an operator, I import the old `macro.py` path during migration so existing callers keep working through the shim.
- `US-009-11`: As a maintainer, I read the macro shim after deletion so all imports resolve directly to `src/deviate/cli/macro/` submodules.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-001` (`FR-004`): old macro import paths keep resolving after the move. Result: callers run unchanged through the shim.
- `AO-002` (`FR-004`, `FR-006`): behavior after the move matches behavior before the move. Result: characterization tests pass unchanged.
- `AO-003` (`FR-004`, `FR-006`): `ruff check .` reports zero violations and `mise run check` exits zero. Result: the quality gate stays green.
- `AO-005` (`FR-007`): no macro submodule imports its shim. Result: the import direction stays one-way from shim to submodule.
- `AO-006` (`FR-005`): macro characterization tests exist under `tests/` before the move. Result: no behavior edit shares a commit with the move.
- `AO-007` (`FR-007`): the macro shim deletes only after zero shim imports remain. Result: direct submodule imports become canonical.

## Multi-Tiered Verification Targets

- **Unit Tests**: macro characterization lock under `tests/`; shim re-export resolution; one-way import check.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/ -v -k macro`
- **Verification Command**: `ruff check .`
- **Verification Command**: `deviate --help`
- **Verification Command**: `mise run check`
- **Verification Command**: `grep -rn "from deviate.cli.macro import" src/ | grep -v "cli/macro/" || echo NO_SHIM_IMPORTS`

## Demonstration Path

```bash
# Snapshot the command list, run the move, compare
deviate --help > /tmp/macro-pre.txt
# (perform verbatim move plus shim on feat/009-god-files-strangler/macro-extraction)
pytest tests/ -v -k macro
ruff check .
deviate --help > /tmp/macro-post.txt && diff /tmp/macro-pre.txt /tmp/macro-post.txt
```
