# RPC Streaming for Pi/OMP — Exploration

## Problem Definition

[Statement]: Catalog what currently exists in the repository to scope work that ships `deviate` driving Pi (`@earendil-works/pi-coding-agent`) and OMP (`oh-my-pi`) agent runtimes through their RPC subprocess mode and streaming live progress into a compact Rich-based TUI region. The product layer already declares this slice as `FLOW-04` in `specs/_product/flows/flows-streaming.md` and as the next release goal in `specs/_product/release-next.md`.

## Release Compass (per `specs/_product/release-next.md`)

Per Universal Invariant #8, the `## Goal` and `## Included Work` blocks of `specs/_product/release-next.md` are the release compass for this explore.

**Goal anchor** (verbatim from `specs/_product/release-next.md`): "**Goal anchor: FLOW-04 (Live-Stream Agent Progress via RPC)**."

**Goal** (verbatim from `specs/_product/release-next.md` §Goal): "Enable `deviate` meso and micro phases to drive Pi or OMP agent runtimes through their RPC mode and stream live progress (tool calls, thinking, edits) into a compact TUI that updates the same region in place rather than scrolling a wall of text. Ship one coherent slice: subprocess-based RPC with strict-LF JSONL framing, an event adapter that normalizes `AgentSessionEvent` frames, and a Rich-based TUI renderer capped at 10 lines."

**Included Work / Included Epics** (verbatim from `specs/_product/release-next.md` §Included Work):

| ID | Title | Type | Flow Refs |
|---|---|---|---|
| E04.1 | RPC subprocess + JSONL framing (C2, C3) | Epic | FLOW-04 |
| E04.2 | RPC command sender + Event Adapter (C4, C5) | Epic | FLOW-04 |
| E04.3 | TUI renderer + final-summary region (C6) | Epic | FLOW-04 |
| A04.1 | OMP transport parity — confirm `--mode rpc` flags match Pi and add an OMP-specific flag-mapping table | ADHOC | FLOW-04 |
| A04.2 | Reconnect strategy — define behavior when `SubprocessHandle` transitions to `disconnected` (reconnect, prompt user, or abort) | ADHOC | FLOW-04 |
| I04.1 | Wire `--agent {pi,omp}` flag into `deviate meso run` and `deviate micro run --all` (argv pass-through to C2) | Infra | none |
| I04.2 | Extend `.deviate/config.toml` `[models]` to declare RPC-mode args per agent id | Infra | none |

[Scope]: **This explore is non-duplicative with `specs/explore/pi-agent-backend.md`.** That artifact already catalogs the existing `AgentBackend` dispatch surface in `src/deviate/core/agent.py` (the `BACKEND_COMMANDS` / `AGENT_TO_BACKEND` / `MODEL_FLAGS` / `PROMPT_AS_ARG_BACKENDS` registries, `PI_RPC_COMMAND`, `_invoke_blocking`, `_invoke_streaming`, `AgentBackend.parse_output` YAML extractor, `StubAgentBackend` / `StubPiBackend` test isolation). Those surfaces are OUT OF SCOPE here. This explore covers the new streaming layer that the prior artifact could not:

- **The new streaming layer** (green-field inside the existing `deviate` package): `src/deviate/rpc/{subprocess,framing,commands,events}.py` (components C2–C5 per `specs/_product/architecture.md`) and `src/deviate/tui/renderer.py` (component C6).
- **The existing UI baseline the new renderer plugs into**: `src/deviate/ui/render.py` (module-level `stdout_lock`, `emit_jsonl`, `is_interactive`), `src/deviate/ui/pipeline.py` (Rich widgets `PipelineBanner`, `PhaseCallout`, `RunBoard`, `TrainIndicator`, `PipelineSummary`), `src/deviate/ui/monitor.py` (`OrchestrationMonitor` + `VALID_EVENT_TYPES`).
- **The existing CLI wiring that must accept `--agent {pi,omp}` pass-through** (release-next Infra I04.1): `_invoke_agent_phase` in `src/deviate/cli/meso.py`, `_invoke_agent` in `src/deviate/cli/micro.py`, `_resolve_agent_config` in `src/deviate/cli/__init__.py`.
- **The existing config surface that must extend** (release-next Infra I04.2): `.deviate/config.toml` (`[agent].backend = "omp"`) and `src/deviate/state/config.py` (`AgentConfig` Literal, `resolve_phase_model`, `resolve_model_for_phase`).
- **The wire-format contracts** already published at `libref pi rpc` (`packages/coding-agent/docs/rpc.md`) and `libref oh-my-pi rpc` (`docs/rpc.md`).
- **The planned package targets do not yet exist**: `ls src/deviate/` shows `cli core main.py prompts state ui visual` only — no `rpc/` and no `tui/` directory on disk. The entire FLOW-04 release is a green-field addition inside an existing Python package.

[Exclusions]: Architectural decisions, transport trade-offs, event-vocabulary design choices, model-routing strategy, reconnect policy (deferred to `deviate-research` / `deviate-adhoc` and release-next ADHOCs A04.1 and A04.2). The existing `AgentBackend` dispatch / `BACKEND_COMMANDS` / YAML manifest extractor (cataloged in `specs/explore/pi-agent-backend.md`). Implementation code, tests, configuration files, or scripts. Risk register and failure-mode analysis.

## Discovery Audit Results

### Headline Finding — The Streaming Layer Is Green-Field Inside the Existing Package

The release-next AC §1 declares `src/deviate/rpc/{subprocess,framing,commands,events}.py` and `src/deviate/tui/renderer.py` as install deliverables. None of these modules exist on disk today:

