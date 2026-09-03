# Shared Phase Kernel (Auto Runner ⇄ Manual Pre/Post) — Product Requirements

Feature: `007-shared-phase-kernel` · Constitution: `specs/constitution.md` v0.10.0 · Phase: PRD

## Document Control and Metadata

| Field | Value |
| :--- | :--- |
| Upstream Reference | `specs/007-shared-phase-kernel/explore.md` |
| Upstream Design | `specs/007-shared-phase-kernel/design.md` |
| Upstream Data Model | `specs/007-shared-phase-kernel/data-model.md` |
| Constitution | `specs/constitution.md` v0.10.0 |
| Epic | `007-shared-phase-kernel` |
| Status | PROPOSED |
| Phase | PRD (macro layer) |
| Plan Target | `.deviate/artifacts/manifest_prd.json` |

## System Objectives and Scope Boundary

### Core Value Proposition

Each micro phase step (pre-contract, post side effects) exists twice today: once in the auto runner, once in the manual CLI. The two copies drift in status tokens, adjudication routes, and side-effect ordering. This feature extracts one kernel function per phase step into `src/deviate/cli/micro.py`. Both surfaces call the same kernels. The already-shared verdict path `_apply_judge_verdict` proves the pattern; this feature extends it to RED, GREEN, and REFACTOR.

User-visible value: drift prevention. The manual RED no-failing-test adjudication (exit 0 / pytest exit 5 / command-not-found exit 127 routes) converges into `red post`, so prompt retry contracts keep working against both surfaces.

Source anchor — `specs/007-shared-phase-kernel/design.md` `[Summary]`:

> "Extract one kernel function per micro phase step into `src/deviate/cli/micro.py`, in place. The auto runner (`_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`) and the eight manual CLI commands (`deviate red|green|judge|refactor pre|post`) call the same kernels."

### In-Scope Boundaries (Hard Directives)

- Add kernel data contracts (`MicroPhaseKernel`, `KernelContext`, `PhaseSideEffects`, `KernelOutcome`, `KernelError`) inside `src/deviate/cli/micro.py`.
- Add four kernels: `_red_pre_kernel`, `_red_post_kernel`, `_green_post_kernel`, `_refactor_pre_kernel` (pre side), `_refactor_post_kernel` (post side); JUDGE stays on the existing `_apply_judge_verdict` seam.
- Convert the eight manual commands to thin wrappers over the kernels.
- Delegate per-phase steps of `_run_red_phase`, `_run_green_phase`, `_run_refactor_phase` to the kernels.
- Unify the manual RED no-failing-test adjudication into `_red_post_kernel` (design decision K5, `HITL-002` RESOLVED).
- Update `tests/unit/test_micro/*` for kernel coverage; update `CHANGELOG.md` under `[Unreleased]` for the manual RED adjudication behavior change.

### Out-of-Scope Boundaries (Defensive Exclusions)

- `_cycle_phase` in `src/deviate/cli/macro.py` — verified to dispatch only `explore|research|prd|shard` and share no code with the four micro phases (`HITL-001` RESOLVED).
- New kernel package (Option B rejected — explore `## Scope Sizing`: "New Modules Required: No").
- One unified agent-invoking orchestrator (Option C rejected — the manual surface has no in-process agent invocation).
- Manual surface delegation to the auto runner via subprocess (Option D rejected — constitution §1 Session Continuity).
- JUDGE prompt, verdict, or diff logic changes — `_apply_judge_verdict` is already converged.
- Ledger, session, or contract state-shape changes (constitution §1 Append-Only Ledger Protocol holds).
- Prompt text changes — `_build_auto_prompt` plus `_LAYER_MAP` and the `_derive_manual_body` splice already single-source prompt text.
- HITL gates, E2E hardening for manual flows (observed gap only), GREEN status semantics changes.

## Architectural Constraints and Prerequisites

### Data Models & Invariants

Five kernel types live in `src/deviate/cli/micro.py`. Persistence shapes (`tasks.jsonl`, `.deviate/session.json`) stay unchanged.

Source anchor — `specs/007-shared-phase-kernel/data-model.md` `## Schema Tables`:

```python
@dataclass(frozen=True)
class KernelContext:
    root: Path
    console: Console
    session: SessionState
    session_path: Path
    ledger_path: Path
    task_id: str
    mode: Literal["auto", "manual"]
```

Source anchor — `specs/007-shared-phase-kernel/data-model.md` `## Schema Tables`:

```python
@dataclass(frozen=True)
class KernelOutcome:
    status_token: str            # fixed token referenced by prompt retry contracts
    contract: MicroPhaseKernel | None
    emit_contract: bool
    task_id: str

class KernelError(Exception):
    token: str                   # e.g. "TEST_NOT_FOUND", "LEDGER_UPDATE_FAILED"
    detail: str
```

Invariants (from `specs/007-shared-phase-kernel/data-model.md`):

- `INV-1` — `MicroPhaseKernel` contract keys are additive-only; existing keys keep names and value semantics; serialized via `json.dumps(..., ensure_ascii=False)`.
- `INV-2` — `KernelContext` is immutable per kernel call; `mode` never alters side-effect semantics, only adjudication routes and error presentation.
- `INV-3` — `ledger_appended == true` implies exactly one `append_task_transition` row; ledger rows are append-only, no overwrite (constitution §1).
- `INV-4` — `emit_contract` is true iff the phase prints contract JSON (`red pre`, `refactor pre`); `green_pre` and `judge_pre` print no contract.
- `INV-5` — `KernelError` carries `token` + `detail`; the CLI maps it to `typer.Exit(code=1)`; the auto runner catches it per phase step; commit literals are never mutated by error paths.

Source anchor — `specs/007-shared-phase-kernel/explore.md` `## Architectural Baselines` (manual RED pre contract):

```python
    contract = {
        "task_id": task_data.get("id", ""),
        "test_command": _resolve_verification_command(root, task_data),
        "lint_command": "mise run lint",
        "spec_dir": spec_dir,
        "task_entry": _task_card_text(root, task_data),
    }
```

Source anchor — `specs/007-shared-phase-kernel/explore.md` `## Data & State Management` (RED side-effect chain, preserved verbatim):

```python
    session = session.force_transition_to("RED")
    session.save(session_path)
    scope = _build_scope(issue_id, task_uuid)
    _commit_phase(
        f"test({scope}): RED phase - failing test",
        root,
        no_verify=True,
        phase="red",
    )
```

### Performance / Scalability Thresholds

- Full pytest suite stays under 30 seconds (AGENTS.md "Test Performance"): every kernel test that reaches `_run_pytest` mocks `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture.
- Pre kernels perform no agent invocation, no network call, and no subprocess beyond the existing doctor attachment (`_attach_mise_pre`); `deviate red pre` and `deviate refactor pre` stay non-blocking JSON emitters.
- Kernel extraction adds zero new subprocess invocations per phase step compared with the current code paths (`_run_test_cmd`, `_run_format_cmd`, `_run_pytest`, `git rev-parse` usage preserved as-is).

### Security & Compliance Invariants

- Append-only ledger (constitution §1): kernels write transitions only through the existing `append_task_transition`; no state shape changes.
- Git isolation (constitution §1): task loops stay on a clean branch or worktree; commits happen at phase boundaries; commit messages reference the task scope per §4.
- Session continuity (constitution §1): kernels never invoke agents; the auto orchestrator keeps `_invoke_agent` in-process with `resolve_model_for_phase` per the `[models]` routing; no model switching mid-task.
- Safe-command filters pass through unchanged: `is_safe_test_command` in `_task_verification_command`, `_constitution_test_command`, and `run_safe_command` in the execution layer.
- Existing `_commit_phase` flags pass through verbatim (`no_verify=True`, `phase="red"`) — behavior-preserving extraction, no flag changes (design RSK-002).
- HITL gates untouched (constitution §1): Gate 1 already passed for this feature; Gate 3 applies after micro.

## Functional Flow and Sequence Architecture

### System Orchestration Mapping

Source anchor — `specs/007-shared-phase-kernel/data-model.md` `## Relationship Graph` (verbatim):

```
Surface orchestrators (2)          Kernels (shared, 1 copy each)
├─ _run_red_phase ──────────────►  _red_pre_kernel / _red_post_kernel
│   └─ _build_auto_prompt → _invoke_agent   (auto only; kernel never invokes agents)
├─ _run_green_phase ────────────►  _green_post_kernel
├─ _run_judge_phase ────────────►  _apply_judge_verdict   (existing shared seam)
├─ _run_refactor_phase ─────────►  _refactor_post_kernel
├─ red_pre / refactor_pre ──────►  pre kernels ──► MicroPhaseKernel (JSON contract)
├─ red_post / green_post ───────►  post kernels ─► PhaseSideEffects
├─ judge_pre / judge_post ──────►  _apply_judge_verdict (judge_post via injected diff)
└─ refactor_post ───────────────►  _refactor_post_kernel
```

