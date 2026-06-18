# Exploration Report: Graphite CLI Integration

## Problem Definition
[Statement]: Add an optional `--graphite` boolean flag to `deviate init` that persists a `graphite` key in `.deviate/config.toml`. When `graphite = true`, the DeviaTDD system must use Graphite's `gt` CLI for branch management (replacing `git checkout -b` with `gt create`) and PR submission (replacing `gh pr create` with `gt submit --stack`). When false (default), all existing behavior is preserved unchanged.
[Scope]: Config schema extension (1 new field on `DeviateConfig`), CLI flag addition (1 new `--graphite` option on `init`), CLAUDE.md conditional section (Graphite-specific workflow instructions), `deviate pr` path selection (`gh` vs `gt`), task-level branch creation commands (`git checkout -b` → `gt create`), skill template updates.
[Exclusions]: Migration/upgrade path for existing `.deviate/config.toml` files, Graphite installation verification logic, CI/CD pipeline changes, Graphite MCP integration (beta feature), legacy `gt` alias configuration.

## Discovery Audit Results
### Verified Dependencies
- `typer` (CLI framework): `src/deviate/cli/__init__.py:8`, `pyproject.toml`
- `pydantic` (data validation): `src/deviate/state/config.py:9`, `pyproject.toml`
- `rich` (terminal I/O): `src/deviate/cli/__init__.py:9`, `pyproject.toml`
- `tomllib` (stdlib, config parsing): `src/deviate/state/config.py:4`, `pyproject.toml`
- `PyYAML` (handover manifest parsing): `src/deviate/cli/micro.py`, `pyproject.toml`
- `httpx` (HTTP client, constitution generation): `pyproject.toml`

### Ghost Dependencies
- `gh` (GitHub CLI): Referenced in `src/deviate/cli/meso.py:1008` via `subprocess.run(["gh", "pr", "create", ...])`. No manifest declaration — this is an external system dependency used at runtime.
- `gt` (Graphite CLI): Not yet referenced anywhere. Will be an optional runtime dependency when `graphite = true`.

### Manifest Files Observed
- `pyproject.toml`: Project metadata, dependencies, build configuration
- `.mise.toml`: Task runner definitions (test, lint, format, check, etc.)
- `.deviate/config.toml`: Current deviate config (profile, llm_backend, timeout, agent_export_mode)
- `.graphite_aliases` (potential): User-level aliasing for `gt` commands, not yet tracked

### Test Runner Configuration
- `TEST_COMMAND`: `pytest tests/ -v` (from constitution §3.1 and `pyproject.toml`)
- `LINT_COMMAND`: `ruff check .`
- `E2E_COMMAND`: `bats tests/e2e/`

### Manifest-Constitution Divergence
- None observed. Manifest and constitution agree on Python 3.13, Typer, Rich, pytest, ruff, uv.

## Constitution Quotes
- **Architectural Principles**: "Three-Layer Architecture: Macro (feature scoping: Explore → Research → PRD → Shard+Specify), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Each layer has strict phase gates — no layer may be skipped."
- **Tech Stack Standards**: "Python 3.13. Target: CLI application (deviate). Framework: Typer (CLI entry points) with Rich for terminal I/O."
- **Testing Protocols**: "TEST_FRAMEWORK: pytest. TEST_ROOT: tests. TEST_EXT: .py. Coverage target: >= 80%."
- **Definition of Done**: "Tests passing (pytest with clean exit code 0). Lint passing (ruff check with no violations). Judge phase passed (git diff validated against spec.md invariants)."

## Architectural Baselines
- **Existing Architectural Patterns**: Three-layer DeviaTDD architecture: Macro (`src/deviate/cli/macro.py` — explore/research/prd/shard pre/post), Meso (`src/deviate/cli/meso.py` — specify/plan/tasks/pr pre/post/run + agent invocation via `_invoke_agent_phase`), Micro (`src/deviate/cli/micro.py` — red/green/refactor/judge/yellow/execute/e2e/hotfix pre/post). All layers use `resolve_model_for_phase()` from `src/deviate/state/config.py:121` for model resolution.
- **Infrastructure & Operations**: Git-based version control with worktree isolation. CI via GitHub Actions (wired in constitution). `.mise.toml` drives all task execution via `uv run`. Session state persists as JSON in `.deviate/session.json`.
- **Data & State Management**: State modeled via Pydantic `BaseModel` subclasses (`DeviateConfig`, `SessionState`). Config serialized to TOML (`src/deviate/cli/__init__.py:65 _dict_to_toml`). Session serialized to JSON. Ledgers are append-only JSONL (`specs/issues.jsonl`, `specs/**/tasks.jsonl`).
- **Quality, Safety & Observability**: pytest for unit tests, ruff for lint/format, bats for E2E. TamperGuard in micro layer prevents unauthorized test edits. HITL gates at 3 points. Session continuity preserved across micro phases.
- **External Integrations**: `gh` CLI for PR creation (`src/deviate/cli/meso.py:1008`). `gt` CLI not yet integrated — this is the subject of the feature.

