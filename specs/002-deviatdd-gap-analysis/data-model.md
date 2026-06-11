## [ENTITY_DEFINITIONS]

### E01: ExecutionProfile
- **Source-of-truth**: `src/deviate/core/profile.py` (new)
- **Lifecycle owner**: `DeviateConfig` (read from `.deviate/config.toml`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | variant | `Literal["full", "fast", "secure"]` | Exactly one of three values | `explore.md` Gap #1.1 |
  | resolve_profile | `(profile: str) -> tuple[bool, bool]` | Maps to `(no_judge, no_refactor)` | `explore.md` Gap #1.3 |
- **Invariants**: No unknown profiles; `full` → all phases, `fast` → no JUDGE+REFACTOR, `secure` → JUDGE but no REFACTOR

### E02: ProfileConfig
- **Source-of-truth**: `.deviate/config.toml` (TOML section)
- **Lifecycle owner**: `DeviateConfig.load()`
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | name | `str` | Non-empty, default "default" | `config.py:110` |
  | profile | `Literal["full", "fast", "secure"]` | Must match ExecutionProfile | `explore.md` Gap #1.1 |
  | llm_backend | `str` | Must be valid backend | `config.py:112` |
  | timeout_seconds | `int` | `> 0`, default 300 | `config.py:113` |
  | agent_export_mode | `Literal["local", "global"]` | Must match allowed values | `config.py:114` |
  | agent | `AgentConfig` | Nested model with `extra = "forbid"` | `config.py:115` |

### E03: ContextContract
- **Source-of-truth**: Emitted as JSON to stdout by `context pre`; not persisted
- **Lifecycle owner**: `context pre` command → agent reads → `context post` validates
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | phase | `str` | In `_VALID_PHASES` | `explore.md` Gap #2.1 |
  | spec_path | `str` | Path must exist | `explore.md` Gap #2.1 |
  | constitution_path | `str` | Path must exist | `explore.md` Gap #2.1 |
  | agents_md_path | `str` | Path to AGENTS.md | `explore.md` Gap #2.2 |
  | claude_md_path | `str` | Path to CLAUDE.md | `explore.md` Gap #2.2 |
  | worktree_path | `str` | Resolved worktree | `explore.md` Gap #2.1 |
  | branch_name | `str` | Git branch name | `explore.md` Gap #2.1 |
  | issue_id | `str` | Active issue | `explore.md` Gap #2.1 |
  | status | `Literal["READY", "DRY_RUN"]` | Output mode | `specs/constitution.md §3` |

### E04: AdhocRecord
- **Source-of-truth**: `specs/adhoc.jsonl` (append-only JSONL)
- **Lifecycle owner**: `adhoc pre` writes → `adhoc post` transitions → deleted on completion
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | id | `str` | UUID format | `explore.md` Gap #3.2 |
  | description | `str` | `min_length >= 1` | `explore.md` Gap #3.2 |
  | complexity | `Literal["LOW", "MEDIUM", "HIGH"]` | Determined by gate | `explore.md` Gap #3.1 |
  | execution_mode | `Literal["DIRECT", "TDD", "E2E"]` | LOW→DIRECT, MEDIUM→TDD, HIGH→TDD | `explore.md` Gap #3.1 |
  | status | `Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"]` | Default "PENDING" | `explore.md` Gap #3.3 |

### E05: CacheEntry
- **Source-of-truth**: `.deviate/cache.json` (single JSON file, mutable)
- **Lifecycle owner**: `CacheDiscipline.validate()` class
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | key | `str` | Unique identifier | `explore.md` Gap #7.1 |
  | source_path | `str` | Must exist for validation | `explore.md` Gap #7.1 |
  | source_mtime | `float` | File modification timestamp | `explore.md` Gap #7.1 |
  | valid | `bool` | Derived from mtime check | `explore.md` Gap #7.1 |
  | digest | `str \| None` | SHA-256 content hash | `explore.md` Gap #7.1 |

### E06: RollbackSnapshot
- **Source-of-truth**: `.deviate/rollback.jsonl` (append-only audit trail)
- **Lifecycle owner**: Judge `post` command on violation
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | phase | `str` | Must be "JUDGE" at creation | `explore.md` Gap #8.1 |
  | branch | `str` | Current git branch | `explore.md` Gap #8.2 |
  | commit_sha | `str` | Pattern `^[a-f0-9]{40}$` | `explore.md` Gap #8.2 |
  | reason | `str` | Violation description | `explore.md` Gap #8.3 |
  | restored | `bool` | Default `False` | `explore.md` Gap #8.4 |

### E07: LedgerFilter
- **Source-of-truth**: Transient query parameter struct; not persisted
- **Lifecycle owner**: `ledger list` CLI command
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | entity_type | `Literal["issue", "task"]` | Which ledger to query | `explore.md` Gap #6.1 |
  | status_filter | `str \| None` | Optional status filter | `explore.md` Gap #6.1 |
  | limit | `int` | `> 0`, default 20 | `explore.md` Gap #6.1 |
  | offset | `int` | `>= 0`, default 0 | `explore.md` Gap #6.1 |

### E08: TaskLedgerBatch
- **Source-of-truth**: Generated transiently; persisted to `specs/<epic>/<slug>/tasks.jsonl`
- **Lifecycle owner**: `tasks post` → parse tasks.md → write JSONL → commit
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | issue_id | `str` | Active session issue | `explore.md` Gap #13.1 |
  | tasks | `list[TaskRecord]` | Each `id` unique within batch | `explore.md` Gap #13.1 |
  | source_file | `str` | Path to tasks.md | `explore.md` Gap #13.1 |
  | count | `int` | `len(tasks)` | `explore.md` Gap #13.1 |

### E09: PlaceholderRegistry
- **Source-of-truth**: Resolved lazily; not persisted
- **Lifecycle owner**: `_resolve_seed()` in init; expanded in constitution pre
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | variables | `dict[str, str]` | Keys: `PROJECT_NAME`, `REPO_ROOT`, `TARGET_BACKEND_FRAMEWORK`, `TARGET_PACKAGE_MANAGER`, `TARGET_TEST_RUNNER`, `TARGET_COVERAGE_MINIMUM` | `explore.md` Gap #10.1–10.4 |
  | resolved_at | `datetime` | Timestamp of last resolution | `explore.md` Gap #10.5 |

### E10: CommonCLIFlags
- **Source-of-truth**: CLI options `--json`/`--quiet` on every `pre` command
- **Lifecycle owner**: Typer option in each macro/meso/micro `pre` function signature
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | json_output | `bool` | Default `False` | `explore.md` Gap #9.1 |
  | quiet | `bool` | Default `False` | `explore.md` Gap #9.1 |

### E11: PytestReportConfig
- **Source-of-truth**: `.deviate/config.toml` under `[pytest]` section
- **Lifecycle owner**: `_run_pytest()` reads config
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | json_report | `bool` | Default `True` | `explore.md` Gap #16.1 |
  | report_path | `Path \| None` | Defaults to `.deviate/pytest-report.json` | `explore.md` Gap #16.1 |
  | junit | `bool` | Default `False` | `explore.md` Gap #16.1 |

### E12: StubAgentBackend
- **Source-of-truth**: `src/deviate/core/agent.py` (new, alongside real backends)
- **Lifecycle owner**: AgentBackend registry (`BACKEND_COMMANDS`)
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | invoke_return | `HandoverManifest` | Always returns canned success response | `plan-tdd-integration-gap.md:98-108` |
  | backend_name | `Literal["stub"]` | Must match `BACKEND_COMMANDS["stub"]` key | `plan-tdd-integration-gap.md:229-235` |
  | subprocess_bypass | `bool` | Always `True` — no real subprocess | `plan-tdd-integration-gap.md:101` |
- **Invariants**: StubBackend must return same `HandoverManifest` schema as real backends; never used in production; E2E tests use real backend

### E13: YELLOW Skill Manifest
- **Source-of-truth**: Emitted as JSON to stdout by `yellow_pre`; consumed by `deviate-yellow` skill agent
- **Lifecycle owner**: `yellow_pre` CLI command
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | proposed_changes | `list[str]` | Changed files detected by `_detect_phase_changes()` | `micro.py:794-810` |
  | rationale | `str` | Always `"YELLOW phase — review proposed test amendments"` | `micro.py:806` |
  | test_files | `list[str]` | Test files from `_find_test_files()` | `micro.py:802` |
  | status | `Literal["REVIEW", "APPROVED", "REJECTED"]` | Updated by yellow_post | — |

### E14: JUDGE Skill Manifest
- **Source-of-truth**: Emitted as JSON to stdout by `judge_pre`; consumed by `deviate-judge` skill agent
- **Lifecycle owner**: `judge_pre` CLI command
- **Attributes**:
  | Attribute | Type | Invariant | Source Anchor |
  |-----------|------|-----------|---------------|
  | verdict | `Literal["COMPLIANCE_PASS", "COMPLIANCE_VIOLATION"]` | Derived from `_find_protected_modules()` | `micro.py:867-897` |
  | details | `list[dict]` | Violation file → protected module mappings | `micro.py:873-891` |
  | changed_files | `list[str]` | Files changed since last phase | `micro.py:870` |
  | protected_modules | `list[str]` | Spec-defined protected module paths | `micro.py:872` |

## [RELATIONSHIP_GRAPH]

| From | Relationship | To | Cardinality | On-Delete | On-Cascade | Source Anchor |
|------|------------|----|-------------|-----------|------------|---------------|
| `DeviateConfig` | selects | `ProfileConfig` | 1:1 | N/A (TOML read) | N/A | `config.py:110` |
| `ProfileConfig` | constrains | `ExecutionProfile` | 1:1 | N/A (inline value) | N/A | `config.py:110` |
| `SessionState` | references | `IssueRecord` | 0..1 | N/A (session reload) | N/A | `config.py:122` |
| `IssueRecord` | owns | `TaskRecord` | 1:N | CASCADE (ledger) | N/A (append-only) | `ledger.py:59` |
| `IssueRecord` | blocks | `IssueRecord` | M:N | N/A (read-time) | N/A | `ledger.py:236` |
| `ContextContract` | references | `ConstitutionRecord` | 0..1 | N/A (transient) | N/A | `context.py` (new) |
| `AdhocRecord` | references | `ExecutionProfile` | 1:1 | N/A (inline) | N/A | `ledger.py` (new) |
| `CacheEntry` | derives from | source file (`Path`) | 1:1 | EVICT (on source delete) | N/A | `cache.py` (new) |
| `RollbackSnapshot` | targets | `SessionState` | 1:1 | N/A (append-only) | N/A | `config.py` (new) |
| `TaskLedgerBatch` | persists to | `TaskRecord` | 1:N | N/A | CASCADE | `ledger.py` (new) |
| `PlaceholderRegistry` | consumes | seed files | 1:N | N/A (transient) | N/A | `config.py:88` |
| `CommonCLIFlags` | decorates | all `pre` commands | M:N | N/A (inline) | N/A | `_common.py` |
| `PytestReportConfig` | configures | `_run_pytest()` | 1:1 | N/A (config read) | N/A | `micro.py:385` |
| `StubAgentBackend` | mocks | `AgentBackend.invoke()` | 1:1 | N/A (test-only) | N/A | `plan-tdd-integration-gap.md:98-108` |
| `yellow_pre` | emits | `YELLOWSkillManifest` | 1:1 | N/A (transient) | N/A | `micro.py:794-810` |
| `judge_pre` | emits | `JUDGESkillManifest` | 1:1 | N/A (transient) | N/A | `micro.py:867-897` |
| `deviate-yellow` skill | reads | `YELLOWSkillManifest` | 1:1 | N/A (transient) | N/A | Gap #18 |
| `deviate-judge` skill | reads | `JUDGESkillManifest` | 1:1 | N/A (transient) | N/A | Gap #19 |

## [SCHEMA_TABLES]

### DeviateConfig (`.deviate/config.toml`)
```toml
profile = "full"
llm_backend = "droid"
timeout_seconds = 300
agent_export_mode = "local"

[agent]
backend = "opencode"
timeout = 600

[pytest]
json_report = true
report_path = ".deviate/pytest-report.json"
```

### SessionState (`.deviate/session.json`)
```json
{
  "current_phase": "SPECIFY",
  "active_issue_id": "ISS-001-001",
  "last_command": "specify pre",
  "timestamp": "2026-06-10T10:30:00Z"
}
```

### Issues Ledger (`specs/issues.jsonl`)
```jsonl
{"issue_id":"ISS-001-001","type":"feature","title":"CLI init scaffold","status":"COMPLETED","source_file":"specs/001-deviate-cli-bootstrapping/explore.md","blocked_by":[],"timestamp":"2026-06-10T10:00:00Z"}
{"issue_id":"ISS-001-002","type":"feature","title":"Profile command","status":"BACKLOG","source_file":"specs/002-deviatdd-gap-analysis/issues/001-profile-command.md","blocked_by":[],"timestamp":"2026-06-11T08:00:00Z"}
```

### Tasks Ledger (`specs/<epic>/<slug>/tasks.jsonl`)
```jsonl
{"id":"TSK-002-01","issue_id":"ISS-001-002","description":"Add ExecutionProfile dataclass","status":"PENDING","execution_mode":"TDD","created_at":"2026-06-11T08:00:00Z"}
{"id":"TSK-002-02","issue_id":"ISS-001-002","description":"Replace no_judge/no_refactor with profile","status":"PENDING","execution_mode":"TDD","created_at":"2026-06-11T08:00:00Z"}
```

### Adhoc Ledger (`specs/adhoc.jsonl`) — new
```jsonl
{"id":"ADHOC-001","description":"Fix init dotfile bug","complexity":"LOW","execution_mode":"DIRECT","status":"COMPLETED","created_at":"2026-06-10T11:00:00Z"}
```

### Rollback Ledger (`.deviate/rollback.jsonl`) — new
```jsonl
{"phase":"JUDGE","branch":"feat/002-deviatdd-gap-analysis","commit_sha":"abc123def4567890abcdef1234567890abcdef12","timestamp":"2026-06-10T12:05:00Z","reason":"COMPLIANCE_VIOLATION: modified protected module src/deviate/core/protected.py","restored":true}
```

### Cache Store (`.deviate/cache.json`) — new
```json
{
  "entries": {
    "constitution_seed": {
      "key": "constitution_seed",
      "source_path": "src/deviate/prompts/constitution_seed.md",
      "source_mtime": 1720000000.0,
      "cached_at": "2026-06-10T12:00:00Z",
      "valid": true,
      "digest": "e3b0c44298fc1c149afbf4c8996fb924"
    }
  }
}
```

### Pydantic: New entities for config.py
```python
class ProfileConfig(BaseModel):
    name: str = "default"
    profile: Literal["full", "fast", "secure"] = "full"
    llm_backend: str = "droid"
    timeout_seconds: int = Field(default=300, gt=0)
    agent_export_mode: Literal["local", "global"] = "local"
    agent: AgentConfig = Field(default_factory=AgentConfig)
    model_config = {"extra": "forbid"}

class PytestReportConfig(BaseModel):
    json_report: bool = True
    report_path: Optional[str] = None
    junit: bool = False
    model_config = {"extra": "forbid"}
```

### Pydantic: New entities for ledger.py
```python
class AdhocRecord(BaseModel):
    id: str
    description: str = Field(min_length=1)
    complexity: Literal["LOW", "MEDIUM", "HIGH"]
    execution_mode: Literal["DIRECT", "TDD", "E2E"]
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"] = "PENDING"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = {"extra": "forbid"}

class LedgerFilter(BaseModel):
    entity_type: Literal["issue", "task"]
    status_filter: str | None = None
    limit: int = Field(default=20, gt=0)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["created_at", "timestamp", "status"] = "created_at"
    sort_desc: bool = True
    model_config = {"extra": "forbid"}

class RollbackSnapshot(BaseModel):
    phase: str
    branch: str
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str
    restored: bool = False
    model_config = {"extra": "forbid"}
```

### StubAgentBackend class (src/deviate/core/agent.py — new)
```python
class StubAgentBackend(AgentBackend):
    """Deterministic stub backend for testing integration logic."""

    def invoke(
        self, prompt: str, backend: str | None = None, timeout: int | None = None
    ) -> HandoverManifest:
        return HandoverManifest(
            phase="RED",
            status="success",
            test_file="tests/test_stub.py",
            verification_command="pytest tests/test_stub.py",
        )

BACKEND_COMMANDS: dict[str, str] = {
    "opencode": "opencode run",
    "claude": "claude -p",
    "droid": "droid exec",
    "stub": "echo",  # Stub backend for testing — no real subprocess
}
```

### YELLOW Skill Manifest Contract (emitted by yellow_pre)
```json
{
  "proposed_changes": ["src/deviate/core/profile.py", "tests/test_profile.py"],
  "rationale": "YELLOW phase — review proposed test amendments",
  "test_files": ["tests/test_core/test_profile.py", "tests/test_cli/test_init.py"]
}
```

### JUDGE Skill Manifest Contract (emitted by judge_pre)
```json
{
  "verdict": "COMPLIANCE_VIOLATION",
  "details": [{"file": "src/deviate/core/protected.py", "protected_module": "src/deviate/core/protected.py"}],
  "changed_files": ["src/deviate/core/protected.py"],
  "protected_modules": ["src/deviate/core/protected.py"]
}
```

### Pydantic: New entities for cache.py, context.py
```python
class CacheEntry(BaseModel):
    key: str
    source_path: str
    source_mtime: float
    cached_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid: bool = False
    digest: str | None = None
    model_config = {"extra": "forbid"}

class CacheStore(BaseModel):
    entries: dict[str, CacheEntry] = Field(default_factory=dict)
    model_config = {"extra": "forbid"}

class ContextContract(BaseModel):
    phase: str
    spec_path: str
    constitution_path: str
    agents_md_path: str
    claude_md_path: str
    worktree_path: str
    branch_name: str
    issue_id: str
    timestamp: datetime
    status: Literal["READY", "DRY_RUN"]
    dry_run: bool = False
    profile: Literal["full", "fast", "secure"] = "full"
    model_config = {"extra": "forbid"}
```

## [STATE_TRANSITIONS]

### SessionState Phase Machine
- **States**: `IDLE → EXPLORE → RESEARCH → PRD → SHARD → SPECIFY → TASKS → RED → GREEN → JUDGE → REFACTOR → E2E → EXECUTE → HOTFIX → YELLOW → IDLE`
- **Initial State**: `IDLE`
- **Terminal States**: None — returns to `IDLE` after each macro/meso/micro cycle
- **Transitions**:

| From | Event | Guard | To | Side Effects |
|------|-------|-------|----|--------------|
| IDLE | explore_pre | constitution exists | EXPLORE | allocate_feature_bucket() |
| EXPLORE | explore_post | explore.md valid | RESEARCH | commit explore.md |
| RESEARCH | research_post | design.md + data-model.md exist | PRD | commit artifacts |
| PRD | prd_post | prd.md valid | SHARD | commit prd.md |
| SHARD | shard_post | issues registered | IDLE | issues → BACKLOG |
| SHARD | specify_pre | issue claimed | SPECIFY | create worktree |
| SPECIFY | specify_post | spec.md valid | TASKS | commit spec.md |
| TASKS | tasks_post | tasks.md valid | IDLE | commit tasks.md |
| IDLE | force_transition_to | micro phase | RED | bypass macro state machine |
| RED | force_transition_to | test fails w/ assertion | GREEN | write implementation |
| GREEN | force_transition_to | pytest passes | JUDGE | compliance check |
| JUDGE | force_transition_to | no violation | REFACTOR | polish |
| JUDGE | force_transition_to | violation | GREEN | git revert, rollback log |
| REFACTOR | force_transition_to | regression check | IDLE | commit, COMPLETED |
| YELLOW | --approved | amendments exist | GREEN | commit amendments + `_load_skill_content("YELLOW")` skill guidance |
| YELLOW | --rejected | amendments exist | GREEN | git restore + no skill invocation |
| JUDGE | force_transition_to | compliance check | REFACTOR | `_load_skill_content("JUDGE")` skill guidance + `_run_judge_phase()` |
| JUDGE | force_transition_to | violation | GREEN | `_load_skill_content("JUDGE")` skill guidance + `_run_judge_phase()` + rollback |

### TaskStatus State Machine
- **States**: `PENDING → RED → GREEN → JUDGE → REFACTOR → COMPLETED → FAILED`
- **Initial State**: `PENDING`
- **Terminal States**: `COMPLETED`, `FAILED`
- **Transitions**:

| From | Event | Guard | To | Side Effects |
|------|-------|-------|----|--------------|
| PENDING | task dispatch | force_transition_to | RED | session → RED, write failing test |
| RED | green_pre | pytest fails + no syntax error | GREEN | session → GREEN, write impl |
| GREEN | judge_pre | pytest passes | JUDGE | session → JUDGE |
| JUDGE | refactor_post | compliance pass | REFACTOR | session → REFACTOR |
| JUDGE | refactor_post | violation | GREEN | RollbackSnapshot, git revert, re-route |
| REFACTOR | refactor_post | regression passes | COMPLETED | commit, session → IDLE |
| any | 2 retry limit | max_retries=2 | FAILED | ledger append |

### IssueStatus State Machine
- **States**: `DRAFT → BACKLOG → SPECIFIED → SHARDED → COMPLETED`
- **Initial State**: `DRAFT`
- **Terminal States**: `COMPLETED`
- **Transitions** (all append-only via `append_issue_transition`):

| From | Event | Guard | To | Side Effects |
|------|-------|-------|----|--------------|
| DRAFT | shard_post | issue registered | BACKLOG | ledger append |
| BACKLOG | specify_pre | claim_issue succeeds | SPECIFIED | worktree create, push |
| SPECIFIED | shard_post | issues registered | SHARDED | ledger append |
| SHARDED | pr merge | `--merge` flag | COMPLETED | ledger append |

### AdhocStatus State Machine
- **States**: `PENDING → IN_PROGRESS → COMPLETED → FAILED`
- **Initial State**: `PENDING`
- **Terminal States**: `COMPLETED`, `FAILED`
- **Transitions**:

| From | Event | Guard | To | Side Effects |
|------|-------|-------|----|--------------|
| PENDING | adhoc_pre | complexity gate resolved | IN_PROGRESS | session force to EXECUTE |
| IN_PROGRESS | adhoc_post | execution done | COMPLETED | session → IDLE |
| IN_PROGRESS | adhoc_post | error | FAILED | session → IDLE |

## [DATA_FLOW]

### Flow: CLI Registration
1. `deviate init --profile fast --agent claude` → `_scaffold_dotfiles()` → `DeviateConfig(profile="fast")` → `.deviate/config.toml` (TOML serialization, `config.py:158-159`)
2. `_apply_governance()` → `_read_seed("deviate.prompts.governance", "claudemd_seed.md")` → `_upsert_governance_block(CLAUDE.md, content)` (`__init__.py:184-197`)
3. `_provision_constitution()` → `PlaceholderRegistry.resolve()` → `specs/constitution.md` (`__init__.py:166-181`)
4. `detect_agents()` → `_install_skills_to_agents()` → skill symlinks per agent (`__init__.py:210-223`, `core/skills.py`)

### Flow: Context Sync
1. `deviate context pre` → validate `.deviate/` exists → load `SessionState` → resolve paths (spec, constitution, AGENTS.md, CLAUDE.md, worktree) → emit `ContextContract` JSON to stdout (`cli/context.py` new)
2. [agent reads contract → generates content]
3. `deviate context post <manifest>` → validate manifest → `_upsert_governance_block(CLAUDE.md)` → `_upsert_governance_block(AGENTS.md)` → enforce `AGENTS.md → CLAUDE.md` symlink via `ln -sf` → session → IDLE (`cli/context.py` new, `explore.md` Gap #2.2)

### Flow: Adhoc Task
1. `deviate adhoc pre "fix typo"` → complexity gate: LOW + description > 50 chars → `execution_mode=DIRECT` → `AdhocRecord` → `specs/adhoc.jsonl` → force session to EXECUTE → emit contract (`cli/adhoc.py` new, `explore.md` Gap #3.2)
2. [agent executes task]
3. `deviate adhoc post <manifest>` → validate → `AdhocRecord.status = COMPLETED` → session → IDLE (`cli/adhoc.py` new, `explore.md` Gap #3.3)

### Flow: Profile Dispatch
1. `deviate run TSK-001-01 --profile fast` → `DeviateConfig.profile = "fast"` → `dispatch()`: `profile=fast` → `_run_tdd_cycle()` skips JUDGE → `_run_refactor_phase` → `_run_pytest` → `_commit_phase` (`cli/micro.py` modified, `explore.md` Gap #1.2-1.4)
2. Contract emitted with `profile` field → agent reads profile → adapts behavior

### Flow: Cache Validation
1. `deviate <command> pre` → `CacheDiscipline.validate()` → for each `CacheEntry`: compare `source_path.mtime` vs `source_mtime` → if mismatch: recompute digest, mark invalid → update `.deviate/cache.json` (`core/cache_discipline.py` new, `explore.md` Gap #7.1-7.2)

### Flow: StubAgentBackend Test Pattern
1. Test declares `agent="stub"` → `_run_red_phase()` / `_run_green_phase()` calls `_invoke_agent(prompt, c, backend_name="stub")` → `AgentBackend.from_name("stub")` → `StubAgentBackend.invoke()` returns canned `HandoverManifest` → no subprocess is spawned (`tests/conftest.py:16-17` replaced with system-edge mock per `plan-tdd-integration-gap.md:257-265`)
2. `mock_popen` fixture asserts `subprocess.Popen` was called with expected CLI args, env vars, and stdin prompt (`plan-tdd-integration-gap.md:57-73`)

### Flow: YELLOW Phase Skill Invocation
1. RED → GREEN → TamperGuard detects test edit → YELLOW trigger (`micro.py:753`)
2. Agent invokes `deviate yellow pre` → `_detect_phase_changes()` → `_find_test_files()` → emits `YELLOWSkillManifest` JSON (`micro.py:794-810`)
3. `deviate-yellow` skill guides agent: review proposed changes, evaluate against spec, approve or reject (`micro.py:42` — new `_SKILL_NAMES["YELLOW"] = "deviate-yellow"`)
4. `deviate yellow post --approved` → `_commit_phase()` → session → GREEN (`micro.py:835-839`)
5. `deviate yellow post --rejected` → `git restore .` → session → GREEN (`micro.py:841-846`)

### Flow: JUDGE Phase Skill Invocation
1. GREEN passes → `_run_tdd_cycle()` dispatches JUDGE via `_PHASE_MAP["JUDGE"]` (`micro.py:348`)
2. `_run_judge_phase()` loads `deviate-judge` skill (replaces `_SKILL_NAMES['JUDGE'] = None` with `"deviate-judge"`) → `_load_skill_content("JUDGE")` → `_build_agent_prompt()` → `_invoke_agent()` (`micro.py:285-319` modified per Gap #19)
3. Skill guides agent to evaluate compliance: read `judge_pre` manifest, verify git diff against spec.md invariants, report findings
4. `judge_pre` → `_detect_phase_changes()` → `_find_protected_modules()` → emits `JUDGESkillManifest` (`micro.py:867-897`)
5. On violation: `RollbackSnapshot` → `git revert --no-edit <green_sha>` → inject feedback → re-route to GREEN (`micro.py` modified per Gap #8)

### Flow: Judge Train Rollback
1. `judge post` detects `COMPLIANCE_VIOLATION` → `RollbackSnapshot(phase="JUDGE", reason=...)` → `.deviate/rollback.jsonl` (`micro.py:200`, `explore.md` Gap #8.1)
2. `git revert --no-edit <green_commit_sha>` (not `--hard`) → preserve RED test file state (`micro.py` modified, `explore.md` Gap #8.2)
3. Inject `<judge_feedback>` into session state → re-route to GREEN phase (`micro.py:203-204`, `explore.md` Gap #8.3-8.4)

## [SOURCE_REGISTRY]

| ID | Type | Source / Path | Relevance Note |
|----|------|---------------|----------------|
| DM-SRC-001 | Explore_MD | `specs/002-deviatdd-gap-analysis/explore.md` | All 16 gap definitions with priority and file mappings |
| DM-SRC-002 | Constitution | `specs/constitution.md` | Governance rules for state transitions, ledger protocol |
| DM-SRC-003 | Codebase_File | `src/deviate/state/config.py` | Existing DeviateConfig, SessionState models |
| DM-SRC-004 | Codebase_File | `src/deviate/state/ledger.py` | Existing IssueRecord, TaskRecord, append transition patterns |
| DM-SRC-005 | Codebase_File | `src/deviate/cli/micro.py` | TDD cycle phase dispatch, run_command signature |
| DM-SRC-006 | Codebase_File | `src/deviate/cli/__init__.py` | CLI registration, init command, placeholder resolution |
| DM-SRC-007 | Codebase_File | `src/deviate/cli/_common.py` | Shared CLI utilities |
| DM-SRC-008 | Codebase_File | `specs/001-deviate-cli-python/data-model.md` | Existing data-model for reference patterns |
| DM-SRC-009 | Plan_MD | `specs/002-deviatdd-gap-analysis/plan-tdd-integration-gap.md` | StubAgentBackend design, mock boundary strategy, test patterns |
| DM-SRC-010 | Codebase_File | `src/deviate/cli/micro.py` | `_SKILL_NAMES`, `_run_judge_phase`, yellow/judge CLI commands |
| DM-SRC-011 | Codebase_File | `tests/test_micro/conftest.py` | Autouse `_invoke_agent` mock pattern — the broken boundary |
| DM-SRC-012 | Codebase_File | `src/deviate/core/agent.py` | AgentBackend base class, BACKEND_COMMANDS registry |