- `ls src/deviate/` returns only `cli core main.py prompts state ui visual` — no `rpc/` directory, no `tui/` directory.
- `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` carry zero references to `rpc|streaming|tui|live-stream` (grep returned empty).
- `grep -l "rpc\|streaming\|tui\|live-stream" specs/DeviaTDD-api.md specs/DeviaTDD-architecture.md src/deviate/main.py` returned no matches.

What DOES exist is the integration surface the new modules will plug into: `BACKEND_COMMANDS` / `AGENT_TO_BACKEND` / `MODEL_FLAGS` registries and `PI_RPC_COMMAND = ["pi", "--mode", "rpc", "--no-session"]` constant in `src/deviate/core/agent.py:61-122` (cataloged in `specs/explore/pi-agent-backend.md`); the Rich UI primitives + module-level `stdout_lock` in `src/deviate/ui/{render,pipeline,monitor}.py`; and the `AgentConfig.backend` Literal in `src/deviate/state/config.py:12-23` that already covers both `pi` and `omp`. The architecture anchor (`specs/_product/architecture.md` C2–C6) is on disk; the implementation is not.

### Verified Dependencies

- `typer>=0.12`: declared in `pyproject.toml:31`, used as CLI framework in `src/deviate/cli/__init__.py` and throughout `src/deviate/cli/`.
- `rich>=13.0`: declared in `pyproject.toml:32`, used for terminal I/O in `src/deviate/ui/pipeline.py`, `src/deviate/ui/render.py`, `src/deviate/cli/micro.py`.
- `pydantic>=2.0`: declared in `pyproject.toml:33`, used by `src/deviate/state/config.py` (`AgentConfig`, `DeviateConfig`, `SessionState`, `ProfileConfig`, `PytestReportConfig`).
- `pyyaml>=6.0.3`: declared in `pyproject.toml:34`, used in `src/deviate/core/agent.py:125-130` to parse YAML handover manifest blocks from agent stdout.
- `tree-sitter` (+ 20 language grammars): declared in `pyproject.toml:35-55`, used by `src/deviate/core/treesitter/` for `deviate inspect` and JUDGE/REFACTOR structural checks.
- `pytest`, `pytest-testmon`, `ruff`: declared in `[project.optional-dependencies].dev` (`pyproject.toml:67-72`); `mise.toml` wires `uv run pytest` and `uv run ruff` for `mise run test`, `lint`, `format`, `check`.

### Ghost Dependencies

- `pi` (CLI binary): referenced in `src/deviate/core/agent.py:65` (`"pi": "pi -p"`) and `src/deviate/core/agent.py:103` (`PI_RPC_COMMAND: list[str] = ["pi", "--mode", "rpc", "--no-session"]`), but no Python wrapper package is declared. Distribution model is npm (per upstream docs) — `pi` is reached exclusively via `subprocess.Popen`, matching the pattern used for `opencode`/`claude`/`droid`/`omp`. No ghost: this is the existing "external binary, no Python wrapper" convention.
- `omp` (CLI binary): referenced in `src/deviate/core/agent.py:70` (`"omp": "omp -p"`) and `src/deviate/core/agent.py:122` (`PROMPT_AS_ARG_BACKENDS = frozenset({"omp"})`). Same external-binary convention — not declared in `pyproject.toml` by design.
- None other observed. All declared `pyproject.toml` deps are reachable; all invoked CLIs follow the `subprocess.Popen` pattern and intentionally carry no Python wrapper.

### Manifest Files Observed

- `pyproject.toml`: PEP 621 metadata; declares Python 3.13+ runtime, hatchling build backend, 20 runtime deps, optional `[dev]` group, `[project.scripts].deviate = "deviate.main:app"`, `[tool.hatch.build.targets.wheel].packages = ["src/deviate"]`, `[tool.pytest.ini_options].testpaths = ["tests"]`.
- `mise.toml`: Project execution contract; declares `python = "3.13"`, `uv = "latest"`, tasks `test` (`uv run pytest --testmon-noselect tests/ -v`), `lint` (`uv run ruff check`), `format` (`uv run ruff format`), `format-check` (`uv run ruff format --check`), `check` (depends on `lint` + `format-check`), `setup` (`uv sync --extra dev && git config core.hooksPath .githooks`).
- `.mise.toml` carries NO `check-types` task — the echo placeholder returns "No type checker configured" (per `mise.toml:42-44`), so `ruff` is the sole static-analysis gate.
- `specs/constitution.md`: Authoritative governance document — four-layer architecture, Python 3.13 + Typer + Rich, pytest + ruff, append-only JSONL ledgers, HITL gates, Definition of Done with CHANGELOG discipline.
- `.deviate/config.toml`: Per-workdir active config; declares `profile = "default"`, `timeout_seconds = 300`, `agent_export_mode = "local"`, `graphite = false`, `use_context = true`, `use_libref = true`, `[agent].backend = "omp"` (one-line `[agent]` table).
- `CHANGELOG.md`: Keep-a-Changelog format; `[Unreleased]` section already records the FLOW-04 architecture correction, Product-layer skill persistence mandate, and `deviate run` becoming a full-pipeline orchestrator with per-task dispatch moved to `deviate micro run`.

### Test Runner Configuration

