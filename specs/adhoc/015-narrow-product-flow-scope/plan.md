## Plan Summary

- **Issue**: ISS-ADH-015 — Narrow Product-Layer Flow Scope — Fix explore_post Ledger Commit, Add Release Flow Tagging, Retire Meso/Micro Ceremony
- **Implementation Strategy**: Five independent vertical slices, ordered by risk-of-regression. Slice 1 (commit-ordering fix) lands first because it changes ledger write semantics. Slice 2 (release CLI) is the second most impactful because it introduces a new producer that downstream `inspect flows candidates` already expects. Slices 3-5 are pure retirement: prompt surgery, model Literal union tightening, and dead-event-type removal. All five can ship in one epic but are independently revertable.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 6-8 hours total

## Workstation Mapping

- **src/deviate/cli/macro.py:366-410** (`explore_post`): MODIFY — restructure commit ordering so `_run_flow_ledger_cycle(specs_root)` runs *before* `stage_and_commit` and `flows_ledger_path` joins the artifact list.
  - **Current State**: Line 397 commits `explore_path` via `commit_artifact`. Line 409 then runs `_run_flow_ledger_cycle(specs_root)` which writes `FLOW_REFERENCED_BY_ISSUE` events to `specs/_product/flows.jsonl`. No second commit fires; the ledger change stays on the working tree.
  - **Changes Required**: Move `_run_flow_ledger_cycle(specs_root)` call to before the commit. Replace `commit_artifact(explore_path)` with `stage_and_commit(message=..., files=[explore_path, flows_ledger_path], repo=Path.cwd())`. The coverage report (`_render_flow_coverage_report`) prints after the commit (output ordering preserved).
  - **Integration Surface**: `commit_artifact` lives at `src/deviate/core/commit.py:101-110` and is a thin wrapper around `stage_and_commit([path])`. `stage_and_commit` itself at lines 26-86 handles the `git add` + `git commit` sequence; idempotent on no-changes. The flow-ledger path is constructed at `src/deviate/cli/macro.py:1179` as `specs_root / "_product" / "flows.jsonl"` — reuse that resolution.

- **src/deviate/cli/release.py** (NEW): CREATE — `release_app = typer.Typer(...)` Typer sub-app exposing `tag-included` command.
  - **Current State**: Does not exist. Release is slash-command only today (`/deviate-release` at `src/deviate/prompts/commands/deviate-release.md`).
  - **Changes Required**: Implement `tag_included(release_md: Path, version: str) -> None`. Read the markdown at `release_md`. Parse the `## Included Flows` table — rows starting with `| FLOW-`. For each flow ID, call `append_flow_event(FlowEvent(flow_id, event_type="FLOW_INCLUDED_IN_RELEASE", event_release_version=version), ledger_path)`. Stage the ledger via `subprocess.run(["git", "add", str(ledger_path)])`. Emit `[green]RELEASE_TAGGED[/] <count> flow(s)` banner. Exit non-zero with `[red]RELEASE_INCLUDED_FLOWS_MISSING[/]` if the table is absent or empty.
  - **Integration Surface**: `append_flow_event` at `src/deviate/state/ledger.py:497-510` is idempotent on `(flow_id, event_type, event_issue_id, event_release_version, evidence_path)`. The `_LINKED_FLOW_EVENT_TYPES` frozenset at lines 378-385 already includes `FLOW_INCLUDED_IN_RELEASE` and enforces a non-null reference — `event_release_version=version` satisfies the validator.

- **src/deviate/cli/__init__.py** (Typer registration): MODIFY — register `release_app` next to existing sub-apps (`flows_app`, `inspect_app`, `merge_app`, `adhoc_app`).
  - **Current State**: Existing groups registered at lines 760-880 in the `cli = typer.Typer(...)` body.
  - **Changes Required**: Add `from deviate.cli.release import release_app` import. Add `cli.add_typer(release_app, name="release", help="Release composition commands (tag flows as included, etc.)")` next to the existing `add_typer` calls.
  - **Integration Surface**: `cli` is the root Typer app. `deviate --help` will surface the new group.

- **src/deviate/state/ledger.py:404-413** (`FlowEvent.event_type`): MODIFY — remove `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` from the Literal union.
  - **Current State**: Seven-variant union declared at lines 405-414.
  - **Changes Required**: Reduce to five variants: `FLOW_DISCOVERED`, `FLOW_DOCUMENTED`, `FLOW_CONFIRMED_IMPLEMENTED`, `FLOW_REFERENCED_BY_ISSUE`, `FLOW_INCLUDED_IN_RELEASE`.
  - **Integration Surface**: All consumers (e.g. `_derive_impl_status` at line 630, `_last_release_reference` at line 709) reference specific variants explicitly; Pydantic validation rejects the retired variants on round-trip. `_LINKED_FLOW_EVENT_TYPES` at lines 378-385 needs no change.

