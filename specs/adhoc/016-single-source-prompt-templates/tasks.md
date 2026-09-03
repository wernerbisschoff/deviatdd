# Implementation Tasks: `feat/adhoc/016-single-source-prompt-templates`

## Phase 1: Rewire the Manual Derivation to the Canonical Auto Core
**Goal**: Make `install_command`/`compose_command_body` derive each manual slash-command body from `auto/{phase}.md` plus a per-phase manual overlay instead of a hand-maintained duplicate. Deliver AC-PLAN-001 (derivation without a duplicate middle) and AC-PLAN-004 (idempotency + auto-only `load_template`).

### Tasks

- TSK-016-01: Derive the manual slash-command body from the canonical `auto/{phase}.md` core plus a per-phase manual overlay
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/unit/test_core/test_commands.py`
  - **Estimated Time**: 90 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/core/commands.py`
    - `src/deviate/prompts/assembly.py`
    - `tests/unit/test_core/test_commands.py`
  - **Rationale**: Implements `US-016-01` and `AC-PLAN-001` (derivation from `auto/{phase}.md` + overlay, no duplicate middle) and `AC-PLAN-004` (idempotent reinstall + auto-only `load_template`). `compose_command_body` (lines 55-133) and `install_command` (lines 189-243) are the manual derivation path; the rework must read the canonical middle from `auto/{phase}.md` and splice the overlay around it. `assembly.py::load_template` must keep emitting the auto core body only. `tests/unit/test_core/test_commands.py` asserts the derived output.
  - **Details**:
    - **Red**: Write `test_install_derives_from_auto_core(tmp_path, tmp_git_repo)` asserting installing `deviate-red` into `tmp_path` produces a `deviate-red.md` whose composed middle equals the core body read from `deviate.prompts.auto/red.md`, with platform `name`/`description` frontmatter only and a manual pre/post-script lifecycle; write `test_install_returns_false_on_unchanged_reinstall(tmp_path)` asserting a second identical install returns `False`; write `test_load_template_emits_auto_core_only()` asserting `load_template("red")` contains no manual-overlay marker.
    - **Green**: Add a deterministic `_MANUAL_PHASE_MAPPING` mapping each of the 11 manual phase names (red, green, refactor, judge, execute, plan, tasks, explore, research, prd, shard) to its canonical `auto/{phase}.md` resource. Rework `compose_command_body(raw, core_dir, ...)` so it takes the auto core body and the per-phase manual overlay instead of a hand-maintained `raw` duplicate. Update `install_command` to resolve the source in `auto/`, compose from the auto core + overlay, strip frontmatter, and write idempotently (`False` when `target_path` equals `composed`).
    - **Refactor**: Factor the frontmatter extraction, layer routing, and constitution injection into small pure helpers; keep `_LAYER_RE` and the product-layer lifecycle branch (`layer != "product"`) intact.
    - **Edge Cases**: Keep constitution injection best-effort and non-fatal when `specs/constitution.md` is missing; keep the `deviate-pr` graphite routing branch (`_graphite_enabled`) unchanged; preserve the `_strip_deviate_frontmatter`/`_emit_platform_frontmatter` contract so only `name`/`description` reach the on-disk frontmatter.
    - **Acceptance**: Installing any of the 11 phases produces a middle body byte-identical to its `auto/{phase}.md` core; unchanged reinstall returns `False`; `load_template` output contains no overlay marker.
  - **Dependency**: none

---

## Phase 2: Reconcile and Reduce the Drafted Manual Middes
**Goal**: Delete the duplicated middle bodies from the 11 `commands/deviate-{phase}.md` files, retain frontmatter + per-phase manual overlay, and reconcile the drifted RED/GREEN semantics to auto. Deliver AC-PLAN-002.

### Tasks

