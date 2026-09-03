## Plan Summary
- **Issue**: ISS-ADH-033 — Redefine /deviate-prune as manual honeycomb test thinning
- **Implementation Strategy**: Verify the existing honeycomb engine and prompts against the issue contract, then close the remaining gaps in classification, ledger protection, and RED mark stamping with the smallest diff that holds.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Prune drops spy and impl tagged tests and keeps behavioral and ac tests**
- **Source Outline**: `AO-033-01`
- **Upstream Traceability**: `US-033-01`, `FR-ADHOC-033`, `AC-ADHOC-033-01`
- **Current-Code Evidence**: `src/deviate/core/prune.py:classify_test`
- **Given**: An issue-scoped suite holds spy, impl, behavioral, and ac tagged tests
- **When**: The operator runs manual prune for that one issue
- **Then**: Spy and impl tests drop while behavioral, ac, and public input-to-output tests stay
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Untagged tests classify from the body and never auto-keep**
- **Source Outline**: `AO-033-01`
- **Upstream Traceability**: `US-033-01`, `FR-ADHOC-033`, `AC-ADHOC-033-01`
- **Current-Code Evidence**: `src/deviate/core/prune.py:_classify_body`
- **Given**: Issue-scoped tests carry no mark and no name tag
- **When**: Prune classifies each untagged test from its body
- **Then**: Internal spies, private-state probes, and sibling mocks drop while public input-to-output and AC tests stay
- **Verification Mode**: automated

**Scenario AC-PLAN-003: In-flight issues thin tests and keep every spec file**
- **Source Outline**: `AO-033-01`
- **Upstream Traceability**: `US-033-01`, `FR-ADHOC-033`, `AC-ADHOC-033-01`
- **Current-Code Evidence**: `src/deviate/core/prune.py:build_prune_plan`
- **Given**: The targeted issue status is not COMPLETED
- **When**: The operator runs manual prune for that issue
- **Then**: Test thinning runs with an IN_FLIGHT contract and `spec_deletes` stays empty
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Prune leaves ledgers byte-identical and cycle markdown present**
- **Source Outline**: `AO-033-02`
- **Upstream Traceability**: `US-033-02`, `FR-ADHOC-033`, `AC-ADHOC-033-02`
- **Current-Code Evidence**: `src/deviate/core/prune.py:apply_prune`
- **Given**: A fixture issue holds cycle markdown plus JSONL ledger rows
- **When**: Prune applies honeycomb thinning for that issue
- **Then**: `specs/issues.jsonl` and `specs/**/tasks.jsonl` bytes match the pre-run snapshot and `plan.md` and `tasks.md` still exist
- **Verification Mode**: automated

**Scenario AC-PLAN-005: Ledger rewrite instructions stop prune before any write**
- **Source Outline**: `AO-033-02`
- **Upstream Traceability**: `US-033-02`, `FR-ADHOC-033`, `AC-ADHOC-033-02`
- **Current-Code Evidence**: `src/deviate/core/prune.py:is_ledger_rewrite_request`
- **Given**: The operator intent asks to compact, squash, or rewrite a ledger
- **When**: Prune pre evaluates that intent
- **Then**: The contract returns LEDGER_REWRITE_REJECTED and post applies zero writes
- **Verification Mode**: automated

**Scenario AC-PLAN-006: Missing optional flows ledger skips without creation**
- **Source Outline**: `AO-033-02`
- **Upstream Traceability**: `US-033-02`, `FR-ADHOC-033`, `AC-ADHOC-033-02`
- **Current-Code Evidence**: `src/deviate/core/prune.py:ledger_paths`
- **Given**: The repository holds no `specs/_product/flows.jsonl` file
- **When**: Prune snapshots ledgers and applies thinning
- **Then**: No flows file appears and existing ledgers stay byte-identical
- **Verification Mode**: automated

**Scenario AC-PLAN-007: RED stamps one honeycomb mark on each new test**
- **Source Outline**: `AO-033-03`
- **Upstream Traceability**: `US-033-03`, `FR-ADHOC-033`, `AC-ADHOC-033-03`
- **Current-Code Evidence**: `src/deviate/prompts/auto/red.md`
- **Given**: A RED task starts with the honeycomb rule active
- **When**: RED authors new tests for the assigned acceptance criteria
- **Then**: Each new test carries exactly one behavioral, spy, or impl mark and most new tests read behavioral
- **Verification Mode**: automated

