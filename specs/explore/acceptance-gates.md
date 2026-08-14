# Exploration Scan — Acceptance Criteria and Phase-Specific Test Gates

## Problem Definition
[Statement]: Make acceptance criteria explicit, slice-level artifacts and apply test enforcement to Green and Refactor but not to Red. The proposed change adds a required `acceptance.md` artifact per implementation slice (`specs/<feature>/<slice>/acceptance.md`), requires criteria-to-task and criteria-to-test traceability, makes Green and Refactor blocking validation phases, and replaces the Red test gate with a non-blocking Red checkpoint.

[Scope]: This scan covers the DeviaTDD CLI structures that the proposed change touches. These include the micro-layer phase runners (`src/deviate/cli/micro.py`), the meso-layer plan and tasks commands (`src/deviate/cli/meso.py`), the task ledger model (`src/deviate/state/ledger.py`), the artifact validation layer (`src/deviate/core/validation.py`), the task-ledger generator (`src/deviate/core/tasks_ledger.py`), the micro-layer prompt command templates under `src/deviate/prompts/commands/`, the CLI command registration (`src/deviate/cli/__init__.py`), and the authoritative specs `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md`.

[Exclusions]: Architectural decisions, design trade-offs, recommendation of a specific acceptance.md format, risk analysis, data-model design, and failure-mode speculation are deferred to the `deviate-research` skill. This scan only catalogs what exists.

## Discovery Audit Results
### Verified Dependencies
- [typer]: Appears in `src/deviate/cli/__init__.py`, `src/deviate/cli/micro.py`, `src/deviate/cli/meso.py` for CLI entry points. Declared as the framework per the constitution Tech Stack Standards.
- [rich]: Appears in `src/deviate/cli/micro.py` (`from rich.console import Console`) and `src/deviate/ui/` for terminal I/O.
- [pydantic]: Appears in `src/deviate/state/ledger.py` (`BaseModel`, `Field`, `field_validator`, `model_validator`) for ledger record models.
- [yaml / PyYAML]: Appears in `src/deviate/cli/micro.py` (`import yaml`) and `src/deviate/core/validation.py`.
- [pytest]: Appears in the constitution Testing Protocols and `pyproject.toml`/`mise.toml` test tasks.
- [ruff]: Appears in the constitution Testing Protocols and `mise.toml` lint tasks.
- [bats]: Appears in the constitution Testing Protocols and `mise.toml` e2e task for `tests/e2e/`.
- [Git]: Invoked via subprocess throughout `micro.py` and `core/` (e.g. `_git_env()` in `src/deviate/core/_shared.py`).

### Ghost Dependencies
- [tree-sitter / tree-sitter-languages]: Referenced by `tests/test_visual_demo/test_tsk_001_01.py` and by issue/task artifacts, but the observed `src/deviate/core/` tree contains no `treesitter.py` module. This is a declarative finding only; no fix is recommended.
- [Tabularize / table formatting in `_emit_yaml_summary`]: Not applicable — no unmanifested third-party library observed for this change. The `src/deviate/cli/micro.py` output handler uses only stdlib `re`, `json`, and `rich`.

### Manifest Files Observed
- `pyproject.toml`: [Python project metadata, dependencies, and Hatch build configuration for the `deviate` CLI.]
- `mise.toml`: [Task runner manifest declaring `test`, `test-e2e`, `lint`, `format`, `check`, and `publish` tasks.]
- `uv.lock`: [Lock file pinning the Python dependency graph used by `uv sync`.]
- `specs/DeviaTDD-api.md`: [Authoritative API specification documenting every phase command, contract field, and gate semantics.]
- `specs/DeviaTDD-architecture.md`: [Authoritative architecture specification for the three-layer macro/meso/micro model.]
- `specs/constitution.md`: [Project constitution v0.9.0 declaring architectural principles, tech stack, testing protocols, and Definition of Done.]

