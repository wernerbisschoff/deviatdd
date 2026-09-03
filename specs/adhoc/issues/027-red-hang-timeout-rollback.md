---
title: "Raise AGENT_TIMEOUT and roll back dirty RED when the agent never returns a manifest"
labels: [bugfix, adhoc, vertical-slice, micro]
blocked_by: []
coordinates_with: [ISS-ADH-025, ISS-ADH-023]
issue_id: ISS-ADH-027
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/027-red-hang-timeout-rollback.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py::_run_red_phase` — TARGET: after `PHASE_START` + `red_baseline = _worktree_status_paths(root)`, a RED `_invoke_agent` that never returns a manifest must not leave the worktree dirty and must not collapse a harness timeout into a silent wait. Today `manifest is None` raises `PhaseFailedError("agent returned no manifest")` with no `_restore_worktree_to_baseline`. Ledger append and `session.force_transition_to("RED")` run only after tests fail, so a hung child leaves IDLE + dirty tracked files + no JSONL row.
  - `src/deviate/cli/micro.py::_invoke_agent` — TARGET: keep logging `AGENT_TIMEOUT` with `error=`, `partial_stderr=`, `partial_stdout=` on `AgentTimeoutError`. RED must not wait for an outer bash kill, and must not hide a timeout behind a generic "no manifest" with no prior `AGENT_TIMEOUT` / `PHASE_DECISION`. Contrast GREEN, which already treats `manifest is None and timeout_ctx` as `GREEN phase agent timed out`.
  - `src/deviate/cli/micro.py::_restore_worktree_to_baseline` — TARGET: reuse on RED harness timeout / never-returned-manifest so files the child wrote after `red_baseline` are discarded (`git restore` tracked, `git clean -fd` untracked). Do not invent a second restore helper.
  - `src/deviate/core/agent.py::invoke` / `_invoke_streaming` — TARGET: a child that writes files or emits some stdout and then never exits / never yields a handover manifest must still raise `AgentTimeoutError` inside the harness budget. Compose ISS-ADH-025: stderr stays diagnostic; do not restore stderr-as-liveness. A post-write hang is not solved by waiting for silence if occasional stdout keeps the 900s clock warm — the operator-visible verdict must still beat the outer ~1800s bash timeout.
  - `src/deviate/core/agent.py::AgentConfig.timeout` / `_invoke_agent` `AgentConfig(backend=backend_name)` — REFERENCE: `_invoke_agent` currently constructs a fresh config with default `timeout=600` and does not thread `DeviateConfig.timeout` / `timeout_seconds` (operator-local 1800). Do not raise the wall-clock so it races the outer bash timeout. Do not revert operator-local `.deviate/config.toml`.
  - `src/deviate/cli/micro.py::EXECUTE_STALL_TIMEOUT_SECONDS` / `_run_execute_phase` — REFERENCE: GH-53 / ISS-ADH-025 compose. EXECUTE stall stays 3600s.
  - `src/deviate/cli/micro.py::_find_task_record` / `_exit_if_already_done` — COMPOSE ONLY: GitHub #62 / ISS-ADH-023 already scopes pinned lookup when the active issue is known and refuses foreign `TASK_ALREADY_DONE`. `_find_task_record` still has a `preferred` first-same-id fallback when no issue resolves; `_LEDGER_GLOB` scans all `specs/**/tasks.jsonl` but keys `(issue_id, tid)`. Close a leftover hole only if the RED hang path (IDLE session, no this-issue ledger row, dirty tree) still prints `TASK_ALREADY_DONE` from a sibling COMPLETED, or if a known active issue still receives that `preferred` hit. Do not reopen #62.
  - `tests/unit/test_cli/test_micro.py` / `tests/unit/test_micro/test_run.py` / `tests/unit/test_core/test_agent.py` — TARGET: pin RED timeout + restore; keep ISS-ADH-025 stall pins and ISS-ADH-023 issue-scope pins.
  - `specs/DeviaTDD-api.md` / `specs/DeviaTDD-architecture.md` — TARGET: document RED `AGENT_TIMEOUT` + dirty-tree rollback when the child never returns a manifest.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible hang/rollback fix.
- **Classification for plan/tasks**: production Python with an observable fail-to-pass contract. Prefer **TDD**. Do not fatten GREEN. Adhoc/plan still picks TDD vs IMMEDIATE for other slices.
- **Upstream Evidence**:
  - GitHub #56: linked-worktree TDD slice. Runner emitted `PHASE_START` + `INVOKE_AGENT`, then silence until the outer bash timeout. No `AGENT_RESULT`, no `PHASE_DECISION`, no `AGENT_TIMEOUT`. Task stayed mid-RED with a dirty tracked file and no ledger row.
  - Same report: `deviate micro run TSK-003-01` printed `TASK_ALREADY_DONE` from a sibling issue's COMPLETED same-number TSK. GitHub #62 (merged PR #78 / ISS-ADH-023) already scoped pinned-ID lookup. Do not reopen #62.
  - `_invoke_agent` swallows `AgentTimeoutError` and returns `None`; RED always maps `None` to "no manifest". GREEN maps timeout partials to `GREEN phase agent timed out`.
  - `_restore_worktree_to_baseline` exists for no-failing-test adjudication only.
  - ISS-ADH-025 / GH-61: stderr is not liveness; streaming stall re-raises without the 30s + second 900s retry. A RED child that already wrote output can still hang without a silent-stdout stall.

## The Problem Contract

A RED `pi` child can write tests (or other tracked files) and then never return a handover manifest. The runner sits after `INVOKE_AGENT` until an outer bash timeout kills it, leaving a dirty mid-RED worktree and no ledger event. Operators need the harness to declare `AGENT_TIMEOUT` itself, roll the tree back to the pre-RED baseline, and keep ISS-ADH-025 / ISS-ADH-023 composed.

## Scope Boundaries

### Hard Inclusions

- A RED agent that writes files (or other output) and never returns a parseable manifest must raise `AgentTimeoutError` / log `AGENT_TIMEOUT` (or an equivalent harness-visible failure that names timeout) instead of waiting for an outer ~1800s bash timeout.
- After that failure, `_run_red_phase` must restore the worktree to the captured `red_baseline` so hung-child diffs do not remain as dirty tracked/untracked state. The task must stay retryable (PENDING or an explicit non-success). Do not append a COMPLETED or RED-success ledger row for the hung attempt.
- Operator-visible outcome after `INVOKE_AGENT` must include `AGENT_TIMEOUT` (or equivalent) and must not be only silence until bash, then a generic `agent returned no manifest`.
- Compose ISS-ADH-025: stderr remains diagnostic for stall liveness; do not reintroduce stderr-as-liveness; do not add a second full 900s stall retry that loses the race to bash.
- Compose ISS-ADH-023: pinned `deviate micro run TSK-NNN-NN` stays issue-scoped. Investigate leftover `TASK_ALREADY_DONE` only if the RED hang path still false-positives a sibling COMPLETED or `_find_task_record` still returns a bare-id / `preferred` hit when the active issue is known.
- EXECUTE continues to pass `stall_timeout=EXECUTE_STALL_TIMEOUT_SECONDS` (3600). Do not reopen GH-53 except to compose.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.
- Tests stay fast: patch stall/timeout budgets; mock `deviate.cli.micro._run_pytest` if a CLI path would spawn it. Do not sleep 900s or 1800s in CI.

### Defensive Exclusions

- Do **not** reopen GitHub #62 / ISS-ADH-023 except to compose or to close a proven leftover hole on the RED hang path.
- Do **not** reopen GitHub #61 / ISS-ADH-025 except to compose (stderr-not-liveness stays).
- Do **not** reopen GitHub #58 / #54 / #53 except to compose. EXECUTE stall stays 3600s.
- Do **not** make the interactive stall so aggressive that a healthy RED quiet for a few minutes of model think time is killed. Do not drop the default 900s GREEN/RED stall solely to paper over a post-write hang.
- Do **not** author, repair, or index Product-layer flows (`flow_refs: []`). FLOW-04 is RPC TUI live-stream, not RED hang/rollback policy.
- Do **not** delete branches, mutate operator-local `.deviate/config.toml` (`backend=pi`, `transport=cli`, `pi_rpc=false`, `timeout=1800`, `models.default=grok-4.6`, `timeout_seconds=1800`), or add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.
- Do **not** change TSK id format, ledger append-only rules, or invent a second issue-id series.
- Do **not** treat schema-rejection (`tool_count_limit`) as this slice; that is ISS-ADH-026.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-027`
- **Acceptance Criteria Tokens**: `AC-ADHOC-027-01`, `AC-ADHOC-027-02`, `AC-ADHOC-027-03`
- **Data Model Entities**: `AgentTimeoutError.partial_stdout`, `AgentTimeoutError.partial_stderr`, `SessionState.red_commit_sha` — no new ledger row types required; hung RED must not mint a success transition
- **Spec Source Anchors**:
  - `src/deviate/cli/micro.py` `_run_red_phase` / `_invoke_agent` / `_restore_worktree_to_baseline`
  - `src/deviate/core/agent.py` `invoke` / `_invoke_streaming` / `AgentTimeoutError`
  - `src/deviate/cli/micro.py` `_find_task_record` / `_exit_if_already_done` (compose ISS-ADH-023)
  - `specs/constitution.md` §1 Git Isolation / Append-Only Ledger; §3 Testing Protocols; §5 Definition of Done (CHANGELOG for user-visible bug fix)

