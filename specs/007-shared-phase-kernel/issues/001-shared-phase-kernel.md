---
title: "Shared phase kernel for micro auto and manual surfaces"
labels: ["epic:007-shared-phase-kernel", "layer:micro"]
source_file: "specs/007-shared-phase-kernel/issues/001-shared-phase-kernel.md"
blocked_by: []
coordinates_with: []
issue_id: "007-001"
---

## System Topology Mapping

- **Epic Domain**: `007-shared-phase-kernel`
- **Local File Path**: `specs/007-shared-phase-kernel/issues/001-shared-phase-kernel.md`
- **Workstation Paths**:
  - `src/deviate/cli/micro.py` (kernel types, five kernels, eight thin wrappers, three auto delegations)
  - `tests/test_micro/` (kernel coverage, token and contract regression tests)
  - `CHANGELOG.md` (`[Unreleased]` bullet for the manual RED adjudication change)
- **Application Layers Touched**: contract assembly (data types plus JSON emission), CLI surface (Typer commands), orchestration (auto runner delegation), persistence (ledger plus session plus git commits). Four layers, so the slice is vertical.

## The Problem Contract

As a DeviaTDD operator, I run micro phases through the auto runner or through the eight manual CLI commands, so both surfaces share one kernel per phase step and prompt retry contracts keep working against either surface.

## Scope Boundaries

- **Hard Inclusions**:
  - Kernel data contracts (`MicroPhaseKernel`, `KernelContext`, `PhaseSideEffects`, `KernelOutcome`, `KernelError`) inside `src/deviate/cli/micro.py`.
  - Five kernels: `_red_pre_kernel`, `_red_post_kernel` (with unified no-failing-test adjudication), `_green_post_kernel`, `_refactor_pre_kernel`, `_refactor_post_kernel`; JUDGE stays on `_apply_judge_verdict`.
  - Eight manual commands converted to thin wrappers with surface-level task resolution.
  - Auto delegation in `_run_red_phase`, `_run_green_phase`, `_run_refactor_phase` with kernels never invoking agents.
  - Fixed status tokens, verbatim commit literals and flags, additive-only contract JSON.
  - Kernel tests in `tests/test_micro/` plus the `CHANGELOG.md` `[Unreleased]` bullet.
- **Defensive Exclusions**:
  - `_cycle_phase` in `src/deviate/cli/macro.py` (dispatches only macro phases).
  - New kernel package, unified agent-invoking orchestrator, subprocess delegation of the manual surface to the auto runner.
  - JUDGE prompt, verdict, or diff logic changes.
  - Ledger, session, or contract state-shape changes.
  - Prompt text changes, HITL gate changes, E2E hardening for manual flows, GREEN status semantics changes.

## Upstream Requirement Tracing

- **FR-007-01**: Kernel data contracts and error model (`AC-007-01-01`, `AC-007-01-02`).
- **FR-007-02**: RED pre-contract kernel (`AC-007-02-01`, `AC-007-02-02`).
- **FR-007-03**: RED post side-effect kernel with unified adjudication (`AC-007-03-01`, `AC-007-03-02`).
- **FR-007-04**: GREEN post side-effect kernel (`AC-007-04-01`, `AC-007-04-02`).
- **FR-007-05**: REFACTOR pre-contract kernel (`AC-007-05-01`, `AC-007-05-02`).
- **FR-007-06**: REFACTOR post side-effect kernel (`AC-007-06-01`, `AC-007-06-02`).
- **FR-007-07**: Manual CLI thin-wrapper conversion (`AC-007-07-01`, `AC-007-07-02`).
- **FR-007-08**: Auto-orchestrator delegation with session continuity (`AC-007-08-01`, `AC-007-08-02`).
- **FR-007-09**: Interface compatibility and drift-prevention guarantees (`AC-007-09-01`, `AC-007-09-02`).
- **Source**: `specs/007-shared-phase-kernel/prd.md` (`FR-007-01` … `FR-007-09`, `AO-001` … `AO-018`).

## Multi-Tiered Verification Targets

- **Unit Tests**: `tests/test_micro/` kernel coverage (contract keys, outcome tokens, `KernelError` mapping, per-phase side effects, wrapper dispatch, auto delegation, regression guards).
- **Integration Tests**: full `pytest tests/ -v` exit 0, `ruff check .` clean, coverage at or above 80 percent.
- **Verification Command**: `pytest tests/test_micro/ -v` and `mise run check`

## Demonstration Path

```bash
# RED contract parity across surfaces
deviate red pre --task-id 007-001-TASK
pytest tests/test_micro/ -v
# GREEN and REFACTOR parity plus full gate
deviate green post --task-id 007-001-TASK
deviate refactor post --task-id 007-001-TASK
mise run check
```

## Acceptance Outline

- `AO-001` (`AC-007-01-01`, `FR-007-01`): kernel returns `KernelOutcome`; CLI prints the fixed status token verbatim.
- `AO-002` (`AC-007-01-02`, `FR-007-01`): `KernelError(token, detail)` maps to exit code 1 on manual; auto catches per step.
- `AO-003` (`AC-007-02-01`, `FR-007-02`): `deviate red pre` prints the five-key contract JSON plus mise doctor fields, additive-only.
- `AO-004` (`AC-007-02-02`, `FR-007-02`): auto RED builds the same contract in-process; shared keys match the manual output.
- `AO-005` (`AC-007-03-01`, `FR-007-03`): both RED surfaces produce identical side effects; manual prints `RED_POST_OK`.
- `AO-006` (`AC-007-03-02`, `FR-007-03`): no-failing-test routes adjudicate identically on both surfaces; CHANGELOG bullet added.
- `AO-007` (`AC-007-04-01`, `FR-007-04`): both GREEN surfaces produce identical side effects; manual prints `GREEN_POST_OK`.
- `AO-008` (`AC-007-04-02`, `FR-007-04`): GREEN guard failure keeps current tokens and exit codes; no partial side effect.
- `AO-009` (`AC-007-05-01`, `FR-007-05`): `deviate refactor pre` prints the eight-field contract JSON plus doctor fields.
- `AO-010` (`AC-007-05-02`, `FR-007-05`): auto refactor builds the same contract in-process; shared keys match.
- `AO-011` (`AC-007-06-01`, `FR-007-06`): both refactor surfaces produce identical side effects; manual prints `REFACTOR_POST_OK`.
- `AO-012` (`AC-007-06-02`, `FR-007-06`): regression-gate failure exits with the current code; no COMPLETED ledger row.
- `AO-013` (`AC-007-07-01`, `FR-007-07`): each of the eight commands wraps exactly one kernel call; outputs match pre-change.
- `AO-014` (`AC-007-07-02`, `FR-007-07`): `green_pre` and `judge_pre` emit no contract; stdout and exit codes byte-identical.
- `AO-015` (`AC-007-08-01`, `FR-007-08`): auto cycle yields the same commits, ledger rows, and session transitions as before.
- `AO-016` (`AC-007-08-02`, `FR-007-08`): one `_invoke_agent` call per auto phase; no kernel reaches `_invoke_agent`.
- `AO-017` (`AC-007-09-01`, `FR-007-09`): status-token regression tests pass on both surfaces; prompt retry contracts hold.
- `AO-018` (`AC-007-09-02`, `FR-007-09`): contract keys and commit literals verified unchanged by regression tests.
