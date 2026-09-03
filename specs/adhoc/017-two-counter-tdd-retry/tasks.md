# Implementation Tasks: `feat/adhoc/017-two-counter-tdd-retry`

## Phase 1: Persist `SessionState` Retry Counters
**Goal**: Store `green_attempts` and `red_attempts` on `SessionState`. Copy both integers through every constructor path. Load missing keys as 0.

### Tasks

- TSK-017-01: Persist `green_attempts` and `red_attempts` on `SessionState`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_state/test_config.py -q`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/state/config.py`
    - `tests/unit/test_state/test_config.py`
  - **Rationale**: US-017-03 and `AC-PLAN-003` require both counters to survive `save`, reload, and phase change. `SessionState` at `src/deviate/state/config.py:255` has `train_feedback` and `pending_judge_action` but no retry counters. `transition_to` at line 287 and `force_transition_to` at line 302 list fields explicitly, so a new default-0 field is dropped on every phase change. Tests in `tests/unit/test_state/test_config.py` pin defaults, JSON round-trip, missing-key load, and transition copy. Constitution §1 Session Continuity and §2 session JSON under `.deviate/` own this surface.
  - **Details**:
    - **Red**: In `tests/unit/test_state/test_config.py` `TestSessionState`, extend `test_default_values` so a fresh `SessionState()` has `green_attempts == 0` and `red_attempts == 0`. Add `test_json_round_trip_persists_retry_counters`: construct `SessionState(green_attempts=2, red_attempts=1)`, `save` to a temp `.deviate/session.json`, `load` in a new object, assert both integers restore. Add `test_missing_counter_keys_load_as_zero`: write JSON that omits both keys, `load`, assert 0/0 never `None`. Add `test_transition_to_copies_retry_counters` and `test_force_transition_to_copies_retry_counters`: set non-zero counters, call each method, assert the new session keeps the same integers.
    - **Green**: In `src/deviate/state/config.py` `SessionState`, add `green_attempts: int = 0` and `red_attempts: int = 0`. Pass both into `transition_to` and `force_transition_to`. Keep Pydantic defaults so pre-existing session JSON without the keys loads as 0/0. Do not add a schema-bump file. Do not un-gitignore `.deviate/session.json`.
    - **Refactor**: Keep field order next to `train_feedback` / `pending_judge_action` / `failure_kind`. Reuse `model_dump_json` in `save` at line 317. Do not invent a second persistence path.
    - **Edge Cases**: Missing session file still returns `cls()` with 0/0 via `load` at line 322. A GREEN to JUDGE phase change must not zero the counters. Extra unknown JSON keys stay forbidden if `extra` is already forbid; new fields only.
    - **Acceptance**: All new assertions pass. Existing `TestSessionState` tests still pass. `save` / `load` round-trip non-zero counters. `transition_to` and `force_transition_to` copy both integers.

---

## Phase 2: Two-Counter TDD Loop
**Goal**: Replace the in-memory `train_attempts` budget in `_run_tdd_cycle` with session counters. Train GREEN three times, then escalate. Stop after three RED escalates.

### Tasks

