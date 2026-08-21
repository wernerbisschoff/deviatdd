---
title: "Stop Padding Epics — One User-Visible Shard, One Fail-to-Pass Task"
labels: [enhancement, adhoc, vertical-slice, prompts, shard, tasks]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-018
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/018-one-behavior-rgr-granularity.md`
- **Primary Architectural Workstations**:
  - `src/deviate/prompts/commands/deviate-shard.md` — TARGET: Pass 1.5 (invariants ~line 30, ICoT ledger template ~line 52) currently says "Hard ceiling: 10 slices per epic. Target range: 4–8." Drop the 4–8 floor; keep cap 10 / `SLICE_CAP_EXCEEDED`; state that 1 is legal. Also reword `vertical_slicing` step 5 ("must warrant its own spec + plan phase") so a single user-visible behavior is enough — do not invent extra slices to look non-trivial.
  - `src/deviate/prompts/auto/shard.md` — TARGET: Pass 1.5 (~line 44) duplicates "Target range: 4-8". Keep auto/manual wording aligned (ISS-ADH-016 single-source invariant).
  - `src/deviate/prompts/commands/deviate-tasks.md` — TARGET: opening "30-90 min each" (~line 17) and **30-90 Minute Rule** (~line 97: "If a task takes < 30 min, merge it. If > 90 min, split it"). Recast 30–90 as the name of one observable fail-to-pass contract, not a wall-clock splitter. Forbid fake splits (test-skeleton vs implement vs add-the-route for the same AC). Keep the 4–8 **Details** bullets (task-body structure, not shard count).
  - `src/deviate/prompts/auto/tasks.md` — TARGET: same 30-90 Minute Rule (~lines 5, 39). Align with the command prompt.
  - `src/deviate/prompts/core/micro-shared.md` — TARGET: "Each task is a Logical Unit (30-90 min)" (~line 7). Tie the phrase to one R-G-R contract, not a duration floor.
  - `src/deviate/prompts/auto/refactor.md` — TARGET: the same Logical Unit (30-90 min) sentence (~line 10).
  - `specs/DeviaTDD-api.md` — TARGET: `/deviate-shard` Granularity Guidelines (~lines 254–260): "Target: 4-8 issues" and "Pass 1.5 hard-enforces the 4–8 / max-10 cap". Replace with as-few-as-needed / min 1 / max 10.
  - `specs/DeviaTDD-architecture.md` — TARGET: Macro Shard (~line 92) "Target 4-8 issues per feature shard" (already also says min 1 / max 10 — drop the target floor). Meso Granularity (~line 142) "Target 4-8 tasks per issue" / "15-60 min" / "maximum 10 tasks" — recast to one fail-to-pass contract per task; do not keep a 4–8 task floor.
  - `CHANGELOG.md` — TARGET: `[Unreleased]` bullet for the user-visible granularity-policy change.
- **Classification for plan/tasks**: prompt text, spec keys, and shard-rule wording. Prefer **IMMEDIATE** execution_mode. Do not force a RED/GREEN cycle for prompt-only work.
- **Upstream Evidence**:
  - Scribe 0.1 brief, 20 Aug 2026 (`/workspace/tdd-agent-task-granularity.md`).
  - SWE-bench Verified difficulty bins (Ganhotra): easy ~5 LOC; medium ~14 LOC / ~1–2 files; hard ~56 LOC / ~7 hunks.
  - Beck Canon TDD: exactly one item on the test list per cycle.
  - Cohen/SmartBear review size: typical <200 LOC, 400 LOC max.
  - Empirical: grok-4.6 micro on a one-function slice finished in 4m 25s — process tax, not risk control.

## The Problem Contract

Shard Pass 1.5 advertises a 4–8 vertical target that agents treat as a floor: a one-behavior PRD is padded into extra issues so the count lands in range, and each extra issue pays specify → plan → worktree → PR. Tasks prompts still say 30–90 minute human slices and "split if > 90 min", which produces layered fake tasks (test skeleton vs implement vs add the route) and more RED/GREEN/JUDGE cycles than fail-to-pass contracts. Operators need fewer issues when they were padding, while each remaining TDD task stays one observable behavior the JUDGE can still see.

## Scope Boundaries

### Hard Inclusions

- Drop the Pass 1.5 "target 4–8" floor in both `deviate-shard.md` and `auto/shard.md`. Keep the **hard cap of 10** and `SLICE_CAP_EXCEEDED` when draft count exceeds 10.
- Emit as few independently shippable **user-visible** verticals as the PRD needs. **1 is legal.** 8 remains correct when there are 8 real verticals.
- Keep Pass 3 / 3.5 horizontal merge and Pass 5 meta-work rejection unchanged.
- Recast the tasks 30–90 minute rule as "this is one observable behavior," not "split if the agent might take 90 min."
- One TDD task = one fail-to-pass contract (Beck: exactly one item on the test list). Not one `assert`. Not one feature file. Not a whole epic.
- Merge fake splits: test-skeleton vs implement vs "add the route" for the same behavior.
- JUDGE still sees that one behavior (safe default ≲2 files / ≲3 hunks / ≲30 production LOC; Cisco-style review ceiling <200 LOC typical / 400 max). A GREEN that would bury the contract in a mixed 10-file / >400 LOC packet is still split.
- Specify the test list **once** per issue; R-G-R **many times** on that list; one PR per vertical.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same implementation commit (spec-alignment mandate).
- Append a `CHANGELOG.md` `[Unreleased]` bullet.

### Defensive Exclusions

- Do **not** grow GREEN to fill 200k–1M context.
- Do **not** change the 10-slice hard cap or `SLICE_CAP_EXCEEDED` halt.
- Do **not** implement or retarget the two-counter GREEN-train / RED-escalate retry (ISS-ADH-017 / `#59`).
- Do **not** change micro runner code (`src/deviate/cli/micro.py`) or JUDGE `next_action` verbs.
- Do **not** change the tasks **Details** 4–8 bullet quota (that is task-body structure, not epic padding).
- Do **not** change `src/deviate/prompts/core/style-ste.md` (the "30-90 minutes" STE example is diction, not a floor).
- Do **not** author or synchronize Product-layer flows; `flow_refs: []`.
- Do **not** revert operator-local `.deviate/config.toml` (backend=pi, transport=cli, pi_rpc=false, timeout=1800, models.default=grok-4.6).
- Do **not** add tests that invoke `deviate.cli.micro._run_pytest` un-mocked.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-018`
- **Acceptance Criteria Tokens**: `AC-ADHOC-018-01`, `AC-ADHOC-018-02`, `AC-ADHOC-018-03`, `AC-ADHOC-018-04`
- **Data Model Entities**: none (prompt and spec wording only; no new ledger models)
- **Spec Source Anchors**:
  - `src/deviate/prompts/commands/deviate-shard.md` Pass 1.5 (~lines 30, 52)
  - `src/deviate/prompts/auto/shard.md` Pass 1.5 (~line 44)
  - `src/deviate/prompts/commands/deviate-tasks.md` (~lines 17, 97)
  - `src/deviate/prompts/auto/tasks.md` (~lines 5, 39)
  - `specs/DeviaTDD-api.md` (~lines 254–260)
  - `specs/DeviaTDD-architecture.md` (~lines 92, 142)
  - `specs/constitution.md` §1 Four-Layer Architecture / Micro-Layer Scope (unchanged process; this issue only stops padding inside it)

## User Stories Ledger

- **US-018-01**: As a DeviaTDD operator sharding a one-behavior PRD, I want exactly one issue so I do not pay specify → plan → worktree → PR four times. *(Ref: FR-ADHOC-018)*
- **US-018-02**: As a DeviaTDD operator writing `tasks.md`, I want one TDD task per fail-to-pass contract so micro does not run extra RED/GREEN/JUDGE cycles for the same AC. *(Ref: FR-ADHOC-018)*
- **US-018-03**: As a DeviaTDD operator on an eight-vertical epic, I still want eight issues, and a mixed 10-file / >400 LOC GREEN packet still split, so large work stays reviewable. *(Ref: FR-ADHOC-018)*

## Acceptance Outline

- **AO-018** *(Ref: AC-ADHOC-018-01, US-018-01)*: Pass 1.5 has no 4–8 floor; 1 is legal; cap 10 remains.
  - **Happy Path**: A PRD with one user-visible behavior produces one shard issue. Prompt text no longer contains "Target range: 4–8" or "Target range: 4-8".
  - **Error Category**: Draft count > 10 still halts with `SLICE_CAP_EXCEEDED` and re-clusters until count ≤ 10.
  - **Boundary Category**: Pass 3 / 3.5 still merge one-layer candidates; Pass 5 still rejects meta work.

- **AO-018** *(Ref: AC-ADHOC-018-02, US-018-02)*: Tasks stay one observable fail-to-pass contract.
  - **Happy Path**: `tasks.md` for a one-AC issue does not emit a RED-only task and a GREEN-only task (or a separate "add the route" task) for that AC. 30–90 min names the unit; it does not split on estimated agent duration.
  - **Error Category**: A tasks prompt that still says "If a task takes < 30 min, merge it. If > 90 min, split it" fails review.
  - **Boundary Category**: Plan/tasks for this slice itself use IMMEDIATE when the change is prompt/spec wording only.

- **AO-018** *(Ref: AC-ADHOC-018-03, US-018-03)*: Real multi-vertical epics and oversized GREEN packets still split.
  - **Happy Path**: Eight independent user-visible verticals still emit eight issues.
  - **Error Category**: Collapsing eight verticals into one fat GREEN to "save process" fails review.
  - **Boundary Category**: Safe JUDGE packet default remains ≲2 files / ≲3 hunks / ≲30 production LOC; review ceiling <200 LOC typical / 400 max.

- **AO-018** *(Ref: AC-ADHOC-018-04)*: Specs and changelog match the prompts.
  - **Happy Path**: API and architecture docs no longer advertise a 4–8 issue or 4–8 task floor; CHANGELOG `[Unreleased]` records the policy.
  - **Boundary Category**: ISS-ADH-017 two-counter retry wording is untouched.

## Edge Cases and Boundaries

- **Auto/manual pair drift**: Edit `commands/deviate-shard.md` and `auto/shard.md` (and the tasks pair) together so ISS-ADH-016's identical-middle invariant is not regressed.
- **Non-triviality step**: Shard `vertical_slicing` step 5 currently requires a slice to "warrant its own spec + plan phase"; that language must not be used to pad a one-behavior PRD.
- **Details 4–8 vs shard 4–8**: Keep the tasks **Details** 4–8 bullet quota; only the epic/task *count* floor is removed.
- **STE diction**: `style-ste.md` may keep "30-90 minutes" as an example of precise time language.
- **Prompt-only verification**: Prefer `rg` pins on the prompt/spec files over a RED/GREEN cycle. If tests are added, they must not call un-mocked `_run_pytest`.
- **Parallel adhoc 017**: ISS-ADH-017 occupies `specs/adhoc/issues/017-two-counter-tdd-retry.md` on another worktree; this issue is 018 and must not reuse 017 tokens.

## Performance Constraints

- **L_max**: Prompt-load and `deviate setup` init remain ≤ 500ms (AGENTS.md). Wording edits add no I/O.
- **Per-agent export**: ≤ 200ms. No new export path.
- **Full test suite**: `mise run test` remains < 30s. Any new pin test must be file-read/`rg` only.
- **Operator cycle time**: A one-behavior epic should pay one specify → plan → worktree → PR, not four. Micro wall-clock of ~4–5 minutes on a one-function slice is acceptable; extra JUDGE packets for fake splits are not.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - Optional pin in `tests/test_meso/test_auto_prompt_templates.py` (or a focused new test) asserting `auto/shard.md` and `commands/deviate-shard.md` contain no "Target range: 4" floor, still contain "10" / `SLICE_CAP_EXCEEDED`, and state that 1 is legal.
  - Optional pin asserting `auto/tasks.md` and `commands/deviate-tasks.md` no longer contain "If a task takes < 30 min, merge it" and do contain "fail-to-pass" / "one observable behavior" language.
- **Integration Sandbox Targets**: none required (no CLI runner change). Skip E2E; this slice has no user-facing FLOW and no new command.

## Demonstration Path

```bash
# Pass 1.5: floor gone, cap 10 remains
rg -n "Target range: 4" src/deviate/prompts/commands/deviate-shard.md src/deviate/prompts/auto/shard.md
# expect empty
rg -n "SLICE_CAP_EXCEEDED|Hard ceiling: 10|1 is legal" src/deviate/prompts/commands/deviate-shard.md src/deviate/prompts/auto/shard.md

# Tasks: no wall-clock splitter; one fail-to-pass contract
rg -n "If a task takes < 30 min" src/deviate/prompts/commands/deviate-tasks.md src/deviate/prompts/auto/tasks.md
# expect empty
rg -n "fail-to-pass|one observable behavior" src/deviate/prompts/commands/deviate-tasks.md src/deviate/prompts/auto/tasks.md

# Specs no longer advertise a 4-8 floor
rg -n "Target: 4-8 issues|Target 4-8 issues|Target 4-8 tasks" specs/DeviaTDD-api.md specs/DeviaTDD-architecture.md
# expect empty (or only historical notes)

# Unrelated retry issue untouched
rg -n "green_attempts|red_attempts" src/deviate/cli/micro.py src/deviate/state/config.py || true
```
