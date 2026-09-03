## Plan Summary
- **Issue**: ISS-ADH-018 — Stop Padding Epics — One User-Visible Shard, One Fail-to-Pass Task
- **Implementation Strategy**: Rewrite shard Pass 1.5 so one user-visible behavior is a legal shard. Recast the tasks 30–90 rule as one fail-to-pass contract, and match API, architecture, and CHANGELOG in the same commit.
- **Estimated Complexity**: Low
- **Estimated Effort**: 1-2 hours

## Product Layer Anchors
- **Flow References**: []
- **Source**: `specs/adhoc/issues/018-one-behavior-rgr-granularity.md` (frontmatter field: `flow_refs`)
- **Release Context**: Enable `deviate` meso and micro phases to drive Pi or OMP agent runtimes through RPC and stream live progress into a compact TUI (FLOW-04). This issue is orthogonal: it changes shard/task granularity policy, not the RPC/TUI transport.
- **Architecture Components Touched**: `C1` (`deviate` CLI — owns phase prompts that the CLI loads for Macro shard and Meso tasks)

## Acceptance Contract

**Scenario AC-PLAN-001: Drop the Pass 1.5 4–8 floor and keep cap 10**
- **Source Outline**: `AO-018`
- **Upstream Traceability**: `US-018-01`, `FR-ADHOC-018`, `AC-ADHOC-018-01`
- **Current-Code Evidence**: `src/deviate/prompts/commands/deviate-shard.md:30`
- **Given**: Shard Pass 1.5 in the command prompt and `auto/shard.md` still names a 4–8 target range.
- **When**: Implementers rewrite Pass 1.5 and `vertical_slicing` step 5 in that auto/command pair.
- **Then**: Both shard prompts omit a `Target range: 4` floor, state that 1 is legal, keep hard ceiling 10, and still halt with `SLICE_CAP_EXCEEDED` when draft count exceeds 10.
- **Verification Mode**: manual

**Scenario AC-PLAN-002: Recast the 30–90 rule as one fail-to-pass contract**
- **Source Outline**: `AO-018`
- **Upstream Traceability**: `US-018-02`, `FR-ADHOC-018`, `AC-ADHOC-018-02`
- **Current-Code Evidence**: `src/deviate/prompts/commands/deviate-tasks.md:97`
- **Given**: Tasks prompts still say to merge under 30 min and split over 90 min.
- **When**: Implementers recast the 30–90 Minute Rule in the tasks pair, `micro-shared.md`, and `auto/refactor.md`.
- **Then**: Those prompts name one observable fail-to-pass contract, forbid fake splits of the same AC, keep the Details 4–8 bullet quota, and omit `If a task takes < 30 min, merge it`.
- **Verification Mode**: manual

**Scenario AC-PLAN-003: Keep real multi-vertical splits and oversized GREEN splits**
- **Source Outline**: `AO-018`
- **Upstream Traceability**: `US-018-03`, `FR-ADHOC-018`, `AC-ADHOC-018-03`
- **Current-Code Evidence**: `specs/DeviaTDD-architecture.md:92`
- **Given**: Architecture already allows a single-issue shard and still names a 4–8 issue target.
- **When**: Implementers drop the 4–8 floor and leave Pass 3, Pass 3.5, Pass 5, and the 10-slice cap in place.
- **Then**: Eight independent user-visible verticals still emit eight issues, a mixed 10-file / >400 LOC GREEN packet still splits, and the JUDGE packet default stays ≲2 files / ≲3 hunks / ≲30 production LOC with review ceiling <200 LOC typical / 400 max.
- **Verification Mode**: manual

**Scenario AC-PLAN-004: Align API, architecture, and CHANGELOG with the prompts**
- **Source Outline**: `AO-018`
- **Upstream Traceability**: `US-018-01`, `FR-ADHOC-018`, `AC-ADHOC-018-04`
- **Current-Code Evidence**: `specs/DeviaTDD-api.md:260`
- **Given**: API Granularity Guidelines still target 4-8 issues and say Pass 1.5 hard-enforces the 4–8 / max-10 cap.
- **When**: Implementers update `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` in the same commit as the prompt edits.
- **Then**: Those specs advertise as-few-as-needed with min 1 and max 10, Meso granularity names one fail-to-pass contract per task, CHANGELOG `[Unreleased]` records the policy, and ISS-ADH-017 retry wording stays untouched.
- **Verification Mode**: manual