## User Stories Ledger

- **US-027-01**: As a DeviaTDD operator running RED via `pi -p`, I want a child that writes files then never returns a manifest to raise `AGENT_TIMEOUT` from the harness so I do not wait for an outer bash kill. *(Ref: FR-ADHOC-027)*
- **US-027-02**: As a DeviaTDD operator, I want uncommitted RED diffs from that hung child rolled back so a retry starts from a clean pre-RED tree instead of a dirty mid-RED worktree with no ledger row. *(Ref: FR-ADHOC-027)*
- **US-027-03**: As a DeviaTDD operator, I want this slice to compose with ISS-ADH-025 / ISS-ADH-023 and keep EXECUTE's 3600s stall, reopening those issues only if a leftover hole still false-positives `TASK_ALREADY_DONE`. *(Ref: FR-ADHOC-027)*

## Acceptance Outline

- **AO-027-01** *(Ref: AC-ADHOC-027-01, US-027-01)*: Hung RED after writes is a harness timeout, not an outer bash kill.
  - **Happy Path**: A mocked RED invoke that creates or dirties a tracked file and then never returns a handover manifest logs `AGENT_TIMEOUT` (with `error=` / partial streams) and fails inside the patched harness budget, well under ~1800s.
  - **Error Category**: Silence after `PHASE_START` + `INVOKE_AGENT` until an outer bash timeout, with no `AGENT_TIMEOUT` / `PHASE_DECISION` / `AGENT_RESULT`, is a failure of this slice.
  - **Boundary Category**: Collapsing the failure to only `agent returned no manifest` without a prior timeout event is a failure. A healthy RED that returns a manifest within the budget still proceeds to the existing test / ledger / commit path.