- `mise.toml:13-15` (`[tasks.test]`): `uv run pytest --testmon-noselect tests/ -v` — forces a full-suite run to keep `.testmondata` fresh.
- `mise.toml:17-19` (`[tasks.test-e2e]`): `bats tests/e2e/`.
- `mise.toml:21-23` (`[tasks.test-affected]`): `uv run pytest --testmon-forceselect` — affected-only subset.
- `mise.toml:26-35` (`[tasks.lint]` / `[tasks.format]` / `[tasks.format-check]`): `uv run ruff check` / `uv run ruff format` / `uv run ruff format --check`.
- `pyproject.toml:84-85` (`[tool.pytest.ini_options]`): `testpaths = ["tests"]`.
- Performance contract from `AGENTS.md`: "src/deviate/cli/micro.py::_run_pytest invokes pytest as a subprocess (~5s). Tests calling CLI commands that hit this function MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture to keep the full suite under 30s."

### Manifest-Constitution Divergence

- **Constitution §1 Architectural Principles vs Product layer.** Constitution §1 enumerates a "Three-Layer Architecture: Macro / Meso / Micro" (`specs/constitution.md:9`). `CHANGELOG.md` and `specs/_product/release-next.md` (and `specs/_product/architecture.md`) reference a four-layer model that adds an optional Product layer above Macro. The constitution's own §6 Version History line `0.6.0 — Promoted the Product layer (Flows → Architecture → Release) into §1 Architectural Principles as an optional fourth layer` reconciles this — the constitution header text lags the changelog. Both quoted verbatim; not adjudicated.
- **Constitution §2 Tech Stack Standards omits `omp`.** The constitution's Tech Stack (`specs/constitution.md:18-23`) names "Python 3.13" + "Typer" + "Rich" but does not enumerate the agent backends. The implementation (`src/deviate/core/agent.py:61-72`) supports five CLI backends plus `stub`. Informational only — the constitution does not claim to enumerate backends — flagged for downstream research awareness.
- **Aider-as-substrate stale reference** in `specs/constitution.md:36` ("Micro-sandbox: Aider Python API (aider.coders.Coder)") — already flagged in `specs/explore/pi-agent-backend.md` Manifest-Constitution Divergence; cross-referenced, not re-adjudicated here.

## Constitution Quotes

- **Architectural Principles** (`specs/constitution.md:9`): "**Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). The Product layer is skipped in single-feature repos; the remaining three layers have strict phase gates — no layer may be skipped."
- **Tech Stack Standards** (`specs/constitution.md:18-23`): "Python 3.13; Target: CLI application (`deviate`); Framework: Typer (CLI entry points) with Rich for terminal I/O; No persistent database runtime (all state tracked in JSONL ledgers and TOML config); Session state: JSON files under `.deviate/`; Issue ledger: `specs/issues.jsonl` (append-only JSONL); Task ledger: `specs/**/tasks.jsonl` (append-only JSONL); Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment."
- **Testing Protocols** (`specs/constitution.md:50-56`): "Test framework: pytest; Test root: `tests/`; Test extension: `.py`; Test command: `pytest tests/ -v`; Lint command: `ruff check .`; E2E command: `bats tests/e2e/`; Coverage target: >= 80%; GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files; REFACTOR phase runs regression gate: tests must re-pass after polish."
- **Definition of Done** (`specs/constitution.md:81-91`): "[ ] Code implemented (satisfies acceptance criteria from `spec.md`); [ ] Tests passing (pytest with clean exit code 0); [ ] Lint passing (ruff check with no violations); [ ] Judge phase passed (git diff validated against `spec.md` invariants); [ ] E2E tests passing (if applicable; bats for CLI integration); [ ] Documentation updated (`spec.md` and `design.md` reflect final implementation); [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies); docs-only, test-only, CI/tooling, and behavior-preserving refactors are exempt; [ ] No governance violations (constitution rules upheld, no HITL gates bypassed); [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)."

## Architectural Baselines

[Pattern_Over_Instance]: One representative example is captured per category, not every file. All paths strictly relative to `repo_root`.

- **Existing Architectural Patterns**:
  - **Backend dispatch table** (`src/deviate/core/agent.py:61-72`): A module-level `dict[str, str]` maps user-facing names to shell command prefixes; `AGENT_TO_BACKEND` resolves aliases (`factory` → `droid`); `MODEL_FLAGS` declares per-backend model-flag support; `PROMPT_AS_ARG_BACKENDS` declares which backends take the prompt as a positional argv. This is the integration surface any new transport has to plug into.
    ```python
    BACKEND_COMMANDS: dict[str, str] = {
        "opencode": "opencode run",
        "claude": "claude -p --permission-mode auto",
        "droid": "droid exec",
        "pi": "pi -p",
        "omp": "omp -p",
        "stub": "stub",
    }
    ```
  - **Popen subprocess invocation** (`src/deviate/core/agent.py:181-213` and `:215-272`): `AgentBackend._invoke_blocking` calls `proc.communicate()` with the prompt piped via stdin and a configurable timeout; `_invoke_streaming` reads stdout/stderr line-by-line via threads with per-line output callbacks. Both are byte-stream-based — replacing them with a JSONL-aware reader is the cleanest seam for RPC mode.
  - **Type-safe backend literal** (`src/deviate/state/config.py:12-23`): `AgentConfig.backend: Literal["opencode", "claude", "droid", "pi", "omp"]` — `omp` is already first-class; `pi` and `omp` are already accepted by the literal, so an RPC-mode flag does not require widening the literal.
  - **YAML handover manifest extraction** (`src/deviate/core/agent.py:125-180`): `AgentBackend.parse_output` locates a YAML block (or `<handover_manifest>` tag) in the agent's stdout, parses it, and validates against the `HandoverManifest` Pydantic schema. The contract is backend-agnostic — RPC mode does not need to alter it, only the way stdout is consumed.
  - **PI RPC command constant** (`src/deviate/core/agent.py:103`): `PI_RPC_COMMAND: list[str] = ["pi", "--mode", "rpc", "--no-session"]` — the RPC argv already lives as a module constant; the missing piece is the subprocess spawn + JSONL framing + event adapter that consumes its stdout.