## Workstation Mapping
- **`src/deviate/prompts/commands/deviate-shard.md`**: TARGET — drop the Pass 1.5 4–8 floor and reword `vertical_slicing` step 5.
  - **Current State**: Line 30 and ICoT line 52 say `Hard ceiling: 10 slices per epic. Target range: 4–8.` Step 5 at line 122 says a slice `must warrant its own spec + plan phase`. Pass 3 / 3.5 / 5 and `SLICE_CAP_EXCEEDED` already exist.
  - **Changes Required**: Replace the 4–8 target with as-few-as-needed, min 1 legal, hard cap 10. Keep `SLICE_CAP_EXCEEDED` when draft count exceeds 10. Reword step 5 so one user-visible behavior is enough. Do not invent extra slices to look non-trivial. Leave Pass 3, 3.5, and 5 unchanged.
  - **Integration Surface**: Loaded as `/deviate-shard`. Must stay aligned with `src/deviate/prompts/auto/shard.md` (ISS-ADH-016 identical-middle).

- **`src/deviate/prompts/auto/shard.md`**: TARGET — same Pass 1.5 wording as the command prompt.
  - **Current State**: Line 44 duplicates `Target range: 4-8` with hard ceiling 10 and `SLICE_CAP_EXCEEDED`. Pass 3 / 3.5 / 5 already match the command prompt.
  - **Changes Required**: Apply the same Pass 1.5 rewrite: 1 is legal, cap 10, no 4–8 floor. Keep halt + re-cluster until count ≤ 10.
  - **Integration Surface**: `deviate.prompts.assembly.load_template("shard")`. Edit in the same task as `deviate-shard.md`.

- **`src/deviate/prompts/commands/deviate-tasks.md`**: TARGET — recast 30–90 as one observable fail-to-pass contract.
  - **Current State**: Line 17 says `vertical tasks, 30-90 min each`. Line 97 says `If a task takes < 30 min, merge it. If > 90 min, split it only while maintaining verticality.` Details 4–8 bullets live at the TASK STRUCTURE CONSTRAINTS block (~line 133). Estimated Time format examples stay `30-90 minutes`.
  - **Changes Required**: Recast the opening duration phrase and the **30-90 Minute Rule** so 30–90 names one fail-to-pass contract, not a wall-clock splitter. Forbid fake splits (test-skeleton vs implement vs add-the-route for the same AC). Keep the Details 4–8 bullet quota. Keep Estimated Time field format. Prefer IMMEDIATE for prompt/spec wording on this slice.
  - **Integration Surface**: Loaded as `/deviate-tasks`. Must stay aligned with `src/deviate/prompts/auto/tasks.md`.

- **`src/deviate/prompts/auto/tasks.md`**: TARGET — same 30–90 recast as the command prompt.
  - **Current State**: Line 5 repeats `30-90 min each`. Line 39 repeats `If a task takes < 30 min, merge it. If > 90 min, split it while maintaining verticality.` Details 4–8 remain at the structure block (~line 101).
  - **Changes Required**: Mirror the command-prompt recast. Keep Details 4–8. Keep Flow References field rules.
  - **Integration Surface**: `load_template("tasks")`. Edit in the same task as `deviate-tasks.md`.

- **`src/deviate/prompts/core/micro-shared.md`**: TARGET — tie Logical Unit (30-90 min) to one R-G-R contract.
  - **Current State**: Line 7 says `Each task is a Logical Unit (30-90 min) that undergoes ONE complete R-G-R cycle`.
  - **Changes Required**: Keep one R-G-R cycle per task. State that the unit is one fail-to-pass contract, not a duration floor.
  - **Integration Surface**: Assembled into every micro-phase prompt via `src/deviate/prompts/assembly.py`.

- **`src/deviate/prompts/auto/refactor.md`**: TARGET — same Logical Unit sentence as `micro-shared.md`.
  - **Current State**: Line 10 repeats `Each task is a Logical Unit (30-90 min) that undergoes ONE complete R-G-R cycle`.
  - **Changes Required**: Apply the same recast as `micro-shared.md`.
  - **Integration Surface**: `load_template("refactor")`. Edit with the tasks/micro wording cluster.

- **`specs/DeviaTDD-api.md`**: TARGET — Granularity Guidelines for `/deviate-shard`.
  - **Current State**: Lines 254–260 say `Target: 4-8 issues per feature shard` and `Pass 1.5 (Slice Cap Gate) hard-enforces the 4–8 / max-10 cap with SLICE_CAP_EXCEEDED`.
  - **Changes Required**: Replace with as-few-as-needed, min 1, max 10. Keep `SLICE_CAP_EXCEEDED` as the over-10 halt. Do not retarget ISS-ADH-017 retry wording.
  - **Integration Surface**: Spec-alignment mandate with `specs/DeviaTDD-architecture.md` in the same commit as the prompt edits (constitution §1 / AGENTS.md Spec Alignment).

