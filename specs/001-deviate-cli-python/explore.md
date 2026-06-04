# Exploration Report: Greenfield DeviaTDD CLI in Python

## [PROBLEM_DEFINITION]
- **Statement**: Build the `deviate` CLI application in Python (Typer + Rich) as a unified replacement for 14 existing shell orchestrator scripts and the RGR TDD cycle runner. The CLI must consolidate runtime context gathering, structural static analysis, configuration discovery, task state mutations, and the micro-sandbox test loop into an atomic, platform-agnostic engine.
- **Scope**: Structural inventory of existing prompt skills, shell scripts, specification documents, project configuration, and tooling baseline. Verified components: `prompts/` (18 skill directories), specs (`constitution.md`, `DeviaTDD-api.md`, `DeviaTDD-architecture.md`), `pyproject.toml`, `mise.toml`, `.githooks/`, `CLAUDE.md`/`AGENTS.md`.
- **Exclusions**: No architectural decisions, design trade-offs, risk evaluations, or data modeling — these are deferred to the `deviate-research` skill. No code generation, test writing, or implementation scaffolding.

## [DISCOVERY_AUDIT_RESULTS]
### Verified Dependencies
- `typer>=0.12` → declared in `pyproject.toml:7`
- `rich>=13.0` → declared in `pyproject.toml:8`
- `pydantic>=2.0` → declared in `pyproject.toml:9`
- `pytest>=8.0` → declared in `pyproject.toml:16` (extras `dev`)
- `ruff>=0.4` → declared in `pyproject.toml:17` (extras `dev`)

### Ghost Dependencies
- `aider` (Python API `aider.coders.Coder`) — referenced extensively in `specs/DeviaTDD-architecture.md` (lines 66-78) as the Micro-layer execution engine, but not listed in `pyproject.toml` dependencies.
- `bats` (Bash automated test system) — referenced in `specs/constitution.md` line 43 as E2E testing tool and in `mise.toml` line 14, but not declared as a Python dependency (expected: system-level tool).
- `hatchling` — build backend declared in `pyproject.toml:22-23`, does not appear in dependencies (expected: build-system only).

### Manifest Files Observed
- `pyproject.toml` — Python project metadata, CLI entry point, dependencies, build config (hatchling), ruff/pytest config.
- `mise.toml` — Task runner definitions (test, lint, format, check, setup, clean), env config, tool versions.

### Test Runner Configuration
- `mise.toml:9` — `pytest tests/ -v` (unit tests)
- `mise.toml:13` — `bats tests/e2e/` (E2E tests via bats)
- `pyproject.toml:31-32` — `testpaths = ["tests"]`
- `.githooks/pre-commit:2` — `mise run check` (runs lint + format-check + test)
- `.githooks/pre-push:2` — `mise run test`

### Manifest-Constitution Divergence
- No divergence detected. The constitution's `[2_5_TOOLING]` section (uv, pytest, ruff, bats, mise) matches `pyproject.toml` and `mise.toml` declarations. The constitution's `[2_1_BACKEND]` (Typer + Rich) matches `pyproject.toml` dependencies.

## [CONSTITUTION_QUOTES]
- **Language**: "Python 3.13"
- **Dependencies**: "Package manager: `uv` | Test runner: `pytest` | Linter: `ruff` (lint + format) | E2E testing: `bats` | Task runner: `mise`"
- **Testing**: "TEST_FRAMEWORK: pytest | TEST_ROOT: tests | TEST_EXT: .py | TEST_COMMAND: pytest tests/ -v | LINT_COMMAND: ruff check . | E2E_COMMAND: bats tests/e2e/"
- **Runtime**: "CLI application (`deviate`) | Framework: Typer (CLI entry points) with Rich for terminal I/O | Micro-sandbox: Aider Python API (`aider.coders.Coder`) as LLM execution substrate"
- **Constraints**: "Three-Layer Architecture | Append-Only Ledger Protocol | Git Isolation Principle | Tamper Guard | Human-in-the-Loop (HITL) | Session Continuity | Model Tiering"
- **Test**: "Coverage target: >= 80% | RED phase tests must fail with AssertionError or NotImplementedError | GREEN phase must pass all tests; Tamper Guard resets unauthorized test edits | REFACTOR phase runs regression gate"

