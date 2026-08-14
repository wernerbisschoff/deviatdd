# Data Model — Acceptance Criteria and Phase-Specific Test Gates

Epic `005-acceptance-gates` · Feature Slug `acceptance-gates` · Phase `RESEARCH`

## Entity Definitions

### TaskRecord
- **Source-of-truth**: `specs/**/tasks.jsonl` (append-only JSONL)
- **Lifecycle owner**: micro-layer phase runner (`src/deviate/cli/micro.py`) and meso task generator (`src/deviate/core/tasks_ledger.py`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `id` | `str` | matches `TSK-\d{3}-\d{2}` | `src/deviate/state/ledger.py:103` |
  | `issue_id` | `str` | non-empty | `src/deviate/state/ledger.py:83` |
  | `description` | `str` | `min_length=1` | `src/deviate/state/ledger.py:84` |
  | `status` | `Literal[...]` | one of `PENDING/RED/GREEN/JUDGE/REFACTOR/COMPLETED/FAILED` | `src/deviate/state/ledger.py:85-93` |
  | `execution_mode` | `Literal[...]` | one of `TDD/DIRECT/EXECUTE/E2E/IMMEDIATE`, default `TDD` | `src/deviate/state/ledger.py:94` |
  | `created_at` | `datetime` | UTC now default | `src/deviate/state/ledger.py:95` |
  | `security_profile` | `SecurityProfile \| None` | nullable | `src/deviate/state/ledger.py:97` |
  | `acceptance_criteria` | `list[CriterionLink] \| None` | additive, optional, default `None` | explore.md Scope Sizing |
- **Invariants**:
  - The record must always remain append-only. No existing line is modified (`specs/constitution.md` §1).
  - `acceptance_criteria` is optional so mixed-version ledgers parse under `extra="forbid"`.
  - Each `CriterionLink.criterion_id` references an `AC-PLAN-NNN` scenario id from the owning slice's `plan.md`.
  - Each `CriterionLink.test_ref` references a test path that exercises the criterion.
  - The RED checkpoint holds no persisted field on this record. It is an in-memory handoff advisory.

### CriterionLink
- **Source-of-truth**: embedded in `TaskRecord.acceptance_criteria` within `specs/**/tasks.jsonl`
- **Lifecycle owner**: meso task generator and micro GREEN/JUDGE validators
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `criterion_id` | `str` | matches `AC-PLAN-\d{3}` | `src/deviate/core/validation.py:121` |
  | `verification_mode` | `Literal["automated","manual","deferred"]` | exactly one mode | explore.md Problem Definition |
  | `test_ref` | `str \| None` | nullable; required when `verification_mode == "automated"` | explore.md Problem Definition |
- **Invariants**:
  - The mode field never exempts the executable automated test suite. It only labels a criterion's verification path.
  - A link with `verification_mode == "automated"` must carry a non-null `test_ref`.
  - Traceability direction is bidirectional: task→criterion and criterion→test.

### RedHandoffAdvisory (transient)
- **Source-of-truth**: in-memory phase-handoff carried by the RED→GREEN runner (`_run_red_phase` return)
- **Lifecycle owner**: micro RED phase runner (`_run_red_phase`) and GREEN runner that consumes it
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `task_id` | `str` | matches `TSK-\d{3}-\d{2}` | `src/deviate/state/ledger.py:103` |
  | `phase` | `Literal["RED"]` | constant | `src/deviate/cli/micro.py:1062` |
  | `passes` | `bool` | `true` when the test suite returned `0` in RED | `src/deviate/cli/micro.py:1123` |
  | `severity` | `Literal["ok","warning"]` | `warning` when `passes == true` | explore.md Problem Definition |
- **Invariants**:
  - The advisory is non-blocking. A `passes == true` advisory must never abort the RED phase.
  - The advisory is transient. It holds no persistent state, so it cannot desync from the git repo after `git reset`.
  - It does not alter `TaskRecord.status`. The `acceptance_criteria` traceability is the only persistent, additive extension.

### AcceptanceContract (in `plan.md` `## Acceptance Contract`)
- **Source-of-truth**: `specs/{epic}/*/plan.md` (derived, rendered artifact)
- **Lifecycle owner**: meso plan phase (`deviate plan post`) and validation layer (`src/deviate/core/validation.py`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `scenario_id` | `str` | matches `AC-PLAN-\d{3}` | `src/deviate/core/validation.py:117` |
  | `body` | `str` | must contain `Given`/`When`/`Then` | `src/deviate/core/validation.py:87` |
  | `source_outline` | `str` | references `AO-\d{3}` | `src/deviate/core/validation.py:127` |
  | `upstream_traceability` | `str` | non-empty | `src/deviate/core/validation.py:132` |
  | `current_code_evidence` | `str` | non-empty | `src/deviate/core/validation.py:134` |
  | `verification_mode` | `Literal["automated","manual","deferred"]` | one per scenario | explore.md Problem Definition |
- **Invariants**:
  - Scenario ids are unique within a slice's `Acceptance Contract`.
  - Every scenario must retain `Source Outline`, `Upstream Traceability`, and `Current-Code Evidence` (enforced by `validate_acceptance_contract`).
  - `verification_mode` is additive and must not remove any existing enforced clause.

## Relationship Graph

| From | Relationship | To | Cardinality | On-Delete | On-Cascade | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TaskRecord` | has | `CriterionLink` | 1:N | orphan the embedded link | none (embedded) | `src/deviate/state/ledger.py:81` |
| `CriterionLink` | references | `AcceptanceContract.scenario_id` | N:1 | hard-break traceability if scenario drops | none | `src/deviate/core/validation.py:121` |
| `CriterionLink` | verified by | `test_ref` test path | 1:1 | none (reference-only string) | none | explore.md Problem Definition |
| `RedHandoffAdvisory` | annotates | `TaskRecord` (transient) | 1:1 | none (in-memory only) | none | `src/deviate/cli/micro.py` |
| `TaskRecord` | transitions to | `TaskRecord(status)` | 1:1 (sequential) | n/a (append-only transition rows) | n/a | `src/deviate/state/ledger.py` |

## Schema Tables

### TaskRecord (Pydantic — extended)
```python
class CriterionLink(BaseModel):
    criterion_id: str          # matches AC-PLAN-\d{3}
    verification_mode: Literal["automated", "manual", "deferred"]
    test_ref: str | None = None  # required when mode == "automated"

    @field_validator("criterion_id")
    @classmethod
    def _validate_criterion_id(cls, v: str) -> str:
        if not re.match(r"^AC-PLAN-\d{3}$", v):
            raise ValueError(f"Invalid criterion ID format: {v}")
        return v

class TaskRecord(BaseModel):
    id: str                    # matches TSK-\d{3}-\d{2}
    issue_id: str
    description: str = Field(min_length=1)
    status: Literal["PENDING","RED","GREEN","JUDGE","REFACTOR","COMPLETED","FAILED"] = "PENDING"
    execution_mode: Literal["TDD","DIRECT","EXECUTE","E2E","IMMEDIATE"] = "TDD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    security_profile: SecurityProfile | None = None
    acceptance_criteria: list[CriterionLink] | None = None  # additive; no checkpoint persisted here
    model_config = {"extra": "forbid"}
```

### RedHandoffAdvisory (Pydantic — transient, not persisted)
```python
class RedHandoffAdvisory(BaseModel):
    task_id: str               # matches TSK-\d{3}-\d{2}
    phase: Literal["RED"] = "RED"
    passes: bool
    severity: Literal["ok", "warning"] = "ok"
    model_config = {"extra": "forbid"}
```
The advisory is passed by value from the RED runner into the session/GREEN runner. It is never serialized to `tasks.jsonl`, `.deviate/`, or any ledger.

### Verification-Mode Metadata (in `plan.md` `AC-PLAN-NNN` body)
```text
**Scenario AC-PLAN-001:** <description>
- **Source Outline**: `AO-001`
- **Upstream Traceability**: <requirement refs>
- **Current-Code Evidence**: <file path>
- **Verification Mode**: automated
**Given** <precondition>
**When** <action>
**Then** <observable outcome>
```

## State Transitions

### TaskRecord State Machine
- **States**: `PENDING`, `RED`, `GREEN`, `JUDGE`, `REFACTOR`, `COMPLETED`, `FAILED`
- **Initial State**: `PENDING`
- **Terminal States**: `COMPLETED`, `FAILED`
- **Transitions**:
  | From | Event | Guard | To | Side Effects |
  | :--- | :--- | :--- | :--- | :--- |
  | `PENDING` | RED phase start | task fields valid | `RED` | append `RED` transition row (`ledger.py:1136`) |
  | `RED` | RED handoff advisory non-blocking | none | `RED` | carry `RedHandoffAdvisory` to GREEN; never abort on pass |
  | `RED` | GREEN phase pass | test suite returncode 0 | `GREEN` | append `GREEN` transition row |
  | `RED` | GREEN phase fail | test suite returncode != 0 | `RED` (retry via JUDGE) | route to JUDGE via `train_feedback`; JUDGE decides retry GREEN or retry RED+GREEN |
  | `GREEN` | JUDGE pass | diff matches acceptance contract | `JUDGE` | append `JUDGE` transition row |
  | `GREEN` | JUDGE reject | scope violation | `FAILED` | append `FAILED` row |
  | `JUDGE` | REFACTOR start | green state | `REFACTOR` | run format cmd |
  | `REFACTOR` | regression gate pass | test suite returncode 0 after polish | `COMPLETED` | append `COMPLETED` row (`micro.py:2506`) |
  | `REFACTOR` | regression gate fail | test suite returncode != 0 after polish | `FAILED` | raise `PhaseFailedError` |

### RedHandoffAdvisory Lifecycle
- **States**: `ok` (test suite failed as expected in RED) → advisory; `warning` (test suite passed in RED) → advisory
- **Initial State**: n/a (transient value created on each RED run)
- **Terminal States**: none (dropped after GREEN consumes it; a crash discards it and RED re-derives on restart)
- **Transitions**:
  | From | Event | Guard | To | Side Effects |
  | :--- | :--- | :--- | :--- | :--- |
  | n/a | RED run | `_run_test_cmd` returns | `ok` | carry advisory to GREEN; proceed to format cmd |
  | n/a | RED run | `_run_test_cmd` returns 0 | `warning` | carry advisory to GREEN; proceed to format cmd; log warning |

## Data Flow

### [Flow: RED Checkpoint]
1. `_run_red_phase` → `_find_test_files(root)` (`micro.py:1120`) — detects if a test file exists. If none, skip gate.
2. If test files exist: `_run_red_phase` → `_run_test_cmd(root)` (`micro.py:1122`) — runs the test suite via the safe-command gate.
3. `_run_red_phase` captures `test_result.returncode`. Result `0` → `passes=true`, `severity=warning`. Result non-zero → `passes=false`, `severity=ok`.
4. `_run_red_phase` builds `RedHandoffAdvisory` and passes it to the GREEN runner — non-blocking, no abort, no persistence.
5. `_run_red_phase` proceeds to `_run_format_cmd(root)` (`micro.py:1131`) and appends the `RED` transition row — the phase always completes.

### [Flow: GREEN Blocking Gate]
1. `_run_green_phase` consumes the `RedHandoffAdvisory` from the RED handoff; a `warning` advisory flags the unexpected-pass.
2. `_run_green_phase` sets session phase to `GREEN` (`micro.py:1289`).
3. `_run_green_phase` → `_run_test_cmd(root, task)` (`micro.py:1298`) — runs the test suite.
4. `_run_test_cmd` returns `returncode != 0` → `_run_green_phase` sets `train_feedback` (`micro.py:1306`) and returns the session; JUDGE decides whether to retry GREEN or retry RED+GREEN.
5. `returncode == 0` → `_run_green_phase` proceeds to `_run_format_cmd` and commits the GREEN result.

### [Flow: REFACTOR Regression Gate]
1. `_run_refactor_phase` runs the agent (`micro.py:2486-2495`).
2. `_run_refactor_phase` → `_run_test_cmd(root)` (`micro.py:2500`) — runs the test suite.
3. The result `returncode` is inspected. Non-zero → `_run_refactor_phase` raises `PhaseFailedError` (blocking). Zero → proceeds.
4. `_run_format_cmd(root)` (`micro.py:2501`) — format check.
5. `_run_refactor_phase` appends the `COMPLETED` transition row (`micro.py:2506`), commits, and force-transitions the session to `IDLE`.

### [Flow: Acceptance Traceability]
1. `deviate plan post` renders `AC-PLAN-NNN` scenarios with `verification_mode` metadata.
2. `deviate meso tasks pre` → `validate_acceptance_contract` (`validation.py:112`) validates structure + mode.
3. `generate_jsonl_from_md` (`tasks_ledger.py`) propagates `acceptance_criteria` links into each generated `TaskRecord`.
4. Micro GREEN/JUDGE validators resolve `criterion_id` → scenario and `test_ref` → test path for traceability.

## Source Registry

| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-DM-001 | Codebase_File | `src/deviate/state/ledger.py:81` | `TaskRecord` model and `extra="forbid"` config anchor the additive field. |
| SRC-DM-002 | Codebase_File | `src/deviate/state/ledger.py:103` | `id` validator regex `TSK-\d{3}-\d{2}` reused across entities. |
| SRC-DM-003 | Codebase_File | `src/deviate/core/validation.py:112` | `validate_acceptance_contract` enforces the scenario structure and ids. |
| SRC-DM-004 | Codebase_File | `src/deviate/cli/micro.py:1123` | RED pass-rejection behavior the advisory replaces. |
| SRC-DM-005 | Codebase_File | `src/deviate/cli/micro.py:1298` | GREEN test-gate invocation. |
| SRC-DM-006 | Codebase_File | `src/deviate/cli/micro.py:2500` | REFACTOR `_run_test_cmd` call lacking returncode check. |
| SRC-DM-007 | Constitution | `specs/constitution.md` | §1 append-only protocol, §2 no-DB, §3 GREEN/REFACTOR gate clauses. |
| SRC-DM-008 | Explore_MD | `specs/005-acceptance-gates/explore.md` | Option A scope; `acceptance_criteria` field; RED checkpoint as non-blocking advisory. |