Graph rules (from `specs/007-shared-phase-kernel/data-model.md`):

- Auto surface → kernels: navigates surface → kernel only; kernels never call orchestrators (acyclic).
- Kernels → state writers: cardinality 1 per side effect per phase; writers stay independent.
- CLI commands → kernels: one command wraps exactly one kernel call; task resolution helpers (`_resolve_task_context`, `_resolve_first_pending` + `--task-id`, `_resolve_judge_post_task`) feed `task_id` into `KernelContext` (design K6 — task resolution stays surface-level).
- Task phase machine is unchanged: PENDING → RED → GREEN → JUDGE → COMPLETED, with the JUDGE branch to RED on rework verdict (data-model `## State Transitions`).

## Functional Requirements and Epics

Epic `007-shared-phase-kernel` carries `FR-007-01` … `FR-007-09`. Every FR implements constitution §1 (in-place, append-only, session-continuity-preserving consolidation) and §3 (pytest-covered observable behavior). Each FR lists its upstream source anchors; acceptance outlines reference the consolidated register in `## Acceptance Outline`.

### FR-007-01: Kernel Data Contracts and Error Model

- **Description**: Define `MicroPhaseKernel` (TypedDict, additive-only), `KernelContext`, `PhaseSideEffects`, `KernelOutcome` (frozen dataclasses), and `KernelError(token, detail)` inside `src/deviate/cli/micro.py`. No new module.
- **Constitutional basis**: §2 (Python 3.13, Typer/Rich stack); §1 Append-Only Ledger Protocol (no persistence-shape change).
- **Preconditions**: `src/deviate/cli/micro.py` builds and imports cleanly before the change.
- **Inputs/Outputs**: Inputs — repo root, console, session, session path, ledger path, task id, mode (`auto` | `manual`). Outputs — in-memory contract dict and outcome objects; nothing new is persisted.
- **State Transition**: None directly; the types parameterize the transitions of `FR-007-02` … `FR-007-06`.
- **Exception Strategy**: `KernelError` is the single domain error type; the CLI maps it to `typer.Exit(code=1)`; the auto runner catches it per phase step (design K4).
- **Source Anchors**: `specs/007-shared-phase-kernel/data-model.md` `## Schema Tables` (verbatim dataclass block quoted in `### Data Models & Invariants`); `specs/007-shared-phase-kernel/design.md` `[Module_Surface]` "Add (inside `src/deviate/cli/micro.py`, no new module)".
- **Acceptance Outline**:
  1. `AC-007-01-01` / `AO-001`: every kernel returns a `KernelOutcome` whose `status_token` is one of the fixed Rich tokens; the CLI prints the token verbatim (`RED_POST_OK` observed on a successful manual `red post`).
  2. `AC-007-01-02` / `AO-002`: a kernel domain failure raises `KernelError` with `token` and `detail`; the manual CLI exits with code 1 and prints the token; the auto runner catches the error and keeps the cycle alive.

### FR-007-02: RED Pre-Contract Kernel

- **Description**: `_red_pre_kernel` builds the `MicroPhaseKernel` contract — `task_id`, `test_command` (via `_resolve_verification_command`), `lint_command: "mise run lint"`, `spec_dir`, `task_entry` (via `_task_card_text`) — plus `_attach_mise_pre` doctor fields. `red_pre` prints it as JSON; `_run_red_phase` consumes it in-process.
- **Constitutional basis**: §1 Micro-Layer Scope (no write-scope change); §2 (stdlib `json` contract emission).
- **Preconditions**: A pending task record resolves for the epic (manual: `_resolve_task_context`; auto: in-process task dict).
- **Inputs/Outputs**: Inputs — root, resolved task data. Outputs — `KernelOutcome(emit_contract=True, contract=MicroPhaseKernel)` for the manual surface; the same contract dict in-process for auto.
- **State Transition**: None (contract assembly only); the machine stays PENDING until RED side effects apply.
- **Exception Strategy**: Task resolution failures keep the current surface behavior; doctor failures surface via the existing `_fail_pre_if_doctor_failed` flow.
- **Source Anchors**: `specs/007-shared-phase-kernel/explore.md` `## Architectural Baselines` (contract dict verbatim, quoted in `### Data Models & Invariants`); `specs/007-shared-phase-kernel/data-model.md` `## Data Flow` step 1.
- **Acceptance Outline**:
  1. `AC-007-02-01` / `AO-003`: `deviate red pre` prints the contract JSON with the five keys and the mise doctor fields; key names and value semantics match the current output (additive-only, `INV-1`).
  2. `AC-007-02-02` / `AO-004`: for the same task, the auto RED path builds a contract equal to the manual `red pre` output on the shared keys — no field divergence between surfaces.

