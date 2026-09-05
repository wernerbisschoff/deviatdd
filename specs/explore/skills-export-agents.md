## Problem Definition
**Statement**: Consolidate skill export on `.agents/skills/` for Pi and Codex. Check Droid support. Check prompts-to-skills effect on auto runner. Check skill-use monitoring when auto skill already injects the prompt.
**Scope**: Export paths in `src/deviate/cli/__init__.py`. Skill source in `src/deviate/prompts/skills/deviatdd/`. Command composition in `src/deviate/core/commands.py`. Prompt assembly in `src/deviate/prompts/assembly.py`. Pi spawn flags in `src/deviate/core/agent.py`. Micro prompt build in `src/deviate/cli/micro.py`.
**Exclusions**: No design choice. No recommendation. No code change.

## Discovery Audit Results
### Verified Dependencies
- `typer>=0.12`, `rich>=13.0`, `pydantic>=2.0`, `pyyaml>=6.0.3` run the CLI. Test stack is `pytest>=8.0` plus `ruff>=0.4`.
- Prompt sources are package resources. The loader reads them with `importlib.resources.files()`. No build step wraps them.

### Ghost Dependencies
- None observed. No import in scanned files names a package missing from `pyproject.toml`.

### Manifest Files Observed
- `pyproject.toml` declares the package, entry point, and tool config. `deviate = "deviate.main:app"` is the entry point.
- `.mise.toml` defines task runner tasks. Constitution names `mise run check` as the quality gate.
- `specs/constitution.md` states version 0.11.0. It governs stack, layers, and gates.

### Test Runner Configuration
- `pytest tests/ -v` runs unit tests. `ruff check .` lints. `bats tests/e2e/` covers CLI integration. Coverage target is >= 80 percent.

### Manifest-Constitution Divergence
- None observed. Manifest tooling (`pytest`, `ruff`, `mise`) matches constitution `§2 Tooling` and `§3 Testing Protocols` verbatim.

## Constitution Quotes
- **Architectural Principles**: "**Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Macro PRD/shard/adhoc artifacts carry User Stories plus ATDD acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract. The three layers have strict phase gates — no layer may be skipped. (Gate 2 was removed: there is no human-approval step between Tasks and Micro — the system auto-advances.)"
- **Tech Stack Standards**: "- Python 3.13" / "- Target: CLI application (`deviate`)" / "- Framework: Typer (CLI entry points) with Rich for terminal I/O"
- **Testing Protocols**: "- Test framework: pytest" / "- Test root: `tests/`" / "- Test command: `pytest tests/ -v`" / "- Lint command: `ruff check .`" / "- E2E command: `bats tests/e2e/`"
- **Definition of Done**: "- [ ] Tests passing (pytest with clean exit code 0)" / "- [ ] Lint passing (ruff check with no violations)" / "- [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)"

## Architectural Baselines
- **Existing Architectural Patterns**
  - Slash commands live under `src/deviate/prompts/commands/<name>.md`. Setup installs them per agent. Assembly composes constitution plus core plus layer plus lifecycle plus body.
  - Auto prompts compose in `src/deviate/prompts/assembly.py::load_template`. Manual slash commands compose in `src/deviate/core/commands.py::compose_command_body`.
- **Infrastructure & Operations**
  - `deviate setup` provisions commands, the `deviatdd` skill, and config in one pass. Export mode is `local` or `global`. Global mode never embeds a project constitution.
  - Backend map lives in `src/deviate/core/agent.py::AGENT_TO_BACKEND`. `factory` maps to the `droid` binary. `pi`, `omp`, and `codex` are distinct backends.
- **Data & State Management**
  - State lives in JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`) plus TOML config (`.deviate/config.toml`). No database runtime exists.
- **Quality, Safety & Observability**
  - Micro enforces GREEN scope. JUDGE checks the diff. REFACTOR re-runs tests. `mise run check` gates merge.
- **External Integrations**
  - Pi spawns through `PI_RPC_COMMAND` or backend commands. Codex spawns through the `codex` backend with reasoning effort flags. Droid spawns through the `droid` binary.

## Sibling Flow Inventory

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | none observed (no money flow in this repo) | n/a |
| Lock vs reserve | claim-branch lock pattern in setup/meso flow | src/deviate/cli/__init__.py |
| Vendor call | HTTP request path: none observed; vendor call is agent-subprocess spawn, not HTTP | src/deviate/core/agent.py |
| Idempotency | install skips rewrite when on-disk copy matches composed output | src/deviate/core/commands.py |
| Destination shape | typed per-agent destination dirs (commands vs skills) | src/deviate/cli/__init__.py |

## Ecosystem Research
- **Best Practices**
  - Codex discovers project skills at `.agents/skills/<name>/SKILL.md`. It scans from CWD up to repo root. Global skills live under `~/.agents/skills`. (Source: project code plus web catalog.)
  - Pi discovers skills in `.pi/skills/`, `.pi/agent/skills/`, and `.agents/skills/`. Directories with `SKILL.md` resolve recursively. (Source: `https://pi.dev/docs/latest/skills`.)
