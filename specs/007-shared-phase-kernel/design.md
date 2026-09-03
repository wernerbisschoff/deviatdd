# Shared Phase Kernel (Auto Runner ⇄ Manual Pre/Post) — Architecture Design

Feature: `007-shared-phase-kernel` · Constitution: `specs/constitution.md` v0.10.0 · Source: `specs/007-shared-phase-kernel/explore.md`

## Recommended Architecture

[Summary]: Extract one kernel function per micro phase step into `src/deviate/cli/micro.py`, in place. The auto runner (`_run_red_phase`, `_run_green_phase`, `_run_judge_phase`, `_run_refactor_phase`) and the eight manual CLI commands (`deviate red|green|judge|refactor pre|post`) call the same kernels. The already-shared verdict path `_apply_judge_verdict` is the working template: `_run_judge_phase` and `judge_post` both converge on it. This change extends that pattern to RED, GREEN, and REFACTOR, so each phase step exists once.

The kernel covers three step families: pre-contract assembly, post side effects (test run, ledger transition, session transition, phase commit, sha persist), and verdict application. Prompt assembly stays out of scope: `_build_auto_prompt` plus `_LAYER_MAP` already single-source the prompt text, and `src/deviate/core/commands.py` splices the same auto core byte-identically into manual bodies. Agent invocation stays at the auto-orchestrator level: the manual surface has no in-process agent invocation, and the kernel must not gain one.

The macro-layer cycle driver is out of scope by evidence. `src/deviate/cli/macro.py::_cycle_phase:1081-1126` dispatches only `explore|research|prd|shard` and shares no code with the four micro phases. The explore brief marked this "verify at research"; verification shows no shared seam, so the extraction stays entirely inside `src/deviate/cli/micro.py`.

[Module_Surface]:

- Add (inside `src/deviate/cli/micro.py`, no new module):
  - `MicroPhaseKernel` TypedDict — the versioned pre-contract shape (see `data-model.md` `## Schema Tables`).
  - `KernelContext` dataclass — repo root, console, session, session path, ledger path, task id, mode (`auto` | `manual`).
  - `PhaseSideEffects` dataclass — test run result, ledger transition, session transition, commit sha.
  - `KernelOutcome` dataclass — status token, contract payload, `emit_contract` flag, task id.
  - `KernelError` exception — domain error; the CLI maps it to `typer.Exit(code=1)`; the auto runner catches it per phase step.
  - Kernel functions: `_red_pre_kernel`, `_red_post_kernel`, `_green_post_kernel`, `_refactor_post_kernel`. JUDGE already converges on `_apply_judge_verdict`; no new JUDGE kernel is needed.
- Modify (existing):
  - `_run_red_phase`, `_run_green_phase`, `_run_refactor_phase` — keep their orchestration (prompt build, agent invocation, monitoring); delegate each phase step to the kernels.
  - `red_pre`, `red_post`, `green_pre`, `green_post`, `judge_pre`, `judge_post`, `refactor_pre`, `refactor_post` — become thin wrappers: parse args, resolve task id, call a kernel, print status token or contract JSON, map `KernelError` to `typer.Exit`.
- Integration seams (unchanged): `_invoke_agent` (auto only), `_run_test_cmd` / `_run_format_cmd`, `append_task_transition`, `SessionState.force_transition_to` + `session.save`, `_commit_phase`, `_attach_mise_pre` doctor fields, `_resolve_task_context` / `_resolve_first_pending` / `_resolve_judge_post_task` (task resolution stays surface-level and feeds a task id into the kernel).
- Explicitly out of scope: `_cycle_phase` in `src/deviate/cli/macro.py` (no shared seam, and micro-layer agents must not touch branch-mutating macro code), ledger/session state shapes, HITL gates, E2E hardening for manual flows (observed gap only).

[Rationale]:

- Explore `## Scope Sizing`: "8 CLI commands become thin wrappers over 2 kernel steps per phase, reusing the existing `_apply_judge_verdict` seam as the template. No new modules, persistence, or integrations."
- Explore `## Scope Sizing`: "New Modules Required — No — kernels extract into the existing `src/deviate/cli/micro.py`."
- Explore `## Architectural Baselines`: `_apply_judge_verdict` at `src/deviate/cli/micro.py:3410` is "the single verdict application path; `_run_judge_phase` and `judge_post` both call it" — the proven convergence pattern.
- Constitution §1 Append-Only Ledger Protocol: kernels write ledger rows only through the existing `append_task_transition`; no state shape changes.
- Constitution §1 Micro-Layer Scope: GREEN keeps writing only to `src/` + permitted paths; JUDGE scope verification is untouched.

