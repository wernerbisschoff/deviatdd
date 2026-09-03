---
title: "Two-Counter TDD Retry — GREEN Train vs RED Escalate"
labels: [bugfix, enhancement, adhoc, vertical-slice, micro, train]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-017
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/017-two-counter-tdd-retry.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/micro.py` — TARGET: `_run_tdd_cycle` (~2932–3175) holds a local `train_attempts = 0` / `max_train_attempts = 3` and **zeros** it on `pending_judge_action == "revert_before"` (~2959 and ~3074–3078). Replace with session-backed `green_attempts` / `red_attempts`. Escalate after 3 GREEN trains; `TRAIN_EXHAUSTED` only after 3 RED escalates. Keep `_coerce_judge_action` mapping `test_defect` / `no_failing_test` → `revert_before`.
  - `src/deviate/state/config.py` — TARGET: `SessionState` (~255–331). Add `green_attempts: int = 0` and `red_attempts: int = 0`. Copy both fields through `transition_to` / `force_transition_to` (those constructors currently list fields explicitly and would silently drop new counters). Persist via existing `save()` to `.deviate/session.json`.
  - `src/deviate/cli/micro.py::_run_red_phase` (~1165) / `_build_auto_prompt` (~1021) — TARGET: escalate path must wipe GREEN `train_feedback` and inject a **short** escalate note (`previous cycle failed because …`) as `{train_feedback}` for the retry RED; do not forward the raw GREEN dump.
  - `src/deviate/ui/pipeline.py` — REFERENCE: `TrainIndicator` still renders GREEN 1/3–3/3. Optionally surface RED escalate `n/3` without breaking the literal `TRAIN` token tests in `tests/unit/test_ui/test_pipeline.py`.
  - `tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore` (~4252) — TARGET: today documents that `revert_before` **resets** `train_attempts`; retarget so `revert_before` is an escalate (`red_attempts += 1`, `green_attempts = 0`) and a third escalate stops.
  - `tests/unit/test_micro/test_orchestration.py` — TARGET: TRAIN / `TRAIN_EXHAUSTED` / HITL pins (~564, ~731, ~1544, ~1602). Add always-`revert_before` and always-`revert_to_red` stub-JUDGE loops.
  - `tests/unit/test_state/test_config.py` — TARGET: JSON round-trip + `transition_to` copy of the new counters.
  - `specs/DeviaTDD-api.md` (~662, ~795, ~1346, ~1359, ~1394) and `specs/DeviaTDD-architecture.md` (~51, ~282, ~289, ~400, ~659) — TARGET: replace single `max_train_attempts = 3` / "resetting `train_attempts`" language with the two-counter contract (spec-alignment mandate).
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible retry-budget change.

## The Problem Contract

`deviate micro` keeps one in-memory `train_attempts` (max 3). `TRAIN_EXHAUSTED` (human handoff) only increments on GREEN / `revert_to_red` retries. When JUDGE returns `next_action: revert_before` or `failure_kind: test_defect`, the runner zeros `train_attempts` and re-runs RED. Empirically a local toy cycle then infinite-loops (181 full scratch restarts in ~90s) and never hands off. `.deviate/session.json` is gitignored, so `git reset` to pre-RED does not roll the session back — but `train_attempts` is not stored there anyway. Operators need two persisted counters so GREEN trains a standing test three times, a bad test escalates immediately, and three escalates return to the human.

## Scope Boundaries

### Hard Inclusions

- Persist `green_attempts` (train; one RED commit / one failing-test contract; max 3; exhaust → escalate) and `red_attempts` (escalate; one task; max 3; exhaust → `TRAIN_EXHAUSTED` / return to human) on `SessionState`, saved on every increment so they survive `git reset --hard` in-process (`git clean -fd` without `-x` already preserves gitignored `.deviate/`) **and** a process crash that reloads `.deviate/session.json`.
- Seed the TDD loop from `session.green_attempts` / `session.red_attempts`; delete the local `train_attempts = 0` initialization that zeros the budget on every `_run_tdd_cycle` entry and on every `revert_before`.
- **GREEN train** (`next_action: revert_to_red`, implementation wrong, test stands): discard GREEN, keep RED, keep `train_feedback` for the next GREEN, increment `green_attempts`, retry GREEN up to 3. Do **not** raise `TRAIN_EXHAUSTED` when the GREEN budget exhausts — escalate instead.
- **Escalate** (fresh RED) after 3 GREEN trains **or** when JUDGE says `revert_before` / `test_defect` (test itself is wrong): git reset to the existing `revert_before` pre-RED boundary; wipe GREEN `train_feedback`; reset `green_attempts` to 0; increment `red_attempts`; re-author RED with a short escalate note; if `red_attempts >= 3`, stop and hand off (`TRAIN_EXHAUSTED` / `PhaseFailedError`). Do not loop.
- Keep JUDGE verb names: `revert_to_red` = GREEN-only train; `revert_before` = escalate now (do not burn remaining GREEN tries when the test is wrong).
- Keep the runner coerce: `failure_kind: test_defect` / `no_failing_test` on a violation still maps to `revert_before` via `_coerce_judge_action`.
- Copy the new counters through `SessionState.transition_to` / `force_transition_to` so a phase change cannot drop them.
- Clear both counters when the task leaves the TDD retry loop successfully (`_finish_tdd_cycle`) or after `TRAIN_EXHAUSTED`, so a later task on the same session does not inherit a spent budget.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit; append a `CHANGELOG.md` `[Unreleased]` bullet.

### Defensive Exclusions

- Do **not** change the 3/3 caps (keep `green_attempts` max 3 and `red_attempts` max 3 unless a later issue says otherwise).
- Do **not** rename JUDGE verbs or add new `next_action` values.
- Do **not** change Product / Macro / Meso layers, flow authoring, or `specs/_product/`.
- Do **not** un-gitignore `.deviate/session.json`; persistence depends on it surviving `git clean -fd`.
- Do **not** revert operator-local `.deviate/config.toml` (backend/transport/model/timeout).
- Do **not** retarget the EXECUTE-mode `max_judge_attempts = 3` loop; this issue is TDD `_run_tdd_cycle` only.
- Do **not** replace `_execute_rollback` / `_resolve_pre_red_sha` boundary mechanics; escalate reuses the existing `revert_before` pre-RED SHA.
- Do **not** forward the raw GREEN test dump as the escalate RED prompt; only a short note.
- Do **not** invoke `deviate.cli.micro._run_pytest` un-mocked in tests (AGENTS.md suite-budget mandate).

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-017`
- **Acceptance Criteria Tokens**: `AC-ADHOC-017-01`, `AC-ADHOC-017-02`, `AC-ADHOC-017-03`, `AC-ADHOC-017-04`, `AC-ADHOC-017-05`
- **Data Model Entities**: `SessionState.green_attempts`, `SessionState.red_attempts` (integers, default 0; not ledger rows)
- **Spec Source Anchors**:
  - `src/deviate/cli/micro.py` ~2932–3175 — single `train_attempts` loop + zero-on-`revert_before`
  - `src/deviate/cli/micro.py` ~2070–2081 — `_coerce_judge_action` test_defect / no_failing_test override
  - `src/deviate/state/config.py` ~255–331 — `SessionState` + explicit field copy in transitions
  - `.gitignore` — `.deviate/session.json`
  - `specs/constitution.md` §1 Session Continuity / Git Isolation (session JSON under `.deviate/`; commits at phase boundaries)