- **Infrastructure & Operations**:
  - **Single shared stdout lock** (`src/deviate/ui/render.py:24-30`): A module-level `threading.Lock` named `stdout_lock` serializes all process-level writes to the interactive Console / raw `sys.stdout` fd. The comment block explains the lock closes a historical SIGSEGV path in `run --all` JUDGE on macOS when background reader threads race main-thread `c.print` writes. Any new TUI renderer MUST take this lock on every redraw.
  - **Interactive detection** (`src/deviate/ui/render.py:40-46`): `is_interactive()` reads `os.environ.get("CI")` and `os.isatty(sys.stdout.fileno())`. The TUI region needs to be skipped when stdout is not a TTY (CI / pipes) and the final-summary region takes over.
  - **Mise-driven lifecycle** (`mise.toml:54-56`): `mise run setup` runs `uv sync --extra dev && git config core.hooksPath .githooks`. The acceptance criterion in `release-next.md` that "mise run setup installs `src/deviate/rpc/{subprocess,framing,commands,events}.py`" must be satisfied by source placement alone — mise setup does not currently run an install step beyond `uv sync`.
  - **Git hooks at `.githooks/`** (per `mise.toml:55`): pre-commit hook path is wired by setup. The pre-commit hook runs the full test suite (per `AGENTS.md` and the post-script runtime budget of 180s).
  - **No containerization / no service runtime** (`specs/constitution.md:37-38`): The implementation runs locally on the host; the only external runtime is the agent subprocess itself. RPC mode extends the existing subprocess boundary; no new runtime surface is introduced.

- **Data & State Management**:
  - **Append-only JSONL ledgers** (`specs/issues.jsonl`, `specs/**/tasks.jsonl`): All session state is sequential-line-parseable; no in-place mutations. `.gitattributes` declares `merge=union` for the cross-branch merge strategy (per `specs/constitution.md:96` v0.4.0 entry).
  - **TOML config surface** (`.deviate/config.toml`): Current single-line `[agent]` table — `backend = "omp"`. The release-next infrastructure work (I04.2) extends `[models]` to declare RPC-mode args per agent id; that is a new schema, not yet on disk.
  - **No persistent agent-runtime state**: Backends are stateless invocations today — each micro/meso/macro call spawns a fresh subprocess. RPC mode does not change this: `pi --mode rpc --no-session` and `omp --mode rpc` are documented as no-session, no-persistent-runtime per upstream docs.
  - **In-process event queue** (`src/deviate/ui/monitor.py`): `OrchestrationMonitor` already maintains an in-process event deque with `push_event(event_type, **data)`. The new TUI renderer can subscribe to this monitor without re-architecting the orchestration layer.

- **Quality, Safety & Observability**:
  - **JUDGE phase scope discipline** (`specs/constitution.md:12`): "GREEN phase writes only to `src/` and permitted implementation paths. Any mutation outside this allow-list is flagged by the JUDGE phase as a scope violation." The new `src/deviate/rpc/` and `src/deviate/tui/` packages live under `src/`, so the GREEN allow-list already covers them.
  - **Tamper Guard sandbox** (per `specs/constitution.md` §1 and `specs/explore/pi-agent-backend.md`): Micro-layer is sandboxed to writes against `src/**/*.py` only; `tests/`, `specs/`, and config files are read-only during micro execution. RPC-mode wiring is micro-layer work that must respect this constraint.
  - **Process-level stdout lock** (`src/deviate/ui/render.py:24-30`): documented above under Infrastructure; this is the single piece of safety infrastructure the new TUI renderer must integrate with.
  - **Validation gate** (`mise run check`): `lint` + `format-check` — no type checker, so ruff is the sole static gate. New RPC/TUI code must pass ruff.
  - **Regression budget** (from `AGENTS.md`): full test suite must finish in < 30s. Tests for new RPC components must mock subprocess boundaries (mirroring the existing `_run_pytest` mock discipline) to keep the suite under the budget.

- **External Integrations**:
  - **`pi` (`@earendil-works/pi-coding-agent`, npm)** — CLI binary `pi`. Documented at `libref pi rpc` (`packages/coding-agent/docs/rpc.md`): "RPC mode uses strict JSONL semantics with LF (`\n`) as the only record delimiter. … Split records on `\n` only. Accept optional `\r\n` input by stripping a trailing `\r`. Do not use generic line readers that treat Unicode separators as newlines." Reference Python client (`packages/coding-agent/docs/rpc.md`): `subprocess.Popen(["pi", "--mode", "rpc", "--no-session"], stdin=PIPE, stdout=PIPE, text=True)` with `proc.stdin.write(json.dumps(cmd) + "\n")` + `proc.stdin.flush()`. Event taxonomy: `agent_start`, `agent_end`, `turn_start`, `turn_end`, `message_start`, `message_update`, `message_end`, `tool_execution_start/update/end`, `auto_compaction_start/end`, `auto_retry_start/end`, `ttsr_triggered`, `todo_reminder`, `todo_auto_clear`; deltas in `message_update.assistantMessageEvent` (`text_delta`, `thinking_delta`, `toolcall_delta`).
  - **`omp` (`oh-my-pi`)** — CLI binary `omp`. Documented at `libref oh-my-pi rpc` (`docs/rpc.md`): "RPC mode runs the coding agent as a newline-delimited JSON protocol over stdio. stdin: commands (`RpcCommand`), extension UI responses, and host-tool updates/results; stdout: a ready frame, command responses (`RpcResponse`), session/agent events, extension UI requests, host-tool requests/cancellations." Same `AgentSessionEvent` taxonomy as Pi. `omp --mode rpc` is documented to disable automatic session title generation and to reject `@file` CLI arguments.
  - **`opencode`**, **`claude`**, **`droid`**, **`stub`**: existing print-mode backends; not RPC-enabled; will continue to use the streaming stdout reader at `src/deviate/core/agent.py:215-272`. Backwards-compat invariant from `release-next.md:21`: "legacy logging path preserved when C2–C6 are absent."
  - **No third-party SDK wrapper** is declared or planned. The convention is subprocess isolation; C2 (`src/deviate/rpc/subprocess.py`) extends that boundary.

