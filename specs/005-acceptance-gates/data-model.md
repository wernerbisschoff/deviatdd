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

### RedCheckpointRecord
- **Source-of-truth**: `.deviate/session.json` (session state)
- **Lifecycle owner**: micro RED phase runner (`_run_red_phase`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `task_id` | `str` | matches `TSK-\d{3}-\d{2}` | `src/deviate/state/ledger.py:103` |
  | `phase` | `Literal["RED"]` | constant | `src/deviate/cli/micro.py:1062` |
  | `passes` | `bool` | `true` when the test suite returned `0` in RED | `src/deviate/cli/micro.py:1123` |
  | `severity` | `Literal["ok","warning"]` | `warning` when `passes == true` | explore.md Problem Definition |
  | `recorded_at` | `datetime` | UTC timestamp | `.deviate/session.json` |
- **Invariants**:
  - The checkpoint is non-blocking. A `passes == true` checkpoint must never abort the RED phase.
  - The checkpoint is advisory only and does not alter `TaskRecord.status`.
  - It persists atomically via the existing `SessionState` save path so a RED→GREEN crash does not corrupt state.

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
| `RedCheckpointRecord` | records outcome for | `TaskRecord` | 1:1 | orphan on task re-run | none | `.deviate/session.json` |
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
    acceptance_criteria: list[CriterionLink] | None = None  # additive
    model_config = {"extra": "forbid"}
```

### RedCheckpointRecord (Pydantic — new)
```python
class RedCheckpointRecord(BaseModel):
    task_id: str               # matches TSK-\d{3}-\d{2}
    phase: Literal["RED"] = "RED"
    passes: bool
    severity: Literal["ok", "warning"] = "ok"
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = {"extra": "forbid"}
```

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
  | `RED` | RED checkpoint non-blocking | none | `RED` | record `RedCheckpointRecord`; never abort on pass |
  | `RED` | GREEN phase pass | test suite returncode 0 | `GREEN` | append `GREEN` transition row |
  | `GREEN` | GREEN phase fail | test suite returncode != 0 | `FAILED` | verbose blocking verdict; retain for JUDGE |
  | `GREEN` | JUDGE pass | diff matches acceptance contract | `JUDGE` | append `JUDGE` transition row |
  | `GREEN` | JUDGE reject | scope violation | `FAILED` | append `FAILED` row |
  | `JUDGE` | REFACTOR start | green state | `REFACTOR` | run format cmd |
  | `REFACTOR` | regression gate pass | test suite returncode 0 after polish | `COMPLETED` | append `COMPLETED` row (`micro.py:2506`) |
  | `REFACTOR` | regression gate fail | test suite returncode != 0 after polish | `FAILED` | raise `PhaseFailedError` |

### RedCheckpointRecord Lifecycle
- **States**: `ok` (test suite failed as expected in RED) → advisory; `warning` (test suite passed in RED) → advisory
- **Initial State**: n/a (ephemeral checkpoint record)
- **Terminal States**: none (record is immutable once persisted to `.deviate/session.json`)
- **Transitions**:
  | From | Event | Guard | To | Side Effects |
  | :--- | :--- | :--- | :--- | :--- |
  | n/a | RED run | `_run_test_cmd` returns | `ok` | persist record; proceed to format cmd |
  | n/a | RED run | `_run_test_cmd` returns 0 | `warning` | persist record; proceed to format cmd; log warning |

## Data Flow

### [Flow: RED Checkpoint]
1. `_run_red_phase` → `_find_test_files(root)` (`micro.py:1120`) — detects if a test file exists. If none, skip gate.
2. If test files exist: `_run_red_phase` → `_run_test_cmd(root)` (`micro.py:1122`) — runs the test suite via the safe-command gate.
3. `_run_red_phase` captures `test_result.returncode`. Result `0` → `passes=true`, `severity=warning`. Result non-zero → `passes=false`, `severity=ok`.
4. `_run_red_phase` writes `RedCheckpointRecord` to `.deviate/session.json` via `SessionState.save` — non-blocking, no abort.
5. `_run_red_phase` proceeds to `_run_format_cmd(root)` (`micro.py:1131`) and appends the `RED` transition row — the phase always completes.

### [Flow: GREEN Blocking Gate]
1. `_run_green_phase` sets session phase to `GREEN` (`micro.py:1289`).
2. `_run_green_phase` → `_run_test_cmd(root, task)` (`micro.py:1298`) — runs the test suite.
3. `_run_test_cmd` returns `returncode != 0` → `_run_green_phase` records a blocking `FAILED` verdict, sets `train_feedback` (`micro.py:1306`), and returns the session for JUDGE assessment.
4. `returncode == 0` → `_run_green_phase` proceeds to `_run_format_cmd` and commits the GREEN result.

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
| SRC-DM-004 | Codebase_File | `src/deviate/cli/micro.py:1123` | RED pass-rejection behavior the checkpoint replaces. |
| SRC-DM-005 | Codebase_File | `src/deviate/cli/micro.py:1298` | GREEN test-gate invocation. |
| SRC-DM-006 | Codebase_File | `src/deviate/cli/micro.py:2500` | REFACTOR `_run_test_cmd` call lacking returncode check. |
| SRC-DM-007 | Constitution | `specs/constitution.md` | §1 append-only protocol, §2 no-DB, §3 GREEN/REFACTOR gate clauses. |
| SRC-DM-008 | Explore_MD | `specs/005-acceptance-gates/explore.md` | Option A scope; `acceptance_criteria` field; Red-checkpoint storage deferral. |
