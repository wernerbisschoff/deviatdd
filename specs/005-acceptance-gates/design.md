# Design — Acceptance Criteria and Phase-Specific Test Gates

Epic `005-acceptance-gates` · Feature Slug `acceptance-gates` · Phase `RESEARCH`

## Recommended Architecture

The feature makes acceptance criteria explicit and applies test enforcement to the GREEN and REFACTOR phases but not to the RED phase. The design reuses the existing authoritative `AC-PLAN-NNN` Gherkin acceptance contract in each slice's `plan.md` `## Acceptance Contract` section. It does not introduce a new `acceptance.md` slice artifact. The change surface narrows to four coordinated extensions. First, each `AC-PLAN-NNN` scenario gains a verification-mode metadata field. Second, task records gain `acceptance_criteria` traceability that links each task to its criteria and each criterion to its test. Third, the GREEN phase keeps enforcing test pass while routing failure to the existing JUDGE retry path. Fourth, the RED phase test gate becomes a non-blocking checkpoint expressed as a phase-handoff advisory.

The architecture follows the existing three-layer macro/meso/micro model. No new module is created. The micro-layer runner `src/deviate/cli/micro.py` gains the RED checkpoint and the GREEN/REFACTOR gate enforcement. The task-ledger model `src/deviate/state/ledger.py` gains additive fields. The artifact-validation layer `src/deviate/core/validation.py` gains verification-mode metadata validation. The meso-layer task generator `src/deviate/core/tasks_ledger.py` carries the new task field. The RED prompt templates under `src/deviate/prompts/commands/` and `src/deviate/prompts/auto/` describe the non-blocking checkpoint.

The design keeps all state in the existing append-only JSONL ledger protocol and the `.deviate/` session store. It adds no persistent database runtime, respecting the constitution's "No persistent database runtime" clause. The RED checkpoint is an in-memory phase-handoff advisory, so it holds no permanent state and cannot desync from the git repo after `git reset`. The `TaskRecord.status` Literal stays unchanged; the new traceability uses additive fields, so the existing canonical-state derivation by sequential ledger parsing remains valid. The `AO-NNN` → `AC-PLAN-NNN` → task → test chain is extended, not replaced, so `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` update in the same commit.

**Module Surface:**
- **Modify** `src/deviate/cli/micro.py` — RED non-blocking checkpoint; GREEN blocking enforcement; REFACTOR blocking regression gate.
- **Modify** `src/deviate/state/ledger.py` — additive `acceptance_criteria` field on `TaskRecord` (no persistent checkpoint record).
- **Modify** `src/deviate/core/validation.py` — verification-mode metadata validation on `AC-PLAN-NNN` scenarios; optional criterion-to-test linkage check.
- **Modify** `src/deviate/core/tasks_ledger.py` — propagate `acceptance_criteria` into generated `TaskRecord`.
- **Modify** `src/deviate/cli/meso.py` — no logic change unless verification-mode is enforced at `tasks_pre`; primary change is metadata pass-through in task generation.
- **Modify** `src/deviate/prompts/commands/deviate-red.md` and `src/deviate/prompts/auto/red.md` — describe the non-blocking checkpoint.
- **Modify** `src/deviate/prompts/auto/green.md` and `src/deviate/prompts/auto/refactor.md` — describe blocking validation.
- **Modify** `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` — reflect gate semantics.
- **Modify** `CHANGELOG.md` — user-visible behavior change entry.
- **Add** tests under `tests/unit/test_micro/` and `tests/unit/test_core/`.

**Rationale:** The constitution's Definition of Done already requires satisfaction of `AC-PLAN-NNN` scenarios, and GREEN/REFACTOR already run the test suite. The design converts existing implicit gates into explicit, verifiable ones while preserving the TDD intent that RED must author a failing test. It aligns with the constitution's "Four-Layer Architecture" and "Append-Only Ledger Protocol" clauses and with the already-enforced `validate_acceptance_contract` path in `src/deviate/core/validation.py:112`.

