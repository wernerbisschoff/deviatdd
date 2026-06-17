# Data Model: Prompt Optimization
<spec_version>0.1.0</spec_version>

---

## Entity Definitions

### PromptTemplate
- **Source-of-truth**: `src/deviate/prompts/` directory tree, indexed via `importlib.resources.files("deviate.prompts")`
- **Lifecycle owner**: `PromptRegistry` (builds in-memory index from FILE_REGISTRY)

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `template_id` | `str` | Unique identifier: `auto/red`, `skills/deviate-research`, `governance/claudemd_seed` | FILE_REGISTRY explore.md:347-395 |
| `file_path` | `str` | Package-relative path within `src/deviate/prompts/` | assembly.py:12 `resources.files("deviate.prompts.auto")` |
| `layer` | `TemplateLayer` | One of: `auto`, `skill`, `governance`, `seed`. Auto = slim, skill = full (explore.md:128-129) | explore.md L128-143 |
| `template_type` | `str` | Structural section: `system_instructions`, `role_definition`, `invariants`, `execution_sequence`, etc. | explore.md L131-142 |
| `phase` | `str \| None` | Mapped DeviaTDD phase(s) | explore.md L188-234 (token size table) |
| `model_tier` | `ModelTier \| None` | Assigned model per constitution tiering | constitution.md L15 |
| `token_count_estimated` | `int` | Estimated token count | explore.md L188-234 |
| `substitution_mode` | `SubstitutionMode` | Must match layer: `regex_curly` for auto, `str_replace_ARGUMENTS` for skill, `regex_dollar` for seed | explore.md L176-184 |
| `has_yaml_frontmatter` | `bool` | True iff layer = `skill` | explore.md L139-142 |
| `content_hash` | `str` | SHA-256 of raw template content, recomputed on any content change | Promptfoo cache key pattern explore.md L299 |
| `version` | `str` | Semver from YAML frontmatter `version` field (skill templates only) | explore.md L139 |
| `created_at` | `datetime` | Set on first index | — |
| `updated_at` | `datetime` | Set on any content change | — |

**Invariants**:
- `template_id` MUST be unique (1:1 with filesystem path)
- `content_hash` MUST be recomputed on every content mutation
- If `layer == "skill"` then `has_yaml_frontmatter` MUST be True and `version` MUST be set
- `substitution_mode` MUST match layer expectations (explore.md L178-184)

### TemplateVariant
- **Source-of-truth**: `.deviate/prompt_eval/variants/{variant_id}.json`
- **Lifecycle owner**: `VariantManager`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `variant_id` | `str` | UUID | — |
| `template_id` | `str` | FK → PromptTemplate.template_id | FILE_REGISTRY |
| `version_label` | `str` | Human label: "v1.2-optimized" | Agenta branching pattern explore.md L338-341 |
| `content` | `str` | Full raw template content (the actual .md text) | explore.md L347-395 |
| `content_hash` | `str` | SHA-256 of content, recomputed on change | explore.md L299 |
| `token_count` | `int` | Actual token count (runtime-computed, not estimated) | explore.md L188-234 |
| `token_delta` | `int` | Difference from baseline variant | — |
| `caching_profile_id` | `str \| None` | FK → CachingProfile | — |
| `parent_variant_id` | `str \| None` | FK → TemplateVariant (self-ref, lineage tracing) | Agenta branching explore.md L338 |
| `status` | `VariantStatus` | One of: DRAFT, EVALUATING, ACTIVE, REJECTED, SUPERSEDED | HITL gate pattern constitution.md L13 |
| `created_at` | `datetime` | Timestamp on creation | — |
| `activated_at` | `datetime \| None` | Set when promoted to ACTIVE | — |

**Invariants**:
- Only one variant per `template_id` may be ACTIVE at a time (exclusive arc)
- Status transitions follow strict state machine (see STATE_TRANSITIONS)
- `content` MUST pass structural validation before status can become EVALUATING
- `token_delta` MUST be recomputed whenever `content` changes relative to baseline

### Baseline
- **Source-of-truth**: `.deviate/prompt_eval/baselines/{baseline_id}.yaml`
- **Lifecycle owner**: `BaselineManager`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `baseline_id` | `str` | UUID | — |
| `name` | `str` | Human label | — |
| `description` | `str` | What this baseline tests | Promptfoo YAML config explore.md L265-283 |
| `template_ids` | `list[str]` | MUST NOT be empty | FILE_REGISTRY |
| `model_provider` | `str` | Must match valid AgentConfig.backend name | config.py L12 |
| `model_name` | `str` | Specific model variant | explore.md L165-174 |
| `query_vars` | `dict[str, Any]` | Default input variables for test prompts | Promptfoo `tests.vars` explore.md L277 |
| `assertions` | `list[EvaluationAssertion]` | Inline child collection | Promptfoo config explore.md L272-283 |
| `created_at` | `datetime` | Timestamp on creation | — |
| `updated_at` | `datetime` | Last modification | — |