- **AO-027-02** *(Ref: AC-ADHOC-027-02, US-027-02)*: Hung-child RED diffs do not survive the harness failure.
  - **Happy Path**: After the timeout failure, `git status` matches the pre-invoke `red_baseline`; files the child wrote or modified are restored or cleaned.
  - **Error Category**: Leaving a dirty tracked file, an uncommitted RED test, and no ledger row (session still mid-RED / IDLE) is a failure.
  - **Boundary Category**: Do not append COMPLETED or a successful RED transition for the hung attempt. Files that were already dirty in `red_baseline` stay untouched. Retry of the same TSK on this issue is allowed.

- **AO-027-03** *(Ref: AC-ADHOC-027-03, US-027-03)*: #61 / #62 / EXECUTE 3600s stay composed.
  - **Happy Path**: Stderr-only noise still does not reset the stall clock (ISS-ADH-025). Pinned `micro run TSK-NNN-NN` still ignores a sibling COMPLETED when this issue has no terminal row (ISS-ADH-023). EXECUTE still passes `stall_timeout=3600`.
  - **Error Category**: Reopening those issues to rewrite their contracts, or collapsing EXECUTE to 900s, is a failure.
  - **Boundary Category**: If and only if the RED hang path still false-positives `TASK_ALREADY_DONE` or `_find_task_record` still returns a `preferred` / bare-id hit for a known active issue, close that leftover hole here. API / architecture / CHANGELOG update in the same implementation commit.

