## Plan Summary
- **Issue**: ISS-ADH-005 — Per-Phase Model Configuration with Configurable Model Routing
- **Implementation Strategy**: Add a `ModelPhaseMap` free-form dict to `DeviateConfig` with a reserved `default` key, extend `AgentBackend.invoke()` with an optional `model` parameter that injects `--model <id>` for opencode/droid backends, then thread per-phase model resolution through every agent-invocation path across micro, meso, and macro layers.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Workstation Mapping
- **`src/deviate/state/config.py`**: Add `ModelPhaseMap` as a stateless Pydantic model with a single `models: dict[str, str]` field (free-form, extra keys allowed). Mount `models: ModelPhaseMap = Field(default_factory=ModelPhaseMap)` on `DeviateConfig`.
  - **Current State**: `DeviateConfig` has no model routing fields. TOML serialization is ad-hoc via `ProfileConfig.to_toml_string()` but `DeviateConfig` itself has no `to_toml_string()` method.
  - **Changes Required**: Add `ModelPhaseMap` model. Add `models` field to `DeviateConfig`. Add `to_toml_string()` to `DeviateConfig` (or a `to_toml()` method) that serializes all fields including `models`. Add `model_config_resolve(phase: str) -> str | None` helper that implements the resolution order: phase-specific key → `default` key → `None`.
  - **Integration Surface**: Consumed by all agent-invocation paths (micro, meso, macro layers) and by `cli/__init__.py` for init config generation.

- **`src/deviate/core/agent.py`**: Extend `AgentBackend.invoke()` signature to accept `model: str | None = None`.
  - **Current State**: `invoke()` accepts `(prompt, backend, timeout, output_callback, cwd)`. Command array is `backend_cmd.split()` — no model flag injection.
  - **Changes Required**: Add `model` param. When non-None and backend is opencode or droid, append `["--model", model]` to `cmd`. For claude backend, skip model injection. Update `StubAgentBackend.invoke()` signature to match.
  - **Integration Surface**: Called from `micro.py:_invoke_agent()`, `meso.py:_invoke_agent_phase()`, `macro.py:_invoke_agent_phase()`.

- **`src/deviate/cli/micro.py`**: Thread per-phase model resolution into `_invoke_agent()` and all phase runners.
  - **Current State**: `_invoke_agent()` accepts `(prompt, c, backend_name, task_id, phase, output_callback)`. Each phase runner (`_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`, `_run_execute_phase`) calls `_invoke_agent()` with `backend_name=agent or "opencode"`. `_resolve_agent_config()` reads agent backend from `.deviate/config.toml [agent] backend`. No model awareness.
  - **Changes Required**: Add a `_resolve_model_config(root, agent_backend, phase) -> str | None` helper that loads `DeviateConfig` from `.deviate/config.toml` and resolves `model_config_resolve(phase)`. Pass the resolved model through `_invoke_agent()` to `AgentBackend.invoke()`. Update all phase runners to pass the phase name for model resolution. Update `run_command()` to read models config and pass it through.
  - **Integration Surface**: All TDD phase entry points and the execute phase.

- **`src/deviate/cli/meso.py`**: Thread per-phase model resolution into `_invoke_agent_phase()`.
  - **Current State**: `_invoke_agent_phase()` creates `AgentBackend()` and calls `backend.invoke(prompt, cwd=cwd)`. No model awareness.
  - **Changes Required**: Load `DeviateConfig`, resolve model for the phase, pass to `backend.invoke(model=...)`.
  - **Integration Surface**: `_plan_pre()` → `_invoke_agent_phase("plan", ...)`, `_tasks_pre()` → `_invoke_agent_phase("tasks", ...)`, `_meso_run()`.

- **`src/deviate/cli/macro.py`**: Thread per-phase model resolution into `_invoke_agent_phase()`.
  - **Current State**: `_invoke_agent_phase()` creates `AgentBackend()` and calls `backend.invoke(prompt)`. No model awareness.
  - **Changes Required**: Same pattern as meso.py — load config, resolve model, pass to `invoke()`.
  - **Integration Surface**: `_cycle_phase()`, `_macro_run()`.

- **`src/deviate/prompts/assembly.py`**: Load model config in `assemble_prompt` context.
  - **Current State**: `assemble_prompt(template_name, context, constitution_path)` — the `context` dict carries phase metadata but not model config.
  - **Changes Required**: No code changes needed for the core MVP — model config is resolved at the CLI layer, not in prompt assembly. Future enhancement: inject model mappings into context for template-based customization.
  - **Integration Surface**: N/A for this issue.

- **`.deviate/config.toml`**: Document `[models]` section schema.
  - **Current State**: Schema TOML section exists for `[agent]`, `[profile]`, etc. No `[models]` section.
  - **Changes Required**: No file edit — this issue documents the schema in code (via `ModelPhaseMap` TOML serialization) and tests. Future `deviate init` templates can include a commented-out `[models]` section.

## Implementation Strategy
- **Phase 1**: Config model — `ModelPhaseMap` Pydantic model + `models` field on `DeviateConfig` + model resolution helper
  - **Files**: `src/deviate/state/config.py`
  - **Approach**: Add `ModelPhaseMap(BaseModel)` with `models: dict[str, str] = Field(default_factory=dict)`. Add `model_config_resolve(phase: str) -> str | None` module-level function. Add `models` field to `DeviateConfig`.
  - **Verification**: `pytest tests/test_state/test_config.py -v` — existing tests still pass; new test for model config defaults and phase lookup

