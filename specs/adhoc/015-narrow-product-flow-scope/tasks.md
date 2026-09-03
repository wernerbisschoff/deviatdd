# Implementation Tasks: `ISS-ADH-015`

## Phase 1: Slice 1 — `explore_post` Commits the Flows Ledger

**Goal**: Restructure `deviate explore post` so the `_run_flow_ledger_cycle` write lands in the same commit as `explore.md`. Five-line fix to `src/deviate/cli/macro.py`.

### Tasks

- TSK-015-01: explore_post commits flows.jsonl atomically with explore.md
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/unit/test_macro/test_explore.py::test_explore_post_commits_flows_ledger_atomically -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/unit/test_macro/test_explore.py`
  - **Rationale**: AC-NARROW-01 requires that the flows ledger change commits in the same call as `explore.md`. Today the call sequence at `src/deviate/cli/macro.py:397-409` commits `explore_path` then runs `_run_flow_ledger_cycle`, leaving the ledger on the working tree. The fix swaps `commit_artifact(explore_path)` for `stage_and_commit([explore_path, flows_ledger_path], ...)` after moving the cycle call ahead of the commit.
  - **Details**:
    - **Red**: Write `test_explore_post_commits_flows_ledger_atomically` in `tests/unit/test_macro/test_explore.py`. Set up a tmp git repo with `README.md` and an initial commit. Write `specs/constitution.md`. Write a minimal `specs/explore/test-slug.md` with the seven required sections (Problem Definition, Discovery Audit Results, Constitution Quotes, Architectural Baselines, Ecosystem Research, File Registry, Status Summary). Write `specs/_product/flows/index.md` with one row `| FLOW-04 | … |`. Pre-populate `specs/issues.jsonl` with one issue row carrying `flow_refs=["FLOW-04"]`. Run `runner.invoke(cli, ["explore", "post", "--slug", "test-slug"])`. Assert exit code 0. Run `subprocess.run(["git", "status", "--porcelain"])` and assert empty stdout. Run `subprocess.run(["git", "log", "-1", "--name-only"])` and assert both `specs/explore/test-slug.md` and `specs/_product/flows.jsonl` appear in the file list.
    - **Green**: In `src/deviate/cli/macro.py`, move the `_run_flow_ledger_cycle(specs_root)` call from line 409 to before line 397. Replace `commit_artifact(explore_path, ...)` with `stage_and_commit(message=..., files=[explore_path, flows_ledger_path], repo=Path.cwd())`. The `flows_ledger_path` is `specs_root / "_product" / "flows.jsonl"`. The coverage report (`_render_flow_coverage_report`) still prints after the commit.
    - **Refactor**: Verify `commit_artifact` import becomes unused (or keep for other callers). Run `mise run lint` to catch any unused-import warnings.
    - **Edge Cases**: Empty `flows.jsonl` (no issues with `flow_refs`) — `_run_flow_ledger_cycle` returns early without creating the file; `stage_and_commit` handles the no-changes case by returning `None`. Pre-existing `flows.jsonl` with no changes — `stage_and_commit` returns `None`, the existing flow-idempotency of `_append_with_compound_key` ensures no duplicate rows are appended.
    - **Acceptance**: Test passes. `git status` clean post-call. `git log -1 --name-only` shows both files. Existing `test_explore_post_does_not_seed_flow_identity_or_documented_events` still passes.

---

## Phase 2: Slice 2 — Release CLI Marks `FLOW_INCLUDED_IN_RELEASE`

**Goal**: New `deviate release tag-included --release-md <path> --version <ver>` subcommand that parses `## Included Flows` from a release markdown and appends `FLOW_INCLUDED_IN_RELEASE` events to the ledger. Update `/deviate-release` slash command workflow.

### Tasks

