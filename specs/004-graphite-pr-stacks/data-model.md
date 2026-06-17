# Data Model: Graphite PR Stacks Integration

## Entity Definitions

### PRStackRecord
- **Source-of-truth**: `.deviate/pr_stacks.jsonl` (append-only JSONL)
- **Lifecycle owner**: `src/deviate/state/pr_stack.py` (new module, mirrors `src/deviate/state/ledger.py` pattern)
- **Idempotency**: compound key `(stack_id, status)` per `_append_with_compound_key` pattern at `ledger.py:147-158`

| Attribute | Type | Invariants | Source Anchor |
| :--- | :--- | :--- | :--- |
| `stack_id` | `str` | Pattern `^STK-\d{3}$`. Stack-scoped numeric; stacks are issue-scoped, not global. | Pattern modeled after `TaskRecord.id` regex at `ledger.py:82-85` |
| `issue_id` | `str` | Non-empty. References `IssueRecord.issue_id` in `specs/issues.jsonl`. | `IssueRecord.issue_id` at `ledger.py:26` |
| `trunk` | `str` | Default `"main"`. The Graphite trunk branch. | `explore.md` line 81: "Configure-once trunk: Graphite init prompts for trunk branch selection, stored in `.git/.graphite_repo_config`" |
| `entries` | `list[str]` | Ordered list of branch names, trunk-closest first (position 0). Cannot be empty after first transition from DRAFT. | `explore.md` line 73: "Bottom-up review: review from the bottom of the stack (closest to main) upwards" |
| `status` | `Literal["DRAFT","SUBMITTED","MERGING","MERGED","ABANDONED"]` | Default `"DRAFT"`. Must follow state transition rules. | Pattern mirrors `IssueRecord.status` Literal at `ledger.py:29` |
| `timestamp` | `datetime` | UTC, auto-set on creation. | Standard field; `IssueRecord.created_at` pattern at `ledger.py:31` |

**Business invariants**:
- A `stack_id` exists for at most one active (non-ABANDONED, non-MERGED) stack per issue.
- Entries must map 1:1 to branches that exist in git at time of record creation (validated via `git rev-parse --verify`).
- No entry may reference a `TaskRecord` whose `status ≠ "COMPLETED"` unless the task's `execution_mode = "IMMEDIATE"`. Per constitution: "Each layer has strict phase gates — no layer may be skipped." (`specs/constitution.md` §[1_ARCHITECTURAL_PRINCIPLES]).

### StackEntryRecord
- **Source-of-truth**: `.deviate/pr_stacks.jsonl` (same ledger; compound-key dedup per `(branch_name, status)`)
- **Lifecycle owner**: `src/deviate/state/pr_stack.py`

| Attribute | Type | Invariants | Source Anchor |
| :--- | :--- | :--- | :--- |
| `stack_id` | `str` | FK to `PRStackRecord.stack_id`. | Same ledger, resolved via sequential parse. |
| `branch_name` | `str` | Valid git branch name. Created via `gt create`. | `explore.md` line 84: "gt create (new branch)" |
| `task_id` | `str` | Pattern `^TSK-\d{3}-\d{2}$`. References the TDD task this branch implements. | `TaskRecord.id` at `ledger.py:83-85` |
| `position` | `int` | Zero-based, 0 = trunk-closest (top of stack, reviewed first). | `explore.md` line 73: "Bottom-up review: review from the bottom of the stack (closest to main) upwards" |
| `pr_number` | `int \| None` | GitHub PR number. Set after `gt submit` succeeds. Null before submission. | `explore.md` line 84: "gt submit (push + create/update PRs)" |
| `pr_url` | `str \| None` | GitHub PR URL. Null before submission. | Existing `pr_url` in `deviate-pr/SKILL.md` pre-phase contract |
| `status` | `Literal["PENDING","PUSHED","IN_REVIEW","MERGED","CONFLICT"]` | Default `"PENDING"`. CONFLICT is terminal (requires human resolution). | Pattern mirrors `TaskRecord.status` at `ledger.py:63-74` |
| `timestamp` | `datetime` | UTC, auto-set. | Standard; `IssueRecord.created_at` at `ledger.py:31` |

**Business invariants**:
- One `StackEntryRecord` per `(stack_id, branch_name)` — no duplicate branches within a stack.
- `position` values must be contiguous from 0 for entries in the same stack (no gaps).
- A `pr_number` may only be set when `status ≥ "PUSHED"`. Per `explore.md` line 74: "Submit PRs as soon as they're ready to review."

