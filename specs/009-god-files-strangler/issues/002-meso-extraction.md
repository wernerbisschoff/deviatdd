---
title: "Meso phase package extraction with parity gate"
labels: ["epic:009-god-files-strangler", "layer:micro"]
source_file: "specs/009-god-files-strangler/issues/002-meso-extraction.md"
blocked_by: ["009-001"]
coordinates_with: []
issue_id: "009-002"
---

## System Topology Mapping

- **Epic Domain**: `009-god-files-strangler`
- **Local File Path**: `specs/009-god-files-strangler/issues/002-meso-extraction.md`
- **Workstation Paths**:
  - `src/deviate/cli/meso.py` (2729 lines; source of the move)
  - `src/deviate/cli/meso/` (new phase package; verbatim move target)
  - `src/deviate/cli/micro/` (upstream extraction; must sit at `PARITY_VERIFIED`)
  - `src/deviate/main.py` (Typer app load path; consumer of the surface)
  - `src/deviate/state/ledger.py` (append-only writes; stays untouched)
  - `tests/` (characterization lock plus parity coverage)
- **Application Layers Touched**: orchestration (meso dispatch: plan, tasks), contract assembly (phase routing), persistence (ledger appends), verification (tests plus gates). Four layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I run any `deviate plan` or `deviate tasks` command after the split so it routes through `src/deviate/cli/meso/` with identical behavior, while the old `src/deviate/cli/meso.py` path keeps resolving through a shim under 100 lines.

## Scope Boundaries

- **Hard Inclusions**:
  - Characterization tests for meso public functions land under `tests/` before the move.
  - Verbatim move of meso command logic into `src/deviate/cli/meso/` with no behavior edits.
  - Old `meso.py` becomes a re-export shim under 100 lines holding no logic.
  - Parity gate passes: `pytest tests/ -v`, `ruff check .`, `deviate --help` snapshot match.
  - Shim deletion in its own commit after zero shim imports remain; parity re-passes.
  - One-way imports: no submodule imports the shim.
- **Defensive Exclusions**:
  - Micro split (belongs to `009-001`).
  - Dispatcher conversion (belongs to `009-003`).
  - Macro split (belongs to `009-004`).
  - Shared-helper consolidation beyond proven duplicates (belongs to `009-005`).
  - Behavior edits, refactors, or deduplication in the move commit.
  - Moves inside `src/deviate/state/ledger.py`.

## Upstream Requirement Tracing

- **Included**: `FR-002` (meso extraction), `FR-005` (characterization lock for meso), `FR-006` (parity gate for meso), `FR-007` (meso shim deletion).
- **Excluded**: `FR-001` (done in `009-001`); `FR-003`, `FR-004` (later issues); `FR-008` (shared consolidation runs last).
- **Source**: `specs/009-god-files-strangler/prd.md` (`FR-002`, `FR-005`, `FR-006`, `FR-007`; `AO-001`, `AO-002`, `AO-003`, `AO-005`, `AO-006`, `AO-007`).

## User Stories Ledger

- `US-009-04`: As an operator, I invoke `deviate plan` and `deviate tasks` commands after the split so each command runs with behavior identical to before the move.
- `US-009-05`: As an operator, I import the old `meso.py` path during migration so existing callers keep working through the shim.
- `US-009-06`: As a maintainer, I read the meso shim after deletion so all imports resolve directly to `src/deviate/cli/meso/` submodules.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-001` (`FR-002`): old meso import paths keep resolving after the move. Result: callers run unchanged through the shim.
- `AO-002` (`FR-002`, `FR-006`): behavior after the move matches behavior before the move. Result: characterization tests pass unchanged.
- `AO-003` (`FR-002`, `FR-006`): `ruff check .` reports zero violations and `mise run check` exits zero. Result: the quality gate stays green.
- `AO-005` (`FR-007`): no meso submodule imports its shim. Result: the import direction stays one-way from shim to submodule.
- `AO-006` (`FR-005`): meso characterization tests exist under `tests/` before the move. Result: no behavior edit shares a commit with the move.
- `AO-007` (`FR-007`): the meso shim deletes only after zero shim imports remain. Result: direct submodule imports become canonical.

## Multi-Tiered Verification Targets

- **Unit Tests**: meso characterization lock under `tests/`; shim re-export resolution; one-way import check.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/ -v -k meso`
- **Verification Command**: `ruff check .`
- **Verification Command**: `deviate --help`
- **Verification Command**: `mise run check`
- **Verification Command**: `grep -rn "from deviate.cli.meso import" src/ | grep -v "cli/meso/" || echo NO_SHIM_IMPORTS`

## Demonstration Path

```bash
# Snapshot the command list, run the move, compare
deviate --help > /tmp/meso-pre.txt
# (perform verbatim move plus shim on feat/009-god-files-strangler/meso-extraction)
pytest tests/ -v -k meso
ruff check .
deviate --help > /tmp/meso-post.txt && diff /tmp/meso-pre.txt /tmp/meso-post.txt
```