## Options Matrix

Only one option satisfies all constraints (Single Option Dominance Rule).

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Option A: In-place per-step kernels in `src/deviate/cli/micro.py`, both surfaces delegate | L-M | M-H — kernel tests mock `deviate.cli.micro._run_pytest` with `CompletedProcess`; CLI tests assert thin dispatch and status tokens | Aligned — §1 Append-Only Ledger Protocol, §1 Micro-Layer Scope, §3 Testing Protocols preserved | Easy — kernels are behavior-preserving extractions; revert restores the duplicated bodies | Module — one file plus its tests | Recommended |

## Rejected Options

- Option B: New kernel package `src/deviate/core/kernel.py` — rejected. Explore `## Scope Sizing` says "New Modules Required: No". A behavior module of this size outside `cli/micro.py` splits micro-layer cohesion and adds import-layer risk for zero behavior gain. The `src/deviate/prompts/assembly.py` precedent keeps micro-layer behavior in the micro module.
- Option C: Unify auto + manual into one agent-invoking orchestrator — rejected. Explore `## Architectural Baselines`: "The manual path has no agent invocation — the human's agent acts on the prompt; the CLI only supplies contract (pre) and applies side effects (post)." In-process invocation on the manual surface would change side-effect timing and break the `GH-154 AC-6` contract (`tests/unit/test_micro/test_red.py`: "manual `deviate red post --task-id` matches the pending record").
- Option D: Manual surface delegates to the auto runner via subprocess (`deviate micro run`) — rejected. Constitution §1 Session Continuity: each task loop holds one LLM session; a spawned child re-resolves and leaks the parent session. Explore `## Architectural Baselines` shows the auto runner drives `_invoke_agent` in-process with a monitor callback; a subprocess boundary adds no shared behavior.

## Design Trade-Offs

| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| K1 — Kernels live in `src/deviate/cli/micro.py` (in place) | Gain: module cohesion, no import-layer change. Lose: `micro.py` grows by the kernel layer while the 8 command bodies shrink | Explore `## Scope Sizing`: "New Modules Required: No"; precedent: `src/deviate/prompts/assembly.py` keeps micro prompt routing in the micro module |
| K2 — Keep two surface orchestrators; share only per-step kernels | Gain: auto semantics unchanged, manual side-effect timing preserved. Lose: two orchestration bodies remain (they are thin) | Explore File Registry: `tests/unit/test_micro/test_red.py` — "GH-154 AC-6: manual `deviate red post --task-id` matches the pending record"; surface entry semantics are part of the installed contract |
| K3 — One `KernelOutcome` with `emit_contract` flag | Gain: one kernel result type across the four phases. Lose: the type carries one field some phases leave `false` | Explore Architectural Baselines: only `red_pre` and `refactor_pre` print contract JSON; `green_pre`/`judge_pre` print no contract |
| K4 — Kernels raise `KernelError`; CLI maps to `typer.Exit(1)`; auto catches per step | Gain: one error path per step; exit codes stay stable. Lose: try/except at both surfaces | Explore Ecosystem Research: "Exit-code-bearing helper functions ... are the observed Typer convention" (project.scripts pattern) |
| K5 — Unify RED no-failing-test adjudication into `_red_post_kernel` | Gain: one RED adjudication path (exit 0 / pytest exit 5 / exit 127 routes). Lose: the auto orchestrator passes its mode flag into the kernel | Explore Architectural Baselines: auto RED "carries an in-process adjudication branch `_adjudicate_red_no_failing_test` ... that has no CLI-post counterpart" — consolidation, not new behavior |
| K6 — Task resolution stays surface-level; kernels are task-id-keyed | Gain: `--task-id`, first-pending, and judge resolution rules stay local per surface. Lose: kernels take a resolved id, not a resolution policy | Explore Architectural Baselines: `_resolve_task_context` (manual pre) vs `_resolve_first_pending` + `--task-id` match (red_post) vs `_resolve_judge_post_task` (judge_post) differ by design |

## Contrarian Viewpoints