- **src/deviate/state/ledger.py:630-639** (`_derive_impl_status`): MODIFY — remove `PARTIALLY_IMPLEMENTED` branch.
  - **Current State**: Function checks for `FLOW_CONFIRMED_IMPLEMENTED` first (returns `CONFIRMED_IMPLEMENTED`), then `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` (returns `PARTIALLY_IMPLEMENTED`), else `UNCONFIRMED`.
  - **Changes Required**: Drop the `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` branch. Reduce `FlowImplementationStatus` Literal at lines 459-461 to `["CONFIRMED_IMPLEMENTED", "UNCONFIRMED"]`. Update `_derive_drift_flag`'s `drift_by_state` dict at lines 658-667 to drop `(False, False, "PARTIALLY_IMPLEMENTED")`, `(True, False, "PARTIALLY_IMPLEMENTED")`, `(True, False, "CONFIRMED_IMPLEMENTED")` references — the only consumer state tuple left is `(discovered, documented, impl_status)` where `impl_status ∈ {"CONFIRMED_IMPLEMENTED", "UNCONFIRMED"}`.
  - **Integration Surface**: `select_release_candidate_flows` at line 998 already filters on `impl_status == "CONFIRMED_IMPLEMENTED"`; works unchanged. `load_flow_coverage` consumers receive a simpler Literal.

- **src/deviate/state/ledger.py:721-727** (`_implementation_evidence_paths`): REMOVE.
  - **Current State**: Helper collects `evidence_path` values from `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` events.
  - **Changes Required**: Delete the function. Update any callers — `load_flow_coverage` at line 763 calls it; remove the call and the `evidence_paths` field on `FlowCoverage` if no longer populated. (Decision: keep `evidence_paths: list[str] = Field(default_factory=list)` on `FlowCoverage` as an empty default for forward-compatibility; consumers tolerate empty list.)
  - **Integration Surface**: `FlowCoverage.evidence_paths` remains; default empty list.

- **src/deviate/prompts/core/micro-shared.md:50-52** (Flow-Anchored Implementation shared discipline): REMOVE.
  - **Current State**: Third bullet in `<shared_disciplines>`, alongside Test-First and Git Isolation. Mandates flow-anchored red/green/refactor, `flow_alignment` rubric in judge.
  - **Changes Required**: Delete the entire `<item><title>Flow-Anchored Implementation</title>…</item>` block. No replacement; the discipline is retired.
  - **Integration Surface**: This block is read by every micro phase prompt (red, green, judge, refactor, execute, yellow) via `assemble_prompt` at `src/deviate/prompts/assembly.py:80-99`. Removing it shrinks every micro-phase prompt's token cost.

- **src/deviate/prompts/core/meso-shared.md:37-39** (Flow Reference Propagation shared discipline): REMOVE.
  - **Current State**: Mandates that `flow_refs` flow from issue → plan → tasks verbatim.
  - **Changes Required**: Delete the entire `<item><title>Flow Reference Propagation</title>…</item>` block.
  - **Integration Surface**: Read by every meso phase prompt (plan, tasks) via the same `assemble_prompt` mechanism.

- **src/deviate/prompts/auto/judge.md:198,244,271** (`flow_alignment` field): REMOVE.
  - **Current State**: Manifest schema declares `flow_alignment: "PASS" | "FAIL" | "SKIP"` field. Edge-case table at line 271 has a row for empty `**Flow References**`.
  - **Changes Required**: Delete the `flow_alignment` field declaration from both manifest schemas (lines 198 and 244). Update the edge-case table to remove the empty-`Flow References` row. Update any prose that references `flow_alignment`.
  - **Integration Surface**: Judges that emit this field will be parsed by the orchestrator (`src/deviate/cli/micro.py`); field absence is tolerated by Pydantic if the manifest parser uses `extra="allow"`. Verify by `grep -n "flow_alignment" src/deviate/cli/`.

- **src/deviate/prompts/auto/red.md**, **green.md**, **refactor.md**: REMOVE flow-anchored language.
  - **Current State**: Each carries restate-flow-refs / write-flow-anchored-tests instructions (verify by grep first).
  - **Changes Required**: Delete any block matching `flow_refs` or `Flow Reference`.
  - **Integration Surface**: Same as micro-shared — read by `assemble_prompt`.

