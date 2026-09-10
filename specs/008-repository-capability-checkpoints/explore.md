# Repository Capability Boundary and Runtime Verification

## Problem Definition

**Statement**: Explore the existing boundary between initialization, task verification, and repository-owned runtime verification.

Source: proposal §36: “DeviaTDD owns specification, TDD, and the decision to verify.”

**Scope**: Task parsing, Micro dispatch, handover validation, prompt composition, verification discovery, initialization, and their tests. Registry entries below anchor these components.

**Exclusions**: RepoReady implementation, application changes, and design decisions. This artifact records existing behavior for `/research`.

Contract anchors:

```json
{"feature_slug":"repository-capability-checkpoints","feature_dir":"specs/explore","spec_target":"specs/explore/repository-capability-checkpoints.md","git_branch":"main","is_greenfield":false}
```

The proposal explicitly establishes a product-independent boundary. Additional RepoReady internals are outside this exploration scope.

Source: proposal §3: “The integration boundary is therefore based on capabilities, not product identity.”

### RepoReady Context

The user supplied `../repoready/vision.md` during exploration. That document identifies itself as an initial design.

Source: `../repoready/vision.md`, §2:

 > RepoReady and DeviaTDD are independent projects.
 > DeviaTDD may discover and consume those capabilities.
 > Neither project should require the other.

The vision places checkpoint timing outside RepoReady ownership.

Source: `../repoready/vision.md`, §3:

 > Decide when a feature issue needs a checkpoint	No
 > Manage TDD task state	No

The vision describes optional capability metadata rather than an established integration schema.

Source: `../repoready/vision.md`, §51:

 > RepoReady may eventually publish a machine-readable capability manifest.
 > Do not make this mandatory for V1.

The vision distinguishes capability observations from command names.

Source: `../repoready/vision.md`, §24:

 > Preconditions
 > What must be running?
 > Action
 > What does the user or external caller do?
 > Expected observation
 > What stable state proves success?

The vision includes verification cleanup and generated evidence. These describe runtime effects, distinct from application source edits.

Source: `../repoready/vision.md`, §24:

 > Cleanup
 > What state must be reset afterwards?

Source: `../repoready/vision.md`, §28:

 > screenshots
 > browser traces
 > HTTP responses
 > application logs
 > database state
 > created files
 > queue state

Both proposals describe repository-owned commands and independent consumers. The current DeviaTDD parser and dispatcher remain as cataloged below.

Source: `../repoready/vision.md`, §58:

 > RepoReady prepares the interface.
 > It should not become the interface.

## Discovery Audit Results

### Verified Dependencies

`pyproject.toml` declares Python `>=3.13`, Typer, Rich, Pydantic, and PyYAML. It declares Hatchling for builds.

```toml
requires-python = ">=3.13"
dependencies = [
    "typer>=0.12",
    "rich>=13.0",
    "pydantic>=2.0",
    "pyyaml>=6.0.3",
]
```

The optional development extra declares pytest, Ruff, and pytest-testmon. The development group additionally declares pytest-timeout and evalplus.

