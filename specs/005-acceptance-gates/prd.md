## Document Control and Metadata
- **Target Release Version**: v2.16.0
- **Upstream Reference**: `specs/005-acceptance-gates/explore.md`
- **Downstream Epic Tracker**: Epic `005-acceptance-gates` under `specs/issues.jsonl`
- **Status**: PROPOSED

## System Objectives and Scope Boundary
### Core Value Proposition
Make acceptance criteria explicit and enforce test gates per micro phase. GREEN and REFACTOR become blocking validation phases. RED becomes a non-blocking checkpoint. The feature reuses the existing `plan.md` `AC-PLAN-NNN` acceptance contract. It adds verification-mode metadata, `acceptance_criteria` task traceability, and a transient RED handoff advisory.

### In-Scope Boundaries (Hard Directives)
- Add `**Verification Mode**: <automated|manual|deferred>` metadata to each `AC-PLAN-NNN` scenario in `plan.md`, validated by `src/deviate/core/validation.py::validate_acceptance_contract`.
- Add an optional `acceptance_criteria: list[CriterionLink] | None` field to `TaskRecord` in `src/deviate/state/ledger.py` and propagate it through `src/deviate/core/tasks_ledger.py::generate_jsonl_from_md`.
- Replace the RED pass-rejection (`PhaseFailedError` on returncode 0 in `src/deviate/cli/micro.py::_run_red_phase`) with a non-blocking `RedHandoffAdvisory` carried in-memory to GREEN.
- Enforce the REFACTOR regression gate: `_run_refactor_phase` inspects `_run_test_cmd` returncode and raises `PhaseFailedError` on non-zero.
- Keep GREEN failure routing to JUDGE via `train_feedback` (no new retry mechanism).
- Update RED/GREEN/REFACTOR prompt templates under `src/deviate/prompts/commands/` and `src/deviate/prompts/auto/`.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit; append a `CHANGELOG.md` entry.

### Out-of-Scope Boundaries (Defensive Exclusions)
- A new `acceptance.md` slice artifact and any generation scaffolding for it (Option B, rejected).
- A new `TaskRecord.status` value or a new persistent checkpoint record in `.deviate/` or the task ledger.
- A standalone acceptance-runner module decoupled from the phase runners (Option D, rejected).
- Any new external integration, database runtime, or slice-level file format.

## Architectural Constraints and Prerequisites
### Data Models & Invariants
```python
class CriterionLink(BaseModel):
    criterion_id: str          # matches AC-PLAN-\d{3}
    verification_mode: Literal["automated", "manual", "deferred"]
    test_ref: str | None = None  # required when mode == "automated"

class TaskRecord(BaseModel):
    id: str
    issue_id: str
    description: str = Field(min_length=1)
    status: Literal["PENDING","RED","GREEN","JUDGE","REFACTOR","COMPLETED","FAILED"] = "PENDING"
    execution_mode: Literal["TDD","DIRECT","EXECUTE","E2E","IMMEDIATE"] = "TDD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    security_profile: SecurityProfile | None = None
    acceptance_criteria: list[CriterionLink] | None = None  # additive, optional, default None
    model_config = {"extra": "forbid"}

class RedHandoffAdvisory(BaseModel):  # transient; never serialized
    task_id: str
    phase: Literal["RED"] = "RED"
    passes: bool
    severity: Literal["ok", "warning"] = "ok"
```
Invariants (source: `specs/005-acceptance-gates/data-model.md`):
- `acceptance_criteria` is optional with default `None`, so mixed-version JSONL ledgers parse under `extra="forbid"`.
- Each `CriterionLink.criterion_id` references an `AC-PLAN-NNN` scenario id from the owning slice's `plan.md`.
- A link with `verification_mode == "automated"` carries a non-null `test_ref`.
- `RedHandoffAdvisory` is never written to `tasks.jsonl`, `.deviate/`, or any ledger.
- `verification_mode` gates only criterion status; it never exempts the executable test suite.

