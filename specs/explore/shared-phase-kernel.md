# Shared Phase Kernel (Auto Runner ⇄ Manual Pre/Post) — Exploration

## Problem Definition

[Statement]: Catalog what currently exists for the four micro phases (RED, GREEN, JUDGE, REFACTOR) along two execution surfaces: the in-process auto runner (`src/deviate/cli/micro.py::_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`) and the manual CLI commands (`deviate red|green|judge|refactor pre|post`). The problem space is the duplication between these surfaces: both implement pre-contract assembly, post side effects (test run, ledger transition, session save, phase commit), and the JUDGE verdict application, as separate copies. The candidate consolidation is one kernel function per phase step — pre-contract, prompt assembly, agent invocation, post side effects — called by both surfaces.

[Scope]: In-scope structural components verified across the scan:

- **The four `_run_*_phase` orchestrators** — `_run_red_phase` at `src/deviate/cli/micro.py:1633-1756`, `_run_green_phase` at `:1904`, `_run_judge_phase` at `:3309` (returns `_apply_judge_verdict(...)` at `:3396`), `_run_refactor_phase` at `:3823`.
- **The eight manual CLI pre/post commands** — `red_pre` (`:5914`), `red_post` (`:6571`), `green_pre` (`:6664`), `green_post` (`:6703`), `judge_pre` (`:6818`), `judge_post` (`:6892`), `refactor_pre` (`:6965`), `refactor_post` (`:7077`). All are Typer commands in `src/deviate/cli/micro.py`.
- **The verdict kernel already shared** — `_apply_judge_verdict` at `src/deviate/cli/micro.py:3410` is the single verdict application path; `_run_judge_phase` and `judge_post` both call it.
- **Prompt assembly** — `_build_auto_prompt` at `src/deviate/cli/micro.py:1383` fills `{task_content}` and `{train_feedback}` placeholders from `src/deviate/prompts/auto/{phase}.md`; layer preamble routing lives in `src/deviate/prompts/assembly.py::_LAYER_MAP` (`red`/`green`/`refactor`/`judge`/`execute` → `"micro"`).
- **Manual prompt derivation already shared** — `src/deviate/core/commands.py:185-194` (`_manual_phase`) maps the 11 overlapping phases to `auto/{phase}.md`; `_derive_manual_body` splices the auto core byte-identically at install time. The prompt TEXT is single-source; the runtime CONTRACT (pre) and SIDE EFFECTS (post) are the duplication target.
- **Auto prompt templates** — `src/deviate/prompts/auto/red.md`, `green.md`, `judge.md`, `refactor.md` (exist on disk; also `execute.md` and the macro/meso templates).
- **Tests touching these seams** — `tests/test_micro/test_red.py` (GH-154 AC-6 `deviate red post --task-id`), `tests/test_micro/test_judge.py` (manual `deviate judge post`), `tests/test_micro/test_cycle_driver.py`, `tests/test_meso/test_prompt_assembly.py` (asserts `deviate red pre` in the RED template retry contract).

[Exclusions]: Design decisions (which kernel signature, module placement, which contract fields are shared vs surface-specific — deferred to `/research`); implementation code, tests, config files, or scripts; the macro/meso `pre`/`post` cycle driver (`src/deviate/cli/macro.py::_cycle_phase:1081-1126`); E2E hardening for manual flows (the scan found no bats coverage asserting `deviate red pre|post` — observed only); any change to the append-only ledger protocol, session state shape, or HITL gates.

## Discovery Audit Results

### Verified Dependencies
- `typer>=0.12`: declared in `pyproject.toml:30-34`; all eight manual pre/post commands are `@*_app.command` Typer entry points in `src/deviate/cli/micro.py`. Application entry: `deviate = "deviate.main:app"` at `pyproject.toml:38`.
- `rich>=13.0`: used by `console.print` status tokens (`TEST_NOT_FOUND`, `RED_POST_OK`, `GREEN_POST_OK`, `JUDGE_POST_OK`, `REFACTOR_POST_OK`) and `_emit_phase_callout`.
- `pydantic>=2.0`: `TaskRecord.model_validate` drives ledger transitions in both `_run_red_phase` and `red_post`.
- `pyyaml>=6.0.3`: JUDGE handover YAML parsing via `AgentBackend.parse_output(yaml_text, "cli")` in `judge_post`.
- Python 3.13 stdlib: `subprocess` (test/format/`git rev-parse` runs), `json` (contract printing), `tomllib` (`_mise_defined_tasks`), `datetime` (contract timestamps).