- "Two orchestrators remain, so duplication persists at the orchestration level" — partly true. The orchestration bodies differ by design (auto: prompt build, agent invocation, monitor; manual: arg parsing, task-id resolution). Forcing one orchestrator merges agent invocation into the manual path and breaks the manual contract (Option C rejection). The kernel bounds duplication at the step level, where it is real. Anchor: explore `## Architectural Baselines` (auto vs manual surface descriptions).
- "In-place extraction makes `micro.py` larger, and it is already 7566 lines" — true, and measured. The counterweight: explore `## Scope Sizing` forbids new modules, and the 8 command bodies shrink. The kernel layer adds structure, not net lines of logic, because each kernel replaces two copies. Anchor: explore File Registry row `src/deviate/cli/micro.py` (7566 lines).
- "Kernel extraction is a pure refactor with no user-visible value" — the user-visible value is drift prevention: the manual RED adjudication gap (exit 0 / pytest exit 5 / exit 127 routes) and per-phase side effects converge, so prompt retry contracts keep working against both surfaces. Anchor: explore `## Architectural Baselines` (adjudication branch with no CLI-post counterpart).
- "Unify GREEN status computation while touching RED kernels" — scope creep risk. The kernel takes GREEN status computation as it exists today; changing status semantics is a separate feature. Anchor: explore `## Scope Sizing` (files likely modified, behavior-adjacent refactor).

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | Status-token drift between auto and manual surfaces after extraction (`RED_POST_OK`, `GREEN_POST_OK`, `JUDGE_POST_OK route=...`, `REFACTOR_POST_OK`, `TEST_NOT_FOUND`, `LEDGER_UPDATE_FAILED`) | M | H — prompt retry contracts reference the tokens | One `KernelOutcome.status_token` per outcome; regression tests assert each token on both surfaces | `src/deviate/cli/micro.py` | Explore `## Architectural Baselines` (Quality section) + `tests/unit/test_meso/test_prompt_assembly.py:70` |
| RSK-002 | Phase commit message or flags drift (e.g. `no_verify=True`, `phase="red"`) | M | H — breaks constitution §4 commit convention and §5 DoD | Commit literals pass through unchanged from the kernels; per-phase commit tests compare full command messages | `src/deviate/cli/micro.py` | Explore baseline snippet: `_commit_phase(f"test({scope}): RED phase - failing test", ..., no_verify=True, phase="red")` |
| RSK-003 | Test-suite slowdown: new tests reaching `_run_pytest` as a subprocess | M | M — AGENTS.md performance rule (full suite < 30s) | All kernel tests mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture | `tests/unit/test_micro/` | AGENTS.md "Test Performance" + explore Test Runner Configuration |
| RSK-004 | Manual RED adjudication change alters `red post` exit codes | L | M — external agents parse exit codes | Kernel preserves route behavior; adjudication tests cover exit 0 / pytest exit 5 / exit 127 | `src/deviate/cli/micro.py` | Explore baseline: `_adjudicate_red_no_failing_test` routes |
| RSK-005 | Contract JSON field changes break installed external agents | L | H — the contract is an installed interface | `MicroPhaseKernel` fields are additive-only; existing keys keep names and order semantics; no field removed | `src/deviate/cli/micro.py` | Explore Ecosystem Research (Codex CLI wire-schema analogy) + `red_pre` contract snippet |
| RSK-006 | Git isolation breakage in tests (kernel tests calling real git) | L | M — pollutes the working repo | Kernel tests reuse `tests/conftest.py` `_git_env` + `tmp_git_repo`; every git call sets `cwd=<tmp_git_repo>` | `tests/unit/test_micro/` | AGENTS.md "Git Isolation" + explore Test Runner Configuration |

## Constitutional Alignment Audit

| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| §1 "Append-Only Ledger Protocol: All state transitions in `issues.jsonl` and `tasks.jsonl` are append-only. No existing line is ever modified or overwritten." | Kernels write transitions only through the existing `append_task_transition`; no state shape changes | Aligned | Explore `## Scope Sizing`: "New Persistence / Data Models — No ... Append-Only Ledger Protocol holds" |
| §1 "Micro-Layer Scope: GREEN phase writes only to `src/` and permitted implementation paths." | GREEN kernel changes no write scope; JUDGE diff verification untouched | Aligned | Explore baseline: JUDGE "verifies GREEN only modified allowed files" (constitution §3 Coverage) |
| §1 "Session Continuity: Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases. Model switching mid-task is prohibited." | Auto orchestrator keeps `_invoke_agent` in-process with `resolve_model_for_phase`; kernels never invoke agents | Aligned | Option C/D rejections; explore baseline: `_invoke_agent(..., model=red_model)` per §1 model routing |
| §1 "Human-in-the-Loop (HITL): Two remaining mandatory gates ... No remaining gate may be programmatically bypassed." | No gate logic touched; `research post` runs after this design with Gate 1 intact | Aligned | Scope excludes HITL gates (explore `## Problem Definition` exclusions) |
| §3 "REFACTOR phase runs regression gate: tests must re-pass after polish" | Kernel extraction preserves per-phase semantics; behavior-preserving refactor | Aligned | `refactor_post` keeps `_run_pytest` regression semantics (explore baseline: `refactor_post:7114` invokes `_run_pytest`) |
| §3 "Test framework: pytest ... Test command: `pytest tests/ -v`" | New kernel tests land in `tests/unit/test_micro/` as pytest tests | Aligned | Explore Test Runner Configuration: micro-layer tests in `tests/unit/test_micro/` |
| §4 "All commits must reference the task ID" + commit convention `test(<scope>): ...` | `_commit_phase` message literals pass through kernels unchanged | Aligned (tension resolved) | Gamma flagged K4; mitigation RSK-002 keeps message literals verbatim |
| §5 DoD "CHANGELOG.md updated under `[Unreleased]` for user-visible changes" | Behavior-adjacent refactor — `red post` gains manual RED adjudication routes | Aligned | CHANGELOG bullet required if manual RED behavior changes; explore `## Scope Sizing` flags "verify exemption or add bullet" |