## Options Matrix

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Option A: Enrich `plan.md` `AC-PLAN-NNN` (verification-mode metadata + `acceptance_criteria` traceability + GREEN/REFACTOR blocking + non-blocking RED checkpoint) | M | H | Aligned | Easy | Module | Recommended |
| Option B: New `acceptance.md` slice artifact with its own scenario format | H | M | Tension | Hard | System | Rejected |
| Option C: Keep RED as a hard blocking gate; only add verification-mode metadata and traceability | L | M | Aligned | Easy | Local | Rejected |
| Option D: Move all acceptance validation into a standalone runner decoupled from the phase runners | H | M | Tension | Hard | System | Rejected |

## Rejected Options

- **Option B: New `acceptance.md` artifact** — The user explicitly chose Option A during explore: "do NOT introduce a new `acceptance.md` artifact" (`explore.md` Problem Definition). A new artifact would require generation scaffolding, a new required slice file, and new command surface, contradicting the explore decision and the constitution's Definition of Done, which already binds implementation to `plan.md` scenarios.
- **Option C: Keep RED hard-blocking** — Explore cites the exact behavior to replace, `src/deviate/cli/micro.py:1123-1129`, where `_run_red_phase` raises `PhaseFailedError` on test returncode 0. TDD intent requires RED to contain a failing test; a hard pass-rejection is already the current behavior. Keeping it contradicts the user decision to make RED a non-blocking checkpoint.
- **Option D: Standalone runner** — Yields the lowest coupling but raises the blast radius to `System` and adds a parallel execution path that the existing safe-command gate in `_run_test_cmd` (`micro.py:4291`) would bypass or duplicate. Not reversible without significant refactor.

## Design Trade-Offs

| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| Verification-mode metadata embedded in `AC-PLAN-NNN` scenarios | Explicit per-criterion mode (automated/manual/deferred) vs. heavier structured metadata | Reuses the already-enforced contract path (`validation.py:112`); `plan.md` remains the single source of truth; adds no new slice artifact |
| `acceptance_criteria` as additive `TaskRecord` field | Extends the existing serialization model vs. a hard schema migration | The constitution's Definition of Done and `Spec Alignment` require additive backward-compatible change (`explore.md` Scope Sizing: "TaskRecord schema change is backward-compatible (additive field)"); satisfies the append-only protocol |
| RED checkpoint as advisory phase-handoff output | Explicit durable record vs. transient handoff consumed by the next runner | No persistent record avoids git-desync (a `.deviate/` checkpoint goes stale after `git reset`); the runner consumes the advisory in-memory so the next phase sees the unexpected-pass and the GREEN gate stays the hard validator |
| GREEN keeps validating test pass but routes failure to JUDGE | Enforce a hard task rejection vs. rely on the existing `train_feedback` → JUDGE retry routing | The existing runner already owns GREEN-failure retry via JUDGE (`micro.py:1306`, `is_feedback_retry` at `micro.py:1175`); no new retry mechanism is introduced. The `verification_mode` never exempts the automated suite, so the DoD stays enforceable |
| REFACTOR regression gate enforces returncode 0 | Blocking re-pass after polish vs. current un-checked `_run_test_cmd(root)` call (`micro.py:2500`) | "REFACTOR phase runs regression gate: tests must re-pass after polish" is a constitution Testing Protocol clause |

## Contrarian Viewpoints