### Ghost Dependencies
- None observed in the scanned micro-layer surface. No import in `src/deviate/cli/micro.py`, `src/deviate/core/commands.py`, or `src/deviate/prompts/assembly.py` lacks a manifest or stdlib declaration.

### Manifest Files Observed
- `pyproject.toml`: project metadata, 4 runtime dependencies, `[project.scripts] deviate = "deviate.main:app"`.
- `mise.toml`: `[tasks.test]` = `uv run pytest --testmon-noselect tests/ -v`; `[tasks.test-e2e]` = `bats tests/e2e/`; `[tasks.test-affected]` (pytest-testmon selection).
- `uv.lock`: present at repo root (not read; lockfile).
- `src/deviate/prompts/assembly.py`: `_LAYER_MAP` (layer routing manifest for 11 phases) and `_AUTO_DIR = "deviate.prompts.auto"`.

### Test Runner Configuration
- `mise run test` → `uv run pytest --testmon-noselect tests/ -v`. Test root `tests/`; micro-layer tests in `tests/test_micro/` (18 files incl. `test_red.py`, `test_green.py`, `test_judge.py`, `test_refactor.py`, `test_cycle_driver.py`); prompt tests in `tests/test_meso/test_prompt_assembly.py` and `tests/test_meso/test_auto_prompt_templates.py`.
- AGENTS.md performance rule: tests that reach `_run_pytest` (`src/deviate/cli/micro.py:5315`, invoked from `refactor_post:7114`) MUST mock `deviate.cli.micro._run_pytest` with a `CompletedProcess` fixture. This constraint applies to any new kernel-level tests.
- Git isolation fixtures: `tests/conftest.py` (`_git_env`, `tmp_git_repo`).

### Manifest-Constitution Divergence
- None observed between `pyproject.toml` / `mise.toml` and `specs/constitution.md` §2 (Tooling: uv, pytest, ruff, bats, mise) or §3 (test command `pytest tests/ -v`).

## Constitution Quotes

- **Architectural Principles**: "- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR). Macro PRD/shard/adhoc artifacts carry User Stories plus ATDD acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract. The three layers have strict phase gates — no layer may be skipped. (Gate 2 was removed: there is no human-approval step between Tasks and Micro — the system auto-advances.) There is no Product layer, flow catalog, or `flow_refs` pointer."
- **Tech Stack Standards**: "### Backend\n- Python 3.13\n- Target: CLI application (`deviate`)\n- Framework: Typer (CLI entry points) with Rich for terminal I/O" and "### Tooling\n- Package manager: `uv`\n- Test runner: `pytest`\n- Linter: `ruff` (lint + format)\n- E2E testing: `bats` (Bash automated test system)\n- Task runner: `mise` (see `mise.toml` for all tasks)\n- Code quality gate: `mise run check`"
- **Testing Protocols**: "### Framework\n- Test framework: pytest\n- Test root: `tests/`\n- Test extension: `.py`\n- Test command: `pytest tests/ -v`\n- Lint command: `ruff check .`\n- E2E command: `bats tests/e2e/`" and "### Coverage\n- Coverage target: >= 80%\n- GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files\n- REFACTOR phase runs regression gate: tests must re-pass after polish"
- **Definition of Done**: "- [ ] Code implemented (satisfies assigned `AC-PLAN-NNN` scenarios from `plan.md`)\n- [ ] Tests passing (pytest with clean exit code 0)\n- [ ] Lint passing (ruff check with no violations)\n- [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract)\n- [ ] E2E tests passing (if applicable; bats for CLI integration)\n- [ ] Documentation updated (`plan.md` Acceptance Contract, `spec.md`, and `design.md` reflect final implementation; `explore.md` lives at `specs/{NNN}-<slug>/explore.md` after `deviate research pre`, alongside design and data-model artifacts)\n- [ ] CHANGELOG.md updated under `[Unreleased]` for user-visible changes (new commands/flags, behavior changes, user-affecting bug fixes, breaking changes, new user-visible dependencies); docs-only, test-only, CI/tooling, and behavior-preserving refactors are exempt\n- [ ] No governance violations (constitution rules upheld, no remaining HITL gates bypassed; Gate 2 was removed)\n- [ ] Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)"

