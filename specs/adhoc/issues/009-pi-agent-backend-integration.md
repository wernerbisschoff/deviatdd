---
title: "Pi Agent Backend Integration — First-Class Backend for Micro/Meso Layers"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-009
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/009-pi-agent-backend-integration.md`
- **Primary Architectural Workstations**:
  - `src/deviate/core/agent.py:60-65` — `BACKEND_COMMANDS` dict: extend with `"pi": "pi -p"`
  - `src/deviate/core/agent.py:274-336` — `AgentBackend.invoke()`: add per-backend `MODEL_FLAGS` map for Pi's `--provider <name> --model <pattern>` injection (print mode does not accept `--model` directly)
  - `src/deviate/core/agent.py:339-356` — `StubAgentBackend` (reference): add `StubPiBackend` for test fixtures
  - `src/deviate/state/config.py:12-18` — `AgentConfig.backend` Literal: widen to include `"pi"`
  - `src/deviate/state/config.py` — `AgentConfig`: add optional `pi_rpc: bool = False` field for opt-in RPC mode
  - `src/deviate/cli/__init__.py:43-53` — `AGENT_CHOICES` / `AGENT_TO_BACKEND`: extend with `"pi"`
  - `src/deviate/cli/__init__.py` — `init` flow: detect `agent.backend = "pi"` and generate `~/.pi/agent/skills/<skill-name>` symlinks + `~/.pi/agent/settings.json`
  - `src/deviate/cli/micro.py:309-316` — `INVOKE_AGENT` / `AGENT_RESULT` logging: append `pi.session_stats` block (tokens.input/output/cacheRead/cacheWrite) to log entries when backend is Pi
  - `src/deviate/cli/micro.py` — `_invoke_agent()`: thread `backend_name` through to RPC-mode dispatcher (conditional)
  - `tests/core/test_agent.py` — add `test_pi_backend_subprocess_contract`, `test_pi_backend_yaml_extraction`, `test_pi_backend_model_flag_injection`, `test_pi_backend_missing_binary`
  - `tests/cli/test_init.py` — add `test_init_creates_pi_skill_symlinks`, `test_init_generates_pi_settings_json`, `test_init_idempotent_pi_setup`
  - `specs/DeviaTDD-api.md` — document `pi` backend in the backend selection matrix
  - `specs/DeviaTDD-architecture.md` — document Pi-specific customizations (skill symlinks, settings file, RPC mode opt-in)
- **Upstream Evidence**: `specs/explore/pi-agent-backend.md` (Pi v0.80.2 facts, Agent Skills spec, RPC mode protocol, model flag syntax, token stats surface)

## The Problem Contract
DeviaTDD currently supports three backends (`opencode`, `claude`, `droid`) but lacks a unified skill-discovery mechanism: each phase re-sends full prompt payloads because none of these backends natively understand the Agent Skills standard. Pi (`@earendil-works/pi-coding-agent` v0.80.2) implements the Agent Skills spec natively, discovering skills from `~/.pi/agent/skills/`, `.pi/skills/`, and `.agents/skills/` — and DeviaTDD's existing 20 `src/deviate/prompts/skills/*/SKILL.md` files already carry the required `name:` + `description:` YAML frontmatter. Adding Pi as a backend requires only: (1) extending the `BACKEND_COMMANDS` registry and `AgentConfig.backend` Literal, (2) generating symlinks at `deviate init` so Pi discovers DeviaTDD's skills natively, (3) generating `~/.pi/agent/settings.json` so per-phase `[models]` config maps onto Pi's provider/model selector, and (4) capturing Pi's `get_session_stats` token data (cache-read ratio) into `prompts.log` for cost observability. Pi's RPC mode (`pi --mode rpc --no-session`) is opt-in and offers streaming JSONL events + token stats — but print mode (`pi -p`) is the default, single-shot, and maps 1:1 onto the existing `AgentBackend.invoke()` subprocess contract (stdin prompt → stdout YAML).

## Scope Boundaries
### Hard Inclusions
- Extend `BACKEND_COMMANDS: dict[str, str]` in `src/deviate/core/agent.py:60-65` with `"pi": "pi -p"`. Source: explore §"Existing Architectural Patterns" (`src/deviate/core/agent.py:60-65`).
- Widen `AgentConfig.backend` Literal in `src/deviate/state/config.py:12-18` from `Literal["opencode", "claude", "droid"]` to `Literal["opencode", "claude", "droid", "pi"]`. Source: explore §"Type-safe backend literal".
- Extend `AGENT_CHOICES` and `AGENT_TO_BACKEND` in `src/deviate/cli/__init__.py:43-53` to include `"pi"`. Source: explore §"File Registry" row `src/deviate/cli/__init__.py`.
- Add `pi_rpc: bool = False` field to `AgentConfig` for opt-in RPC mode (default off → print mode).
- Add per-backend `MODEL_FLAGS: dict[str, list[str]]` map in `src/deviate/core/agent.py` so Pi's `--provider <name> --model <pattern>` flag pair is injected correctly (current code injects `--model <model>` only, which Pi print mode rejects). For Pi print mode, route model selection through `~/.pi/agent/settings.json` instead of CLI flag — see `init` hook below.
- In `deviate init` flow, when `agent.backend = "pi"`:
  - Create `~/.pi/agent/skills/<skill-name>` symlinks (one per `src/deviate/prompts/skills/*/SKILL.md`) pointing back to the project skill directory — Pi discovers skills natively. Use `pathlib.Path.symlink_to()` with absolute targets.
  - Generate `~/.pi/agent/settings.json` with `{"provider": "<resolved>", "model": "<resolved>", "skillPaths": ["<absolute-path-to-src/deviate/prompts/skills>"]}`. Provider/model resolution reads the `[models]` section of `.deviate/config.toml` with `default` key as fallback.
  - Idempotency: skip symlink creation if target already exists and points to correct path; skip settings.json write if identical content already present.
- Enrich `prompts.log` `AGENT_RESULT` events with a `pi.session_stats` block when `backend_name == "pi"` and the subprocess emits structured token data. Pi's `--print-tokens` flag (or, in RPC mode, `get_session_stats` response) yields `tokens.input`, `tokens.output`, `tokens.cacheRead`, `tokens.cacheWrite`. Source: explore §"Token-cost levers".
- Add `StubPiBackend` test fixture (mirroring `StubAgentBackend`) emitting canned YAML handover manifest + canned session stats block.
- Add unit tests:
  - `tests/core/test_agent.py::test_pi_backend_subprocess_contract` — verify `pi -p` is the spawned command, prompt is piped via stdin, YAML manifest extracted from stdout
  - `tests/core/test_agent.py::test_pi_backend_yaml_extraction` — verify a Pi-shaped output (fenced YAML block + `<handover_manifest>` tag) parses via existing `_YAML_BLOCK_RE` / `_YAML_HANDOVER_MARKER_RE` pipeline
  - `tests/core/test_agent.py::test_pi_backend_missing_binary` — verify `AgentBinaryNotFoundError` raised when `pi` is not on `PATH`
  - `tests/cli/test_init.py::test_init_creates_pi_skill_symlinks` — verify one symlink per skill (20 skills → 20 symlinks), targets point to `src/deviate/prompts/skills/<name>`
  - `tests/cli/test_init.py::test_init_generates_pi_settings_json` — verify settings.json content matches `provider`/`model` resolved from `[models]` config
  - `tests/cli/test_init.py::test_init_idempotent_pi_setup` — re-running `init` does not duplicate symlinks or settings.json
- Update `specs/DeviaTDD-api.md` backend matrix to include `pi` with print mode + opt-in RPC mode.
- Update `specs/DeviaTDD-architecture.md` §"Backend Architecture" with Pi-specific customizations (skill symlink strategy, settings.json generation, model flag injection difference, RPC mode opt-in).

### Defensive Exclusions
- Do NOT bundle or vendor the `pi` binary — assume the operator installs it via `npm install -g @earendil-works/pi-coding-agent`. Surface a clear error if the binary is missing.
- Do NOT modify the YAML handover manifest schema — Pi produces output in the same format other backends use (`<handover_manifest>` tag or fenced YAML block); reuse existing `HandoverManifest` Pydantic model.
- Do NOT add RPC mode (`pi --mode rpc --no-session`) as default — print mode is sufficient for single-shot phase invocations and matches the existing `AgentBackend.invoke()` contract. RPC mode is opt-in via `agent.pi_rpc = true`.
- Do NOT generate skill symlinks for non-DeviaTDD skill paths (e.g., third-party skills from `~/.pi/agent/skills/`) — symlinks only cover `src/deviate/prompts/skills/*`.
- Do NOT overwrite `~/.pi/agent/settings.json` if it already contains non-DeviaTDD-managed entries (keys not starting with `deviate_`) — merge only `deviate_*` keys, preserve user-managed entries.
- Do NOT add `--model` flag injection for Pi print mode (it rejects bare `--model`) — model selection routes through `~/.pi/agent/settings.json`.
- Do NOT modify Pi's Tamper Guard sandbox enforcement — Pi has no built-in permission system; DeviaTDD's wrapper-level Tamper Guard (allowing writes only to `src/**/*.py`) applies at the pre/post-commit hook layer.
- Do NOT add Pi as an option for the macro layer (explore/research/prd/shard) in this issue — macro layer runs single-agent, per-feature invocations; Pi is a micro/meso candidate only. Macro support deferred to a follow-up issue if token savings are observed.
- Do NOT integrate Pi's sub-agent delegation or plan mode (Pi philosophy: "no sub-agents, no plan mode, no MCP" per explore §"Pitfall — Pi philosophy") — DeviaTDD's external orchestration model is incompatible with Pi's sub-agent model.
- Do NOT change the JUDGE phase's isolation model — JUDGE continues to run in an isolated V4 Pro session; backend choice is orthogonal to session isolation.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-009`
- **Acceptance Criteria Tokens**: `AC-ADHOC-009-01` through `AC-ADHOC-009-10`
- **Data Model Entities**: None new (existing `AgentConfig`, `HandoverManifest`, `IssueRecord`, `AdhocRecord` cover all fields; one new boolean `AgentConfig.pi_rpc`)

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->
- **US-009-01**: As a DeviaTDD operator running micro-layer phases, I want Pi as a selectable backend (`--agent pi`) so that I can leverage Pi's Agent Skills native discovery and automatic context compaction for token-cost savings. *(Ref: FR-ADHOC-009)*
- **US-009-02**: As a DeviaTDD operator configuring per-phase models in `.deviate/config.toml`, I want the `[models]` section to map onto Pi's `~/.pi/agent/settings.json` so that I do not pass `--model` as a CLI flag (which Pi print mode rejects) and so per-phase model routing works across all backends uniformly. *(Ref: FR-ADHOC-009)*
- **US-009-03**: As a DeviaTDD operator analysing token costs, I want `prompts.log` to capture Pi's `tokens.cacheRead` and `tokens.cacheWrite` so that I can compute cache-hit ratio and validate token savings vs `opencode`/`claude`/`droid` backends. *(Ref: FR-ADHOC-009)*
- **US-009-04**: As a DeviaTDD architect with custom skills in `src/deviate/prompts/skills/`, I want Pi to discover those skills natively via symlinks generated at `deviate init` so that I do not duplicate skill content across DeviaTDD and Pi skill catalogues. *(Ref: FR-ADHOC-009)*
- **US-009-05**: As a DeviaTDD operator running JUDGE phase with strict isolation, I want Pi's RPC mode (`pi --mode rpc`) available as opt-in so that I can stream JSONL events and capture fine-grained token stats during compliance verification without changing the existing print-mode contract. *(Ref: FR-ADHOC-009)*

