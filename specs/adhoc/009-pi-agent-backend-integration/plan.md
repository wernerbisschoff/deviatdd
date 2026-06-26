## Plan Summary
- **Issue**: ISS-ADH-009 — Pi Agent Backend Integration — First-Class Backend for Micro/Meso Layers
- **Implementation Strategy**: Extend the `BACKEND_COMMANDS` registry, `AgentConfig.backend` Literal, `AGENT_CHOICES`, and `AGENT_TO_BACKEND` to recognise `pi`. Add per-backend `MODEL_FLAGS` map so Pi print mode does not receive `--model` (which it rejects — model selection is the operator's responsibility via Pi's own config). At `deviate setup`, when `agent.backend = "pi"`, treat Pi as a regular project-local agent: file-copy DeviaTDD skills into `<workdir>/.pi/skills/<name>/SKILL.md` via the existing `install_skill` pipeline (same path convention as `.claude/`, `.opencode/`, `.factory/`). **Do NOT write to `~/.pi/agent/`** and **do NOT generate a `settings.json`** — those are the operator's responsibility. Add `pi.session_stats` block to `prompts.log` `AGENT_RESULT` events when Pi emits token-stats output. Enable opt-in RPC mode via `agent.pi_rpc = true` config key.
- **Estimated Complexity**: Low–Medium
- **Estimated Effort**: 4-6 hours

## Workstation Mapping
- **`src/deviate/core/agent.py:60-65`**: Extend `BACKEND_COMMANDS` dict with `"pi": "pi -p"`; add `MODEL_FLAGS` per-backend map
  - **Current State**: `BACKEND_COMMANDS` has `opencode`, `claude`, `droid`, `stub`. No per-backend model-flag differentiation. `AgentBackend.invoke()` at line 274-336 hardcodes `cmd.extend(["--model", model])` for all non-claude backends.
  - **Changes Required**: Add `"pi": "pi -p"` to `BACKEND_COMMANDS`. Add `MODEL_FLAGS: dict[str, list[str] | None] = {"pi": None}` — `None` means model flag injection is prohibited for this backend (Pi routes model through settings.json). Update `invoke()` at line 291 to consult `MODEL_FLAGS.get(backend_name)` before injecting `--model`. If `MODEL_FLAGS[backend_name]` is `None`, skip model injection entirely.
  - **Integration Surface**: `AgentBackend.invoke()` (line 290-293), `AgentConfig.backend` Literal (in `src/deviate/state/config.py`).

- **`src/deviate/state/config.py:12-18`**: Widen `AgentConfig.backend` Literal to include `"pi"`; add `pi_rpc: bool` field
  - **Current State**: `backend: Literal["opencode", "claude", "droid"] = "opencode"`. `model_config = {"extra": "forbid"}`. No `pi_rpc` field.
  - **Changes Required**: Widen Literal to `Literal["opencode", "claude", "droid", "pi"]`. Add `pi_rpc: bool = Field(default=False, description="Opt-in RPC mode for Pi — spawns pi --mode rpc --no-session instead of pi -p")`.
  - **Integration Surface**: `DeviateConfig.agent` composition, TOML serialisation in `cli/__init__.py:_scaffold_dotfiles`, `_serialize_value` already handles bool.

- **`src/deviate/cli/__init__.py:43-54`**: Extend `AGENT_CHOICES` and `AGENT_TO_BACKEND`
  - **Current State**: `AGENT_CHOICES = ("factory", "droid", "claude", "opencode")`. `AGENT_TO_BACKEND = {"factory": "droid", "droid": "droid", "claude": "claude", "opencode": "opencode"}`.
  - **Changes Required**: Append `"pi"` to `AGENT_CHOICES`. Add `"pi": "pi"` to `AGENT_TO_BACKEND`. No changes needed to `_validate_agent_choice` (line 218-220, dynamic against `AGENT_CHOICES`).
  - **Integration Surface**: `_resolve_agent_to_backend` (line 286-293), `setup` command (line 555-627), `_prompt_agent_selection`.