### PRReviewRecord
- **Source-of-truth**: `.deviate/review/pr_reviews.jsonl` (append-only JSONL)
- **Lifecycle owner**: `src/deviate/state/pr_stack.py` (or `src/deviate/cli/review.py` extended)

| Attribute | Type | Invariants | Source Anchor |
| :--- | :--- | :--- | :--- |
| `review_id` | `str` | Pattern `^REV-\d{3}-\d{2}$`. Unique per review event. | Pattern modeled after `TaskRecord.id` at `ledger.py:83` |
| `stack_id` | `str \| None` | References `PRStackRecord.stack_id` when reviewing the full stack. Null for single-entry review. | |
| `entry_branch` | `str \| None` | References `StackEntryRecord.branch_name` when reviewing a single PR. Null for full-stack reviews. | |
| `reviewer` | `Literal["deviate","graphite-agent","human"]` | `"deviate"` = built-in skill; `"graphite-agent"` = Graphite's Diamond review; `"human"` = HITL Gate 3. | `explore.md` line 86: "Graphite AI Review (Diamond → Graphite Agent): Focuses on real bugs" |
| `review_tool` | `str` | Tool used: `"deviate-review"`, `"graphite-agent"`, `"coderabbit"`. | `explore.md` line 91: "CodeRabbit: AI-native code review" |
| `status` | `Literal["PENDING","IN_PROGRESS","APPROVED","CHANGES_REQUESTED","DISMISSED"]` | Default `"PENDING"`. | |
| `summary` | `str` | Min length 1. Review summary text. | Existing `review post` pattern at `review.py:147-168` |
| `violations` | `list[str]` | List of violation descriptions (security, constitution, style). Empty = clean review. | `deviate-review/SKILL.md`: "flagging cross-cutting issues that no single TDD cycle catches" |
| `timestamp` | `datetime` | UTC, auto-set. | Standard. |

**Business invariants**:
- Exactly one of `stack_id` or `entry_branch` must be non-null (mutually exclusive).
- A review in `CHANGES_REQUESTED` status blocks the parent stack from transitioning to `MERGING`.
- All entries in a stack must have `status ≥ "PUSHED"` before a full-stack review is initiated. Per `explore.md` line 72: "Stack atomicity: Each PR in a stack must be independently reviewable."

## Relationship Graph

| From | Relationship | To | Cardinality | On-Delete | On-Cascade | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PRStackRecord` | parented_by | `IssueRecord` | M:1 | No action (append-only; COMPLETED issue keeps stack history) | Mark stack ABANDONED if issue is re-opened | `IssueRecord.issue_id` → `PRStackRecord.issue_id` at `ledger.py:26` |
| `StackEntryRecord` | belongs_to | `PRStackRecord` | M:1 | Remove entry from stack's `entries` list (new transition record) | Mark stack ABANDONED if all entries are CONFLICT | `stack_id` FK; same ledger |
| `StackEntryRecord` | implements | `TaskRecord` | 1:1 | No action (tasks are immutable history) | Entry status mirrors task completion | `task_id` → `TaskRecord.id` at `ledger.py:60` |
| `PRReviewRecord` | reviews | `PRStackRecord` or `StackEntryRecord` | M:1 (per stack or per entry) | No action (review history is immutable) | `CHANGES_REQUESTED` blocks `MERGING` transition | `stack_id` / `entry_branch` FK |
| `StackEntryRecord` | maps_to | GitHub PR | 1:1 | PR closure is external; entry status updated reactively | MERGED entry removes from active stack ordering | `explore.md` line 84: "PR per branch: Each branch in a stack maps to one GitHub PR" |

## Schema Tables

### PRStackRecord (Pydantic)
```python
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PRStackRecord(BaseModel):
    """A Graphite PR stack for a DeviaTDD issue.

    Source-of-truth: .deviate/pr_stacks.jsonl (append-only)
    Idempotency: compound key (stack_id, status)
    """

    stack_id: str
    issue_id: str = Field(min_length=1)
    trunk: str = "main"
    entries: list[str] = []
    status: Literal["DRAFT", "SUBMITTED", "MERGING", "MERGED", "ABANDONED"] = "DRAFT"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "forbid"}

    @field_validator("stack_id")
    @classmethod
    def _validate_stack_id(cls, v: str) -> str:
        if not re.match(r"^STK-\d{3}$", v):
            raise ValueError(f"Invalid stack ID format: {v}. Expected STK-NNN")
        return v

    @field_validator("entries")
    @classmethod
    def _validate_entries_unique(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("Stack entries must have unique branch names")
        return v
```

### StackEntryRecord (Pydantic)
```python
class StackEntryRecord(BaseModel):
    """A single branch/PR within a Graphite stack.

    Source-of-truth: .deviate/pr_stacks.jsonl (same ledger, inline entries)
    Idempotency: compound key (branch_name, status)
    """

    stack_id: str
    branch_name: str = Field(min_length=1)
    task_id: str
    position: int = Field(ge=0)
    pr_number: int | None = None
    pr_url: str | None = None
    status: Literal["PENDING", "PUSHED", "IN_REVIEW", "MERGED", "CONFLICT"] = "PENDING"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "forbid"}

    @field_validator("task_id")
    @classmethod
    def _validate_task_id(cls, v: str) -> str:
        if not re.match(r"^TSK-\d{3}-\d{2}$", v):
            raise ValueError(f"Invalid task ID format: {v}")
        return v

    @field_validator("pr_number")
    @classmethod
    def _pr_number_only_when_pushed(cls, v: int | None, info) -> int | None:
        if v is not None and info.data.get("status") not in {"PUSHED", "IN_REVIEW", "MERGED", "CONFLICT"}:
            raise ValueError("pr_number requires status >= PUSHED")
        return v
