---
title: "Generate separate test and verification commands with pre-JUDGE evidence"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-062
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/062-pre-judge-verification-evidence.md`
- **Primary Architectural Workstation**: `src/deviate/prompts/auto/tasks.md`, `src/deviate/cli/micro/surface.py`, `src/deviate/prompts/auto/judge.md`.
- **Discovery Basis**: S1–S5 below anchor the current behavior. The acceptance outlines define proposed behavior.

## The Problem Contract
Operators need generated tasks to distinguish test commands from application verification commands.
The runner executes required verification before `JUDGE` and supplies execution evidence.
Completion requires successful checks and a passing correctness verdict.

## Scope Boundaries
### Hard Inclusions
- `TASKS` emits separately identifiable test commands and verification commands for applicable tasks. Preserve one meaning per field.
- Reuse the existing test strategy and command execution infrastructure. Resolve explicit verification commands exactly as declared.
- Assign each verification command to the task whose acceptance criteria it proves. Assign whole-epic checks to the closing verification boundary.
- Mark verification applicability explicitly when a task has only test coverage. Require real assertions for declared verification commands.
- Run required verification before the corresponding `JUDGE` invocation. Supply command, relative working directory, exit status, stdout, stderr, and timeout/error status.
- Enforce passing required checks independently of the `JUDGE` verdict. Route failures through existing bounded correction behavior.
- Bind evidence to the current candidate. Re-run applicable checks after repairs and `REFACTOR` changes before completion.
- Update `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and `CHANGELOG.md` with the implementation.

### Defensive Exclusions
- Preserve existing test ladders, valid `RED` failure semantics, phase order, session continuity, and HITL gates.
- Preserve the separate queue-drain regression gate described by `specs/adhoc/issues/050-micro-run-final-verification-gate.md`.
- Limit command discovery to declared application checks. Keep existing agent installation and repository setup as preconditions.
- Keep application-specific assertion logic inside the declared commands. Keep semantic correctness assessment inside `JUDGE`.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-061`
- **Acceptance Criteria Tokens**: `AC-ADHOC-061-01`, `AC-ADHOC-061-02`, `AC-ADHOC-061-03`, `AC-ADHOC-061-04`
- **Data Model Entities**: Existing task card, task session, subprocess result, and `JUDGE` context; exact field integration belongs to `PLAN`.
- **Request Anchor**: User input: "lets make sure we have the tasks generate verify commands AND test commands, then we run verify before JUDGE and pass it the output?"

## User Stories Ledger
- **US-062-01**: As an operator, I want separate test and verification commands so the runner executes each required check predictably. *(Ref: FR-ADHOC-061)*
- **US-062-02**: As an operator, I want `JUDGE` to receive actual check results so completion requires executable proof and correctness review. *(Ref: FR-ADHOC-061)*

## Acceptance Outline
- **AO-062-01** *(Ref: AC-ADHOC-061-01, US-062-01)*: Generated task contracts distinguish test execution from application verification.
  - **Happy Path**: A task declares its layer test command and its applicable `mise run verify:<epic_slug>` command separately.
  - **Error Category**: An unresolved required verification command produces a contract error identifying that command.
  - **Boundary Category**: Legacy cards retain their test behavior; new cards state verification applicability explicitly.
- **AO-062-02** *(Ref: AC-ADHOC-061-02, US-062-02)*: The runner executes required verification before `JUDGE` and supplies attributable evidence.
  - **Happy Path**: `JUDGE` receives the exact command, relative working directory, exit status, stdout, and stderr from the current candidate.
  - **Error Category**: Nonzero exit, timeout, and execution errors reach `JUDGE` as failed execution evidence and block completion.
  - **Boundary Category**: An existing `mise test` or `mise unit` task preserves the separately declared verification invocation.
- **AO-062-03** *(Ref: AC-ADHOC-061-03, US-062-02)*: Completion requires successful required checks and a passing `JUDGE` verdict.
  - **Happy Path**: Successful tests, successful verification, and a passing verdict permit advancement under the existing phase contract.
  - **Error Category**: A passing verdict paired with failed required verification remains blocked and enters bounded correction handling.
  - **Boundary Category**: Repairs and `REFACTOR` changes receive fresh required checks; successful evidence belongs to the verified candidate.
- **AO-062-04** *(Ref: AC-ADHOC-061-04, US-062-01)*: Verification runs at its declared acceptance boundary.
  - **Happy Path**: Task-local checks run before that task's `JUDGE`; whole-epic checks run at the closing verification boundary.
  - **Error Category**: Missing prerequisites for an applicable required check report failure and retain blocked completion.
  - **Boundary Category**: Earlier tasks retain their scoped tests while whole-epic behavior remains under construction.

## Edge Cases and Boundaries
- Exit code 0 represents successful assertions; verification scripts propagate failed child commands through nonzero exit codes.
- Empty passing placeholders fail the correctness review. Source S4 already requires real checks.
- Treat captured command output as execution evidence, separate from trusted `JUDGE` instructions. Redact secrets before persistence or prompt injection.
- Bound captured output and flag truncation while retaining command identity and execution status.
- Preserve safe-command validation and configured execution deadlines. Use existing retry policy for failed verification.

## Performance Constraints
- L_max: preserve initialization at 500 ms and agent export at 200 ms, excluding external check execution.
- Throughput: execute each distinct required verification command once per candidate at its applicable boundary.
- Verification duration uses a finite configured deadline. Tests mock command execution and preserve the full-suite target below 30 seconds.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: Extend `tests/unit/test_cli/test_mise_verification.py` for explicit command preservation, legacy behavior, and required-check failures.
- **Integration Sandbox Targets**: Extend `tests/unit/test_cli/test_micro.py` with mocked agents and subprocess results. Assert execution order, evidence delivery, and completion blocking.
- **Task Contract Targets**: Validate generated cards through existing `TASKS` validation and task-card reading paths; cover independent commands and applicability.

## Demonstration Path
```bash
mise run test
mise run check
```
Acceptance demonstration: use a fixture with a passing test command and a failing verification command. Confirm `JUDGE` receives failure evidence and completion remains blocked. Repair verification, rerun, and confirm both checks precede successful completion.

## Discovery Audit
- S1 — `src/deviate/prompts/auto/tasks.md`: `4. **Assign Verification**: Stamp **Verification** as this layer's named mise task:`
- S2 — `src/deviate/cli/micro/surface.py`, `_legacy_full_suite_command`:
  ```python
  if "test" in defined:
      return "mise test"
  if "unit" in defined:
      return "mise unit"
  ```
- S3 — `src/deviate/cli/micro/surface.py`, `_run_test_cmd`:
  ```python
  last = _execute_test_command(command, cwd)
  if last.returncode != 0:
      return last
  ```
- S4 — `specs/DeviaTDD-api.md`: `This prompt rule does not add automatic runner execution.`
- S5 — `specs/constitution.md`: `- REFACTOR phase runs regression gate: tests must re-pass after polish`
- S6 — `src/deviate/prompts/auto/judge.md`: `3. Load the git diff and changed tests.`
- **Scope Size**: This single capability spans generation, execution, and evidence delivery. Required documentation and tests increase the implementation file count above five.
- **Discovery Context**: Existing issue `050` concerns the queue-drain gate; this issue concerns command separation and pre-`JUDGE` evidence.