### Performance / Scalability Thresholds
- Full test suite stays under 30 seconds (project execution contract).
- CLI init stays at L_max ≤ 500ms; per-agent export ≤ 200ms.
- Tests that invoke CLI commands hitting `_run_pytest` must mock `deviate.cli.micro._run_pytest`.

### Security & Compliance Invariants
- Git isolation: all test git calls use `cwd=<tmp_git_repo>` + `env=_git_env()`; production uses `src/deviate/core/_shared.py::git_env`.
- Test commands run through the existing safe-command gate `_run_test_cmd`.
- Append-only ledger protocol: no existing JSONL line is modified or overwritten.

## Functional Flow and Sequence Architecture
### System Orchestration Mapping
```mermaid
sequenceDiagram
    participant P as plan post
    participant V as validation.py
    participant T as tasks_ledger.py
    participant R as _run_red_phase
    participant G as _run_green_phase
    participant J as JUDGE
    participant F as _run_refactor_phase

    P->>V: validate AC-PLAN-NNN + Verification Mode
    V-->>P: contract valid
    P->>T: tasks generation
    T->>T: propagate acceptance_criteria into TaskRecord
    R->>R: _run_test_cmd (non-blocking)
    R-->>G: RedHandoffAdvisory (ok | warning)
    G->>G: _run_test_cmd returncode 0?
    G->>J: on failure: train_feedback retry
    G->>F: on pass
    F->>F: _run_test_cmd returncode 0?
    F-->>F: non-zero → PhaseFailedError; zero → COMPLETED
```

## Functional Requirements and Epics

### FR-005-01: Acceptance Contract Verification-Mode Metadata
- **Description**: Each `AC-PLAN-NNN` scenario in a slice's `plan.md` `## Acceptance Contract` carries a `**Verification Mode**: <automated|manual|deferred>` line. `validate_acceptance_contract` in `src/deviate/core/validation.py` validates the mode value. Existing enforced clauses (Source Outline, Upstream Traceability, Current-Code Evidence, Given/When/Then) stay mandatory.
- **Preconditions**: A `plan.md` with at least one `AC-PLAN-NNN` scenario.
- **Inputs/Outputs**: Input: `plan.md` content. Output: validation errors list; empty when valid.
- **State Transition**: PLAN_DRAFTED ➔ CONTRACT_VALIDATED (mode present and legal) / CONTRACT_REJECTED (mode missing or illegal value).
- **Exception Strategy**: A scenario without a Verification Mode line, or with a value outside the three literals, produces a validation error. `deviate meso tasks pre` blocks on any error.
- **Acceptance Outline (Definition of Done)**:
  1. `AC-005-01-01` / `AO-001`: `validate_acceptance_contract` accepts a scenario with `**Verification Mode**: automated`.
     - **Happy Path**: `deviate plan post` and `deviate meso tasks pre` pass.
     - **Error Category**: Missing or illegal mode value blocks `tasks pre` with a named error.
     - **Boundary Category**: A `manual` or `deferred` mode validates but requires no `test_ref` in the contract body.
  2. `AC-005-01-02` / `AO-001`: Validation keeps requiring Source Outline, Upstream Traceability, Current-Code Evidence, and Given/When/Then.
     - **Observable Result**: Removing any existing clause still fails validation.
- **Downstream Shard Mapping**: Epic `005-acceptance-gates`, first issue.