## Architectural Baselines

- **Existing Architectural Patterns**: Two parallel micro-phase execution surfaces share sub-helpers but keep separate orchestration. `_run_red_phase` calls `_build_auto_prompt("red", task, root, train_feedback=session.train_feedback)` → `_invoke_agent(...)` → `_run_test_cmd` → `append_task_transition(record with status "RED")` → `session.force_transition_to("RED")` → `_commit_phase(f"test({scope}): RED phase - failing test", ...)` → `session.red_commit_sha`. `red_post` independently runs `_run_test_cmd` → `_run_format_cmd` → `append_task_transition(record.status = "RED")` → `session.force_transition_to("RED")` → `_commit_phase` with the same message format → `session.red_commit_sha`. JUDGE is the one phase whose side effects already converge: `_run_judge_phase` ends with `return _apply_judge_verdict(task, ledger_path, session, session_path, c, manifest, injected_diff=...)` and `judge_post` calls the same `_apply_judge_verdict` with an injected diff from `_assemble_judge_injected_diff`. RED also carries an in-process adjudication branch `_adjudicate_red_no_failing_test` (exit 0 / pytest exit 5 / command-not-found exit 127 routes) that has no CLI-post counterpart.

```python
def _run_red_phase(
    task: dict,
    ledger_path: Path,
    session: SessionState,
    session_path: Path,
    c: Console,
```

```python
    try:
        record = TaskRecord.model_validate(pending_record)
        record.status = "RED"  # type: ignore[assignment]
        append_task_transition(record, ledger_path)
    except Exception as e:
        console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")
        raise typer.Exit(code=1)
```

- **Infrastructure & Operations**: Manual pre commands emit a JSON contract on stdout and fail fast on doctor issues. `red_pre` builds `{"task_id", "test_command", "lint_command": "mise run lint", "spec_dir", "task_entry"}` plus `_attach_mise_pre(root, contract)` doctor fields, then `print(json.dumps(contract, ensure_ascii=False))` and `_fail_pre_if_doctor_failed(doctor)`. `refactor_pre` emits a larger contract (`status: READY`, `task_title`, `task_type`, `verification`, `repo_root`, `git_branch`, `timestamp`, `files_to_refactor`). `judge_post` accepts a handover manifest path argument or stdin. The auto runner builds its own context in-process (`_build_auto_prompt`, `_resolve_verification_command`, `_task_card_text`) and never reads these printed contracts.

```python
    contract = {
        "task_id": task_data.get("id", ""),
        "test_command": _resolve_verification_command(root, task_data),
        "lint_command": "mise run lint",
        "spec_dir": spec_dir,
        "task_entry": _task_card_text(root, task_data),
    }
    doctor = _attach_mise_pre(root, contract)
    print(json.dumps(contract, ensure_ascii=False))
```

- **Data & State Management**: All phase state is append-only JSONL plus session JSON — no database. Ledger transition: `TaskRecord.model_validate(task)` → `record.status = "RED"|"GREEN"|"COMPLETED"` → `append_task_transition(record, ledger_path)`. Session: `SessionState.force_transition_to(...)` → `session.save(session_path)` under `.deviate/session.json`; `session.red_commit_sha` is persisted after `git rev-parse HEAD`. Task resolution helpers: `_resolve_task_context` (manual pre), `_resolve_first_pending` + `--task-id` match (red_post), `_resolve_judge_post_task` (judge_post: explicit task_id → latest GREEN → latest JUDGE).

```python
    session = session.force_transition_to("RED")
    session.save(session_path)
    scope = _build_scope(issue_id, task_uuid)
    _commit_phase(
        f"test({scope}): RED phase - failing test",
        root,
        no_verify=True,
        phase="red",
    )
```

- **Quality, Safety & Observability**: Safety filters guard every command path — `is_safe_test_command` is applied in `_task_verification_command`, `_constitution_test_command`, and again in the execution layer `run_safe_command`. Test classification (`_is_no_tests_collected` for pytest exit 5, `_is_no_test_command` for exit 127) routes the auto RED no-failing-test case to JUDGE adjudication. Observability: `_log_run("PHASE_START", task_id=tid, phase="RED")`, `_emit_phase_callout`, `OrchestrationMonitor` via `_make_agent_output_callback(monitor, tid, "RED")`. The manual post commands print fixed Rich status tokens (`RED_POST_OK`, `GREEN_POST_OK`, `JUDGE_POST_OK route=...`, `REFACTOR_POST_OK`) that the prompt `retry contracts` reference (`tests/test_meso/test_prompt_assembly.py:70` asserts `deviate red pre` appears in the RED template).

