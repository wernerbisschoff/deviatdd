# Implementation Tasks: `feat/adhoc/046-judge-rpc-no-agent-end-sidecar`

## Phase 1: RPC no-agent_end diagnostics
**Goal**: Failed `prompt` response error text surfaces in `EmptyOutputError` on the no-`agent_end` path

### Tasks

- TSK-046-01: Surface pi-side response error on no-agent_end RPC run
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_judge_rpc_no_agent_end.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/unit/test_micro/test_judge_rpc_no_agent_end.py`
  - **Rationale**: `src/deviate/core/agent.py` owns `_invoke_rpc_blocking` which drops failed `prompt` response payloads per `AC-PLAN-001` (`US-046-01`, `AO-046-01`); the unit test file encodes that scenario as the failing observable plus the `AC-PLAN-004` preservation pin for the valid-`agent_end` path
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_judge_rpc_no_agent_end.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Feed a mocked RPC transcript holding a failed `prompt` response (`success:false` with `error` text), no `agent_end` event, exit code 0, and assert `EmptyOutputError` carries the response error text plus stderr. Preservation: feed a valid-`agent_end` transcript and assert the manifest flows through unchanged (`AC-PLAN-004`); feed a nonzero-exit transcript and assert `AgentSubprocessError` still raises first. Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture per repo policy where the CLI path is touched
    - **Green**: Implement failed-response tracking in `_invoke_rpc_blocking` in `src/deviate/core/agent.py`, scoped to the workstation files for these scenarios. Parse `error`/`message` from parsed `response`-type events with `success:false`; skip non-JSON lines as today; when `manifest_text` stays empty with exit 0 raise `EmptyOutputError` with combined response error plus stderr. GREEN cannot edit tests
    - **Refactor**: Align parsing with existing defensive style in `agent.py`; keep the stderr fallback; no new dependencies
    - **Edge Cases**: Handle malformed JSON lines by skipping without crash; handle missing `error`/`message` keys by falling back to stderr alone; handle nonzero exit by keeping the `AgentSubprocessError` branch first
    - **Acceptance**: Failed-response transcript raises `EmptyOutputError` with pi-side text; valid-`agent_end` and nonzero-exit paths behave as before; `Verification` passes

---

## Phase 2: Sidecar plus distinguishing event on empty-manifest path
**Goal**: JUDGE empty-manifest failures write `.raw/judge-*.log` sidecars and log `JUDGE_AGENT_NO_AGENT_END`

### Tasks

- TSK-046-02: Write judge sidecar and distinguishing event on empty-manifest path
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_judge_rpc_no_agent_end.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_judge_rpc_no_agent_end.py`
  - **Rationale**: `src/deviate/cli/micro.py` owns `_invoke_agent` which returns `(None, "")` on `EmptyOutputError` without sidecars per `AC-PLAN-002` and `AC-PLAN-003` (`US-046-01`, `AO-046-01`); the unit test file asserts the sidecar call, the event fields, and the JUDGE message carrying pi-side text
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_micro/test_judge_rpc_no_agent_end.py` only — forbid `tests/integration` and `tests/e2e` in this RED. Mock `_invoke_rpc_blocking` to raise `EmptyOutputError("pi-side boom")` and assert `_invoke_agent` calls `_write_invoke_sidecars` with stderr plus response error text, logs `JUDGE_AGENT_NO_AGENT_END` for phase JUDGE only, and the JUDGE `PhaseFailedError` message carries the pi-side text (`AC-PLAN-002`). Assert the empty-stderr variant still writes the response error text into `.raw/judge-*.log` with nothing dropped (`AC-PLAN-003`). Preservation: assert a valid-manifest run emits existing events only and compliance rejections keep current messages (`AC-PLAN-004`). Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture per repo policy
    - **Green**: Implement the sidecar call on the shared `EmptyOutputError`/`MalformedHandoverManifestError` except path in `_invoke_agent` in `src/deviate/cli/micro.py`, scoped to the workstation files for these scenarios. Gate the distinguishing `JUDGE_AGENT_NO_AGENT_END` log event on phase JUDGE, keep the sidecar write generic, and thread `exc` text into the JUDGE `PhaseFailedError`. GREEN cannot edit tests
    - **Refactor**: Reuse `_write_invoke_sidecars` and `_log_run` idioms; keep non-JUDGE phases unchanged
    - **Edge Cases**: Handle empty stderr by writing response error text alone; handle `MalformedHandoverManifestError` on the same path; handle response payload shape variance defensively without crashing
    - **Acceptance**: Empty-manifest JUDGE run writes the sidecar, logs the distinguishing event, and surfaces pi-side text; valid-run path unchanged; `Verification` passes
  - **Dependency**: TSK-046-01

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 (Phase 2 consumes the `EmptyOutputError` text Phase 1 produces)

**Critical Dependency Chains**:
- TSK-046-02 must follow TSK-046-01

**Risk Hotspots**:
- Response payload shape varies across pi versions — parse defensively, keep stderr fallback, never drop the sidecar
- Shared `_invoke_agent` path changes non-JUDGE phases — gate the distinguishing event on phase JUDGE, keep sidecar write generic

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/unit/test_micro/test_judge_rpc_no_agent_end.py` (both tasks append distinct test cases; Phase 2 rebases on Phase 1)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