- **(Verification-mode as metadata inside `plan.md`)** — If a scenario is marked `manual` or `deferred`, a strict blocking GREEN gate might skip it and silently reduce coverage. The scenario where GREEN auto-passes because all scenarios are tagged `manual` means the gate enforces nothing. Mitigation: `manual`/`deferred` must still run the automated subset, and the mode field must not exempt the automated suite.
- **(Additive `TaskRecord` field under `extra="forbid"`)** — `TaskRecord` declares `model_config = {"extra": "forbid"}` (`ledger.py:98`). An additive field is allowed, but any JSONL written by an older CLI version without the field still validates; forcing the field could break the append-only protocol. Mitigation: make the field optional with a default, so mixed-version ledgers parse.
- **(Non-blocking RED checkpoint)** — Removing the hard RED pass-rejection lets a RED phase that accidentally authors a passing test proceed to GREEN. The scenario is a RED phase that fixes the code instead of writing a failing test. Mitigation: the checkpoint records a `RED_PASSED_WARNING` and leaves the GREEN gate to catch the false-positive scenario.
- **(Handoff-output RED checkpoint)** — If the advisory is only in-memory, an abrupt process exit between RED and GREEN loses it. Mitigation: the advisory rides the same RED→GREEN transition handoff the runner already carries; a crash restarts RED, which re-derives the outcome, so no persistent store is needed.

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | Additive `TaskRecord.acceptance_criteria` field conflicts with `extra="forbid"` when older JSONL rows lack it | M | M | Declare the field optional with a default; preserve append-only serialization | meso/micro | `src/deviate/state/ledger.py:98` |
| RSK-002 | `manual`/`deferred` verification modes weaken the GREEN gate by exempting all automated tests | M | H | Mode field gates only the criterion status, never the executable test suite; automated tests always run | micro | `src/deviate/core/validation.py:112` |
| RSK-003 | Non-blocking RED checkpoint permits a passing-test RED to slip through | M | M | The RED phase emits an advisory `unexpected-pass` handoff warning; the GREEN gate remains the hard validator | micro | `src/deviate/cli/micro.py:1123` |
| RSK-004 | Checkpoint advisory lost between RED and GREEN on abrupt exit | L | M | Advisory rides the RED→GREEN phase-transition handoff; a crash restarts RED and re-derives the outcome; no persistent store | micro | `src/deviate/cli/micro.py` |
| RSK-005 | Test-run value (`_run_test_cmd`) diverges from constitution `pytest tests/ -v` due to `--testmon-noselect` wrapper | L | M | Document the divergence without adjudication; reuse `_test_command_candidates` | core | `mise.toml [tasks.test]` |

## Constitutional Alignment Audit

| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| "GREEN phase must pass all tests" (§3) | GREEN keeps the test-pass gate and routes failure to JUDGE | Aligned | The existing `train_feedback` → JUDGE routing enforces the clause outcome |
| "REFACTOR phase runs regression gate: tests must re-pass after polish" (§3) | REFACTOR inspects `_run_test_cmd` returncode | Aligned | Converts implicit call into explicit gate |
| "No persistent database runtime (all state tracked in JSONL ledgers and TOML config)" (§2) | No DB; additive fields on JSONL ledger + `.deviate/` session | Aligned | Extends existing stores only |
| "Append-Only Ledger Protocol" (§1) | Additive, optional task field; no row mutation | Aligned | New columns are append-only compatible |
| "Macro PRD/shard/adhoc artifacts carry acceptance outlines; Plan owns the finalized Gherkin Acceptance Contract" (§1) | Reuse `plan.md` `AC-PLAN-NNN` contract | Aligned | Plan remains the owner |
| "Four-Layer Architecture" with "strict phase gates — no layer may be skipped" (§1) | Gates enforced at micro phases | Aligned | Extends existing TDD gates, no new layer |
| "Micro-Layer Scope: GREEN writes only to `src/` and permitted implementation paths" (§1) | Gate enforced as a blocking check | Aligned | Reinforces the scope rule |

## Pending HITL Decisions

<!-- HITL_DECISIONS -->
<!-- Populate with decisions that explicitly reverse or deviate from the explore brief, reject tools requested in the explore phase, introduce novel architecture not anticipated during explore, or otherwise require human judgment before PRD proceeds. If empty (zero rows), PRD may proceed automatically. -->