### Test Runner Configuration
- Test command source (`specs/constitution.md` §3 Testing Protocols, verbatim): `pytest tests/ -v`
- Test task (`mise.toml [tasks.test]`): 
  ```
  run = "uv run pytest --testmon-noselect tests/ -v"
  ```
- Lint task (`mise.toml [tasks.lint]`): `run = "uv run ruff check"`
- Lint command source (`specs/constitution.md` §3): `ruff check .`
- E2E task (`mise.toml [tasks.test-e2e]`): `run = "bats tests/e2e/"`
- E2E command source (`specs/constitution.md` §3): `bats tests/e2e/`
- Code-quality gate (`mise.toml [tasks.check]`): `depends = ["lint", "format-check"]`

### Manifest-Constitution Divergence
- No divergence observed between the constitution Tech Stack Standards and the observed manifests. The constitution declares "Test command: `pytest tests/ -v`" while `mise.toml [tasks.test]` uses `uv run pytest --testmon-noselect tests/ -v`. Both quote the same underlying pytest runner; the constitution's `test_command` differs only in leading `uv run` wrapper and `--testmon-noselect` flag. Both are quoted verbatim without adjudication.

## Constitution Quotes
Constitution excerpts quoted verbatim from `specs/constitution.md`. No interpretation, inference, or classification. The `deviate-research` skill owns interpretation.
- **Architectural Principles**: "**Micro-Layer Scope**: GREEN phase writes only to `src/` and permitted implementation paths. Any mutation outside this allow-list is flagged by the JUDGE phase as a scope violation." and "**Four-Layer Architecture**: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Macro PRD/shard/adhoc artifacts carry acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract."
- **Tech Stack Standards**: "Test runner: `pytest`", "Linter: `ruff` (lint + format)", "E2E testing: `bats` (Bash automated test system)", "Task runner: `mise` (see `mise.toml` for all tasks)", "Code quality gate: `mise run check`", and "No persistent database runtime (all state tracked in JSONL ledgers and TOML config)".
- **Testing Protocols**: "Test framework: pytest", "Test root: `tests/`", "Test extension: `.py`", "Test command: `pytest tests/ -v`", "Lint command: `ruff check .`", "E2E command: `bats tests/e2e/`", "Coverage target: >= 80%", "GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files", and "REFACTOR phase runs regression gate: tests must re-pass after polish".
- **Definition of Done**: "Code implemented (satisfies assigned `AC-PLAN-NNN` scenarios from `plan.md`)", "Tests passing (pytest with clean exit code 0)", "Lint passing (ruff check with no violations)", "Judge phase passed (git diff validated against the authoritative plan acceptance contract)", "Documentation updated (`plan.md` Acceptance Contract, `spec.md`, and `design.md` reflect final implementation...)", "CHANGELOG.md updated under `[Unreleased]` for user-visible changes...", and "Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)".