### FR-007-03: RED Post Side-Effect Kernel with Unified Adjudication

- **Description**: `_red_post_kernel` runs `_run_test_cmd` (plus `_run_format_cmd` on the manual surface), applies the RED no-failing-test adjudication routes (exit 0 / pytest exit 5 / command-not-found exit 127, unified from `_adjudicate_red_no_failing_test` per design K5 and `HITL-002`), appends the RED ledger row, forces the session transition to RED, saves the session, runs `_commit_phase` with the literal `test({scope}): RED phase - failing test` (`no_verify=True`, `phase="red"`), and persists `session.red_commit_sha`. Called by `red_post` and `_run_red_phase`.
- **Constitutional basis**: §1 Append-Only Ledger Protocol (`INV-3`); §1 Session Continuity (no agent invocation); §4 commit convention.
- **Preconditions**: Task record resolves; session is loadable; working tree is clean per git isolation.
- **Inputs/Outputs**: Inputs — `KernelContext` with resolved task id. Outputs — `PhaseSideEffects(test_result, ledger_appended=True, session_status="RED", commit_sha)`; `KernelOutcome(status_token="RED_POST_OK")` on success.
- **State Transition**: PENDING → RED, exactly one `append_task_transition` row, one `session.force_transition_to("RED")` + `save`, one phase commit.
- **Exception Strategy**: No-failing-test routes adjudicate (not fail) per the unified `_adjudicate_red_no_failing_test` behavior; ledger or session failures raise `KernelError("LEDGER_UPDATE_FAILED", detail)`; missing test command raises `KernelError("TEST_NOT_FOUND", detail)`. Ordering preserves the current code path: abort before any partial side effect persists where the existing code guarantees ordering.
- **Source Anchors**: `specs/007-shared-phase-kernel/explore.md` `## Data & State Management` (side-effect chain verbatim, quoted in `### Data Models & Invariants`); `specs/007-shared-phase-kernel/design.md` trade-off `K5`; `specs/007-shared-phase-kernel/design.md` `## Pending HITL Decisions` `HITL-002` (RESOLVED).
- **Acceptance Outline**:
  1. `AC-007-03-01` / `AO-005`: manual `deviate red post` and the auto RED phase produce identical observable side effects — one RED ledger row, session status RED, the same commit message literal, persisted `red_commit_sha` — and the manual command prints `RED_POST_OK`.
  2. `AC-007-03-02` / `AO-006`: the no-failing-test routes (pytest exit 5, exit 0, command-not-found exit 127) adjudicate identically on both surfaces; `red post` exit codes match the unified routes; `CHANGELOG.md` gains a `[Unreleased]` bullet for the manual behavior change.

### FR-007-04: GREEN Post Side-Effect Kernel

- **Description**: `_green_post_kernel` applies the GREEN side effects with the current `_run_green_phase` and `green_post` semantics preserved verbatim: verification run per the existing guard ("GREEN must pass all tests", constitution §3), GREEN ledger row, session transition to GREEN, save, phase commit with the current message literal, sha persist. Called by `green_post` and `_run_green_phase`.
- **Constitutional basis**: §3 Coverage ("GREEN phase must pass all tests"); §1 Append-Only Ledger Protocol; §1 Micro-Layer Scope (no write-scope change — status computation passes through as-is per design trade-off K-scope note).
- **Preconditions**: RED side effects applied; task record in GREEN-eligible state per the current resolution rules.
- **Inputs/Outputs**: Inputs — `KernelContext` with resolved task id. Outputs — `PhaseSideEffects(ledger_appended=True, session_status="GREEN", commit_sha)`; `KernelOutcome(status_token="GREEN_POST_OK")`.
- **State Transition**: RED → GREEN, one ledger row, one session transition, one phase commit.
- **Exception Strategy**: Verification failure keeps the current green failure tokens and exit codes; ledger/session failures raise `KernelError("LEDGER_UPDATE_FAILED", detail)`. No GREEN status-semantics change in this feature.
- **Source Anchors**: `specs/007-shared-phase-kernel/explore.md` `## Architectural Baselines` (green_post side-effect list); `specs/007-shared-phase-kernel/data-model.md` `## State Transitions` row GREEN → JUDGE; `specs/007-shared-phase-kernel/design.md` "Contrarian Viewpoints" (status computation passes through unchanged).
- **Acceptance Outline**:
  1. `AC-007-04-01` / `AO-007`: manual `deviate green post` and the auto GREEN phase produce identical side effects (ledger row, session GREEN, commit literal, sha) and the manual command prints `GREEN_POST_OK`.
  2. `AC-007-04-02` / `AO-008`: when the GREEN verification guard fails, the kernel surfaces the same error token and exit code as the current `green_post` and persists no partial side effect beyond the current ordering guarantee.