- TSK-017-02: Train GREEN three times on `revert_to_red`, then escalate
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_two_counter_retry.py -k revert_to_red -q`
  - **Estimated Time**: 90 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_two_counter_retry.py`
  - **Rationale**: US-017-01 and `AC-PLAN-001` require three `revert_to_red` outcomes against one RED contract to train GREEN, then escalate. `_run_tdd_cycle` at `src/deviate/cli/micro.py:2932` sets `train_attempts = 0` and `max_train_attempts = 3` on every entry. Lines 3005–3013 raise `TRAIN_EXHAUSTED` when that single counter reaches 3. The new loop seeds from `session.green_attempts`, increments on each `revert_to_red`, and escalates when `green_attempts` reaches 3 instead of printing `TRAIN_EXHAUSTED` on cycle 1. Constitution §1 Micro-layer TDD (RED → GREEN → JUDGE → REFACTOR) stays intact. Session Continuity keeps one LLM session across RED → GREEN → REFACTOR.
  - **Details**:
    - **Red**: Create `tests/unit/test_micro/test_two_counter_retry.py`. Add `test_always_revert_to_red_trains_green_three_times_then_escalates`. Stub `_run_judge_phase` to set `pending_judge_action` to `revert_to_red` every pass. Stub `_run_red_phase` / `_run_green_phase`. Mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess`. Seed `SessionState.green_attempts = 0`. Drive `_run_tdd_cycle`. Assert `green_attempts` increments on each `revert_to_red`. Assert a new `_run_red_phase` runs after 3 trains. Assert stdout does not contain `TRAIN_EXHAUSTED` on that first GREEN cycle. Assert RED `session.red_commit_sha` and GREEN `train_feedback` stay for trains 1–3. Add `test_counters_persist_across_session_reload`: increment, `save`, `SessionState.load` in a new object, re-enter `_run_tdd_cycle`, assert the runner does not assign a local `train_attempts = 0` that wipes the loaded integers.
    - **Green**: In `_run_tdd_cycle` (`src/deviate/cli/micro.py:2893`), seed from `session.green_attempts` and `session.red_attempts`. Delete the local `train_attempts = 0` initialization. On `revert_to_red` (implementation wrong, test stands): keep RED, keep `train_feedback`, add 1 to `green_attempts`, call `session.save(session_path)`, retry GREEN up to 3. When `green_attempts` reaches 3, escalate (reset `green_attempts` to 0, add 1 to `red_attempts`, reuse `_resolve_pre_red_sha` / `_execute_rollback`) instead of raising `TRAIN_EXHAUSTED`. First GREEN of a fresh RED does not increment `green_attempts`. Optionally pass `green_attempts` into `TrainIndicator.render` as `attempt` so GREEN 1/3–3/3 stays meaningful. Keep the literal `TRAIN` token. Do not edit `_run_execute_phase` `max_judge_attempts = 3` at line 3208.
    - **Refactor**: Name the GREEN cap `3` next to the RED cap `3` in one place inside `_run_tdd_cycle`. Remove dead `train_attempts` assignments at the former lines 2960 and 3078 once TSK-017-03 lands; until then, stop zeroing on `revert_to_red`.
    - **Edge Cases**: Crash mid-GREEN-train: re-entry reads `session.green_attempts` and does not zero the budget. `no_judge` still skips JUDGE; map post-cleanup GREEN retries onto `green_attempts` only when they already share this loop. Do not invoke un-mocked `_run_pytest`.
    - **Acceptance**: Always-`revert_to_red` stub trains GREEN three times, then escalates. Cycle 1 does not print `TRAIN_EXHAUSTED`. Reload restores the saved integers. Constitution §3 coverage target stays ≥ 80%. Full suite stays under 30 seconds via the mock.
  - **Dependency**: TSK-017-01

- TSK-017-03: Escalate on `revert_before` and stop after three escalates
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore tests/unit/test_micro/test_two_counter_retry.py -k revert_before -q`
  - **Estimated Time**: 90 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_two_counter_retry.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-017-02, US-017-03, and `AC-PLAN-002` require `revert_before` to escalate immediately and stop after three escalates. Today `_run_tdd_cycle` at `src/deviate/cli/micro.py:3074` zeros `train_attempts` on `revert_before` and re-dispatches RED, which empirically loops (181 restarts). `TestRunnerLoopRestartsRedOnRevertBefore` at `tests/unit/test_cli/test_micro.py:4231` documents that reset; retarget it to escalate accounting. `_finish_tdd_cycle` at line 2809 must zero both counters on success and on `TRAIN_EXHAUSTED` so the next task starts at 0/0. Constitution §1 Git Isolation: escalate reuses the existing pre-RED SHA; counters live in gitignored `.deviate/session.json`.
  - **Details**:
    - **Red**: Add `test_always_revert_before_stops_after_three_escalates` in `tests/unit/test_micro/test_two_counter_retry.py`. Stub JUDGE to always set `pending_judge_action` to `revert_before`. Stub `_run_red_phase` / `_run_green_phase`. Mock `_run_pytest`. Assert the runner consumes each `revert_before` once. Assert `red_attempts` increments and `green_attempts` resets to 0 on each escalate. Assert `TRAIN_EXHAUSTED` and `PhaseFailedError` after exactly three escalates. Assert no fourth `_run_red_phase`. In `tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore`, keep the RED restart pin. Assert `red_attempts` increments, `green_attempts` is 0, and a third escalate stops. Add a pin that `_finish_tdd_cycle` writes `green_attempts = 0` and `red_attempts = 0` on a successful forward route.
    - **Green**: On escalate (`revert_before`, or GREEN budget exhausted from TSK-017-02): reuse `_resolve_pre_red_sha` / `_execute_rollback`; set `green_attempts = 0`; add 1 to `red_attempts`; `session.save`; consume `pending_judge_action` exactly once (clear after the increment, matching today's one-shot clear at line 3103). Evaluate `red_attempts >= 3` before another `_run_red_phase`. If the cap is hit, print `TRAIN_EXHAUSTED`, zero both counters, save, raise `PhaseFailedError`. In `_finish_tdd_cycle`, set both counters to 0 on every successful exit (`skip_refactor`, `continue_refactor`, `proceed_to_refactor_no_diff`, CLI `no_refactor`) and save. Retry RED still uses `bypass_phase_done=True` so a fresh RED row is appended (constitution §1 append-only ledgers). Do not replace `_execute_rollback` / `_resolve_pre_red_sha`. Do not edit `_run_execute_phase`.
    - **Refactor**: Share one escalate helper used by `revert_before` and GREEN-budget exhaust so the increment/save/consume order stays identical. Delete remaining `train_attempts = 0` writes.
    - **Edge Cases**: Crash after escalate increment but before the new RED commit: resume must not double-increment on the same pending `revert_before`. Remaining GREEN tries are not burned when the test is wrong. An always-`revert_before` stub terminates in 3 escalates, never hundreds of scratch restarts. Next task on the same session starts at 0/0.
    - **Acceptance**: Third escalate prints `TRAIN_EXHAUSTED` and raises `PhaseFailedError`. Fourth `_run_red_phase` does not run. `TestRunnerLoopRestartsRedOnRevertBefore` still dispatches a second RED on the first `revert_before`. Successful `_finish_tdd_cycle` zeros both counters.
  - **Dependency**: TSK-017-02

---

## Phase 3: Escalate Note for Retry RED
**Goal**: Give the retry RED a short failure note. Omit the raw GREEN dump from the escalate prompt.

### Tasks

- TSK-017-04: Inject a short escalate note, not the GREEN dump
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_micro/test_two_counter_retry.py -k escalate -q`
  - **Estimated Time**: 45 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_two_counter_retry.py`
  - **Rationale**: US-017-02 and `AC-PLAN-004` require escalate RED to receive a short `previous cycle failed because …` note. `_run_red_phase` at `src/deviate/cli/micro.py:1196` builds `prompt = _build_auto_prompt("red", task, root, train_feedback=session.train_feedback)`. `_build_auto_prompt` at line 1021 injects that string as `{train_feedback}`. Today the `revert_before` path keeps the GREEN dump on `session.train_feedback` and forwards it to the retry RED. GREEN-train (`revert_to_red`) still keeps the existing `train_feedback` for the next GREEN.
  - **Details**:
    - **Red**: Add `test_escalate_injects_short_note_not_green_dump` in `tests/unit/test_micro/test_two_counter_retry.py`. After GREEN stores a long `train_feedback` dump that includes `<test_output>` and a full rationale, stub JUDGE to return `revert_before`. Capture the `train_feedback` passed into `_build_auto_prompt` (or the `session.train_feedback` that `_run_red_phase` forwards). Assert the retry RED prompt contains a short `previous cycle failed because` note. Assert it omits raw GREEN `<test_output>` and the full rationale dump. Add a companion assertion that `revert_to_red` still keeps the existing GREEN `train_feedback` for the next GREEN. Mock `_run_pytest`.
    - **Green**: On escalate in `_run_tdd_cycle`, wipe GREEN `train_feedback` and set a short note of the form `previous cycle failed because …`. Pass that note as `{train_feedback}` for the retry RED. Do not change `_build_auto_prompt` signature; `_run_red_phase` already threads `session.train_feedback`. Keep GREEN-train `train_feedback` on `revert_to_red`.
    - **Refactor**: Build the note in one helper so the escalate branch does not inline string format twice. Keep the note short enough that it is not a dump.
    - **Edge Cases**: Empty GREEN `train_feedback` still yields a short note, not `None`. Escalate must not forward `<test_output>`. GREEN-train path must not wipe `train_feedback`.
    - **Acceptance**: Escalate RED prompt contains the short note and omits the GREEN dump. `revert_to_red` still keeps GREEN `train_feedback`.
  - **Dependency**: TSK-017-03

---

## Phase 4: Coerce Matrix, Orchestration Pins, Spec Alignment
**Goal**: Keep JUDGE verbs, the coerce matrix, and 3/3 caps. Pin stub-JUDGE loops. Update API, architecture, and CHANGELOG.

### Tasks

- TSK-017-05: Keep JUDGE verbs, coerce matrix, and 3/3 caps; align specs
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore tests/unit/test_state/test_config.py tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_two_counter_retry.py -q`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/micro.py`
    - `tests/unit/test_micro/test_orchestration.py`
    - `tests/unit/test_micro/test_two_counter_retry.py`
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `CHANGELOG.md`
  - **Rationale**: US-017-02 and `AC-PLAN-005` require `_coerce_judge_action` at `src/deviate/cli/micro.py:2060` to keep mapping `failure_kind` `test_defect` / `no_failing_test` plus `COMPLIANCE_VIOLATION` to `revert_before`. `_JUDGE_ACTIONS` at line 2049 stays the five-verb frozenset. Both TDD caps stay 3. EXECUTE `max_judge_attempts = 3` at line 3208 stays out of contract. Orchestration pins in `tests/unit/test_micro/test_orchestration.py` (HITL / forward-route `TRAIN_EXHAUSTED` negatives near lines 564, 731, 1544, 1602) must keep passing. Spec-alignment mandate and constitution §5 require `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` `[Unreleased]` in the same implementation change.
  - **Details**:
    - **Red**: In `tests/unit/test_micro/test_two_counter_retry.py` or `tests/unit/test_micro/test_orchestration.py`, add a stub-JUDGE case with `failure_kind` `test_defect` (and `no_failing_test`) on a `COMPLIANCE_VIOLATION`. Assert `_coerce_judge_action` still returns `revert_before` and the TDD loop escalates now. Assert `_JUDGE_ACTIONS` is unchanged. Assert GREEN and RED caps are 3. Assert `_run_execute_phase` still uses `max_judge_attempts = 3` (do not edit that function). Keep existing HITL / forward-route tests that assert `TRAIN_EXHAUSTED` is the wrong path. Mock `_run_pytest` on every path that would invoke it. Extend `test_orchestration.py` with always-`revert_to_red` and always-`revert_before` stub-JUDGE loops if those classes do not already call the new two-counter file.
    - **Green**: Do not change `_coerce_judge_action` body. Do not rename JUDGE verbs. Do not add `next_action` values. Confirm `_run_tdd_cycle` caps both budgets at 3. Leave `_run_execute_phase` untouched. In `specs/DeviaTDD-api.md` (~662, ~795, ~1346, ~1394), replace `max_train_attempts = 3` and “resetting `train_attempts`” with `green_attempts` / `red_attempts` (max 3 each), GREEN-train vs escalate, `TRAIN_EXHAUSTED` only after three RED escalates, and session JSON persistence. Keep the `_coerce_judge_action` override. In `specs/DeviaTDD-architecture.md` (~51, ~282, ~289, ~400, ~659), replace the ASCII loop and Train Gates `max_train_attempts = 3` language with GREEN train 3 then escalate, escalate-now on `revert_before`, and `TRAIN_EXHAUSTED` after three escalates. Append a Changed (or Fixed) bullet under `CHANGELOG.md` `[Unreleased]`: GREEN trains three times then escalates; three RED escalates print `TRAIN_EXHAUSTED` and stop the infinite `revert_before` loop.
    - **Refactor**: Share stub-JUDGE fixtures between `test_two_counter_retry.py` and `test_orchestration.py` only if a helper already exists; do not invent a new test framework.
    - **Edge Cases**: Introducing a new `next_action` token fails the `_JUDGE_ACTIONS` pin. Product / macro / meso files stay unmodified. `TrainIndicator` literal `TRAIN` token stays. Do not retarget EXECUTE `max_judge_attempts`.
    - **Acceptance**: Coerce matrix still forces `revert_before` for `test_defect` / `no_failing_test`. Caps stay 3/3. Orchestration negatives still pass. API and architecture text describe the two-counter contract. CHANGELOG `[Unreleased]` has the user-visible bullet. Verification command exits 0.
  - **Dependency**: TSK-017-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4

**Critical Dependency Chains**:
- TSK-017-01 must precede TSK-017-02
- TSK-017-02 must precede TSK-017-03
- TSK-017-03 must precede TSK-017-04
- TSK-017-04 must precede TSK-017-05

**Risk Hotspots**:
- Always-`revert_before` stub loops forever unless `red_attempts >= 3` is evaluated before the next RED
- GREEN-budget exhaust raises `TRAIN_EXHAUSTED` on cycle 1 unless exhaust escalates
- `transition_to` drops new counters unless both fields are copied
- Un-mocked `_run_pytest` blows the 30s suite budget
- Escalate RED still receives the GREEN dump unless `train_feedback` is wiped on escalate
- Next task inherits a spent budget unless `_finish_tdd_cycle` and `TRAIN_EXHAUSTED` zero both counters
- EXECUTE `max_judge_attempts` loop is retargeted by accident

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_two_counter_retry.py`

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/017-two-counter-tdd-retry/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Tests that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3).

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