**Invariants**:
- `template_ids` MUST NOT be empty
- `model_provider` MUST match a valid AgentConfig.backend name
- A baseline targeting skill templates MUST NOT be evaluated against auto templates

### EvaluationAssertion
- **Source-of-truth**: Embedded within Baseline YAML files (child collection)
- **Lifecycle owner**: `BaselineManager`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `assertion_id` | `str` | UUID | — |
| `baseline_id` | `str` | FK → Baseline | — |
| `assertion_type` | `AssertionType` | One of: `contains-json`, `javascript`, `python`, `llm-rubric`, `not-contains`, `regex`, `factuality`, `similar`, `is_valid_yaml`, `contains_handover_manifest` | Promptfoo assertion types explore.md L286 |
| `value` | `Any` | Assertion parameter: JS code, rubric text, regex pattern | explore.md L286 |
| `weight` | `float` | In [0.0, 1.0]; sum across baseline must not exceed 1.0 | — |
| `order_index` | `int` | Execution order within baseline | Promptfoo config structure explore.md L265 |

**Invariants**:
- `weight` MUST be in [0.0, 1.0]
- Sum of weights per `baseline_id` MUST approximate 1.0
- For `javascript` or `python` assertions, `value` MUST return `{"pass": bool, "score": float, "reason": str}`

### EvaluationRun
- **Source-of-truth**: `.deviate/prompt_eval/runs/runs.jsonl` (append-only JSONL per constitution ledger protocol)
- **Lifecycle owner**: `EvaluationRunner`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `run_id` | `str` | UUID | — |
| `variant_id` | `str` | FK → TemplateVariant | — |
| `baseline_id` | `str` | FK → Baseline | — |
| `status` | `RunStatus` | One of: PENDING, RUNNING, COMPLETED, FAILED, TIMED_OUT, CANCELLED | agent.py invoke lifecycle L234-294 |
| `model_provider` | `str` | Provider used for this run | agent.py L60-65 |
| `model_name` | `str` | Model used | explore.md L165-174 |
| `prompt_sent` | `str` | Fully assembled prompt (cached for reproducibility) | assembly.py L53-62 |
| `raw_output` | `str` | Full LLM response text | agent.py L108-139 |
| `results` | `list[AssertionResult]` | Inline child collection | Promptfoo results explore.md L286 |
| `duration_ms` | `int` | Set when reaching terminal state | agent.py L154-165 |
| `token_usage_input` | `int \| None` | Input tokens consumed (from model metadata if available) | explore.md L314-321 |
| `token_usage_output` | `int \| None` | Output tokens consumed | — |
| `cache_hit` | `bool \| None` | Set from model metadata response | explore.md L312-320 |
| `created_at` | `datetime` | Run initiation timestamp | — |
| `completed_at` | `datetime \| None` | Set when reaching terminal state | — |

**Invariants**:
- `variant_id` + `baseline_id` combination MUST be unique for non-terminal runs
- `prompt_sent` and `raw_output` MUST be persisted before transition to COMPLETED or FAILED
- `duration_ms` MUST be set when reaching terminal state
- Runs are append-only JSONL records (constitution.md L10-11)

### AssertionResult
- **Source-of-truth**: Embedded within EvaluationRun JSONL records (child collection)
- **Lifecycle owner**: `EvaluationRunner`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `result_id` | `str` | UUID | — |
| `run_id` | `str` | FK → EvaluationRun | — |
| `assertion_id` | `str` | FK → EvaluationAssertion | — |
| `passed` | `bool` | Whether assertion passed | explore.md L286 |
| `score` | `float` | In [0.0, 1.0]; 0.0 or 1.0 for deterministic, continuous for model-assisted | explore.md L286 |
| `reason` | `str` | Must NOT be empty if `passed == False` | explore.md L286 |
| `execution_duration_ms` | `int` | Wall-clock for single assertion | — |

**Invariants**:
- `score` MUST be in [0.0, 1.0]
- If `passed == False`, `reason` MUST NOT be empty
- Deterministic assertions: `score` = 0.0 or 1.0
- Model-assisted assertions: `score` may be continuous