## Edge Cases and Boundaries

- Post-write hang is distinct from a silent-from-start stall: the child may have emitted tool/write stdout, so the 900s stall clock may have been reset. The harness must still own the deadline before bash.
- `_invoke_agent` currently returns `None` on timeout; RED must not treat that the same as a clean skip (`AGENT_NOT_AVAILABLE`) or leave diffs behind.
- Session `red_commit_sha` is cleared at RED start and only rewritten after a RED commit. A hang must not invent a SHA or leave a half-written session that blocks GREEN.
- `preferred` fallback in `_find_task_record` remains legal only when no active issue resolves (unscoped unit tests). A known worktree issue must never receive a sibling COMPLETED.
- Operator-local `.deviate/config.toml` timeout 1800s is context for the race, not a value this slice should rewrite.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: harness timeout + restore must complete inside the configured agent/stall budget plus small in-process slack, not at an outer ~1800s bash deadline. Init stays ≤ 500ms; no extra live agent calls on the healthy path.
- Throughput: full test suite remains < 30s. Timeout/restore tests use patched millisecond-to-sub-second budgets and mocked `Popen` / `_invoke_agent`. Mock `deviate.cli.micro._run_pytest` if a CLI path would spawn it.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_cli/test_micro.py` — new pin: `_run_red_phase` when `_invoke_agent` raises/returns timeout (`AgentTimeoutError` / `None` + timeout partial) logs `AGENT_TIMEOUT` and calls restore; worktree matches `red_baseline`; no RED ledger success row.
  - `tests/unit/test_cli/test_micro.py` — keep ISS-ADH-025 first-stall `AGENT_TIMEOUT` pin and EXECUTE `stall_timeout==3600` pin.
  - `tests/unit/test_cli/test_micro.py` / `tests/unit/test_micro/test_e2e.py` — keep ISS-ADH-023 issue-scoped lookup pins; add a leftover-hole pin only if a known active issue can still see a sibling COMPLETED after a hung RED.
  - `tests/unit/test_core/test_agent.py` — keep stdout-stall / stderr-not-liveness / stall-override pins; add a post-write hang pin only if invoke still waits for bash when stdout already flowed and no manifest arrives.
- **Integration Sandbox Targets**:
  - Not a live `pi -p` hang. Mocked backend / `Popen` is sufficient. If a `deviate micro run` CLI test is added, mock the agent and `deviate.cli.micro._run_pytest`.

## Demonstration Path

```bash
# Mocked RED timeout + restore + composed stall/scope pins (no live agent)
uv run pytest tests/unit/test_cli/test_micro.py tests/unit/test_core/test_agent.py tests/unit/test_micro/test_e2e.py -q -k "timeout or stall or find_task_record or already_done or red"
```