**Scenario AC-PLAN-008: COMPLETED, --all, and the skill loop never auto-invoke prune**
- **Source Outline**: `AO-033-03`
- **Upstream Traceability**: `US-033-03`, `FR-ADHOC-033`, `AC-ADHOC-033-03`
- **Current-Code Evidence**: `src/deviate/prompts/skills/deviatdd/SKILL.md`
- **Given**: A micro task reaches COMPLETED or the skill loop advances
- **When**: The runner finishes that task boundary
- **Then**: No prune phase runs and only a manual `deviate prune` or `/deviate-prune` invocation thins tests
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/core/prune.py**: Honeycomb classify and apply engine for this issue
  - **Current State**: `classify_test`, `build_prune_plan`, `apply_prune`, and `is_ledger_rewrite_request` already encode the target behavior
  - **Changes Required**: Close gaps only — missing `flows.jsonl` skip, `ledger_paths` coverage, and any classification miss the RED pins expose
  - **Integration Surface**: `src/deviate/cli/prune.py` pre and post commands, `/deviate-prune` prompt contract
- **src/deviate/cli/prune.py**: Thin pre and post CLI surface the prompt calls
  - **Current State**: Delegates to `build_prune_plan` and `apply_prune` with no extra writes
  - **Changes Required**: None expected unless the engine contract shifts
  - **Integration Surface**: `src/deviate/core/prune.py`, `deviate-prune.md` STEP_0 and STEP_3
- **src/deviate/prompts/commands/deviate-prune.md**: Single manual operator surface for one issue
  - **Current State**: Declares manual invoke, mark-first classification, body fallback, and no spec deletes
  - **Changes Required**: Align wording gaps only — keep one surface, keep aliases unchanged
  - **Integration Surface**: `deviate prune pre` and `post` JSON contract, `deviatdd` skill dispatch row
- **src/deviate/prompts/auto/red.md**: RED core that stamps honeycomb marks
  - **Current State**: Rule 6 requires exactly one behavioral, spy, or impl mark per new test
  - **Changes Required**: None expected unless pins show a wording miss
  - **Integration Surface**: `src/deviate/prompts/commands/deviate-red.md` overlay, micro RED runner
- **src/deviate/prompts/commands/deviate-red.md**: Manual RED overlay over the auto core
  - **Current State**: Derives its body from `auto/red.md` and adds pre and post handling
  - **Changes Required**: None expected — core carries the mark rule
  - **Integration Surface**: `src/deviate/prompts/auto/red.md`
- **src/deviate/prompts/skills/deviatdd/SKILL.md**: Per-task micro loop with manual-only prune
  - **Current State**: Dispatch row and guard clauses forbid prune from the success loop, COMPLETED, and `--all`
  - **Changes Required**: None expected unless wording drifts from the issue
  - **Integration Surface**: `deviate micro run`, `/deviate-prune` dispatch
- **README.md**: Operator-facing prune description
  - **Current State**: Describes prune as manual honeycomb thinning with ledger and spec keeps
  - **Changes Required**: Touch only lines that still describe spec-delete-on-COMPLETED
  - **Integration Surface**: None — prose mirror of the prompt contract
- **specs/DeviaTDD-api.md**: Authoritative CLI and prune contract reference
  - **Current State**: Documents `deviate prune pre` and `post` as manual honeycomb inventory plus apply
  - **Changes Required**: Update only stale prune passages in the same commit as code changes
  - **Integration Surface**: `src/deviate/cli/prune.py`, `src/deviate/core/prune.py`
- **specs/DeviaTDD-architecture.md**: Authoritative prune architecture passage
  - **Current State**: Describes single manual surface, mark-first classification, RED stamping, and no auto-hook
  - **Changes Required**: Update only stale prune passages in the same commit as code changes
  - **Integration Surface**: `src/deviate/core/prune.py`, `deviate-prune.md`

## Implementation Strategy
- **Phase 1**: Pin current behavior with failing-first regression tests
  - **Files**: `tests/unit/test_core/test_prune.py`, `tests/unit/test_cli/test_prune.py`
  - **Approach**: Add pins for marks-first ordering, untagged-not-auto-keep, ledger byte-identity, rewrite rejection, missing-flows skip, and RED mark stamping before touching production code
  - **Verification**: Run `mise run test` and confirm only the new gap pins fail
