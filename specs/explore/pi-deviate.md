## Problem Definition
**Statement**: Define what exists today for a Pi extension (`pi-deviate`) to own `micro`/`meso` runs and worktree management.
**Scope**: CLI entry points for `meso run`, `micro run`, worktree helpers, session state, agent backend dispatch, skill orchestrator text.
**Exclusions**: No design for the extension. No session-model decision. No code changes.

## Discovery Audit Results
### Verified Dependencies
- `typer` + `rich` declare the CLI. `pyproject.toml` declares `requires-python = ">=3.13"`, package version `2.27.3`.
- `pydantic>=2.0` validates `AgentConfig` and `SessionState`.
- `aider` Python API is the micro execution substrate per constitution.
- `pytest`, `ruff`, `bats`, `mise` form the check gate.

### Ghost Dependencies
- None observed. `pi`/`omp` binaries are runtime backends, not Python imports.

### Manifest Files Observed
- `pyproject.toml` (package, deps, ruff/pytest config).
- `mise.toml` (task runner).
- `.deviate/config.toml` (`[agent].backend`, `[models]` routing).
- `specs/issues.jsonl`, `specs/**/tasks.jsonl` (append-only ledgers).
- `.deviate/session.json` (session state).

### Test Runner Configuration
- `pytest tests/ -v` is the unit gate. `ruff check .` is lint. `bats tests/e2e/` is E2E.

### Manifest-Constitution Divergence
- None observed. Manifests declare Python 3.13, Typer, Rich, pytest, ruff, bats, mise. Constitution states the same stack.

## Constitution Quotes
- **Architectural Principles**: "**Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)."
- **Tech Stack Standards**: "- Python 3.13" / "- Target: CLI application (`deviate`)" / "- Framework: Typer (CLI entry points) with Rich for terminal I/O"
- **Testing Protocols**: "- Test framework: pytest" / "- Test root: `tests/`" / "- Test command: `pytest tests/ -v`" / "- Lint command: `ruff check .`" / "- E2E command: `bats tests/e2e/`"
- **Definition of Done**: "- [ ] Tests passing (pytest with clean exit code 0)" / "- [ ] Lint passing (ruff check with no violations)" / "- [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)"

## Architectural Baselines
- **Existing Architectural Patterns**
  - Typer app per layer: `src/deviate/cli/meso.py` hosts `meso run` and `specify`. `src/deviate/cli/micro.py` hosts `micro run`.
  - Agent dispatch via `src/deviate/core/agent.py` `AgentBackend.invoke` with `BackendName` literal covering `pi` and `omp`.
  - Pre/post script lifecycle per phase (`deviate <phase> pre/post`).
- **Infrastructure & Operations**
  - Git worktrees under `.worktrees/feat-*` hold per-issue isolation. Branches follow `feat/<epic-slug>/<issue-slug>`.
  - No containerization. Local host execution.