- **Phase 2**: Agent command construction — extend `invoke()` with model parameter
  - **Files**: `src/deviate/core/agent.py`
  - **Approach**: Add `model: str | None = None` to `invoke()`. After building `cmd`, if `model` is non-None and backend supports it (opencode, droid), append `["--model", model]`. For claude backend, skip. Update `StubAgentBackend`.
  - **Verification**: `pytest tests/core/test_agent.py -v` — new unit tests for command construction with/without model

- **Phase 3**: Micro-layer threading — model resolution in `_invoke_agent()` and phase runners
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Add `_resolve_model_config()` that reads `.deviate/config.toml`, loads `DeviateConfig`, calls `model_config_resolve(phase)`. Thread the resolved model through `_invoke_agent()` → `AgentBackend.invoke()`. Each phase runner passes its phase name.
  - **Verification**: `pytest tests/cli/test_micro.py -v` — new tests for per-phase model routing

- **Phase 4**: Meso- and macro-layer threading
  - **Files**: `src/deviate/cli/meso.py`, `src/deviate/cli/macro.py`
  - **Approach**: Same pattern — load config, resolve model for the phase, pass to `backend.invoke(model=...)`.
  - **Verification**: Updated integration tests

- **Phase 5**: Documentation alignment
  - **Files**: `specs/constitution.md`, `AGENTS.md`
  - **Approach**: Update `Model Tiering` section in constitution to reference the new config mechanism. Add brief note in AGENTS.md.
  - **Verification**: Manual review

## Data Flow Analysis
1. **Config Loading**: `run_command()` or `_invoke_agent_phase()` loads `.deviate/config.toml` → `tomllib.load()` → `DeviateConfig.model_validate()` → `models` dict available in memory.
2. **Model Resolution**: `model_config_resolve(phase)` checks `models[phase]` → if None, checks `models["default"]` → if None, returns None (no model flag).
3. **Command Assembly**: `AgentBackend.invoke(model=resolved_model)` → if model is non-None and backend is opencode/droid, `cmd += ["--model", model]` → `subprocess.Popen(cmd)`.
4. **Backend Routing**: If backend is claude, the model param is silently ignored (no flag support). If backend is invalid (unknown), `AgentBinaryNotFoundError` is raised before model injection.
5. **No config → no model**: If `.deviate/config.toml` doesn't exist or has no `[models]` section, the resolution returns `None` → no `--model` flag → backend uses its native default.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| TOML parsing failure corrupts `[models]` section silently | Low — malformed TOML raises `tomllib.TOMLDecodeError`; caught and logged, falls back to empty dict | Low | Always wrap TOML parsing in try/except; empty dict = no model override |
| Phase name case mismatch (e.g., "red" vs "RED") | Medium — user writes lowercase key but lookup is uppercase | Medium | Document that keys match canonical phase names (RED, GREEN, PLAN etc.); resolution helper normalizes to uppercase |
| Backend-specific flag syntax diverges | Low — both opencode and droid use `--model` | Low | Confirmed by reading opencode and droid CLI source; if divergence occurs, use backend-specific flag map |
| Claude backend receives `--model` flag and breaks | High — CLI binary may error on unknown flag | Medium | Guard clause: if backend is "claude", skip model injection entirely regardless of model value |
| Model config loaded but agent backend is overridden via CLI `--agent` flag | Low — model config is per-phase, agent backend is per-invocation; they're orthogonal | Low | Model resolution does not depend on agent backend selection; model flag only appended if backend supports it |
| `default` key used as a phase name in lookup | Low — `default` is reserved and excluded from phase matching | Low | Documented in spec; resolution helper explicitly skips "default" when matching phase keys |

## Integration Points
- **`AgentBackend.invoke(model=...)`**: The contract between CLI layers (micro/meso/macro) and the agent layer. Accepts `str | None`. If non-None and backend supports it, injects `--model`. The caller is responsible for resolving the model string from config.
- **`tomllib.load()` on `.deviate/config.toml`**: Standard library TOML parser. The file must be valid TOML. The `[models]` section is a flat `key = "value"` mapping where keys are phase names (or `default`) and values are model identifiers.
- **`_resolve_model_config()`**: A helper function (or method on `DeviateConfig`) that encapsulates the resolution logic: `config.models.get(phase, config.models.get("default"))`. Returns `None` when neither key exists.

## Constitutional Alignment
- **Architecture**: Aligns with the `Model Tiering` section of the constitution, which declares V4 Flash for high-frequency phases, V4 Pro for compliance/planning, Qwen 3.7+ for architecture. This issue makes that tiering enforceable by adding a config-driven mechanism.
- **Testing**: Unit tests for `ModelPhaseMap` serialization (pydantic round-trip, TOML round-trip). Unit tests for command construction with/without model flag across opencode/droid/claude backends. Unit tests for phase resolution with default fallback. Integration tests for micro-layer model routing.
- **Git Isolation**: No git state mutation in model resolution. Config reads are read-only. All changes are in source files or new test files, committed via standard TDD cycle.
