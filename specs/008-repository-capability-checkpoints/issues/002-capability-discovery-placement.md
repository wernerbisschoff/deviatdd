---
title: "Repository capability discovery and checkpoint placement"
labels: ["epic:008-repository-capability-checkpoints", "layer:meso"]
source_file: "specs/008-repository-capability-checkpoints/issues/002-capability-discovery-placement.md"
blocked_by: ["008-001"]
coordinates_with: []
issue_id: "008-002"
---

## System Topology Mapping

- **Epic Domain**: `008-repository-capability-checkpoints`
- **Local File Path**: `specs/008-repository-capability-checkpoints/issues/002-capability-discovery-placement.md`
- **Workstation Paths**:
  - `src/deviate/cli/init.py` (capability reporting at init)
  - `src/deviate/cli/meso.py` (Tasks phase: capability observations, boundary selection, closing batch)
  - `src/deviate/core/` (RepositoryCapability model, Mise declaration reader)
  - `tests/` (discovery classification, placement, degradation coverage)
- **Application Layers Touched**: discovery (Mise plus docs read), contract authoring (Tasks prompt output with declared commands), orchestration (init reporting plus planning-time revalidation hooks). Three layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I plan an issue so fresh repository capability observations shape checkpoint placement: intermediate batches sit only on assembled boundaries and every issue closes with one terminal verification batch.

## Scope Boundaries

- **Hard Inclusions**:
  - Discovery reads repository-scoped Mise declarations, treats `verify` and `verify:*` as candidates, and reports each with source provenance plus a `test`, `runtime`, or `unknown` classification.
  - Runtime claims require documented assembled observations; command names alone establish zero verification claims.
  - Tasks emits intermediate checkpoints only where completed dependencies expose assembled behavior, each mapped to at least one `AC-PLAN-NNN` scenario.
  - Every new issue ends with one terminal batch holding applicable tests plus relevant runtime commands.
  - Missing optional capability degrades to a test-only batch with `VERIFICATION_CAPABILITY_MISSING` visible; discovery errors report explicitly and never read as established absence.
  - Micro revalidates declared commands at execution time; a disappeared required command fails the checkpoint.
- **Defensive Exclusions**:
  - Checkpoint dispatch, proof validation, and queue state transitions (belongs to `008-001`).
  - Read-only agent role wording and prompt-file alignment (belongs to `008-003`).
  - User documentation and specification updates (belongs to `008-003`).
  - Optional capability-manifest consumption (explicitly out of scope for V1).
  - Persistent capability history and verification dashboards.

## Upstream Requirement Tracing

- **FR-002-CAPABILITY-DISCOVERY**: ephemeral capability observations with test/runtime/unknown classification (`AO-002`, `AO-003`).
- **FR-003-CHECKPOINT-PLACEMENT**: intermediate batches at assembled boundaries plus one terminal batch per issue (`AO-004`, `AO-005`).
- **Source**: `specs/008-repository-capability-checkpoints/prd.md` (`FR-002`, `FR-003`; `AO-002` … `AO-005`).

## User Stories Ledger

- `US-008-04`: As an operator, I declare repository `verify` tasks so the Tasks phase sees current capability observations with source provenance.
- `US-008-05`: As an issue author, I place checkpoints so intermediate batches verify assembled behavior and every issue closes with terminal proof.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-002` (`FR-002`): discovery reports every repository `verify` and `verify:*` declaration with source provenance and a `test`, `runtime`, or `unknown` classification. Result: the Tasks prompt sees current observations.
- `AO-003` (`FR-002`): a candidate without documented assembled observations never counts as runtime proof. Result: command names alone establish zero verification claims.
- `AO-004` (`FR-003`): an intermediate checkpoint exists only where its dependencies completed and assembled behavior is observable. Result: every intermediate batch maps to at least one `AC-PLAN-NNN` scenario.
- `AO-005` (`FR-003`): every new issue ends with one terminal batch holding applicable tests plus relevant runtime commands. Result: zero new issues close without a verification batch.

## Multi-Tiered Verification Targets

- **Unit Tests**: Mise declaration reading, test/runtime/unknown classification, undocumented-candidate rejection, intermediate-boundary selection, terminal-batch presence, missing-capability degradation.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/ -v -k "capability or discovery or placement"`
- **Verification Command**: `mise run check`

## Demonstration Path

```bash
# Declare a verify task in mise.toml, then confirm discovery reports it
deviate init --report-capabilities
# Plan an issue and confirm intermediate plus terminal batch placement
deviate meso run --issue-id 008-002
grep -c "Verification_Batch" specs/008-repository-capability-checkpoints/tasks.jsonl
pytest tests/ -v -k "capability or discovery or placement"
```