- **Common Use Cases & Pitfalls**
  - Codex CLI 0.117+ dropped `.codex/prompts` and `/prompts:`. Old prompt paths stop working. `.agents/skills/` is the supported path.
  - A local skill plus an injected prompt can double-load the same instruction. The runner then sees two copies of one directive. Later phases treat this as fact to verify, not as a decided risk.
- **Standard Tooling**
  - Agent Skills spec (`SKILL.md` with `name` + `description` frontmatter) is the shared format. Claude, Codex, Pi, and Cursor all read it. Droid/Factory has no documented project-local skills convention in this repo.

## File Registry
| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| src/deviate/cli/__init__.py | Python CLI | Owns setup export, per-agent dirs, Codex skill install | `Official project-local discovery is ``.agents/skills/<name>/SKILL.md``` / `skills_root = install_root / ".agents" / "skills"` |
| src/deviate/cli/__init__.py | Python CLI | Documents Pi global skill path vs Codex path | `Pi loads global skills from ``~/.pi/agent/skills/``; the` / `other platforms use ``~/.{agent}/skills/`` (Claude) or` / ```~/.agents/skills/`` (Codex).` |
| src/deviate/cli/__init__.py | Python CLI | Returns per-agent skill dir; codex maps to `.agents/skills` | `if agent == "codex":` / `return workdir / ".agents" / "skills"` |
| src/deviate/cli/__init__.py | Python CLI | Notes opencode/factory have no documented skills convention | `- ``opencode`` / ``factory`` — no documented project-local skills` / `convention; the file is still written so the skill is on disk if` |
| src/deviate/core/commands.py | Python core | Composes slash-command bodies for install | `def compose_command_body(` / `raw: str,` / `core_dir: Path,` |
| src/deviate/core/commands.py | Python core | Installs one command; supports SKILL.md target name | `Pass ``target_filename`` to override the basename (Codex skills use` / ```SKILL.md``). Returns ``True`` when the file was created or` |
| src/deviate/prompts/assembly.py | Python prompts | Composes auto-mode prompts from tiers | `specs/constitution.md       — project governance (from *constitution_path*)` / `core/core.md                — universal invariants (shared by ALL phases)` |
| src/deviate/core/agent.py | Python core | Defines Pi lean flags plus conditional skill injection | `PI_DEVIATDD_SKILL = Path(".pi") / "skills" / "deviatdd" / "SKILL.md"` / `if (skill_root / PI_DEVIATDD_SKILL).is_file():` / `flags.extend(["--skill", str(PI_DEVIATDD_SKILL)])` |
| src/deviate/core/agent.py | Python core | Starts Pi with `--no-skills` by default | `"--tools",` / `",".join(PI_CODING_TOOLS),` / `"--no-skills",` |
| src/deviate/cli/micro.py | Python CLI | Builds agent prompt from skill content plus task JSON | `skill_content = _SKILL_NAMES.get(phase_name.upper())` / `return skill_content.replace("$ARGUMENTS", task_context)` |
| src/deviate/prompts/skills/deviatdd/SKILL.md | Skill prompt | Ships the per-task micro orchestrator loop | `This skill runs \`deviate micro run\` (bare, no task ID) on repeat.` / `**Do NOT use \`deviate micro run --all\`**` |
| src/deviate/prompts/commands/deviate-adhoc.md | Slash command | Defines the adhoc issue compiler frontmatter pattern | `name: deviate-adhoc` / `description: Emit a single ad-hoc vertical-slice issue from a natural-language task` |
| pyproject.toml | Manifest | Declares runtime deps and CLI entry point | `deviate = "deviate.main:app"` / `"typer>=0.12",` / `"rich>=13.0",` |
| specs/constitution.md | Governance | Pins stack, layers, gates, and done criteria | `Version: 0.11.0` / `- Python 3.13` / `- Framework: Typer (CLI entry points) with Rich for terminal I/O` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 4 — `src/deviate/cli/__init__.py`, `src/deviate/core/agent.py`, `src/deviate/core/commands.py`, `src/deviate/prompts/skills/deviatdd/SKILL.md` |
| New Modules Required | No |
| New Persistence / Data Models | No |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Auto-runner prompt path (`assembly.py::load_template` vs `commands.py::compose_command_body`) plus Pi `--skill` injection flag |
| Rationale | Export touches two install targets and one spawn path. No new store exists. No new vendor exists. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | skills-export-agents |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/skills-export-agents.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) or `/deviate-research` (High complexity) — see `## Scope Sizing` |
