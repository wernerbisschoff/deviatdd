---
title: "Opt-in /deviate-converge pack after Micro, before PR"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-058
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/058-converge-opt-in-pack.md`
- **Primary Architectural Workstation**: `src/deviate/core/commands.py`, `src/deviate/prompts/commands/deviate-converge.md`, `src/deviate/cli/converge.py`, `src/deviate/cli/__init__.py`, `src/deviate/state/ledger.py`, `tests/unit/test_cli/test_converge.py`

## The Problem Contract
JUDGE is task-scoped. Gate 3 walkthrough and review comment and map — they do not reopen the TDD queue when plan or AO work is still missing across tasks. This issue adds an opt-in Converge pack that assesses this issue's present-state code against this issue's intent, appends gap tasks, and re-enters Micro until clean, then PR.

## Scope Boundaries
### Hard Inclusions
- Opt-in pack `converge` installing `/deviate-converge` plus `deviate converge pre|post`, same class as `pr` / `review` / `walkthrough`
- Issue-scoped Meso loop after this issue's Micro tasks drain and before `/deviate-pr`; may re-enter Micro
- Read set: this issue brief (AO/US/named checks), this issue `plan.md` Acceptance Contract (`AC-PLAN-*`), this issue `tasks.md` plus ledger IDs/status, constitution MUST (if filled), and in-scope code from plan/task paths
- Write set: on gaps, append a single `## Phase N: Convergence` section to this issue's `tasks.md` and matching PENDING `TSK-*` rows via the ledger CLI (`append_task_record`); never hand-edit JSONL
- Taxonomy: every finding is `missing` | `partial` | `contradicts` | `unrequested`; constitution MUST violations are CRITICAL and ordered first
- Clean path leaves `tasks.md` byte-unchanged and reports converged (no empty Convergence header)
- Task IDs continue this issue's `TSK-{issue}-{nn}` series; new Convergence phase number is max existing phase + 1
- Specs Kit append contract adapted to DeviaTDD ledger IDs; present-state assessment only (no git history / branch-diff tool)

### Defensive Exclusions
- Not a Macro phase; not inside per-task JUDGE; not wired into mandatory `deviate run` in MVP
- Converge MUST NOT read epic explore, leftover research, or epic prd/design/data-model unless the brief names those paths
- NEVER rewrite, renumber, or delete existing tasks; NEVER edit `plan.md`, the issue brief, constitution, or application code
- `unrequested` only appends a review/justify/remove task — no auto-delete of code
- No conditional closeout, `closeout.md`, or epic as-built museum
- No "attach related work to an existing epic" explore routing
- No Gate 2 restore; no hard Gate 3 prerequisite (later: soft banner / optional `--converge` only if needed)
- Converge is not a substitute for JUDGE, four-look walkthrough, or review comments

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-058`
- **Acceptance Criteria Tokens**: `AC-ADHOC-058-01`, `AC-ADHOC-058-02`, `AC-ADHOC-058-03`, `AC-ADHOC-058-04`, `AC-ADHOC-058-05`
- **Data Model Entities**: ConvergenceFinding, ConvergenceTask, TaskRecord
- **Remote Source**: `https://github.com/wernerbisschoff/deviatdd/issues/219` (gh issue 219; Spec Kit analog: https://github.com/github/spec-kit/blob/main/templates/commands/converge.md)

## User Stories Ledger
- **US-058-01**: As an operator, I want Converge installed only when I select the `converge` pack so default setup and `deviate run` stay unchanged. *(Ref: FR-ADHOC-058)*
- **US-058-02**: As a Converge agent, I want a bounded read set of this issue's brief, plan AC-PLAN, tasks, constitution MUST, and in-scope code so I do not ingest epic explore or leftover research. *(Ref: FR-ADHOC-058)*
- **US-058-03**: As an operator, I want gap findings appended as Convergence tasks via the ledger CLI so I can re-enter Micro without rewriting existing tasks or application code. *(Ref: FR-ADHOC-058)*
- **US-058-04**: As an operator, I want each finding classified as `missing`, `partial`, `contradicts`, or `unrequested`, and a clean run to leave `tasks.md` byte-unchanged, so I know when to open a PR. *(Ref: FR-ADHOC-058)*
- **US-058-05**: As an operator, I want Converge after this issue's Micro drain and before `/deviate-pr` so walkthrough and review still run after a clean converge. *(Ref: FR-ADHOC-058)*