- TSK-016-02: Reconcile the drifted manual middes to the auto RED and GREEN semantics and reduce each `commands/deviate-{phase}.md` to a manual overlay
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `mise run format-check` then `mise run test tests/unit/test_core/test_commands.py`
  - **Estimated Time**: 90 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/prompts/commands/deviate-red.md`
    - `src/deviate/prompts/commands/deviate-green.md`
    - `src/deviate/prompts/commands/deviate-refactor.md`
    - `src/deviate/prompts/commands/deviate-judge.md`
    - `src/deviate/prompts/commands/deviate-execute.md`
    - `src/deviate/prompts/commands/deviate-plan.md`
    - `src/deviate/prompts/commands/deviate-tasks.md`
    - `src/deviate/prompts/commands/deviate-explore.md`
    - `src/deviate/prompts/commands/deviate-research.md`
    - `src/deviate/prompts/commands/deviate-prd.md`
    - `src/deviate/prompts/commands/deviate-shard.md`
  - **Rationale**: Implements `US-016-02` and `AC-PLAN-002` (reconcile RED `status:"FAIL"` at line 69 to auto `status:"PASS"` + `failure_kind`; GREEN "Maintain existing functional signatures" at line 109 to auto "write ONLY production code" at line 90). These 11 files are the stale hand-maintained duplicates (17-68% drift); deleting the duplicated middle bodies fulfills `AC-PLAN-001`'s "no hand-maintained duplicate" and turns each file into the overlay consumed by `TSK-016-01`.
  - **Details**:
    - **Implementation**: For each of the 11 files, diff the manual body against the `auto/{phase}.md` core, resolve the drifted middle to the auto semantics (RED → `status: "PASS"` + `failure_kind` discriminator; GREEN → "write ONLY production code (minimal change so that RED works)"; tasks → `TSK-\d{3}-\d{2}` per `src/deviate/cli/meso.py:938`; plan → `{plan_path}` per `src/deviate/core/validation.py`), then delete the duplicated middle and retain only frontmatter (`name`/`description`/`layer`) + manual-only overlay (pre/post-script lifecycle, rich handover manifest, `<context><user_input>`, per-phase manual-only steps such as `reduce_phase`/`interactive_hitl_gate_1`/`html_artifact` for research).
    - **Edge Cases**: Do not touch the 15 commands-only prompts (adhoc, architecture, constitution, e2e, flows, hotfix, html, init, merge, pr, prune, release, review, triage, walkthrough) — they have no auto counterpart and stay hand-maintained. Resolve field-name drift per-phase (do not uniform-inject structure). Keep `layer` frontmatter so `compose_command_body` route to the correct `{layer}-shared.md`.
    - **Acceptance**: No `commands/deviate-{phase}.md` for the 11 overlapping phases retains a duplicated middle; RED no longer emits `status: "FAIL"` or abort-on-passing-test; GREEN instructs "write ONLY production code"; every retained overlay line is manual-only content absent from the corresponding `auto/{phase}.md`.
  - **Dependency**: `TSK-016-01`

---

## Phase 3: Drift-Guard and Auto-Semantics Pinning
**Goal**: Enforce the identical-middle invariant and pin the reconciled auto semantics so the derivation can never diverge. Deliver AC-PLAN-003 and back up AC-PLAN-002.

### Tasks

- TSK-016-03: Add the drift-guard and auto-semantics pinning tests
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Solitary_Unit
  - **Verification**: `mise run test tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `tests/unit/test_meso/test_auto_prompt_templates.py`
    - `tests/unit/test_meso/test_prompt_assembly.py`
  - **Rationale**: Implements `US-016-03` and `AC-PLAN-003` (drift guard over the 11 overlapping phases). `tests/unit/test_meso/test_auto_prompt_templates.py` currently pins slim-template composition only (lines 58-61 `test_composed_template_has_context_marker`); it gains the identical-middle assert and auto-semantics pins. `tests/unit/test_meso/test_prompt_assembly.py` verifies `load_template` emits the auto core only with no overlay leakage (`AC-PLAN-004`).
  - **Details**:
    - **Red**: Write `test_auto_and_manual_middle_identical(tmp_path)` asserting the installed derived middle (via `install_command(name, tmp_path)`) equals `deviate.prompts.auto/{phase}.md` byte-for-byte for each of the 11 phases — the test fails with a diff when an unrelated line is added to an auto middle. Write `test_auto_red_uses_pass_failure_kind()` asserting `auto/red.md` declares `status: "PASS"` + `failure_kind` and never `status: "FAIL"`. Write `test_manual_red_matches_auto_semantics(tmp_path)` asserting the derived RED no longer emits `status: "FAIL"`/abort-on-passing-test. Write `test_load_template_has_no_manual_overlay_leakage()` in `test_prompt_assembly.py`.
    - **Green**: Read the auto core and the derived installed middle via `importlib.resources`/`install_command` against `tmp_path`; compare normalized middle lines and assert equality. No production-code change is expected — the drift-guard is a regression lock over `TSK-016-01`/`TSK-016-02`.
    - **Refactor**: Extract a helper returning the middle slice (frontmatter stripped, lifecycle/overlay markers removed) shared by the compare tests.
    - **Edge Cases**: Mock nothing — the drift-guard reads the two source files and calls `install_command` against `tmp_path` only (no `deviate.cli.micro._run_pytest` subprocess, per the AGENTS.md performance mandate < 30s). Exempt the 15 commands-only prompts from the identical-middle invariant (`AC-ADHOC-016-03` boundary).
    - **Acceptance**: All drift-guard and semantic tests pass on clean templates; a deliberate auto-middle edit makes `test_auto_and_manual_middle_identical` fail; suite stays under 30s.
  - **Dependency**: `TSK-016-01`, `TSK-016-02`

---

## Phase 4: Documentation, Specs, and Changelog
**Goal**: Reflect the single-source prompt architecture in the authoritative specs and record the user-visible change in the changelog in the same commit as the implementation. Satisfies the spec-alignment and CHANGELOG mandates.

### Tasks