### CachingProfile
- **Source-of-truth**: `.deviate/prompt_eval/caching_profiles/{profile_id}.toml`
- **Lifecycle owner**: `CachingOptimizer`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `profile_id` | `str` | UUID | — |
| `layer` | `TemplateLayer` | Which template layer this profile targets | explore.md L128-129 |
| `model_tier` | `ModelTier \| None` | Model tier for optimization | constitution.md L15 |
| `prefix_boundary_marker` | `str` | Marker after which dynamic content begins (e.g., `## Context`, `$ARGUMENTS`) | explore.md L332-333 |
| `static_sections` | `list[str]` | Ordered section keys forming static prefix | explore.md L131-136 |
| `estimated_cache_ratio` | `float` | In [0.0, 1.0]; fraction of prompt that is cacheable | — |
| `cache_hit_discount` | `float` | Multiplier: 0.02 = 50x discount on V4 Flash | explore.md L316-317 |
| `cache_hit_cost_per_mtok` | `float` | $/MTok on cache hit | explore.md L316-317 |
| `cache_miss_cost_per_mtok` | `float` | $/MTok on cache miss | explore.md L316-317 |
| `ttl_seconds` | `int` | Anticipated cache TTL (provider-dependent) | explore.md L299 |
| `is_active` | `bool` | Whether profile is currently enforced | — |

**Invariants**:
- `estimated_cache_ratio` MUST be in [0.0, 1.0]
- `static_sections` MUST list only sections that appear in template structure (explore.md L131-146)
- Composite key: `(layer, model_tier)` is unique per profile

### TokenBudget
- **Source-of-truth**: `.deviate/prompt_eval/token_budgets/{budget_id}.toml`
- **Lifecycle owner**: `BudgetEnforcer`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `budget_id` | `str` | UUID | — |
| `scope` | `BudgetScope` | One of: `per_invocation`, `per_session`, `per_task`, `per_epic` | constitution.md L9 |
| `layer` | `ArchitectureLayer` | One of: `macro`, `meso`, `micro` | constitution.md L9 |
| `model_tier` | `ModelTier` | Which model tier | constitution.md L15 |
| `max_input_tokens` | `int` | Hard cap on input tokens; MUST be > 0 | explore.md L188-234 |
| `max_output_tokens` | `int \| None` | Hard cap on output tokens, None = unbounded | — |
| `max_total_tokens` | `int \| None` | Aggregate cap for scope, None = unbounded | — |
| `warning_threshold_pct` | `float` | In [0.0, 1.0]; % of max triggering warning | — |
| `estimated_cost_cap` | `float \| None` | Optional USD cost cap, None = unbounded | explore.md L314-321 |
| `is_enforced` | `bool` | Enforced vs advisory | — |

**Invariants**:
- `max_input_tokens` MUST be > 0
- Composite key: `(scope, layer, model_tier)` is unique
- `warning_threshold_pct` MUST be in [0.0, 1.0]
- Current prompt token sizes MUST NOT exceed `max_input_tokens`

### OptimizationAttempt
- **Source-of-truth**: `.deviate/prompt_eval/optimizations/optimizations.jsonl` (append-only JSONL)
- **Lifecycle owner**: `OptimizationOrchestrator`

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `attempt_id` | `str` | UUID | — |
| `template_id` | `str` | FK → PromptTemplate | FILE_REGISTRY |
| `source_variant_id` | `str \| None` | FK → TemplateVariant (starting variant) | — |
| `result_variant_id` | `str \| None` | FK → TemplateVariant (result, null until created) | — |
| `optimization_type` | `OptimizationType` | One of: `token_reduction`, `prefix_cache_reorder`, `instruction_clarify`, `manual_edit` | — |
| `token_count_before` | `int` | Token count before optimization | explore.md L188-234 |
| `token_count_after` | `int \| None` | Token count after (set when result_variant created) | — |
| `evaluation_run_ids` | `list[str]` | FK list → EvaluationRun (verification runs) | — |
| `status` | `AttemptStatus` | One of: PENDING, IN_PROGRESS, AWAITING_EVALUATION, ACCEPTED, REJECTED | TDD cycle pattern constitution.md L12 |
| `rationale` | `str \| None` | Agent-provided rationale | — |
| `created_at` | `datetime` | Attempt initiation timestamp | — |
| `resolved_at` | `datetime \| None` | Terminal state timestamp | — |

**Invariants**:
- `result_variant_id` MUST be set before status can be AWAITING_EVALUATION
- `evaluation_run_ids` MUST NOT be empty before status can be ACCEPTED or REJECTED
- If `optimization_type == "token_reduction"`, then `token_count_after` MUST be < `token_count_before` for ACCEPTED
- Append-only JSONL records (constitution.md L10-11)

