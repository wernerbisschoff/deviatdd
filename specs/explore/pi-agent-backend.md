# Pi Agent Backend — Exploration

## Problem Definition

[Statement]: Integrate the Pi agent (`@earendil-works/pi-coding-agent`, CLI binary `pi`) as a first-class DeviaTDD backend option for the micro layer (and optionally meso), reusing DeviaTDD's existing skill catalogue (`src/deviate/prompts/skills/<name>/SKILL.md`) and the YAML handover manifest contract. The exploration covers required customisations, expected token savings, and whether Pi provides native skill discovery that DeviaTDD can consume directly.

[Scope]: Existing backend abstraction (`AgentBackend`), backend command registry (`BACKEND_COMMANDS`), user-facing agent selection (`AGENT_CHOICES` / `AGENT_TO_BACKEND`), per-phase model routing via `[models]` in `.deviate/config.toml`, micro/meso/macro invocation surface in `src/deviate/cli/{micro,meso,macro}.py`, and the skill asset vault under `src/deviate/prompts/skills/`. The exploration examines Pi's binary invocation modes (`-p` print, `--mode rpc`), Agent Skills standard conformance (`SKILL.md` with YAML frontmatter), and DeviaTDD's existing YAML handover manifest contract.

[Exclusions]: Design decisions, model-routing trade-offs, prompt-engineering recommendations, sandbox customisation strategy, and risk register are all deferred to the `deviate-research` skill. This artifact catalogs observed facts only.

## Discovery Audit Results

### Verified Dependencies

- `typer>=0.12`: declared in `pyproject.toml:14`, used as CLI framework in `src/deviate/cli/__init__.py`.
- `rich>=13.0`: declared in `pyproject.toml:15`, used for terminal I/O in `src/deviate/cli/micro.py` and `src/deviate/cli/__init__.py`.
- `pydantic>=2.0`: declared in `pyproject.toml:16`, used for `AgentConfig`, `DeviateConfig`, `HandoverManifest` in `src/deviate/state/config.py` and `src/deviate/core/agent.py`.
- `pyyaml>=6.0.3`: declared in `pyproject.toml:17`, used in `src/deviate/core/agent.py:10` to parse the YAML handover manifest.
- `tree-sitter-*` (Python, JS/TS, Rust, Go, etc.): declared in `pyproject.toml:19-32`, used by `src/deviate/cli/inspect.py` for the `deviate inspect` command.

### Ghost Dependencies

- None observed. All invoked CLI backends (`opencode`, `claude`, `droid`) are external binaries invoked via `subprocess.Popen` (`src/deviate/core/agent.py:304`) — they are not Python packages and are not declared in `pyproject.toml`. The `pi` binary would follow the same pattern (Node.js/npm distribution, no Python wrapper package required).

### Manifest Files Observed

- `pyproject.toml`: PEP 621 project metadata; declares Python 3.13+ runtime, hatchling build backend, optional `[dev]` test group (`pytest`, `ruff`), and dependency-groups `dev`.
- `.mise.toml`: Project execution contract declaring task names (`test`, `lint`, `check-types`, `format`, `check`, etc.) and Python tooling pins (`uv`).
- `specs/constitution.md`: Authoritative governance document (Architectural Principles, Tech Stack Standards, Testing Protocols, Definition of Done).

### Test Runner Configuration

- `pyproject.toml:50-53`: `[tool.pytest.ini_options]` testpaths = `["tests"]`.
- `.mise.toml` (referenced): `mise run test` → `pytest tests/ -v`; `mise run lint` → `ruff check .`; `mise run check-types` (no mypy step declared; ruff handles basic typing).
- `tests/core/test_agent.py`, `tests/test_core/test_agent.py`: Backed-end test fixtures exist for `opencode`, `claude`, `droid` backends with `StubAgentBackend` mock.

### Manifest-Constitution Divergence

None observed. Constitution §2 "Tech Stack Standards" mandates Python 3.13 CLI via Typer + Rich — matches `pyproject.toml`. Constitution §2 "Infrastructure" cites Aider Python API as the "Micro-sandbox" substrate, but this is legacy terminology — the current implementation invokes `opencode`/`claude`/`droid` binaries via subprocess, not Aider. The Aider reference appears stale relative to the codebase.

## Constitution Quotes

- **Architectural Principles**: "Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped."
- **Tech Stack Standards**: "Python 3.13; Target: CLI application (deviate); Framework: Typer (CLI entry points) with Rich for terminal I/O; No persistent database runtime (all state tracked in JSONL ledgers and TOML config); Micro-sandbox: Aider Python API (aider.coders.Coder) as LLM execution substrate."
- **Testing Protocols**: "Test framework: pytest; Test root: tests/; Test extension: .py; Test command: pytest tests/ -v; Lint command: ruff check .; Coverage target: >= 80%; RED phase tests must fail with AssertionError or NotImplementedError — syntax crashes are rejected."
- **Definition of Done**: "Tests passing (pytest with clean exit code 0); Lint passing (ruff check with no violations); Judge phase passed (git diff validated against spec.md invariants); Documentation updated (spec.md and design.md reflect final implementation)."