### FR-005-02: Task Acceptance Traceability
- **Description**: `TaskRecord` gains an optional `acceptance_criteria: list[CriterionLink] | None` field. `generate_jsonl_from_md` in `src/deviate/core/tasks_ledger.py` propagates task-to-criterion and criterion-to-test links into each generated task row. The field parses as absent for JSONL rows written by older CLI versions.
- **Preconditions**: A validated `plan.md` acceptance contract and a `tasks.md` with per-task criterion references.
- **Inputs/Outputs**: Input: `tasks.md` + `AC-PLAN-NNN` contract. Output: `specs/**/tasks.jsonl` rows carrying `acceptance_criteria`.
- **State Transition**: TASKS_MD ➔ TASKS_JSONL_WITH_TRACEABILITY.
- **Exception Strategy**: An invalid `criterion_id` (not `AC-PLAN-\d{3}`) raises a validation error. `verification_mode == "automated"` with null `test_ref` raises a validation error. Absent field defaults to `None`; parse succeeds.
- **Acceptance Outline (Definition of Done)**:
  1. `AC-005-02-01` / `AO-002`: Generated task rows carry the `acceptance_criteria` links from `tasks.md`.
     - **Happy Path**: `deviate meso tasks pre` emits rows with valid links.
     - **Error Category**: Malformed criterion id or missing `test_ref` on an automated link fails generation.
     - **Boundary Category**: Legacy JSONL rows without the field still parse under `extra="forbid"`.
- **Downstream Shard Mapping**: Epic `005-acceptance-gates`, second issue.

### FR-005-03: Non-Blocking RED Checkpoint
- **Description**: `_run_red_phase` in `src/deviate/cli/micro.py` stops raising `PhaseFailedError` on test returncode 0. It builds a `RedHandoffAdvisory` (`passes`, `severity`) and passes it in-memory to the GREEN runner. The RED phase always completes and appends its `RED` transition row. No persistent record is written.
- **Preconditions**: An active task in `PENDING` or restart state; a test file detected by `_find_test_files`.
- **Inputs/Outputs**: Input: test suite returncode. Output: `RedHandoffAdvisory` consumed by GREEN; RED transition row appended; log warning on unexpected pass.
- **State Transition**: RED_RUNNING ➔ RED_COMPLETE (always; advisory severity `ok` or `warning`).
- **Exception Strategy**: An unexpected pass (`returncode == 0`) records a warning advisory and logs `RED_PASSED_WARNING`. A crash discards the advisory; RED restart re-derives it.
- **Acceptance Outline (Definition of Done)**:
  1. `AC-005-03-01` / `AO-003`: A RED run whose test suite passes completes the phase and emits a `warning` advisory.
     - **Happy Path**: Phase completes; no `PhaseFailedError`; advisory reaches GREEN.
     - **Error Category**: Test-infrastructure failure still surfaces as a phase error.
     - **Boundary Category**: No test file detected — the checkpoint is skipped.
  2. `AC-005-03-02` / `AO-003`: A RED run whose test suite fails completes with an `ok` advisory.
     - **Observable Result**: RED transition row appended; GREEN starts.
- **Downstream Shard Mapping**: Epic `005-acceptance-gates`, third issue.

### FR-005-04: Blocking GREEN Gate with JUDGE Routing
- **Description**: `_run_green_phase` requires `_run_test_cmd` returncode 0. On failure it sets `train_feedback` and routes to JUDGE, which decides retry GREEN or revert to RED, bounded by `_MAX_JUDGE_FEEDBACK = 3`. Verification mode never exempts the automated suite.
- **Preconditions**: RED complete; advisory consumed.
- **Inputs/Outputs**: Input: test suite result. Output: GREEN transition row on pass; JUDGE retry routing on failure.
- **State Transition**: RED_COMPLETE ➔ GREEN_PASSED / JUDGE_RETRY.
- **Exception Strategy**: Failure routes to JUDGE; no new retry threshold is introduced.
- **Acceptance Outline (Definition of Done)**:
  1. `AC-005-04-01` / `AO-004`: GREEN with returncode 0 appends the GREEN transition.
     - **Happy Path**: Format cmd runs; GREEN result commits.
     - **Error Category**: Non-zero returncode routes to JUDGE via `train_feedback`.
     - **Boundary Category**: A `warning` RED advisory does not block GREEN start.
- **Downstream Shard Mapping**: Epic `005-acceptance-gates`, fourth issue (may merge with FR-005-03).