---

## Relationship Graph

| From | Relationship | To | Cardinality | On-Delete | On-Cascade | Source Anchor |
|------|-------------|----|------------|-----------|------------|---------------|
| PromptTemplate | HAS_VARIANTS | TemplateVariant | 1:N | RESTRICT | CASCADE | explore.md L128-143 |
| TemplateVariant | BELONGS_TO | PromptTemplate | N:1 | CASCADE | — | FILE_REGISTRY |
| TemplateVariant | HAS_PARENT | TemplateVariant | 0..1:0..N | SET NULL | — | Agenta branching explore.md L338 |
| Baseline | HAS_ASSERTIONS | EvaluationAssertion | 1:N | CASCADE | — | Promptfoo config explore.md L265-283 |
| TemplateVariant | EVALUATED_AGAINST | Baseline | N:M (via EvaluationRun) | — | — | Join entity pattern |
| EvaluationRun | FOR_VARIANT | TemplateVariant | N:1 | CASCADE | — | — |
| EvaluationRun | AGAINST_BASELINE | Baseline | N:1 | RESTRICT | — | — |
| EvaluationRun | HAS_RESULTS | AssertionResult | 1:N | CASCADE | — | — |
| AssertionResult | FOR_ASSERTION | EvaluationAssertion | N:1 | CASCADE | — | — |
| AssertionResult | IN_RUN | EvaluationRun | N:1 | CASCADE | — | — |
| CachingProfile | APPLIES_TO_LAYER | — | 1:1 per (layer, model_tier) | — | — | explore.md L128-129 |
| TokenBudget | CONSTRAINS_LAYER | — | 1:1 per (scope, layer, model_tier) | — | — | constitution.md L9, L15 |
| OptimizationAttempt | OPTIMIZES | PromptTemplate | N:1 | RESTRICT | — | — |
| OptimizationAttempt | FROM_VARIANT | TemplateVariant | N:1 | SET NULL | — | — |
| OptimizationAttempt | PRODUCES | TemplateVariant | 1:0..1 | SET NULL | — | — |
| OptimizationAttempt | VERIFIED_BY | EvaluationRun | 1:N | SET NULL | — | — |

**Notes**:
- `TemplateVariant EVALUATED_AGAINST Baseline` is resolved via `EvaluationRun` join entity
- Self-referencing `TemplateVariant.HAS_PARENT` tracks optimization lineage
- `CachingProfile` and `TokenBudget` are environmental constraints, not linked to specific templates
- All JSONL-based entities (EvaluationRun, OptimizationAttempt) follow the Append-Only Ledger Protocol (constitution.md L10)

---

## Schema Tables

All schemas use Pydantic v2 models (Python 3.13, Pydantic >=2.0 per constitution.md:80).

### Enumerations

```python
from enum import Enum

class TemplateLayer(str, Enum):
    AUTO = "auto"
    SKILL = "skill"
    GOVERNANCE = "governance"
    SEED = "seed"

class SubstitutionMode(str, Enum):
    REGEX_CURLY = "regex_curly"
    STR_REPLACE_ARGUMENTS = "str_replace_ARGUMENTS"
    REGEX_DOLLAR = "regex_dollar"
    NONE = "none"

class ModelTier(str, Enum):
    V4_FLASH = "V4_FLASH"
    V4_PRO = "V4_PRO"
    QWEN37_PLUS = "QWEN37_PLUS"

class VariantStatus(str, Enum):
    DRAFT = "DRAFT"
    EVALUATING = "EVALUATING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"

class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"

class AssertionType(str, Enum):
    CONTAINS_JSON = "contains-json"
    JAVASCRIPT = "javascript"
    PYTHON = "python"
    LLM_RUBRIC = "llm-rubric"
    NOT_CONTAINS = "not-contains"
    REGEX = "regex"
    FACTUALITY = "factuality"
    SIMILAR = "similar"
    IS_VALID_YAML = "is_valid_yaml"
    CONTAINS_HANDOVER_MANIFEST = "contains_handover_manifest"

class OptimizationType(str, Enum):
    TOKEN_REDUCTION = "token_reduction"
    PREFIX_CACHE_REORDER = "prefix_cache_reorder"
    INSTRUCTION_CLARIFY = "instruction_clarify"
    MANUAL_EDIT = "manual_edit"

class AttemptStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_EVALUATION = "AWAITING_EVALUATION"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class BudgetScope(str, Enum):
    PER_INVOCATION = "per_invocation"
    PER_SESSION = "per_session"
    PER_TASK = "per_task"
    PER_EPIC = "per_epic"

class ArchitectureLayer(str, Enum):
    MACRO = "macro"
    MESO = "meso"
    MICRO = "micro"
```