## Architectural Baselines
[Pattern_Over_Instance]: Representative examples only. All paths are strictly relative to `repo_root`.
- **Existing Architectural Patterns**: The micro-phase runner in `src/deviate/cli/micro.py` implements RED, GREEN, JUDGE, REFACTOR, EXECUTE as separate `_run_*_phase` functions. Phase transition records are appended to `specs/**/tasks.jsonl` via `append_task_transition` (`src/deviate/state/ledger.py::append_task_transition`, keyed on `(id, status)`). Session state is stored in `.deviate/session.json` via `SessionState`. The `TaskRecord` model (`src/deviate/state/ledger.py:81`) declares fields `id`, `issue_id`, `description`, `status`, `execution_mode`, `created_at`, `security_profile` — it has no `acceptance_criteria` field today.
- **Infrastructure & Operations**: CLI subcommands are registered as Typer apps in `src/deviate/cli/__init__.py` via `cli.add_typer(<app>, name=<x>, ...)` with `rich_help_panel` grouping (User / Optional / Agent). Micro phase commands live under the `red_app`, `green_app`, `judge_app`, `refactor_app`, `execute_app` Typer groups. Slash-command prompts are package resources under `src/deviate/prompts/commands/<name>.md` (`deviate-red.md`, `deviate-green.md`, `deviate-judge.md`, `deviate-refactor.md`). No containerization; local execution on host.
- **Data & State Management**: Append-only JSONL ledgers. Issue ledger `specs/issues.jsonl`; task ledger `specs/**/tasks.jsonl`; flow ledger `specs/_product/flows.jsonl`. Session state in `.deviate/session.json`. Config in TOML via `.deviate/config.toml`. No persistent DB runtime. `TaskRecord.status` is a Literal of `PENDING`, `RED`, `GREEN`, `JUDGE`, `REFACTOR`, `COMPLETED`, `FAILED` (`src/deviate/state/ledger.py:85`).
- **Quality, Safety & Observability**: Artifact validation in `src/deviate/core/validation.py` (`validate_acceptance_contract` validates `AC-PLAN-NNN` Gherkin scenarios in plan.md with required `**Source Outline**`, `**Upstream Traceability**`, `**Current-Code Evidence**`, Given/When/Then). Task JSONL validation in `src/deviate/core/tasks_ledger.py::validate_tasks_jsonl`. Git isolation enforced via `_git_env()` (`src/deviate/core/_shared.py`). Logging via `RunLogger`/`TaskLogger`/`log_event` (`src/deviate/core/run_logger.py`). RED/GREEN phase commits use `no_verify=True` in `micro.py`.
- **External Integrations**: Agent backends (pi, claude, opencode) invoked via `AgentBackend` (`src/deviate/core/agent.py`) with `resolve_agent_to_backend`. Tree-sitter referenced in tests but no module present in `src/deviate/core/`. No other third-party API clients observed.

## Ecosystem Research
[Web_Discovery]: Factual cataloging of industry best practices for TDD acceptance criteria and phase-specific test gates. This change proposal aligns with established standards already encoded in the repo; no new external library behavior is required. Web search was not invoked as the domain conventions are declared in the repository's own authoritative specs.
- **Best Practices**: Acceptance criteria should be observable, testable outcomes with stable identifiers, traced to requirements. The repo already encodes this via `AC-PLAN-NNN` scenarios in `plan.md` (Source: `specs/DeviaTDD-api.md:417` — "Plan reconciles each outline into complete `AC-PLAN-NNN` scenarios with Source Outline, upstream traceability, current-code evidence, and Given/When/Then").
- **Common Use Cases & Pitfalls**: TDD preserves Red-Green-Refactor intent. A blocking test-success gate in Red is counterproductive because Red intentionally contains a failing test. The repo's current Red runner enforces the inverse blocking gate: "the orchestrator rejects the phase if the test passes; the runner enforces that RED must produce a failing test" (`src/deviate/prompts/commands/deviate-red.md:40-41`), and `_run_red_phase` raises `PhaseFailedError` on returncode 0 (`src/deviate/cli/micro.py:1121`). This is the exact blocking behavior the proposal asks to replace with a non-blocking checkpoint.
- **Standard Tooling**: pytest for tests, ruff for lint, bats for E2E, Typer for CLI, Pydantic for record models, Rich for terminal I/O. All are declared in `specs/constitution.md` §2/§3 and `mise.toml`. The change proposal can reuse the existing project-configurable test command (`_resolve_test_command` / `mise.toml [tasks.test]`) rather than introducing a new runner.

