---
title: "Narrow Product-Layer Flow Scope — Fix explore_post Ledger Commit, Add Release Flow Tagging, Retire Meso/Micro Ceremony"
labels: [refactor, adhoc, product-layer, ledger, scope-reduction]
blocked_by: []
coordinates_with: ["ISS-ADH-013"]
issue_id: ISS-ADH-015
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/015-narrow-product-flow-scope.md`
- **Primary Architectural Workstations**:
  - `src/deviate/cli/macro.py:366-410` — `explore_post` MODIFY: restructure commit ordering so `_run_flow_ledger_cycle(specs_root)` runs *before* `stage_and_commit`, and `flows_ledger_path` is added to the artifact list so the ledger change lands in the same commit as `explore.md`. Today the cycle runs after the commit; the ledger write is orphaned on the working tree.
  - `src/deviate/cli/macro.py:25,397` — `commit_artifact` REPLACE with `stage_and_commit([explore_path, flows_ledger_path], ...)` so both files commit atomically.
  - `src/deviate/cli/release.py` — NEW: `release_app` Typer group exposing `tag-included --release-md <path> --version <ver>`. Reads `## Included Flows` markdown table, appends one `FLOW_INCLUDED_IN_RELEASE` event per flow ID, stages `specs/_product/flows.jsonl`. Registers in `src/deviate/cli/__init__.py` next to existing sub-app groups.
  - `src/deviate/cli/__init__.py` — REGISTER the new `release_app` Typer group.
  - `src/deviate/cli/inspect.py:482,510-513` — NO CHANGE: existing `inspect flows candidates --include-released` already consumes `FLOW_INCLUDED_IN_RELEASE` once Slice 2 lands the new producer.
  - `src/deviate/state/ledger.py:404-413` — `FlowEvent.event_type` Literal union MODIFY: remove `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` (no producers).
  - `src/deviate/state/ledger.py:630-639` — `_derive_impl_status` MODIFY: remove `PARTIALLY_IMPLEMENTED` branch (the only producer `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` is retired). `FlowImplementationStatus` Literal simplifies to `["CONFIRMED_IMPLEMENTED", "UNCONFIRMED"]`.
  - `src/deviate/state/ledger.py:441-451,463-470` — `FlowDriftFlag` Literal KEEP all seven flags. `PROMPT_ONLY_NO_CODE` and `DOC_ARTIFACT_ONLY` still fire correctly post-narrowing because `flow_refs` on issues remains a real input and `flows sync` produces `discovered`/`documented` flags.
  - `src/deviate/state/ledger.py:721-727` — `_implementation_evidence_paths` REMOVE (no callers once `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` is retired).
  - `src/deviate/prompts/core/micro-shared.md:50-52` — REMOVE the `<item><title>Flow-Anchored Implementation</title>…</item>` block from `<shared_disciplines>`. This is the third micro-layer invariant today, alongside Test-First and Git Isolation; removing it is a substantial prompt surgery, not a one-line change.
  - `src/deviate/prompts/core/meso-shared.md:37-39` — REMOVE the `<item><title>Flow Reference Propagation</title>…</item>` block from `<shared_disciplines>`. Meso stops propagating `flow_refs` to plan/tasks.
  - `src/deviate/prompts/auto/judge.md:198,244,271` — REMOVE `flow_alignment` field from the handover manifest schema. Update edge-case table.
  - `src/deviate/prompts/auto/red.md`, `green.md`, `refactor.md` — REMOVE any `flow_refs` restatement instructions (grep first).
  - `src/deviate/prompts/auto/plan.md:63-64,143,157` — REMOVE `## Product Layer Anchors` section template and `flow_refs` references.
  - `src/deviate/prompts/auto/tasks.md:25,69,72,182,198` — REMOVE `**Flow References**` field on tasks.
  - `src/deviate/prompts/commands/deviate-plan.md:128-129` — REMOVE `## Product Layer Anchors` references.
  - `src/deviate/prompts/commands/deviate-tasks.md:80,84` — REMOVE flow-driven `[E2E]` task gating (the gating logic stays — only the flow-derivation language is removed).
  - `src/deviate/prompts/commands/deviate-judge.md:140,184,228` — REMOVE `flow_alignment` field.
  - `src/deviate/prompts/commands/deviate-release.md:120-140` — UPDATE workflow step 2.5 to invoke `deviate release tag-included --release-md <path> --version <ver>` before the release commit lands.
  - `src/deviate/prompts/commands/deviate-flows.md` — NO CHANGE today (slash command already manages sign-off commit). The current command emits the canonical `flows-<domain>.md` files + `index.md` row but does not invoke `deviate flows sync` to seed the ledger; that's a separate scope decision deferred from this issue (see Open Questions).
  - `specs/DeviaTDD-api.md` — REMOVE `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` from the event-type taxonomy.
  - `specs/constitution.md:33,98` — DROP mention of retired event types in §2 Database and §9 Version History.
  - `tests/unit/test_macro/test_explore.py` — NEW: `test_explore_post_commits_flows_ledger_atomically`. Asserts working tree is clean post-call when flows ledger had changes.
  - `tests/unit/test_cli/test_release.py` — NEW: covers parse + idempotent + missing-table paths for the new `deviate release tag-included` command.
  - `tests/unit/test_state/test_ledger.py` — DROP tests for retired event types. UPDATE `_derive_impl_status` tests for the simplified Literal.
  - `tests/unit/test_cli/test_inspect.py:812,871` — DROP corresponding test cases.
  - `tests/unit/test_core/test_flow_confirmation.py:454,490` — DROP corresponding test cases.
  - `tests/unit/test_micro/test_orchestration.py` — DROP any test asserting `flow_alignment` (verify by grep).
