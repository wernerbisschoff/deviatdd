# Data Model: Prompt Optimization
<spec_version>0.2.0</spec_version>

---

> **HITL Gate 1 Decisions** (2026-06-17):
> - **Git-native variant management**: No TemplateVariant entity. All template changes go through the TDD cycle; git log = lineage.
> - **PromptFoo is a thin wrapper**: Single-file YAML generator + subprocess call. No Baseline/EvaluationRun entities — deferred until concrete need emerges.
> - **Advisory token budgets**: TokenBudget.is_enforced removed — budgets are warnings, not blocks.
> - **Programmatic prefix assembly**: No shared/prefix.md file. Static prefix built in code by assembly.py.
> - **Layer 1: $ARGUMENTS already at tail**: Confirmed by grep audit. Layer 1 scope reduced to ensuring consistency.

---

## Entity Definitions

### PromptTemplate
- **Source-of-truth**: `src/deviate/prompts/` directory tree, indexed via `importlib.resources.files("deviate.prompts")`
- **Lifecycle owner**: `PromptRegistry` (builds in-memory index from importlib resources)

| Attribute | Type | Invariant | Source Anchor |
|-----------|------|-----------|---------------|
| `template_id` | `str` | Unique identifier: `auto/red`, `skills/deviate-research`, `governance/claudemd_seed` | FILE_REGISTRY explore.md:347-395 |
| `file_path` | `str` | Package-relative path within `src/deviate/prompts/` | assembly.py:12 `resources.files("deviate.prompts.auto")` |
| `layer` | `TemplateLayer` | One of: `auto`, `skill`, `governance`, `seed` | explore.md L128-143 |
| `template_type` | `str` | Structural section: `system_instructions`, `role_definition`, `invariants`, `execution_sequence`, etc. | explore.md L131-142 |
| `phase` | `str \| None` | Mapped DeviaTDD phase(s) | explore.md L188-234 |
| `model_tier` | `ModelTier \| None` | Assigned model per constitution tiering | constitution.md L15 |
| `token_count_estimated` | `int` | Estimated token count from explore.md | explore.md L188-234 |
| `substitution_mode` | `SubstitutionMode` | Must match layer: `regex_curly` for auto, `str_replace_ARGUMENTS` for skill, `regex_dollar` for seed | explore.md L176-184 |
| `has_yaml_frontmatter` | `bool` | True iff layer = `skill` | explore.md L139-142 |
| `content_hash` | `str` | SHA-256 of raw template content | Promptfoo cache key pattern explore.md L299 |
| `version` | `str` | Semver from YAML frontmatter (skill templates only) | explore.md L139 |

**Invariants**:
- `template_id` MUST be unique (1:1 with filesystem path)
- `content_hash` MUST be recomputed on every content mutation
- If `layer == "skill"` then `has_yaml_frontmatter` MUST be True and `version` MUST be set
- `substitution_mode` MUST match layer expectations (explore.md L178-184)

*(Baseline, EvaluationRun, EvaluationAssertion, AssertionResultItem, and EvalSummary entities are deferred — not part of this epic. PromptFoo Layer 3 is a single eval.py file that generates a canned YAML config inline and shells out to `npx promptfoo eval`. No persistent data models needed.)*

### CachingProfile
- **Source-of-truth**: `.deviate/prompt_eval/caching_profiles/{profile_id}.toml`
- **Lifecycle owner**: `CacheOptimizer`

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
| `is_active` | `bool` | Whether profile is currently used by the cache assembler | — |

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
| `max_input_tokens` | `int` | Advisory cap on input tokens; MUST be > 0 | explore.md L188-234 |
| `max_output_tokens` | `int \| None` | Advisory cap on output tokens, None = unbounded | — |
| `max_total_tokens` | `int \| None` | Aggregate cap for scope, None = unbounded | — |
| `warning_threshold_pct` | `float` | In [0.0, 1.0]; % of max triggering warning | — |
| `estimated_cost_cap` | `float \| None` | Optional USD cost cap, None = unbounded | explore.md L314-321 |

**Invariants**:
- `max_input_tokens` MUST be > 0
- Composite key: `(scope, layer, model_tier)` is unique
- `warning_threshold_pct` MUST be in [0.0, 1.0]
- All budgets are advisory — exceeding them produces warnings in `deviate prompt stats`, never blocks assembly (HITL Gate 1 decision)

---

## Entity Relationship Graph

| Entity | Relationships |
|--------|--------------|
| PromptTemplate | Indexed record — no managed relationships |
| CachingProfile | 1:1 per `(layer, model_tier)` — applied to prompt assembly at runtime |
| TokenBudget | 1:1 per `(scope, layer, model_tier)` — advisory warnings only |

**Notes**:
- No Baseline/EvaluationRun entities (deferred — see design.md Layer 3)
- No TemplateVariant entity (git-native — decided at HITL Gate 1)
- No OptimizationAttempt entity (auto optimization deferred to future epic)
- No JSONL-persisted entities in this epic; all state is in-memory or TOML files

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

*(Baseline, EvaluationAssertion, EvaluationRun, AssertionResultItem, and EvalSummary Pydantic models are deferred — see design.md Layer 3. These entities would be added in a future epic if PromptFoo usage expands.)*

### CachingProfile