### FR-007-05: REFACTOR Pre-Contract Kernel

- **Description**: `_refactor_pre_kernel` builds the larger refactor contract — `status: READY`, `task_title`, `task_type`, `verification`, `repo_root`, `git_branch`, `timestamp`, `files_to_refactor` — plus `_attach_mise_pre` doctor fields. `refactor_pre` prints it as JSON; `_run_refactor_phase` consumes it in-process.
- **Constitutional basis**: §2 (stdlib `json`, `datetime`); §1 (no state-shape change).
- **Preconditions**: A COMPLETED-or-refactor-eligible task resolves per the current `refactor_pre` resolution rules.
- **Inputs/Outputs**: Inputs — root, resolved task data, git branch. Outputs — `KernelOutcome(emit_contract=True, contract=...)` for the manual surface; the same contract in-process for auto.
- **State Transition**: None (contract assembly only).
- **Exception Strategy**: Task resolution and doctor failures keep the current surface behavior.
- **Source Anchors**: `specs/007-shared-phase-kernel/explore.md` `## Architectural Baselines` ("`refactor_pre` emits a larger contract (`status: READY`, `task_title`, `task_type`, `verification`, `repo_root`, `git_branch`, `timestamp`, `files_to_refactor`)"); `specs/007-shared-phase-kernel/data-model.md` `## Entity Definitions` row `MicroPhaseKernel`.
- **Acceptance Outline**:
  1. `AC-007-05-01` / `AO-009`: `deviate refactor pre` prints contract JSON containing all eight listed fields plus doctor fields; existing key names and value semantics are unchanged (`INV-1`).
  2. `AC-007-05-02` / `AO-010`: the auto refactor path builds the same contract in-process; shared keys match the manual output for the same task.

### FR-007-06: REFACTOR Post Side-Effect Kernel

- **Description**: `_refactor_post_kernel` runs the `_run_pytest` regression gate (constitution §3: tests must re-pass after polish), applies the existing format-command step, appends the COMPLETED ledger row, forces the session transition, saves, and runs the phase commit with the current message literal. Called by `refactor_post` and `_run_refactor_phase`.
- **Constitutional basis**: §3 Coverage ("REFACTOR phase runs regression gate: tests must re-pass after polish"); §1 Append-Only Ledger Protocol.
- **Preconditions**: JUDGE verdict COMPLETED per the state machine; session loadable.
- **Inputs/Outputs**: Inputs — `KernelContext` with resolved task id. Outputs — `PhaseSideEffects(test_result, ledger_appended=True, session_status="COMPLETED", commit_sha)`; `KernelOutcome(status_token="REFACTOR_POST_OK")`.
- **State Transition**: JUDGE/COMPLETED → COMPLETED (terminal per data-model `## State Transitions`), one ledger row, one session transition, one phase commit.
- **Exception Strategy**: Regression-gate failure keeps the current `refactor_post` exit codes and diagnostics; ledger/session failures raise `KernelError("LEDGER_UPDATE_FAILED", detail)`.
- **Source Anchors**: `specs/007-shared-phase-kernel/explore.md` `## Architectural Baselines` ("`refactor_post:7114` invokes `_run_pytest`"); `specs/007-shared-phase-kernel/data-model.md` `## State Transitions` terminal row.
- **Acceptance Outline**:
  1. `AC-007-06-01` / `AO-011`: manual `deviate refactor post` and the auto refactor phase produce identical side effects (regression run, ledger row, session transition, commit literal) and the manual command prints `REFACTOR_POST_OK`.
  2. `AC-007-06-02` / `AO-012`: when the regression gate fails, the kernel exits with the current `refactor_post` failure code and appends no COMPLETED ledger row.

### FR-007-07: Manual CLI Thin-Wrapper Conversion