## Ecosystem Research
[Web_Discovery]: Graphite CLI documentation (via `context query graphite.com@latest`)
- **Best Practices**: Graphite recommends a stacked-changes workflow where each branch is an atomic changeset with a single commit. Use `gt create -am "message"` to create a branch from working changes, `gt submit` to push and create/update PRs, `gt submit --stack` for multi-branch stacks, `gt sync` for trunk updates and branch cleanup.
- **Common Use Cases & Pitfalls**: Use `gt create` instead of `git checkout -b` + `git commit`. Use `gt modify -a` to amend and restack. Avoid simultaneous worktrees on the same stack. Run `gt log` to verify branch state. Use `gt submit --stack` to submit all branches in one go. `gt submit --update-only` to only update existing PRs. `gt submit --merge-when-ready` for auto-merge.
- **Standard Tooling**: Core commands: `gt create` (branch+commit), `gt submit` (PR), `gt submit --stack` (stack PRs), `gt sync` (trunk sync + restack), `gt log` / `gt ls` (visualize), `gt modify -a` (amend+restack), `gt restack` (rebase stack), `gt merge` (merge downstack), `gt fold` (fold child into parent). GT MCP (beta) available for AI agent integration. Key flags: `--publish` (publish draft PR), `--reviewers` (set reviewer), `--merge-when-ready` (auto-merge), `--update-only` (existing PRs only).

