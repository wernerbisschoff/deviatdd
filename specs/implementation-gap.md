# Implementation Gap: DeviaTDD Docs → Code Alignment

> **Generated**: 2026-06-10
> **Source Documents**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`
> **Reference**: `findings.md`, `src/deviate/`

---

## Priority Key

| Tag | Meaning |
|-----|---------|
| **P0** | Blocking — other work depends on this |
| **P1** | High — must ship in next release |
| **P2** | Medium — should ship soon |
| **P3** | Low — nice to have |

---

## 1. CLI: `--profile` replaces `--no-judge`/`--no-refactor` [P0]

**Spec says**: `deviate micro run <task-id> --profile [full|fast|secure]`
> (Top-level `deviate run` was promoted to a full-pipeline orchestrator that chains
> `deviate meso run` with `deviate micro run --all` inside the created worktree;
> see `DeviaTDD-api.md` §5 for the new contract. The per-task / `--all` dispatch
> surface lives at `deviate micro run`.)
**Code has**: `--no-judge` and `--no-refactor` booleans

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1.1 | Add `ExecutionProfile` dataclass to `src/deviate/state/config.py` (or `core/`): `full` = all phases, `fast` = RED+GREEN only, `secure` = RED+GREEN+JUDGE | `state/config.py` | |
| 1.2 | Replace `no_judge: bool, no_refactor: bool` params with `profile: ExecutionProfile` in `run_command()`, `_run_tdd_cycle()`, `_dispatch_task()`, `_run_single()`, `_run_all()` | `cli/micro.py` | |
| 1.3 | Map `--profile fast` → `no_judge=True, no_refactor=True`; `--profile secure` → `no_judge=False, no_refactor=True`; `--profile full` → defaults | `cli/micro.py` | |
| 1.4 | Add `--profile` to Typer option on `run_command()` with choices `["full", "fast", "secure"]` | `cli/micro.py` | |
| 1.5 | Remove `--no-judge` and `--no-refactor` from Typer options (or keep as deprecated hidden aliases) | `cli/micro.py` | |
| 1.6 | Update SKILL.md files that reference `--no-judge`/`--no-refactor`: `deviate-green`, `deviate-red`, `deviate-refactor`, `deviate-execute` | `src/deviate/prompts/skills/deviate-*/SKILL.md` | |
| 1.7 | Write tests for all three profiles | `tests/` | |

**Verify**: `deviate micro run TSK-001-01 --profile fast` skips JUDGE+REFACTOR; `--profile secure` runs JUDGE but skips REFACTOR; `--profile full` (default) runs all.

---

## 2. CLI: `deviate context pre/post` [P0]

**Spec says**: `deviate context pre` emits JSON contract; `deviate context post <manifest>` syncs CLAUDE.md and AGENTS.md; auto-triggered after macro/meso post commands.
**Code has**: No `deviate context` command exists. Only a SKILL.md that references `deviate context pre`.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 2.1 | Create `deviate context pre` command: directory crawl to find `.deviate/config.toml`, resolve git branch, derive feature slug, compute paths, emit JSON contract | `cli/__init__.py` or new `cli/context.py` | |
| 2.2 | Create `deviate context post <manifest>`: read manifest, find `## Technical Execution Context` in CLAUDE.md, replace block, enforce `AGENTS.md` → `CLAUDE.md` symlink via `ln -sf`, commit | `cli/__init__.py` or `cli/context.py` | |
| 2.3 | Add `--no-context-sync` flag to all macro/meso post commands (`explore post`, `research post`, `prd post`, `shard post`, `specify post`, `tasks post`, `adhoc post`) | `cli/macro.py`, `cli/meso.py` | |
| 2.4 | Wire auto-trigger: each post command calls `deviate context post` internally after its artifact commit (unless `--no-context-sync`) | `cli/macro.py`, `cli/meso.py` | |
| 2.5 | Register `context_app` Typer in `cli/__init__.py` and wire `pre`/`post` subcommands | `cli/__init__.py` | |
| 2.6 | Update `deviate-context` SKILL.md: remove `deviate context pre` invocation as a manual step (it's auto-triggered) | `src/deviate/prompts/skills/deviate-context/SKILL.md` | |
| 2.7 | Write tests: `test_context_pre`, `test_context_post`, `test_context_auto_trigger` | `tests/` | |

**Verify**: After `deviate explore post`, CLAUDE.md has updated `## Technical Execution Context` block; AGENTS.md → CLAUDE.md symlink exists.

---

## 3. CLI: `deviate adhoc pre/post` [P1]

**Spec says**: `deviate adhoc pre <task-description>` with complexity gate, `deviate adhoc post <manifest>` for ledger registration.
**Code has**: No `deviate adhoc` command. Only a SKILL.md.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 3.1 | Implement complexity gate: classify task as low/medium/high complexity based on file scope | `cli/macro.py` | |
| 3.2 | Create `deviate adhoc pre <task-description>`: complexity eval, proportional exploration contract, next `ADH-NNN` computation | `cli/macro.py` | |
| 3.3 | Create `deviate adhoc post <manifest>`: validate issue markdown, append to `specs/adhoc/prd.md`, register in `issues.jsonl` with `type: "adhoc"`, commit + context sync | `cli/macro.py` | |
| 3.4 | Ensure `specs/adhoc/` directory is auto-created on first use | `cli/macro.py` | |
| 3.5 | Update `deviate-adhoc` SKILL.md: reference `deviate adhoc pre/post` instead of direct filesystem operations | `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` | |
| 3.6 | Write tests: `test_adhoc_pre_low`, `test_adhoc_pre_medium`, `test_adhoc_pre_high_rejected`, `test_adhoc_post` | `tests/` | |

**Verify**: `deviate adhoc pre "fix typo" --json` emits contract; `deviate adhoc pre "rewrite auth system"` halts with `COMPLEXITY_GATE_REJECTION`.

---

## 4. CLI: `deviate feature create` [P1]

**Spec says**: `deviate feature create <title>` derives slug, creates branch/worktree, scaffolds `specs/{FEATURE_SLUG}/`, sets active workspace.
**Code has**: Rolled into `deviate specify pre` implicitly. No standalone command.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 4.1 | Extract `deviate feature create <title> [--slug]` as a standalone command: slug derivation, branch creation, directory scaffolding, session update | `cli/macro.py` | |
| 4.2 | Have `deviate specify pre` internally call `feature create` logic if no feature workspace exists | `cli/meso.py` | |
| 4.3 | Write tests: `test_feature_create_basic`, `test_feature_create_with_slug` | `tests/` | |

**Verify**: `deviate feature create "auth overhaul"` creates `specs/auth-overhaul/` and sets session.

---

## 5. CLI: `deviate constitution pre/post` [P2]

**Spec says**: `deviate constitution pre` validates constitution; `deviate constitution post` commits updates.
**Code has**: Constitution validation exists in `core/constitution.py` but no CLI endpoint.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 5.1 | Create `deviate constitution pre` that validates `specs/constitution.md` exists, extracts commands, emits JSON contract | `cli/__init__.py` | |
| 5.2 | Create `deviate constitution post <manifest>` that validates constitution sections, commits | `cli/__init__.py` | |
| 5.3 | Register `constitution_app` Typer | `cli/__init__.py` | |

**Verify**: `deviate constitution pre --json` emits test/lint/typecheck commands.

---

## 6. CLI: `deviate tasks list` & `deviate issues list` [P2]

**Spec says**: Two inspection commands for reading ledgers with `--json` output.
**Code has**: Neither exists.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 6.1 | `deviate tasks list [--type tdd|direct|e2e] [--status] [--json]`: parse active issue's `tasks.jsonl`, derive status, render table | `cli/micro.py` | |
| 6.2 | `deviate issues list [--type feature|adhoc] [--status] [--json]`: parse `issues.jsonl` bottom-up, render table | `cli/macro.py` | |
| 6.3 | Write tests: `test_tasks_list`, `test_issues_list` | `tests/` | |

**Verify**: `deviate issues list --json | jq` outputs valid parsed ledger data.

---

## 7. Cache Discipline Module [P1]

**Spec says**: `CacheDiscipline` class in `src/deviate/core/cache_discipline.py` enforcing 4 rules during micro loops.
**Code has**: No cache discipline enforcement.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 7.1 | Create `src/deviate/core/cache_discipline.py` with `CacheDiscipline` class: validates (1) no model switching, (2) no tool definition changes, (3) no system prompt mutation, (4) no read-only test file conversation append | `core/cache_discipline.py` | |
| 7.2 | Hook `CacheDiscipline.validate()` into `_run_tdd_cycle()` at phase boundaries | `cli/micro.py` | |
| 7.3 | Write tests: `test_cache_discipline_model_switch`, `test_cache_discipline_tool_change` | `tests/` | |

**Verify**: A test that simulates model switching mid-cycle triggers a `CacheDisciplineViolation`.

---

## 8. Train Rollback in JUDGE Phase [P1]

**Spec says**: On `COMPLIANCE_VIOLATION`, JUDGE does `git reset --hard HEAD~1`, preserves task states, injects `<judge_feedback>`, routes back to GREEN.
**Code has**: No rollback in `_run_judge_phase()` (micro.py:185-208) — only prints violation, no rollback.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 8.1 | In `_run_judge_phase()`: after detecting `COMPLIANCE_VIOLATION`, derive current task states from `tasks.jsonl` into memory | `cli/micro.py` | |
| 8.2 | Execute `git reset --hard HEAD~1` to wipe bad GREEN commit while preserving RED test | `cli/micro.py` | |
| 8.3 | Inject `<judge_feedback>` into session state for agent's next GREEN attempt | `cli/micro.py` | |
| 8.4 | Re-route task to GREEN phase (push back onto the run queue) | `cli/micro.py` | |
| 8.5 | Write tests: `test_judge_train_rollback`, `test_judge_train_rollback_preserves_red` | `tests/` | |

**Verify**: A task that triggers a compliance violation in JUDGE gets rolled back to the RED commit and re-enters GREEN with judge feedback.

---

## 9. `--json` / `--quiet` Flags on All `pre` Subcommands [P1]

**Spec says**: Every `pre` subcommand accepts `--json` (emit contract to stdout) and `--quiet` (suppress diagnostic output).
**Code has**: Neither flag on most commands.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 9.1 | Add `--json` and `--quiet` to `_common.py` as reusable Typer callback or decorator | `cli/_common.py` | |
| 9.2 | Wire `--json`/`--quiet` into all `pre` subcommands in `macro.py`, `meso.py`, `micro.py` | `cli/macro.py`, `cli/meso.py`, `cli/micro.py` | |
| 9.3 | When `--json` is passed, `pre` subcommands emit JSON contract to stdout; when `--quiet`, suppress rich console output (errors still go to stderr) | all cli modules | |
| 9.4 | Write tests: verify `--json` output is valid JSON, `--quiet` produces no stdout noise | `tests/` | |

**Verify**: `deviate explore pre "test" --json --quiet 2>/dev/null | jq .spec_target` works.

---

## 10. Placeholder Resolution Table in `deviate init` [P2]

**Spec says**: 6 variables resolved: `PROJECT_NAME`, `REPO_ROOT`, `TARGET_BACKEND_FRAMEWORK`, `TARGET_PACKAGE_MANAGER`, `TARGET_TEST_RUNNER`, `TARGET_COVERAGE_MINIMUM`.
**Code has**: Only `PROJECT_NAME` and `REPO_ROOT` in `_resolve_placeholder()` (__init__.py:88-108).

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 10.1 | Add framework detection: scan `pyproject.toml` dependencies (Django/FastAPI/Flask), `package.json`, `mix.exs` | `cli/__init__.py` | |
| 10.2 | Add package manager detection: check for `pyproject.toml` (uv/poetry), `package.json` (npm/yarn/pnpm), `Cargo.toml` | `cli/__init__.py` | |
| 10.3 | Add test runner detection: pytest, jest, go test, etc. | `cli/__init__.py` | |
| 10.4 | Add coverage minimum: default 80%, overridable via `.deviate/config.toml` | `cli/__init__.py` | |
| 10.5 | Write tests | `tests/` | |

---

## 11. AGENTS.md & CLAUDE.md Alignment [P1]

**Spec says**: Both files get `## DeviaTDD Orchestration Rules` block during `deviate init`; AGENTS.md → CLAUDE.md symlink enforced by `deviate context post`.
**Code has**: `deviate init` writes governance blocks to both (correct). AGENTS.md → CLAUDE.md symlink enforcement not yet in context flow.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 11.1 | In `deviate context post`: enforce `AGENTS.md` → `CLAUDE.md` symlink via `ln -sf` before block replacement | `cli/context.py` (new) | |
| 11.2 | Audit AGENTS.md for stale references: `deviate context`, `rgr run`, `manage-tasks.sh`, `sdd-parse-ast.sh`, `get-test-config.sh`, `.rgr/` | `AGENTS.md` | |
| 11.3 | Re-run `deviate init` to regenerate AGENTS.md with current governance seed | manual step | |

**Verify**: `grep -r "rgr run\|manage-tasks.sh\|sdd-parse" AGENTS.md` returns empty.

---

## 12. Action Logic in Skills [P2]

**Spec says**: Each slash command skill references explicit step sequences with numbered steps, calling `deviate <subcommand> pre/post`.
**Code has**: Skills exist in `src/deviate/prompts/skills/` but vary in completeness.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 12.1 | `/explore` skill: 6 steps (feature create, constitution validate, bucket allocate, codebase scan, write explore.md, commit + context sync) | `skills/deviate-explore/SKILL.md` | |
| 12.2 | `/research` skill: 5 steps (read explore.md, analyze options, produce design.md, produce data-model.md, commit + context sync) | `skills/deviate-research/SKILL.md` | |
| 12.3 | `/prd` skill: 4 steps (read design.md, synthesize requirements, write prd.md, commit + context sync) | `skills/deviate-prd/SKILL.md` | |
| 12.4 | `/shard` skill: 5 steps (read prd.md, identify vertical slices, validate granularity, create stubs, register in ledger) | `skills/deviate-shard/SKILL.md` | |
| 12.5 | `/specify` skill: 3 steps (claim issue + worktree, produce spec.md, validate + commit) | `skills/deviate-specify/SKILL.md` | |
| 12.6 | `/tasks` skill: 6 steps (resolve spec.md, decompose, assign execution modes, encode deps, append E2E task, validate + commit) | `skills/deviate-tasks/SKILL.md` | |
| 12.7 | Remove stale `<SKILL_DIR>/deviate-*.sh` references from all SKILL.md files; replace with `deviate <subcommand> pre/post` | all 18 SKILL.md files | |
| 12.8 | Remove `.sh` scripts from `src/deviate/prompts/skills/` directories | 15 skill directories | |

---

## 13. `tasks.md` vs `tasks.jsonl` Separation [P1]

**Spec says**: `tasks.md` = human-authored what/why/how; `tasks.jsonl` = CLI-managed append-only event ledger.
**Code has**: `deviate tasks post` treats `tasks.md` as the only artifact. No `tasks.jsonl` generation during tasks post.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 13.1 | In `deviate tasks post`: after validating tasks.md, parse task entries and write corresponding `PENDING` rows to `tasks.jsonl` | `cli/meso.py` | |
| 13.2 | Ensure no agent or skill writes to `tasks.jsonl` directly — only the CLI appends via `append_task_transition()` | all skills, `cli/micro.py` | |
| 13.3 | Add validator assertion: if `tasks.jsonl` is missing but `tasks.md` is committed, the CLI should generate initial `tasks.jsonl` from `tasks.md` | `cli/micro.py` or `core/validation.py` | |
| 13.4 | Write tests | `tests/` | |

---

## 14. `deviate init` Placeholder Work in constitution_seed.md [P3]

**Spec says**: 6 `${VARIABLE}` placeholders in constitution seed.
**Code has**: Need to verify `src/deviate/prompts/constitution_seed.md` actually uses all 6 variables.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 14.1 | Audit `constitution_seed.md` for all 6 variable placeholders | `src/deviate/prompts/constitution_seed.md` | |
| 14.2 | If any are missing, add them with appropriate surrounding context | `src/deviate/prompts/constitution_seed.md` | |

---

## 15. DeepSeek V4 Pricing in constitution.md [P3]

**Spec says**: Pricing reference table in api.md Section 5.
**Already done**: Added to specs. No code changes needed — this is documentation only.

---

## 16. Verify `_run_pytest` Uses `pytest --json-report` [P2]

**Architecture doc §2.3 says**: `pytest --json-report` for structured test result parsing.
**Code has**: `python -m pytest -v` with string-based outcome classification via `_classify_pytest_outcome()`.

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 16.1 | Update `_run_pytest()` to use `--json-report` flag (requires `pytest-json-report` plugin) | `cli/micro.py` | |
| 16.2 | Update `_classify_pytest_outcome()` to parse JSON output instead of string matching | `cli/micro.py` | |
| 16.3 | Add `pytest-json-report` to dev dependencies in `pyproject.toml` | `pyproject.toml` | |

---

## Execution Order (Dependency-Aware)

```
BLOCK 1 (parallel, independent):
  ├── #9  --json/--quiet flags
  ├── #5  deviate constitution pre/post
  └── #10 Placeholder resolution

BLOCK 2 (requires BLOCK 1 --json/--quiet):
  ├── #1  --profile (needs --json for test contracts)
  ├── #2  deviate context pre/post
  ├── #3  deviate adhoc pre/post
  └── #4  deviate feature create

BLOCK 3 (requires BLOCK 2):
  ├── #6  tasks list / issues list
  ├── #7  Cache discipline (needs profile)
  ├── #8  Train rollback (needs cache discipline context)
  ├── #11 AGENTS.md alignment (needs context)
  └── #13 tasks.md vs tasks.jsonl (needs tasks post wiring)

BLOCK 4 (requires BLOCK 2, 3):
  ├── #12 Skill rewrites with action logic
  └── #14 constitution seed audit

BLOCK 5 (independent):
  ├── #15 DeepSeek pricing (docs only — done)
  └── #16 pytest --json-report migration
```