## User Stories Ledger

- **US-017-01**: As a DeviaTDD operator running `deviate micro`, I want GREEN implementation retries capped at 3 against one RED contract so a wrong implementation trains GREEN without rewriting the test. *(Ref: FR-ADHOC-017)*
- **US-017-02**: As a DeviaTDD operator, I want a wrong RED test (`revert_before` / `test_defect`) to escalate immediately to a fresh RED so the runner does not burn three GREEN tries on a defective contract. *(Ref: FR-ADHOC-017)*
- **US-017-03**: As a DeviaTDD operator, I want three RED escalates on one task to stop with `TRAIN_EXHAUSTED` and return control to me so a stub JUDGE that always `revert_before`s cannot infinite-loop. *(Ref: FR-ADHOC-017)*

## Acceptance Outline

- **AO-017** *(Ref: AC-ADHOC-017-01, US-017-01)*: Three `revert_to_red` outcomes against one RED contract train GREEN three times, then escalate to a new RED.
  - **Happy Path**: Each `revert_to_red` discards GREEN, keeps RED, keeps `train_feedback`, increments `green_attempts`, retries GREEN. After `green_attempts` reaches 3, the runner escalates (new RED) instead of raising `TRAIN_EXHAUSTED` on that first cycle.
  - **Error Category**: A JUDGE that always `revert_to_red`s never `TRAIN_EXHAUSTED`s before the first escalate.
  - **Boundary Category**: `green_attempts` is not reset on `revert_to_red`; it resets only as part of an escalate.

- **AO-017** *(Ref: AC-ADHOC-017-02, US-017-02, US-017-03)*: Immediate escalate on `revert_before` / `test_defect`, with a hard stop after three escalates.
  - **Happy Path**: `revert_before` (including coerce from `failure_kind: test_defect` / `no_failing_test` on a violation) skips remaining GREEN tries, resets `green_attempts` to 0, increments `red_attempts`, re-authors RED.
  - **Error Category**: After `red_attempts >= 3`, the runner prints `TRAIN_EXHAUSTED`, raises `PhaseFailedError`, and does not dispatch a fourth RED.
  - **Boundary Category**: A stub JUDGE that always `revert_before`s stops after exactly three escalates and returns to the human.