### PromptTemplate

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, timezone

class PromptTemplate(BaseModel):
    """33 prompt files indexed from src/deviate/prompts/ (FILE_REGISTRY explore.md:347-395)"""
    template_id: str
    file_path: str
    layer: TemplateLayer
    template_type: str = "system_instructions"
    phase: str | None = None
    model_tier: ModelTier | None = None
    token_count_estimated: int = 0
    substitution_mode: SubstitutionMode = SubstitutionMode.NONE
    has_yaml_frontmatter: bool = False
    content_hash: str = ""
    version: str = "0.1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _substitution_must_match_layer(self) -> "PromptTemplate":
        expected = {
            TemplateLayer.AUTO: SubstitutionMode.REGEX_CURLY,
            TemplateLayer.SKILL: SubstitutionMode.STR_REPLACE_ARGUMENTS,
            TemplateLayer.SEED: SubstitutionMode.REGEX_DOLLAR,
        }
        if self.layer in expected and self.substitution_mode != expected[self.layer]:
            raise ValueError(
                f"Layer {self.layer} requires {expected[self.layer]} "
                f"(explore.md L178-184), got {self.substitution_mode}"
            )
        return self

    @model_validator(mode="after")
    def _skill_layer_requires_frontmatter(self) -> "PromptTemplate":
        if self.layer == TemplateLayer.SKILL and not self.has_yaml_frontmatter:
            raise ValueError("Skill templates require YAML frontmatter (explore.md L139)")
        return self

    model_config = {"extra": "forbid"}
```

### TemplateVariant

```python
class TemplateVariant(BaseModel):
    variant_id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    version_label: str
    content: str
    content_hash: str = ""
    token_count: int = 0
    token_delta: int = 0
    caching_profile_id: str | None = None
    parent_variant_id: str | None = None
    status: VariantStatus = VariantStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: datetime | None = None

    model_config = {"extra": "forbid"}
```

### Baseline

```python
class Baseline(BaseModel):
    baseline_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    template_ids: list[str] = Field(default_factory=list)
    model_provider: str = "deepseek"
    model_name: str = "deepseek-v4-flash"
    query_vars: dict[str, object] = Field(default_factory=dict)
    assertions: list["EvaluationAssertion"] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("template_ids")
    @classmethod
    def _not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Baseline must target at least one template")
        return v

    model_config = {"extra": "forbid"}
```

### EvaluationAssertion

```python
class EvaluationAssertion(BaseModel):
    assertion_id: str = Field(default_factory=lambda: str(uuid4()))
    baseline_id: str
    assertion_type: AssertionType
    value: object = None
    weight: float = 1.0
    order_index: int = 0

    @field_validator("weight")
    @classmethod
    def _weight_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("weight must be in [0.0, 1.0]")
        return v

    model_config = {"extra": "forbid"}
```

### EvaluationRun

```python
class EvaluationRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    variant_id: str
    baseline_id: str
    status: RunStatus = RunStatus.PENDING
    model_provider: str = "deepseek"
    model_name: str = "deepseek-v4-flash"
    prompt_sent: str = ""
    raw_output: str = ""
    results: list["AssertionResult"] = Field(default_factory=list)
    duration_ms: int | None = None
    token_usage_input: int | None = None
    token_usage_output: int | None = None
    cache_hit: bool | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    model_config = {"extra": "forbid"}
```

### AssertionResult

```python
class AssertionResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    assertion_id: str
    passed: bool
    score: float = 0.0
    reason: str = ""
    execution_duration_ms: int = 0

    @field_validator("score")
    @classmethod
    def _score_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("score must be in [0.0, 1.0]")
        return v

    model_config = {"extra": "forbid"}
```

### CachingProfile

```python
class CachingProfile(BaseModel):
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    layer: TemplateLayer
    model_tier: ModelTier | None = None
    prefix_boundary_marker: str = ""
    static_sections: list[str] = Field(default_factory=list)
    estimated_cache_ratio: float = 0.0
    cache_hit_discount: float = 1.0
    cache_hit_cost_per_mtok: float = 0.0
    cache_miss_cost_per_mtok: float = 0.0
    ttl_seconds: int = 1209600
    is_active: bool = False

    @field_validator("estimated_cache_ratio")
    @classmethod
    def _ratio_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("estimated_cache_ratio must be in [0.0, 1.0]")
        return v

    model_config = {"extra": "forbid"}