### FR-005-05: Blocking REFACTOR Regression Gate
- **Description**: `_run_refactor_phase` inspects the `_run_test_cmd` returncode. Non-zero raises `PhaseFailedError` and the task fails. Zero proceeds to format cmd, appends the `COMPLETED` transition, commits, and transitions the session to `IDLE`.
- **Preconditions**: JUDGE passed; refactor agent run complete.
- **Inputs/Outputs**: Input: test suite returncode after polish. Output: `COMPLETED` row or `PhaseFailedError`.
- **State Transition**: REFACTOR_RUNNING ➔ COMPLETED / FAILED.
- **Exception Strategy**: Regression failure is terminal for the phase; no silent pass of an unchecked result.
- **Acceptance Outline (Definition of Done)**:
  1. `AC-005-05-01` / `AO-005`: A refactor run that breaks a test raises `PhaseFailedError`.
     - **Happy Path**: All tests pass after polish; `COMPLETED` row appended.
     - **Error Category**: Non-zero returncode raises and records failure.
     - **Boundary Category**: Tests unchanged and passing — gate passes without side effects.
- **Downstream Shard Mapping**: Epic `005-acceptance-gates`, fifth issue.

### FR-005-06: Prompt Template and Specification Alignment
- **Description**: Update `src/deviate/prompts/commands/deviate-red.md`, `src/deviate/prompts/auto/red.md`, `green.md`, and `refactor.md` to describe the checkpoint and gates. Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` gate semantics in the same commit. Append a `CHANGELOG.md` entry under `[Unreleased]`.
- **Preconditions**: FR-005-01 through FR-005-05 implemented.
- **Inputs/Outputs**: Input: implemented gate behavior. Output: aligned prompt templates, spec sections, and changelog entry.
- **State Transition**: IMPLEMENTED ➔ SPEC_ALIGNED.
- **Exception Strategy**: Spec drift between code and `specs/DeviaTDD-api.md` fails the Spec Alignment review.
- **Acceptance Outline (Definition of Done)**:
  1. `AC-005-06-01` / `AO-006`: The RED prompt states the phase completes on a passing test with a warning; it no longer states rejection.
     - **Happy Path**: Templates and specs match runner behavior.
     - **Error Category**: A stale rejection statement in any template fails review.
     - **Boundary Category**: CHANGELOG entry present under `[Unreleased]`.
- **Downstream Shard Mapping**: Epic `005-acceptance-gates`, final issue.

## Acceptance Outline
- `AO-001` / `AC-005-01-*`: Verification-mode metadata on `AC-PLAN-NNN` scenarios validates in `validate_acceptance_contract`.
- `AO-002` / `AC-005-02-*`: `acceptance_criteria` traceability links propagate from `tasks.md` into `TaskRecord` rows.
- `AO-003` / `AC-005-03-*`: RED completes with a non-blocking `RedHandoffAdvisory`; no `PhaseFailedError` on a passing test.
- `AO-004` / `AC-005-04-*`: GREEN blocks on test failure and routes to JUDGE via `train_feedback`.
- `AO-005` / `AC-005-05-*`: REFACTOR regression gate raises `PhaseFailedError` on non-zero returncode.
- `AO-006` / `AC-005-06-*`: Prompt templates, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` align with the gate behavior.

## Non-Functional Engineering Requirements
- **Observability & Telemetry**: Log an event (`RED_PASSED_WARNING`) when RED produces a passing test. Use the existing `RunLogger`/`TaskLogger`/`log_event` facilities in `src/deviate/core/run_logger.py`.
- **Reliability & Fallbacks**: GREEN failure keeps the existing JUDGE retry path with `_MAX_JUDGE_FEEDBACK = 3`. No new retry algorithm or backoff is introduced.
- **Type Safety & Modularity**: Pydantic models enforce the schemas above. `ruff check` and `ruff format --check` pass. Coverage stays at or above 80%. Tests mock `deviate.cli.micro._run_pytest` where CLI commands reach it.

## Issue Sharding Strategy
Shard the epic into 5-6 issues, one per FR: contract metadata (`FR-005-01`), task traceability (`FR-005-02`), RED checkpoint (`FR-005-03`), GREEN gate (`FR-005-04`), REFACTOR gate (`FR-005-05`), and template/spec alignment (`FR-005-06`). `FR-005-04` may merge with `FR-005-03` into one slice. Each issue keeps its own `plan.md` `AC-PLAN-NNN` acceptance contract with verification-mode metadata.

