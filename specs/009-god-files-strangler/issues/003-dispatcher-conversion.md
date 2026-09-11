---
title: "Dispatcher shim conversion with command snapshot"
labels: ["epic:009-god-files-strangler", "layer:micro"]
source_file: "specs/009-god-files-strangler/issues/003-dispatcher-conversion.md"
blocked_by: ["009-001", "009-002"]
coordinates_with: []
issue_id: "009-003"
---

## System Topology Mapping

- **Epic Domain**: `009-god-files-strangler`
- **Local File Path**: `specs/009-god-files-strangler/issues/003-dispatcher-conversion.md`
- **Workstation Paths**:
  - `src/deviate/cli/__init__.py` (1891 lines; source of the conversion)
  - `src/deviate/cli/micro/` (extracted consumer; must sit at `PARITY_VERIFIED`)
  - `src/deviate/cli/meso/` (extracted consumer; must sit at `PARITY_VERIFIED`)
  - `src/deviate/cli/macro.py` (still intact; routes through the dispatcher)
  - `src/deviate/main.py` (Typer app load path; primary consumer of the dispatcher)
  - `tests/` (command-list snapshot plus parity coverage)
- **Application Layers Touched**: orchestration (command routing), contract assembly (re-export map), persistence (no ledger change; ledger untouched), verification (snapshot plus gates). The dispatcher surface is the behavior under test, so the slice stays valid.

## The Problem Contract

As a DeviaTDD operator, I invoke `deviate --help` after the conversion so the Typer command list matches the pre-move snapshot exactly, while `src/deviate/cli/__init__.py` holds only re-exports under 100 lines.

## Scope Boundaries

- **Hard Inclusions**:
  - Pre-move `deviate --help` command snapshot captured before the conversion.
  - Conversion of `__init__.py` into a dispatcher surface: re-exports only, no command logic.
  - Re-export map covering micro, meso, and macro phase packages.
  - Parity gate passes: `pytest tests/ -v`, `ruff check .`, snapshot comparison.
  - One-way imports: no phase submodule imports the dispatcher shim.
- **Defensive Exclusions**:
  - Micro split (belongs to `009-001`).
  - Meso split (belongs to `009-002`).
  - Macro split (belongs to `009-004`).
  - Shared-helper consolidation (belongs to `009-005`).
  - New commands, flags, or routing behavior.
  - Moves inside `src/deviate/state/ledger.py`.

## Upstream Requirement Tracing

- **Included**: `FR-003` (dispatcher conversion), `FR-006` (parity gate for the dispatcher), `FR-007` (dispatcher one-way import rule).
- **Excluded**: `FR-001`, `FR-002` (done in `009-001`, `009-002`); `FR-004` (macro moves next); `FR-005` (characterization lock lands per extraction issue); `FR-008` (shared consolidation runs last).
- **Source**: `specs/009-god-files-strangler/prd.md` (`FR-003`, `FR-006`, `FR-007`; `AO-001`, `AO-004`, `AO-005`).

## User Stories Ledger

- `US-009-07`: As an operator, I run `deviate --help` after the conversion so I see the identical command list as before.
- `US-009-08`: As an operator, I run any layer command after the conversion so routing resolves through the dispatcher with identical behavior.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-001` (`FR-003`): old dispatcher import paths keep resolving after the conversion. Result: callers run unchanged.
- `AO-004` (`FR-003`, `FR-006`): the Typer command list stays identical. Result: the `deviate --help` snapshot matches the pre-move snapshot.
- `AO-005` (`FR-003`, `FR-007`): no phase submodule imports the dispatcher. Result: the import direction stays one-way from dispatcher to submodule.

## Multi-Tiered Verification Targets

- **Unit Tests**: re-export map resolution; dispatcher line count under 100; no-logic check.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `deviate --help`
- **Verification Command**: `pytest tests/ -v -k "cli or dispatch or help"`
- **Verification Command**: `ruff check .`
- **Verification Command**: `mise run check`
- **Verification Command**: `grep -rn "from deviate.cli import\|from . import" src/deviate/cli/micro/ src/deviate/cli/meso/ || echo ONE_WAY_OK`

## Demonstration Path

```bash
# Snapshot, convert, compare
deviate --help > /tmp/disp-pre.txt
# (perform dispatcher conversion on feat/009-god-files-strangler/dispatcher-conversion)
deviate --help > /tmp/disp-post.txt && diff /tmp/disp-pre.txt /tmp/disp-post.txt
wc -l src/deviate/cli/__init__.py
```