## Architectural Baselines

- **Existing Architectural Patterns**:
  - **Backend dispatch** (`src/deviate/core/agent.py:60-65`): A module-level dict literal maps user-facing names to shell command prefixes.
    ```python
    BACKEND_COMMANDS: dict[str, str] = {
        "opencode": "opencode run",
        "claude": "claude -p --permission-mode auto",
        "droid": "droid exec",
        "stub": "stub",
    }
    ```
  - **Type-safe backend literal** (`src/deviate/state/config.py:12-18`): `AgentConfig.backend` is a Pydantic `Literal["opencode", "claude", "droid"]` — extending to Pi requires widening the literal and the `BACKEND_COMMANDS` registry together.
  - **YAML handover manifest extraction** (`src/deviate/core/agent.py:142-179`): `AgentBackend.parse_output` locates a YAML block (or `<handover_manifest>` tag) in the agent's stdout, parses it, and validates against the `HandoverManifest` Pydantic schema. This is the single contract every backend must satisfy.
  - **Streaming invocation** (`src/deviate/core/agent.py:215-272`): `_invoke_streaming` reads stdout/stderr line-by-line via threads, with per-line output callbacks.
  - **Subprocess isolation** (`src/deviate/core/agent.py:181-213`): `_invoke_blocking` calls `proc.communicate()` with the prompt piped via stdin and a configurable timeout.
- **Infrastructure & Operations**:
  - **Subprocess-only backend contract** (`src/deviate/core/agent.py:303-308`): All backends are external CLI binaries reachable via `subprocess.Popen`. The `pi` CLI fits this contract natively.
  - **Timeout + 30s retry** (`src/deviate/core/agent.py:319-334`): On `AgentTimeoutError`, the system sleeps 30s and re-spawns the same command. This applies uniformly across all backends.
  - **Logging surface** (`src/deviate/cli/micro.py:309-316`): Each agent invocation is logged with `INVOKE_AGENT` / `AGENT_RESULT` / `AGENT_RAW_OUTPUT` events to `.deviate/prompts.log`.
- **Data & State Management**:
  - **Append-only JSONL ledgers** (`specs/issues.jsonl`, `specs/**/tasks.jsonl`): All session state is sequential-line-parseable; no in-place mutations.
  - **TOML config** (`.deviate/config.toml`): `[agent].backend` and `[models]` (per-phase `default`, `judge`, `plan`, `red`, …) drive the routing.
  - **No persistent agent-runtime state**: The current backends are stateless invocations — each micro/meso/macro call spawns a fresh subprocess.
- **Quality, Safety & Observability**:
  - **Tamper Guard sandbox** (referenced in `specs/constitution.md` §1): Micro-layer LLM is sandboxed to writes against `src/**/*.py` only; `tests/`, `specs/`, and config files are read-only during Micro execution.
  - **No built-in permission system in Pi**: Per upstream docs, Pi runs with the invoking user's full permissions. Sandboxing is delegated to the host process or container — DeviaTDD's Tamper Guard would still apply at the wrapper layer.
  - **JUDGE phase** runs in an isolated V4 Pro session (per project AGENTS.md) and validates `git diff` against `spec.md` invariants. Backend-agnostic.
- **External Integrations**:
  - **`opencode`**: `opencode run <prompt>` — prompt piped via stdin, YAML manifest returned on stdout.
  - **`claude`**: `claude -p --permission-mode auto` — print mode, prompt via stdin; ignores `--model` flag.
  - **`droid`**: `droid exec` — supports `--model <id>` flag.
  - **`pi`** (proposed): CLI binary `pi` (npm: `@earendil-works/pi-coding-agent`); supports `pi -p "<prompt>"` (print mode), `pi --mode rpc` (JSONL over stdin/stdout), and skill discovery from `.pi/skills/`, `~/.pi/agent/skills/`, `.agents/skills/`.

## Ecosystem Research