Source: `pyproject.toml`:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-timeout>=2.4",
    "ruff>=0.15.16",
    "typer>=0.26.7",
    "evalplus>=0.3.1",
]
```

`mise.toml` declares Python and uv tools. CI installs Bats and jq through apt. Dependency declarations establish configuration presence, rather than installation health.

Source: `.github/workflows/ci.yml`:

```yaml
      - name: Install bats + jq
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends bats jq
```

### Ghost Dependencies

The constitution names Aider. The complete runtime dependency declaration above contains Typer, Rich, Pydantic, and PyYAML.

Source: `specs/constitution.md`, §2:

> - Micro-sandbox: Aider Python API (`aider.coders.Coder`) as LLM execution substrate

This is a documentation/declaration discrepancy. Runtime import necessity remains unestablished by this scan.

### Manifest Files Observed

`pyproject.toml`, `uv.lock`, and `mise.toml` are present. Their excerpts appear in the registry.

The filesystem listing also contains `.deviate/config.toml`. Its contents remain outside this scan. The constitution identifies that configuration contract:

> - Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment

### Test Runner Configuration

`pyproject.toml` sets pytest's root to `tests`. `mise.toml` declares full-suite and affected-suite commands.

Source: `mise.toml`:

```toml
[tasks.test]
run = "uv run pytest --testmon-noselect tests/ -v"
description = "Run the full test suite (forces full-suite; keeps .testmondata fresh)"
```

Source: `mise.toml`:

```toml
[tasks.check]
depends = ["lint", "format-check"]
description = "All validation checks"
```

The current `check` task covers lint and formatting. CI separately invokes pytest and Bats. This exploration executes structural reads only.

### Manifest-Constitution Divergence

- Aider: the constitution names its Python API; the runtime dependency list above omits that package.
- Tool path: `AGENTS.md` says “All task definitions live in `.mise.toml`”; the observed manifest is `mise.toml`.
- Closing verification: the current Tasks prompt states an issue-end closing task; both authoritative specifications describe conditional closing sweeps.

Source: `src/deviate/prompts/auto/tasks.md`, step 9:

> 9. **Closing verification task** (issue-end, last, no forward Dependency). It is always `Verification_Batch` / `IMMEDIATE`, and MUST NOT have a `Test Strategy` because it creates no tests. Never emit empty e2e files. Never require integration setup. Its Verification may run the full existing ladder: `mise unit`, `mise integration` if available, and `mise e2e` when applicable.

Source: `specs/DeviaTDD-architecture.md`, §2.2:

> A closing sweep is emitted only when a rung exists: user-facing + e2e → terminal `[E2E]` `Verification_Batch` whose Verification is the full existing ladder; else if integ exists → `[VERIFY]` unit-if-exists + integ; else no extra sweep.

The E2E prompt also labels `Verification_Batch` as test-authoring work.

Source: `src/deviate/prompts/commands/deviate-e2e.md`, `STEP_6`:

> 2. Tasks whose **Type** is `Verification_Batch` (the E2E-authoring task).

These excerpts record distinct current contracts. This scan leaves adjudication to `/research`.

## Constitution Quotes

This artifact preserves §1 phase separation through discovery-only output. It records §2, §3, and §5 constraints for later phases.

Source: `specs/constitution.md`.

- **Architectural Principles**, §1:

> - **User Scenarios Are the Flow**: RED must encode the issue's user scenarios (User Stories + ATDD on the shard issue) as failing tests before GREEN. GREEN still cannot edit tests. After COMPLETED, those tests *are* the flow.
> - **Git Isolation Principle**: Every task loop executes on a clean git branch or worktree. Commits are automatic at each phase boundary.

- **Tech Stack Standards**, §2:

> - Python 3.13
> - Target: CLI application (`deviate`)
> - Framework: Typer (CLI entry points) with Rich for terminal I/O

> - No persistent database runtime (all state tracked in JSONL ledgers and TOML config)
> - Session state: JSON files under `.deviate/`
> - Issue ledger: `specs/issues.jsonl` (append-only JSONL)
> - Task ledger: `specs/**/tasks.jsonl` (append-only JSONL)
> - Config: TOML via `.deviate/config.toml`; `[models]` section for per-phase model assignment

- **Testing Protocols**, §3:

> - Test framework: pytest
> - Test root: `tests/`
> - Test extension: `.py`
> - Test command: `pytest tests/ -v`
> - Lint command: `ruff check .`
> - E2E command: `bats tests/e2e/`

> - Coverage target: >= 80%
> - GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files
> - REFACTOR phase runs regression gate: tests must re-pass after polish

- **Definition of Done**, §5:

> - [ ] Code implemented (satisfies assigned `AC-PLAN-NNN` scenarios from `plan.md`)
> - [ ] Tests passing (pytest with clean exit code 0)
> - [ ] Lint passing (ruff check with no violations)
> - [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)
> - [ ] E2E tests passing (if applicable; bats for CLI integration)

## Architectural Baselines

### Existing Architectural Patterns

The existing parser recognizes `Verification_Batch` and forces `IMMEDIATE`. Registry entries anchor `resolve_execution_mode` and `_build_task_record`.

`_TaskBlock.task_type` holds the parsed type. `_build_task_record` receives the resolved mode, rather than the type. `TaskRecord` forbids extra fields.

Source: `src/deviate/core/tasks_ledger.py`:

```python
            execution_mode=resolve_execution_mode(
                block.task_type, block.execution_mode
            ),
            test_strategy=block.test_strategy,
            criteria_entries=block.criteria_entries,
