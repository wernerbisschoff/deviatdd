# Shared Phase Kernel (Auto Runner ⇄ Manual Pre/Post) — Data Model

Feature: `007-shared-phase-kernel` · Constitution: `specs/constitution.md` v0.10.0 · Source: `specs/007-shared-phase-kernel/explore.md`

## Entity Definitions

| Entity | Attributes (typed) | Invariants | Source of Truth | Lifecycle Owner | Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `MicroPhaseKernel` | `task_id: str`, `test_command: str`, `lint_command: str = "mise run lint"`, `spec_dir: str`, `task_entry: str`, `doctor: dict[str, str]` | Keys are additive-only; existing keys keep names and value semantics; serialized via `json.dumps(..., ensure_ascii=False)` | Built by `_red_pre_kernel` / `_refactor_pre_kernel`; printed verbatim by the CLI pre commands | `src/deviate/cli/micro.py` (kernel) | explore baseline snippet: `contract = {"task_id": ..., "test_command": _resolve_verification_command(root, task_data), "lint_command": "mise run lint", "spec_dir": spec_dir, "task_entry": _task_card_text(root, task_data)}` |
| `KernelContext` | `root: Path`, `console: Console`, `session: SessionState`, `session_path: Path`, `ledger_path: Path`, `task_id: str`, `mode: Literal["auto", "manual"]` | Immutable per kernel call; `mode` never alters side-effect semantics, only adjudication routes and error presentation | Assembled by each surface orchestrator at entry | `src/deviate/cli/micro.py` | explore baseline: `_run_red_phase(task, ledger_path, session, session_path, c, agent, monitor)` signature |
| `PhaseSideEffects` | `test_result: subprocess.CompletedProcess | None`, `ledger_appended: bool`, `session_status: str`, `commit_sha: str | None` | Produced only by post kernels; `ledger_appended` true implies exactly one `append_task_transition` row | Derived from `_run_test_cmd`, `append_task_transition`, `session.save`, `_commit_phase` | `src/deviate/cli/micro.py` (post kernels) | explore baseline: `record.status = "RED"` → `append_task_transition(record, ledger_path)` → `session.force_transition_to("RED")` → `_commit_phase(...)` → `session.red_commit_sha` |
| `KernelOutcome` | `status_token: str`, `contract: MicroPhaseKernel | None`, `emit_contract: bool`, `task_id: str` | `emit_contract` true iff the phase prints contract JSON (`red pre`, `refactor pre`); `status_token` values are the fixed Rich tokens the prompt retry contracts reference | Returned by every kernel; consumed by CLI printers and auto orchestrator | `src/deviate/cli/micro.py` | explore baseline: fixed tokens `TEST_NOT_FOUND`, `RED_POST_OK`, `GREEN_POST_OK`, `JUDGE_POST_OK`, `REFACTOR_POST_OK` |
| `KernelError` | `token: str` (e.g. `TEST_NOT_FOUND`, `LEDGER_UPDATE_FAILED`), `detail: str` | No message mutation of commit literals; CLI maps to `typer.Exit(code=1)`; auto catches per phase step to keep the cycle driver alive | Raised by kernels on domain failure | `src/deviate/cli/micro.py` | explore baseline snippet: `console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")` → `raise typer.Exit(code=1)` |
| `TaskRecord` (existing, unchanged) | Pydantic model with `status` transitions `RED | GREEN | JUDGE | COMPLETED` | Append-only rows; no line ever modified | `tasks.jsonl` via `TaskRecord.model_validate` → `append_task_transition` | `src/deviate/state/` ledgers | explore Verified Dependencies: "`TaskRecord.model_validate` drives ledger transitions in both `_run_red_phase` and `red_post`" |
| `SessionState` (existing, unchanged) | JSON under `.deviate/session.json`; `red_commit_sha` and per-phase transition fields | One transition per phase; `session.save(session_path)` persists after each kernel side effect | `.deviate/session.json` | `src/deviate/state/` session module | explore Data & State Management: "`session.red_commit_sha` is persisted after `git rev-parse HEAD`" |

## Relationship Graph

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

Kernel ─► append_task_transition ─► tasks.jsonl   (append-only)
Kernel ─► SessionState.force_transition_to ─► session.save ─► .deviate/session.json
Kernel ─► _commit_phase ─► git commit (phase boundary, task-scoped message)
```

- Auto surface → kernels: navigates surface → kernel only; kernels never call orchestrators (acyclic).
- Kernels → state writers: cardinality 1 per side effect per phase; no cascade (each writer is independent).
- CLI commands → kernels: one command wraps exactly one kernel call; task resolution helpers feed `task_id` into `KernelContext` (K6).

## Schema Tables

Typed shapes for the two new data contracts (Python 3.13 / Pydantic v2 conventions per constitution §2). Persistence shapes (`tasks.jsonl`, `.deviate/session.json`) are unchanged — no new persistence.

```python
# Pre-contract (versioned wire interface; printed by red pre / refactor pre)
class MicroPhaseKernel(TypedDict, total=False):
    task_id: str
    test_command: str
    lint_command: str          # default "mise run lint"
    spec_dir: str
    task_entry: str
    doctor: dict[str, str]     # _attach_mise_pre fields (mise pre doctor)