- TSK-015-02: Create `deviate release tag-included` CLI subcommand
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/unit/test_cli/test_release.py -v`
  - **Estimated Time**: 90 minutes
  - **Files**:
    - `src/deviate/cli/release.py` (NEW)
    - `src/deviate/cli/__init__.py`
    - `src/deviate/prompts/commands/deviate-release.md`
    - `tests/unit/test_cli/test_release.py` (NEW)
    - `specs/DeviaTDD-api.md`
  - **Rationale**: AC-NARROW-02 and AC-NARROW-03 require a new producer for `FLOW_INCLUDED_IN_RELEASE`. Today no code writes this event type (`grep -rn "append_flow_event.*INCLUDED" src/` returns nothing). The slash command `/deviate-release` is the natural caller; it composes the release markdown and approves the final commit. Splitting the ledger write into a CLI subcommand (rather than embedding the markdown parsing in the slash prompt) keeps the parsing logic unit-testable.
  - **Details**:
    - **Red**: Write three tests in `tests/unit/test_cli/test_release.py`:
      - `test_release_tag_included_appends_event`: write `release-next.md` containing `## Included Flows\n\n| Flow ID | Name | Why in this release |\n|---|---|---|\n| FLOW-04 | Live-Stream | Primary |\n`. Invoke `runner.invoke(cli, ["release", "tag-included", "--release-md", "release-next.md", "--version", "1.0.0"])`. Assert exit 0. Read `specs/_product/flows.jsonl`; assert one new row with `event_type="FLOW_INCLUDED_IN_RELEASE"`, `flow_id="FLOW-04"`, `event_release_version="1.0.0"`, `event_issue_id=null`, `evidence_path=null`.
      - `test_release_tag_included_idempotent`: invoke the same command twice. Assert the ledger has exactly one row matching the compound key `(FLOW-04, FLOW_INCLUDED_IN_RELEASE, 1.0.0)`.
      - `test_release_tag_included_missing_table`: write `release-next.md` with no `## Included Flows` heading. Assert exit code 1 and `RELEASE_INCLUDED_FLOWS_MISSING` in stderr.
    - **Green**: Create `src/deviate/cli/release.py`. Define `release_app = typer.Typer(no_args_is_help=True, help="Release composition commands")`. Implement `@release_app.command("tag-included")` with parameters `release_md: Path = typer.Option(..., "--release-md", help="Path to release-next.md")` and `version: str = typer.Option(..., "--version", help="Release version, e.g. 1.0.0")`. Resolve `flows_ledger = Path("specs") / "_product" / "flows.jsonl"`. Read `release_md` text. Find lines starting with `| FLOW-` (after the `## Included Flows` heading if present). Extract the first column as the flow ID; validate against `^FLOW-\d{2,}$`. If zero rows found after the heading, emit `[red]RELEASE_INCLUDED_FLOWS_MISSING[/]` and `raise typer.Exit(code=1)`. For each flow ID, call `append_flow_event(FlowEvent(flow_id=flow_id, event_type="FLOW_INCLUDED_IN_RELEASE", event_release_version=version, timestamp=datetime.now(timezone.utc)), flows_ledger)`. Run `subprocess.run(["git", "add", str(flows_ledger)])` to stage. Emit `[green]RELEASE_TAGGED[/] <count> flow(s) for version <version>` banner.
    - **Refactor**: Extract the markdown table parsing into a pure helper `_parse_included_flows(release_md_path) -> list[str]` for testability. Use `re.match(r"^FLOW-\d{2,}$", flow_id)` for validation. Centralize the `flows_ledger_path` resolution (mirror `src/deviate/cli/flow_commands.py:35` pattern).
    - **Edge Cases**: `release-md` path does not exist — emit `[red]RELEASE_MD_NOT_FOUND[/]` and exit 1. Flow ID in the table fails the regex — emit `[yellow]INVALID_FLOW_REF_SKIPPED[/] <ref>` and continue (mirror `deviate merge` orphan policy). `flows.jsonl` does not yet exist — `append_flow_event` creates it via `_append_with_compound_key`'s `parent.mkdir(parents=True, exist_ok=True)`.
    - **Acceptance**: Three new tests pass. `deviate --help` lists the `release` group. `deviate release tag-included --help` shows the new command.