- **Description**: Convert `red_pre`, `red_post`, `green_pre`, `green_post`, `judge_pre`, `judge_post`, `refactor_pre`, `refactor_post` to thin wrappers: parse args, resolve the task id at the surface (`_resolve_task_context`, `_resolve_first_pending` + `--task-id`, `_resolve_judge_post_task`), call the one kernel or the converged `_apply_judge_verdict` seam, print the status token or contract JSON, and map `KernelError` to `typer.Exit(code=1)`. `green_pre` and `judge_pre` keep their current no-contract behavior (`INV-4`).
- **Constitutional basis**: §2 (Typer CLI entry points); design K6 (task resolution stays surface-level).
- **Preconditions**: `FR-007-01` … `FR-007-06` kernels exist with stable outcomes.
- **Inputs/Outputs**: Inputs — Typer arguments/options as today (including `--task-id`). Outputs — identical stdout tokens, contract JSON, and exit codes as the current commands.
- **State Transition**: Delegated entirely to the kernels; the wrapper performs no ledger, session, or git writes.
- **Exception Strategy**: `KernelError` → print token + detail, `typer.Exit(code=1)`; argument and resolution errors keep current behavior.
- **Source Anchors**: `specs/007-shared-phase-kernel/design.md` `[Module_Surface]` "Modify (existing) … become thin wrappers: parse args, resolve task id, call a kernel, print status token or contract JSON, map `KernelError` to `typer.Exit`"; `specs/007-shared-phase-kernel/explore.md` File Registry rows for the eight commands.
- **Acceptance Outline**:
  1. `AC-007-07-01` / `AO-013`: each of the eight commands dispatches to exactly one kernel call (or `_apply_judge_verdict`) and performs no inline side-effect code; command stdout tokens and contract JSON match the pre-change outputs.
  2. `AC-007-07-02` / `AO-014`: `green_pre` and `judge_pre` print no contract JSON (`emit_contract=False` path), and their stdout/exit-code behavior is byte-identical to the pre-change commands.

### FR-007-08: Auto-Orchestrator Delegation with Session Continuity

- **Description**: `_run_red_phase`, `_run_green_phase`, and `_run_refactor_phase` keep their orchestration (prompt build, agent invocation, monitoring) and delegate each phase step to the kernels. Kernels never invoke agents. JUDGE keeps `_apply_judge_verdict` unchanged.
- **Constitutional basis**: §1 Session Continuity (single LLM session per task loop; no model switching); §1 Config-Driven Model Routing (`resolve_model_for_phase` per `[models]`); §1 Micro-Layer Scope.
- **Preconditions**: Kernels from `FR-007-02` … `FR-007-06` exist; `KernelContext` supports `mode="auto"`.
- **Inputs/Outputs**: Inputs — task dict, ledger path, session, session path, console, backend, monitor. Outputs — the same per-phase results as today: prompt, agent invocation, test outcomes, ledger rows, commits, session transitions.
- **State Transition**: Unchanged machine (PENDING → RED → GREEN → JUDGE → COMPLETED with JUDGE rework branch to RED).
- **Exception Strategy**: The auto runner catches `KernelError` per phase step to keep the cycle driver alive (design K4); agent invocation errors keep current handling.
- **Source Anchors**: `specs/007-shared-phase-kernel/design.md` `[Module_Surface]` ("keep their orchestration (prompt build, agent invocation, monitoring); delegate each phase step to the kernels"); `specs/007-shared-phase-kernel/explore.md` `## External Integrations` (`_invoke_agent` with `resolve_model_for_phase`).
- **Acceptance Outline**:
  1. `AC-007-08-01` / `AO-015`: an auto task cycle produces the same phase commits, ledger rows, and session transitions as before the change (behavior-preserving delegation).
  2. `AC-007-08-02` / `AO-016`: each auto phase invokes the agent exactly once via `_invoke_agent` with the model resolved per `[models]` routing; no kernel call path reaches `_invoke_agent`.

### FR-007-09: Interface Compatibility and Drift-Prevention Guarantees