- **Best Practices — Agent Skills Standard**: Pi implements the [Agent Skills specification](https://agentskills.io/specification). Skills are directories with `SKILL.md` (YAML frontmatter `name` + `description`, then Markdown body), with optional `scripts/`, `references/`, `assets/` subdirectories. Frontmatter validation is lenient (warnings, not errors); missing `description` is the only fatal case. Source: `https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md`.
- **Best Practices — Subprocess Integration via RPC Mode**: Pi's `--mode rpc` exposes a strict JSONL-over-stdin/stdout protocol with `prompt`, `steer`, `follow_up`, `abort`, `get_state`, `set_model`, `set_thinking_level`, `compact`, `get_session_stats` commands and streaming events (`agent_start`, `message_update`, `tool_execution_*`, `agent_end`). Source: `https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md`. The example client is a Python subprocess spawn (`pi --mode rpc --no-session` with stdin/stdout pipes), which is exactly the pattern `AgentBackend._invoke_blocking`/`_invoke_streaming` already uses.
- **Best Practices — Print Mode Simplicity**: For single-shot, stateless invocations matching DeviaTDD's current model, `pi -p "<prompt>"` exits after the first assistant turn and streams the response to stdout. Source: `https://www.npmjs.com/package/@earendil-works/pi-coding-agent`. This is the lowest-friction integration: it would map to `BACKEND_COMMANDS["pi"] = "pi -p"` (no `--model` flag — model is selected via `--provider <name> --model <pattern>` or `provider/id:<thinking>` shorthand).
- **Common Use Cases & Pitfalls**:
  - **Pitfall — Pi has no built-in permission/popup system**: Per `https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/containerization.md`, Pi does not include a built-in permission system; the host must containerize or sandbox. DeviaTDD's micro-sandbox restriction to `src/**/*.py` would still need to be enforced at the DeviaTDD wrapper level (or via Pi's `bash`/file tools restricted through extension overrides).
  - **Pitfall — Pi philosophy is "no sub-agents, no plan mode, no MCP"**: Per `https://www.npmjs.com/package/@earendil-works/pi-coding-agent`, sub-agent delegation and plan mode are user-built via extensions. DeviaTDD's micro-layer model (one specialised agent per phase) is compatible because Pi itself is a single agent — DeviaTDD orchestrates multiple Pi invocations externally.
  - **Pitfall — Skill name ≠ directory name**: Pi allows skill names to differ from their parent directory, but the [Agent Skills standard](https://agentskills.io/specification) requires them to match. DeviaTDD's existing skills (`src/deviate/prompts/skills/deviate-red/SKILL.md`, etc.) currently use the directory name as the skill name and lack YAML frontmatter — they would need a `name:` + `description:` frontmatter block to be Pi-compatible (or Pi would need to be told to skip frontmatter validation).
- **Standard Tooling**:
  - **Package**: `@earendil-works/pi-coding-agent` (the `@mariozechner/pi-coding-agent` package has been deprecated; the author has asked consumers to switch). Source: `https://www.npmjs.com/package/@mariozechner/pi-coding-agent` (deprecation banner) → `https://github.com/earendil-works/pi` (new home).
  - **CLI binary**: `pi` (installed globally via `npm install -g @earendil-works/pi-coding-agent`).
  - **Latest version**: v0.80.2 (released 23 Jun 2026, per `https://github.com/earendil-works/pi/releases/tag/v0.80.2`). License: MIT.
  - **Token-cost levers**: Pi exposes automatic compaction on context overflow/threshold and a `/compact <custom instructions>` command, plus a `--thinking <off|minimal|low|medium|high|xhigh>` flag for reasoning budgets. Per `https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md`, `get_session_stats` returns `tokens.input`, `tokens.output`, `tokens.cacheRead`, `tokens.cacheWrite` — exposing token-cache-hit ratios that DeviaTDD's existing `prompts.log` does not currently capture.

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/core/agent.py` | Codebase_File | Backend registry, Popen invocation, YAML manifest parser, timeout/retry loop | `BACKEND_COMMANDS: dict[str, str] = {`<br>`    "opencode": "opencode run",`<br>`    "claude": "claude -p --permission-mode auto",`<br>`    "droid": "droid exec",`<br>`    "stub": "stub",`<br>`}` |
| `src/deviate/state/config.py` | Codebase_File | Pydantic config models — `AgentConfig.backend` Literal and per-phase `models` resolver | `class AgentConfig(BaseModel):`<br>`    # Agent backend: "opencode", "claude", or "droid"`<br>`    backend: Literal["opencode", "claude", "droid"] = "opencode"`<br>`    # Agent invocation timeout in seconds (must be > 0)`<br>`    timeout: int = Field(default=600, gt=0)` |
| `src/deviate/cli/__init__.py` | Codebase_File | User-facing agent selection (`AGENT_CHOICES`, `AGENT_TO_BACKEND`) and init flow | `AGENT_CHOICES: tuple[str, ...] = ("factory", "droid", "claude", "opencode")`<br>`AGENT_TO_BACKEND: dict[str, str] = {`<br>`    "factory": "droid",`<br>`    "droid": "droid",`<br>`    "claude": "claude",`<br>`    "opencode": "opencode",`<br>`}` |
| `src/deviate/cli/micro.py` | Codebase_File | Micro-layer `_invoke_agent` — streams agent stdout, parses YAML handover manifest | `def _invoke_agent(`<br>`    prompt: str,`<br>`    c: Console,`<br>`    backend_name: str = "opencode",`<br>`    task_id: str = "",`<br>`    phase: str = "",`<br>`    output_callback: Callable[[str], None] | None = None,`<br>`    model: str | None = None,`<br>`) -> tuple[HandoverManifest | None, str]:` |
| `src/deviate/cli/meso.py` | Codebase_File | Meso-layer `_invoke_agent_phase` — single backend call per `plan` / `tasks` phase | `def _invoke_agent_phase(`<br>`    phase: str,`<br>`    contract: dict[str, str],`<br>`    cwd: str | None = None,`<br>`) -> None:`<br>`    """Build a slim prompt, invoke the agent, and abort on failure."""` |
| `src/deviate/cli/macro.py` | Codebase_File | Macro-layer `_cycle_phase` / `_macro_run` — iterates explore→research→prd→shard, calls `_invoke_agent_phase` for each | `def _cycle_phase(`<br>`    phase: str, resolved: str, specs_root: Path, force: bool = False`<br>`) -> None:`<br>`    """Execute a single macro phase: upstream check, pre, agent, post."""`<br>`    if phase == "research" and not (specs_root / resolved / "explore.md").exists():` |
| `src/deviate/prompts/skills/deviate-red/SKILL.md` | Codebase_File | Representative micro-layer skill (RED phase) — Plain Markdown body, no YAML frontmatter currently | `# deviate-red Skill` *(content not loaded — relative path only)* |
| `src/deviate/prompts/governance/claudemd_seed.md` | Codebase_File | Governance seed for Claude agent export — referenced by `_read_seed` in `src/deviate/cli/__init__.py` | *(block located at `src/deviate/prompts/governance/claudemd_seed.md:1-30`)* |
| `specs/constitution.md` | Manifest | Authoritative governance document — Architectural Principles, Tech Stack, Testing Protocols, DoD | `# Project Constitution`<br>`Version: 0.2.0`<br>`---`<br>`## 1. Architectural Principles`<br>`- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).` |
| `pyproject.toml` | Manifest | PEP 621 metadata; declares Python 3.13, typer, rich, pydantic, pyyaml, tree-sitter deps | `[project]`<br>`name = "deviate"`<br>`version = "0.2.4"`<br>`description = "DeviaTDD CLI — agent orchestration framework"`<br>`requires-python = ">=3.13"`<br>`dependencies = [`<br>`    "typer>=0.12",`<br>`    "rich>=13.0",`<br>`    "pydantic>=2.0",`<br>`    "pyyaml>=6.0.3",` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Low–Medium |
| Files Likely Modified | `src/deviate/core/agent.py` (extend `BACKEND_COMMANDS` + `AgentConfig` Literal), `src/deviate/cli/__init__.py` (extend `AGENT_CHOICES` + `AGENT_TO_BACKEND` + `--agent <name>` validation), `tests/core/test_agent.py` and/or `tests/test_core/test_agent.py` (new backend test fixtures), `src/deviate/prompts/skills/*/SKILL.md` (add YAML frontmatter if Pi-native skill discovery is desired), `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` (document the new backend option). |
| New Modules Required | No (extend existing `AgentBackend` class — Pi supports the same `subprocess.Popen` + stdin-prompt + stdout-YAML contract used by all current backends; no new transport module is required unless RPC mode is adopted). |
| New Persistence / Data Models | No (no new Pydantic models required; the `HandoverManifest` schema is backend-agnostic). |
| New External Integrations | Yes — one new external binary (`pi`, npm package `@earendil-works/pi-coding-agent` v0.80.2). Distribution: npm install — no Python wrapper package needed. |
| Upstream / Cross-Cutting Concerns | Tamper Guard sandboxing (Pi has no built-in permission system — DeviaTDD's `src/**/*.py`-only write restriction must still be enforced at the wrapper level, or via Pi's `--tools` allowlist and a custom extension); skill-format compatibility (Pi requires YAML frontmatter on `SKILL.md`; DeviaTDD's skills currently use plain Markdown — a shim or a frontmatter-injection step may be required for Pi-native skill discovery). |
| Rationale | The Pi CLI binary's print mode (`pi -p`) maps 1:1 onto the existing `AgentBackend.invoke()` subprocess contract (stdin prompt → stdout response → YAML extraction). The integration surface is the `BACKEND_COMMANDS` dict, the `AgentConfig.backend` Literal, and the `AGENT_CHOICES` / `AGENT_TO_BACKEND` user-facing tuples. Token-savings levers exist (Pi's automatic compaction + cache-read accounting via `get_session_stats`) but capturing them requires either RPC mode adoption or a new `--print-tokens` flag in Pi. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | pi-agent-backend |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/pi-agent-backend.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low–Medium complexity) — see `## Scope Sizing` |