```

### PRReviewRecord (Pydantic)
```python
class PRReviewRecord(BaseModel):
    """A review event on a PR stack or individual stack entry.

    Source-of-truth: .deviate/review/pr_reviews.jsonl (append-only)
    Idempotency: compound key (review_id, status)
    """

    review_id: str
    stack_id: str | None = None
    entry_branch: str | None = None
    reviewer: Literal["deviate", "graphite-agent", "human"] = "deviate"
    review_tool: str = "deviate-review"
    status: Literal["PENDING", "IN_PROGRESS", "APPROVED", "CHANGES_REQUESTED", "DISMISSED"] = "PENDING"
    summary: str = Field(min_length=1)
    violations: list[str] = []
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "forbid"}

    @field_validator("review_id")
    @classmethod
    def _validate_review_id(cls, v: str) -> str:
        if not re.match(r"^REV-\d{3}-\d{2}$", v):
            raise ValueError(f"Invalid review ID format: {v}. Expected REV-NNN-NN")
        return v

    @field_validator("stack_id")
    @classmethod
    def _validate_target(cls, v: str | None, info) -> str | None:
        if v is None and info.data.get("entry_branch") is None:
            raise ValueError("Either stack_id or entry_branch must be set")
        if v is not None and info.data.get("entry_branch") is not None:
            raise ValueError("Cannot set both stack_id and entry_branch")
        return v
```

### Persistence Functions (mirroring `ledger.py:147-158`)
```python
def append_stack_transition(record: PRStackRecord, ledger_path: Path) -> bool:
    """Append a status-transition entry for a PR stack. Idempotent on (stack_id, status)."""
    return _append_with_compound_key(
        record_json=record.model_dump_json(),
        key_fields=["stack_id", "status"],
        ledger_path=ledger_path,
    )


def append_entry_transition(record: StackEntryRecord, ledger_path: Path) -> bool:
    """Append a status-transition entry for a stack entry. Idempotent on (branch_name, status)."""
    return _append_with_compound_key(
        record_json=record.model_dump_json(),
        key_fields=["branch_name", "status"],
        ledger_path=ledger_path,
    )


def append_review_record(record: PRReviewRecord, ledger_path: Path) -> bool:
    """Append a review record. Idempotent on (review_id, status)."""
    return _append_with_compound_key(
        record_json=record.model_dump_json(),
        key_fields=["review_id", "status"],
        ledger_path=ledger_path,
    )
```

## State Transitions

### PRStackRecord Status Machine

```
        DRAFT       ← initial state (entries accumulated by agent)
          │
          │ gt submit --stack succeeds (all entries PUSHED)
          ▼
        SUBMITTED    ← awaits review
          │
          │ merge initiated (HITL Gate 3 approval)
          ▼
     ┌─ MERGING ──┐
     │             │
     │ all merged  │ merge failure / stack conflict
     ▼             ▼
   MERGED      ABANDONED   ← terminal states
                     ▲
                     │ from any non-terminal state: human abandons