- TSK-016-04: Document the single-source prompt derivation in specs and changelog
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `mise run check` then `mise run lint` then `mise run format-check` then `mise run test`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: The spec-alignment mandate requires `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` to mirror the derivation change in the same commit as the implementation. `CHANGELOG.md` must append a `[Unreleased]` bullet because the template-derivation change is user-visible (new derivation behavior for `deviate setup`). The 15 commands-only prompts and shared preambles (`core/{layer}-shared.md`, `core/core.md`, `core/style-ste.md`) stay untouched per the defensive exclusions.
  - **Details**:
    - **Implementation**: Append a `[Unreleased]` bullet to `CHANGELOG.md` describing the single-source prompt derivation, the manual-midded reconciliation to auto semantics, and the drift guard. Update `specs/DeviaTDD-api.md` to document that manual slash-command bodies derive from `auto/{phase}.md` + a per-phase manual overlay at install time. Update `specs/DeviaTDD-architecture.md` to document the auto-canonical/manual-derived prompt architecture and the deletion of the duplicated middles (17-68% drift removed) across the 11 overlapping phases.
    - **Edge Cases**: Keep the change to docs/specs/changelog only — no production-code or test edits in this task. Do not regenerate `specs/_product/` flow artifacts (`flow_refs: []`).
    - **Acceptance**: `CHANGELOG.md` `[Unreleased]` lists the derivation change; both spec documents name `auto/{phase}.md` as the single source of truth and `compose_command_body`/`install_command` as the derivation path; full `mise run check`/`lint`/`format-check`/`test` passes.
  - **Dependency**: `TSK-016-03`

---

## Phase 5: Closing Application E2E Verification
**Goal**: Verify the `deviate setup` install path end-to-end on the application's own E2E surface.

### Tasks

- TSK-016-05: [E2E] Smoke-test the derived manual slash-command install against the auto core
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `mise run test-e2e`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `tests/e2e/test_single_source_prompts.bats`
  - **Rationale**: Application verification for the user-facing `deviate setup` CLI workflow touching C1. The happy path drives `compose_command_body`/`install_command` to install a derived `deviate-red.md` whose middle equals `auto/red.md` (AC-PLAN-001); the critical-failure path adds an unrelated line to an auto middle and confirms the drift-guard fails (AC-PLAN-003).
  - **Details**:
    - **Red**: Author a bats smoke test in `tests/e2e/test_single_source_prompts.bats`: happy path runs `install_command('deviate-red', $TMPDIR)` and asserts the installed `$TMPDIR/deviate-red.md` copied middle equals the `auto/red.md` body; critical-failure path appends an unrelated line to a copy of an auto `green.md` middle and asserts a comparison helper reports a diff.
    - **Implementation**: Build the install into a temp dir via the `deviate` package entry point (no branch-mutating git commands), capture the composed `deviate-red.md`, and diff its middle against `src/deviate/prompts/auto/red.md`. The failure scenario diffs an intentionally mutated auto middle and asserts a non-zero comparison result.
    - **Edge Cases**: Keep the suite < 30s; do not invoke `deviate.cli.micro._run_pytest`; do not touch `~/.config/opencode/skills/` or `<workdir>/.<agent>/commands/` — use a `tmp_path`/`$TMPDIR` target only.
    - **Acceptance**: `mise run test-e2e` exits 0 with the derive-and-compare happy path and the drift-failure scenario reported.
  - **Dependency**: none (last, no forward dependency)

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5

**Critical Dependency Chains**:
- TSK-016-01 must precede TSK-016-02 (the derivation rework consumes the reduced overlays)
- TSK-016-01 and TSK-016-02 must precede TSK-016-03 (the drift-guard compares derived output against reduced overlays)
- TSK-016-03 must precede TSK-016-04 (docs mirror the implemented behavior)
- TSK-016-05 runs last with no forward dependency

**Risk Hotspots**:
- Field-name/structural drift per phase (plan `{plan_path}` vs `plan_target`; tasks `TSK-\d{3}-\d{2}` vs `T001`) — reconcile per-phase; do not uniform-inject structure. Resolve to the runner-enforced format per `src/deviate/cli/meso.py:938` and `src/deviate/core/validation.py:260`.
- Manual-overlay content leaking into the auto core changes auto-runner behavior — `load_template` must keep emitting the auto core only; the `test_load_template_has_no_manual_overlay_leakage` assertion guards it.
- Install idempotency regression (returns `True` on unchanged reinstall) — keep the `target_path == composed` short-circuit returning `False` in `install_command`.
- Drift-guard test invoking `deviate.cli.micro._run_pytest` and slowing the suite past 30s — the drift-guard reads the two source files and calls `install_command` against a `tmp_path` only (no subprocess), per the AGENTS.md performance mandate.
- Greenfield `specs/constitution.md` absence must not break derivation — keep constitution injection best-effort and non-fatal (current `OSError`-tolerant path).

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/core/commands.py` (TSK-016-01 only), `tests/unit/test_core/test_commands.py` (TSK-016-01 only), `tests/unit/test_meso/test_auto_prompt_templates.py` and `tests/unit/test_meso/test_prompt_assembly.py` (TSK-016-03 only), the 11 `commands/deviate-{phase}.md` files (TSK-016-02 only), spec/changelog files (TSK-016-04 only), `tests/e2e/test_single_source_prompts.bats` (TSK-016-05 only). No file is touched by more than one task, so merge conflicts are avoided.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/016-single-source-prompt-templates.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