- **Data & State Management**
  - Append-only JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`). Canonical state comes from sequential parse.
  - Session pointer at `.deviate/session.json` (`SessionState`: `current_phase`, `active_issue_id`).
- **Quality, Safety & Observability**
  - JUDGE validates GREEN diff scope. REFACTOR re-runs the regression gate.
  - `mise run check` is the merge gate (pytest + ruff + types).
- **External Integrations**
  - `pi -p` / `omp -p` print-mode subprocess backends. Opt-in `pi_rpc` flag spawns `pi --mode rpc --no-session`.
  - Pi extensions exist as prior art: `ask-user.ts`, `local-env.ts`, `message-history.ts` under the Pi extension dir.

## Sibling Flow Inventory
The nearest sibling is the `meso run` → worktree → `micro run` chain described by the `deviatdd` skill.

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed (no money flow) | n/a |
| Lock vs reserve | claim-then-worktree (ledger claim + branch lock) | src/deviate/cli/meso.py |
| Vendor call | agent subprocess spawn per phase (`AgentBackend.invoke`) | src/deviate/core/agent.py |
| Idempotency | `find_worktree_for_branch` returns existing worktree; Meso skips Specify inside linked worktree | src/deviate/core/worktree.py |
| Destination shape | typed `SessionState` + worktree path string handed to next command | src/deviate/state/config.py |

Key verbatim facts:
- "From `main` or `master`, Meso claims the next issue and creates its linked worktree." (`src/deviate/prompts/skills/deviatdd/SKILL.md`)
- "Use the returned worktree path for all Micro commands." (`src/deviate/prompts/skills/deviatdd/SKILL.md`)
- "Inside a linked `feat/...` worktree, Meso skips Specify and resumes there." (`src/deviate/prompts/skills/deviatdd/SKILL.md`)
- "After Meso succeeds or emits `MESO_ALREADY_COMPLETE`, run `deviate micro run` in the returned worktree." (`src/deviate/prompts/skills/deviatdd/SKILL.md`)

## Ecosystem Research
Catalog only. Later phases must not treat these rows as Required unless a local flow, constitution clause, or money/auth/provider integrity test applies.
- **Best Practices**
  - Pi extensions register tools and UI via TypeScript extension modules (prior art: `ask-user.ts`, `cmux-session.ts` in the Pi extension dir).
  - `git worktree list` is the source of truth for worktree inventory; parse its stdout per repo root.
- **Common Use Cases & Pitfalls**
  - One Pi session per cwd: a root Pi instance cannot directly `cd` into a worktree and keep tool-path scoping correct without re-anchoring.
  - Session-per-worktree avoids cross-branch file writes; root-as-orchestrator needs explicit cwd routing per tool call.
- **Standard Tooling**
  - `git worktree list --porcelain` for machine-readable inventory.
  - Pi RPC mode (`pi --mode rpc`) for programmatic session control when print mode is not enough.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/meso.py` | CLI entry | `meso run` pipeline and `specify` claim | `def meso_run_command(` / `"""Run the meso automated pipeline (setup → plan → tasks).` / `Default: worktree + claim, then spawn the agent for PLAN/TASKS.` |
| `src/deviate/cli/micro.py` | CLI entry | `micro run` task loop | `def _worktree_status_paths(root: Path) -> list[str]:` |
| `src/deviate/core/worktree.py` | Core helper | worktree create/lookup | `def create_worktree(` / `branch: str,` / `path: Path,` / `repo: Path | None = None,` / `) -> Path:` |
| `src/deviate/core/worktree.py` | Core helper | idempotent worktree lookup | `def find_worktree_for_branch(branch: str, repo: Path \| None = None) -> Path \| None:` |
| `src/deviate/core/agent.py` | Core dispatch | backend invoke incl. `pi` | `BackendName = Literal["opencode", "claude", "droid", "pi", "omp", "codex", "stub"]` |
| `src/deviate/state/config.py` | State model | `AgentConfig`, `SessionState` | `class AgentConfig(BaseModel):` / `backend: Literal["opencode", "claude", "droid", "pi", "omp"] = "opencode"` |
| `src/deviate/prompts/skills/deviatdd/SKILL.md` | Skill text | current skill-owned orchestration the extension would absorb | `After Meso succeeds or emits MESO_ALREADY_COMPLETE, run deviate micro run in the returned worktree.` |
| `pyproject.toml` | Manifest | deps, Python floor | `requires-python = ">=3.13"` / `version = "2.27.3"` |
| `.deviate/config.toml` | Config | backend + model routing | `[agent].backend = "omp"` |
| `specs/constitution.md` | Governance | hard constraints | `**Git Isolation Principle**: Every task loop executes on a clean git branch or worktree.` |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 4-5: `src/deviate/core/worktree.py`, `src/deviate/cli/meso.py`, `src/deviate/cli/micro.py`, `src/deviate/core/agent.py`, plus new extension dir |
| New Modules Required | Yes |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Pi extension host API (session/cwd scoping); worktree inventory source of truth |
| Rationale | The CLI already owns runs and worktrees. The extension wraps them. Open point is session topology only. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | pi-deviate |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/pi-deviate.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) or `/deviate-research` (High complexity) — see `## Scope Sizing` |