## Acceptance Outline
- **AO-058-01** *(Ref: AC-ADHOC-058-01, US-058-01)*: Opt-in pack
  - **Happy Path**: Default `deviate setup` does not install Converge commands; `deviate setup --packs converge` installs `/deviate-converge` and `deviate converge pre|post`
  - **Error Category**: Unknown pack names still fail closed; `converge` is a known optional pack after this issue
  - **Boundary Category**: `deviate run` does not auto-invoke Converge in MVP
- **AO-058-02** *(Ref: AC-ADHOC-058-02, US-058-02)*: Read set
  - **Happy Path**: Converge reads this issue brief (AO/US/named checks), this issue `plan.md` Acceptance Contract (`AC-PLAN-*`), this issue `tasks.md` plus ledger IDs/status, constitution MUST when filled, and in-scope code from plan/task paths
  - **Error Category**: Missing issue brief, plan, or tasks stops with an actionable prerequisite message; unfilled constitution template skips constitution checks
  - **Boundary Category**: MUST NOT read epic explore, leftover research, or epic prd/design/data-model unless the brief names those paths
- **AO-058-03** *(Ref: AC-ADHOC-058-03, US-058-03)*: Write set is append-only
  - **Happy Path**: On gaps, append one `## Phase N: Convergence` section (N = max existing phase + 1) and matching PENDING `TSK-{issue}-{nn}` rows via the ledger CLI
  - **Error Category**: Ledger append failure surfaces a named diagnostic and does not rewrite `tasks.md` or JSONL by hand
  - **Boundary Category**: NEVER rewrite, renumber, or delete existing tasks; NEVER edit `plan.md`, the issue brief, constitution, or application code
- **AO-058-04** *(Ref: AC-ADHOC-058-04, US-058-04)*: Taxonomy and clean path
  - **Happy Path**: Every finding is one of `missing` | `partial` | `contradicts` | `unrequested` with a source-ref; constitution MUST violations are CRITICAL and ordered first
  - **Error Category**: `unrequested` only appends a review/justify/remove task — no auto-delete of code
  - **Boundary Category**: When fully satisfied, leave `tasks.md` byte-unchanged and report converged (no empty Convergence header)
- **AO-058-05** *(Ref: AC-ADHOC-058-05, US-058-05)*: Loop and Gate 3 order
  - **Happy Path**: Operator path is Micro drain → `/deviate-converge` → (if tasks appended) Micro again → re-converge until clean → walkthrough → review → `/deviate-pr`
  - **Error Category**: Invoking Converge before this issue's Micro queue drains reports a not-ready diagnostic
  - **Boundary Category**: Converge is not a substitute for JUDGE, four-look walkthrough, or review comments; not a hard Gate 3 prerequisite

## Edge Cases and Boundaries
- Little or no code yet treats the specified scope as `missing` remaining work rather than failing
- A prior Convergence phase stays untouched; a later run adds a new separately numbered phase below it
- Present-state assessment only — no git history, branch-diff, or merge-base tool
- Soft banner or optional `--converge` on `deviate run` is out of scope for MVP
- Gate 2 restore and closeout / as-built museum stay out of scope

## Performance Constraints
- L_max: 500ms for `deviate converge pre` contract emission on a typical issue
- Throughput: one issue per invocation; append-only writes are a single `tasks.md` section plus matching ledger rows

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/unit/test_cli/test_converge.py` — pack not in default setup, pre/post JSON contracts, append-only ledger writes, clean-path no-op, fabricated missing AC appends Convergence tasks with `missing` plus source-ref
- **Integration Sandbox Targets**: optional-pack tests classify `converge` with `review` / `walkthrough` / `pr`; default setup install list excludes Converge commands

## Demonstration Path
```bash
# pack off by default
TMP=$(mktemp -d) && cd "$TMP"
deviate setup --agent opencode --packs none
test ! -f .opencode/commands/deviate-converge.md

# pack on when selected
deviate setup --agent opencode --packs converge
test -f .opencode/commands/deviate-converge.md

# contracts + append-only / clean-path pins
uv run pytest tests/unit/test_cli/test_converge.py -v
```
