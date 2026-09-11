## Plan Summary
- **Issue**: 009-001 — Micro phase package extraction with parity gate
- **Implementation Strategy**: Lock behavior with characterization tests under `tests/`, verbatim-move `src/deviate/cli/micro.py` into `src/deviate/cli/micro/`, leave a re-export shim under 100 lines, pass the parity gate, then delete the shim in its own commit.

## Acceptance Contract
**Scenario AC-PLAN-001: Old micro import paths resolve through the shim**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-009-02`, `FR-001`, `AC-009-01-01`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:from deviate.cli.micro import`
- **Given**: Callers import names from `deviate.cli.micro`
- **When**: The operator runs any `deviate micro` command after the move
- **Then**: Every import resolves through the shim and each command runs unchanged
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Behavior after the move matches behavior before the move**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-009-01`, `FR-001`, `AC-009-01-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_all`
- **Given**: Characterization tests for micro public functions exist under `tests/`
- **When**: The operator runs the full suite after the move
- **Then**: All characterization tests pass unchanged and the `deviate --help` snapshot matches the pre-move snapshot
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Lint and quality gate stay green after the move**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-009-01`, `FR-006`, `AC-009-03-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_log_run`
- **Given**: The package move and shim are in place
- **When**: The operator runs `ruff check .` and `mise run check`
- **Then**: Ruff reports zero violations and `mise run check` exits zero
- **Verification Mode**: automated

**Scenario AC-PLAN-004: No micro submodule imports the shim**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-009-01`, `FR-001`, `AC-009-05-01`
- **Current-Code Evidence**: `src/deviate/core/converge.py:from deviate.cli.micro import _find_all_pending_tasks`
- **Given**: Micro logic lives in `src/deviate/cli/micro/` submodules
- **When**: The operator greps submodule imports for the shim path
- **Then**: Zero submodule files import the shim and the import direction stays one-way
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Characterization tests land before the move commit**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-009-01`, `FR-005`, `AC-009-06-01`
- **Current-Code Evidence**: `tests/unit/test_micro/test_kernel_outcome.py:KernelOutcome`
- **Given**: No move commit exists yet on the issue branch
- **When**: The operator inspects git history after the extraction
- **Then**: Characterization tests under `tests/` predate the move and no behavior edit shares the move commit
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Shim deletes only after zero shim imports remain**
- **Source Outline**: `AO-007`
- **Upstream Traceability**: `US-009-03`, `FR-007`, `AC-009-07-01`
- **Current-Code Evidence**: `src/deviate/cli/meso.py:from deviate.cli.micro import existing_verification_suites`
- **Given**: All callers import directly from `src/deviate/cli/micro/` submodules
- **When**: The maintainer deletes the shim in its own commit and re-runs parity
- **Then**: The shim file is gone, parity re-passes, and all imports resolve to submodules
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro/**: new package holding the verbatim-moved micro logic + `evidence: _run_all, micro_app, red_app, green_app, judge_app, refactor_app` + `Integrates: deviate.cli __init__ Typer registration, converge.py pending-task lookup, meso.py verification-suite import`
- **src/deviate/cli/micro.py**: shrinks to a re-export shim under 100 lines with no logic + `evidence: line count 9970 shrinking to shim` + `Integrates: src/deviate/cli/micro/ submodules`
- **src/deviate/cli/__init__.py**: keeps importing the same public names, source switches to package when shim deletes + `evidence: from deviate.cli.micro import (line 32)` + `Integrates: Typer app assembly`
- **src/deviate/core/converge.py**: direct-submodule import target after shim deletion + `evidence: from deviate.cli.micro import _find_all_pending_tasks (line 117)` + `Integrates: src/deviate/cli/micro/ lookup submodule`
- **src/deviate/cli/meso.py**: direct-submodule import target after shim deletion + `evidence: from deviate.cli.micro import existing_verification_suites (line 1294)` + `Integrates: src/deviate/cli/micro/ verification submodule`
- **tests/**: characterization lock for micro public surface plus parity coverage + `evidence: tests/unit/test_micro/test_kernel_outcome.py:KernelOutcome` + `Integrates: pytest suite, ruff gate`

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 9970-line verbatim move drops or renames a symbol consumed by `__init__.py`, `converge.py`, or `meso.py` | High | Medium | Characterization tests predate the move; shim re-exports the full public surface; parity gate runs the full suite |
| Circular import between new submodules during the split | High | Low | Keep the move verbatim in one package first, split into submodules only after parity passes |
| Shim exceeds 100 lines or accumulates logic | Low | Low | Shim holds re-exports only; line-count check runs in the parity gate |
| Scope creep into `ledger.py` or shared-helper consolidation | Medium | Low | Out of scope per 009-005; JUDGE flags edits outside the allow-list |

## Security Profile
Risk surfaces: subprocess invocation, git branch operations, ledger appends
Negative tests: shim exposes no new CLI flags, no secret material in sidecars or logs
Constraints: no new dependencies, no edits to `src/deviate/state/ledger.py`, no behavior edits in the move commit

## Constitutional Alignment
- **Constitution**: §1, §3, §4 — three-layer gates hold with no layer skipped, parity keeps pytest plus ruff green with coverage at or above 80 percent, work stays on the issue worktree branch with commits at phase boundaries
