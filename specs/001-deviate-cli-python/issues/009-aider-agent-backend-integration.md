---
title: "[FR-009] Aider Agent Backend Integration"
labels: ["epic:001-deviate-cli-python", "layer:micro", "layer:agent"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-004"]
coordinates_with: []
issue_id: "ISS-009"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/009-aider-agent-backend-integration.md`
- **Workstation Paths**:
  - `src/deviate/core/agent.py` — Extend `AgentBackend` with Aider provider
  - `src/deviate/state/config.py` — Extend `AgentConfig.backend` with `"aider"` literal
  - `tests/test_core/test_agent.py` — Aider-specific invocation tests
  - `tests/test_integration/test_aider_backend.py`

## [THE_PROBLEM_CONTRACT]
As a developer using `aider` as my AI coding agent, I need the `deviate` CLI to support invoking aider as a subprocess in automated micro/meso/macro pipelines — with aider-specific prompt formatting, flag handling, and output parsing — so that the full DeviaTDD workflow can run with aider as the code-generation backend.

## [ARCHITECTURAL_OVERVIEW]

### Why Separate from ISS-004

Aider has fundamentally different invocation semantics than opencode/claude/droid:
- **No heredoc pipe**: Aider does not accept prompts via stdin. Invocation is `aider --message "..."` or `aider --load prompt.md`.
- **Interactive by default**: Aider's default mode is interactive chat. Automated mode requires `--yes` (auto-confirm) and `--no-suggest-shell-commands`.
- **File context via args**: Aider accepts `--file`, `--read`, `--auto-commits` flags for context and auto-commit behavior.
- **Different output format**: Aider's output is chat-style, not YAML manifest blocks. Output parsing must differ from opencode/claude/droid.

### Invocation Pattern

```
aider \
  --message "$PROMPT" \
  --yes \
  --no-suggest-shell-commands \
  --no-auto-commits \
  --model <model> \
  --read specs/constitution.md \
  --read CLAUDE.md \
  --file src/**/*.py
```

Flags used:
- `--message` — The slim prompt (non-interactive, single message mode)
- `--yes` — Auto-confirm all aider actions (no interactive prompts)
- `--no-suggest-shell-commands` — Prevent aider from suggesting shell commands
- `--no-auto-commits` — Delegate all git operations to deviate CLI, not aider
- `--model` — Model selection from `.deviate/config.toml`
- `--read` — Inject constitution.md and CLAUDE.md as read-only context files
- `--file` — Explicitly scope aider's edit context to allowed paths (reduces Tamper Guard violations)

### Configuration

```toml
# .deviate/config.toml
[agent]
backend = "aider"
timeout = 900

[agent.aider]
model = "claude-sonnet-4-20250514"     # or deepseek, etc.
auto_commits = false                     # deviate handles all git
suggest_shell_commands = false
yes_mode = true                          # non-interactive
read_files = ["specs/constitution.md", "CLAUDE.md"]
```

Extend `DeviateConfig`:

```python
class AiderConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    auto_commits: bool = False
    suggest_shell_commands: bool = False
    yes_mode: bool = True
    read_files: list[str] = Field(default_factory=lambda: ["specs/constitution.md", "CLAUDE.md"])

class AgentConfig(BaseModel):
    backend: Literal["opencode", "claude", "droid", "aider"] = "opencode"
    timeout: int = Field(default=600, gt=0)
    aider: AiderConfig = Field(default_factory=AiderConfig)

class DeviateConfig(BaseModel):
    # ... existing fields ...
    agent: AgentConfig = Field(default_factory=AgentConfig)
```

## [SCOPE_BOUNDARIES]

### Hard Inclusions

- **Aider as `AgentBackend` provider** in `src/deviate/core/agent.py`:
  - Implement `AiderBackend` subclass of `AgentBackend`
  - Build invocation command from `AiderConfig` + slim prompt
  - Invoke via `subprocess.run()` with configured timeout
  - Capture stdout, check exit code
  - Parse aider output for success/failure indicators (test pass/fail counts, file modifications)
- **Aider-specific output parsing**:
  - Unlike opencode/claude/droid which emit YAML handover manifests, aider output is chat-style
  - Parse for: "All tests passed", "N tests failed", modified file paths from aider log
  - Extract: list of files touched, test results, error messages
  - Map to internal `AgentResult` struct for phase sequencing
- **Configuration model extensions** in `src/deviate/state/config.py`:
  - `AiderConfig` Pydantic model
  - `agent.aider` field in `DeviateConfig`
  - `"aider"` added to `AgentConfig.backend` Literal type
- **Tamper Guard awareness**:
  - With `--no-auto-commits`, aider won't commit — deviate CLI remains the sole committer
  - With `--file src/**/*.py`, aider's edit scope is bounded to allowed paths
  - Post-invocation Tamper Guard still evaluates full `git diff` for safety
- **Constitution/CLAUDE.md injection**:
  - Delivered via `--read` flag (aider reads these as read-only context)
  - More efficient than injecting full content into prompt (avoids token bloat in `--message`)

### Defensive Exclusions

- Interactive aider mode (chat, follow-up questions) — automated pipeline only supports single-shot `--message` mode.
- Aider configuration management beyond `.deviate/config.toml` — no `.aider.conf.yml` generation or management.
- Model API key management — delegated to aider's own environment/configuration.
- Aider version pinning — delegated to `mise.toml` or user environment.

## [UPSTREAM_REQUIREMENT_TRACING]

- **FR-009-AIDER-BACKEND**: `AiderBackend` provider implementing the `AgentBackend` interface with aider-specific subprocess invocation via `--message` + `--yes` + `--no-auto-commits`.
- **FR-009-AIDER-CONFIG**: `AiderConfig` Pydantic model and `DeviateConfig.agent.aider` configuration section.
- **FR-009-AIDER-PARSE**: Aider output parsing — extract file modifications, test results, and error messages from aider's chat-style output.
- **FR-009-AIDER-CONTEXT**: Constitution and CLAUDE.md delivered via `--read` flag for efficient read-only context injection.

## [MULTI_TIERED_VERIFICATION_TARGETS]

- **Unit Tests**: `tests/test_core/test_agent.py` — Aider-specific invocation, config validation, output parsing
- **Integration Tests**: `tests/test_integration/test_aider_backend.py` — Full aider invocation in automated pipeline, Tamper Guard interaction

## [DEMONSTRATION_PATH]

```bash
# Verify aider backend
pytest tests/test_core/test_agent.py -v -k aider

# Verify aider integration in pipeline
pytest tests/test_integration/test_aider_backend.py -v

# Verify aider config validation
python -c "from deviate.state.config import DeviateConfig; c = DeviateConfig.model_validate({'agent': {'backend': 'aider'}}); print(c.agent.aider.model)"

mise run check
```