- TSK-015-03: Register `release_app` in the root CLI
  - **Type**: Config
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run deviate --help | grep release`
  - **Estimated Time**: 10 minutes
  - **Files**:
    - `src/deviate/cli/__init__.py`
  - **Rationale**: The new `release_app` Typer group must be wired into the root `cli` so it's reachable via `deviate release …`. Existing pattern: `cli.add_typer(flows_app, name="flows", help=…)`.
  - **Details**:
    - **Red**: Write `test_cli_help_lists_release_group` in `tests/unit/test_cli/test_help.py` — invoke `deviate --help`, assert `release` appears in the command list with the description from the Typer decorator.
    - **Green**: In `src/deviate/cli/__init__.py`, add `from deviate.cli.release import release_app`. Add `cli.add_typer(release_app, name="release", help="Release composition commands")` next to existing `add_typer` calls.
    - **Refactor**: Verify alphabetical or logical ordering of `add_typer` calls matches the project's convention.
    - **Acceptance**: Test passes. `deviate --help` shows `release` group.

- TSK-015-04: Update `/deviate-release` slash command workflow
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -n "tag-included" src/deviate/prompts/commands/deviate-release.md`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `src/deviate/prompts/commands/deviate-release.md`
  - **Rationale**: Operators running `/deviate-release` directly must be told to invoke `deviate release tag-included` after the release markdown is finalized. Today step 2.5 invokes `select_release_candidate_flows` for the Included Flows table; the new step 2.5b invokes the new CLI.
  - **Details**:
    - **Green**: In `src/deviate/prompts/commands/deviate-release.md`, insert a new step `## 2.5b. Tag Included Flows` between the current step 2.5 and step 3. The new step instructs the agent to invoke `uv run deviate release tag-included --release-md specs/_product/release-next.md --version <extracted from Version: field in release-next.md>`. Add the `[green]RELEASE_TAGGED[/]` and `[red]RELEASE_INCLUDED_FLOWS_MISSING[/]` banners to the workflow reference.
    - **Refactor**: Verify the workflow numbering remains sequential.
    - **Acceptance**: `grep "tag-included" deviate-release.md` returns one match.