- **`src/deviate/cli/__init__.py` — `deviate setup` flow**: Pi treated as a project-local agent
  - **Current State**: `_install_skills_to_agents` (line 518-531) creates `install_skill()` file copies for `claude`, `opencode`, `factory`. `_get_agent_skill_dir` (line 508-515) returns `None` for unknown agents. No Pi-specific logic.
  - **Changes Required**: Add `"pi"` branch to `_get_agent_skill_dir` returning `workdir / ".pi" / "skills"` (project-local, same convention as `.claude/`, `.opencode/`, `.factory/`). In the `setup` command, when `agent.backend == "pi"`, set `active_agents = ["pi"]` so the existing `_install_skills_to_agents` flow handles Pi uniformly. No global `~/.pi/agent/` writes. No `settings.json` generation — model/provider selection is the operator's responsibility via Pi's own configuration mechanism. Add `"pi"` to `core/skills.py:detect_agents` so subsequent setup runs detect the `.pi/` directory.
  - **Integration Surface**: `install_skill` from `deviate.core.skills`, `_read_agent_backend_from_config` (line 267-283), `_write_agent_block_to_config` (line 296-343), `_ensure_agent_gitignored` (existing).

- **`src/deviate/cli/micro.py:309-316`**: Enrich `prompts.log` with `pi.session_stats`
  - **Current State**: `_invoke_agent` (line 305) logs `INVOKE_AGENT` / `AGENT_RESULT` / `AGENT_RAW_OUTPUT` events via `_log_run`. No backend-specific log enrichment. `AgentBackend.invoke()` returns `(HandoverManifest, stdout)` via the current return pattern.
  - **Changes Required**: Add `_extract_pi_session_stats(stdout: str) -> dict[str, int] | None` helper in `micro.py` that parses a Pi-specific token stats block (`tokens.input`, `tokens.output`, `tokens.cacheRead`, `tokens.cacheWrite`) from agent raw stdout. When `backend_name == "pi"` and stats are present, append `pi.session_stats` sub-object to `_log_run("AGENT_RESULT", ...)` call. If stats absent, log warning. Note: `_invoke_agent` currently receives `raw_output: str` from the backend after resolution — the raw output string must be retained and passed to stats extraction. The issue's AC-009-04 requires non-null fields when present.
  - **Integration Surface**: `_log_run` (line 258-303 in `micro.py`), `_invoke_agent` (line 305-370), `AgentBackend.invoke()` return type.

- **`src/deviate/core/agent.py` — RPC mode dispatch (opt-in)**: Route `pi_rpc = true` to `pi --mode rpc --no-session`
  - **Current State**: `invoke()` at line 290 splits `BACKEND_COMMANDS["pi"]` (`"pi -p"`) into `["pi", "-p"]`. No RPC mode branch.
  - **Changes Required**: In `invoke()`, after resolving `backend_name == "pi"` and `self.config.pi_rpc == True`, construct `cmd = ["pi", "--mode", "rpc", "--no-session"]` instead of `["pi", "-p"]`. For RPC mode, replace `_invoke_blocking` / `_invoke_streaming` with a JSONL-over-stdin/stdout RPC client that sends `{"type": "prompt", "content": "..."}`, parses streaming `agent_start` / `message_update` / `agent_end` events, and extracts the handover manifest from the `agent_end` payload. RPC mode also enables `get_session_stats` capture for `pi.session_stats`.
  - **Integration Surface**: `AgentConfig.pi_rpc`, `BACKEND_COMMANDS["pi"]`, existing `subprocess.Popen` pattern.

- **`tests/core/test_agent.py`**: Unit tests for Pi backend contract
  - **Current State**: `TestAgentCommandModel` class (line 10-114) tests command construction with `patch("deviate.core.agent.subprocess.Popen")`. Tests `opencode`/`claude`/`droid` backends. No Pi tests.
  - **Changes Required**: Add tests: `test_pi_backend_subprocess_contract` (verify `pi -p` spawns), `test_pi_backend_yaml_extraction` (Pi-shaped YAML parses correctly), `test_pi_backend_missing_binary` (`FileNotFoundError` → `AgentBinaryNotFoundError`), `test_pi_backend_model_flag_suppressed` (no `--model` injected for Pi), `test_pi_rpc_mode_opt_in` (`pi_rpc = true` → `pi --mode rpc --no-session`), `test_agent_config_literal_accepts_pi` (Pydantic validation), `test_agent_config_literal_rejects_unknown` (`ValidationError`).