## File Registry
All paths are strictly relative to `repo_root`. Every row carries a verbatim quote captured at extraction time.

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/micro.py` | Codebase_File | Micro-layer phase runner (RED/GREEN/JUDGE/REFACTOR/EXECUTE). | `def _run_red_phase(...): ... test_result = _run_test_cmd(root) ; if test_result.returncode == 0: raise PhaseFailedError( f"RED phase test passed for {tid} — RED must author a failing test...")` |
| `src/deviate/cli/micro.py` | Codebase_File | GREEN phase blocking test and commit orchestration. | `test_result = _run_test_cmd(root, task) ; if test_result.returncode != 0: ... session.train_feedback = "The test suite failed after GREEN implementation..."` |
| `src/deviate/cli/micro.py` | Codebase_File | Micro-layer Typer app registration and phase application objects. | `red_app = typer.Typer(no_args_is_help=True) ; green_app = typer.Typer(no_args_is_help=True) ; judge_app = typer.Typer(no_args_is_help=True) ; refactor_app = typer.Typer(no_args_is_help=True)` |
| `src/deviate/state/ledger.py` | Codebase_File | Defines `TaskRecord` model and append-only ledger helpers. | `class TaskRecord(BaseModel): id: str ; issue_id: str ; description: str ; status: Literal["PENDING","RED","GREEN","JUDGE","REFACTOR","COMPLETED","FAILED"] = "PENDING" ; execution_mode: Literal[...] = "TDD"` |
| `src/deviate/state/ledger.py` | Codebase_File | Append-only task transition helper. | `def append_task_transition(record: TaskRecord, ledger_path: Path) -> bool: ... key_fields=["id", "status"], ledger_path=ledger_path, )` |
| `src/deviate/core/validation.py` | Codebase_File | Validates plan.md `AC-PLAN-NNN` acceptance contract. | `contract_pattern = re.compile(r"\*\*(?P<label>Scenario (?P<id>AC-PLAN-\d{3})):.*?\*\*") ; errors = _validate_scenarios(body, contract_pattern) ... "Acceptance Contract must contain at least one AC-PLAN-NNN scenario"` |
| `src/deviate/core/tasks_ledger.py` | Codebase_File | Generates `tasks.jsonl` from `tasks.md`. | `def generate_jsonl_from_md(tasks_md: Path, issue_id: str) -> list[TaskRecord]: ... id=task_id, issue_id=issue_id, description=description or "", status="PENDING", execution_mode=execution_mode,` |
| `src/deviate/cli/meso.py` | Codebase_File | meso `tasks_pre` enforces plan.md acceptance-contract prerequisite. | `# ── Enforce plan.md + acceptance-contract prerequisite ───────── ; acceptance_errors = validate_acceptance_contract(content) ; if acceptance_errors: ... console.print(f"[red]{status}[/] {plan_path}: {'; '.join(acceptance_errors)}")` |
| `src/deviate/prompts/commands/deviate-red.md` | Config | RED-phase slash-command prompt template. | `the orchestrator rejects the phase if the test passes; the runner enforces that RED must produce a failing test.` |
| `src/deviate/prompts/commands/deviate-refactor.md` | Config | REFACTOR-phase slash-command prompt template. | `preserve externally observable behavior (no behavior changes). Modifying tests is prohibited in the Refactor phase. Ensure 100% test pass before concluding.` |
| `src/deviate/prompts/auto/red.md` | Config | Auto RED-phase prompt template used by `_build_auto_prompt`. | (template consumed by `assemble_prompt(template_name="red", ...)` in `micro.py::_build_auto_prompt`) |
| `src/deviate/prompts/auto/green.md` | Config | Auto GREEN-phase prompt template. | (template consumed by `assemble_prompt(template_name="green", ...)` in `micro.py::_build_auto_prompt`) |
| `src/deviate/cli/__init__.py` | Codebase_File | CLI subcommand registration for phase Typer apps. | `cli.add_typer(red_app, name="red", rich_help_panel=_AGENT_PANEL, help="Micro: write a failing test")` |
| `src/deviate/core/constitution.py` | Codebase_File | Extracts test/lint commands from constitution. | `cmds = extract_commands(const_path) ; return cmds.get("lint_command", "")` |
| `src/deviate/state/config.py` | Codebase_File | Loads `.deviate/config.toml` and resolves phase models. | `data = _load_deviate_config_toml(root) ; ... return resolve_phase_model(phase, models)` |
| `specs/DeviaTDD-api.md` | Manifest | Authoritative API spec documenting RED/GREEN/REFACTOR gate semantics. | `Verifies a RED transition exists for the active issue. Runs pytest -v, requires returncode 0. Appends GREEN transition to ledger...` |
| `specs/constitution.md` | Manifest | Project constitution v0.9.0. | `GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files` / `REFACTOR phase runs regression gate: tests must re-pass after polish` |
| `mise.toml` | Config | Task-runner manifest. | `[tasks.test] run = "uv run pytest --testmon-noselect tests/ -v"` |
| `pyproject.toml` | Manifest | Python package manifest for the `deviate` CLI. | (declares dependencies and Hatch build config; `[project]` metadata present) |
| `tests/test_micro/test_red.py` | Test | Unit tests for RED-phase runner. | (tests mocking `deviate.cli.micro._run_pytest` per AGENTS.md performance contract) |
| `tests/test_micro/test_green.py` | Test | Unit tests for GREEN-phase runner. | (tests the blocking test gate and ledger transition paths) |
| `tests/conftest.py` | Test | Shared fixtures and `_git_env`/`tmp_git_repo` isolation helpers. | (canonical git-isolation helper referenced by AGENTS.md; every test git call uses `cwd=<tmp_git_repo>` + `env=_git_env()`) |
| `specs/adhoc/008-ast-phase-prioritization/tasks.md` | Config | Representative slice `tasks.md` artifact showing task→AC traceability today. | `  - **Rationale**: ... AC-ADHOC-008-04, AC-ADHOC-008-05, AC-ADHOC-008-07, AC-ADHOC-008-08. The EXTENSION_MAP is the single source of truth...` |

