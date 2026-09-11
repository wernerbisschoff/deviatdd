---
title: "Read-only checkpoint role, sibling compatibility, prompts, and docs"
labels: ["epic:008-repository-capability-checkpoints", "layer:micro"]
source_file: "specs/008-repository-capability-checkpoints/issues/003-readonly-role-prompts-docs.md"
blocked_by: ["008-001", "008-002"]
coordinates_with: []
issue_id: "008-003"
---

## System Topology Mapping

- **Epic Domain**: `008-repository-capability-checkpoints`
- **Local File Path**: `specs/008-repository-capability-checkpoints/issues/003-readonly-role-prompts-docs.md`
- **Workstation Paths**:
  - `src/deviate/prompts/auto/checkpoint.md` (new verification-only prompt)
  - `src/deviate/prompts/` (`tasks.md`, `deviate-e2e.md`, `deviate-init.md` alignment plus `_LAYER_MAP` checkpoint routing)
  - `src/deviate/cli/_safe_commands.py` (declared-command validation at execution time)
  - `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md` (both verification levels documented)
  - `tests/` (read-only role, sibling regression, prompt contract coverage)
- **Application Layers Touched**: prompt authoring (role plus label alignment), command validation (safe-command boundary), orchestration (unchanged sibling dispatch), documentation (user plus specification updates). Four layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I run checkpoints and normal tasks side by side so verification stays read-only, existing TDD and immediate behavior stays unchanged, prompts use distinct instructions, and docs explain both verification levels.

## Scope Boundaries

- **Hard Inclusions**:
  - Checkpoint prompt directs verification-only work: execute declared commands, report evidence, change no implementation, tests, configuration, or workflow state; declared commands validate through `src/deviate/cli/_safe_commands.py`.
  - Existing TDD cycles, ordinary `IMMEDIATE` tasks, init merges, and GREEN/JUDGE scope verdicts behave exactly as before with sibling regression suites passing unchanged.
  - Tasks prompt distinguishes atomic tests from assembled verification and preserves the closing batch; E2E prompt drops the conflicting test-authoring label; init separates minimum testing from optional repository capabilities; `_LAYER_MAP` routes `checkpoint` to Micro.
  - Ambiguous historical batches halt for review instead of silent reclassification.
  - `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` explain atomic versus assembled verification, discovery ownership, and migration fallbacks in the implementation commit.
- **Defensive Exclusions**:
  - Checkpoint dispatch mechanics and queue state transitions (belongs to `008-001`).
  - Capability discovery and placement rules (belongs to `008-002`).
  - Checkpoint-specific sandboxing and write monitoring (explicitly out of scope for V1).
  - Persistent capability history and verification dashboards.
  - Removal of every legacy doctor fallback.

## Upstream Requirement Tracing

- **FR-005-VERIFICATION-ROLE**: verification-only agent role with no implementation, test, config, or ledger writes (`AO-008`).
- **FR-008-COMPATIBILITY**: unchanged TDD, immediate, init, and JUDGE behavior (`AO-013`).
- **FR-009-PROMPT-CONTRACTS**: distinct assembled versus atomic instructions and historical-ambiguity halt (`AO-014`).
- **FR-010-DOCUMENTATION**: both verification levels plus ownership and migration in user and spec docs (`AO-015`).
- **Source**: `specs/008-repository-capability-checkpoints/prd.md` (`FR-005`, `FR-008`, `FR-009`, `FR-010`; `AO-008`, `AO-013`, `AO-014`, `AO-015`).

## User Stories Ledger

- `US-008-06`: As an operator, I run a checkpoint so verification executes declared commands and leaves implementation, tests, config, and ledger unchanged.
- `US-008-07`: As an operator, I keep shipping normal tasks so existing TDD cycles and immediate execution behave exactly as before.
- `US-008-08`: As a new operator, I read the docs so I can place, run, and interpret checkpoints from docs alone.

## ATDD Acceptance Criteria

## Acceptance Outline

- `AO-008` (`FR-005`): a checkpoint run changes no application source, tests, configuration, or workflow ledger outside runtime-owned evidence paths. Result: implementation diffs stay empty after verification-only runs.
- `AO-013` (`FR-008`): existing TDD cycles, ordinary immediate tasks, init merges, and JUDGE scope verdicts behave exactly as before. Result: existing regression suites pass unchanged.
- `AO-014` (`FR-009`): assembled verification and atomic test authoring use distinct prompt instructions, and historical ambiguity halts for review. Result: zero historical E2E-authoring batches silently convert to read-only checks.
- `AO-015` (`FR-010`): user documentation and specifications describe both verification levels, repository ownership, and migration fallbacks. Result: a new operator can place, run, and interpret checkpoints from docs alone.

## Multi-Tiered Verification Targets

- **Unit Tests**: read-only role (empty implementation diff after checkpoint run), sibling regression parity, prompt label distinction, historical-ambiguity halt.
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `git diff --stat` shows zero implementation changes after a verification-only run
- **Verification Command**: `pytest tests/ -v -k "not checkpoint"` confirms sibling suites pass unchanged

## Demonstration Path

```bash
# Run a checkpoint, then confirm the implementation tree is untouched
deviate micro run --task-id 008-003-TASK
git diff --stat
# Confirm sibling behavior and prompt routing
pytest tests/ -v -k "not checkpoint"
grep -rn "checkpoint" src/deviate/prompts/assembly.py
mise run check
```
