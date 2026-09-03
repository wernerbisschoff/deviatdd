## Plan Summary

- **Issue**: ISS-ADH-017 — Two-Counter TDD Retry — GREEN Train vs RED Escalate
- **Implementation Strategy**: Replace the in-memory `train_attempts` budget in `_run_tdd_cycle` with persisted `SessionState.green_attempts` and `SessionState.red_attempts`. GREEN trains three times against one RED contract, then escalates. `revert_before` / `test_defect` escalates immediately. Three escalates print `TRAIN_EXHAUSTED` and return to the operator.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Product Layer Anchors

- **Flow References**: []
- **Source**: `specs/adhoc/issues/017-two-counter-tdd-retry.md` (frontmatter field: `flow_refs`)
- **Release Context**: `specs/_product/release-next.md` Goal ships FLOW-04 (RPC streaming into a 10-line TUI). This issue is orthogonal: it bounds TDD retry in C1, not the RPC/TUI transport.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns phase state and the TDD runner)

## Acceptance Contract

**Scenario AC-PLAN-001: Train GREEN three times on `revert_to_red`, then escalate**
- **Source Outline**: `AO-017`
- **Upstream Traceability**: `US-017-01`, `FR-ADHOC-017`, `AC-ADHOC-017-01`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:2932`
- **Given**: `_run_tdd_cycle` seeds from `session.green_attempts` and a stub JUDGE returns `revert_to_red` every pass.
- **When**: the runner trains GREEN against one standing RED contract.
- **Then**: the runner increments `green_attempts` on each `revert_to_red` and escalates to a new RED after 3 without printing `TRAIN_EXHAUSTED`.
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Escalate on `revert_before` and stop after three escalates**
- **Source Outline**: `AO-017`
- **Upstream Traceability**: `US-017-02`, `US-017-03`, `FR-ADHOC-017`, `AC-ADHOC-017-02`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:3074`
- **Given**: `_run_tdd_cycle` has a stub JUDGE that always sets `pending_judge_action` to `revert_before`.
- **When**: the runner consumes each `revert_before` once and considers a fresh RED.
- **Then**: the runner stops after exactly three escalates with `TRAIN_EXHAUSTED` and no fourth `_run_red_phase`.
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Persist both counters across save, reload, and phase transition**
- **Source Outline**: `AO-017`
- **Upstream Traceability**: `US-017-03`, `FR-ADHOC-017`, `AC-ADHOC-017-03`
- **Current-Code Evidence**: `src/deviate/state/config.py:287`
- **Given**: `SessionState` holds non-zero `green_attempts` and `red_attempts` after `save`.
- **When**: a new process loads `.deviate/session.json` or `transition_to` / `force_transition_to` copies the session.
- **Then**: both counters restore as the saved integers, missing keys load as 0, and a phase change does not zero them.
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Inject a short escalate note, not the GREEN dump**
- **Source Outline**: `AO-017`
- **Upstream Traceability**: `US-017-02`, `FR-ADHOC-017`, `AC-ADHOC-017-04`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:1021`
- **Given**: JUDGE returns `revert_before` after GREEN stored a long `train_feedback` dump.
- **When**: the runner escalates and `_build_auto_prompt` builds the retry RED prompt with `{train_feedback}`.
- **Then**: the prompt contains a short `previous cycle failed because …` note and omits the raw GREEN dump.
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Keep JUDGE verbs, coerce matrix, and 3/3 caps**
- **Source Outline**: `AO-017`
- **Upstream Traceability**: `US-017-02`, `FR-ADHOC-017`, `AC-ADHOC-017-05`
- **Current-Code Evidence**: `src/deviate/cli/micro.py:2060`
- **Given**: `_coerce_judge_action` receives `failure_kind` `test_defect` or `no_failing_test` on a `COMPLIANCE_VIOLATION`.
- **When**: the runner maps the verdict and applies the TDD retry caps.
- **Then**: the action stays `revert_before`, both caps stay 3, and `_JUDGE_ACTIONS` is unchanged.
- **Verification Mode**: automated

## Workstation Mapping

- **`src/deviate/state/config.py:255` (`SessionState`)**: TARGET — add persisted retry counters and copy them through every constructor path.
  - **Current State**: `SessionState` has `train_feedback`, `pending_judge_action`, and `failure_kind`. It has no `green_attempts` or `red_attempts`. `transition_to` (line 287) and `force_transition_to` (line 302) list fields explicitly, so a new field with a default of 0 is dropped on every phase change. `save` (line 317) writes `model_dump_json` to `.deviate/session.json`. `load` (line 322) returns `cls()` when the file is missing.
  - **Changes Required**: Add `green_attempts: int = 0` and `red_attempts: int = 0`. Pass both into `transition_to` and `force_transition_to`. Keep Pydantic defaults so a pre-existing session JSON without the keys loads as 0/0. Do not add a schema-bump file.
  - **Integration Surface**: `_run_tdd_cycle` and `_finish_tdd_cycle` in `src/deviate/cli/micro.py` read and write the same `SessionState` object and call `session.save(session_path)` after each increment.

- **`src/deviate/cli/micro.py:2893` (`_run_tdd_cycle`)**: TARGET — replace the local `train_attempts` budget with the two session counters.
  - **Current State**: Line 2932 sets `train_attempts = 0` and `max_train_attempts = 3` on every entry. Line 2960 and line 3078 set `train_attempts = 0` on `revert_before`. Lines 3005–3013 and 3125–3133 raise `TRAIN_EXHAUSTED` when that single counter reaches 3. The `revert_before` branch re-dispatches `_run_red_phase(..., bypass_phase_done=True)` and clears `pending_judge_action` after the call (line 3103).
  - **Changes Required**: Seed from `session.green_attempts` / `session.red_attempts`. Delete the local zeroing. On `revert_to_red` (implementation wrong, test stands): keep RED, keep `train_feedback`, increment `green_attempts`, save, retry GREEN up to 3. When `green_attempts` reaches 3, escalate instead of raising `TRAIN_EXHAUSTED`. On escalate (`revert_before`, coerced `test_defect` / `no_failing_test`, or GREEN budget exhausted): reuse `_resolve_pre_red_sha` / `_execute_rollback`; set `green_attempts = 0`; increment `red_attempts`; save; consume `pending_judge_action` exactly once; if `red_attempts >= 3` before another RED, print `TRAIN_EXHAUSTED` and raise `PhaseFailedError`. Cap both budgets at 3. Do not change `_run_execute_phase` `max_judge_attempts = 3` (line 3208).
  - **Integration Surface**: `_run_red_phase` (line 1165), `_run_green_phase`, `_run_judge_phase`, `_coerce_judge_action` (line 2060), `_finish_tdd_cycle` (line 2809), `TrainIndicator.render` (optional display of GREEN 1/3–3/3).

- **`src/deviate/cli/micro.py:2809` (`_finish_tdd_cycle`)**: TARGET — clear both counters when the task leaves the TDD retry loop.
  - **Current State**: Forward routes (`skip_refactor`, `continue_refactor`, `proceed_to_refactor_no_diff`, CLI `no_refactor`) clear `pending_judge_action` / `train_feedback` / `judge_rejected` and save. They do not reset a train budget because the budget is local to `_run_tdd_cycle`.
  - **Changes Required**: Set `green_attempts = 0` and `red_attempts = 0` on every successful exit. On `TRAIN_EXHAUSTED`, zero both counters and save before `PhaseFailedError` so the next task on the same session starts at 0/0.
  - **Integration Surface**: Called at `_run_tdd_cycle` line 3177 after `judge_passed`.

- **`src/deviate/cli/micro.py:1021` (`_build_auto_prompt`) / `_run_red_phase` (line 1165)**: TARGET — escalate RED gets a short note.
  - **Current State**: `_run_red_phase` builds `prompt = _build_auto_prompt("red", task, root, train_feedback=session.train_feedback)` (line 1196). `_build_auto_prompt` injects that string as `{train_feedback}`. The `revert_before` path keeps the GREEN dump on `session.train_feedback` and forwards it to the retry RED.
  - **Changes Required**: On escalate, wipe GREEN `train_feedback` and set a short note of the form `previous cycle failed because …`. Pass that note as `{train_feedback}` for the retry RED. Keep the existing GREEN-train `train_feedback` on `revert_to_red`. Do not forward `<test_output>` or the full GREEN rationale dump on escalate.
  - **Integration Surface**: Auto RED template placeholder `{train_feedback}` already consumed by `assemble_prompt`.

- **`src/deviate/cli/micro.py:2060` (`_coerce_judge_action`)**: REFERENCE — keep the coerce matrix.
  - **Current State**: `failure_kind in {"test_defect", "no_failing_test"}` plus `COMPLIANCE_VIOLATION` returns `revert_before`. `_JUDGE_ACTIONS` is the five-verb frozenset at line 2049.
  - **Changes Required**: None to the function body. The TDD loop must keep treating the coerced `revert_before` as escalate-now.
  - **Integration Surface**: `_run_judge_phase` line 2418 already passes `failure_kind=session.failure_kind`.

- **`src/deviate/ui/pipeline.py:374` (`TrainIndicator`)**: REFERENCE — keep the literal `TRAIN` token and GREEN 1/3–3/3.
  - **Current State**: `render(attempt, maximum, phase="GREEN")` always emits `TRAIN` and cells `n/3`. Tests in `tests/unit/test_ui/test_pipeline.py` pin the token.
  - **Changes Required**: Pass `green_attempts` as `attempt` on GREEN train so 1/3–3/3 stays meaningful (first GREEN of a fresh RED does not increment). Optionally pass `phase="RED"` with `red_attempts` on escalate. Do not break the `TRAIN` token tests.
  - **Integration Surface**: `_run_tdd_cycle` call sites at lines 3017, 3137, 3155.

- **`tests/unit/test_state/test_config.py:151` (`TestSessionState`)**: TARGET — pin JSON round-trip, defaults, and transition copy.
  - **Current State**: `test_json_round_trip` (line 187) and `test_default_values` (line 152) omit the new counters. Transition tests (line 212+) assert only `current_phase`.
  - **Changes Required**: Assert defaults 0/0. Round-trip non-zero counters. Load JSON missing the keys as 0/0. Assert `transition_to` and `force_transition_to` copy both integers.
  - **Integration Surface**: `SessionState.save` / `load` / `model_validate`.

- **`tests/unit/test_cli/test_micro.py:4231` (`TestRunnerLoopRestartsRedOnRevertBefore`)**: TARGET — retarget reset-budget docs to escalate accounting.
  - **Current State**: `test_revert_before_dispatches_red_again` (line 4244) documents that `revert_before` resets `train_attempts` and dispatches a second RED. Stubs `_run_red_phase` / `_run_green_phase` / `_run_judge_phase` / `_finish_tdd_cycle`.
  - **Changes Required**: Keep the RED restart. Assert `red_attempts` increments, `green_attempts` resets to 0, and a third escalate stops with `TRAIN_EXHAUSTED`. Mock `deviate.cli.micro._run_pytest` on any path that would invoke it.
  - **Integration Surface**: `_run_tdd_cycle` with patched phase helpers.

- **`tests/unit/test_micro/test_orchestration.py`**: TARGET — add always-`revert_to_red` and always-`revert_before` stub-JUDGE loops.
  - **Current State**: Pins around lines 564, 731, 1544, 1602 assert `TRAIN_EXHAUSTED` is the wrong path for HITL / forward-route cases. No two-counter matrix exists.
  - **Changes Required**: Extend with patched `_run_red_phase` / `_run_green_phase` / `_run_judge_phase` (no live agent, no un-mocked pytest) covering both stub-JUDGE matrices plus `failure_kind: test_defect` coerce.
  - **Integration Surface**: `_run_tdd_cycle` / `deviate micro run` orchestration.

- **`tests/unit/test_micro/test_two_counter_retry.py`**: TARGET — new focused pins listed in the issue verification targets.
  - **Current State**: File does not exist.
  - **Changes Required**: Add `test_always_revert_to_red_trains_green_three_times_then_escalates` (no `TRAIN_EXHAUSTED` on cycle 1), `test_always_revert_before_stops_after_three_escalates` (`TRAIN_EXHAUSTED`, no fourth `_run_red_phase`), `test_counters_persist_across_session_reload`, `test_escalate_injects_short_note_not_green_dump`. Mock `_run_pytest`.
  - **Integration Surface**: `_run_tdd_cycle` + `SessionState.save` / `load`.

- **`specs/DeviaTDD-api.md` (~662, ~795, ~1346, ~1394)**: TARGET — replace the single-budget language.
  - **Current State**: Documents `max_train_attempts = 3` and “resetting `train_attempts`” on `revert_before`.
  - **Changes Required**: Document `green_attempts` / `red_attempts` (max 3 each), GREEN-train vs escalate, `TRAIN_EXHAUSTED` only after three RED escalates, and session JSON persistence. Keep the `_coerce_judge_action` override.
  - **Integration Surface**: Spec-alignment mandate; same commit as the code change.

- **`specs/DeviaTDD-architecture.md` (~51, ~282, ~289, ~400, ~659)**: TARGET — same two-counter contract.
  - **Current State**: ASCII loop and Train Gates section say `max_train_attempts = 3` rollbacks then `PhaseFailedError`.
  - **Changes Required**: Replace that language with GREEN train 3 then escalate, escalate-now on `revert_before`, and `TRAIN_EXHAUSTED` after three escalates. Do not rename JUDGE verbs.
  - **Integration Surface**: Spec-alignment mandate; same commit as the code change.

- **`CHANGELOG.md` (`[Unreleased]`)**: TARGET — user-visible retry-budget change.
  - **Current State**: `[Unreleased]` has Added / Changed / Fixed sections and no two-counter bullet.
  - **Changes Required**: Append a Changed (or Fixed) bullet: GREEN trains three times then escalates; three RED escalates print `TRAIN_EXHAUSTED` and stop the infinite `revert_before` loop.
  - **Integration Surface**: Constitution §5 Definition of Done.

## Implementation Strategy

- **Phase 1**: Persist counters on `SessionState`
  - **Files**: `src/deviate/state/config.py`, `tests/unit/test_state/test_config.py`
  - **Approach**: Add `green_attempts` and `red_attempts` with default 0. Copy both fields in `transition_to` and `force_transition_to`. Rely on existing `save` / `load`. Pin round-trip, missing-key defaults, and transition copy.
  - **Verification**: `uv run pytest tests/unit/test_state/test_config.py -q`

- **Phase 2**: Two-counter loop in `_run_tdd_cycle`
  - **Files**: `src/deviate/cli/micro.py`
  - **Approach**: Seed from the session. Delete `train_attempts = 0`. Map `revert_to_red` to GREEN train (`green_attempts += 1`, save, retry GREEN). Map `revert_before` / coerce / GREEN-budget exhaust to escalate (`green_attempts = 0`, `red_attempts += 1`, save, consume `pending_judge_action` once). Evaluate `red_attempts >= 3` before another RED. Clear both counters in `_finish_tdd_cycle` and on `TRAIN_EXHAUSTED`. Leave `_execute_rollback` / `_resolve_pre_red_sha` / `_coerce_judge_action` / EXECUTE `max_judge_attempts` unchanged.
  - **Verification**: `uv run pytest tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore tests/unit/test_micro/test_two_counter_retry.py -q`

- **Phase 3**: Escalate note for retry RED
  - **Files**: `src/deviate/cli/micro.py` (`_run_tdd_cycle` escalate branch, `_build_auto_prompt` consumer)
  - **Approach**: On escalate, replace GREEN `train_feedback` with a short `previous cycle failed because …` note. Keep GREEN-train feedback on `revert_to_red`. `_run_red_phase` already threads `session.train_feedback` into `_build_auto_prompt`.
  - **Verification**: `uv run pytest tests/unit/test_micro/test_two_counter_retry.py -k escalate -q`

- **Phase 4**: Orchestration pins and spec alignment
  - **Files**: `tests/unit/test_micro/test_orchestration.py`, `tests/unit/test_cli/test_micro.py`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Add always-`revert_to_red` and always-`revert_before` stub-JUDGE loops. Keep HITL / forward-route `TRAIN_EXHAUSTED` negatives. Update API and architecture text in the same commit. Append the `[Unreleased]` bullet. Mock `_run_pytest` on every path that would invoke it.
  - **Verification**: `uv run pytest tests/unit/test_cli/test_micro.py::TestRunnerLoopRestartsRedOnRevertBefore tests/unit/test_state/test_config.py tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_two_counter_retry.py -q`

## Data Flow Analysis

1. **Load**: `_run_tdd_cycle` loads `.deviate/session.json` via `SessionState.load`. Missing file yields `green_attempts=0` and `red_attempts=0`.
2. **GREEN train**: JUDGE `revert_to_red` keeps `session.red_commit_sha` and `train_feedback`. The runner adds 1 to `green_attempts`, calls `session.save`, and re-enters GREEN. `TrainIndicator` shows GREEN `n/3`.
3. **Escalate**: JUDGE `revert_before` (or coerce from `test_defect` / `no_failing_test`, or `green_attempts == 3`) rolls back to the existing pre-RED SHA. The runner sets `green_attempts=0`, adds 1 to `red_attempts`, writes a short escalate note into `train_feedback`, saves, and clears `pending_judge_action` once.
4. **Stop**: If `red_attempts >= 3` before the next `_run_red_phase`, the runner prints `TRAIN_EXHAUSTED`, zeros both counters, saves, and raises `PhaseFailedError`.
5. **Retry RED**: `_run_red_phase` passes `session.train_feedback` into `_build_auto_prompt`. The agent sees the short note, not the GREEN dump.
6. **Success**: `_finish_tdd_cycle` zeros both counters and saves so the next task starts at 0/0.
7. **Crash resume**: `.gitignore` keeps `.deviate/session.json` out of git. `git reset --hard` and `git clean -fd` (no `-x`) leave the file. A new process reloads the same integers. Re-entry does not assign `train_attempts = 0`.

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |
| Always-`revert_before` stub loops forever (181 restarts) | High | High | Evaluate `red_attempts >= 3` before the next RED. Pin `test_always_revert_before_stops_after_three_escalates`. |
| GREEN-budget exhaust raises `TRAIN_EXHAUSTED` on cycle 1 | High | High | Escalate when `green_attempts` reaches 3. Pin `test_always_revert_to_red_trains_green_three_times_then_escalates`. |
| `transition_to` drops the new counters | High | High | Copy both fields in `transition_to` and `force_transition_to`. Pin a transition-copy test. |
| Double-increment after crash between save and RED | Medium | Medium | Consume `pending_judge_action` exactly once after the increment, matching today's one-shot clear. |
| Escalate RED still receives the GREEN dump | Medium | Medium | Wipe `train_feedback` on escalate and set the short note. Pin `test_escalate_injects_short_note_not_green_dump`. |
| Next task inherits a spent budget | Medium | Medium | Zero both counters in `_finish_tdd_cycle` and on `TRAIN_EXHAUSTED`. |
| EXECUTE `max_judge_attempts` loop is retargeted by accident | Medium | Low | Do not edit `_run_execute_phase`. AC-PLAN-005 pins `_JUDGE_ACTIONS` and the TDD caps only. |
| Un-mocked `_run_pytest` blows the 30s suite budget | Medium | Medium | Mock `deviate.cli.micro._run_pytest` in every TDD-loop test. |
| `TrainIndicator` tests fail if the `TRAIN` token disappears | Low | Low | Keep the literal `TRAIN` token. Pass GREEN `n/3` from `green_attempts`. |

## Security Profile

Risk surfaces: file paths (`.deviate/session.json` under the worktree), subprocess (existing TDD agent and git rollback; this issue adds no new subprocess), git reset / git clean (existing `_execute_rollback` reused on escalate). No auth, secrets, PII, outbound HTTP, deserialization, SQL/ORM, or eval surfaces. Counters are integers. The session file is already gitignored.

Negative tests: an always-`revert_before` stub stops after three escalates and never dispatches a fourth `_run_red_phase`; an always-`revert_to_red` stub does not print `TRAIN_EXHAUSTED` on the first GREEN cycle; escalate RED prompt omits raw GREEN `<test_output>` / full rationale; missing session JSON loads 0/0, never `None`; `transition_to` cannot zero the counters; `_coerce_judge_action` still forces `revert_before` for `test_defect` / `no_failing_test` on a violation.

Constraints: no new dependencies; no hardcoded secrets; do not un-gitignore `.deviate/session.json`; do not add a session schema-bump file; do not rename JUDGE verbs; do not change EXECUTE `max_judge_attempts`; do not invoke un-mocked `_run_pytest` in tests.

## Integration Points

- **`SessionState.save` / `load`** (`src/deviate/state/config.py:317`): persist `green_attempts` and `red_attempts` in `.deviate/session.json` so `git reset --hard` and process crash keep the budget.
- **`_run_tdd_cycle`** (`src/deviate/cli/micro.py:2893`): sole owner of GREEN-train vs escalate vs `TRAIN_EXHAUSTED`.
- **`_coerce_judge_action`** (`src/deviate/cli/micro.py:2060`): unchanged override that maps `test_defect` / `no_failing_test` violation to `revert_before`.
- **`_build_auto_prompt`** (`src/deviate/cli/micro.py:1021`): injects `{train_feedback}` into retry RED; escalate supplies a short note.
- **`_execute_rollback` / `_resolve_pre_red_sha`**: reused as the escalate boundary; this issue does not replace them.
- **`TrainIndicator.render`** (`src/deviate/ui/pipeline.py:374`): GREEN 1/3–3/3 display; literal `TRAIN` token stays.
- **`_run_execute_phase` `max_judge_attempts`** (`src/deviate/cli/micro.py:3208`): out of contract; do not edit.

## Constitutional Alignment

- **Architecture**: Aligns with constitution §1 four-layer model and Micro-layer TDD (RED → GREEN → JUDGE → REFACTOR). The change stays inside the micro runner and session JSON. It does not skip a layer and does not add Product-layer work. Session Continuity (§1) keeps one LLM session across RED → GREEN → REFACTOR; JUDGE stays on its own model. Append-only ledgers stay append-only: retry RED still uses `bypass_phase_done=True` so a fresh RED row is appended.
- **Testing**: pytest unit and orchestration tests in `tests/unit/test_state/test_config.py`, `tests/unit/test_cli/test_micro.py`, `tests/unit/test_micro/test_orchestration.py`, and `tests/unit/test_micro/test_two_counter_retry.py`. Coverage target stays ≥ 80% (constitution §3). The full suite stays under 30 seconds by mocking `_run_pytest`.
- **Git Isolation**: constitution §1 Git Isolation and §2 session JSON under `.deviate/`. Counters live in gitignored `.deviate/session.json`, so `git reset --hard` at the pre-RED boundary does not roll the budget back. Micro agents do not run branch-mutating git. Escalate reuses the existing `revert_before` SHA.
- **Product Layer**: `flow_refs` is empty. This issue bounds `deviate micro` retry inside C1 and does not alter FLOW-04 RPC streaming named in `specs/_product/release-next.md`. This section is traceability only.