- **AO-017** *(Ref: AC-ADHOC-017-03)*: Counters survive worktree reset and process crash.
  - **Happy Path**: After increment, `SessionState.save` writes both integers to `.deviate/session.json`. Reloading the session (new process or post-`git reset --hard`) restores the same counts.
  - **Error Category**: Missing session file loads defaults of 0/0 (fresh task), never `None`.
  - **Boundary Category**: `transition_to` / `force_transition_to` copy both counters; a GREEN→JUDGE phase change cannot zero them.

- **AO-017** *(Ref: AC-ADHOC-017-04)*: Escalate RED receives a short note, not the GREEN dump.
  - **Happy Path**: Escalate wipes GREEN `train_feedback` and sets a short escalate note of the form `previous cycle failed because …` that `_build_auto_prompt(..., train_feedback=...)` injects into the retry RED.
  - **Error Category**: Raw GREEN `<test_output>` / full rationale dump is absent from the escalate RED prompt.
  - **Boundary Category**: GREEN-train (`revert_to_red`) still keeps the existing `train_feedback` for the next GREEN.

- **AO-017** *(Ref: AC-ADHOC-017-05)*: Verb names, coerce matrix, and 3/3 caps are unchanged.
  - **Happy Path**: `_coerce_judge_action` still forces `revert_before` for `test_defect` / `no_failing_test` on a violation; caps remain 3 and 3.
  - **Error Category**: Introducing a new `next_action` token or changing EXECUTE `max_judge_attempts` is out of contract.
  - **Boundary Category**: Product / macro / meso files are unmodified.

## Edge Cases and Boundaries

- Crash mid-GREEN-train: re-entering `_run_tdd_cycle` must **not** assign `train_attempts = 0`; it must resume from `session.green_attempts` / `session.red_attempts`.
- Crash after escalate increment but before the new RED commit: resume must not double-increment `red_attempts` on the same pending `revert_before` (consume `pending_judge_action` exactly once, as today's one-shot clear already does).
- Successful `_finish_tdd_cycle` (forward routes `continue_refactor` / `proceed_to_refactor_no_diff` / `skip_refactor`) clears both counters so the next task on the same session starts at 0/0.
- `no_judge` still skips JUDGE; this issue does not invent a second budget for `--no-judge` GREEN post-cleanup retries beyond mapping them onto `green_attempts`.
- First GREEN of a fresh RED does not increment `green_attempts`; increment happens on each `revert_to_red` train, matching today's "increment on rejection" cadence so `TrainIndicator` 1/3–3/3 stays meaningful.
- `red_attempts >= 3` is evaluated **before** dispatching another RED, including the escalate that would have been the fourth restart.
- Pre-existing session JSON without the new keys must load with 0/0 (Pydantic defaults); do not require a session schema bump file.
- Do not treat a missing Product-layer flow as work; `flow_refs` stays empty.

## Performance Constraints

- L_max: ≤ 500ms CLI init; counter increment + `SessionState.save` of `.deviate/session.json` ≤ 50ms on the hot TDD loop (no extra subprocess, no extra git).
- Throughput: no additional agent calls versus today's loop; the change only bounds existing retries. Full test suite remains < 30s; tests that would drive `_run_pytest` must mock `deviate.cli.micro._run_pytest`.
- Anti-loop: an always-`revert_before` stub must terminate in 3 escalates, never hundreds of scratch restarts.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_state/test_config.py` — `SessionState` round-trip of `green_attempts` / `red_attempts`; `transition_to` / `force_transition_to` copy; missing-key load defaults to 0.
  - `tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore` — retarget from "reset train_attempts" to escalate accounting; third escalate stops.
  - New (or extended) `tests/unit/test_micro/test_orchestration.py` / `tests/unit/test_micro/test_two_counter_retry.py`:
    - `test_always_revert_to_red_trains_green_three_times_then_escalates` — no `TRAIN_EXHAUSTED` on the first cycle.
    - `test_always_revert_before_stops_after_three_escalates` — `TRAIN_EXHAUSTED`, no fourth `_run_red_phase`.
    - `test_counters_persist_across_session_reload` — save/load after increment.
    - `test_escalate_injects_short_note_not_green_dump`.
- **Integration Sandbox Targets**:
  - Stub-JUDGE `_run_tdd_cycle` with patched `_run_red_phase` / `_run_green_phase` / `_run_judge_phase` (no real agent, no un-mocked pytest) covering both always-`revert_before` and always-`revert_to_red` matrices plus `failure_kind: test_defect` coerce.

## Demonstration Path

```bash
# Mocked TDD-loop pins (no live agent, no un-mocked pytest)
uv run pytest tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore tests/unit/test_state/test_config.py tests/unit/test_micro/test_orchestration.py -q
# After implementation, the always-revert_before stub must print TRAIN_EXHAUSTED
# and the always-revert_to_red stub must escalate rather than exhaust on cycle 1.
```