```python
def _is_no_test_command(proc: subprocess.CompletedProcess) -> bool:
    """Return whether the test command could not be resolved.

    ``_run_test_cmd`` returns ``returncode == 127`` with a fixed
    diagnostic when no command configures and no project is detected,
```

- **External Integrations**: Agent backends invoked through `_invoke_agent(prompt, c, backend_name=backend, task_id=tid, phase="RED", output_callback=..., model=red_model)` (`src/deviate/cli/micro.py:550-565`) with `resolve_model_for_phase("RED", root, backend=backend)` per constitution §1 model routing. JUDGE handover YAML parsed by `AgentBackend.parse_output(yaml_text, "cli")`. The manual path has no agent invocation — the human's agent acts on the prompt; the CLI only supplies contract (pre) and applies side effects (post).

```python
def _invoke_agent(
    prompt: str,
    c: Console,
    backend_name: str = "pi",
    task_id: str = "",
    phase: str = "",
```

## Ecosystem Research

- **Best Practices**: CLI thin wrappers over library functions are the standard consolidation shape — the CLI layer holds only argument parsing, output printing, and exit codes, while a library module owns behavior. Stack Overflow's "API wrapper library" pattern states it directly: "If you want to support additional configurations that differ between endpoints ... that's where you use composition" — surface-specific options compose on top of one shared core. (source: stackoverflow.com/q/63552828 "Design pattern - Writing an API wrapper library").
- **Common Use Cases & Pitfalls**: Duplication appears when a tool offers both an interactive (agent/human-driven) path and an automated path — the two drift in status tokens, contract fields, and side effects. Agent-tooling write-ups note "slash commands are just prompt injection" — i.e., the prompt is data while the pre/post runtime must stay code, which is exactly the split the candidate kernel draws (jxnl.co "Slash Commands vs Subagents"). Codex CLI keeps one canonical wire schema for hook inputs/outputs, "schemas follow JSON Schema draft-07 ... source of truth for the wire format" (codex hooks guide), i.e. contract JSON emitted by `pre` is a versioned interface.
- **Standard Tooling**: Python/Typer projects expose this as `project.scripts` entry points wrapping internal functions (the repo already does: `deviate = "deviate.main:app"`). Exit-code-bearing helper functions (return contract dict / raise domain errors, CLI maps them to `typer.Exit`) are the observed Typer convention.

## File Registry