## Ecosystem Research

### Best Practices

- **Strict-LF JSONL framing is mandatory.** `pi@latest` (`packages/coding-agent/docs/rpc.md`): "RPC mode uses strict JSONL semantics with LF (`\n`) as the only record delimiter. … In particular, Node `readline` is not protocol-compliant for RPC mode because it allows Unicode line separators as newlines." `oh-my-pi@latest` (`docs/rpc.md`) confirms the same protocol: "newline-delimited JSON protocol over stdio."
- **Subprocess isolation over in-process linking.** `pi@latest` (`packages/coding-agent/docs/sdk.md`): "RPC mode is preferred when: You're integrating from another language; You want process isolation; You're building a language-agnostic client." `deviate` is Python driving a TypeScript runtime, and process isolation is mandated by the constitution §1 Git Isolation Principle.
- **Request/response correlation by generated id.** `oh-my-pi@latest` (`docs/rpc.md`, `rpc-client.ts` note): "Correlates responses by generated `req_<n>` ids." C4 (`src/deviate/rpc/commands.py`) must generate ids in that shape so future host-tool / extension-UI surfaces (which `oh-my-pi` documents at `docs/rpc.md` Extension UI Sub-Protocol) can reuse the correlation registry.
- **Unknown event types render as `…`.** Product-layer invariant per `release-next.md:53` and `specs/_product/architecture.md:48-49`: C5 must map every documented `AgentSessionEvent` type and render unknown values as `…` rather than raising. The `oh-my-pi` `rpc-client.ts` convenience wrapper "dispatches recognized core `AgentEvent` types to listeners" — the same pattern.

### Common Use Cases & Pitfalls

- **Pitfall — Unicode line separators.** `pi@latest` (`packages/coding-agent/docs/rpc.md`): "Do not use generic line readers that treat Unicode separators as newlines." Release-next AC §6 mandates a regression test that feeds records containing `\u2028` and `\u2029` and asserts the splitter does NOT treat them as record terminators.
- **Pitfall — Backwards compatibility.** `release-next.md:21`: "legacy logging path preserved when C2–C6 are absent." C2–C6 must be opt-in; existing print-mode invocations of `pi`/`omp`/`opencode`/`claude`/`droid` must keep working.
- **Pitfall — Reconnect policy is undefined.** `release-next.md:38` (ADHOC A04.2): "Reconnect strategy — define behavior when `SubprocessHandle` transitions to `disconnected` (reconnect, prompt user, or abort)." The product layer surfaces the open question but does not pre-decide; the `deviate-adhoc` flow consumes this.
- **Pitfall — `--agent {pi,omp}` flag wiring.** `release-next.md:39` (Infra I04.1): argv pass-through to C2 must include `--mode rpc` (per `PI_RPC_COMMAND` already at `src/deviate/core/agent.py:103`). The flag is not currently a positional in any CLI command.

### Standard Tooling