## ATDD Acceptance Criteria
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

**Scenario 009-01**: Pi backend is selectable and dispatches correctly
**Given** `agent.backend = "pi"` in `.deviate/config.toml`
**When** `AgentBackend.invoke(prompt="...", backend="pi")` is called
**Then** the subprocess command spawned is `["pi", "-p"]` (per `BACKEND_COMMANDS["pi"]`); prompt is piped via `stdin`; stdout is parsed via the existing `_YAML_BLOCK_RE` / `_YAML_HANDOVER_MARKER_RE` regex pipeline; the extracted YAML is validated against `HandoverManifest` Pydantic schema.

**Scenario 009-02**: Skill symlinks are created at `deviate init`
**Given** 20 skill directories exist under `src/deviate/prompts/skills/*/` (each with `SKILL.md` containing `name:` + `description:` YAML frontmatter)
**When** `deviate init` runs with `agent.backend = "pi"`
**Then** 20 symlinks are created under `~/.pi/agent/skills/<skill-name>`, each pointing to the absolute path of `src/deviate/prompts/skills/<skill-name>`; `pi -p "<prompt asking to list skills>"` enumerates all 20 skills via Pi's native discovery.

**Scenario 009-03**: Settings.json maps `[models]` config to Pi
**Given** `.deviate/config.toml` contains `[models]` with `default = "anthropic/claude-sonnet-4-5"` and `judge = "openai/gpt-5-pro"`
**When** `deviate init` runs with Pi backend
**Then** `~/.pi/agent/settings.json` is written with `{"provider": "anthropic", "model": "claude-sonnet-4-5", "skillPaths": ["<abs-path-to-src/deviate/prompts/skills>"]}` (default model used as initial setting; per-phase model overrides applied via temporary settings swap or Pi's session-scoped `set_model` RPC command in RPC mode).

**Scenario 009-04**: Token stats captured in prompts.log
**Given** a Pi subprocess invocation completes successfully and emits a session stats block (`tokens.input`, `tokens.output`, `tokens.cacheRead`, `tokens.cacheWrite`)
**When** the `AGENT_RESULT` event is written to `.deviate/prompts.log`
**Then** the log entry contains a `pi.session_stats` JSON sub-object with all four fields populated — no field is null or missing.

**Scenario 009-05**: AGENT_CHOICES exposes Pi to users
**Given** the `AGENT_CHOICES` tuple is extended with `"pi"`
**When** `deviate init` runs interactively and the user selects `pi`
**Then** `AGENT_TO_BACKEND["pi"] == "pi"` and the init flow proceeds with Pi-specific setup (skill symlinks, settings.json).

**Scenario 009-06**: Tamper Guard applies to Pi writes
**Given** a Pi subprocess attempts to write a file outside `src/**/*.py` (e.g., `tests/test_foo.py` or `specs/adhoc/issues/001-foo.md`)
**When** DeviaTDD's Tamper Guard hook runs post-invocation
**Then** the unauthorized write is detected, `git checkout -- <file>` reverts the change, and the session transitions to a ROLLBACK state — the same enforcement that applies to `opencode`/`claude`/`droid`.

**Scenario 009-07**: BACKEND_COMMANDS includes Pi
**Given** `BACKEND_COMMANDS["pi"]` is `"pi -p"`
**When** `AgentBackend.invoke()` resolves the backend command via `BACKEND_COMMANDS.get(backend_name)`
**Then** the returned prefix splits to `["pi", "-p"]`; `subprocess.Popen(["pi", "-p"], stdin=PIPE, stdout=PIPE, stderr=PIPE)` is the actual spawned command.

**Scenario 009-08**: AgentConfig Literal accepts Pi
**Given** `AgentConfig.backend: Literal["opencode", "claude", "droid", "pi"] = "opencode"`
**When** `DeviateConfig(agent=AgentConfig(backend="pi"))` is constructed
**Then** Pydantic validation succeeds with no `ValidationError`; `model_dump()` includes `"backend": "pi"`; round-trip via TOML parse preserves the value.

**Scenario 009-09**: YAML handover manifest extraction is backend-agnostic
**Given** a Pi subprocess emits stdout containing a fenced YAML block ` ```yaml\nphase: RED\nstatus: COMPLETED\n``` ` followed by the rest of the agent's response
**When** `AgentBackend.parse_output(stdout, "pi")` runs
**Then** the `_YAML_BLOCK_RE` regex extracts the YAML body, `yaml.safe_load` parses it, and `HandoverManifest.model_validate(...)` succeeds — the same code path used for `opencode`/`claude`/`droid` backends.

**Scenario 009-10**: RPC mode opt-in via config
**Given** `agent.pi_rpc = true` in `.deviate/config.toml`
**When** `AgentBackend.invoke()` resolves backend `"pi"`
**Then** instead of `["pi", "-p"]`, the subprocess spawns `["pi", "--mode", "rpc", "--no-session"]` with JSONL-over-stdin/stdout; `_invoke_blocking` is replaced by an RPC client that sends `{"type": "prompt", "content": "..."}`, parses streaming events (`agent_start`, `message_update`, `agent_end`), and extracts the final handover manifest from the `agent_end` event payload; `get_session_stats` response is captured into `pi.session_stats`.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->
- **Pi binary missing on PATH**: `subprocess.Popen(["pi", "-p"], ...)` raises `FileNotFoundError` → wrapped as `AgentBinaryNotFoundError(f"Agent binary not found on PATH for backend: pi — install via `npm install -g @earendil-works/pi-coding-agent`")`. Same handling as other backends.
- **Skill directory already exists as real directory (not symlink)**: `deviate init` skips creation with a `[yellow]SKIP[/]` log line — does NOT overwrite or delete existing user-managed skills.
- **`~/.pi/agent/` directory does not exist**: `deviate init` creates the directory tree (`mkdir -p ~/.pi/agent/skills`) before writing symlinks/settings.json.
- **Settings.json already contains non-DeviaTDD keys**: Merge logic preserves keys not prefixed with `deviate_` — only `deviate_provider`, `deviate_model`, `deviate_skill_paths` (or top-level keys managed by DeviaTDD) are written; user-managed keys are untouched.
- **Pi subprocess exits with non-zero code**: Existing `AgentSubprocessError` handling applies — stderr is captured and surfaced. No backend-specific error translation needed.
- **YAML handover manifest contains unknown fields**: `HandoverManifest` has `model_config = {"extra": "allow"}` (`src/deviate/core/agent.py:30`), so extra fields pass through validation — no Pi-specific schema changes needed.
- **Skill frontmatter missing `name:` or `description:`**: Pi's skill loader logs a warning but still loads the skill (per Agent Skills spec, only missing `description` is fatal). DeviaTDD's skills all have both fields, so this edge case does not trigger in practice — but the init flow should not fail if a third-party skill added to the directory lacks them.
- **Token stats emitted in non-RPC mode**: Pi's `--print-tokens` flag (print mode extension) or a final stdout footer line in `agent_end` events (RPC mode) provides stats. If stats are absent in print mode, `pi.session_stats` block in `prompts.log` is `null` — logged as a warning, not a failure.
- **Concurrent `deviate init` runs**: `~/.pi/agent/settings.json` write uses file-level locking (`fcntl.flock` like the existing ledger writer) to prevent races. Symlink creation is atomic via `os.symlink` (POSIX guarantees atomicity).
- **Cross-platform path handling**: Symlink targets use `pathlib.Path.absolute()` — Windows symlinks require admin privileges or Developer Mode; surface a clear error if `OSError: symbolic link privilege not held` is raised on Windows.
- **RPC mode streaming event parse error**: JSONL deserialization failure on a malformed event line → log warning, skip that line, continue parsing. Final `agent_end` event is the source of truth for the handover manifest.
- **Provider/model in `[models]` config not supported by Pi**: `~/.pi/agent/settings.json` writes the values as-is; Pi rejects unknown providers at runtime with a clear error — DeviaTDD does not pre-validate the provider list (keeps the integration lean).

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->
- `deviate init` skill symlink creation: ≤ 50ms total (20 symlinks × ~2ms each on macOS/Linux)
- `deviate init` settings.json write: ≤ 10ms (single file write)
- `AgentBackend.invoke()` Pi print mode spawn: ≤ 100ms cold start, ≤ 20ms warm (subprocess fork+exec)
- `BACKEND_COMMANDS["pi"]` dict lookup: ≤ 1μs (O(1) dict access)
- `AgentConfig.backend` Literal validation: ≤ 1ms (Pydantic model_validate overhead)
- `pi.session_stats` extraction + `prompts.log` append: ≤ 20ms per invocation
- Skill symlink existence check: ≤ 1μs (pathlib `.exists()` + `.is_symlink()` + `.resolve()`)
- `~/.pi/agent/settings.json` JSON parse on subsequent `init` runs: ≤ 5ms (small file, < 1KB)
- RPC mode JSONL event parsing throughput: ≥ 1000 events/second (json.loads + dict access in tight loop)
- Per-phase model swap in RPC mode (`set_model` command): ≤ 50ms round-trip (single JSONL request/response)
- Token savings target (measured via `pi.session_stats.cacheRead / (cacheRead + input)`): ≥ 30% cache-hit ratio on repeated phase invocations within the same session — proxy for prompt prefix cache utilization

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets** — `tests/core/test_agent.py`:
  - `test_pi_backend_subprocess_contract` — verify `pi -p` is the spawned command, prompt via stdin, YAML manifest extraction from stdout
  - `test_pi_backend_yaml_extraction` — Pi-shaped stdout (fenced YAML + `<handover_manifest>` tag) parses correctly
  - `test_pi_backend_missing_binary` — `FileNotFoundError` → `AgentBinaryNotFoundError` with install instructions
  - `test_pi_backend_model_flag_not_injected` — Pi print mode does NOT receive `--model` flag (model routes via settings.json instead)
  - `test_pi_rpc_mode_opt_in` — `agent.pi_rpc = true` spawns `pi --mode rpc --no-session` instead of `pi -p`
  - `test_pi_session_stats_logged` — `AGENT_RESULT` event contains `pi.session_stats` block when stats present in stdout
  - `test_stub_pi_backend_yields_canonical_manifest` — `StubPiBackend` fixture emits Pi-shaped output for downstream tests
  - `test_agent_config_literal_accepts_pi` — `AgentConfig(backend="pi")` validates; round-trip via TOML preserves value
  - `test_agent_config_literal_rejects_unknown` — `AgentConfig(backend="unknown")` raises `ValidationError`
- **Unit Sandbox Targets** — `tests/cli/test_init.py`:
  - `test_init_creates_pi_skill_symlinks` — 20 symlinks under `~/.pi/agent/skills/`, each pointing to correct project path
  - `test_init_generates_pi_settings_json` — settings.json content matches `[models]` config + `skillPaths`
  - `test_init_idempotent_pi_setup` — re-running init does not duplicate symlinks/settings.json; no errors on existing entries
  - `test_init_preserves_user_managed_settings_keys` — non-DeviaTDD keys in `settings.json` are preserved across re-runs
  - `test_init_pi_skill_symlinks_skip_existing_directories` — if `~/.pi/agent/skills/<name>` exists as a real directory, init logs SKIP and proceeds
  - `test_agent_choices_includes_pi` — `AGENT_CHOICES` tuple contains `"pi"` after init
  - `test_agent_to_backend_maps_pi` — `AGENT_TO_BACKEND["pi"] == "pi"`
- **Integration Sandbox Targets**:
  - `tests/cli/test_init_export_cycle.py` — verify full init + Pi export cycle completes within performance constraints (≤ 500ms for init, ≤ 200ms for symlink+settings.json setup)
  - `tests/core/test_agent.py` — verify Pi backend integrates with `_invoke_streaming` path (per-line output callback) when `output_callback` is provided

## Demonstration Path
```bash
# Unit tests for Pi backend contract
mise run test tests/core/test_agent.py::test_pi_backend_subprocess_contract -v
mise run test tests/core/test_agent.py::test_pi_backend_yaml_extraction -v
mise run test tests/core/test_agent.py::test_pi_backend_missing_binary -v
mise run test tests/core/test_agent.py::test_pi_rpc_mode_opt_in -v

# Unit tests for init flow
mise run test tests/cli/test_init.py::test_init_creates_pi_skill_symlinks -v
mise run test tests/cli/test_init.py::test_init_generates_pi_settings_json -v
mise run test tests/cli/test_init.py::test_init_idempotent_pi_setup -v

# Integration test: full init + Pi export cycle
mise run test tests/cli/test_init_export_cycle.py -v

# Manual smoke test (requires `pi` binary on PATH):
# 1. Run init with Pi backend
deviate init --agent pi --profile default
# 2. Verify symlinks
ls -la ~/.pi/agent/skills/ | grep deviate
# 3. Verify settings.json
cat ~/.pi/agent/settings.json
# 4. Run a single micro phase end-to-end
deviate red --task T001 --backend pi
# 5. Inspect prompts.log for pi.session_stats
grep "pi.session_stats" .deviate/prompts.log | tail -5
```