- **src/deviate/prompts/auto/plan.md:63-64,143,157**: REMOVE `## Product Layer Anchors` template.
  - **Current State**: Lines 63-64 declare `**Flow References**` and `**Source**` (source is `flow_refs` field) as required plan sections. Line 143 carries `flow_refs: []` in the plan frontmatter schema. Line 157 covers the "no flow_refs" edge case.
  - **Changes Required**: Delete the `## Product Layer Anchors` template. Update the edge-case table to drop the "no `flow_refs`" row.
  - **Integration Surface**: Plan output is parsed by `deviate tasks`; field absence tolerated.

- **src/deviate/prompts/auto/tasks.md:25,69,72,182,198**: REMOVE `**Flow References**` field on tasks.
  - **Current State**: Mandates per-task `**Flow References**` field. References drive the closing `[E2E]` task gating.
  - **Changes Required**: Delete the field requirement. The closing `[E2E]` task gating can derive from the issue's `flow_refs` directly (no propagation step) or from the `user-facing workflow` heuristic that already exists at line 80.
  - **Integration Surface**: Tasks parsed by `deviate micro`; field absence tolerated.

- **src/deviate/prompts/commands/deviate-plan.md:128-129**, **deviate-tasks.md:80,84**, **deviate-judge.md:140,184,228**: REMOVE matching flow sections.
  - **Current State**: Manual slash-command prompts mirror the auto/ versions.
  - **Changes Required**: Apply the same deletions as the auto/ counterparts.
  - **Integration Surface**: Loaded by `compose_command_body` (referenced in `src/deviate/prompts/assembly.py:66`); only matters when an operator invokes `/deviate-plan`, `/deviate-tasks`, `/deviate-judge` directly.

- **src/deviate/prompts/commands/deviate-release.md:120-140** (workflow step 2.5): UPDATE.
  - **Current State**: Step 2.5 invokes `select_release_candidate_flows` for the Included Flows table.
  - **Changes Required**: Insert new sub-step 2.5b that invokes `deviate release tag-included --release-md <path> --version <ver>` after the operator approves the release markdown. Update the workflow sequence to include this step.
  - **Integration Surface**: Loaded when operator runs `/deviate-release` directly.

- **specs/DeviaTDD-api.md**: UPDATE event-type taxonomy.
  - **Current State**: Documents all seven event types.
  - **Changes Required**: Reduce to five. Add a `deviate release tag-included` subsection under the `deviate` CLI command list.
  - **Integration Surface**: Reference doc only.

- **specs/constitution.md:33,98**: UPDATE §2 Database and §9 Version History.
  - **Current State**: §2 lists `flows.jsonl` and references all event types. §9 records 0.7.0 with the full taxonomy.
  - **Changes Required**: §2 update enumerates only the five retained event types. §9 appends a 0.8.0 entry: *"Retired `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` event types; no producers existed. `FlowImplementationStatus` simplified to `["CONFIRMED_IMPLEMENTED", "UNCONFIRMED"]`."*
  - **Integration Surface**: Constitutional doc only.

- **tests/test_macro/test_explore.py**: NEW test.
  - **Current State**: 322 lines; `test_explore_post_does_not_seed_flow_identity_or_documented_events` at line 285 is the closest existing test.
  - **Changes Required**: Add `test_explore_post_commits_flows_ledger_atomically` — set up git repo, write `explore.md` and `flows/index.md`, write a stub `issues.jsonl` with one row carrying `flow_refs=["FLOW-04"]`. Run `deviate explore post`. Assert `git status` exits 0 with empty output (working tree clean). Assert `git log -1 --name-only` includes both `specs/explore/test-slug.md` and `specs/_product/flows.jsonl`.

- **tests/test_cli/test_release.py**: NEW file.
  - **Current State**: Does not exist.
  - **Changes Required**: Three tests: (1) `test_release_tag_included_appends_event` — write a `release-next.md` with one `## Included Flows` row, invoke the command, parse `flows.jsonl`, assert one `FLOW_INCLUDED_IN_RELEASE` row. (2) `test_release_tag_included_idempotent` — invoke twice, assert no duplicate rows. (3) `test_release_tag_included_missing_table` — write a `release-next.md` without the table, assert exit code 1 and `RELEASE_INCLUDED_FLOWS_MISSING` stderr banner.