| Decision ID | Question | Context | Impact | Recommended Resolution | Status |
|---|---|---|---|---|---|
| `HITL-001` | How is the non-blocking RED checkpoint recorded? | explore.md defers to "`.deviate/` or the task ledger". A review concern: a `.deviate/` checkpoint goes out of sync with the git repo after `git reset`. | Durable record desyncs with the repo; a handoff-only advisory loses nothing on reset and keeps the ledger untouched. | Emit the checkpoint as a phase-handoff advisory (e.g., `unexpected-pass`) consumed in-memory by the next runner; no persistent record, no new ledger field, no `.deviate/` store. | `RESOLVED` |
| `HITL-002` | What are the GREEN / REFACTOR failure semantics? | The existing runner already routes GREEN test failure to JUDGE via `train_feedback` (`micro.py:1298-1311`, `is_feedback_retry` at `micro.py:1175`), and JUDGE already owns retry with `revert_to_red` / `revert_before` and `_MAX_JUDGE_FEEDBACK = 3` (`micro.py:1391`). | No new retry mechanism is needed; Option A adds only `verification_mode` metadata and the non-blocking RED advisory. | GREEN test failure continues to route to JUDGE, which decides retry (GREEN vs RED+GREEN); REFACTOR regression gate raises on test failure; no new retry threshold is introduced. | `RESOLVED` |
| `HITL-003` | How is verification-mode (`automated` / `manual` / `deferred`) encoded on an `AC-PLAN-NNN` scenario? | Explore proposes "explicit verification-mode metadata" on the existing contract; no format is specified. | A structured field (e.g., `**Verification Mode**: automated`) is human-readable and Gherkin-safe; a front-matter table is harder to validate. | Encode it as a per-scenario `**Verification Mode**: <mode>` line inside each `AC-PLAN-NNN` scenario body. | `RESOLVED` |
| `HITL-004` | Does RED need a new `TaskRecord` status value, or a separate checkpoint record? | `TaskRecord.status` Literal is fixed at `PENDING/RED/GREEN/JUDGE/REFACTOR/COMPLETED/FAILED` (`ledger.py:85`). | A new status mutates the canonical state machine and DoD; a separate persistent record desyncs under `git reset`. | Keep the status Literal unchanged; the checkpoint is a handoff advisory, not a persisted status or record. | `RESOLVED` |

**Gate Rule**: If ANY row has Status `PENDING`, the `deviate prd pre` command will halt and display this table to the human operator. The human MUST resolve each PENDING row before PRD can proceed.

## Source Registry

| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-001 | Explore_MD | `specs/005-acceptance-gates/explore.md` | Problem Definition declares Option A: no new `acceptance.md` artifact; enriches `plan.md`. |
| SRC-002 | Codebase_File | `src/deviate/state/ledger.py:81` | `TaskRecord` model lacks `acceptance_criteria`; `extra="forbid"` at line 98. |
| SRC-003 | Explore_MD | `specs/005-acceptance-gates/explore.md` | Scope Sizing defers Red-checkpoint storage to "`.deviate/` or the task ledger". |
| SRC-004 | Codebase_File | `src/deviate/cli/micro.py:1123` | RED phase raises `PhaseFailedError` when tests pass (returncode 0). |
| SRC-005 | Codebase_File | `src/deviate/cli/micro.py:1298` | GREEN phase sets `train_feedback` and returns on test failure; not a hard gate. |
| SRC-006 | Codebase_File | `src/deviate/cli/micro.py:2500` | REFACTOR calls `_run_test_cmd(root)` without inspecting the result. |
| SRC-007 | Constitution | `specs/constitution.md` | §3 "GREEN phase must pass all tests" and "REFACTOR phase runs regression gate". |
| SRC-008 | Manifest | `mise.toml` | `[tasks.test]` uses `uv run pytest --testmon-noselect tests/ -v`. |
| SRC-009 | Codebase_File | `src/deviate/core/validation.py:112` | `validate_acceptance_contract` enforces `AC-PLAN-NNN` structure. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | `acceptance-gates` |
| EPIC_ID | `005-acceptance-gates` |
| GIT_BRANCH | `main` |
| SPEC_TARGET_DESIGN | `specs/005-acceptance-gates/design.md` |
| SPEC_TARGET_DATAMODEL | `specs/005-acceptance-gates/data-model.md` |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the `prd` skill |
