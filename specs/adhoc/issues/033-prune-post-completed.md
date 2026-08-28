---
title: "Redefine /deviate-prune as manual honeycomb test thinning"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-033
flow_refs: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/033-prune-post-completed.md`
- **Primary Architectural Workstation**: `src/deviate/prompts/commands/deviate-prune.md`, `src/deviate/prompts/auto/red.md`, `src/deviate/prompts/commands/deviate-red.md`, `src/deviate/prompts/skills/deviatdd/SKILL.md`, `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`

## The Problem Contract
`/deviate-prune` thins implementation-coupled tests (Testing Honeycomb / sociable units). Operators need a **manual** pass that classifies every issue-scoped test — pytest marks and name tags first, then the body when a test has no mark. Untagged tests must not auto-keep. RED must stamp `@pytest.mark.behavioral` | `@pytest.mark.spy` | `@pytest.mark.impl` so later prune has a tag. Prune must never auto-run after micro COMPLETED, `--all`, or the `deviatdd` skill success loop. Spec-delete-on-COMPLETED is out: `apply_prune` / READY must not unlink `plan.md`, `tasks.md`, `explore.md`, `prd.md`, issue md, or JSONL ledgers.

## Scope Boundaries
### Hard Inclusions
- Keep **one** surface: `/deviate-prune` (aliases unchanged). Do not add `/deviate-spec-prune` or a second skill.
- Honeycomb test thinning: drop `spy` / `impl`; keep public `behavioral` / `ac`. Prefer pytest marks and name tags. If a test has no mark, decide from the body (drop internal spies/mocks/private state; keep public input-to-output / AC). Untagged must not auto-keep.
- RED (`auto/red.md` and `/deviate-red`) stamps `@pytest.mark.behavioral` | `@pytest.mark.spy` | `@pytest.mark.impl` on each new test. Most RED tests are behavioral.
- Prune is manual invoke only. Do not hook it into micro COMPLETED, `--all`, or the `deviatdd` skill success loop.
- Never delete `plan.md`, `tasks.md`, `explore.md`, `prd.md`, `specs/**/issues/*.md`, leftover cycle markdown, or JSONL ledgers.
- Thin `deviate prune pre` / `post` CLI remains the contract the prompt calls.

### Defensive Exclusions
- Do **not** compact, rewrite, squash, delete rows from, or delete `specs/issues.jsonl`, `specs/**/tasks.jsonl`, or `specs/_product/flows.jsonl`.
- Do not write a compiled epic digest or "why this exists" essay. That why lives in the behavioral test that would fail if the behavior were removed.
- Do not delete `specs/constitution.md`, in-flight specs, Product/flows (`specs/_product/`), epic `explore.md`, epic `prd.md`, shared `specs/adhoc/prd.md`, or `issues/<slug>.md`.
- Do not change Gate 1, `/deviate-explore`, `/deviate-research`, `/deviate-review`, or ponytail-in-review (ISS-ADH-029).
- Do not alter `flow_refs` mapping or merge=union gitattributes on the ledgers.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-033`
- **Acceptance Criteria Tokens**: `AC-ADHOC-033-01`, `AC-ADHOC-033-02`, `AC-ADHOC-033-03`
- **Data Model Entities**: prune prompt; honeycomb test marks; append-only JSONL ledgers

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **US-033-01**: As a DeviaTDD operator, I want `/deviate-prune` to classify every issue-scoped test (marks, name tags, then body) so spy/impl tests drop and public behavioral / AC tests stay. *(Ref: FR-ADHOC-033)*
- **US-033-02**: As a DeviaTDD operator, I want JSONL ledgers and cycle markdown (`plan.md`, `tasks.md`, explore/prd, issue md) left untouched so prune cannot delete the audit trail or living specs. *(Ref: FR-ADHOC-033)*
- **US-033-03**: As a DeviaTDD operator, I want RED to stamp honeycomb marks on each new test, and prune to stay manual, so untagged tests are not auto-kept and COMPLETED / `--all` / the skill loop never auto-prunes. *(Ref: FR-ADHOC-033)*

## Acceptance Outline
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- **AO-033-01** *(Ref: AC-ADHOC-033-01, US-033-01)*: `/deviate-prune` classifies issue-scoped tests (marks and name tags first; untagged from the body) and thins spy/impl / internal probes while keeping behavioral / `ac` / public I/O.
  - **Happy Path**: After prune, spy/impl and untagged internal probes are gone; public behavioral / AC tests remain; `plan.md` / `tasks.md` still exist.
  - **Error Category**: Targeting an in-flight issue still thins tests and never deletes specs.
  - **Boundary Category**: Untagged tests must not auto-keep; body heuristics decide drop vs keep.
- **AO-033-02** *(Ref: AC-ADHOC-033-02, US-033-02)*: Prune never modifies JSONL ledger bytes and never unlinks cycle markdown.
  - **Happy Path**: `specs/issues.jsonl`, `specs/**/tasks.jsonl`, `specs/_product/flows.jsonl`, `plan.md`, and `tasks.md` are byte-identical / still present after prune.
  - **Error Category**: An instruction to compact, squash, or rewrite a ledger is rejected and prune stops.
  - **Boundary Category**: Empty or missing optional `flows.jsonl` is skipped, not created. READY does not unlink specs.
- **AO-033-03** *(Ref: AC-ADHOC-033-03, US-033-03)*: RED stamps `@pytest.mark.behavioral` | `@pytest.mark.spy` | `@pytest.mark.impl` on each new test. Prune is not hooked into micro COMPLETED, `--all`, or the skill success loop.
  - **Happy Path**: Auto and `/deviate-red` prompts require a honeycomb mark; most RED tests are behavioral.
  - **Error Category**: Skill success loop / `--all` / COMPLETED must not invoke prune.
  - **Boundary Category**: Manual `deviate prune pre` / `post` remains the only apply path.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- Shared `specs/adhoc/prd.md` and epic `specs/{epic}/prd.md` stay.
- Never delete `specs/**/issues/*.md`. Judge `_find_protected_modules` still globs every issue md after COMPLETED.
- README / SKILL.md / API / architecture must describe prune as manual honeycomb thinning, not spec-delete-on-COMPLETED.
- `deviate prune pre` / `post` stay as a thin contract; the slash command remains the operator surface.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/commands/deviate-shard.md -->
- L_max: 2s added for issue-scoped test inventory (no repo-wide test rewrite beyond the targeted suite).
- Throughput: One issue per invocation; do not walk every epic unless the operator names a broader target.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: classify_test pins for marks, name tags, untagged-not-auto-keep, and body honeycomb; prompt pins that RED stamps marks and prune forbids spec deletes.
- **Integration Sandbox Targets**: a fixture issue with cycle markdown + spy + behavioral + untagged tests; after prune, spies gone, public tests and `plan.md` / `tasks.md` / ledger bytes unchanged.

## Demonstration Path
```bash
# From a consumer repo (or this repo) with an issue that has a mix of
# behavioral + spy + untagged tests, plus plan.md / tasks.md.
# Expected after: spy/impl and untagged internal probes gone; behavioral /
# public I/O tests pass; plan.md / tasks.md / issue md / ledgers still present;
# git diff -- specs/issues.jsonl specs/**/tasks.jsonl specs/_product/flows.jsonl is empty.
```