```

| From | Event | Guard | To | Side Effects |
| :--- | :--- | :--- | :--- | :--- |
| `DRAFT` | `gt submit --stack` succeeds | All entries have `status = "PUSHED"` | `SUBMITTED` | `append_stack_transition()` to ledger; emit contract to `deviate-pr/SKILL.md` |
| `SUBMITTED` | HITL Gate 3 approval | All entries have latest `PRReviewRecord.status = "APPROVED"` (human reviewer); or `--auto-merge` flag with AI advisory approval | `MERGING` | `append_stack_transition()`; tell Graphite merge queue to begin |
| `MERGING` | All entries merged | Stack-aware merge queue completes all PRs | `MERGED` | `append_stack_transition()`; mark issue COMPLETED in `issues.jsonl` |
| `MERGING` | Any entry merge failure | Unresolvable conflict detected | `ABANDONED` | `append_stack_transition()`; surface conflict to human |
| `DRAFT` | Human abandon | — | `ABANDONED` | `append_stack_transition()` |
| `SUBMITTED` | Human abandon | — | `ABANDONED` | `append_stack_transition()` |
| `MERGING` | Human abandon | — | `ABANDONED` | `append_stack_transition()` |

### StackEntryRecord Status Machine

```
        PENDING      ← branch created, not yet submitted
          │
          │ gt submit succeeds
          ▼
        PUSHED       ← PR exists on GitHub
       ┌───│────┐
       │   │    │ conflict detected (gt sync failure)
       │   ▼    │
       │ IN_REVIEW ──┐
       │   │         │
       │   ▼         ▼
       │ MERGED   CONFLICT   ← terminal states
       ▲                    ▲
       │ from PENDING / PUSHED / IN_REVIEW
       └────────────────────┘
```

| From | Event | Guard | To | Side Effects |
| :--- | :--- | :--- | :--- | :--- |
| `PENDING` | `gt submit` succeeds | Branch exists, `gt` auth valid | `PUSHED` | `pr_number` and `pr_url` assigned; `append_entry_transition()` |
| `PUSHED` | Review initiated | `PRReviewRecord` with `status = "IN_PROGRESS"` exists for this entry | `IN_REVIEW` | `append_entry_transition()` |
| `IN_REVIEW` | PR merged | GitHub PR status = merged | `MERGED` | Entry removed from stack ordering; dependent entries shift position up; `append_entry_transition()` |
| `PENDING` | `gt sync` detects conflict | Conflict during restack | `CONFLICT` | Surface to human; requires manual rebase |
| `PUSHED` | `gt sync` detects conflict | Conflict during restack | `CONFLICT` | Surface to human; requires manual rebase |
| `IN_REVIEW` | `gt sync` detects conflict | Conflict during restack | `CONFLICT` | Surface to human; requires manual rebase |

## Data Flow

### Flow 1: Single Task PR Stack Creation (via Graphite)

**Trigger**: After `deviate execute` or TDD cycle completion (post-REFACTOR). `task.status = "COMPLETED"`.

> *`AGENTS.md`: "RED → GREEN → JUDGE → REFACTOR. Execute: direct task execution (non-TDD)."*

```
1. SessionState reports task TSK-001-01 is COMPLETED.
                           │
2. _resolve_branch_name(task_id) → "feat/001-task-01"
   Source: meso.py line 929-933
                           │
3. gt create feat/001-task-01 --onto main
   Source: explore.md line 84: "gt create (new branch)"
                           │
4. Append StackEntryRecord:
     stack_id="STK-001", task_id="TSK-001-01",
     branch_name="feat/001-task-01", status="PENDING", position=0
   Source: pr_stack.py — append_entry_transition()
                           │
5. gt submit  → GitHub PR created, pr_number=42, pr_url assigned
   Source: explore.md line 84: "gt submit (push + create/update PRs)"
                           │
6. Append StackEntryRecord (transition):
     same entry, status="PUSHED", pr_number=42, pr_url="https://..."
                           │
7. console.print(f"[green]PR_CREATED[/] {pr_url}")
   Pattern: meso.py line 1042
```

### Flow 2: Multi-Task Issue Stack Submission

**Trigger**: All tasks for an issue are COMPLETED. `deviate pr --graphite` invoked.

> *`meso.py`: "PR — new pre/run subcommand behavior"*
> *`explore.md` line 72: "Stack atomicity: Each PR in a stack must be independently reviewable"*

```
1. _pr_pre() extended: detect multiple completed tasks for active issue.
   Source: meso.py lines 906-950 (existing _pr_pre)
                           │
2. For each COMPLETED task TSK-001-{01,02,03}:
   ├─ Resolve branch name from StackEntryRecord
   ├─ If entry.status == "PENDING":
   │    gt create feat/001-task-{NN} --onto {trunk or prior branch}
   └─ gt submit → assign pr_number, pr_url
                           │
3. Append PRStackRecord:
     stack_id="STK-001", issue_id="ISS-001",
     entries=["feat/001-task-01", "feat/001-task-02", "feat/001-task-03"],
     status="DRAFT"
                           │
4. For each entry: Append StackEntryRecord (status="PUSHED")
                           │