```python
class CachingProfile(BaseModel):
    """Configures cache optimization parameters per (layer, model_tier)"""
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    layer: TemplateLayer
    model_tier: ModelTier | None = None
    prefix_boundary_marker: str = ""
    static_sections: list[str] = Field(default_factory=list)
    estimated_cache_ratio: float = 0.0
    cache_hit_discount: float = 1.0
    cache_hit_cost_per_mtok: float = 0.0
    cache_miss_cost_per_mtok: float = 0.0
    ttl_seconds: int = 1209600  # 14 days (PromptFoo default)
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
    """Advisory token caps per (scope, layer, model_tier) — warnings only (HITL Gate 1)"""
    budget_id: str = Field(default_factory=lambda: str(uuid4()))
    scope: BudgetScope = BudgetScope.PER_INVOCATION
    layer: ArchitectureLayer
    model_tier: ModelTier
    max_input_tokens: int = 100_000
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    warning_threshold_pct: float = 0.9
    estimated_cost_cap: float | None = None

    @field_validator("warning_threshold_pct")
    @classmethod
    def _threshold_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("warning_threshold_pct must be in [0.0, 1.0]")
        return v

    model_config = {"extra": "forbid"}
```

### Storage Layout (constitution.md L28-32: no database runtime)

| Entity | Storage | Format | Location |
|--------|---------|--------|----------|
| PromptTemplate | In-memory index | Runtime only | Built from `importlib.resources.files("deviate.prompts")` |
| CachingProfile | File per profile | TOML | `.deviate/prompt_eval/caching_profiles/{profile_id}.toml` |
| TokenBudget | File per budget | TOML | `.deviate/prompt_eval/token_budgets/{budget_id}.toml` |

---

## State Transitions

*No state machines in this epic. EvaluationRun state machine (PENDING → RUNNING → COMPLETED/FAILED) is deferred until PromptFoo usage expands to multi-baseline evaluation.*

---

## Data Flow

*PromptFoo Data Flow (baseline resolution → config gen → subprocess eval → export → parse → persist → view) is deferred — see design.md Layer 3. The current thin wrapper generates a canned config inline, shells out to `npx promptfoo eval`, and prints stdout.*

### Data Flow 2: Template Optimization Loop (Cache + Validator)

```
STEP 1: DISCOVERY
  Action: PromptRegistry.scan() → reads all 33 prompt files via importlib.resources
  Output: PromptTemplate index with token_count_estimated (from tiktoken)
  Source: explore.md L188-234, FILE_REGISTRY L347-395

STEP 2: BUDGET ANALYSIS
  Action: Compare token_count_estimated against TokenBudget for matching (scope, layer, model_tier)
  Output: list of (template_id, budget_warning_pct) — advisory only
  Source: TokenBudget model (advisory — HITL Gate 1 decision)

STEP 3: CACHING ANALYSIS
  Action: Scan template structure for static vs dynamic sections using
          CachingProfile.prefix_boundary_marker
  Output: Cache efficiency score per template
  Source: Prefix caching best practices (explore.md L332-333)

STEP 4: CACHE-OPTIMIZED ASSEMBLY
  Action: assemble_cache_optimized_prompt() builds three-segment prompt:
          (1) Static preamble — constitution + CLAUDE.md + system_instructions + role + invariants
          (2) Phase-specific — procedural instructions for this phase
          (3) Volatile context — task metadata, diff blocks, runtime vars
  Output: Fully resolved prompt string with cacheable prefix
  Source: Three-segment assembly (design.md Recommended Architecture)

STEP 5: VERIFICATION (CI)
  Action: Run pytest tests/ -v + ruff (constitution.md L53)
          → test_prompt_assembly.py, test_cache_aware.py, test_validator.py
          → @pytest.mark.prompt_quality marker runs validator checks
  Output: CI pass/fail
  Source: Testing protocols (constitution.md L47-63)
```

---

## Source Registry

| ID | Type | Source / Path | Relevance Note |
|----|------|---------------|----------------|
| SRC-001 | Codebase_File | `src/deviate/prompts/assembly.py` | Core prompt assembly engine |
| SRC-002 | Codebase_File | `src/deviate/cli/micro.py` | Micro-layer prompt loading + $ARGUMENTS substitution |
| SRC-003 | Codebase_File | `src/deviate/cli/macro.py` | Macro-layer slim prompt building |
| SRC-004 | Codebase_File | `src/deviate/core/agent.py` | AgentBackend.invoke() — prompt dispatch |
| SRC-005 | Codebase_File | `src/deviate/cli/__init__.py` | Init command: ${VARIABLE} resolution |
| SRC-006 | Explore_MD | `specs/003-prompt-optimization/explore.md` | Authoritative empirical input |
| SRC-007 | Constitution | `specs/constitution.md` | Non-negotiable governance rules |
| SRC-008 | Ecosystem | PromptFoo docs (promptfoo.dev) | CLI commands, assertion model — referenced for thin wrapper config generation |
| SRC-009 | Industry | DeepSeek prefix caching (explore.md L312-321) | 50x-120x discount economics |
| SRC-010 | Test_File | `tests/test_meso/test_prompt_assembly.py` | Existing prompt assembly tests |
| SRC-011 | Test_File | `tests/test_meso/test_auto_prompt_templates.py` | Existing template validation tests |
| SRC-012 | Manifest | `pyproject.toml` | Dependencies and project metadata |