- TSK-015-05: Document `deviate release tag-included` in `specs/DeviaTDD-api.md`
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -n "tag-included" specs/DeviaTDD-api.md`
  - **Estimated Time**: 10 minutes
  - **Files**:
    - `specs/DeviaTDD-api.md`
  - **Rationale**: API doc must describe the new subcommand per the spec-alignment mandate.
  - **Details**:
    - **Green**: Add a new subsection under the `deviate` CLI command list describing `deviate release tag-included`. Include: synopsis, parameter table (`--release-md`, `--version`), behavior summary, idempotency contract, banner reference (`RELEASE_TAGGED`, `RELEASE_INCLUDED_FLOWS_MISSING`, `INVALID_FLOW_REF_SKIPPED`).
    - **Acceptance**: Grep returns the section.

---

## Phase 3: Slice 5 — Retire Dead Event Types

**Goal**: Drop `FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` from the model Literal union. Drop `PARTIALLY_IMPLEMENTED` from `_derive_impl_status`. Drop `_implementation_evidence_paths`. Update consumers and tests.

### Tasks

- TSK-015-06: Remove retired event types from `FlowEvent.event_type` Literal union
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/unit/test_state/test_ledger.py -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/unit/test_state/test_ledger.py`
    - `tests/unit/test_cli/test_inspect.py`
    - `tests/unit/test_core/test_flow_confirmation.py`
  - **Rationale**: AC-NARROW-06 requires Pydantic rejection of retired event types. Three event types have zero producers in `src/`; keeping them in the union is misleading and risks future contributors wiring producers for dead types.
  - **Details**:
    - **Red**: Write `test_flow_event_rejects_retired_event_types` — assert `FlowEvent.model_validate({"flow_id": "FLOW-04", "event_type": "FLOW_DEPRECATED", "timestamp": "2026-01-01T00:00:00Z"})` raises `ValidationError`. Same for `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`.
    - **Green**: In `src/deviate/state/ledger.py:404-414`, remove `"FLOW_DEPRECATED"` and `"FLOW_IMPLEMENTATION_EVIDENCE_ADDED"` from the `event_type` Literal union.
    - **Refactor**: Verify `_LINKED_FLOW_EVENT_TYPES` at lines 378-385 is unchanged (it doesn't list the retired types).
    - **Edge Cases**: Existing JSONL rows in `flows.jsonl` carrying retired event types — `_iter_flow_ledger_rows` at lines 605-627 already handles Pydantic validation errors per-row, so malformed rows are skipped silently. This is acceptable; the rows simply don't contribute to coverage derivation.
    - **Acceptance**: New test passes. Existing tests for valid event types still pass.

- TSK-015-07: Simplify `_derive_impl_status` to two-valued Literal
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/unit/test_state/test_ledger.py::test_derive_impl_status -v`
  - **Estimated Time**: 20 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/unit/test_state/test_ledger.py`
  - **Rationale**: AC-NARROW-07 requires `_derive_impl_status` to return only `"CONFIRMED_IMPLEMENTED"` or `"UNCONFIRMED"`. The `PARTIALLY_IMPLEMENTED` branch is unreachable once the only producer (`FLOW_IMPLEMENTATION_EVIDENCE_ADDED`) is retired.
  - **Details**:
    - **Red**: Update existing `_derive_impl_status` tests to drop `PARTIALLY_IMPLEMENTED` assertions. Add `test_derive_impl_status_only_two_values` — assert the function returns one of `{"CONFIRMED_IMPLEMENTED", "UNCONFIRMED"}` for any input.
    - **Green**: In `src/deviate/state/ledger.py:630-639`, drop the `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` branch. Reduce the `FlowImplementationStatus` Literal at lines 459-461 to `["CONFIRMED_IMPLEMENTED", "UNCONFIRMED"]`. Update `_derive_drift_flag`'s `drift_by_state` dict at lines 658-667 to remove tuples referencing `PARTIALLY_IMPLEMENTED`. Verify the remaining tuples still cover all reachable `(discovered, documented, impl_status)` combinations.
    - **Refactor**: Verify `select_release_candidate_flows` at line 998 still filters correctly on `"CONFIRMED_IMPLEMENTED"`.
    - **Acceptance**: New tests pass. Coverage taxonomy remains exhaustive.

- TSK-015-08: Drop `_implementation_evidence_paths` helper
  - **Type**: Refactor
  - **Mode**: DIRECT
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `grep -n "_implementation_evidence_paths" src/`
  - **Estimated Time**: 10 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
  - **Rationale**: The helper collects `evidence_path` from retired event types. With no callers once the event types are gone, it is dead code.
  - **Details**:
    - **Green**: Remove `_implementation_evidence_paths` function (lines 721-727). Remove the `evidence_paths = _implementation_evidence_paths(events)` line in `load_flow_coverage` at line 763. The `evidence_paths: list[str] = Field(default_factory=list)` field on `FlowCoverage` (line 454) remains for forward-compatibility; default empty list.
    - **Acceptance**: `grep` returns nothing. Existing `FlowCoverage` consumers tolerate empty `evidence_paths`.

- TSK-015-09: Drop tests for retired event types
  - **Type**: Refactor
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -rn "FLOW_DEPRECATED\|FLOW_IMPLEMENTATION_EVIDENCE_ADDED\|PARTIALLY_IMPLEMENTED" tests/`
  - **Estimated Time**: 20 minutes
  - **Files**:
    - `tests/unit/test_cli/test_inspect.py`
    - `tests/unit/test_core/test_flow_confirmation.py`
  - **Rationale**: Existing tests reference the retired event types as fixture inputs. With the types rejected by Pydantic, these tests now fail. Clean removal is the right move.
  - **Details**:
    - **Green**: Drop `tests/unit/test_cli/test_inspect.py:812` and `:871` (test cases that write `FLOW_INCLUDED_IN_RELEASE` events — keep these, only drop the retired types). Drop `tests/unit/test_core/test_flow_confirmation.py:454` and `:490` (test cases for retired types).
    - **Acceptance**: `grep` returns nothing for retired types. Full test suite passes.

- TSK-015-10: Update `specs/constitution.md` and `specs/DeviaTDD-api.md`
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -n "FLOW_DEPRECATED\|FLOW_IMPLEMENTATION_EVIDENCE_ADDED" specs/`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `specs/constitution.md`
    - `specs/DeviaTDD-api.md`
  - **Rationale**: Constitutional and API docs must reflect the simplified taxonomy.
  - **Details**:
    - **Green**: In `specs/constitution.md:33`, replace the event-type enumeration with the five remaining types. Append a 0.8.0 entry to §9 Version History noting the retirement. In `specs/DeviaTDD-api.md`, drop the retired types from the event-type taxonomy section.
    - **Acceptance**: Grep returns nothing for retired types in specs.

---

## Phase 4: Slice 3 — Drop `Flow-Anchored Implementation` from Micro Layer

**Goal**: Remove the `Flow-Anchored Implementation` shared discipline from `micro-shared.md`. Remove `flow_alignment` from JUDGE handover manifest schema. Remove flow-anchored language from red/green/refactor prompts.

### Tasks

- TSK-015-11: Remove `Flow-Anchored Implementation` from `micro-shared.md`
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -n "Flow-Anchored" src/deviate/prompts/core/micro-shared.md`
  - **Estimated Time**: 10 minutes
  - **Files**:
    - `src/deviate/prompts/core/micro-shared.md`
  - **Rationale**: AC-NARROW-04 requires the third micro-layer invariant be removed. Today the file at `src/deviate/prompts/core/micro-shared.md:50-52` carries this invariant.
  - **Details**:
    - **Green**: Delete the entire `<item><title>Flow-Anchored Implementation</title>…</item>` block from `<shared_disciplines>`. The remaining items (Test-First, Sociable Tests, Verification-is-Done, Git Isolation, YAML Quoting Rule) are unchanged.
    - **Acceptance**: Grep returns nothing.

- TSK-015-12: Remove `flow_alignment` from JUDGE handover manifest schema
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -rn "flow_alignment" src/deviate/prompts/ tests/`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `src/deviate/prompts/auto/judge.md`
    - `src/deviate/prompts/commands/deviate-judge.md`
  - **Rationale**: AC-NARROW-04 requires `flow_alignment` removed from the manifest schema.
  - **Details**:
    - **Green**: In `src/deviate/prompts/auto/judge.md`, delete `flow_alignment` field declarations at lines 198 and 244. Update the edge-case table at line 271 to remove the empty-`Flow References` row. Delete any prose referencing `flow_alignment`. Apply the same deletions to `src/deviate/prompts/commands/deviate-judge.md:140,184,228`.
    - **Acceptance**: Grep returns nothing.

- TSK-015-13: Remove flow-anchored language from red/green/refactor prompts
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -rn "flow_refs\|Flow Reference" src/deviate/prompts/auto/`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `src/deviate/prompts/auto/red.md`
    - `src/deviate/prompts/auto/green.md`
    - `src/deviate/prompts/auto/refactor.md`
  - **Rationale**: The micro-shared deletion does not propagate to phase-specific prompts; each carries its own restate-flow-refs instructions.
  - **Details**:
    - **Green**: For each file, grep for `flow_refs`, `Flow Reference`, `flow-anchored`, `parent flow`, and delete matching blocks. Verify the resulting prompts still produce valid manifests.
    - **Acceptance**: Grep returns nothing for `flow_refs` in the auto/ prompts.

- TSK-015-14: Drop `flow_alignment` test assertions
  - **Type**: Refactor
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -rn "flow_alignment" tests/`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `tests/unit/test_micro/test_orchestration.py`
  - **Rationale**: Tests asserting on a retired field fail post-removal.
  - **Details**:
    - **Green**: Drop any test case asserting `flow_alignment` is present in a rendered manifest. If a test asserts `flow_alignment == "SKIP"` for empty `Flow References`, remove the assertion (the field no longer exists).
    - **Acceptance**: Grep returns nothing.

---

## Phase 5: Slice 4 — Drop `Flow Reference Propagation` from Meso Layer

**Goal**: Remove the `Flow Reference Propagation` shared discipline from `meso-shared.md`. Remove `## Product Layer Anchors` from plan templates. Remove `**Flow References**` from task templates.

### Tasks

- TSK-015-15: Remove `Flow Reference Propagation` from `meso-shared.md`
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -n "Flow Reference Propagation" src/deviate/prompts/core/meso-shared.md`
  - **Estimated Time**: 10 minutes
  - **Files**:
    - `src/deviate/prompts/core/meso-shared.md`
  - **Rationale**: AC-NARROW-05 requires meso-shared's `Flow Reference Propagation` invariant be removed.
  - **Details**:
    - **Green**: Delete the entire `<item><title>Flow Reference Propagation</title>…</item>` block from `<shared_disciplines>` at `src/deviate/prompts/core/meso-shared.md:37-39`.
    - **Acceptance**: Grep returns nothing.

- TSK-015-16: Remove `## Product Layer Anchors` from plan templates
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -rn "Product Layer Anchors" src/deviate/prompts/`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `src/deviate/prompts/auto/plan.md`
    - `src/deviate/prompts/commands/deviate-plan.md`
  - **Rationale**: AC-NARROW-05 requires the plan template to no longer carry the `Product Layer Anchors` section.
  - **Details**:
    - **Green**: Delete `## Product Layer Anchors` section, `**Flow References**` and `**Source**` (frontmatter field: flow_refs) lines. Delete the `flow_refs: []` line from the plan frontmatter schema. Update the edge-case table to drop the no-`flow_refs` row. Apply same deletions to the slash-command counterpart.
    - **Acceptance**: Grep returns nothing.

- TSK-015-17: Remove `**Flow References**` from task templates
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -rn "Flow References" src/deviate/prompts/`
  - **Estimated Time**: 15 minutes
  - **Files**:
    - `src/deviate/prompts/auto/tasks.md`
    - `src/deviate/prompts/commands/deviate-tasks.md`
  - **Rationale**: AC-NARROW-05 requires the task template to no longer carry per-task `** Flow References**`.
  - **Details**:
    - **Green**: Delete the `**Flow References**` field requirement from each task. Delete the `Flow Reference Propagation Rule` invariant. Update the closing `[E2E]` task gating to derive from `user-facing workflow` only (no `flow_refs` reference). Update the edge-case table to drop the propagation-gap row. Apply same deletions to the slash-command counterpart.
    - **Acceptance**: Grep returns nothing.

---

## Phase 6: Documentation and Final Verification

**Goal**: Update CHANGELOG. Run full verification.

### Tasks

- TSK-015-18: Append CHANGELOG bullet under `[Unreleased]`
  - **Type**: Docs
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: `grep -A 5 "## \[Unreleased\]" CHANGELOG.md | grep -i "narrow"`
  - **Estimated Time**: 10 minutes
  - **Files**:
    - `CHANGELOG.md`
  - **Rationale**: Constitution §5 DoD requires user-visible changes to carry a CHANGELOG bullet.
  - **Details**:
    - **Green**: Under `## [Unreleased]`, add a `### Changed` subsection with bullets:
      - **`explore post` now commits the flows ledger atomically with `explore.md`.** The previous behavior appended `FLOW_REFERENCED_BY_ISSUE` events to `specs/_product/flows.jsonl` after committing `explore.md`, leaving the ledger change orphaned on the working tree.
      - **`deviate release tag-included` is the new owner of `FLOW_INCLUDED_IN_RELEASE` events.** New subcommand parses `## Included Flows` from a release markdown and appends one event per flow ID. Idempotent on `(flow_id, event_type, event_release_version)`.
      - **`FLOW_DEPRECATED` and `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` event types retired.** No producers existed. `FlowImplementationStatus` simplified to `["CONFIRMED_IMPLEMENTED", "UNCONFIRMED"]`.
      - **Meso and micro prompts no longer propagate `flow_refs`.** Plan no longer carries `## Product Layer Anchors`. Tasks no longer carry `**Flow References**`. Micro JUDGE no longer carries a `flow_alignment` rubric dimension. Release composition is the only enforcement point.
    - **Acceptance**: Grep returns the bullets.

- TSK-015-19: Run full verification
  - **Type**: Verification
  - **Mode**: DIRECT
  - **Test Strategy**: Manual_Smoke
  - **Verification**: All five verification commands in the plan's Verification section return zero.
  - **Estimated Time**: 30 minutes
  - **Files**:
    - (no file changes)
  - **Rationale**: AC-NARROW-08, AC-NARROW-09, AC-NARROW-10 require the full suite, lint, format-check, and type-check all exit 0.
  - **Details**:
    - **Green**: Run `mise run test`. Run `mise run lint`. Run `mise run format-check`. Run `mise run check-types`. Run `grep -rn "flow_alignment\|FLOW_DEPRECATED\|FLOW_IMPLEMENTATION_EVIDENCE_ADDED\|Product Layer Anchors\|Flow Reference Propagation\|Flow References" src/ tests/ specs/` and confirm only `flow_refs` (issue field) and `IssueRecord.flow_refs` mentions remain.
    - **Acceptance**: All commands exit 0. Final grep returns only legitimate `flow_refs` references (issue field, adhoc CLI flag, _FLOW_REF_PATTERN).