## Ambiguity Resolution and Stakeholder Decisions
- `RESOLVED-Q-001` (HITL-001): RED checkpoint storage ➔ **Resolution Requirement Invariant**: The checkpoint is an in-memory phase-handoff advisory; the system writes no persistent record, no ledger field, and no `.deviate/` store.
- `RESOLVED-Q-002` (HITL-002): GREEN/REFACTOR failure semantics ➔ **Resolution Requirement Invariant**: GREEN failure routes to JUDGE via `train_feedback`; JUDGE decides retry GREEN or revert to RED. REFACTOR regression failure raises `PhaseFailedError`. No new retry threshold exists.
- `RESOLVED-Q-003` (HITL-003): Verification-mode encoding ➔ **Resolution Requirement Invariant**: Each `AC-PLAN-NNN` scenario carries one `**Verification Mode**: <automated|manual|deferred>` line in its body.
- `RESOLVED-Q-004` (HITL-004): RED status representation ➔ **Resolution Requirement Invariant**: The `TaskRecord.status` Literal stays unchanged at seven values; the checkpoint never becomes a status or a persisted record.

### Decision Readiness
- [x] Requirements space clear of technical blindspots
- [x] Interface data type contracts completely defined
- [x] Constitutional exceptions isolated and closed
- **Blocking Decisions**: None. All four HITL decisions carry status `RESOLVED` in `specs/005-acceptance-gates/design.md`.

### Clarification Log
- `Q-001`: Where does the RED checkpoint live? — **Status**: RESOLVED — **Impact**: `src/deviate/cli/micro.py` RED/GREEN runners.
- `Q-002`: What happens on GREEN/REFACTOR test failure? — **Status**: RESOLVED — **Impact**: `src/deviate/cli/micro.py` GREEN, JUDGE, REFACTOR runners.
- `Q-003`: How is verification mode encoded? — **Status**: RESOLVED — **Impact**: `src/deviate/core/validation.py`, `plan.md` contract.
- `Q-004`: Does RED need a new status or record? — **Status**: RESOLVED — **Impact**: `src/deviate/state/ledger.py` `TaskRecord`.

## Session State
```json
{
  "current_focus": "PRD compiled for epic 005-acceptance-gates: verification-mode metadata, acceptance_criteria traceability, non-blocking RED advisory, blocking GREEN/REFACTOR gates",
  "resolved_questions": "Q-001, Q-002, Q-003, Q-004",
  "pending_unknowns": "none"
}
```

## Source Registry
ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note
--- | --- | --- | ---
`SRC-001` | Spec_Discovery | `specs/005-acceptance-gates/explore.md` | Option A decision; scope sizing; file registry.
`SRC-002` | Design | `specs/005-acceptance-gates/design.md` | Recommended architecture; options matrix; resolved HITL decisions.
`SRC-003` | Data_Model | `specs/005-acceptance-gates/data-model.md` | `CriterionLink`, `TaskRecord`, `RedHandoffAdvisory`, `AcceptanceContract` schemas.
`SRC-004` | Codebase_File | `src/deviate/cli/micro.py` | RED pass-rejection at line 1123; GREEN gate at 1298; REFACTOR unchecked call at 2500.
`SRC-005` | Codebase_File | `src/deviate/state/ledger.py` | `TaskRecord` model, `extra="forbid"`, status Literal.
`SRC-006` | Codebase_File | `src/deviate/core/validation.py` | `validate_acceptance_contract` enforces `AC-PLAN-NNN` structure.
`SRC-007` | Constitution | `specs/constitution.md` | §1 append-only; §3 GREEN/REFACTOR gate clauses; §5 DoD.
`SRC-008` | Manifest | `mise.toml` | `[tasks.test]` command wrapper divergence noted without adjudication.