```

### TokenBudget

```python
class TokenBudget(BaseModel):
    budget_id: str = Field(default_factory=lambda: str(uuid4()))
    scope: BudgetScope = BudgetScope.PER_INVOCATION
    layer: ArchitectureLayer
    model_tier: ModelTier
    max_input_tokens: int = 100_000
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    warning_threshold_pct: float = 0.9
    estimated_cost_cap: float | None = None
    is_enforced: bool = False

    @field_validator("warning_threshold_pct")
    @classmethod
    def _threshold_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("warning_threshold_pct must be in [0.0, 1.0]")
        return v

    model_config = {"extra": "forbid"}
```

### OptimizationAttempt

```python
class OptimizationAttempt(BaseModel):
    attempt_id: str = Field(default_factory=lambda: str(uuid4()))
    template_id: str
    source_variant_id: str | None = None
    result_variant_id: str | None = None
    optimization_type: OptimizationType = OptimizationType.TOKEN_REDUCTION
    token_count_before: int = 0
    token_count_after: int | None = None
    evaluation_run_ids: list[str] = Field(default_factory=list)
    status: AttemptStatus = AttemptStatus.PENDING
    rationale: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None

    model_config = {"extra": "forbid"}
```

### Storage Layout (constitution.md L28-32: no database runtime)

| Entity | Storage | Format | Location |
|--------|---------|--------|----------|
| PromptTemplate | In-memory index | Runtime only | Built from `importlib.resources.files("deviate.prompts")` |
| TemplateVariant | File per variant | JSON | `.deviate/prompt_eval/variants/{variant_id}.json` |
| Baseline | File per baseline | YAML | `.deviate/prompt_eval/baselines/{baseline_id}.yaml` |
| EvaluationRun | Append-Only JSONL | JSONL | `.deviate/prompt_eval/runs/runs.jsonl` |
| AssertionResult | Embedded in run records | JSON inline | Within EvaluationRun JSONL rows |
| EvaluationAssertion | Embedded in baseline files | YAML inline | Within Baseline YAML files |
| CachingProfile | File per profile | TOML | `.deviate/prompt_eval/caching_profiles/{profile_id}.toml` |
| TokenBudget | File per budget | TOML | `.deviate/prompt_eval/token_budgets/{budget_id}.toml` |
| OptimizationAttempt | Append-Only JSONL | JSONL | `.deviate/prompt_eval/optimizations/optimizations.jsonl` |

---

## State Transitions

### TemplateVariant.status State Machine

```
                    +----------+
                    |  DRAFT   |  <-- Initial state on creation
                    +----+-----+
                         |
                         | [evaluate() called]
                         v
                    +----------+
            +-------|EVALUATING|-------+
            |       +----+-----+       |
            |            |             |
    [all assertions     |     [any assertion
     pass, accepted]    |      fails, rejected]
            |            |             |
            v            v             v
    +----------+  +----------+
    |  ACTIVE  |  | REJECTED |  <-- Terminal
    +----+-----+  +----------+
         |
    [newer variant  |
     becomes ACTIVE]|
         |
         v
    +----------+
    |SUPERSEDED|  <-- Terminal
    +----------+
```

**Transition Rules:**
1. **DRAFT → EVALUATING**: Requires `content` to pass structural validation. Triggered by `OptimizationOrchestrator.evaluate(variant_id)`.
2. **EVALUATING → ACTIVE**: All assertions in all linked baselines pass. Previous ACTIVE variant for same `template_id` transitions to SUPERSEDED. `activated_at` set.
3. **EVALUATING → REJECTED**: Any assertion fails. Rationale recorded from OptimizationAttempt.
4. **ACTIVE → SUPERSEDED**: Another variant for same `template_id` transitions to ACTIVE. Automatic cascade.
5. No direct DRAFT → ACTIVE (must go through EVALUATING).

**Source Anchor**: HITL gate pattern (constitution.md L13: "No gate may be programmatically bypassed"). Micro-layer phase transitions (micro.py PHASE_MAP).

### EvaluationRun.status State Machine

```
    +----------+
    | PENDING  |  <-- Created with variant_id + baseline_id
    +----+-----+
         |
         | [runner.start()]
         v
    +----------+
    | RUNNING  |  <-- Agent invoked, prompt dispatched
    +----+-----+
         |
    +----+--------------------+
    |    |                    |
    v    v                    v