- **Available offline docs.** `libref list` output: `pi@latest` (1.1 MB, 454 sections) and `oh-my-pi@latest` (2.8 MB, 1337 sections) are already registered. Both packages are documented under `packages/coding-agent/docs/rpc.md` (Pi) and `docs/rpc.md` (OH-MY-PI) — same protocol vocabulary.
- **No new Python dependency required.** The wire format and subprocess boundary are both reachable via stdlib (`subprocess`, `json`, `threading`). `rich>=13.0` (already in `pyproject.toml:32`) is the only TUI primitive required; no need for `prompt_toolkit`, `textual`, or `urwid`.
- **Test boundary.** Tests can use `subprocess.Popen` against a stub script that writes a recorded JSONL stream to stdout, exercising C3 framing + C5 event adapter without spawning a real `pi`/`omp` binary. This mirrors the existing `StubAgentBackend` / `StubPiBackend` pattern (`src/deviate/core/agent.py:500-527`).

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
|:---|:---|:---|:---|
| `specs/constitution.md` | Manifest | Authoritative governance document — four-layer architecture, Python 3.13 + Typer + Rich, pytest + ruff, Definition of DoD with CHANGELOG discipline | `# Project Constitution`<br>`Version: 0.6.0`<br>`---`<br>`## 1. Architectural Principles`<br>`- **Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).` |
| `specs/_product/release-next.md` | Spec | Next-release goal anchored on FLOW-04 — sets the boundary of the RPC streaming slice | `# DeviaTDD Next Release`<br>`Version: 0.1.0`<br>`Status: Active`<br>`Goal anchor: FLOW-04 (Live-Stream Agent Progress via RPC)`<br>`Architecture anchor: specs/_product/architecture.md (v0.2.0)`<br>`Domain model anchor: specs/_product/domain-model.md (v0.2.0)` |
| `specs/_product/architecture.md` | Spec | Cross-epic architecture — declares components C2 (subprocess), C3 (JSONL framing), C4 (commands), C5 (event adapter), C6 (TUI renderer) with verbatim protocol surface and two ADRs (subprocess-vs-link, dedicated framing layer) | `### C2 — Subprocess Adapter (new — `src/deviate/rpc/subprocess.py`)`<br>`- Responsibility: Spawns and supervises the chosen agent runtime as a child process in RPC mode.`<br>`- Contract surface:`<br>`  - `spawn(agent: Literal["pi","omp"], args: list[str]) -> Popen``<br>`  - `args` includes `--mode rpc` and any provider/model flags forwarded verbatim from `.deviate/config.toml`.`<br>`- Returns a live `Popen` with `stdin`, `stdout`, `stderr` wired for JSONL framing.` |
| `specs/_product/domain-model.md` | Spec | Cross-epic entities — `AgentRuntime`, `SubprocessHandle`, `AgentFrame`, `RpcCommand`, `RpcResponse`, `AgentEvent`, `StreamingDelta`, `TuiRenderer`, `Terminal` with relationship table | `### AgentRuntime`<br>`- Attributes:`<br>`  - `id`: enum(`"pi"`, `"omp"`)`<br>`  - `mode`: enum(`"rpc"`) — only RPC mode is in scope for FLOW-04`<br>`  - `state`: enum(`"spawning"`, `"streaming"`, `"disconnected"`, `"closed"``)` |
| `specs/_product/flows/flows-streaming.md` | Spec | FLOW-04 — Live-Stream Agent Progress via RPC — actor Developer, domain Agent Integration; triggers on `deviate run`; success state is TUI under 10 lines with final summary after clear | `## FLOW-04 Live-Stream Agent Progress via RPC`<br>`- Actor: Developer`<br>`- Domain: Agent Integration`<br>`- Status: Active`<br>`### Problem / job to be done`<br>`- Stream Pi/OMP agent progress (tool calls, thinking, edits) into a compact TUI that updates in place instead of scrolling a wall of text.` |
| `specs/_product/flows/index.md` | Spec | Flow index — currently four flows (FLOW-01..FLOW-04); FLOW-04 is the only one anchored on Agent Integration | `# DeviaTDD Product Flow Index`<br>`\| Flow ID \| Name \| Actor \| Domain \| Status \| Source \|`<br>`\|---------\|------\|-------\|--------\|--------\|--------\|`<br>`\| FLOW-01 \| Flows \| Developer \| Software Engineering \| Active \| `specs/_product/flows/flows-product.md` \|`<br>`\| FLOW-02 \| Architecture \| Developer \| Software Engineering \| Active \| `specs/_product/flows/flows-product.md` \|` |
| `pyproject.toml` | Manifest | PEP 621 metadata; declares Python 3.13, typer, rich, pydantic, pyyaml, tree-sitter, pytest, ruff; `[project.scripts].deviate = "deviate.main:app"`; build target `["src/deviate"]` | `[project]`<br>`name = "deviatdd"`<br>`version = "2.7.3"`<br>`description = "DeviaTDD CLI — agent orchestration framework"`<br>`requires-python = ">=3.13"`<br>`dependencies = [`<br>`    "typer>=0.12",`<br>`    "rich>=13.0",`<br>`    "pydantic>=2.0",` |
| `mise.toml` | Manifest | Project execution contract; declares Python 3.13, uv, tasks `test`, `lint`, `format`, `format-check`, `check`, `setup`, `setup` wires `uv sync --extra dev` and `core.hooksPath .githooks` | `[env]`<br>`python = "3.13"`<br>`[tools]`<br>`python = "3.13"`<br>`uv = "latest"`<br>`[tasks.test]`<br>`run = "uv run pytest --testmon-noselect tests/ -v"` |
| `.deviate/config.toml` | Config | Per-workdir active config; `profile = "default"`, `agent.backend = "omp"`, `[models]` not yet declared — release-next Infra I04.2 adds it | `profile = "default"`<br>`timeout_seconds = 300`<br>`agent_export_mode = "local"`<br>`graphite = false`<br>`use_context = true`<br>`use_libref = true`<br>`[agent]`<br>`backend = "omp"` |
| `src/deviate/core/agent.py` | Codebase_File | Backend registry, `PI_RPC_COMMAND` constant, Popen invocation, YAML manifest parser, timeout/retry loop, StubAgentBackend / StubPiBackend test isolation | `BACKEND_COMMANDS: dict[str, str] = {`<br>`    "opencode": "opencode run",`<br>`    "claude": "claude -p --permission-mode auto",`<br>`    "droid": "droid exec",`<br>`    "pi": "pi -p",`<br>`    "omp": "omp -p",`<br>`    "stub": "stub",`<br>`}` |
| `src/deviate/state/config.py` | Codebase_File | Pydantic config models — `AgentConfig.backend` Literal (already covers `pi` and `omp`), per-phase `models` resolver (`resolve_phase_model`, `resolve_model_for_phase`) | `class AgentConfig(BaseModel):`<br>`    # Agent backend: "opencode", "claude", "droid", "pi", or "omp"`<br>`    backend: Literal["opencode", "claude", "droid", "pi", "omp"] = "opencode"`<br>`    # Agent invocation timeout in seconds (must be > 0)`<br>`    timeout: int = Field(default=600, gt=0)` |
| `src/deviate/cli/__init__.py` | Codebase_File | User-facing agent selection (`AGENT_CHOICES`, `AGENT_TO_BACKEND`), Typer CLI composition, `_resolve_agent_config` helper | `AGENT_CHOICES: tuple[str, ...] = ("factory", "droid", "claude", "opencode", "pi", "omp")`<br>`AGENT_TO_BACKEND: dict[str, str] = {`<br>`    "factory": "droid",<br>`    "droid": "droid",<br>`    "claude": "claude",<br>`    "opencode": "opencode",<br>`    "pi": "pi",<br>`    "omp": "omp",<br>`}` |
| `src/deviate/cli/meso.py` | Codebase_File | Meso-layer `_invoke_agent_phase` — single backend call per `plan` / `tasks` phase; entry point that must accept `--agent {pi,omp}` pass-through to C2 per release-next I04.1 | `def _invoke_agent_phase(`<br>`    phase: str,`<br>`    contract: dict[str, str],`<br>`    cwd: str | None = None,`<br>`) -> None:`<br>`    """Build a slim prompt, invoke the agent, and abort on failure."""` |
| `src/deviate/cli/micro.py` | Codebase_File | Micro-layer `_invoke_agent`, `_run_pytest` (mocked in tests for < 30s suite), `_make_output_handler` (Rich output callback with stdout lock); `run_command` is the `micro run` entry point that must accept `--agent` per I04.1 | `def _invoke_agent(`<br>`    prompt: str,`<br>`    c: Console,`<br>`    backend_name: str = "opencode",`<br>`    task_id: str = "",`<br>`    phase: str = "",`<br>`    output_callback: Callable[[str], None] | None = None,`<br>`    model: str | None = None,`<br>`) -> tuple[HandoverManifest | None, str]:` |
| `src/deviate/ui/render.py` | Codebase_File | Module-level `stdout_lock` (`threading.Lock`), `emit_jsonl` (JSONL stdout writer for `--json` mode), `is_interactive()` — the safety primitives any new TUI renderer MUST integrate with | `_stdout_lock = threading.Lock()`<br>`stdout_lock = _stdout_lock`<br>`def emit_jsonl(event: str, **fields: Any) -> None:`<br>`    with _stdout_lock:`<br>`        data = {"event": event, "timestamp": _now_iso(), **fields}`<br>`        sys.stdout.write(json.dumps(data) + "\n")`<br>`        sys.stdout.flush()` |
| `src/deviate/ui/pipeline.py` | Codebase_File | Rich pipeline widgets — `PipelineBanner`, `PhaseCallout`, `RunBoard`, `TrainIndicator`, `PipelineSummary`; pattern-over-instance baseline for how the new `TuiRenderer` redraws a fixed region | `class RunBoard:`<br>`    """Live, multi-row task table for `deviate micro run --all`."""`<br>`    def __init__(self, tasks: list[TaskStatus], ...) -> None: ...`<br>`    def render(self) -> Group:`<br>`        """Return a fresh Rich Group containing the table + footer."""` |
| `src/deviate/prompts/assembly.py` | Codebase_File | Layer routing map `_LAYER_MAP` — Macro/Meso/Micro → auto prefix; package-resource loader; constitution injection (micro-layer entries shown, the four phases this release touches) | `_LAYER_MAP: dict[str, str | None] = {`<br>`    "red": "micro-auto",`<br>`    "green": "micro-auto",`<br>`    "judge": "micro-auto",`<br>`    "refactor": "micro-auto",`<br>`}` |
| `src/deviate/main.py` | Codebase_File | CLI entry point — registers `faulthandler` before any other import to catch C-extension SIGSEGVs; re-exports `cli` as `app` for `[project.scripts]` | `"""`<br>`faulthandler.enable()`<br>`from .cli import cli`<br>`app = cli`<br>`__all__ = ["app"]` |
| `tests/conftest.py` | Test | Test fixtures for git isolation: `_git_env`, `tmp_git_repo` — every test git call uses `cwd=<tmp_git_repo>` + `env=_git_env()` | `def _git_env() -> dict[str, str]:`<br>`    """Return env with GIT_* vars stripped — must be used for every git call in tests."""`<br>`    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}` |
| `tests/test_cli/test_micro.py` | Test | Top-level CLI smoke test for `deviate micro run`; entry-point registration through Typer; representative example for where new `--agent {pi,omp}` flag tests will land (release-next Infra I04.1) | `from __future__ import annotations`<br>`import json`<br>`import subprocess`<br>`import warnings`<br>`from pathlib import Path`<br>`from unittest.mock import MagicMock, patch`<br>`import pytest`<br>`from typer.testing import CliRunner`<br>`from deviate.cli.__init__ import cli`<br>`from deviate.cli.micro import _run_judge_phase` |
| `tests/test_micro/test_red.py` | Test | Micro-layer RED-phase tests; representative example for the new TUI redraw-budget regression test (release-next AC §4: "rendered region never exceeds 10 lines across 1,000 simulated events") | `from __future__ import annotations`<br>`import json`<br>`import subprocess`<br>`from contextlib import chdir`<br>`from pathlib import Path`<br>`from unittest.mock import patch`<br>`from typer.testing import CliRunner`<br>`from deviate.cli import cli`<br>`from deviate.state.config import SessionState`<br>`from deviate.state.ledger import TaskRecord` |
| `tests/e2e/test_macro_workflow.bats` | Test | Bats E2E CLI smoke suite — verifies the installed `deviate` binary is on PATH and every subcommand accepts `--help`; the bats framework under which a new RPC framing E2E test would land (release-next AC §6: Unicode line separator regression) | `#!/usr/bin/env bats`<br>`#`<br>`# CLI smoke suite — verifies that the installed `deviate` binary is on PATH,`<br>`# reports the expected version, and that every documented subcommand accepts`<br>`# `--help`. Pure installation / packaging smoke; behavioral tests live in`<br>`# `tests/` (pytest). Runs in CI under `.github/workflows/ci.yml`.`<br>`#`<br>`# Each test starts in a fresh tmpdir so `deviate` does not pick up the host`<br>`# repo's `.deviate/session.json` or `specs/` state.` |
| `CHANGELOG.md` | Doc | Keep-a-Changelog `[Unreleased]` discipline — release-next AC §10 mandates a `[Unreleased] → Added` bullet for the new `--agent` flag and the TUI renderer | `## [Unreleased]`<br>`### Changed`<br>`- **\`/deviate-architecture\` (v1.1.0) now mandates \`libref\` verification for every architectural claim.**` |