- **`tests/cli/test_init.py`**: Unit tests for Pi init flow
  - **Current State**: Tests `init` command with `runner.invoke(cli, ["init", ...])`. Tests for agent selection, governance, constitution. No Pi-specific tests.
  - **Changes Required**: Add tests for Pi symlink creation, settings.json generation, idempotence, agent choices extension, user-managed key preservation. Requires temporary `Path.home()` mocking via `tmp_path` fixture override or `patch("pathlib.Path.home")`.

- **`specs/DeviaTDD-api.md`** and **`specs/DeviaTDD-architecture.md`**: Document Pi backend
  - **Current State**: Document `opencode`, `claude`, `droid` backends with `--model` support matrix. No Pi entry.
  - **Changes Required**: Add Pi to backend selection matrix in both specs. Document print mode (`pi -p`) as default, RPC mode as opt-in, skill symlink strategy, settings.json generation, model-flag injection difference (Pi routes via settings.json, not `--model`), and `pi.session_stats` logging.

## Implementation Strategy
- **Phase 1**: Core backend registration — `BACKEND_COMMANDS`, `AgentConfig`, `MODEL_FLAGS`
  - **Files**: `src/deviate/core/agent.py`, `src/deviate/state/config.py`
  - **Approach**: Add `"pi": "pi -p"` to dict. Widen Literal. Add `pi_rpc` field. Add `MODEL_FLAGS` map. Thread `MODEL_FLAGS` check into `invoke()` model-flag injection. Add `StubPiBackend` fixture.
  - **Verification**: `mise run test tests/core/test_agent.py::test_pi_backend_missing_binary -v`, `mise run test tests/core/test_agent.py::test_pi_backend_model_flag_suppressed -v`, `mise run test tests/core/test_agent.py::test_agent_config_literal_accepts_pi -v`

- **Phase 2**: User-facing agent selection — `AGENT_CHOICES`, `AGENT_TO_BACKEND`, init flow integration
  - **Files**: `src/deviate/cli/__init__.py`
  - **Approach**: Extend tuples. Add Pi skill symlink logic behind `backend == "pi"` check in init. Generate settings.json. Idempotent: skip existing symlinks/dirs, merge settings keys.
  - **Verification**: `mise run test tests/cli/test_init.py::test_agent_choices_includes_pi -v`, `mise run test tests/cli/test_init.py::test_agent_to_backend_maps_pi -v`, `mise run test tests/cli/test_init.py::test_init_creates_pi_skill_symlinks -v`, `mise run test tests/cli/test_init.py::test_init_generates_pi_settings_json -v`, `mise run test tests/cli/test_init.py::test_init_idempotent_pi_setup -v`, `mise run test tests/cli/test_init.py::test_init_preserves_user_managed_settings_keys -v`

- **Phase 3**: RPC mode opt-in and token stats capture
  - **Files**: `src/deviate/core/agent.py`, `src/deviate/cli/micro.py`
  - **Approach**: Branch `invoke()` on `pi_rpc = true` to spawn `["pi", "--mode", "rpc", "--no-session"]`. Implement JSONL RPC client for streaming events. Extract `pi.session_stats` from `agent_end` event. In print mode, parse `--print-tokens` footer if available. Append stats to `AGENT_RESULT` log.
  - **Verification**: `mise run test tests/core/test_agent.py::test_pi_rpc_mode_opt_in -v`, `mise run test tests/core/test_agent.py::test_pi_session_stats_logged -v`, `mise run test tests/core/test_agent.py::test_pi_backend_subprocess_contract -v`