+---------+ +---------+   +---------+
|COMPLETED| |  FAILED |   |TIMED_OUT|  <-- All terminal
+---------+ +---------+   +---------+
```

**Transition Rules:**
1. **PENDING → RUNNING**: Agent invocation begins. `prompt_sent` populated.
2. **RUNNING → COMPLETED**: Agent returns successfully AND all assertions executed. `completed_at`, `duration_ms`, `raw_output` set.
3. **RUNNING → FAILED**: Agent returns but assertions fail. Matches `_run_green_phase` pattern (micro.py).
4. **RUNNING → TIMED_OUT**: Exceeds `AgentConfig.timeout` (config.py L13). Partial output captured per agent.py timeout handling.
5. No direct PENDING → terminal (must go through RUNNING).

**Source Anchor**: Agent invocation lifecycle (agent.py:234-294). Micro-layer error handling (micro.py:1531-1536).

### OptimizationAttempt.status State Machine

```
    +----------+
    | PENDING  |  <-- Optimization requested
    +----+-----+
         |
         | [orchestrator.start_optimization()]
         v
    +----------+
    |IN_PROGRESS| <-- Template being modified
    +----+-----+
         |
         | [result_variant created, evaluation triggered]
         v
    +------------------+
    |AWAITING_EVALUATION|
    +--------+---------+
             |
      +------+------+
      |             |
      v             v
+----------+  +----------+
| ACCEPTED |  | REJECTED |  <-- Terminal
+----------+  +----------+
```

**Source Anchor**: Gate-based approval (constitution.md L12, L13). TDD cycle train_feedback loop (micro.py:1367-1382).

---

## Data Flow

### Data Flow 1: Prompt Evaluation Cycle

```
STEP 1: BASELINE RESOLUTION
  Input:  baseline_id
  Action: BaselineManager.load(baseline_id) → reads .deviate/prompt_eval/baselines/{id}.yaml
  Output: Baseline entity with assertions + model_provider + template_ids
  Source: Promptfoo YAML config model (explore.md L265-283)

STEP 2: VARIANT SELECTION
  Input:  template_ids from baseline, variant_id (optional)
  Action: VariantManager.resolve(template_id) → finds ACTIVE variant, else latest DRAFT
  Output: TemplateVariant with content
  Source: FILE_REGISTRY explore.md L347-395

STEP 3: PROMPT ASSEMBLY
  Input:  TemplateVariant.content + baseline.query_vars
  Action: assembly.assemble_prompt(template_name, context, constitution_path, claude_path)
          → load_template() → inject_constitution() → regex substitution
          → For skill templates: _build_agent_prompt() str.replace("$ARGUMENTS", ...)
  Output: Fully resolved prompt string
  Source: assembly.py L53-62; macro.py L298-344; micro.py L121-133

STEP 4: AGENT INVOCATION
  Input:  assembled prompt + model_provider + model_name
  Action: AgentBackend.invoke(prompt, backend=..., timeout=...)
          → subprocess.Popen → invoke_blocking or invoke_streaming
  Output: (raw_output, HandoverManifest | None, duration_ms)
  Source: agent.py L234-294

STEP 5: ASSERTION EXECUTION
  Input:  raw_output + baseline.assertions
  Action: Deterministic assertions run locally; model-assisted assertions invoke agent with rubric prompt
  Output: list[AssertionResult]
  Source: Promptfoo assertion model (explore.md L286)

STEP 6: RESULT PERSISTENCE
  Input:  AssertionResult list + EvaluationRun metadata
  Action: Append EvaluationRun JSONL record to .deviate/prompt_eval/runs/runs.jsonl
  Output: EvaluationRun.status → COMPLETED or FAILED
  Source: Append-Only Ledger Protocol (constitution.md L10-11)

STEP 7: SCORE AGGREGATION
  Input:  All AssertionResults for this run
  Action: weighted_score = sum(r.score * r.assertion.weight for r in results)
  Output: overall_pass = weighted_score >= 0.8
  Source: Promptfoo scoring (explore.md L286)
```

### Data Flow 2: Template Optimization Loop

```
STEP 1: DISCOVERY
  Action: PromptRegistry.scan() → reads all 33 prompt files via importlib.resources
  Output: PromptTemplate index with token_count_estimated
  Source: explore.md L188-234, FILE_REGISTRY L347-395

STEP 2: BUDGET ANALYSIS
  Action: Compare token_count_estimated against TokenBudget for matching (scope, layer, model_tier)
  Output: list of (template_id, budget_exceeded_by)
  Source: TokenBudget + explore.md L314-317

STEP 3: CACHING ANALYSIS
  Action: Scan template structure for static vs dynamic sections using CachingProfile.prefix_boundary_marker
  Output: Cache efficiency score per template
  Source: Prefix caching best practices (explore.md L332-333)