## [ARCHITECTURAL_BASELINES]
- **Existing Architectural Patterns**: The project defines a three-layer architecture (Macro/Meso/Micro) in `specs/constitution.md:9-16`. No production source code exists yet — greenfield. The 14 shell scripts follow a pre/post script pattern: each orchestrator script has a `pre` subcommand that validates state and emits a JSON contract, and a `post` subcommand that validates output, stages, and commits.
  ```sh
  # From prompts/deviate-explore/deviate-explore.sh (line 1 excerpt)
  #!/usr/bin/env bash
  set -euo pipefail
  ```
- **Infrastructure & Operations**: No CI/CD, Docker, or K8s configs present. Local execution only. Git hooks at `.githooks/pre-commit` and `.githooks/pre-push` enforce validation gates.
  ```bash
  # .githooks/pre-commit
  #!/usr/bin/env bash
  set -e
  mise run check
  ```
- **Data & State Management**: No database runtime. JSONL append-only ledgers (`issues.jsonl`, `tasks.jsonl`) and TOML config (`config.toml`) specified in `specs/constitution.md:28-32`. No ORM, caching, or async worker infrastructure exists.
- **Quality, Safety & Observability**: Testing patterns defined in `specs/constitution.md:49-63` and `mise.toml:8-38`. Ruff for linting/formatting. No mypy (explicitly "not yet configured"). Bats for E2E CLI integration tests.
  ```toml
  # mise.toml:37
  [tasks.check]
  depends = ["lint", "format-check", "test"]
  ```
- **External Integrations**: Aider Python API (`aider.coders.Coder`) specified as the Micro-layer LLM execution substrate (`specs/constitution.md:35`). No other third-party API clients, webhooks, or SDKs.

## [ECOSYSTEM_RESEARCH]
- **Best Practices — Typer subcommand grouping**: Use `app.add_typer(sub_app, name="group")` to compose independent `typer.Typer()` apps as command groups. Each sub-app lives in its own file. Enables nested subcommands at arbitrary depth. Source: `typer.tiangolo.com/tutorial/subcommands/add-typer/`
  ```python
  import typer
  app = typer.Typer()
  app.add_typer(users.app, name="users")
  app.add_typer(items.app, name="items")
  ```
- **Best Practices — Aider Python API**: `Coder.create()` accepts `main_model`, `fnames`, `io`. Call `coder.run("instruction")`. Use `InputOutput(yes=True)` for scripting. Source: `aider.chat/docs/scripting.html`
  ```python
  from aider.coders import Coder
  from aider.models import Model
  from aider.io import InputOutput
  coder = Coder.create(main_model=model, fnames=["file.py"], io=InputOutput(yes=True))
  coder.run("implement the function")
  ```
- **Best Practices — Rich Interactive UI**: Rich provides `Progress` (context manager with `add_task`/`update`), `Panel` (bordered containers), and `Console.input()`. Source: `rich.readthedocs.io/en/stable/progress.html`
  ```python
  from rich.progress import Progress
  with Progress() as progress:
      task = progress.add_task("[red]Processing...", total=100)
      progress.update(task, advance=1)
  ```
- **Standard Tooling — uv + mise**: mise manages Python versions, uv handles packages. Set `python.uv_venv_auto = "create|source"` in `mise.toml`. Source: `mise.jdx.dev/lang/python.html`
  ```toml
  [settings]
  python.uv_venv_auto = "create|source"
  ```
