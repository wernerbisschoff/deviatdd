---
title: "Restore a committed RED boundary after session loss"
labels: [bug, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-051
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/051-micro-restores-committed-red-boundary.md`
- **Primary Architectural Workstation**: `src/deviate/cli/micro.py`, `tests/unit/test_micro/test_orchestration.py`, `tests/unit/test_micro/test_run.py`

## The Problem Contract
The JSONL task ledger is the authoritative source for phase state because it persists across session loss.
A micro run must resume GREEN when the ledger records completed RED work and Git proves the task-specific RED commit.
The runner must stop with a diagnostic when evidence is missing or ambiguous.

## Scope Boundaries
### Hard Inclusions
- Treat the JSONL task ledger as authoritative and reconstruct the task-specific RED commit boundary from its recorded state plus Git evidence after session loss or cherry-pick.
- Resume GREEN without invoking RED or rollback when the recovered boundary is valid.
- Clear rejection state tied to an earlier RED attempt before resuming a later recovered boundary.
- Report a named diagnostic when recovery evidence is missing or ambiguous.

### Defensive Exclusions
- Keep RED test authoring, GREEN implementation, retry budgets, and model routing unchanged.
- Keep append-only ledgers and Git isolation rules unchanged.
- Keep unrelated phase recovery and JUDGE verdict behavior unchanged.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-051`
- **Acceptance Criteria Tokens**: `AC-ADHOC-051-01`, `AC-ADHOC-051-02`
- **Data Model Entities**: task JSONL phase transition as authoritative state, `SessionState.red_commit_sha` as a cache, Git commit boundary

## User Stories Ledger
- **US-051-01**: As an operator, I want a completed RED boundary restored after session loss so the micro run continues with GREEN. *(Ref: FR-ADHOC-051)*
- **US-051-02**: As a developer, I want ambiguous RED evidence to produce a diagnostic so the runner never destroys completed work. *(Ref: FR-ADHOC-051)*

## Acceptance Outline
- **AO-051-01** *(Ref: AC-ADHOC-051-01, US-051-01)*: A task with an authoritative RED ledger state and matching on-branch RED commit resumes GREEN.
  - **Happy Path**: The runner restores `red_commit_sha`, clears stale attempt rejection, and skips RED and rollback.
  - **Error Category**: The runner names the recovery failure when evidence cannot identify one boundary.
  - **Boundary Category**: A cherry-picked RED commit remains valid when its task evidence matches.
- **AO-051-02** *(Ref: AC-ADHOC-051-02, US-051-02)*: Missing or ambiguous RED evidence stops the run safely.
  - **Happy Path**: The runner emits a diagnostic with task and evidence details.
  - **Error Category**: The runner does not silently rerun RED or roll back.
  - **Boundary Category**: Rejection state from an earlier RED attempt does not apply to a recovered later boundary.

## Edge Cases and Boundaries
- Session state has an empty `red_commit_sha` after state reset.
- The RED commit exists on the active branch through a cherry-pick.
- Multiple candidate commits match partial evidence.
- A stale `pending_judge_action` or `judge_rejected` flag references an earlier attempt.

## Performance Constraints
- L_max: 200ms per recovery decision, excluding Git subprocess time.
- Throughput: one task boundary recovery per micro cycle.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_micro/test_orchestration.py` recovery and stale-rejection cases; `tests/unit/test_micro/test_run.py` session-resume cases.
- **Integration Sandbox Targets**: `deviate micro run --dry-run` and a task run with a restored RED commit.

## Demonstration Path
```bash
uv run pytest tests/unit/test_micro/test_orchestration.py tests/unit/test_micro/test_run.py -q
mise run check
```

## Constitution Compliance
This issue implements `specs/constitution.md` §1 **User Scenarios Are the Flow**, **Git Isolation Principle**, and **Session Continuity**.

> “RED must encode the issue's user scenarios ... as failing tests before GREEN.”
>
> “Every task loop executes on a clean git branch or worktree.”
>
> “Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases.”

## Source Anchors
`src/deviate/cli/micro.py::_tdd_pre_green_decision` currently escalates when `red_commit_sha` is empty.

> “a missing RED SHA re-dispatches RED so a cleared retry gate cannot fall through to GREEN.”

`src/deviate/cli/micro.py::_has_red_commit_boundary` checks only the session field.

> “Return True when `session.red_commit_sha` is a non-empty SHA.”

GitHub issue 211 reports that a committed RED state can lose this session reference and trigger another RED attempt.

The runner must always rebuild session state from the JSONL ledger before dispatch decisions. `SessionState.red_commit_sha` supports the decision but does not override ledger state.