# Kernel inputs / outputs (in-memory; not persisted)
@dataclass(frozen=True)
class KernelContext:
    root: Path
    console: Console
    session: SessionState
    session_path: Path
    ledger_path: Path
    task_id: str
    mode: Literal["auto", "manual"]

@dataclass(frozen=True)
class PhaseSideEffects:
    test_result: subprocess.CompletedProcess | None
    ledger_appended: bool
    session_status: str
    commit_sha: str | None

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

Persisted-shape anchors (verbatim, unchanged): ledger row write `record.status = "RED"` + `append_task_transition(record, ledger_path)`; session persist `session = session.force_transition_to("RED")` + `session.save(session_path)`; commit `_commit_phase(f"test({scope}): RED phase - failing test", root, no_verify=True, phase="red")`.

## State Transitions

Machine: micro task phase progression (unchanged by this feature; kernels apply the same transitions).

| From | Event | Guard | To | Side Effects | Terminal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| PENDING | `red pre` / RED start | pending record resolves (`--task-id` match or first-pending) | RED | contract JSON printed (manual); `_log_run("PHASE_START", phase="RED")` (auto) | No |
| RED | `red post` / GREEN start | RED side effects applied; failing test verified (or adjudicated: exit 0 / pytest exit 5 / command-not-found 127) | GREEN | `_run_test_cmd` (+ `_run_format_cmd` manual), ledger row, `session.force_transition_to("RED")`, `_commit_phase`, `session.red_commit_sha` | No |
| GREEN | `green post` / JUDGE start | GREEN side effects applied; all tests pass (§3: GREEN must pass all tests) | JUDGE | ledger row, session transition, `_commit_phase`, sha persist | No |
| JUDGE | `judge post` / verdict | handover manifest parses (`AgentBackend.parse_output(yaml_text, "cli")`); scope verification passes | COMPLETED (pass) \| RED (rework) | `_apply_judge_verdict` applies manifest, ledger row, commit | No |
| COMPLETED | `refactor post` | regression gate: tests re-pass after polish (§3) | COMPLETED | `_run_pytest` via `refactor_post:7114`, ledger row, `_commit_phase` | Yes |

Kernel rules: one `append_task_transition` row per transition (append-only, no overwrite — constitution §1). `KernelError` aborts the step before any partial side effect is persisted where the existing code path already guarantees ordering; kernel extraction preserves that ordering verbatim.

## Data Flow

1. **Manual pre (red/refactor)**: Typer command → `_resolve_task_context` → task id → `_red_pre_kernel` builds `MicroPhaseKernel` (+ `_attach_mise_pre` doctor) → `KernelOutcome(emit_contract=True)` → CLI prints `json.dumps(contract, ensure_ascii=False)` → external agent consumes the contract.
2. **Auto RED**: `_run_red_phase` → `_red_pre_kernel` (in-process contract) → `_build_auto_prompt("red", ...)` → `_invoke_agent(..., model=red_model)` → `_red_post_kernel` (`_run_test_cmd`, adjudication, ledger, session, commit) → `KernelOutcome` → monitor callback.
3. **Manual post (red/green/refactor)**: Typer command → task resolution (`--task-id` / first-pending) → post kernel runs `_run_test_cmd` (+ `_run_format_cmd`) → `append_task_transition` → `session.force_transition_to(...)` + `save` → `_commit_phase` → `KernelOutcome.status_token` → CLI prints (`RED_POST_OK` / `GREEN_POST_OK` / `REFACTOR_POST_OK`).
4. **JUDGE (both surfaces)**: `_run_judge_phase` and `judge_post` → `_apply_judge_verdict(task, ledger_path, session, session_path, c, manifest, injected_diff=...)` — the existing converged seam; this feature changes no JUDGE data flow.
5. **Ledger/session writes**: every post kernel terminates in `append_task_transition` (append-only `tasks.jsonl`) and `session.save(session_path)` (`.deviate/session.json`) — shapes unchanged.

## Source Registry

| ID | Type | Source / Path | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Explore_MD | `specs/007-shared-phase-kernel/explore.md` | Factual baseline for all entities, transitions, and flows above |
| SRC-002 | Constitution | `specs/constitution.md` | §1 append-only ledger + session state shapes; §2 Pydantic/Typer stack |
| SRC-003 | Codebase_File | `src/deviate/cli/micro.py` | Kernel host; `_apply_judge_verdict:3410` template; `_run_pytest:5315`; `refactor_post:7114` |
| SRC-004 | Codebase_File | `src/deviate/state/` ledgers | `TaskRecord`, `append_task_transition`, `SessionState` (unchanged shapes) |
| SRC-005 | Codebase_File | `tests/unit/test_micro/test_red.py` | GH-154 AC-6 manual RED contract |
| SRC-006 | Codebase_File | `tests/unit/test_micro/test_judge.py` | Manual JUDGE verdict side-effect contract |