5. gt submit --stack  → pushes all stacked PRs
   Source: explore.md line 84: "gt submit --stack (push all PRs in stack)"
                           │
6. Append PRStackRecord (transition): status="SUBMITTED"
                           │
7. gt log → visualize stack for HITL confirmation
   Source: explore.md line 84: "gt log (visualize stack)"
                           │
8. Contract emitted (JSON on stdout):
   { "status": "SUBMITTED", "stack_id": "STK-001",
     "entries": [...], "pr_urls": [...] }
   Pattern: deviate-pr/SKILL.md pre-phase contract
```

### Flow 3: Stack Review Cycle (Deviate + Optional Graphite AI Advisory)

**Trigger**: PR stack status = `"SUBMITTED"`. Human or automated review initiated.

> *`explore.md` line 86: "Graphite AI Review (Diamond → Graphite Agent): Focuses on real bugs — not just style issues or best practices."*
> *`deviate-review/SKILL.md`: "lightweight single-pass scan over the PR's diff, flagging cross-cutting issues that no single TDD cycle catches"*

```
1. deviate review pre (extended for stacks)
   Source: review.py lines 17-49 (existing review pre)
                           │
2. Gather context for each stack entry:
   ├─ git diff {trunk}..{branch_name} per entry
   ├─ constitution_path resolved
   └─ prd_path resolved (epic-scoped)
                           │
3. Append PRReviewRecord:
     review_id="REV-001-01", stack_id="STK-001",
     reviewer="deviate", review_tool="deviate-review",
     status="IN_PROGRESS", summary="", violations=[]
                           │
4. AI Review Execution — two parallel paths:
   ┌─────────────────────────────────────────────────────────┐
   │ Path A: Built-in deviate-review skill                   │
   │  - Scans ledger integrity (tasks→commits alignment)    │
   │  - Scans cross-file consistency                        │
   │  - Scans security surface                              │
   │  Source: deviate-review/SKILL.md                       │
   ├─────────────────────────────────────────────────────────┤
   │ Path B: graphite-agent (Diamond) — ADVISORY ONLY       │
   │  - Full codebase context analysis                      │
   │  - Real bug detection (not style)                      │
   │  - Custom rules + exclusions support                   │
   │  Output tagged: [AI_ADVISORY]                          │
   │  Source: explore.md §Ecosystem Research                │
   └─────────────────────────────────────────────────────────┘
                           │
5. Append PRReviewRecord (transition):
     status="APPROVED" or status="CHANGES_REQUESTED",
     summary="<review findings>",
     violations=[...]
   Tagged: [AI_ADVISORY: ...] for Graphite Agent findings
                           │
6. console.print review summary (chat-based output, no file persistence)
   Source: deviate-review/SKILL.md: "Chat-based output, no report file"
                           │
7. HITL Gate 3: Human reviews aggregated findings.
   Source: specs/constitution.md: "Three mandatory gates... No gate may be programmatically bypassed."
                           │
8. On APPROVED: stack → MERGING.
   On CHANGES_REQUESTED: stack remains SUBMITTED; author revises.
```

## Source Registry

| ID | Type | Source / Path (Strictly Relative to Repo Root) | Relevance Note |
| :--- | :--- | :--- | :--- |
| SRC-01 | Constitution | `specs/constitution.md` | Database constraints (JSONL), tech stack (Pydantic models) |
| SRC-02 | Explore_MD | `specs/004-graphite-pr-stacks/explore.md` | Ecosystem research: Graphite commands, best practices, entity grounding |
| SRC-03 | Codebase_File | `src/deviate/state/ledger.py` | Pattern reference: `IssueRecord`, `TaskRecord`, `_append_with_compound_key` |
| SRC-04 | Codebase_File | `src/deviate/state/config.py` | `SessionState` phase model — NOT modified; PR/stack kept out of micro-layer phases |
| SRC-05 | Codebase_File | `src/deviate/cli/meso.py` | Existing `_pr_pre()`/`_pr_run()` — Graphite extends these |
| SRC-06 | Codebase_File | `src/deviate/cli/review.py` | Review pre/post — extended for stack review advisory |
| SRC-07 | Skill | `src/deviate/prompts/skills/deviate-pr/SKILL.md` | PR orchestration skill — gains Graphite conditional branch |
| SRC-08 | Skill | `src/deviate/prompts/skills/deviate-review/SKILL.md` | Review skill — extended with Graphite AI advisory supplement path |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 004-graphite-pr-stacks |
| EPIC_ID | 004-graphite-pr-stacks |
| SPEC_TARGET_DATAMODEL | specs/004-graphite-pr-stacks/data-model.md |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the `prd` skill |
