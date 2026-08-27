---
title: "Redefine /deviate-prune as post-COMPLETED spec+test cleanup"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-033
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/033-prune-post-completed.md`
- **Primary Architectural Workstation**: `src/deviate/prompts/commands/deviate-prune.md`, `src/deviate/prompts/skills/deviatdd/SKILL.md`, `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`

## The Problem Contract
`/deviate-prune` is a TDD PRUNE phase that thins implementation-coupled tests (Testing Honeycomb / sociable units). After an issue is COMPLETED, cycle markdown (`explore.md`, `design.md`, `data-model.md`, leftover `prd.md`, `plan.md`, `tasks.md`) is left in `specs/` by hand. Coworkers and later agents treat that scaffolding as living SoT. There is no single command that does post-COMPLETED cleanup of both spy/impl tests and that ticket's cycle markdown. JSONL ledgers must stay an append-only audit trail.

## Scope Boundaries
### Hard Inclusions
- Keep **one** surface: `/deviate-prune` (aliases unchanged). Do not add `/deviate-spec-prune` or a second skill.
- Keep existing honeycomb test thinning: drop `spy` / `impl` tests; retain public behavioral / `ac` contracts.
- After the targeted issue is COMPLETED, delete that issue or epic's cycle markdown: `explore.md`, `design.md`, `data-model.md`, leftover `prd.md`, `plan.md`, `tasks.md`, the issue file if nothing in-flight still points at it, and empty completed folders.
- Promote ACs out of `plan.md` into behavioral tests before deleting the plan. Halt if those ACs are not yet encoded as tests.
- Optionally add a thin `deviate prune pre` / `post` CLI if the rewritten prompt still calls it and the group is still missing (prompt on 2.23.1 calls `deviate prune pre` / `post`; no `prune_app` is registered).

### Defensive Exclusions
- Do **not** compact, rewrite, squash, delete rows from, or delete `specs/issues.jsonl`, `specs/**/tasks.jsonl`, or `specs/_product/flows.jsonl`.
- Do not write a compiled epic digest or "why this exists" essay. That why lives in the behavioral test that would fail if the behavior were removed.
- Do not delete `specs/constitution.md`, in-flight specs for open issues, or Product/flows (`specs/_product/`).
- Do not change Gate 1, `/deviate-explore`, `/deviate-research`, `/deviate-review`, or ponytail-in-review (ISS-ADH-029).
- Do not alter `flow_refs` mapping or merge=union gitattributes on the ledgers.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-033`
- **Acceptance Criteria Tokens**: `AC-ADHOC-033-01`, `AC-ADHOC-033-02`, `AC-ADHOC-033-03`
- **Data Model Entities**: prune prompt; COMPLETED issue cycle markdown; append-only JSONL ledgers

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-033-01**: As a DeviaTDD operator, I want `/deviate-prune` after COMPLETED to drop that ticket's cycle markdown and spy/impl tests so `specs/` and the test suite stay maintainable on one command. *(Ref: FR-ADHOC-033)*
- **US-033-02**: As a DeviaTDD operator, I want JSONL ledgers left untouched so the audit trail cannot be compacted or rewritten by prune. *(Ref: FR-ADHOC-033)*
- **US-033-03**: As a DeviaTDD operator, I want prune to halt if plan ACs are not yet encoded as behavioral tests, so deleting `plan.md` cannot orphan the contract. *(Ref: FR-ADHOC-033)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-033-01** *(Ref: AC-ADHOC-033-01, US-033-01)*: `/deviate-prune` on a COMPLETED issue removes that issue's cycle markdown listed in Hard Inclusions and thins spy/impl tests while keeping behavioral / `ac` tests.
  - **Happy Path**: After prune, the COMPLETED issue folder has no `explore.md` / `plan.md` / `tasks.md` (and no empty leftover dir); public behavioral tests still pass.
  - **Error Category**: Targeting an in-flight (non-COMPLETED) issue is a no-op for spec deletion and reports why.
  - **Boundary Category**: Honeycomb test thinning still runs when there is no cycle markdown left to delete.
- **AO-033-02** *(Ref: AC-ADHOC-033-02, US-033-02)*: Prune never modifies JSONL ledger bytes except by refusing to touch them.
  - **Happy Path**: `specs/issues.jsonl`, `specs/**/tasks.jsonl`, and `specs/_product/flows.jsonl` are byte-identical before and after prune.
  - **Error Category**: An instruction to compact, squash, or rewrite a ledger is rejected and prune stops.
  - **Boundary Category**: Empty or missing optional `flows.jsonl` is skipped, not created.
- **AO-033-03** *(Ref: AC-ADHOC-033-03, US-033-03)*: `plan.md` is not deleted until each of its ACs is present as a behavioral / `ac` test.
  - **Happy Path**: ACs already in tests; plan is deleted; tests remain.
  - **Error Category**: Missing AC encoding halts with the unmatched AC tokens named; no cycle-markdown deletes land.
  - **Boundary Category**: A COMPLETED issue with no `plan.md` skips this gate and still deletes the other listed leftovers.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- Shared `specs/adhoc/prd.md` is not "that issue's leftover prd" — do not delete the shared adhoc PRD ledger.
- Issue file deletion only when no in-flight issue `source_file` or `coordinates_with` still points at it.
- README / SKILL.md / API / architecture must describe prune as post-COMPLETED spec+test cleanup, not "stale tests only".
- `deviate prune pre` / `post` may be added as a thin contract, but the slash command remains the operator surface.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- L_max: 2s added for COMPLETED-issue file inventory (no repo-wide test rewrite beyond the targeted suite).
- Throughput: One issue per invocation; do not walk every COMPLETED epic unless the operator names a broader target.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: prompt/help tests that `/deviate-prune` description names spec+test cleanup and forbids ledger compaction; any new `deviate prune pre` contract parser.
- **Integration Sandbox Targets**: a fixture COMPLETED issue with cycle markdown + one spy test + one behavioral test + a JSONL ledger; after prune, markdown and spy test gone, behavioral test and ledger bytes unchanged.

## Demonstration Path
```bash
# From a consumer repo (or this repo) with a COMPLETED adhoc issue that still has plan.md / tasks.md
# and a mix of behavioral + spy tests.
# Expected after: cycle markdown for that issue gone; spy tests gone; behavioral tests pass;
# git diff -- specs/issues.jsonl specs/**/tasks.jsonl specs/_product/flows.jsonl is empty.
```
