# Implementation Tasks: `feat/adhoc/005-per-phase-model-configuration`

## Phase 1: Config Model — ModelPhaseMap + Resolution Helper
**Goal**: Add `ModelPhaseMap` Pydantic model with free-form `dict[str, str]`, mount it on `DeviateConfig`, implement the resolution order (phase-specific key → `default` key → `None`), and verify round-trip serialization.

### Tasks

- TSK-005-01: Add ModelPhaseMap model and model_config_resolve helper
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/test_state/test_config.py -v -k "model"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/test_state/test_config.py`
  - **Rationale**: **`config.py`** — add `ModelPhaseMap(BaseModel)` with `models: dict[str, str] = Field(default_factory=dict)`, mount `models: ModelPhaseMap = Field(default_factory=ModelPhaseMap)` on `DeviateConfig`, add module-level `model_config_resolve(phase: str) -> str | None` that checks `phase` key → `"default"` key → `None`, with phase name uppercasing for canonical matching. **`test_config.py`** — add `TestModelPhaseMap` class with tests for: empty dict default (AC-005-07), round-trip serialization, phase lookup returns known model (AC-005-02), unknown phase returns `None`, `default` key fallback (AC-005-01), empty string treated as no override (EDGE-005-empty), `default` excluded from phase key matching (EDGE-005-default-key).
  - **Details**:
    - **Red**: Write `test_model_config_defaults()` asserting empty `model_config.models == {}` on fresh `DeviateConfig()`. Write `test_model_config_round_trip()` — serialize to TOML (via `model_dump()`) and assert `models` key round-trips. Write `test_model_config_resolve_known_phase()` asserting `model_config_resolve("RED") == "fast-model"` when `{"RED": "fast-model"}` configured. Write `test_model_config_resolve_fallback_default()` asserting `model_config_resolve("GREEN") == "fast-model"` when `{"default": "fast-model"}` configured. Write `test_model_config_resolve_no_match()` asserting `None` when dict is empty. Write `test_model_config_resolve_empty_string()` asserting `None` when phase key has empty string value. Write `test_model_config_resolve_default_not_phase()` asserting `model_config_resolve("default")` returns `None` when only `{"default": "x"}` set and no `"DEFAULT"` key exists.
    - **Green**: Implement `ModelPhaseMap(BaseModel)` with `models: dict[str, str] = Field(default_factory=dict)` and `model_config = {"extra": "forbid"}`. Add `models` field on `DeviateConfig`: `models: ModelPhaseMap = Field(default_factory=ModelPhaseMap)`. Implement `model_config_resolve(phase: str) -> str | None` — normalize `phase` to uppercase, check `self.models.get(phase)` (returns `None` if value is `""`), then `self.models.get("default")`, then `None`. Add `_MODEL_CONFIG_NONE_SENTINEL` sentinel value to distinguish empty string from missing key.
    - **Refactor**: Ensure `extra = "forbid"` is set on `ModelPhaseMap`. Remove redundant sentinel; use Python dict's natural behavior: `.get()` returns `None` for missing key OR if value is `None`.
    - **Edge Cases**: Empty string phase value → treat as not set, fall through to default then None. Phase name `"default"` is excluded from phase-key matching — only matches if a literal `"DEFAULT"` entry exists (case-folded phase lookup won't find it). Missing `[models]` section in TOML → empty dict → all lookups return `None`. Concurrent access: config is read-only during TDD cycles.
    - **Acceptance**: All AC-005-01 through AC-005-04 resolved: default applies to all phases (01), phase override takes precedence over default (02), no config section → no model flag (03), droid backend uses model flag (04). EDGE-005-empty, EDGE-005-default-key resolved.
  - **Dependency**: none

---

## Phase 2: Agent Command Construction — `--model` Flag Injection
**Goal**: Extend `AgentBackend.invoke()` to accept an optional `model: str | None` parameter and inject `--model <id>` for backends that support it (opencode, droid), skip for claude. Keep `StubAgentBackend` in sync.

### Tasks

- TSK-005-02: Add model parameter to AgentBackend.invoke() and inject --model flag
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `pytest tests/test_core/test_agent.py -v -k "model_flag"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/core/agent.py`
    - `tests/test_core/test_agent.py`
  - **Rationale**: **`agent.py`** — add `model: str | None = None` parameter to `AgentBackend.invoke()` signature. After `cmd = backend_cmd.split()`, if `model` is non-None and `backend_name` is in `{"opencode", "droid"}`, append `["--model", model]` to `cmd`. For `claude` backend and any unknown backend, skip model injection. Update `StubAgentBackend.invoke()` to accept the same `model` parameter (currently no-op, update signature). **`test_agent.py`** — add `TestModelFlagInjection` class with tests for: model flag appears for opencode backend (AC-005-01, AC-005-02), model flag appears for droid backend (AC-005-04), no model flag for claude backend (AC-005-05), no model flag when model is `None`, no model flag when model is empty string, model is a single shell argument (no splitting on spaces), phase override takes precedence over default (AC-005-02).
  - **Details**:
    - **Red**: Write `test_model_flag_opencode()` — mock `subprocess.Popen`, call `backend.invoke(prompt, model="deepseek-v4-flash")`, assert `--model deepseek-v4-flash` in `cmd`. Write `test_model_flag_droid()` — same with `backend="droid"`. Write `test_no_model_flag_claude()` — invoke with `model="x"` and `backend="claude"`, assert `--model` NOT in `cmd`. Write `test_no_model_flag_when_none()` — invoke with `model=None`, assert no `--model`. Write `test_no_model_flag_when_empty()` — invoke with `model=""`, assert no `--model`. Write `test_model_flag_single_argument()` — invoke with `model="deepseek-v4-flash"`, assert `["--model", "deepseek-v4-flash"]` not `["--model=deepseek-v4-flash"]`.
    - **Green**: Add `model` param to `AgentBackend.invoke()`. After `cmd = backend_cmd.split()`, add: `if model and backend_name in ("opencode", "droid"): cmd.extend(["--model", model])`. Update `StubAgentBackend.invoke()` to accept `**kwargs` or explicit `model` param and ignore it. Update `StubAgentBackend` to match `AgentBackend.invoke()` signature (same parameters).
    - **Refactor**: Extract model-injection logic into `_inject_model_flag(cmd, model, backend)` for testability. Ensure `BACKEND_COMMANDS` dict remains the single source of truth for backend→command mapping.
    - **Edge Cases**: Model identifier with spaces (TOML quoted string → single shell arg → passes through). Model identifier with special chars (quotes, backticks) — subprocess.Popen passes raw without shell interpretation. Claude backend silently ignores — no error. Unknown backend (not in `{"opencode", "droid", "claude"}`) raises `AgentBinaryNotFoundError` before model injection.
    - **Acceptance**: AC-005-01 (default model → `--model`), AC-005-02 (phase override → different `--model`), AC-005-04 (droid backend → `--model`), AC-005-05 (claude backend → no `--model`). Backend support matrix enforced at command construction, not config loading.
  - **Dependency**: TSK-005-01

---

## Phase 3: Micro-Layer Threading — Model Resolution in Phase Runners
**Goal**: Add `_resolve_model_config()` helper in `micro.py`, thread resolved model through `_invoke_agent()` to `AgentBackend.invoke(model=...)`, update all phase runners to pass their phase name.

### Tasks

- TSK-005-03: Thread per-phase model resolution through micro.py agent invocations
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/cli/test_micro_model.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/cli/test_micro_model.py`
  - **Rationale**: **`micro.py`** — add `_resolve_model_config(root: Path, phase: str) -> str | None` that loads `.deviate/config.toml` → `tomllib.load()` → constructs `DeviateConfig` → calls `model_config_resolve(phase)`. Add `model` parameter to `_invoke_agent()` and pass through to `backend.invoke(model=model)`. Update `_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`, `_run_execute_phase` to call `_resolve_model_config()` and pass result. **`test_micro_model.py`** — integration-style tests verifying the entire chain from config file to command array for each phase (AC-005-01, AC-005-02, AC-005-08), with default fallback, phase override, and missing config scenarios.
  - **Details**:
    - **Red**: Write `test_red_uses_default_model()` — create temp `.deviate/config.toml` with `[models]\ndefault = "fast/model"`, mock `subprocess.Popen` on `opencode run`, call `_run_red_phase(...)`, assert `--model fast/model` in `cmd`. Write `test_judge_uses_override_model()` — config has `default = "fast/model"\njudge = "premium/model"`, assert JUDGE phase uses `premium/model` while RED uses `fast/model` (AC-005-08). Write `test_no_models_no_flag()` — config has no `[models]` section, assert no `--model` in command (AC-005-03). Write `test_execute_resolves_models()` — EXECUTE phase runner loads and passes model. Write `test_missing_config_toml_model_not_none()` — no `.deviate/config.toml`, assert no crash and no `--model`. Write `test_yellow_reuses_green_model()` (YELLOW uses same model as GREEN per defensive exclusion) — assert GREEN and YELLOW both resolve to the same model.
    - **Green**: Implement `_resolve_model_config(root: Path, phase: str) -> str | None` — read `.deviate/config.toml` via `tomllib.load()`, validate as `DeviateConfig.model_validate()`, call `model_config_resolve(phase)`. Wrap TOML parsing in try/except returning `None` on error. Thread `model` param through `_invoke_agent()` → `backend.invoke(model=model)`. Each phase runner calls `_resolve_model_config(root=Path.cwd(), phase="RED")` etc. and passes to `_invoke_agent()`. Update `_invoke_agent()` call sites in `_finish_tdd_cycle()`, `_dispatch_task()`, etc.
    - **Refactor**: Extract config loading from `_resolve_model_config` into a private `_load_deviate_config(path)` helper that can be reused by meso/macro layers. Ensure `_resolve_model_config` returns `None` on any failure (missing file, parse error, validation error) so agent invocation degrades gracefully.
    - **Edge Cases**: Missing `.deviate/` directory → `tomllib` raises `FileNotFoundError` → caught, returns `None`. Malformed TOML → `tomllib.TOMLDecodeError` → caught, returns `None`. Phase name case mismatch — resolution helper upper-cases the phase name before dict lookup. Empty model value in TOML → treated as none, falls through. Claude backend configured but model config present → model config resolved but backend strips `--model` at invocation time in Phase 2.
    - **Acceptance**: AC-ADH-005-01 (default applies to all), AC-ADH-005-02 (phase override works), AC-ADH-005-03 (both backends supported — flag construction at Phase 2, config loading here), AC-ADH-005-08 (TDD cycle uses phase-specific models with default fallback). YELLOW reuses GREEN model per defensive exclusion.
  - **Dependency**: TSK-005-01, TSK-005-02

