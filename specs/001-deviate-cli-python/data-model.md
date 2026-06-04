## [ENTITY_DEFINITIONS]

### DeviateConfig
- **Source-of-truth**: `.deviate/config.toml`
- **Lifecycle owner**: `deviate init` / `deviate config` CLI commands
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `profile` | `str` | Default "default" | `specs/constitution.md:32` |
  | `llm_backend` | `str` | Default "droid" | `specs/constitution.md:35` |
  | `timeout_seconds` | `int` | `> 0` | `specs/constitution.md:35` |
  | `agent_export_mode` | `Literal["local", "global"]` | Default "local" | `explore.md:4` |
- **Invariants**: Must serialize/deserialize cleanly to TOML; `timeout_seconds` must be > 0.

### SessionState
- **Source-of-truth**: `.deviate/session.json`
- **Lifecycle owner**: `deviate` CLI state manager (`src/deviate/state/session.py`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `current_phase` | `str` | Must map to valid DeviaTDD phase | `specs/constitution.md:14` |
  | `active_issue_id` | `str \| None` | UUID4 format if present | `specs/constitution.md:29` |
  | `last_command` | `str` | Non-empty string | `explore.md:4` |
  | `timestamp` | `datetime` | UTC timezone aware | `specs/constitution.md:14` |
- **Invariants**: Valid JSON structure; `current_phase` must map to a valid DeviaTDD macro/micro phase.

### IssueRecord
- **Source-of-truth**: `specs/issues.jsonl`
- **Lifecycle owner**: `/shard` and `/prd` macro-layer orchestrators
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `id` | `str` | UUID4 identifier | `specs/constitution.md:10` |
  | `title` | `str` | Min length 1 | `specs/constitution.md:10` |
  | `status` | `Literal["DRAFT", "SPECIFIED", "SHARDED", "COMPLETED"]` | Default "DRAFT" | `specs/constitution.md:10` |
  | `created_at` | `datetime` | UTC timezone aware | `specs/constitution.md:10` |
  | `shard_index` | `int` | `>= 0` | `specs/constitution.md:10` |
- **Invariants**: Append-only; immutable once written to ledger.

### TaskRecord
- **Source-of-truth**: `specs/**/tasks.jsonl`
- **Lifecycle owner**: `/tasks` meso-layer orchestrator and micro-layer TDD executor
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `id` | `str` | UUID4 identifier | `specs/constitution.md:10` |
  | `issue_id` | `str` | Must reference valid `IssueRecord.id` | `specs/constitution.md:10` |
  | `description` | `str` | Min length 1 | `specs/constitution.md:10` |
  | `status` | `Literal["PENDING", "RED", "GREEN", "REFACTOR", "COMPLETED"]` | Default "PENDING" | `specs/constitution.md:10` |
  | `execution_mode` | `Literal["TDD", "DIRECT", "E2E"]` | Default "TDD" | `specs/constitution.md:15` |
  | `created_at` | `datetime` | UTC timezone aware | `specs/constitution.md:10` |
- **Invariants**: Append-only; `issue_id` must reference a valid `IssueRecord.id`.

### PromptTemplate
- **Source-of-truth**: `src/deviate/prompts/`
- **Lifecycle owner**: `deviate` package resource manager (`importlib.resources`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  | :--- | :--- | :--- | :--- |
  | `name` | `str` | Matches skill directory name | `explore.md:115-132` |
  | `content` | `str` | Non-empty markdown | `explore.md:115-132` |
  | `version` | `str` | Semantic version string | `explore.md:115-132` |
- **Invariants**: Read-only at runtime; sourced from package resources.

---

## [RELATIONSHIP_GRAPH]

| From | Relationship | To | Cardinality | On-Delete | On-Cascade | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SessionState` | references active config | `DeviateConfig` | 1:1 | N/A (Append-only) | N/A | `specs/constitution.md:30-32` |
| `IssueRecord` | decomposes into | `TaskRecord` | 1:N | N/A (Append-only) | N/A | `specs/constitution.md:10` |
| `TaskRecord` | references template | `PromptTemplate` | N:1 | N/A (Read-only) | N/A | `explore.md:115-132` |

---

## [SCHEMA_TABLES]

### DeviateConfig
```python
from pydantic import BaseModel, Field
from typing import Literal

class DeviateConfig(BaseModel):
    profile: str = Field(default="default", description="Active configuration profile")
    llm_backend: str = Field(default="droid", description="Default LLM backend for generation")
    timeout_seconds: int = Field(default=300, gt=0, description="Execution timeout in seconds")
    agent_export_mode: Literal["local", "global"] = Field(default="local")

    model_config = {"extra": "forbid"}
```

### SessionState
```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class SessionState(BaseModel):
    current_phase: str = Field(default="IDLE", description="Current DeviaTDD phase")
    active_issue_id: Optional[str] = Field(default=None, description="UUID of active issue")
    last_command: str = Field(default="", description="Last executed CLI command")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('current_phase')
    @classmethod
    def validate_phase(cls, v: str) -> str:
        valid_phases = {"IDLE", "EXPLORE", "RESEARCH", "PRD", "SHARD", "SPECIFY", "TASKS", "RED", "GREEN", "REFACTOR", "E2E"}
        if v not in valid_phases:
            raise ValueError(f"Phase must be one of {valid_phases}")
        return v
```

### IssueRecord
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class IssueRecord(BaseModel):
    id: str = Field(..., description="UUID4 identifier")
    title: str = Field(..., min_length=1)
    status: Literal["DRAFT", "SPECIFIED", "SHARDED", "COMPLETED"] = Field(default="DRAFT")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    shard_index: int = Field(..., ge=0)
```

### TaskRecord
```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class TaskRecord(BaseModel):
    id: str = Field(..., description="UUID4 identifier")
    issue_id: str = Field(..., description="Reference to parent IssueRecord.id")
    description: str = Field(..., min_length=1)
    status: Literal["PENDING", "RED", "GREEN", "REFACTOR", "COMPLETED"] = Field(default="PENDING")
    execution_mode: Literal["TDD", "DIRECT", "E2E"] = Field(default="TDD")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## [STATE_TRANSITIONS]

### IssueRecord State Machine
- **States**: `DRAFT` → `SPECIFIED` → `SHARDED` → `COMPLETED`
- **Initial State**: `DRAFT`
- **Terminal States**: `COMPLETED`
- **Transitions**:
  | From | Event | Guard | To | Side Effects |
  | :--- | :--- | :--- | :--- | :--- |
  | `DRAFT` | `specify` | `explore.md` and `design.md` exist | `SPECIFIED` | Appends status update to `specs/issues.jsonl` |
  | `SPECIFIED` | `shard` | `prd.md` is generated and validated | `SHARDED` | Appends status update to `specs/issues.jsonl` |
  | `SHARDED` | `e2e_verify` | All child `TaskRecord`s are `COMPLETED` | `COMPLETED` | Appends status update to `specs/issues.jsonl` |

### TaskRecord State Machine
- **States**: `PENDING` → `RED` → `GREEN` → `REFACTOR` → `COMPLETED`
- **Initial State**: `PENDING`
- **Terminal States**: `COMPLETED`
- **Transitions**:
  | From | Event | Guard | To | Side Effects |
  | :--- | :--- | :--- | :--- | :--- |
  | `PENDING` | `start` | Task is assigned and context is loaded | `RED` | Updates `SessionState.current_phase` |
  | `RED` | `implement` | Failing test exists; production code written | `GREEN` | Runs `mise run check`; appends to task ledger |
  | `GREEN` | `polish` | All tests pass; no implementation-coupled tests | `REFACTOR` | Runs regression gate; appends to task ledger |
  | `REFACTOR` | `verify` | Lint, type-check, and regression tests pass | `COMPLETED` | Updates `SessionState.current_phase` to `IDLE` |

---

## [DATA_FLOW]

### Flow: Initialization
1. **User executes `deviate init`**: CLI reads `src/deviate/prompts/` via `importlib.resources`.
2. **Config & Session Creation**: CLI writes `.deviate/config.toml` (validated by `DeviateConfig`) and `.deviate/session.json` (validated by `SessionState`).
3. **Governance Provisioning**: CLI idempotently appends to `CLAUDE.md` / `AGENTS.md` and provisions `specs/constitution.md`.

### Flow: Macro-Layer Scoping
1. **User executes `deviate explore` → `research` → `prd` → `shard`**: Each command reads current `SessionState`.
2. **LLM Orchestration**: Invokes respective LLM orchestrator based on model tiering rules.
3. **Ledger Append**: Appends a new `IssueRecord` to `specs/issues.jsonl`.
4. **State Update**: `SessionState.active_issue_id` is updated to the newly created issue.

### Flow: Meso-Layer Engineering
1. **User executes `deviate specify` → `tasks`**: Orchestrator reads `IssueRecord` from `specs/issues.jsonl`.
2. **Task Generation**: Orchestrator appends multiple `TaskRecord` entries to `specs/{issue_id}/tasks.jsonl`.

### Flow: Micro-Layer TDD Execution
1. **User executes `deviate red` / `green` / `refactor`**: CLI reads target `TaskRecord` from `specs/**/tasks.jsonl`.
2. **Prompt Loading**: CLI loads corresponding `PromptTemplate` from package resources.
3. **Sandboxed Execution**: Agent generates code/tests within `src/**/*.py` allow-list; CLI runs `mise run check`.
4. **State Mutation**: On success, `TaskRecord.status` is updated in memory and appended as a new state entry to the ledger (maintaining append-only immutability).
5. **Session Update**: `SessionState` is updated to reflect the new phase.

---

## [SOURCE_REGISTRY]

| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Constitution | `specs/constitution.md` | Authoritative architectural rules: 3-layer arch, append-only ledgers, tamper guard, model tiering. |
| SRC-002 | Explore_MD | `specs/001-deviate-cli-python/explore.md` | Verified dependencies, ghost dependencies, and architectural baselines for the greenfield CLI. |
| SRC-003 | Codebase_File | `pyproject.toml` | Python project metadata, CLI entry point, deps (Typer, Rich, Pydantic), build config. |
| SRC-004 | Codebase_File | `mise.toml` | Task runner definitions (test, lint, format, check, setup, clean, help), tool versions. |