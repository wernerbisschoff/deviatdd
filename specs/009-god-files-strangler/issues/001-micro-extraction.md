---
title: "Micro phase package extraction with parity gate"
labels: ["epic:009-god-files-strangler", "layer:micro"]
source_file: "specs/009-god-files-strangler/issues/001-micro-extraction.md"
blocked_by: []
coordinates_with: []
issue_id: "009-001"
---

## System Topology Mapping

- **Epic Domain**: `009-god-files-strangler`
- **Local File Path**: `specs/009-god-files-strangler/issues/001-micro-extraction.md`
- **Workstation Paths**:
  - `src/deviate/cli/micro.py` (9440 lines, 307 functions; source of the move)
  - `src/deviate/cli/micro/` (new phase package; verbatim move target)
  - `src/deviate/main.py` (Typer app load path; consumer of the surface)
  - `src/deviate/core/agent.py::AgentBackend` (invocation substrate; stays untouched)
  - `src/deviate/state/ledger.py` (append-only writes; stays untouched)
  - `tests/` (characterization lock plus parity coverage)
- **Application Layers Touched**: orchestration (micro dispatch), contract assembly (phase routing), persistence (ledger appends), verification (tests plus gates). Four layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I run any `deviate micro` command after the split so it routes through `src/deviate/cli/micro/` with identical behavior, while the old `src/deviate/cli/micro.py` path keeps resolving through a shim under 100 lines.

## Scope Boundaries

- **Hard Inclusions**:
  - Characterization tests for micro public functions land under `tests/` before the move.
  - Verbatim move of micro command logic into `src/deviate/cli/micro/` with no behavior edits.
  - Old `micro.py` becomes a re-export shim under 100 lines holding no logic.
  - Parity gate passes: `pytest tests/ -v`, `ruff check .`, `deviate --help` snapshot match.
  - Shim deletion in its own commit after zero shim imports remain; parity re-passes.
  - One-way imports: no submodule imports the shim.
- **Defensive Exclusions**:
  - Meso split (belongs to `009-002`).
  - Dispatcher conversion (belongs to `009-003`).
  - Macro split (belongs to `009-004`).
  - Shared-helper consolidation beyond proven duplicates (belongs to `009-005`).
  - Behavior edits, refactors, or deduplication in the move commit.
  - Moves inside `src/deviate/state/ledger.py`.

## Upstream Requirement Tracing

- **Included**: `FR-001` (micro extraction), `FR-005` (characterization lock for micro), `FR-006` (parity gate for micro), `FR-007` (micro shim deletion).
- **Excluded**: `FR-002`, `FR-003`, `FR-004` (other units move in later issues); `FR-008` (shared consolidation runs last).
- **Source**: `specs/009-god-files-strangler/prd.md` (`FR-001`, `FR-005`, `FR-006`, `FR-007`; `AO-001`, `AO-002`, `AO-003`, `AO-005`, `AO-006`, `AO-007`).

## User Stories Ledger

- `US-009-01`: As an operator, I invoke `deviate micro` commands after the split so each command runs with behavior identical to before the move.
- `US-009-02`: As an operator, I import the old `micro.py` path during migration so existing callers keep working through the shim.
- `US-009-03`: As a maintainer, I read the micro shim after deletion so all imports resolve directly to `src/deviate/cli/micro/` submodules.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-001` (`FR-001`): old micro import paths keep resolving after the move. Result: callers run unchanged through the shim.
- `AO-002` (`FR-001`, `FR-006`): behavior after the move matches behavior before the move. Result: characterization tests pass unchanged.
- `AO-003` (`FR-001`, `FR-006`): `ruff check .` reports zero violations and `mise run check` exits zero. Result: the quality gate stays green.
- `AO-005` (`FR-007`): no micro submodule imports its shim. Result: the import direction stays one-way from shim to submodule.
- `AO-006` (`FR-005`): micro characterization tests exist under `tests/` before the move. Result: no behavior edit shares a commit with the move.
- `AO-007` (`FR-007`): the micro shim deletes only after zero shim imports remain. Result: direct submodule imports become canonical.

## Multi-Tiered Verification Targets

- **Unit Tests**: micro characterization lock under `tests/`; shim re-export resolution; one-way import check.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/ -v -k micro`
- **Verification Command**: `ruff check .`
- **Verification Command**: `deviate --help`
- **Verification Command**: `mise run check`
- **Verification Command**: `grep -rn "cli.micro import\|from deviate.cli.micro import" src/ | grep -v "cli/micro/" || echo NO_SHIM_IMPORTS`

## Demonstration Path

```bash
# Snapshot the command list, run the move, compare
deviate --help > /tmp/micro-pre.txt
# (perform verbatim move plus shim on feat/009-god-files-strangler/micro-extraction)
pytest tests/ -v -k micro
ruff check .
deviate --help > /tmp/micro-post.txt && diff /tmp/micro-pre.txt /tmp/micro-post.txt
```