STEP 4: OPTIMIZATION PROPOSAL
  Action: Create OptimizationAttempt (PENDING) → Create TemplateVariant (DRAFT) → Modify content
          → Compute token_count, update content_hash → Transition to EVALUATING
  Output: OptimizationAttempt + TemplateVariant (EVALUATING)
  Source: Template optimization best practices (explore.md L330-341)

STEP 5: EVALUATION GATE
  Action: Execute Prompt Evaluation Cycle for each baseline targeting this template
          → If any fails: REJECTED; If all pass: ACCEPTED, ACTIVE
  Output: Terminal status for OptimizationAttempt and TemplateVariant
  Source: HITL gate pattern (constitution.md L12)

STEP 6: PROMOTION
  Action: Previous ACTIVE variant → SUPERSEDED
          Write variant content to source-of-truth: src/deviate/prompts/auto/ or skills/ or governance/
  Output: Source template file updated on disk
  Source: FILE_REGISTRY explore.md L347-395

STEP 7: VERIFICATION (CI)
  Action: Run pytest tests/ -v (constitution.md L53)
          → test_prompt_assembly.py, test_auto_prompt_templates.py, test_skills.py, test_skill_installation.py
  Output: CI pass/fail; if fail, rollback variant
  Source: Testing protocols (constitution.md L47-63), Definition of Done (constitution.md L64-72)
```

### Data Flow 3: Prompt Assembly → Dispatch (End-to-End Trace)

```
src/deviate/prompts/           assembly.py             agent.py
+------------------+         +--------------+       +--------------+
| TemplateFile     | --read->| load_template|       | AgentBackend |
| (auto/red.md)    |         |              |       |              |
| 2,324 tokens     |         | +inject_     |       | invoke()     |
| <system_         |         |  constitution|       |  +---------+ |
|  instructions>   |         |              |       |  |Popen    | |
| ROLE_DEFINITION  |         | +regex_sub   |       |  |stdin=P  | |
| INVARIANTS...    |         |  ${VAR}->val |       |  |stdout=M | |
+------------------+         +------+-------+       |  +----+----+ |
                                    |                |       |     |
specs/constitution.md --------------+                |       |     |
CLAUDE.md --------------------------+                |       |     |
                                                     |       v     |
micro.py                                             |  Handover  |
_load_skill_content() --> skill variant ------------>|  Manifest  |
_build_agent_prompt() -> $ARGUMENTS->JSON ---------->|  (YAML)    |
                                    +--------------+            |
```

**Source Anchors**:
- Template file → `src/deviate/prompts/auto/red.md` (explore.md L351)
- `assembly.py` load/inject/substitute chain (explore.md L148-156)
- `micro.py` skill loading + $ARGUMENTS substitution (micro.py L105-133)
- `agent.py` invoke → HandoverManifest (agent.py L234-294)
- Constitution injection from `specs/constitution.md` (assembly.py L21-42)
- Prompt sizes: red.md = 2,324 tokens (explore.md L191)

---

## Source Registry

| ID | Type | Source / Path | Relevance Note |
|----|------|---------------|----------------|
| SRC-001 | Codebase_File | `src/deviate/prompts/assembly.py` | Core prompt assembly engine |
| SRC-002 | Codebase_File | `src/deviate/cli/micro.py` | Micro-layer prompt loading + $ARGUMENTS substitution |
| SRC-003 | Codebase_File | `src/deviate/cli/macro.py` | Macro-layer slim prompt building |
| SRC-004 | Codebase_File | `src/deviate/core/agent.py` | AgentBackend.invoke() — prompt dispatch to agent |
| SRC-005 | Codebase_File | `src/deviate/cli/__init__.py` | Init command: ${VARIABLE} resolution |
| SRC-006 | Explore_MD | `specs/003-prompt-optimization/explore.md` | Authoritative empirical input |
| SRC-007 | Constitution | `specs/constitution.md` | Non-negotiable governance rules |
| SRC-008 | Ecosystem | Promptfoo docs (explore.md L240-327) | Assertion model, caching, CI patterns — referenced, not adopted |
| SRC-009 | Industry | DeepSeek prefix caching (explore.md L312-321) | 50x-120x discount economics |
| SRC-010 | Test_File | `tests/test_meso/test_prompt_assembly.py` | Existing prompt assembly tests |
| SRC-011 | Test_File | `tests/test_meso/test_auto_prompt_templates.py` | Existing template validation tests |
| SRC-012 | Manifest | `pyproject.toml` | Dependencies and project metadata |