- **Upstream Evidence**:
  - `git log --follow --pretty=format:"%H %s" -- specs/_product/flows.jsonl` → single commit (`69a630e`). The ledger has been modified exactly once, by accident, as a side effect of `_run_flow_ledger_cycle` running inside the squash-merge worktree for that fix.
  - `specs/_product/flows.jsonl` live data: 2 rows, both `FLOW_REFERENCED_BY_ISSUE`. Zero identity rows. Zero `FLOW_DISCOVERED`/`FLOW_DOCUMENTED`/`FLOW_CONFIRMED_IMPLEMENTED`.
  - `grep -rn "append_flow_event\|FLOW_INCLUDED_IN_RELEASE\|FLOW_IMPLEMENTATION_EVIDENCE_ADDED\|FLOW_DEPRECATED" src/ --include="*.py"` → zero producers for three of the seven declared event types.
  - `grep -rn "flow_refs" src/deviate/prompts/ | wc -l` → 79 mentions across the prompt corpus. The system is heavily instrumented for a feature with one canonical flow in production (`FLOW-04`).
  - `deviate inspect flows coverage` reports `FLOW-04: PROMPT_ONLY_NO_CODE` despite the TUI renderer shipping in `main`. The drift flag is wrong because no `FlowRecord` was ever written.
  - `src/deviate/cli/macro.py:397-409` shows the smoking gun: `commit_artifact(explore_path)` runs before `_run_flow_ledger_cycle(specs_root)`. The append to `flows.jsonl` is orphaned.

## The Problem Contract

The Product-layer flow ledger (`specs/_product/flows.jsonl`) and `flow_refs` machinery are wired into every DeviaTDD layer, but only **release composition** has a clear use case. Three concrete defects exist today:

1. **Orphaned ledger writes.** `deviate explore post` appends to `flows.jsonl` then exits. No commit fires for the ledger. The two existing rows in the file landed because the `69a630e` squash-merge happened to capture the working tree, not because anyone intended to commit them.
2. **Missing event producers.** Three of the seven declared `FlowEvent` types (`FLOW_DEPRECATED`, `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`, `FLOW_INCLUDED_IN_RELEASE`) have zero call sites in `src/`. The release workflow reads the ledger but never writes to it.
3. **Over-instrumentation.** Meso plans carry a `## Product Layer Anchors` section. Tasks carry `**Flow References**`. Micro JUDGE carries a `flow_alignment` rubric dimension. These exist for one production flow (`FLOW-04`) — a developer-tool feature, not a user-facing product flow.

The cost is prompt bloat in every meso/micro phase, with no enforcement value beyond what release-time `deviate inspect flows coverage` already provides.

## Scope Boundaries

### Hard Inclusions
- Slice 1: Restructure `explore_post` so the flows ledger commits in the same call as `explore.md`. New test asserting working tree is clean.
- Slice 2: New CLI `deviate release tag-included --release-md <path> --version <ver>`. Parses `## Included Flows` table, appends `FLOW_INCLUDED_IN_RELEASE` events, stages the ledger. Updated `/deviate-release` slash command workflow.
- Slice 3: Remove the `Flow-Anchored Implementation` shared discipline from micro-shared. Remove `flow_alignment` from JUDGE handover manifest schema.
- Slice 4: Remove the `Flow Reference Propagation` shared discipline from meso-shared. Remove `## Product Layer Anchors` from plan and `**Flow References**` from tasks.
- Slice 5: Retire `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` event types. Drop `PARTIALLY_IMPLEMENTED` from `_derive_impl_status`. Update tests, API spec, and constitution.

### Defensive Exclusions
- Modifying `_FLOW_REF_PATTERN` or `IssueRecord.flow_refs` field semantics.
- Touching the slash command `/deviate-flows` (its relationship to `deviate flows sync` is a separate scope decision deferred from this issue; see Open Questions).
- Changing `flows/index.md` schema or `seed_flow_ledger` behavior.
- Adding new producers for retired event types.
- Changing `_derive_drift_flag` taxonomy beyond removing `PARTIALLY_IMPLEMENTED` references. The seven drift flags stay (per design rationale above).

### Open Questions (deferred to follow-up)
1. **Should `/deviate-flows` invoke `deviate flows sync`?** Today no slash command invokes the sync, which is why zero identity rows exist. Out of scope here but worth a follow-up issue.
2. **Should the `_run_flow_ledger_cycle` reverse-index helper be timestamped at the call site rather than the issue record's `created_at`?** Today the ghost-row bug (timestamps matching past issues but rows appearing in unrelated commits) makes `last_referenced_by_issue_id` ordering in `select_release_candidate_flows` unreliable. Out of scope here.
3. **Should `deviate flows sync` be auto-invoked by `deviate explore post` after Flow Coverage finds orphan `flow_refs`?** Operators get a `[yellow]FLOWS_INDEX_ORPHAN[/]` banner but no auto-fix. Out of scope here.

## Acceptance Criteria

