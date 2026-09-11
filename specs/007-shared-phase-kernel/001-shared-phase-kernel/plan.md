## Plan Summary
- **Issue**: 007-001 — Shared phase kernel for micro auto and manual surfaces
- **Implementation Strategy**: Extract pure kernel functions in `src/deviate/cli/micro.py` for RED pre/post, GREEN post, and REFACTOR pre/post, then convert the eight manual commands to thin wrappers and point the three auto runners at the same kernels.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Manual kernel outcome prints fixed status token verbatim**
- **Source Outline**: `AO-001`
- **Upstream Traceability**: `US-007-01`, `FR-007-01`, `AC-007-01-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:red_pre`
- **Given**: Kernel types exist in `src/deviate/cli/micro.py`
- **When**: A manual command prints the `KernelOutcome` status token
- **Then**: Stdout holds the fixed token verbatim and the exit code is 0
- **Verification Mode**: automated
**Scenario AC-PLAN-002: Kernel error maps to exit 1 on manual and per-step catch on auto**
- **Source Outline**: `AO-002`
- **Upstream Traceability**: `US-007-01`, `FR-007-01`, `AC-007-01-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_resolve_task_context`
- **Given**: A kernel raises `KernelError` with token and detail
- **When**: The error surfaces on the manual command and on the auto runner
- **Then**: Manual exits 1 with the token and auto catches the error per step
- **Verification Mode**: automated
**Scenario AC-PLAN-003: Manual RED pre prints five-key contract JSON additively**
- **Source Outline**: `AO-003`
- **Upstream Traceability**: `US-007-01`, `FR-007-02`, `AC-007-02-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:red_pre`
- **Given**: A pending task resolves in the worktree
- **When**: The operator runs `deviate red pre`
- **Then**: Stdout holds the five-key contract JSON plus mise doctor fields with no key removed
- **Verification Mode**: automated
**Scenario AC-PLAN-004: Auto RED builds the same contract as manual RED pre**
- **Source Outline**: `AO-004`
- **Upstream Traceability**: `US-007-01`, `FR-007-02`, `AC-007-02-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_red_phase`
- **Given**: The auto runner starts a RED phase for the same task
- **When**: `_red_pre_kernel` builds the contract in-process
- **Then**: Shared contract keys match the manual `red pre` output exactly
- **Verification Mode**: automated
**Scenario AC-PLAN-005: Both RED post surfaces produce identical side effects**
- **Source Outline**: `AO-005`
- **Upstream Traceability**: `US-007-01`, `FR-007-03`, `AC-007-03-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:red_post`
- **Given**: RED tests ran for a pending task
- **When**: The operator runs manual `red post` and auto runs `_run_red_phase`
- **Then**: Ledger rows, session transitions, and commits match and manual prints `RED_POST_OK`
- **Verification Mode**: automated
**Scenario AC-PLAN-006: No-failing-test adjudication matches on both RED surfaces**
- **Source Outline**: `AO-006`
- **Upstream Traceability**: `US-007-01`, `FR-007-03`, `AC-007-03-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_adjudicate_red_no_failing_test`
- **Given**: A RED run collects no failing test
- **When**: Adjudication executes on either surface
- **Then**: Both surfaces route identically and `CHANGELOG.md` carries the `[Unreleased]` bullet
- **Verification Mode**: automated
**Scenario AC-PLAN-007: Both GREEN post surfaces produce identical side effects**
- **Source Outline**: `AO-007`
- **Upstream Traceability**: `US-007-01`, `FR-007-04`, `AC-007-04-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:green_post`
- **Given**: GREEN tests ran for the active task
- **When**: The operator runs manual `green post` and auto runs `_run_green_phase`
- **Then**: Ledger rows, session transitions, and commits match and manual prints `GREEN_POST_OK`
- **Verification Mode**: automated
**Scenario AC-PLAN-008: GREEN guard failure keeps tokens and writes no partial side effect**
- **Source Outline**: `AO-008`
- **Upstream Traceability**: `US-007-01`, `FR-007-04`, `AC-007-04-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_green_phase`
- **Given**: The GREEN guard fails for the active task
- **When**: `_green_post_kernel` rejects the transition
- **Then**: Status tokens and exit codes stay current and no ledger or session write occurs
- **Verification Mode**: automated
**Scenario AC-PLAN-009: Manual refactor pre prints eight-field contract JSON**
- **Source Outline**: `AO-009`
- **Upstream Traceability**: `US-007-01`, `FR-007-05`, `AC-007-05-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:refactor_pre`
- **Given**: A task sits in GREEN-passed state
- **When**: The operator runs `deviate refactor pre`
- **Then**: Stdout holds the eight-field contract JSON plus doctor fields
- **Verification Mode**: automated
**Scenario AC-PLAN-010: Auto refactor builds the same contract as manual refactor pre**
- **Source Outline**: `AO-010`
- **Upstream Traceability**: `US-007-01`, `FR-007-05`, `AC-007-05-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_refactor_phase`
- **Given**: The auto runner starts a REFACTOR phase for the same task
- **When**: `_refactor_pre_kernel` builds the contract in-process
- **Then**: Shared contract keys match the manual `refactor pre` output exactly
- **Verification Mode**: automated
**Scenario AC-PLAN-011: Both refactor post surfaces produce identical side effects**
- **Source Outline**: `AO-011`
- **Upstream Traceability**: `US-007-01`, `FR-007-06`, `AC-007-06-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:refactor_post`
- **Given**: REFACTOR work finished for the active task
- **When**: The operator runs manual `refactor post` and auto runs `_run_refactor_phase`
- **Then**: Ledger rows, session transitions, and commits match and manual prints `REFACTOR_POST_OK`
- **Verification Mode**: automated
**Scenario AC-PLAN-012: Regression-gate failure exits current code with no COMPLETED row**
- **Source Outline**: `AO-012`
- **Upstream Traceability**: `US-007-01`, `FR-007-06`, `AC-007-06-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:refactor_post`
- **Given**: The refactor regression gate fails
- **When**: `_refactor_post_kernel` rejects the transition
- **Then**: The command exits with the current code and appends no COMPLETED ledger row
- **Verification Mode**: automated
**Scenario AC-PLAN-013: Each manual command wraps exactly one kernel call**
- **Source Outline**: `AO-013`
- **Upstream Traceability**: `US-007-01`, `FR-007-07`, `AC-007-07-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:green_pre`
- **Given**: The eight manual commands exist in `src/deviate/cli/micro.py`
- **When**: Any manual command executes
- **Then**: It resolves the task, calls exactly one kernel, and emits the pre-change output
- **Verification Mode**: automated
**Scenario AC-PLAN-014: green_pre and judge_pre emit no contract and stay byte-identical**
- **Source Outline**: `AO-014`
- **Upstream Traceability**: `US-007-01`, `FR-007-07`, `AC-007-07-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:judge_pre`
- **Given**: The operator invokes `green_pre` or `judge_pre`
- **When**: The thin wrapper executes
- **Then**: Stdout and exit codes match pre-change bytes with no contract emitted
- **Verification Mode**: automated
**Scenario AC-PLAN-015: Auto cycle keeps commits ledger rows and session transitions**
- **Source Outline**: `AO-015`
- **Upstream Traceability**: `US-007-01`, `FR-007-08`, `AC-007-08-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_run_tdd_cycle_impl`
- **Given**: The auto runner executes a full TDD cycle
- **When**: RED GREEN and REFACTOR delegate to kernels
- **Then**: Commits, ledger rows, and session transitions equal pre-change behavior
- **Verification Mode**: automated
**Scenario AC-PLAN-016: One agent call per auto phase and none from kernels**
- **Source Outline**: `AO-016`
- **Upstream Traceability**: `US-007-01`, `FR-007-08`, `AC-007-08-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_invoke_agent`
- **Given**: The auto runner executes RED GREEN and REFACTOR phases
- **When**: Each phase delegates contract and side effects to kernels
- **Then**: Each phase calls `_invoke_agent` once and no kernel reaches `_invoke_agent`
- **Verification Mode**: automated
**Scenario AC-PLAN-017: Status-token regression tests pass and retry contracts hold**
- **Source Outline**: `AO-017`
- **Upstream Traceability**: `US-007-01`, `FR-007-09`, `AC-007-09-01`
- **Current-Code Evidence**: `tests/unit/test_micro/test_red.py`
- **Given**: Both manual and auto surfaces exist
- **When**: The suite runs `pytest tests/unit/test_micro/ -v`
- **Then**: Status-token regression tests pass and prompt retry contracts hold on either surface
- **Verification Mode**: automated
**Scenario AC-PLAN-018: Contract keys and commit literals verified unchanged**
- **Source Outline**: `AO-018`
- **Upstream Traceability**: `US-007-01`, `FR-007-09`, `AC-007-09-02`
- **Current-Code Evidence**: `tests/unit/test_micro/test_output_filter.py`
- **Given**: Kernel extraction refactors `src/deviate/cli/micro.py`
- **When**: The regression suite runs
- **Then**: Contract keys, status tokens, and commit literals verify unchanged
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: hosts kernel types, five kernels, eight thin wrappers, three auto delegations
  - **Current State**: 9046-line module with inline pre/post logic duplicated between manual commands and auto runners, no kernel types
  - **Changes Required**: Add `MicroPhaseKernel`, `KernelContext`, `PhaseSideEffects`, `KernelOutcome`, `KernelError`, extract five kernels, convert eight commands to wrappers, delegate three auto phases
  - **Integration Surface**: Typer commands, `_invoke_agent`, session and ledger helpers, git commit helpers, mise doctor helpers