## Scope Sizing

| Metric | Value |
|:---|:---|
| Estimated Complexity | High |
| Files Likely Modified | `src/deviate/cli/__init__.py` (extend `--agent {pi,omp}` pass-through into meso/micro), `src/deviate/cli/meso.py` (`_invoke_agent_phase` argv), `src/deviate/cli/micro.py` (`_invoke_agent` argv), `src/deviate/core/agent.py` (extend `BACKEND_COMMANDS` with RPC argv, broaden `_invoke_blocking`/`_invoke_streaming`), `src/deviate/state/config.py` (extend `AgentConfig` schema with RPC flags + `[models]` per-agent RPC-arg map per I04.2); **new**: `src/deviate/rpc/__init__.py`, `src/deviate/rpc/subprocess.py`, `src/deviate/rpc/framing.py`, `src/deviate/rpc/commands.py`, `src/deviate/rpc/events.py`, `src/deviate/tui/__init__.py`, `src/deviate/tui/renderer.py`; tests: `tests/test_rpc/test_subprocess.py`, `tests/test_rpc/test_framing.py`, `tests/test_rpc/test_commands.py`, `tests/test_rpc/test_events.py`, `tests/test_tui/test_renderer.py`, plus a 1,000-event E2E test under `tests/e2e/`; `specs/constitution.md` (no change expected — tech stack already covers Typer + Rich + subprocess), `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` (document new flags and modules); `CHANGELOG.md` `[Unreleased] → Added`. |
| New Modules Required | Yes — `src/deviate/rpc/{subprocess,framing,commands,events}.py` (C2–C5 per `specs/_product/architecture.md`) and `src/deviate/tui/renderer.py` (C6). All six modules are explicitly declared by the release-next AC §1. |
| New Persistence / Data Models | No new database, no new append-only ledger. `AgentFrame`, `RpcCommand`, `RpcResponse`, `AgentEvent`, `StreamingDelta`, `TuiRenderer`, `Terminal` are declared in `specs/_product/domain-model.md` but live as in-process dataclasses / Pydantic models, not persisted. |
| New External Integrations | No new external package. `pi` and `omp` CLIs are already integrated as print-mode backends; the work promotes them to RPC mode without adding new binaries. Both are documented offline at `libref pi rpc` and `libref oh-my-pi rpc`. |
| Upstream / Cross-Cutting Concerns | (a) `[models]` schema extension (I04.2) — needs an additive change so existing `.deviate/config.toml` files (no `[models]` section) keep parsing. (b) Reconnect policy ADHOC A04.2 — open question with three candidate policies, deferred to `deviate-adhoc`. (c) OMP transport parity ADHOC A04.1 — verify OMP `--mode rpc` flag set matches Pi. (d) `--agent` argv pass-through (I04.1) must coexist with the existing `AGENT_TO_BACKEND` aliasing layer (e.g. `factory` → `droid`). (e) GREEN-scope enforcement per constitution §1 — new modules live under `src/`, so already in the allow-list. (f) Test budget discipline per `AGENTS.md` — RPC subprocess tests must mock `Popen` boundaries to keep the suite < 30s. (g) `stdout_lock` integration — the new TUI renderer must take `src/deviate/ui/render.py::stdout_lock` on every redraw to avoid the SIGSEGV path documented in the lock's comment block. |
| Rationale | The release-next scope is bounded but multi-module: six new modules under two new packages (`src/deviate/rpc/`, `src/deviate/tui/`), one new CLI flag wired through meso and micro, a `[models]` schema extension, three ADHOCs (reconnect policy, OMP parity, install ergonomics), and a regression test suite covering strict-LF framing under Unicode separators, the full `AgentSessionEvent` taxonomy, and a 1,000-event TUI redraw budget. The architecture anchor (`specs/_product/architecture.md`) is already in place at FLOW-04 scope, so this is a build pass, not a design pass — but it touches four existing call sites and the GREEN-scope discipline means each module lands as a separate epic with its own issue file. |

## Status Summary

| Metric | Value |
|:---|:---|
| STATUS | SUCCESS |
| EXPLORE_SLUG | rpc-streaming |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/rpc-streaming.md |
| NEXT_ACTION | Run `/deviate-research` (High complexity) — the work spans six new modules across two new packages, three ADHOCs, and a `[models]` schema extension. The release-next architecture anchor is already on disk, so research will focus on locking down ADHOC A04.1 (OMP transport parity) and A04.2 (reconnect policy) before design. |