- **tests/test_state/test_ledger.py**: UPDATE existing tests.
  - **Current State**: Tests for `FlowEvent`, `FlowRecord`, `_derive_impl_status`.
  - **Changes Required**: Drop tests that assert `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` validity. Update `_derive_impl_status` tests to drop `PARTIALLY_IMPLEMENTED` assertions. Add a regression test: `test_flow_event_rejects_retired_event_types` — assert Pydantic `ValidationError` for both retired types.

- **tests/test_cli/test_inspect.py:812,871**, **tests/test_core/test_flow_confirmation.py:454,490**: DROP tests that reference retired event types.

- **tests/test_micro/test_orchestration.py**: DROP `flow_alignment` assertions (verify by grep first).

## Implementation Strategy

### Phase 1 — Slice 1 (commit ordering)

Five-line fix to `src/deviate/cli/macro.py`. Move `_run_flow_ledger_cycle` call to before the commit, switch to `stage_and_commit([explore_path, flows_ledger_path])`. Add one test asserting the working tree is clean. Verify with `mise run test tests/test_macro/test_explore.py -v -k atomic`.

### Phase 2 — Slice 2 (release CLI)

New `src/deviate/cli/release.py` with `tag-included` subcommand. Register in `src/deviate/cli/__init__.py`. Update `/deviate-release` workflow step 2.5b. Three new tests in `tests/test_cli/test_release.py`. Verify with `mise run test tests/test_cli/test_release.py -v`.

### Phase 3 — Slice 5 (retire dead event types)

Drop `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` from `FlowEvent.event_type`. Drop `PARTIALLY_IMPLEMENTED` branch from `_derive_impl_status`. Drop `_implementation_evidence_paths`. Update tests. Verify with `mise run test tests/test_state/test_ledger.py tests/test_cli/test_inspect.py tests/test_core/test_flow_confirmation.py -v`.

### Phase 4 — Slice 3 (micro ceremony)

Remove `Flow-Anchored Implementation` from `micro-shared.md`. Remove `flow_alignment` from `judge.md` (both auto and commands). Remove flow-anchored language from `red.md`, `green.md`, `refactor.md`. Drop test assertions. Verify with `mise run test tests/test_micro/ -v`.

### Phase 5 — Slice 4 (meso ceremony)

Remove `Flow Reference Propagation` from `meso-shared.md`. Remove `## Product Layer Anchors` from `plan.md`. Remove `**Flow References**` from `tasks.md`. Update slash-command counterparts. Verify with `mise run test tests/test_meso/ -v`.

### Phase 6 — Documentation + final verification

Update `specs/DeviaTDD-api.md`, `specs/constitution.md`, `CHANGELOG.md`. Run `mise run check` (lint + format + types + tests). Run `deviate inspect flows coverage` end-to-end to confirm the simplified taxonomy reports correctly.

## Risk

- **Backward compatibility:** `IssueRecord.flow_refs` field is preserved. The two existing `flows.jsonl` rows remain valid under the simplified taxonomy. `deviate inspect flows coverage` reports drift flags correctly because the five remaining event types still drive the same derivation.
- **Meso/micro prompt surgery:** Removing two `<shared_disciplines>` items and one manifest field is a non-trivial prompt change. Each prompt is loaded by `assemble_prompt` for every CLI-orchestrated phase. Operators running `/deviate-plan`, `/deviate-tasks`, `/deviate-judge` directly will see smaller prompts (less token cost per phase).
- **Existing tests:** ~7 test files reference retired event types or `flow_alignment`. All updates are mechanical (remove the assertion or the fixture row).
- **Slash-command drift:** `src/deviate/prompts/commands/deviate-flows.md` does NOT invoke `deviate flows sync` today — out of scope here, but flagged as a follow-up. The narrow-scope plan does not regress this behavior; it just doesn't fix it.
- **Release workflow change:** operators gain one extra step at release time (`deviate release tag-included`). The slash command `/deviate-release` step 2.5b documents this.

## Verification

- `mise run test` exits 0 with all five slices applied.
- `mise run lint && mise run format-check && mise run check-types` exit 0.
- `grep -rn "flow_alignment" src/deviate/prompts/ tests/` returns nothing.
- `grep -rn "FLOW_DEPRECATED\|FLOW_IMPLEMENTATION_EVIDENCE_ADDED" src/ tests/` returns nothing.
- `grep -rn "Product Layer Anchors\|Flow References" src/deviate/prompts/` returns nothing.
- End-to-end: `deviate flows sync → deviate explore post → deviate merge → deviate release tag-included` produces the expected `flows.jsonl` events (identity rows, referenced-by-issue, confirmed-implemented, included-in-release).