- **Description**: The extraction keeps the installed interface stable: fixed status tokens (`RED_POST_OK`, `GREEN_POST_OK`, `JUDGE_POST_OK route=...`, `REFACTOR_POST_OK`, `TEST_NOT_FOUND`, `LEDGER_UPDATE_FAILED`), verbatim `_commit_phase` message literals and flags, and additive-only contract JSON. Prompt retry contracts in `src/deviate/prompts/auto/*.md` keep working against both surfaces.
- **Constitutional basis**: §4 commit convention; §5 Definition of Done (CHANGELOG under `[Unreleased]` for the manual RED adjudication change); design RSK-001/RSK-002/RSK-005.
- **Preconditions**: `FR-007-01` … `FR-007-08` implemented.
- **Inputs/Outputs**: Inputs — kernel outcomes. Outputs — unchanged tokens, literals, and contract keys consumed by prompts, tests, and external agents.
- **State Transition**: None (compatibility invariants over all transitions).
- **Exception Strategy**: Any drift is a test failure; regression tests assert each token on both surfaces (RSK-001) and the contract key set (RSK-005).
- **Source Anchors**: `specs/007-shared-phase-kernel/design.md` `## Risk Register` `RSK-001`, `RSK-002`, `RSK-005`; `specs/007-shared-phase-kernel/explore.md` `## Quality, Safety & Observability` (fixed token list); `tests/unit/test_meso/test_prompt_assembly.py` retry-contract coupling.
- **Acceptance Outline**:
  1. `AC-007-09-01` / `AO-017`: regression tests assert each fixed status token on both the auto and manual surfaces, and the prompt retry contracts still reference tokens that exist in the code.
  2. `AC-007-09-02` / `AO-018`: a contract-JSON regression test proves existing `MicroPhaseKernel` keys keep names and value semantics across both surfaces, and per-phase commit tests compare full commit message literals before and after the change.

## Non-Functional Engineering Requirements

| ID | Requirement | Source |
| :--- | :--- | :--- |
| NFR-01 | Kernel tests that reach `_run_pytest` mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture; the full suite stays under 30 seconds. | AGENTS.md "Test Performance"; design RSK-003 |
| NFR-02 | Kernel tests reuse `tests/conftest.py` `_git_env` + `tmp_git_repo`; every git call sets `cwd=<tmp_git_repo>`. | AGENTS.md "Git Isolation"; design RSK-006 |
| NFR-03 | `ruff check .` passes with no violations; `pytest tests/ -v` exits 0. | Constitution §3 |
| NFR-04 | Coverage stays at or above 80%. | Constitution §3 |
| NFR-05 | No new runtime dependencies; `pyproject.toml` keeps `typer>=0.12`, `rich>=13.0`, `pydantic>=2.0`, `pyyaml>=6.0.3`. | Constitution §2; explore Verified Dependencies |
| NFR-06 | No new modules; all kernels live in `src/deviate/cli/micro.py`. | Design Option A / trade-off K1 |
| NFR-07 | `CHANGELOG.md` gains an `[Unreleased]` bullet for the manual RED no-failing-test adjudication behavior change. | Constitution §5; `HITL-002` |
| NFR-08 | The module graph stays acyclic: kernels never call surface orchestrators; surface orchestrators and CLI commands call kernels only. | Data-model Relationship Graph rules |

## Acceptance Outline

Consolidated register. Every AO is observable, traced to one AC token and one FR, and free of implementation-level scenario clauses. Final Gherkin belongs to `plan.md` (constitution §1: Plan owns the Acceptance Contract).

| AO | AC Token | FR | Observable Outcome (happy path) |
| :--- | :--- | :--- | :--- |
| `AO-001` | `AC-007-01-01` | `FR-007-01` | Kernel returns `KernelOutcome`; CLI prints the fixed status token verbatim. |
| `AO-002` | `AC-007-01-02` | `FR-007-01` | `KernelError(token, detail)` maps to exit code 1 on manual; auto catches per step. |
| `AO-003` | `AC-007-02-01` | `FR-007-02` | `deviate red pre` prints the five-key contract JSON plus mise doctor fields, additive-only. |
| `AO-004` | `AC-007-02-02` | `FR-007-02` | Auto RED builds the same contract in-process; shared keys match the manual output. |
| `AO-005` | `AC-007-03-01` | `FR-007-03` | Both RED surfaces produce identical side effects; manual prints `RED_POST_OK`. |
| `AO-006` | `AC-007-03-02` | `FR-007-03` | No-failing-test routes adjudicate identically on both surfaces; CHANGELOG bullet added. |
| `AO-007` | `AC-007-04-01` | `FR-007-04` | Both GREEN surfaces produce identical side effects; manual prints `GREEN_POST_OK`. |
| `AO-008` | `AC-007-04-02` | `FR-007-04` | GREEN guard failure keeps current tokens/exit codes; no partial side effect. |
| `AO-009` | `AC-007-05-01` | `FR-007-05` | `deviate refactor pre` prints the eight-field contract JSON plus doctor fields. |
| `AO-010` | `AC-007-05-02` | `FR-007-05` | Auto refactor builds the same contract in-process; shared keys match. |
| `AO-011` | `AC-007-06-01` | `FR-007-06` | Both refactor surfaces produce identical side effects; manual prints `REFACTOR_POST_OK`. |
| `AO-012` | `AC-007-06-02` | `FR-007-06` | Regression-gate failure exits with the current code; no COMPLETED ledger row. |
| `AO-013` | `AC-007-07-01` | `FR-007-07` | Each of the eight commands wraps exactly one kernel call; outputs match pre-change. |
| `AO-014` | `AC-007-07-02` | `FR-007-07` | `green_pre` and `judge_pre` emit no contract; stdout/exit codes byte-identical. |
| `AO-015` | `AC-007-08-01` | `FR-007-08` | Auto cycle yields the same commits, ledger rows, and session transitions as before. |
| `AO-016` | `AC-007-08-02` | `FR-007-08` | One `_invoke_agent` call per auto phase; no kernel reaches `_invoke_agent`. |
| `AO-017` | `AC-007-09-01` | `FR-007-09` | Status-token regression tests pass on both surfaces; prompt retry contracts hold. |
| `AO-018` | `AC-007-09-02` | `FR-007-09` | Contract keys and commit literals verified unchanged by regression tests. |