- **`specs/DeviaTDD-architecture.md`**: TARGET — Macro Shard and Meso Granularity.
  - **Current State**: Line 92 says `Target 4-8 issues per feature shard` and already `minimum 1 issue, maximum 10 issues`. Line 142 says `Target 4-8 tasks per issue` and `15-60 min` with `maximum 10 tasks`.
  - **Changes Required**: Drop the 4–8 issue floor. Recast Meso granularity to one fail-to-pass contract per task. Keep min 1 / max 10. Do not keep a 4–8 task floor. Keep Pass 1.5 hard cap language.
  - **Integration Surface**: Same-commit pair with `specs/DeviaTDD-api.md`.

- **`CHANGELOG.md`**: TARGET — `[Unreleased]` policy bullet.
  - **Current State**: `[Unreleased]` has Added/Changed/Fixed lists. No granularity-policy bullet yet.
  - **Changes Required**: Append a Changed bullet: shard Pass 1.5 drops the 4–8 floor (1 is legal, cap 10 remains); tasks 30–90 names one fail-to-pass contract.
  - **Integration Surface**: Constitution §5 Definition of Done CHANGELOG discipline.

## Implementation Strategy
- **Phase 1**: Shard Pass 1.5 floor removal (auto/command pair)
  - **Files**: `src/deviate/prompts/commands/deviate-shard.md`, `src/deviate/prompts/auto/shard.md`
  - **Approach**: IMMEDIATE wording edit. Replace `Target range: 4–8` / `Target range: 4-8` with as-few-as-needed, `1 is legal`, hard ceiling 10, `SLICE_CAP_EXCEEDED` unchanged. Reword `vertical_slicing` step 5 so one user-visible behavior is enough. Keep Pass 3 / 3.5 / 5 verbatim. Edit both files in one task (ISS-ADH-016).
  - **Verification**: `rg -n "Target range: 4" src/deviate/prompts/commands/deviate-shard.md src/deviate/prompts/auto/shard.md` is empty. `rg -n "SLICE_CAP_EXCEEDED|Hard ceiling: 10|1 is legal"` hits both files.

- **Phase 2**: Tasks and micro 30–90 recast
  - **Files**: `src/deviate/prompts/commands/deviate-tasks.md`, `src/deviate/prompts/auto/tasks.md`, `src/deviate/prompts/core/micro-shared.md`, `src/deviate/prompts/auto/refactor.md`
  - **Approach**: IMMEDIATE wording edit. Recast the 30-90 Minute Rule as one observable fail-to-pass contract. Forbid fake splits of the same AC. Keep Details 4–8. Do not edit `src/deviate/prompts/core/style-ste.md`. Do not emit a RED-only task and a GREEN-only task for this wording work.
  - **Verification**: `rg -n "If a task takes < 30 min" src/deviate/prompts/commands/deviate-tasks.md src/deviate/prompts/auto/tasks.md` is empty. `rg -n "fail-to-pass|one observable behavior"` hits the tasks pair.

- **Phase 3**: Spec alignment and CHANGELOG
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: IMMEDIATE. Same implementation commit as Phases 1–2. Drop 4–8 issue/task floors. Keep min 1 / max 10. Recast Meso granularity to one fail-to-pass contract. Leave ISS-ADH-017 two-counter retry wording untouched.
  - **Verification**: `rg -n "Target: 4-8 issues|Target 4-8 issues|Target 4-8 tasks" specs/DeviaTDD-api.md specs/DeviaTDD-architecture.md` is empty or historical only. CHANGELOG `[Unreleased]` carries the policy bullet.