- **Standard Tooling — Typer CLI testing**: Use `typer.testing.CliRunner` (wraps Click's CliRunner). Source: `typer.tiangolo.com/tutorial/testing/`
  ```python
  from typer.testing import CliRunner
  runner = CliRunner()
  result = runner.invoke(app, ["arg1", "--flag"])
  assert result.exit_code == 0
  ```

## [FILE_REGISTRY]
| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `pyproject.toml` | Manifest | Python project metadata, CLI entry point, deps (Typer, Rich, Pydantic), build config | `[project]\nname = "deviate"\nversion = "0.1.0"\ndescription = "DeviaTDD CLI — agent orchestration framework"\nrequires-python = ">=3.13"\ndependencies = [\n    "typer>=0.12",\n    "rich>=13.0",\n    "pydantic>=2.0",\n]` |
| `mise.toml` | Config | Task runner definitions (test, lint, format, check, setup, clean, help), tool versions | `[tasks.test]\nrun = "pytest tests/ -v"\ndescription = "Run unit tests"\n\n[tasks.check]\ndepends = ["lint", "format-check", "test"]\ndescription = "All validation checks"` |
| `CLAUDE.md` | Governance | Agent behavior rules, DeviaTDD phase architecture, model routing, HITL gates | `<!-- MANAGED_BY: tools:init -->\n\n## ⚙️ Project Execution Contract (MANDATORY)\n- **Repository Type**: single-language (Python)\n- **Execution Mode**: TDD (Red-Green-Refactor via deviate cycle)` |
| `AGENTS.md` | Governance | Symlink to CLAUDE.md for multi-agent platform compatibility | `AGENTS.md: symbolic link to CLAUDE.md` |
| `specs/constitution.md` | Governance | Authoritative architectural rules: 3-layer arch, append-only ledgers, tamper guard, model tiering | `[CONSTITUTION_VERSION]: 0.1.0\n\n## [1_ARCHITECTURAL_PRINCIPLES]\n- **Three-Layer Architecture**: Macro (feature scoping), Meso (issue engineering), Micro (TDD sandbox).` |
| `specs/DeviaTDD-api.md` | Architecture Spec | Full CLI endpoint blueprint: all deviate subcommands, document architecture, prompt matrix, model pricing | `# DeviaTDD Framework Migration & Endpoint Architecture Blueprint\n\nThis document details the transition from legacy Spec-Driven Development (SDD) scripts...` |
| `specs/DeviaTDD-architecture.md` | Architecture Spec | Complete architecture: hierarchical layers, state machine engine, phase prompts, HITL gates, cost architecture | `# DeviaTDD: Dual Engine Verification Infrastructure for Agentic Test-Driven Development` |
| `.githooks/pre-commit` | Git Hook | Runs all validation checks on pre-commit | `#!/usr/bin/env bash\nset -e\nmise run check` |
| `.githooks/pre-push` | Git Hook | Runs tests on pre-push | `#!/usr/bin/env bash\nset -e\nmise run test` |
| `.gitignore` | Config | Python artifacts, uv files, test cache, IDE files, worktrees | `__pycache__/\n*.py[cod]\n*.so\nbuild/\ndist/\n*.egg-info/\n*.egg` |
| `prompts/deviate-adhoc/SKILL.md` | Skill/MD | Condensed explore+prd+shard for low/medium complexity tasks (163 lines) | `name: deviate-adhoc\ndescription: Generate a single ad-hoc vertical-slice issue...` |
| `prompts/deviate-constitution/SKILL.md` | Skill/MD | Initialize/update specs/constitution.md with architectural standards (221 lines) | `name: deviate-constitution\ndescription: Governance artifact generation...` |
| `prompts/deviate-context/SKILL.md` | Skill/MD | Sync spec.md and constitution.md into CLAUDE.md/AGENTS.md (207 lines) | `name: deviate-context\ndescription: Synchronize agent context files (CLAUDE.md, AGENTS.md)...` |
| `prompts/deviate-cycle/SKILL.md` | Skill/MD | Routes to execute/red/green/refactor based on state (573 lines) | `name: deviate-cycle\ndescription: Determine the current workflow state...` |
| `prompts/deviate-e2e/SKILL.md` | Skill/MD | End-to-end verification after all phases complete (234 lines) | `name: deviate-e2e\ndescription: Use when executing the E2E verification phase...` |
| `prompts/deviate-execute/SKILL.md` | Skill/MD | Direct task execution for low-complexity tasks (262 lines) | `name: deviate-execute\ndescription: Use when executing a single task directly...` |
| `prompts/deviate-explore/SKILL.md` | Skill/MD | Fast codebase scan, produces explore.md (238 lines) | `name: deviate-explore\ndescription: Pure exploration only. Deterministic, factual structural scan...` |
| `prompts/deviate-green/SKILL.md` | Skill/MD | GREEN phase: implement minimal code to pass failing tests (210 lines) | `name: deviate-green\ndescription: Use when executing the GREEN (implementation) phase of TDD...` |
| `prompts/deviate-hotfix/SKILL.md` | Skill/MD | Bug-fix planning: 1-2 task TDD cycle for urgent fixes (193 lines) | `name: deviate-hotfix\ndescription: Use when decomposing bug reports into Red-Green-Refactor hotfix units...` |
| `prompts/deviate-prd/SKILL.md` | Skill/MD | Compile explore+research into prd.md with FR/AC tokens (216 lines) | `name: deviate-prd\ndescription: Compile exploration results into a Product Requirements Document...` |
| `prompts/deviate-prune/SKILL.md` | Skill/MD | Test optimization: removes implementation-coupled tests (259 lines) | `name: deviate-prune\ndescription: Use when executing the PRUNE (test optimization) phase of TDD...` |
| `prompts/deviate-red/SKILL.md` | Skill/MD | RED phase: write failing tests as executable specification (219 lines) | `name: deviate-red\ndescription: Use when executing the RED (test-writing) phase of TDD for a single task...` |
| `prompts/deviate-refactor/SKILL.md` | Skill/MD | REFACTOR phase: behavior-preserving structural improvement (195 lines) | `name: deviate-refactor\ndescription: Use when executing the REFACTOR (code cleanup) phase of TDD...` |
| `prompts/deviate-research/SKILL.md` | Skill/MD | Expensive reasoning: produces design.md and data-model.md (326 lines) | `name: deviate-research\ndescription: Architectural analysis of the feature scope...` |
| `prompts/deviate-shard/SKILL.md` | Skill/MD | Decompose PRD into standalone GitHub Issues with DAG topology (193 lines) | `name: deviate-shard\ndescription: Decompose a Product Requirements Document (prd.md)...` |
| `prompts/deviate-specify/SKILL.md` | Skill/MD | Specify phase: produce spec.md with Gherkin acceptance criteria (134 lines) | `name: deviate-specify\ndescription: Write a functional specification contract (spec.md)...` |
| `prompts/deviate-tasks/SKILL.md` | Skill/MD | Tasks phase: decompose spec.md into Red-Green-Refactor units (236 lines) | `name: deviate-tasks\ndescription: Decompose spec.md into a granular task decomposition...` |
| `prompts/deviate-triage/SKILL.md` | Skill/MD | Triage gatekeeper: classify requirements as FULL/CORE/TDD/NONE (141 lines) | `name: deviate-triage\ndescription: Classify development requirements against fixed decision predicates...` |
| `prompts/deviate-constitution/deviate-constitution.sh` | Bash Script | Pre/post orchestrator for constitution: git state, path discovery, validation, commit (1107 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-context/deviate-context.sh` | Bash Script | Pre/post orchestrator for context sync: spec dir discovery, language detection, symlink (1233 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-e2e/deviate-e2e.sh` | Bash Script | Pre/post orchestrator for E2E: project type detection, phase completion, stage+commit (1193 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-execute/deviate-execute.sh` | Bash Script | Pre/post orchestrator for direct execution: workflow discovery, task auto-discovery (1386 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-explore/deviate-explore.sh` | Bash Script | Pre/post orchestrator for explore: feature bucket allocation, constitution gate, issue ledger (1133 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-green/deviate-green.sh` | Bash Script | Pre/post orchestrator for GREEN: task location, constitution command extraction, commit (1139 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-hotfix/deviate-hotfix.sh` | Bash Script | Pre/post orchestrator for hotfix: bug context discovery, issue file lookup, commit (960 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-prd/deviate-prd.sh` | Bash Script | Pre/post orchestrator for PRD: epic slug discovery, artifact validation, commit (1166 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-prune/deviate-prune.sh` | Bash Script | Pre/post orchestrator for PRUNE: task location, test file identification, commit (1155 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-red/deviate-red.sh` | Bash Script | Pre/post orchestrator for RED: task discovery, constitution command extraction, commit (1161 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-refactor/deviate-refactor.sh` | Bash Script | Pre/post orchestrator for REFACTOR: task location, constitution extraction, commit (1124 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-research/deviate-research.sh` | Bash Script | Pre/post orchestrator for research: feature resolution, explore validation, artifact commit (1253 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-shard/deviate-shard.sh` | Bash Script | Pre/post orchestrator for shard: epic discovery, PRD validation, issue ledger registration (1310 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-specify/deviate-specify.sh` | Bash Script | Pre/post orchestrator for specify: issue resolution, worktree creation, spec validation (1655 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |
| `prompts/deviate-tasks/deviate-tasks.sh` | Bash Script | Pre/post orchestrator for tasks: worktree detection, spec validation, task validation (1298 lines) | `#!/usr/bin/env bash\nset -euo pipefail` |

## [STATUS_SUMMARY]
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| FEATURE_SLUG | 001-deviate-cli-python |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/001-deviate-cli-python/explore.md |
| EPIC_ID | 001 |
| NEXT_ACTION | Run the `deviate-research` skill |