## Issue Sharding Strategy

- **Recommended shard**: one issue, `007-001` (per-epic id format per constitution §1), inside epic `007-shared-phase-kernel`.
- **Rationale**: the change is one cohesive, behavior-preserving refactor inside `src/deviate/cli/micro.py` plus tests. Splitting kernels from CLI conversion would create an intermediate state where kernels exist but no caller uses them (dead code between commits).
- **Task shape**: micro tasks map to `FR-007-01` … `FR-007-09`; each task references its AC tokens; RED encodes the observable surface contracts (status tokens, contract JSON, exit codes, ledger/session/commit side effects) as failing tests per constitution §1 "User Scenarios Are the Flow".
- **Dependency topology**: `FR-007-01` → `FR-007-02`/`FR-007-03`/`FR-007-04`/`FR-007-05`/`FR-007-06` → `FR-007-07`/`FR-007-08` → `FR-007-09`. All dependencies resolve inside the single issue.
- **Traceability**: the shard issue carries `FR-007-*` tokens from this PRD; `plan.md` finalizes the Gherkin Acceptance Contract against `AO-001` … `AO-018`.

## Ambiguity Resolution and Stakeholder Decisions

### [DECISION_READINESS]

READY. `specs/007-shared-phase-kernel/design.md` `## Pending HITL Decisions` holds zero `PENDING` rows (`HITL-001`, `HITL-002` both RESOLVED). No unresolved architectural parameter blocks PRD generation.

### [CLARIFICATION_LOG]

| ID | Decision | Resolution | Impact on this PRD |
| :--- | :--- | :--- | :--- |
| `HITL-001` | Should the macro `_cycle_phase` driver share the micro kernel seam? | RESOLVED — excluded. `_cycle_phase` dispatches only `explore|research|prd|shard` and shares no code with the four micro phases. | No FR covers `src/deviate/cli/macro.py`. |
| `HITL-002` | Unify the manual RED no-failing-test adjudication into the kernel? | RESOLVED — unified into `_red_post_kernel`; user-visible; CHANGELOG bullet required. | `FR-007-03` (`AO-006`), `NFR-07`. |
| `CLR-003` | Prompt-embedded constitution snapshot (v0.9.0) mentions a Product layer and `flow_refs`; the authoritative `specs/constitution.md` is v0.10.0 with no Product layer. | Follow the authoritative local constitution v0.10.0. | No `FLOW-XX` tags; scope excludes flow artifacts. |

## Session State

| Field | Value |
| :--- | :--- |
| repo_root | `.` |
| git_branch | `main` |
| phase | `PRD` |
| epic_slug | `007-shared-phase-kernel` |
| feature_bucket | `007-shared-phase-kernel` |
| explore_md_path | `specs/007-shared-phase-kernel/explore.md` |
| design_path | `specs/007-shared-phase-kernel/design.md` |
| data_model_path | `specs/007-shared-phase-kernel/data-model.md` |
| prd_path | `specs/007-shared-phase-kernel/prd.md` |
| plan_target | `.deviate/artifacts/manifest_prd.json` |
| issue_id | (empty — sharding allocates `007-001`) |
| FR tokens | `FR-007-01` … `FR-007-09` |
| AC tokens | `AC-007-01-01` … `AC-007-09-02` |
| AO tokens | `AO-001` … `AO-018` |