| Path | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/cli/micro.py` | py | Micro-layer CLI: 4 auto `_run_*_phase` orchestrators + 8 manual pre/post commands (7566 lines) | `def _run_red_phase(\n    task: dict,\n    ledger_path: Path,\n    session: SessionState,\n    session_path: Path,\n    c: Console,\n    agent: str \| None = None,\n    monitor: OrchestrationMonitor \| None = None,` |
| `src/deviate/cli/micro.py` | py | `red_pre` — manual RED contract (task_id, test_command, lint_command, spec_dir, task_entry + mise doctor) | `    contract = {\n        "task_id": task_data.get("id", ""),\n        "test_command": _resolve_verification_command(root, task_data),\n        "lint_command": "mise run lint",\n        "spec_dir": spec_dir,\n        "task_entry": _task_card_text(root, task_data),\n    }` |
| `src/deviate/cli/micro.py` | py | `red_post` — manual RED side effects (test run, ledger RED transition, commit, sha persist) | `    try:\n        record = TaskRecord.model_validate(pending_record)\n        record.status = "RED"  # type: ignore[assignment]\n        append_task_transition(record, ledger_path)\n    except Exception as e:\n        console.print(f"[red]LEDGER_UPDATE_FAILED[/] {e}")\n        raise typer.Exit(code=1)` |
| `src/deviate/cli/micro.py` | py | `_apply_judge_verdict:3410` — already-shared verdict kernel used by both auto and manual JUDGE | `def _apply_judge_verdict(\n    task: dict,\n    ledger_path: Path,\n    session: SessionState,\n    session_path: Path,\n    c: Console,\n    manifest: HandoverManifest,\n    injected_diff: str,` |
| `src/deviate/cli/micro.py` | py | `_build_auto_prompt:1383` — in-process prompt assembly from `auto/{phase}.md` placeholders | `def _build_auto_prompt(\n    phase: str,\n    task: dict,\n    root: Path,\n    *,\n    train_feedback: str = "",\n) -> str:` |
| `src/deviate/cli/micro.py` | py | `_invoke_agent:550` — shared agent invocation (backend, model, phase, monitor callback) | `def _invoke_agent(\n    prompt: str,\n    c: Console,\n    backend_name: str = "pi",\n    task_id: str = "",\n    phase: str = "",\n    output_callback: Callable[[str], None] \| None = None,\n    model: str \| None = None,` |
| `src/deviate/core/commands.py` | py | Manual slash-command derivation — auto core spliced byte-identically into manual bodies | `    phase = _manual_phase(name)\n    if phase is None:\n        return raw\n    auto_body = _read_auto_body(phase)\n    if auto_body is None:\n        return None\n    fm_match = _YAML_FM_RE.match(raw)` |
| `src/deviate/prompts/assembly.py` | py | Layer routing manifest — micro phases share the `"micro"` preamble | `    # Micro layer — shared preamble\n    "red": "micro",\n    "green": "micro",\n    "refactor": "micro",\n    "judge": "micro",\n    "execute": "micro",\n}` |
| `src/deviate/prompts/auto/red.md` | md | Canonical RED prompt core used by auto runner and (via splice) manual command | (file resource; loaded by `_read_auto_body` in `src/deviate/core/commands.py`) — referenced verbatim in `tests/test_meso/test_prompt_assembly.py`: `for marker in ("Retry Contract", "deviate red pre"):` |
| `pyproject.toml` | toml | Project manifest — 4 runtime deps, CLI entry point | `requires-python = ">=3.13"\ndependencies = [\n    "typer>=0.12",\n    "rich>=13.0",\n    "pydantic>=2.0",\n    "pyyaml>=6.0.3",\n]` |
| `mise.toml` | toml | Task runner definitions — test and E2E commands | `[tasks.test]\nrun = "uv run pytest --testmon-noselect tests/ -v"` |
| `tests/test_micro/test_red.py` | py | GH-154 AC-6: manual `deviate red post --task-id` matches pending record | `    """GH-154 AC-6: ``deviate red post --task-id`` matches the pending record."""` |
| `tests/test_micro/test_judge.py` | py | Manual judge post applies auto-mode verdict side effects | `    """Manual ``deviate judge post`` applies auto-mode JUDGE side effects."""` |
| `specs/constitution.md` | md | Governance: 3-layer architecture, model routing, testing protocols (v0.10.0) | `- **Three-Layer Architecture**: Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR).` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 3-5: `src/deviate/cli/micro.py` (extract kernels, thin the 8 CLI commands), `src/deviate/cli/macro.py` (if the meso `_cycle_phase` reuses the same seam — verify at research), plus `tests/test_micro/*` and `CHANGELOG.md` (behavior-adjacent refactor: verify exemption or add bullet) |
| New Modules Required | No — kernels extract into the existing `src/deviate/cli/micro.py` (or an adjacent core module already in the package) |
| New Persistence / Data Models | No — `issues.jsonl` / `tasks.jsonl` / `session.json` shapes unchanged (constitution §1 Append-Only Ledger Protocol holds) |
| New External Integrations | No — same agent backends via `_invoke_agent` |
| Upstream / Cross-Cutting Concerns | Status-token and exit-code contract (`*_POST_OK`, `TEST_NOT_FOUND`, `LEDGER_UPDATE_FAILED`) is consumed by prompt `retry contracts` in `src/deviate/prompts/auto/*.md` and asserted in `tests/test_meso/test_prompt_assembly.py:70`; contract JSON emitted by `pre` commands is an installed interface for external agents. Kernel extraction must keep both stable or update prompts + tests in the same change. |
| Rationale | The change is a behavior-preserving consolidation inside one module plus test updates: 8 CLI commands become thin wrappers over 2 kernel steps per phase, reusing the existing `_apply_judge_verdict` seam as the template. No new modules, persistence, or integrations; the cross-cutting concern is the status-token/contract surface shared with prompts. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | shared-phase-kernel |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/shared-phase-kernel.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Medium complexity) — see `## Scope Sizing` |