```

The shared dispatch routes TDD separately. Every other mode enters `_run_execute_phase`, as the registry shows.

The existing direct prompt explicitly permits implementation and repair.

Source: `src/deviate/prompts/auto/execute.md`:

> 1. Implement the task using minimal, focused modifications

> 6. Run lint to ensure code quality:

`_run_execute_phase` stages deliverables and creates an implementation commit. It also contains JUDGE and rollback paths.

Source: `src/deviate/cli/micro.py`, `_run_execute_phase`:

```python
        subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)

        _commit_phase_with_recovery(
            f"feat({scope}): EXECUTE phase - {tid}",
```

The proposal's dedicated read-only checkpoint differs from this existing direct execution path.

Source: proposal §9: “modifies no code”; “does not enter RED/GREEN”.

### Infrastructure & Operations

Initialization already preserves existing named Mise commands when adding missing tasks. The registry quotes `_merge_mise_toml`.

Initialization also provisions integration support, doctor checks, and test reset instructions.

Source: `src/deviate/prompts/commands/deviate-init.md`:

> - `setup:integration` — provisioning for the integration layer (test databases, services, `.env.instance`). Runs on worktree create when defined. Add when the project needs integration tests.

Source: `src/deviate/cli/init.py`, `_named_mise_tasks`:

```python
        "test": "mise run test:unit",
        "test:unit": "mise run unit",
        "test:integration": "mise run unit && mise run integration",
        "doctor:unit": unit_check,
        "doctor:integration": integration_check,
```

### Data & State Management

`TaskRecord.status` enumerates the existing TDD states, `COMPLETED`, and `FAILED`. Its enumeration appears in the registry.

`HandoverManifest` already provides phase, status, rationale, task identity, and parse-error handling. Its existing failure classifications describe TDD failures.

Source: `src/deviate/core/agent.py`:

```python
    failure_kind: Literal["mechanical", "test_defect", "already_satisfied"] | None = (
        None
    )
```

The proposal's `CHECKPOINT_STARTED`, `CHECKPOINT_FAILED`, and diagnostic classifications are proposed extensions, rather than current model values.

Source: proposal §20: “T004 CHECKPOINT_STARTED”; “T004 CHECKPOINT_FAILED”.

### Quality, Safety & Observability

The queue already halts when a task fails.

Source: `src/deviate/cli/micro.py`, `_run_all`:

```python
                    any_failed = True
                    c.print(
                        "[red]Pipeline halted: task failure breaks dependency chain[/]"
                    )
                    monitor.push_event(
                        "pipeline_halted",
                        task_id=task.get("id", "?"),
                    )
                    break
```

Repository command execution already has a security boundary.

Source: `src/deviate/cli/_safe_commands.py`:

> This module replaces that boundary with a strict allowlist. Every test
> command must:

> 1. Tokenise via :func:`shlex.split` so quoted paths land as a single argv.

Existing unit tests cover the type-to-mode lock, initialization merging, and prompt routing. Registry entries name those tests.

### External Integrations

The implementation invokes an agent backend through `_invoke_agent`. The direct path resolves a phase model.

Source: `src/deviate/cli/micro.py`, `_run_execute_phase`:

```python
    execute_model = resolve_model_for_phase("EXECUTE", root, backend=backend)
```

Existing verification discovery exposes named test layers to Tasks.

Source: `src/deviate/cli/meso.py`, `_tasks_pre`:

```python
        "verification_suites": existing_verification_suites(repo_root),
```

The discovered suite function enumerates `unit`, `integration`, and `e2e`. Its current contract differs from the proposal's feature-specific runtime capabilities.

Source: `src/deviate/cli/micro.py`:

```python
def existing_verification_suites(root: Path) -> list[str]:
    """Product-named rungs that exist (``unit``, ``integration``, ``e2e``)."""
```

## Sibling Flow Inventory

The nearest existing flow is direct task execution through `_dispatch_task` and `_run_execute_phase`.

| Dimension | Observed fact | Path |
| :--- | :--- | :--- |
| Amount vs fee | None observed in the task model: `description: str = Field(min_length=1)` | `src/deviate/state/ledger.py`, `TaskRecord` |
| Lock vs reserve | TDD branch verification: `_verify_worktree_branch(root)`; inventory covers workflow isolation rather than financial reservation | `src/deviate/cli/micro.py`, `_run_tdd_cycle_impl` |
| Vendor call | Agent invocation inside CLI execution: `manifest, agent_tail = _invoke_agent(` | `src/deviate/cli/micro.py`, `_run_execute_phase` |
| Idempotency | TDD completed-task guard: `if _phase_already_done(ledger_path, tid, "COMPLETED"):` | `src/deviate/cli/micro.py`, `_run_tdd_cycle_impl` |
| Destination shape | Structured result: `class HandoverManifest(BaseModel):` | `src/deviate/core/agent.py` |

## Ecosystem Research

Catalog only. These rows describe available tooling rather than required components.

Local lookup: `libref` lists `mise@main` and `uv@0.12.9`. Mise queries returned empty results. Official web documentation supplies the excerpts below.

Source for all three entries: https://mise.jdx.dev/cli/tasks/ls.html, retrieved 2026-09-10; unpinned current documentation.

- **Best Practices**: Discovery has an explicitly read-only CLI interface. Quote: “**Effect:** read-only”.
- **Common Use Cases & Pitfalls**: Task discovery includes inherited definitions. Quote: “Tasks from all parent directories are merged into this list.”
- **Standard Tooling**: Machine output and local filtering exist. Quotes: “**`-J --json`** — Output in JSON format”; “**`-l --local`** — Only show non-global tasks”.

## File Registry

Every excerpt below copies source text. `<br>` separates source lines within table cells.

| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `pyproject.toml` | Manifest | CLI entry point | `[project.scripts]`<br>`deviate = "deviate.main:app"` |
| `pyproject.toml` | Build configuration | Build backend | `[build-system]`<br>`requires = ["hatchling"]`<br>`build-backend = "hatchling.build"` |
| `pyproject.toml` | Test configuration | Test root | `[tool.pytest.ini_options]`<br>`testpaths = ["tests"]` |
| `uv.lock` | Dependency lock | Python resolution | `version = 1`<br>`revision = 3`<br>`requires-python = ">=3.13"` |
| `mise.toml` | Task manifest | Tool selection | `[tools]`<br>`python = "3.13"`<br>`uv = "latest"` |
| `.github/workflows/ci.yml` | CI | Test execution | `        run: uv run pytest --testmon-noselect tests/` |
| `.githooks/pre-commit` | Hook | Python validation | `uv run ruff check "${changed[@]}"`<br>`uv run ruff format --check "${changed[@]}"` |
| `src/deviate/core/tasks_ledger.py` | Parser | Verification type lock | `IMMEDIATE_TASK_TYPES = frozenset({"Verification_Batch"})` |
| `src/deviate/core/tasks_ledger.py` | Parser | Persist resolved mode | `        status="PENDING",`<br>`        execution_mode=execution_mode,` |
| `src/deviate/state/ledger.py` | Model | Task status vocabulary | `    status: Literal[`<br>`        "PENDING",`<br>`        "RED",`<br>`        "GREEN",`<br>`        "JUDGE",`<br>`        "REFACTOR",`<br>`        "COMPLETED",`<br>`        "FAILED",`<br>`    ] = "PENDING"` |
| `src/deviate/core/agent.py` | Model | Handover schema | `class HandoverManifest(BaseModel):`<br>`    phase: str = "UNKNOWN"`<br>`    status: str = "UNKNOWN"`<br>`    task_id: str \| None = None` |
| `src/deviate/cli/micro.py` | Runtime | Shared direct dispatch | `    else:`<br>`        _run_execute_phase(task, ledger_path, c, agent=agent, monitor=monitor)` |
| `src/deviate/cli/meso.py` | CLI | Tasks discovery input | `        "verification_suites": existing_verification_suites(repo_root),` |
| `src/deviate/cli/init.py` | Scaffolder | Preserve named tasks | `    existing = _mise_task_names(content)`<br>`    additions = [`<br>`        _render_named_task(name, run)`<br>`        for name, run in named.items()`<br>`        if name not in existing`<br>`    ]` |
| `src/deviate/cli/_safe_commands.py` | Security | Command timeout result | `TEST_TIMEOUT_EXIT_CODE: int = 124` |
| `src/deviate/prompts/assembly.py` | Prompt assembly | Existing Micro phases | `    "red": "micro",`<br>`    "green": "micro",`<br>`    "refactor": "micro",`<br>`    "judge": "micro",`<br>`    "execute": "micro",` |
| `src/deviate/prompts/auto/execute.md` | Prompt | Direct implementation instruction | `1. Implement the task using minimal, focused modifications` |
| `src/deviate/prompts/auto/tasks.md` | Prompt | Application target rule | `7. **Consumer Implementation Audit**: Every task MUST have at least one application implementation or application verification target tied to a named story and \`AC-PLAN-NNN\`. A task whose primary target is DeviaTDD setup, an agent skill, a slash command, a catalog file, release scaffolding, or a workflow ledger is invalid; halt with \`META_WORK_NOT_ALLOWED\`.` |
| `src/deviate/prompts/commands/deviate-init.md` | Prompt | Existing governance ownership | `4. Symlink \`AGENTS.md\` ↔ \`CLAUDE.md\` (via \`_linkify_governance_files\`)` |
| `tests/unit/test_core/test_tasks_ledger.py` | Unit tests | Verification mode regression | `        assert resolve_execution_mode("Verification_Batch", "TDD") == "IMMEDIATE"` |
| `tests/unit/test_meso/test_auto_prompt_templates.py` | Prompt tests | Type-lock coverage | `class TestVerificationBatchImmediateRouting:` |
| `tests/unit/test_cli/test_init_mise.py` | Init tests | Existing Mise merge coverage | `def test_existing_mise_without_named_tasks_adds_unit_and_integration(` |
| `specs/constitution.md` | Governance | Test coverage target | `- Coverage target: >= 80%` |

## Scope Sizing

Estimates describe the supplied proposal's breadth, rather than an implementation design.

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | High |
| Files Likely Modified | At least 12 surfaces: `src/deviate/cli/micro.py`, `src/deviate/cli/init.py`, `src/deviate/cli/meso.py`, `src/deviate/core/tasks_ledger.py`, `src/deviate/core/agent.py`, `src/deviate/state/ledger.py`, `src/deviate/prompts/assembly.py`, `src/deviate/prompts/auto/tasks.md`, `src/deviate/prompts/commands/deviate-init.md`, `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`; registry anchors existing execution surfaces; proposal §§13–18 and §§28–34 name requested changes |
| New Modules Required | Yes — proposed `src/deviate/prompts/auto/checkpoint.md` resource; proposal §16: “Add: src/deviate/prompts/auto/checkpoint.md” |
| New Persistence / Data Models | Yes — existing model extensions in proposal §17: “Prefer extending the existing Pydantic handover model”; current models appear above |
| New External Integrations | Yes — repository runtime verification commands; proposal §24: “verify verify:<feature>”; proposal §3 retains product-independent discovery |
| Upstream / Cross-Cutting Concerns | Parsing, queue dispatch, command safety, failure evidence, initialization, and prompt composition; registry anchors each current surface |
| Rationale | Current `Verification_Batch` resolves to general direct execution. The proposal adds dedicated verification semantics across the existing parser, runtime, and handover models. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | repository-capability-checkpoints |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/repository-capability-checkpoints.md |
| NEXT_ACTION | Run `/deviate-research` after human review; High complexity |

Discovery limitations: semantic search returned `INDEX_MISSING`; exact `zg query --rg` searches supplied source locations. Subagent tools were unavailable. This scan used one read-only discovery pass and one artifact write. Design approval remains with the human gate.

## Related Epic Candidates

None observed in the bounded exact search of existing `*prd.md` and `*design.md` artifacts.

Search terms: `Verification_Batch`, `runtime verification`, and `capability discovery`. Search result: `No matches`.

Contract anchor: `"feature_slug":"repository-capability-checkpoints"`. The allocated target remains `specs/explore/repository-capability-checkpoints.md`.