- **Phase 4**: Spec documentation
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`
  - **Approach**: Add Pi row to backend selection matrix. Document print mode default, RPC opt-in, skill symlink strategy, settings.json for model routing, `pi.session_stats` logging.
  - **Verification**: Manual review of both spec files for consistency with implementation.

## Data Flow Analysis
1. **Config persistence**: `deviate setup --agent pi` → `_write_agent_block_to_config` writes `[agent]\nbackend = "pi"` to `.deviate/config.toml`. `_scaffold_dotfiles` writes `pi_rpc = false` under `[agent]`. TOML serialisation handled by `_dict_to_toml` → `_write_if_missing`.
2. **Model routing**: Pi does not accept `--model` CLI flag. At runtime, `[models]` entries in `.deviate/config.toml` are read by `resolve_model_for_phase()`, but for Pi, the resolved model is **not** injected via `cmd.extend(["--model", model])`. Model selection is the operator's responsibility — configured via Pi's own configuration mechanism. Per-phase model swaps in Pi require RPC mode opt-in via `agent.pi_rpc = true` (Pi's `set_model` RPC command).
3. **Skill discovery**: At setup, skills are file-copied into `<workdir>/.pi/skills/<name>/SKILL.md` via the existing `install_skill` pipeline. Pi's native skill loader discovers them from `.pi/skills/` at startup. DeviaTDD skills contain YAML frontmatter (`name:` + `description:`) per the Agent Skills spec — Pi parses and registers them. The `.gitignore` entry `.pi/skills/deviate-*/` is added by `_ensure_agent_gitignored`, preventing the file-copied skills from being committed.
4. **Token observability**: After each Pi invocation, `prompts.log` receives `AGENT_RESULT` event with optional `pi.session_stats` block containing `tokens.input`, `output`, `cacheRead`, `cacheWrite`. In RPC mode, stats come from `get_session_stats` / `agent_end` event. In print mode, stats come from `--print-tokens` output footer if enabled.
5. **RPC mode dispatch**: When `pi_rpc = true`, `invoke()` spawns `["pi", "--mode", "rpc", "--no-session"]`, sends JSONL `{"type": "prompt", "content": "..."}`, parses streaming events, extracts handover manifest from `agent_end` payload. Manifest extraction reuses existing `HandoverManifest` Pydantic validation.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Pi binary not on operator PATH | Low | Medium | `FileNotFoundError` → `AgentBinaryNotFoundError` with install instructions (same as other backends) |
| Operator's global `~/.pi/agent/settings.json` clobbered | High | Eliminated | DeviaTDD does NOT write to `~/.pi/agent/` — operator's global Pi config is out of scope |
| Project-local `.pi/skills/<name>` overwritten with newer version | Low | Low | `install_skill` compares content; identical → skip, different → replace, parent dir auto-created |
| RPC mode JSONL event parse failure | Medium | Low | Log warning, skip malformed line, continue; `agent_end` event is source of truth for manifest |
| Per-phase model swap requires RPC mode opt-in | Low | Medium | Documented; print mode is static, RPC mode is opt-in via `agent.pi_rpc = true` |
| Cross-platform file copy permissions | Low | Very Low | Standard `pathlib.Path.write_text()` — no symlink privilege issues on Windows |

## Integration Points
- **`BACKEND_COMMANDS` dict**: Single source of truth for CLI command prefixes; extended with `"pi": "pi -p"`. All `invoke()` paths consume this via `BACKEND_COMMANDS.get(backend_name)`.
- **`AgentConfig` Pydantic model**: `backend` Literal widened to `"pi"`. `pi_rpc: bool` added. Round-trip through TOML serialisation in `cli/__init__.py:_serialize_value` → `_dict_to_toml`.
- **`MODEL_FLAGS` per-backend map**: New module-level dict `{"pi": None, "opencode": ["--model"], "droid": ["--model"]}`. `invoke()` checks `MODEL_FLAGS.get(backend_name)` before appending `--model`. `None` means skip.
- **`deviate setup` command**: `--agent pi` routes through the existing `_install_skills_to_agents` flow with `active_agents = ["pi"]`. The `_get_agent_skill_dir("pi")` branch returns `workdir / ".pi" / "skills"`. Idempotent via `install_skill`'s content-comparison path. No `~/.pi/agent/` writes, no `settings.json` generation.
- **`HandoverManifest`**: Unchanged; Pi output conforms to same YAML schema. `model_config = {"extra": "allow"}` at line 30 handles any Pi-specific extra fields.
- **`prompts.log`**: `AGENT_RESULT` entries enriched with `pi.session_stats` sub-object when backend is `"pi"` and token data is present.
- **`StubPiBackend`**: Mirrors `StubAgentBackend` with Pi-shaped output for downstream tests. Emits canned YAML handover manifest + canned session stats block.

## Constitutional Alignment
- **Architecture**: Pi integrates at the meso/micro layer via the existing `AgentBackend` subprocess contract. Extends the three-layer architecture without introducing new layers or phase gates. Macro layer is explicitly excluded per `## Defensive Exclusions`.
- **Testing**: All new tests follow existing patterns in `tests/core/test_agent.py` (backend contract tests with `patch("subprocess.Popen")`) and `tests/cli/test_init.py` (init flow tests with `runner.invoke`). Pytest is the runner. RED phase tests must fail with `AssertionError`.
- **Git Isolation**: Pi subprocess runs within the worktree. All Git operations obey existing `_git_env()` isolation. Tamper Guard applies identically — writes outside `src/**/*.py` detected and reverted.