1. **AC-NARROW-01** (Slice 1): Given `deviate explore post --slug foo` runs in a repo where flows ledger has rows to append, When the call completes, Then `git status` shows zero working-tree changes and the latest commit contains both `specs/explore/foo.md` and `specs/_product/flows.jsonl`.
2. **AC-NARROW-02** (Slice 2): Given `release-next.md` `## Included Flows` table contains `| FLOW-04 | … |`, When `deviate release tag-included --release-md specs/_product/release-next.md --version 1.0.0` runs, Then `specs/_product/flows.jsonl` gains one `FLOW_INCLUDED_IN_RELEASE` row with `flow_id="FLOW-04"`, `event_release_version="1.0.0"`, `event_issue_id=null`, `evidence_path=null`, `event_type="FLOW_INCLUDED_IN_RELEASE"`. Re-running is idempotent (compound key `(flow_id, event_type, event_release_version)`).
3. **AC-NARROW-03** (Slice 2): Given `release-next.md` lacks a `## Included Flows` table, When the command runs, Then it exits non-zero with `[red]RELEASE_INCLUDED_FLOWS_MISSING[/]` and writes nothing.
4. **AC-NARROW-04** (Slice 3): Given the micro-shared prompt is loaded, When the agent reads `<shared_disciplines>`, Then it contains no `Flow-Anchored Implementation` item. The JUDGE handover manifest schema contains no `flow_alignment` field.
5. **AC-NARROW-05** (Slice 4): Given the meso-shared prompt is loaded, When the agent reads `<shared_disciplines>`, Then it contains no `Flow Reference Propagation` item. The plan template contains no `## Product Layer Anchors` section. The task template contains no `**Flow References**` field.
6. **AC-NARROW-06** (Slice 5): Given `FlowEvent.model_validate({"flow_id": "FLOW-04", "event_type": "FLOW_DEPRECATED", "timestamp": "2026-01-01T00:00:00Z"})` is called, Then Pydantic raises `ValidationError`. Same for `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`.
7. **AC-NARROW-07** (Slice 5): Given `_derive_impl_status(events)` is called, When the only event is `FLOW_DISCOVERED`, Then it returns `"UNCONFIRMED"`. When `FLOW_CONFIRMED_IMPLEMENTED` is present, Then it returns `"CONFIRMED_IMPLEMENTED"`. The function no longer references `PARTIALLY_IMPLEMENTED`.
8. **AC-NARROW-08** (full suite): `mise run test` exits 0 with all five slices applied.
9. **AC-NARROW-09** (full suite): `mise run lint && mise run format-check && mise run check-types` exit 0.
10. **AC-NARROW-10** (full suite): `deviate inspect flows coverage` post-narrowing reports FLOW-04 with status derived from real ledger state (after `deviate flows sync` and `deviate merge` have run); the `flow_alignment` field is absent from any rendered JUDGE manifest.

## Risk and Migration

- **Backward compatibility:** `IssueRecord.flow_refs` field is preserved. Existing `flows.jsonl` rows are preserved (the two `FLOW_REFERENCED_BY_ISSUE` rows remain valid under the simplified taxonomy).
- **Migration:** None required for existing data. The drift-flag taxonomy is unchanged on the wire; only the event-type Literal union shrinks.
- **Coverage drift flag semantics:** Seven flags become six (no `PARTIALLY_IMPLEMENTED` states possible). `STALE_DRIFT` becomes effectively a synonym for "CONFIRMED_IMPLEMENTED but not yet shipped" — exactly its original intent.
- **PR templates:** Quick sweep needed; the `IssueRecord.flow_refs` field is unchanged so PR templates that consume it continue to work.

## Verification Commands

```bash
# Slice 1 verification
mise run test tests/unit/test_macro/test_explore.py -v -k atomic

# Slice 2 verification
mise run test tests/unit/test_cli/test_release.py -v

# Slice 3 verification
grep -rn "flow_alignment" src/deviate/prompts/ tests/ # should return nothing

# Slice 4 verification
grep -rn "Product Layer Anchors\|Flow References" src/deviate/prompts/ # should return nothing

# Slice 5 verification
grep -rn "FLOW_DEPRECATED\|FLOW_IMPLEMENTATION_EVIDENCE_ADDED" src/ tests/ # should return nothing

# Full suite
mise run test
mise run lint
mise run format-check
mise run check-types
```

## Documentation Updates

- `specs/DeviaTDD-api.md`: remove `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` from the event-type taxonomy section; document new `deviate release tag-included` subcommand.
- `specs/DeviaTDD-architecture.md`: add the new `release_app` Typer group to the CLI architecture diagram.
- `specs/constitution.md`: §2 Database entry for `flows.jsonl` reflects the retired event types; §9 Version History records this as a non-breaking ledger simplification.
- `CHANGELOG.md`: append a `[Unreleased]` bullet under `### Changed` documenting each slice.