## Data Flow Analysis
1. **Input**: A PRD with N user-visible verticals enters `/deviate-shard`. The agent reads Pass 1.5 in `deviate-shard.md` / `auto/shard.md`.
2. **Today**: The 4–8 target acts as a floor. A one-behavior PRD is padded to land in range. Each extra issue pays specify → plan → worktree → PR.
3. **After Phase 1**: Pass 1.5 emits as few independently shippable user-visible verticals as the PRD needs. Count 1 is legal. Count 8 stays correct for 8 real verticals. Count > 10 still halts with `SLICE_CAP_EXCEEDED` and re-clusters.
4. **Tasks input**: `plan.md` `## Acceptance Contract` enters `/deviate-tasks`. The agent reads the 30-90 Minute Rule.
5. **Today**: Wall-clock split produces layered fake tasks (test skeleton vs implement vs add the route) and extra RED/GREEN/JUDGE cycles.
6. **After Phase 2**: Each TDD task is one fail-to-pass contract. Fake splits merge. Oversized GREEN packets (10-file / >400 LOC) still split. JUDGE still sees one behavior (≲2 files / ≲3 hunks / ≲30 production LOC; review ceiling <200 typical / 400 max).
7. **Storage**: No ledger schema change. `specs/issues.jsonl` and `tasks.jsonl` stay append-only. Prompt text is the control surface.
8. **Verification**: Operators run the `rg` pins in the issue `## Demonstration Path`. Optional file-read pins may land in `tests/unit/test_meso/test_auto_prompt_templates.py`. Those pins must not call un-mocked `deviate.cli.micro._run_pytest`.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Auto/command shard or tasks pair drift (ISS-ADH-016 identical-middle) | High | Medium | Edit each auto/command pair in one IMMEDIATE task. Verify both files with the same `rg` pins. |
| Agents still pad because leftover 4–8 wording remains in specs | Medium | Medium | Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit as the prompts. |
| Accidental removal of cap 10 or `SLICE_CAP_EXCEEDED` | High | Low | Keep those tokens verbatim. Pin them in the Phase 1 `rg` command. |
| Details 4–8 bullet quota removed while dropping the shard 4–8 floor | Medium | Low | Touch only the epic/task *count* floor. Leave TASK STRUCTURE CONSTRAINTS 4–8 Details bullets. |
| `style-ste.md` 30-90 example rewritten as if it were a floor | Low | Low | Leave `src/deviate/prompts/core/style-ste.md` unchanged. |
| Parallel ISS-ADH-017 retry worktree collision | Medium | Low | Do not edit `src/deviate/cli/micro.py`, JUDGE `next_action` verbs, or 017 tokens. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping is available | Medium | Low | Preserve empty flow references and plan the application's requested behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths (prompt and spec markdown under `src/deviate/prompts/` and `specs/`). No auth, secrets, PII, outbound HTTP, deserialization, subprocess, SQL/ORM, or eval.

Negative tests: `rg` still finds `SLICE_CAP_EXCEEDED` and hard ceiling 10. `rg` does not find `If a task takes < 30 min` in the tasks pair. `src/deviate/prompts/core/style-ste.md` still contains the STE example `30-90 minutes`. `src/deviate/cli/micro.py` is unmodified. Details 4–8 quota remains. No test invokes un-mocked `deviate.cli.micro._run_pytest`.

Constraints: prompt/spec wording only. IMMEDIATE execution_mode. No new dependencies. No hardcoded secrets. No GREEN growth to fill context. No change to operator-local `.deviate/config.toml`.

## Integration Points
- **ISS-ADH-016 single-source prompts**: Auto templates stay canonical; command prompts stay aligned. Shard and tasks pairs change together.
- **Pass 3 / 3.5 / 5**: Horizontal merge and meta-work rejection stay the halt contracts they are today.
- **JUDGE packet size**: Prompt text restates ≲2 files / ≲3 hunks / ≲30 production LOC and the <200 / 400 LOC review ceiling. No `src/deviate/cli/micro.py` change.
- **ISS-ADH-017 / `#59`**: Two-counter GREEN-train / RED-escalate retry stays out of this slice.
- **Constitution §5 CHANGELOG**: `[Unreleased]` bullet ships with the wording change.

## Constitutional Alignment
- **Architecture**: Constitution §1 Four-Layer Architecture stays. This slice stops padding inside Macro shard and Meso tasks. It does not skip a layer. Gate 2 stays removed. Micro-Layer Scope and JUDGE packet visibility stay.
- **Testing**: Constitution §3 pytest / ruff. This slice prefers `rg` pins over a RED/GREEN cycle (issue classification IMMEDIATE). Optional pin tests are file-read only. Full suite stays < 30s. Coverage target ≥ 80% is unchanged because no production Python changes.
- **Git Isolation**: Constitution §1 Git Isolation. Work stays on `feat/adhoc/018-one-behavior-rgr-granularity`. The orchestrator commits at phase boundaries. Do not delete the branch.
- **Product Layer**: `flow_refs` is `[]`. This slice does not author or sync flows, release scaffolding, or workflow ledgers. Traceability stays empty on purpose.