- **tests/unit/test_micro/**: holds kernel coverage and regression guards
  - **Current State**: Phase tests exist per surface with no kernel-level contract tests
  - **Changes Required**: Add kernel contract, outcome token, `KernelError` mapping, side-effect parity, dispatch, delegation, and regression tests
  - **Integration Surface**: `src/deviate/cli/micro.py` kernels and commands, pytest fixtures in `conftest.py`
- **CHANGELOG.md**: records the manual RED adjudication change
  - **Current State**: No entry for unified no-failing-test adjudication
  - **Changes Required**: Append one `[Unreleased]` bullet for the manual RED adjudication change
  - **Integration Surface**: Release notes process only

## Implementation Strategy
- **Phase 1**: Extract kernel data contracts and five kernels with unified RED adjudication
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Add dataclasses and `KernelError`, move contract assembly and side-effect blocks into kernels, keep literals and flags verbatim
  - **Verification**: `pytest tests/unit/test_micro/ -v` passes for contract and adjudication tests
- **Phase 2**: Convert eight manual commands to thin wrappers and delegate three auto phases
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Wrappers resolve task context then call one kernel, auto phases call kernels around the single `_invoke_agent` call each
  - **Verification**: Wrapper dispatch and delegation tests pass, full `pytest tests/ -v` exits 0
- **Phase 3**: Add regression guards and CHANGELOG bullet
  - **Files**: `tests/unit/test_micro/`, `CHANGELOG.md`
  - **Approach**: Add token, key, literal, and retry-contract regression tests plus one `[Unreleased]` bullet
  - **Verification**: `mise run check` passes with coverage at or above 80 percent

## Data Flow Analysis
- Manual surface resolves task context, calls one kernel, prints the kernel outcome token and JSON. Auto surface builds `KernelContext`, calls the pre kernel for the contract, invokes the agent once, then calls the post kernel for ledger, session, and git side effects. Kernels never touch the network or agents. JUDGE keeps its `_apply_judge_verdict` path unchanged.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Contract key drift between surfaces | High | Medium | Shared kernel builds both contracts, regression test asserts key sets |
| Commit literal drift | High | Low | Verbatim literals stay in kernels, regression test asserts subjects |
| Kernel calls agent directly | Medium | Low | Delegation test asserts zero `_invoke_agent` calls from kernels |

## Security Profile
Risk surfaces: file paths, subprocess, deserialization
Negative tests: missing task id fails with token, doctored contract JSON rejected, guard failure writes no side effect
Constraints: GREEN writes only `src/` plus permitted paths, no new dependencies, no hardcoded secrets

## Integration Points
- **Typer manual commands**: eight commands keep names flags and stdout, each wraps one kernel
- **`_invoke_agent`**: stays the sole agent entry, called once per auto phase, never from kernels
- **Session plus ledger plus git**: post kernels own all side effects identically for both surfaces

## Constitutional Alignment
- **Architecture**: Micro-layer kernels unify auto and manual surfaces, JUDGE path unchanged, no layer skipped per §1
- **Testing**: pytest plus ruff via `mise run check`, kernel unit tests plus regression guards, coverage at or above 80 percent per §3
- **Git Isolation**: Work happens on the issue worktree branch, commits at phase boundaries per §4
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-018` encode the operator flow of running micro phases on either surface, RED turns them into failing kernel tests before GREEN