No `Violation` rows. No `Constitutional Violation` block; the workflow continues to `deviate research post` after Gate 1.

## Pending HITL Decisions

<!-- HITL_DECISIONS -->
<!-- Populate with decisions that explicitly reverse or deviate from the explore brief, reject tools requested in the explore phase, introduce novel architecture not anticipated during explore, or otherwise require human judgment before PRD proceeds. If empty (zero rows), PRD may proceed automatically. -->

| Decision ID | Question | Context | Impact | Recommended Resolution | Status |
|---|---|---|---|---|---|
| `HITL-001` | Should the macro `_cycle_phase` driver share the micro kernel seam? | Explore `## Scope Sizing` deferred this: "`src/deviate/cli/macro.py` (if the meso `_cycle_phase` reuses the same seam — verify at research)". Verified at `src/deviate/cli/macro.py:1081-1126`: `_cycle_phase` dispatches only `explore|research|prd|shard` and shares no code with the four micro phases. | Including it would couple macro branch-mutating dispatch to micro kernels for zero shared behavior; AGENTS.md forbids micro-layer agents from branch-mutating macro code. | Exclude `_cycle_phase` from scope; kernel stays in `src/deviate/cli/micro.py`. | `RESOLVED` |
| `HITL-002` | Unify the manual RED no-failing-test adjudication into the kernel? | Explore baseline: `_adjudicate_red_no_failing_test` (exit 0 / pytest exit 5 / exit 127 routes) "has no CLI-post counterpart". Kernel consolidation implies `red post` gains the same adjudication routes. | Without unification, RED adjudication stays auto-only and the two RED surfaces keep diverging. With it, `red post` exit codes change for the no-failing-test case (a user-visible behavior change requiring a CHANGELOG bullet). | Unify into `_red_post_kernel`; add CHANGELOG bullet under `[Unreleased]`; per-route tests. | `RESOLVED` |

**Gate Rule**: No row has Status `PENDING`; `deviate prd pre` may proceed after Gate 1 review.

## Source Registry

| ID | Type | Source / Path | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Explore_MD | `specs/007-shared-phase-kernel/explore.md` | Factual baseline: surfaces, seams, scope sizing, ecosystem research |
| SRC-002 | Constitution | `specs/constitution.md` | Governance: §1 principles, §2 stack, §3 testing, §4 workflow, §5 DoD (v0.10.0) |
| SRC-003 | Codebase_File | `src/deviate/cli/micro.py` | Kernel host: 4 auto orchestrators + 8 manual commands + `_apply_judge_verdict` |
| SRC-004 | Codebase_File | `src/deviate/cli/macro.py` | `_cycle_phase:1081-1126` — verified out of scope (HITL-001) |
| SRC-005 | Codebase_File | `src/deviate/prompts/assembly.py` | `_LAYER_MAP` — prompt text already single-source |
| SRC-006 | Codebase_File | `src/deviate/core/commands.py` | Manual prompt splice — auto core byte-identical at install time |
| SRC-007 | Codebase_File | `tests/unit/test_micro/test_red.py` | GH-154 AC-6 manual `red post --task-id` contract |
| SRC-008 | Codebase_File | `tests/unit/test_micro/test_judge.py` | Manual `judge post` applies auto-mode verdict side effects |
| SRC-009 | Codebase_File | `tests/unit/test_meso/test_prompt_assembly.py` | Status-token / retry-contract coupling (`:70`) |
| SRC-010 | Codebase_File | `src/deviate/prompts/auto/red.md` | Canonical RED prompt core (auto + manual via splice) |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 007-shared-phase-kernel |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the prd skill |
