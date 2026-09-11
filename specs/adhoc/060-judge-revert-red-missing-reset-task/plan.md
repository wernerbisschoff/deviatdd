## Plan Summary
- **Issue**: ISS-ADH-060 — Complete JUDGE revert_red rollback when the mise reset task is missing
- **Implementation Strategy**: Reorder the `revert_red` path so the git reset lands first, then convert a missing-reset `EnvNotReadyError` into a reported ENV precondition that preserves RED evidence and gates re-entry.

## Acceptance Contract
**Scenario AC-PLAN-001: Complete git reset to reset_to when reset task is missing**
- **Source Outline**: `AO-060-01`
- **Upstream Traceability**: `US-060-01`, `FR-ADHOC-060`, `AC-ADHOC-060-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_execute_rollback`
- **Given**: An integration task holds a valid orphan RED commit and no `[tasks.reset]` entry exists
- **When**: JUDGE fires `revert_red` against the pre-RED boundary
- **Then**: HEAD resets to `reset_to` and the orphan RED commit stays reachable via `recovery_ref`
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Report missing reset as distinct ENV precondition without behavior change for unit tasks**
- **Source Outline**: `AO-060-01`
- **Upstream Traceability**: `US-060-01`, `FR-ADHOC-060`, `AC-ADHOC-060-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_maybe_reset_isolated_env`
- **Given**: A unit or unstamped `test_strategy` task triggers a JUDGE rollback
- **When**: The runner evaluates the isolated-env reset hook
- **Then**: The runner skips `mise run reset` and completes the rollback with no ENV error
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Preserve RED evidence and gate re-entry until reset hook exists**
- **Source Outline**: `AO-060-02`
- **Upstream Traceability**: `US-060-01`, `FR-ADHOC-060`, `AC-ADHOC-060-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_apply_judge_verdict`
- **Given**: A `revert_red` rollback completed its git reset with no `reset` task defined
- **When**: The runner records the JUDGE verdict and advances the session
- **Then**: The report carries `head_sha`, `reset_to`, and `recovery_ref`, the RED ledger row persists, and the next RED/GREEN stays gated until a `reset` task exists
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Keep nonzero-exit reset failure as ENV_NOT_READY**
- **Source Outline**: `AO-060-02`
- **Upstream Traceability**: `US-060-01`, `FR-ADHOC-060`, `AC-ADHOC-060-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:_maybe_reset_isolated_env`
- **Given**: A `[tasks.reset]` entry exists and exits nonzero during a JUDGE rollback
- **When**: The runner executes `mise run reset`
- **Then**: The runner raises `ENV_NOT_READY` with the failure detail and blocks the next RED/GREEN
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/micro.py**: Reorder `revert_red` so `_execute_rollback` lands before `_maybe_reset_isolated_env` and convert missing-reset into a gated ENV report with rollback trace + `EnvNotReadyError:_maybe_reset_isolated_env` + `Integrates: _apply_judge_verdict, SessionState.red_commit_sha`
- **src/deviate/cli/init.py**: Keep `[tasks.reset]` merge-if-missing stub insertion unchanged; no consumer overwrite + `evidence: _generate_mise_toml_base:[tasks.reset]` + `Integrates: deviate init pre`
- **tests/unit/test_micro/test_rollback_safety.py**: Add `revert_red` without reset task case asserting git reset plus preserved RED evidence + `evidence: _execute_rollback` + `Integrates: src/deviate/cli/micro.py`
- **tests/unit/test_micro/test_run.py**: Assert `deviate micro run` surfaces the missing-reset ENV precondition with recovery details + `evidence: EnvNotReadyError` + `Integrates: src/deviate/cli/micro.py:_apply_judge_verdict`

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Env error swallowed and re-entry loops on stale catalog | High | Low | Gate next RED/GREEN on reset-hook presence |
| Fix leaks into revert_green path | Medium | Low | Touch only revert_red branch, keep ISS-ADH-059 path intact |
| Recovery ref lost when reset hook raises | High | Medium | Capture rollback trace before env reset attempt |

## Security Profile
Risk surfaces: subprocess (git, mise), recovery refs, ledger rows
Negative tests: missing reset never deletes RED evidence, unit tasks never invoke reset hook
Constraints: no new dependencies, no hardcoded secrets, stub insertion stays merge-if-missing
## Constitutional Alignment
- **Constitution**: §1, §3 — Micro-layer scope, session continuity, regression gate