- **Phase 2**: Close engine gaps with the smallest production diff
  - **Files**: `src/deviate/core/prune.py`, `src/deviate/cli/prune.py`
  - **Approach**: Fix classification or protection misses in place, keep `spec_deletes` always empty, keep `apply_prune` ledger-free
  - **Verification**: Run `mise run test` and `mise run check` until green
- **Phase 3**: Align prompts, skill, README, and specs prose
  - **Files**: `src/deviate/prompts/commands/deviate-prune.md`, `src/deviate/prompts/auto/red.md`, `src/deviate/prompts/commands/deviate-red.md`, `src/deviate/prompts/skills/deviatdd/SKILL.md`, `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`
  - **Approach**: Edit only passages that contradict manual honeycomb thinning, keep one surface and existing aliases, record spec updates in the same commit
  - **Verification**: Prompt pins pass, `git diff` shows prose plus engine only, CHANGELOG gains an `[Unreleased]` bullet

## Data Flow Analysis
- The operator invokes `/deviate-prune` or `deviate prune pre --issue <id>` for one issue. Pre resolves the issue id from the flag or session, rejects ledger-rewrite intent and multi-issue intent, and emits a JSON contract with status, keep lists, drop lists, unmatched ACs, and the ledger-untouched flag. The prompt classifies tagged tests first and untagged tests from the body. Post applies thinning by removing dropped test functions and rewriting only the touched test files. Ledger files and spec markdown never enter the write path. The operator commits the cleanup with a conventional message.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Body heuristic drops a public behavioral test | High | Medium | Keep-wins on AC tokens and public I/O asserts; unmatched-AC list surfaces losses before post |
| Empty-file unlink removes a file the operator expected to keep | Medium | Low | Only unlink test files with zero surviving tests; never unlink specs or ledgers by construction |
| Prior ADH-033 commits already cover the behavior and the plan over-scopes | Medium | Medium | Treat this plan as verify-and-fill-gaps; change production code only where pins fail |
| Prose drift across README, skill, and specs reintroduces spec-delete language | Low | Medium | Prompt pins assert manual-only and no-delete wording; update all mirrors in one commit |

## Security Profile
Risk surfaces: file paths (test-file rewrite, unlink), subprocess (none added), deserialization (JSON contract only).
Negative tests: ledger rewrite intent rejected with zero writes; second issue id stops with ONE_ISSUE_ONLY; unknown issue id returns FAILURE with no writes; missing flows ledger creates zero files.
Constraints: GREEN writes only to test files named in the drop list plus approved prose mirrors; no new dependencies; no ledger or spec-markdown writes from any prune path.

## Integration Points
- **`deviate prune pre` JSON contract**: Single-issue inventory the prompt parses — status, keeps, drops, unmatched ACs, ledger-untouched flag
- **`deviate prune post` apply path**: Sole write path — thins dropped test functions, never writes ledgers, never unlinks specs, never commits
- **Micro COMPLETED boundary**: No prune hook exists there — prune stays out of `micro.py`, `meso.py`, and the `deviatdd` skill success loop
- **RED stamping**: `auto/red.md` and the `deviate-red.md` overlay require one honeycomb mark per new test so later prune has a tag to read

## Constitutional Alignment
- **Architecture**: Three-layer model holds — prune is an operational pass over micro outputs, not a new layer; no Product folder, no `flow_refs`, no second skill surface per constitution §1
- **Testing**: pytest pins under `tests/unit/test_core/test_prune.py` and `tests/unit/test_cli/test_prune.py` cover classification and prompt wording; RED-first for gap pins; coverage target stays >= 80% per constitution §3
- **Git Isolation**: Work happens on the dedicated issue branch `feat/adhoc/033-prune-post-completed`; the orchestrator owns staging and commits; no branch switches per constitution §4
- **User Scenarios**: `AC-PLAN-001` through `AC-PLAN-003` encode `US-033-01` thinning, `AC-PLAN-004` through `AC-PLAN-006` encode `US-033-02` ledger and spec protection, `AC-PLAN-007` and `AC-PLAN-008` encode `US-033-03` RED stamping and manual-only operation; RED turns those scenarios into failing tests