## Target File Structure
The following target workstation files have been pre-scanned with structural analysis. Each entry shows the detected language, extracted symbols, and import/include/using blocks.

### `src/deviate/core/agent.py` (Language: python)
- **Symbols**: `BACKEND_COMMANDS` (dict), `AgentBackend` (class), `AgentBackend.invoke()` (method), `StubAgentBackend` (class), `HandoverManifest` (class), `AgentTimeoutError`, `AgentSubprocessError`, `MalformedHandoverManifestError`, `AgentBinaryNotFoundError`, `EmptyOutputError`, `_YAML_BLOCK_RE`, `_YAML_HANDOVER_MARKER_RE`, `_YAML_MAPPING_START_RE`, `_extract_yaml_block`, `_yaml_error_hint`, `parse_output`, `_invoke_blocking`, `_invoke_streaming`
- **Imports**: `re`, `subprocess`, `threading`, `time`, `Callable`, `Literal`, `yaml`, `BaseModel`, `ValidationError`, `AgentConfig`

### `src/deviate/state/config.py` (Language: python)
- **Symbols**: `AgentConfig` (class), `DeviateConfig` (class), `SessionState` (class), `TransitionViolationError`, `PytestReportConfig`, `to_toml_string`, `resolve_phase_model`, `resolve_model_for_phase`, `force_transition_to`, `reconstruct_from_worktree`, `validate_filesystem_state`
- **Imports**: `json`, `tomllib`, `datetime`, `Path`, `Literal`, `Optional`, `BaseModel`, `Field`, `field_validator`

### `src/deviate/cli/__init__.py` (Language: python)
- **Symbols**: `AGENT_CHOICES` (tuple), `AGENT_TO_BACKEND` (dict), `setup` (cli command), `_install_skills_to_agents`, `_get_agent_skill_dir`, `_read_agent_backend_from_config`, `_resolve_agent_to_backend`, `_write_agent_block_to_config`, `_scaffold_dotfiles`, `_apply_governance`, `_serialize_value`, `_dict_to_toml`, `_write_if_missing`, `main` (callback)
- **Imports**: `re`, `typer`, `Console`, `DeviateConfig`, `SessionState`, `shutil`, `Prompt`, `tomllib`, `Path`, `importlib.resources`, `detect_agents`, `discover_skills`, `install_skill`

### `src/deviate/cli/micro.py` (Language: python)
- **Symbols**: `_invoke_agent`, `_log_run`, `_run_pytest`, `_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`, `_run_execute_phase`, `_run_yellow_phase`, `_commit_phase`, `_execute_rollback`, `PhaseFailedError`, `RedPhaseError`
- **Imports**: `json`, `re`, `subprocess`, `sys`, `os`, `yaml`, `AgentBackend`, `AgentBinaryNotFoundError`, `AgentSubprocessError`, `AgentTimeoutError`, `EmptyOutputError`, `HandoverManifest`, `MalformedHandoverManifestError`, `AgentConfig`, `PytestReportConfig`, `SessionState`, `resolve_graphite_config`, `resolve_model_for_phase`, `RunLogger`, `OrchestrationMonitor`, `TamperContext`, `TamperGuard`, `find_worktree_for_branch`, `Console`, `Callable`, `typer`, `Path`

### `tests/core/test_agent.py` (Language: python)
- **Symbols**: `TestAgentCommandModel` (class), `test_command_with_model`, `test_command_without_model`, `test_command_claude_backend`, `test_command_droid_backend`
- **Imports**: `MagicMock`, `patch`, `pytest`, `AgentBackend`, `AgentConfig`, `AgentSubprocessError`
