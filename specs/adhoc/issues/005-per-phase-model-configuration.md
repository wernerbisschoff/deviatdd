---
title: "Per-Phase Model Configuration with Configurable Model Routing"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: [ISS-001-005]
issue_id: ISS-ADH-005
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/005-per-phase-model-configuration.md`
- **Primary Architectural Workstation**:
  - `src/deviate/state/config.py` — Add `ModelConfig` model with phase→model mapping under `DeviateConfig`
  - `src/deviate/core/agent.py` — Extend `AgentBackend.invoke()` to accept optional `model` parameter; append `--model <id>` to `opencode run` command
  - `src/deviate/cli/micro.py` — Thread per-phase model resolution into `_invoke_agent()` and each phase runner (`_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`, `_run_execute_phase`)
  - `src/deviate/cli/meso.py` — Thread per-phase model resolution into `_invoke_agent_phase()`
  - `src/deviate/cli/macro.py` — Thread per-phase model resolution into `_invoke_agent_phase()`
  - `src/deviate/prompts/assembly.py` — Load model config in `assemble_prompt` context (future: template injection)
  - `.deviate/config.toml` — Document `[models]` section schema

## [THE_PROBLEM_CONTRACT]
The DeviaTDD workflow routes all phase agent invocations through `opencode run` or `droid exec` without any per-phase model differentiation. The constitution documents a tiered model strategy (V4 Flash for high-frequency phases, V4 Pro for compliance/planning, Qwen 3.7+ for architecture), but this strategy is not enforced — every phase uses whatever model the backend has configured as its default. Users need a declarative mechanism to assign a default model for all phases and override specific phases so that cheap models handle high-volume work and premium models handle planning and compliance gates, regardless of which agent backend is active.

## [SCOPE_BOUNDARIES]
### Hard Inclusions
- Add `ModelPhaseMap` model to `src/deviate/state/config.py` as a free-form dict with a reserved `default` key for the fallback model
- Mount `[models]` section in `.deviate/config.toml` serialization
- Implement resolution order: phase-specific key → `default` key → no `--model` flag (backend-native default)
- Extend `AgentBackend.invoke()` signature to accept an optional `model: str | None` parameter and inject `--model <id>` when non-None
- Support BOTH opencode and droid backends — both use `-m, --model <id>` flag syntax
- Resolve per-phase model in every agent-invocation path across micro, meso, and macro layers by loading the session config and resolving against the current phase
- Provide idempotent read semantics: no config → no model flag; no `[models]` section → empty dict → no model flag; phase not in dict AND no `default` → no model flag
- Update AGENTS.md and constitution `Model Tiering` section to reference the new config mechanism
- Add unit tests for config model serialization, command construction, phase resolution, and default fallback

### Defensive Exclusions
- No runtime model validation against any provider catalog — pass-through to the backend which handles its own validation
- No new CLI flags on `deviate` — the config file is the sole surface
- No live reload of config — agent invocation reads `.deviate/config.toml` fresh each call via `DeviateConfig` loading
- No `--model` support for the `claude` backend — `claude -p` does not accept a model flag; if claude is the active backend, model config is silently ignored
- No migration of existing `.deviate/config.toml` files — the section is optional and absent by default
- No YELLOW phase model override — YELLOW reuses whatever model GREEN was configured with (per session continuity rule in constitution)
- No TOML key validation — any key other than `default` is treated as a phase name and passed through as-is

## [UPSTREAM_REQUIREMENT_TRACING]
- **Requirements Tokens**: `FR-ADHOC-005`
- **Acceptance Criteria Tokens**: `AC-ADHOC-005-01`, `AC-ADHOC-005-02`, `AC-ADHOC-005-03`, `AC-ADHOC-005-04`, `AC-ADHOC-005-05`, `AC-ADHOC-005-06`, `AC-ADHOC-005-07`, `AC-ADHOC-005-08`
- **Data Model Entities**: `ModelPhaseMap` (free-form `dict[str, str]` with reserved `default` key)
- **Constitution Anchors**: [`ARCHITECTURAL_PRINCIPLES` — Section `Model Tiering`]

## [USER_STORIES_LEDGER]
- **US-ADH-005-01**: As a DeviaTDD operator, I want to configure a `default` model that all phases use in `.deviate/config.toml` so that I set one model for the entire workflow without repeating it per phase.
- **US-ADH-005-02**: As a DeviaTDD operator, I want to override specific phases with a different model than the default so that premium models are reserved for planning and compliance gates while cheaper models handle the rest.
- **US-ADH-005-03**: As a DeviaTDD operator, I want the model selection to work for both `opencode` and `droid` backends so that my model routing works regardless of which agent CLI I use.
- **US-ADH-005-04**: As a DeviaTDD operator, I want phases without an explicit model entry and without a `default` to fall through to the backend's native default so that I only configure what I need and maintain backward compatibility.

## [ATDD_ACCEPTANCE_CRITERIA]
**Scenario 005-01**: Default model applies to all phases
**Given** `.deviate/config.toml` has `[models]\ndefault = "opencode/deepseek-v4-flash"`
**When** any phase (e.g., PLAN, RED, JUDGE) builds the agent command
**Then** the command array includes `["opencode", "run", "--model", "opencode/deepseek-v4-flash"]`

**Scenario 005-02**: Phase override takes precedence over default
**Given** `.deviate/config.toml` has `[models]\ndefault = "opencode/deepseek-v4-flash"\njudge = "opencode/deepseek-v4-pro"`
**When** the RED phase builds the command
**Then** the command includes `--model opencode/deepseek-v4-flash`
**When** the JUDGE phase builds the command
**Then** the command includes `--model opencode/deepseek-v4-pro`

**Scenario 005-03**: No config section → no model flag
**Given** `.deviate/config.toml` has no `[models]` section
**When** any phase calls `AgentBackend.invoke()`
**Then** the command array is `["opencode", "run"]` without `--model`

**Scenario 005-04**: Droid backend uses model flag
**Given** `.deviate/config.toml` has `[models]\nplan = "deepseek-v4-pro"`
**When** the PLAN phase invokes with backend `droid`
**Then** the command array includes `["droid", "exec", "--model", "deepseek-v4-pro"]`

**Scenario 005-05**: Claude backend ignores model config
**Given** `.deviate/config.toml` has `[models]\nred = "opencode/deepseek-v4-flash"`
**When** the RED phase invokes with backend `claude`
**Then** the command array is `["claude", "-p"]` without `--model`

**Scenario 005-06**: Invalid model passes through
**Given** `.deviate/config.toml` has `[models]\nplan = "nonexistent/model"`
**When** the PLAN phase invokes `opencode run --model nonexistent/model`
**Then** the backend exits non-zero and the error surfaces as an `AgentSubprocessError`

**Scenario 005-07**: ModelPhaseMap schema round-trip
**Given** a fresh `DeviateConfig(profile="local")` instance
**When** serialized to TOML and deserialized
**Then** the `models` field defaults to an empty dict `{}`

**Scenario 005-08**: TDD cycle uses phase-specific models with default fallback
**Given** `.deviate/config.toml` configures `{default: "fast/model", judge: "premium/model"}`
**When** a TDD cycle runs RED, GREEN, JUDGE, REFACTOR
**Then** RED uses `fast/model`, GREEN uses `fast/model`, JUDGE uses `premium/model`, REFACTOR uses `fast/model`

## [EDGE_CASES_AND_BOUNDARIES]
- **Missing config.toml**: `DeviateConfig()` default has no models field, so any lookup returns `None` — safe fallback
- **Phase name case sensitivity**: Phase keys in `[models]` are matched as-is (case-sensitive). The lookup uses the canonical upper-case phase name (`RED`, `GREEN`, etc.) as the dict key
- **Empty model string**: If config has `plan = ""` (empty string), treat as no override — fall through to `default` or skip `--model`
- **Whitespace/quoting**: TOML parsing handles string quoting; unquoted values without spaces are valid bare keys in TOML
- **Backend support matrix**: opencode → supports `--model`; droid → supports `-m, --model`; claude → no model flag supported — model config is silently ignored for claude
- **Backend override collision**: If `--agent claude` is passed alongside a `[models]` entry, the model flag is not appended because the claude backend doesn't support it
- **`default` as a TOML key**: The key `default` is reserved and treated specially — it is never matched as a phase key. Any TOML key other than `default` is treated as a phase name
- **Concurrent access**: Config is read-only during TDD cycles — no concurrent mutation risk
- **Model identifiers with spaces**: TOML handles quoted strings; `--model` flag is a single shell argument passed as-is to the backend

## [PERFORMANCE_CONSTRAINTS]
- L_max: < 10ms for model resolution (dict lookup + optional string concat)
- Throughput: N/A (model resolution is not a throughput path)
- Zero overhead when `[models]` section is absent — the lookup returns an empty dict

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Sandbox Targets**:
  - `tests/test_state/test_config.py::test_model_config_defaults` — empty models dict on fresh config
  - `tests/test_state/test_config.py::test_model_config_round_trip` — serialization preserves map
  - `tests/test_state/test_config.py::test_model_config_phase_lookup` — known phase returns model, unknown returns None
  - `tests/core/test_agent.py::test_agent_command_with_model` — command contains `--model`
  - `tests/core/test_agent.py::test_agent_command_without_model` — command has no `--model`
  - `tests/core/test_agent.py::test_agent_command_droid_backend` — command includes `--model` for droid backend
  - `tests/core/test_agent.py::test_agent_command_claude_backend` — no `--model` for claude backend
  - `tests/core/test_agent.py::test_agent_command_default_fallback` — `default` key applies when phase not in dict
  - `tests/core/test_agent.py::test_agent_command_phase_overrides_default` — specific phase overrides `default`
  - `tests/cli/test_micro.py::test_phase_routes_model[RED]` — RED uses configured model
  - `tests/cli/test_micro.py::test_phase_routes_model[JUDGE]` — JUDGE uses configured model
- **Integration Sandbox Targets**:
  - `tests/test_integration/test_init_export_cycle.py` — verify `deviate init` creates valid config with no `[models]` section

## [DEMONSTRATION_PATH]
```bash
# 1a. Minimal config: default model for all phases, override for JUDGE/PLAN
cat >> .deviate/config.toml << 'EOF'
[models]
default = "opencode/deepseek-v4-flash"
plan = "opencode/deepseek-v4-pro"
judge = "opencode/deepseek-v4-pro"
EOF

# 1b. Same config with droid backend (model IDs differ by provider)
cat >> .deviate/config.toml << 'EOF'
[models]
default = "deepseek-v4-flash"
plan = "deepseek-v4-pro"
judge = "deepseek-v4-pro"
EOF

# 2. Verify the config is TOML-valid
python3 -c "import tomllib; print(tomllib.load(open('.deviate/config.toml','rb'))['models'])"

# 3. Run unit tests for model routing
pytest tests/test_state/test_config.py::test_model_config -v
pytest tests/core/test_agent.py -v
```
