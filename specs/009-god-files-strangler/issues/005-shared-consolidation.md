---
title: "Shared helper consolidation for proven duplicates"
labels: ["epic:009-god-files-strangler", "layer:micro"]
source_file: "specs/009-god-files-strangler/issues/005-shared-consolidation.md"
blocked_by: ["009-001", "009-002", "009-004"]
coordinates_with: []
issue_id: "009-005"
---

## System Topology Mapping

- **Epic Domain**: `009-god-files-strangler`
- **Local File Path**: `specs/009-god-files-strangler/issues/005-shared-consolidation.md`
- **Workstation Paths**:
  - `src/deviate/cli/shared/` (new package; holds proven duplicates only)
  - `src/deviate/cli/micro/` (extracted caller; must sit at `PARITY_VERIFIED`)
  - `src/deviate/cli/meso/` (extracted caller; must sit at `PARITY_VERIFIED`)
  - `src/deviate/cli/macro/` (extracted caller; must sit at `PARITY_VERIFIED`)
  - `tests/` (parity coverage for consolidated imports)
- **Application Layers Touched**: orchestration (phase callers), contract assembly (shared import updates), verification (parity plus gates). The duplicate helper moved across callers is the behavior under test, so the slice stays valid.

## The Problem Contract

As a maintainer, I import a proven duplicate helper from `src/deviate/cli/shared/` so at least two phase packages share one copy, while every caller keeps identical behavior and unproven helpers stay duplicated.

## Scope Boundaries

- **Hard Inclusions**:
  - Evidence that the duplicate exists in at least two phase packages.
  - Move of proven duplicates into `src/deviate/cli/shared/` with updated caller imports.
  - Parity gate passes: `pytest tests/ -v`, `ruff check .`, `mise run check`.
  - One duplication pass first; consolidation ships as a follow-up commit.
- **Defensive Exclusions**:
  - Phase extractions (belong to `009-001`, `009-002`, `009-004`).
  - Dispatcher conversion (belongs to `009-003`).
  - Consolidation of unproven or single-owner helpers.
  - Shared-service extraction first (Rejected Option C).
  - Moves inside `src/deviate/state/ledger.py`.

## Upstream Requirement Tracing

- **Included**: `FR-008` (shared consolidation), `FR-007` (callers sit at `PARITY_VERIFIED`; imports stay canonical).
- **Excluded**: `FR-001` … `FR-004` (done in `009-001` … `009-004`); `FR-005`, `FR-006` (locks and gates land per extraction issue).
- **Source**: `specs/009-god-files-strangler/prd.md` (`FR-008`, `FR-007`; `AO-007`, `AO-008`).

## User Stories Ledger

- `US-009-12`: As a maintainer, I update a proven duplicate helper once so all phase callers receive the same change.
- `US-009-13`: As an operator, I run phase commands after consolidation so behavior matches the pre-consolidation run.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-007` (`FR-007`): direct submodule imports stay canonical after consolidation. Result: zero caller resolves through a removed shim.
- `AO-008` (`FR-008`): `cli/shared/` holds only proven duplicates. Result: unproven helpers stay duplicated in their phase packages.

## Multi-Tiered Verification Targets

- **Unit Tests**: duplicate-evidence check; shared import resolution per caller.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/ -v -k "shared or cli"`
- **Verification Command**: `ruff check .`
- **Verification Command**: `mise run check`
- **Verification Command**: `ls src/deviate/cli/shared/`

## Demonstration Path

```bash
# Show the duplicate in two callers, consolidate, verify
grep -rn "<helper-name>" src/deviate/cli/micro/ src/deviate/cli/meso/ src/deviate/cli/macro/
# (move proven duplicate into src/deviate/cli/shared/ on feat/009-god-files-strangler/shared-consolidation)
pytest tests/ -v -k "shared or cli" && mise run check
```