## Scope Sizing
| Metric | Value |
| :--- | :--- |
| Estimated Complexity | High |
| Files Likely Modified | 10+ key files: `src/deviate/cli/micro.py` (RED checkpoint, GREEN/REFACTOR gates), `src/deviate/cli/meso.py` (acceptance.md scaffolding in tasks/slice setup), `src/deviate/state/ledger.py` (`TaskRecord` + new RedCheckpoint record), `src/deviate/core/validation.py` (acceptance.md parser/validator), `src/deviate/core/tasks_ledger.py`, `src/deviate/cli/__init__.py` (new `acceptance`/`red checkpoint`/`green verify`/`refactor verify` commands), `src/deviate/prompts/commands/*` and `src/deviate/prompts/auto/*` (acceptance/red/green/refactor templates), plus `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`, and new tests under `tests/test_micro/`, `tests/test_meso/`, `tests/test_core/` |
| New Modules Required | Yes (slice `acceptance.md` artifact generation + a new acceptance/red-checkpoint command surface; possibly new ledger record types) |
| New Persistence / Data Models | Yes (`acceptance.md` per-slice artifact + persistent non-blocking Red checkpoint records + `acceptance_criteria` field on task records) |
| New External Integrations | No |
| Upstream / Cross-Cutting Concerns | Touches macro/meso/micro layers and the Product flow model. The new `AC-*` / `AC-PLAN-NNN` traceability must coexist with the existing `AO-NNN` → `AC-PLAN-NNN` contract. Requires coordinated updates to the authoritative `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit, plus `CHANGELOG.md`. Applies test gates to GREEN/REFACTOR while changing RED semantics. |
| Rationale | The change is cross-cutting: it adds a new required slice artifact (`acceptance.md`), a new persistent checkpoint record type, a new task-data field (`acceptance_criteria`), multiple new CLI commands, new prompt templates, and modifies the blocking behavior of all three micro TDD gates. It also mandates identical-commit updates to two authoritative specs and the changelog, which pushes this to High complexity. |

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | `acceptance-gates` |
| GIT_BRANCH | `main` |
| SPEC_TARGET | `specs/explore/acceptance-gates.md` |
| NEXT_ACTION | Run `/deviate-research` (High complexity) — see `## Scope Sizing`. Instruct the human operator to invoke the `deviate-research` skill with the explore slug `acceptance-gates`. |