---

## Phase 4: Meso- and Macro-Layer Threading
**Goal**: Thread per-phase model resolution into `_invoke_agent_phase()` in both `meso.py` and `macro.py` using the same `_resolve_model_config()` pattern.

### Tasks

- TSK-005-04: Thread model resolution through meso.py and macro.py agent invocations
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `pytest tests/cli/test_meso_model.py tests/cli/test_macro_model.py -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/cli/meso.py`
    - `src/deviate/cli/macro.py`
    - `tests/cli/test_meso_model.py`
    - `tests/cli/test_macro_model.py`
  - **Rationale**: **`meso.py`** — in `_invoke_agent_phase()`, before creating `AgentBackend()`, load `DeviateConfig` from `.deviate/config.toml`, resolve model for the phase via `model_config_resolve(phase)`, pass to `backend.invoke(model=model, cwd=cwd)`. **`macro.py`** — same pattern: load config, resolve model, pass to `backend.invoke(model=model)`. **`test_meso_model.py`** — mock subprocess, verify PLAN phase injects `--model` when configured. **`test_macro_model.py`** — verify EXPLORE/RESEARCH/PRD/SHARD phases resolve models.
  - **Details**:
    - **Red**: Write `test_meso_plan_uses_configured_model()` — create temp `.deviate/config.toml` with `[models]\nplan = "deepseek-v4-pro"`, mock `subprocess.Popen` on `opencode run`, call `_invoke_agent_phase("plan", contract)`, assert `--model deepseek-v4-pro` in cmd. Write `test_meso_task_uses_default_model()` — config with `default = "deepseek-v4-flash"`, call `_invoke_agent_phase("tasks", contract)`, assert `--model deepseek-v4-flash`. Write `test_meso_no_model_when_not_configured()` — no `[models]` section, assert no `--model`. Write `test_macro_phase_uses_model()` — config with `[models]\nprd = "qwen3.7-plus"`, call macro's `_invoke_agent_phase("prd", contract)`, assert `--model qwen3.7-plus`. Write `test_macro_no_model_when_absent()` — no config section → no `--model`.
    - **Green**: In `meso.py:_invoke_agent_phase()`, add: load config from `.deviate/config.toml`, resolve model for `phase` param, pass `model=resolved` to `backend.invoke(prompt, cwd=cwd, model=model)`. In `macro.py:_invoke_agent_phase()`, same pattern — load config, resolve model, pass to `backend.invoke(prompt, model=model)`. Both should share the config loading logic — consider extracting to `_common.py` or a `ConfigLoader` utility.
    - **Refactor**: Extract config loading to a shared helper in `deviate/cli/_common.py` or `deviate/state/config.py` to avoid duplication across micro/meso/macro layers.
    - **Edge Cases**: The config path resolution — meso runs inside worktrees, so `.deviate/config.toml` is relative to worktree root (not `Path.cwd()` if called from outside). Both `meso.py` and `macro.py` use `Path(".deviate/config.toml")` which resolves relative to CWD — same as micro.py. Ensure consistency.
    - **Acceptance**: AC-ADH-005-01 (default model for all phases including meso/macro), AC-ADH-005-02 (phase override works for plan/tasks/prd/explore/research/shard), AC-ADH-005-03 (backend agnostic — model flag construction is Phase 2's responsibility).
  - **Dependency**: TSK-005-01, TSK-005-02

---

## Phase 5: Documentation and Constitutional Alignment
**Goal**: Update `specs/constitution.md` `Model Tiering` section and `AGENTS.md` to reference the new config-driven model routing mechanism.

### Tasks

- TSK-005-05: Update constitution and AGENTS.md to document model routing config
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Test Strategy**: (none — documentation only)
  - **Verification**: `grep -q 'config-driven model routing\|\[models\]' specs/constitution.md AGENTS.md`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `specs/constitution.md`
    - `AGENTS.md`
  - **Rationale**: **`constitution.md`** — update the `Model Tiering` subsection under `[ARCHITECTURAL_PRINCIPLES]` to reference the new `.deviate/config.toml [models]` section as the enforcement mechanism for the declared tiering strategy. **`AGENTS.md`** — add a brief note on the available `[models]` configuration option under the DeviaTDD Phase Architecture section, referencing the resolution order. No code changes.
  - **Details**:
    - **Implementation**: In `constitution.md`, update `Model Tiering` bullet: append `(enforced via .deviate/config.toml [models] section — see model_config_resolve() for resolution order)` to the existing tiering description. In `AGENTS.md`, under the DeviaTDD Phase Architecture → Model Routing Rationale section, add a note: `"Model routing is configurable per-phase via the [models] section in .deviate/config.toml. Resolution order: phase-specific key → default key → no model flag (backend-native default)."`
    - **Acceptance**: Constitution `Model Tiering` section references the config mechanism. AGENTS.md documents the `[models]` section and resolution order.
  - **Dependency**: none

---

## Phase 6: E2E Verification
**Goal**: End-to-end test verifying the full model routing integration — init creates config with no `[models]` section (backward compatible), and the demonstration paths from the spec execute correctly.

### Tasks

- TSK-005-06: End-to-end verification of per-phase model routing
  - **Type**: Infra_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/test_model_routing.bats`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/e2e/test_model_routing.bats`
  - **Rationale**: **`test_model_routing.bats`** — bats integration test that: runs `deviate init` in temp dir, verifies no `[models]` section exists, creates a minimal `[models]` section, runs `deviate red post ...` with mocked agent, verifies command uses configured model. Adapted from the demonstration paths in the spec. Also add a pytest integration test verifying `deviate init` creates valid config with empty models section.
  - **Details**:
    - **Implementation**: Write `tests/e2e/test_model_routing.bats` with test cases: (1) `deviate init` creates config without `[models]` — backward compatible check. (2) Appending `[models]\ndefault = "test/model"` makes RED phase resolve to `test/model`. (3) Full demonstration path from spec: `[models]\ndefault = "v4-flash"\nplan = "v4-pro"\njudge = "v4-pro"`. Write `tests/test_integration/test_init_export_cycle.py` update to verify the init-scaffolded config.toml is valid and has no `[models]` section.
    - **Acceptance**: E2E test passes. Integration test confirms `deviate init` produces backward-compatible config.
  - **Dependency**: TSK-005-03, TSK-005-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6

**Critical Dependency Chains**:
- TSK-005-03 depends on TSK-005-01 (for `model_config_resolve`) and TSK-005-02 (for `AgentBackend.invoke()` model parameter)
- TSK-005-04 depends on TSK-005-01 and TSK-005-02 (same dependencies as 005-03 — the `model_config_resolve` helper and `backend.invoke(model=...)` signature)
- TSK-005-06 depends on TSK-005-03 and TSK-005-04 (end-to-end integration)

**Risk Hotspots**:
- **Phase name case normalization**: Config keys `[models]` are case-sensitive. The resolution helper uppercases phase names before lookup. If a user writes `[models]\nred = "model"` (lowercase `red`), the uppercased lookup `RED` won't match, and it falls through to `default`. Mitigation: document that keys must match canonical uppercase phase names.
- **Config loading divergence**: micro/meso/macro layers may resolve `.deviate/config.toml` differently. Extract shared helper to ensure consistent loading pattern.
- **Claude backend conflict**: If user configures `[models]` but runs with `--agent claude`, the model config is silently ignored. This is documented behavior in defensive exclusions but may confuse users.

**Merge Conflict Boundaries**:
- `src/deviate/state/config.py` touched by TSK-005-01
- `src/deviate/core/agent.py` touched by TSK-005-02
- `src/deviate/cli/micro.py` touched by TSK-005-03
- `src/deviate/cli/meso.py`, `src/deviate/cli/macro.py` touched by TSK-005-04
- `tests/test_state/test_config.py` touched by TSK-005-01
- `tests/test_core/test_agent.py` touched by TSK-005-02

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.

## Universal Model Config Access (ALL PHASES)

- All config loading via `tomllib.load()` MUST be wrapped in try/except returning `None` on `FileNotFoundError`, `TOMLDecodeError`, or any `ValidationError`.
- Model resolution output is `str | None`. The caller (micro/meso/macro `_invoke_*`) passes it to `AgentBackend.invoke(model=...)`. The backend decides whether to inject `--model` based on backend type.
- Uppercase phase names are the canonical lookup keys. The `model_config_resolve()` helper handles normalization.