## File Registry
| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `pyproject.toml` | Manifest | Project metadata and dependencies | `[project]\nname = "deviate"\ndependencies = [\n  "typer>=0.12.0",\n  "rich>=13.8.0",\n  "pydantic>=2.0.0",\n  "PyYAML>=6.0",\n  "httpx>=0.27.0",\n]` |
| `.mise.toml` | Config | Task runner definitions | `[tasks.check]\ndescription = "All validation checks"\ndepends = ["lint", "check-types", "test"]` |
| `.deviate/config.toml` | Config | Current deviate configuration | `profile = "default"\nllm_backend = "opencode"\ntimeout_seconds = 300\nagent_export_mode = "local"` |
| `src/deviate/state/config.py` | Codebase_File | Config/session Pydantic models | `class DeviateConfig(BaseModel):\n    profile: str = "default"\n    llm_backend: str = "droid"\n    timeout_seconds: int = Field(default=300, gt=0)\n    agent_export_mode: Literal["local", "global"] = "local"\n    agent: AgentConfig = Field(default_factory=AgentConfig)\n    models: dict[str, str] = Field(default_factory=dict)\n    model_config = {"extra": "forbid"}` |
| `src/deviate/cli/__init__.py` | Codebase_File | CLI entry points, init command, scaffolding | `@cli.command()\ndef init(\n    agent_export_mode: str = typer.Option(\n        "local", "--agent-export-mode", help="Export mode for agent commands"\n    ),\n    generate_constitution: bool = typer.Option(\n        False, "--generate-constitution", help="Generate constitution boilerplate"\n    ),\n    agent: str | None = typer.Option(\n        None, "--agent", help="Override auto-detected agent platform"\n    ),\n) -> None:` |
| `src/deviate/cli/__init__.py` | Codebase_File | Dotfile scaffolding function | `def _scaffold_dotfiles(workdir: Path, agent_export_mode: str) -> None:\n    dot_dir = workdir / ".deviate"\n    _ensure_dir(dot_dir)\n    _ensure_dir(dot_dir / "artifacts")\n    config = DeviateConfig(agent_export_mode=agent_export_mode)\n    config_path = dot_dir / "config.toml"\n    _write_if_missing(config_path, _dict_to_toml(config.model_dump()))` |
| `src/deviate/cli/__init__.py` | Codebase_File | TOML serialization for config | `def _dict_to_toml(data: dict) -> str:\n    lines: list[str] = []\n    for key, value in data.items():\n        if value is None:\n            continue\n        if isinstance(value, dict):\n            lines.append(f"\\n[{key}]")\n            for k, v in value.items():\n                line = _serialize_value(k, v)\n                if line:\n                    lines.append(line)` |
| `src/deviate/cli/__init__.py` | Codebase_File | TOML value serialization | `def _serialize_value(key: str, value: object) -> str:\n    if value is None:\n        return ""\n    if isinstance(value, bool):\n        return f"{key} = {'true' if value else 'false'}"` |
| `src/deviate/prompts/governance/claudemd_seed.md` | Codebase_File | CLAUDE.md governance seed template | `## DeviaTDD Orchestration Rules\n\n### Three-Layer Architecture\n- **Macro Layer** — Feature scoping: /explore → /research → /prd → /shard.` |
| `src/deviate/prompts/governance/agents_seed.md` | Codebase_File | AGENTS.md governance seed template | `## DeviaTDD Orchestration Rules\n\n### Three-Layer Architecture\n- **Macro Layer** — Feature scoping: /explore → /research → /prd → /shard.` |
| `src/deviate/cli/meso.py` | Codebase_File | PR run command (gh pr create) | `title = _pr_title(issue_id, record.title, record.type)\n    cmd = ["gh", "pr", "create", "--title", title, "--body-file", str(body_file)]\n    if merge:\n        cmd.append("--merge")\n    elif auto_merge:\n        cmd.append("--auto-merge")\n    result = subprocess.run(cmd, capture_output=True, text=True, env=_git_env())\n    if result.returncode != 0:\n        console.print(f"[red]PR_CREATE_FAILED[/] {result.stderr.strip()}")` |
| `src/deviate/cli/meso.py` | Codebase_File | `_invoke_agent_phase` for meso layer | `def _invoke_agent_phase(\n    phase: str,\n    contract: dict[str, str],\n    cwd: str | None = None,\n) -> None:\n    prompt = _build_slim_prompt(phase, contract)\n    backend = AgentBackend()\n    root = Path(cwd) if cwd else Path.cwd()\n    model = resolve_model_for_phase(phase, root)\n    manifest = backend.invoke(prompt, cwd=cwd, model=model)` |
| `src/deviate/cli/micro.py` | Codebase_File | Phase runner entry points | `@red_app.command(name="pre")\n@red_app.command(name="post")\n@green_app.command(name="pre")\n@green_app.command(name="post")` ... (multiple phase pre/post commands) |
| `src/deviate/cli/macro.py` | Codebase_File | Macro phase pre/post | `@explore_app.command("pre")\n@explore_app.command("post")` ... (explore/research/prd/shard pre/post) |
| `src/deviate/core/repo.py` | Codebase_File | Git state gathering | `def gather_git_state(repo: Path | None = None) -> dict:` |
| `src/deviate/core/worktree.py` | Codebase_File | Worktree create/remove | `def create_worktree(branch: str, path: Path, repo: Path | None = None) -> Path:` |
| `src/deviate/core/agent.py` | Codebase_File | Agent backend invocation | `class AgentBackend:\n    def invoke(self, prompt: str, ..., model: str | None = None) -> HandoverManifest:` |
| `src/deviate/core/commit.py` | Codebase_File | Artifact commit helper | `def commit_artifact(...):` |
| `src/deviate/core/constitution.py` | Codebase_File | Constitution extraction | `def extract_commands(...):` |
| `src/deviate/core/issues.py` | Codebase_File | Issue claim/lifecycle | `def claim_issue(...):` |
| `src/deviate/core/_shared.py` | Codebase_File | Git env isolation | `def git_env() -> dict[str, str]:` |
| `src/deviate/state/ledger.py` | Codebase_File | Ledger operations | `IssueRecord`, `TaskRecord`, `append_issue_transition`, `append_task_record`, `resolve_issue_record`, `select_next_unblocked_issue` |
| `src/deviate/prompts/skills/red/SKILL.md` | Codebase_File | RED phase skill template | Agent instruction for RED phase (test writing) |
| `src/deviate/prompts/skills/green/SKILL.md` | Codebase_File | GREEN phase skill template | Agent instruction for GREEN phase (implementation) |
| `src/deviate/prompts/skills/pr/SKILL.md` | Codebase_File | PR skill template | Agent instruction for PR creation flow |
| `src/deviate/prompts/skills/plan/SKILL.md` | Codebase_File | Plan skill template | Agent instruction for plan phase |
| `src/deviate/prompts/skills/tasks/SKILL.md` | Codebase_File | Tasks skill template | Agent instruction for task decomposition |
| `src/deviate/prompts/constitution_seed.md` | Codebase_File | Constitution seed template | Template with `${VARIABLE}` placeholders for project-specific values |
| `tests/test_cli/test_init.py` | Test | Init command tests | `class TestInitCommand:\n    def test_init_creates_dotfile_structure(self, tmp_path: Path):\n        with chdir(tmp_path):\n            result = runner.invoke(cli, ["init"])\n            assert result.exit_code == 0` |
| `tests/test_cli/test_config.py` | Test | Config model tests | Tests for DeviateConfig schema, serialization, and validation |
| `tests/test_state/test_config.py` | Test | Config state tests | Tests for config model validation and IO cycles |
| `.opencode/skills/deviate-pr/SKILL.md` | Skill | PR skill template (agent-facing) | Skill definition for `/deviate-pr` with gh pr create workflow instructions |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Low |
| Files Likely Modified | 6-8 (DeviateConfig model, CLI init command, claudemd seed, meso PR runner, PR skill template, green/red skill templates, tests) |
| New Modules Required | No |
| New Persistence / Data Models | No (1 new boolean field on existing DeviateConfig model) |
| New External Integrations | `gt` (Graphite CLI) as optional runtime dependency (not a Python package) |
| Upstream / Cross-Cutting Concerns | Conditional branching in 3 execution surfaces: config resolution, CLAUDE.md generation, PR submission path. Scope is well bounded — `graphite` flag is read at startup, behavior diverges only at the call site. |
| Rationale | The feature adds a single boolean field to an existing Pydantic model, one CLI option on an existing command, and conditional branching in 3 well-defined locations (claudemd seed, _pr_run, task creation). No new modules, no new data models, no new persistence. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| FEATURE_SLUG | graphite-cli |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/graphite-cli.md |
| EPIC_ID | graphite-cli |
| NEXT_ACTION | Run the `deviate-research` skill |
