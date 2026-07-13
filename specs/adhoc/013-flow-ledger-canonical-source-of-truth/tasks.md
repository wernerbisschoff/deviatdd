# Implementation Tasks: `feat/adhoc/013-flow-ledger-canonical-source-of-truth`

## Phase 1: Flow Ledger Substrate (Pydantic Models + Append Helpers)
**Goal**: Ship the append-only `specs/_product/flows.jsonl` substrate — `FlowRecord` / `FlowEvent` / `FlowCoverage` Pydantic models with the same `extra=forbid` discipline as `IssueRecord`, plus idempotent append helpers and the `load_flow_coverage` derivation that produces the seven drift flags enumerated in `specs/explore/flow-ledger.md:128-132`. This slice serves US-013-02 (the maintainer substrate story) and is the precondition for the Flow Coverage Report in Phase 2.

### Tasks

- TSK-013-01: Add `FlowRecord`, `FlowEvent`, `FlowCoverage` Pydantic models with `_FLOW_REF_PATTERN` validator
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_state/test_ledger.py::TestFlowRecord -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[FLOW-01, FLOW-02, FLOW-03]`
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: US-013-02 demands a Pydantic-enforced substrate with `model_config = {"extra": "forbid"}` and the canonical `^FLOW-\d{2,}$` regex (canonical source: `src/deviate/cli/adhoc.py:19`). The validator is duplicated as a module-level constant in `state/ledger.py` with an explicit comment block to avoid the circular import between `state.ledger` and `cli.adhoc` (both already use the regex independently). The three models are the substrate that AC-01, AC-02, and AC-07 hang off; this task satisfies story US-013-02 directly and serves FLOW-01 (canonical flow inventory) by providing the typed identity row.
  - **Details**:
    - **Red**: In `tests/test_state/test_ledger.py`, append `TestFlowRecord` class with `test_flow_record_validates_against_canonical_regex` (assert `FlowRecord(flow_id="FLOW-1")` and `FlowRecord(flow_id="flow-04")` both raise `ValidationError`; `FlowRecord(flow_id="FLOW-04")` succeeds and round-trips) and `test_flow_record_round_trip_byte_equal` (build `FlowRecord(flow_id="FLOW-04", name="Live-Stream Agent Progress via RPC", actor="Developer", domain="Agent Integration", source="specs/_product/flows/flows-streaming.md")`, parse `model_dump_json()` back, byte-equal). Append `TestFlowEvent` class with `test_flow_event_requires_reference_field_for_linked_events` (assert `FlowEvent(event_type="FLOW_REFERENCED_BY_ISSUE", event_issue_id=None, event_release_version=None, evidence_path=None)` raises `ValidationError`; same for `FLOW_INCLUDED_IN_RELEASE` and `FLOW_CONFIRMED_IMPLEMENTED` with all-None references; `FlowEvent(event_type="FLOW_DISCOVERED", timestamp=...)` with all-None references still succeeds).
    - **Green**: In `src/deviate/state/ledger.py`:
      1. Add module-level constant `_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")` immediately after the `import re` line (line 4), with a comment block stating canonical source is `src/deviate/cli/adhoc.py:19` and that duplication avoids the circular import.
      2. After `AdhocRecord` (line 343), add `class FlowRecord(BaseModel)` with fields `flow_id: str`, `name: str`, `actor: str`, `domain: str`, `source: str`, `status: Literal["Active", "Deprecated"] = "Active"`, `first_discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`, `model_config = {"extra": "forbid"}`. Apply `field_validator("flow_id")` reusing `_FLOW_REF_PATTERN`.
      3. Add `class FlowEvent(BaseModel)` with fields `flow_id: str`, `event_type: Literal["FLOW_DISCOVERED", "FLOW_DOCUMENTED", "FLOW_IMPLEMENTATION_EVIDENCE_ADDED", "FLOW_CONFIRMED_IMPLEMENTED", "FLOW_REFERENCED_BY_ISSUE", "FLOW_INCLUDED_IN_RELEASE", "FLOW_DEPRECATED"]`, `event_issue_id: str | None = None`, `event_release_version: str | None = None`, `evidence_path: str | None = None`, `timestamp: datetime`, `model_config = {"extra": "forbid"}`. Apply `field_validator("flow_id")` reusing `_FLOW_REF_PATTERN`. Apply `model_validator(mode="after")` that enforces: when `event_type` is one of `{"FLOW_REFERENCED_BY_ISSUE", "FLOW_INCLUDED_IN_RELEASE", "FLOW_IMPLEMENTATION_EVIDENCE_ADDED", "FLOW_CONFIRMED_IMPLEMENTED"}`, at least one of `event_issue_id` / `event_release_version` / `evidence_path` must be non-None.
      4. Add `class FlowCoverage(BaseModel)` with fields `flow_id: str`, `discovered_status: Literal["DISCOVERED", "UNDISCOVERED"]`, `doc_status: Literal["DOCUMENTED", "UNDOCUMENTED"]`, `impl_status: Literal["CONFIRMED_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "UNCONFIRMED"]`, `drift_flag: Literal["PROMPT_ONLY_NO_CODE", "DOC_ARTIFACT_ONLY", "DOCUMENTED_BUT_NOT_IMPLEMENTED", "IMPLEMENTED_BUT_UNDOCUMENTED", "ORPHANED_FLOW", "STALE_DRIFT", "OK"]`, `last_referenced_by_issue_id: str | None = None`, `last_referenced_by_release_version: str | None = None`, `evidence_paths: list[str] = Field(default_factory=list)`, `model_config = {"extra": "forbid"}`. Never persisted — derivation only.
    - **Refactor**: Move the `field_validator` for `flow_id` to a private helper `_validate_flow_id(value: str) -> str` shared by both `FlowRecord` and `FlowEvent` to keep the regex reference in one place per file.
    - **Edge Cases**: `FlowRecord(flow_id="FLOW-1")` rejected (single digit); `FlowRecord(flow_id="FLOW-001")` accepted (digits are not zero-padded-strict); `FlowRecord` with `status="Deprecated"` allowed; `FlowEvent` with `timestamp=datetime.now(timezone.utc)` and any other field None accepted for `FLOW_DISCOVERED` / `FLOW_DOCUMENTED` / `FLOW_DEPRECATED`.
    - **Acceptance**: Both new test classes pass; existing 18+ tests in `test_ledger.py` still pass; the three new Pydantic models export from `deviate.state.ledger` module-level (consistent with `IssueRecord` / `AdhocRecord`); `_FLOW_REF_PATTERN` is a single module-level constant, no inline re-compile.

- TSK-013-02: Add `append_flow_record`, `append_flow_event`, and `load_flow_coverage` derivation helpers
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_state/test_ledger.py::TestAppendFlowEvent tests/test_state/test_ledger.py::TestLoadFlowCoverage -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[FLOW-01, FLOW-02, FLOW-03]`
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `tests/test_state/test_ledger.py`
  - **Rationale**: US-013-02 and US-013-03 require idempotent append helpers that reuse the existing `_append_record` / `_append_with_compound_key` primitives, plus a `load_flow_coverage` derivation that replays events to compute the seven drift flags enumerated in `specs/explore/flow-ledger.md:128-132`. AC-04 demands compound-key idempotency on `(flow_id, event_type, event_issue_id, event_release_version, evidence_path)`; AC-02 demands the derivation flags `DOCUMENTED_BUT_NOT_IMPLEMENTED` correctly. This task serves FLOW-01 (flow inventory), FLOW-02 (architecture component drift signal), and FLOW-03 (release-goal enforceability) by emitting the canonical coverage view.
  - **Details**:
    - **Red**: In `tests/test_state/test_ledger.py`, append `TestAppendFlowEvent::test_append_flow_event_idempotent` (seed ledger with one `FlowEvent(flow_id="FLOW-04", event_type="FLOW_REFERENCED_BY_ISSUE", event_issue_id="ISS-ADH-012", timestamp=T0)`; call `append_flow_event(ledger_path, event)` again with same compound key; assert file size unchanged and `False` return on duplicate). Append `TestLoadFlowCoverage::test_load_flow_coverage_detects_documented_but_not_implemented` (build a temp `flows/index.md` with 4 flows (6-column markdown table: `| Flow ID | Name | Actor | Domain | Status | Source |`); build empty `flows.jsonl`; call `append_flow_record` for `FLOW-04` + `append_flow_event` for `FLOW_DISCOVERED` and `FLOW_DOCUMENTED`; call `load_flow_coverage(ledger_path, flows_index, issues_ledger)`; assert returned row for `FLOW-04` carries `drift_flag == "DOCUMENTED_BUT_NOT_IMPLEMENTED"`, `doc_status == "DOCUMENTED"`, `impl_status == "UNCONFIRMED"`).
    - **Green**: In `src/deviate/state/ledger.py`, after `_append_with_compound_key` (line 142):
      1. Add `def append_flow_record(record: FlowRecord, ledger_path: Path) -> bool:` that delegates to `_append_record` keyed on `flow_id` (mirrors `append_issue_record` at line 241).
      2. Add `def append_flow_event(event: FlowEvent, ledger_path: Path) -> bool:` that delegates to `_append_with_compound_key` keyed on `["flow_id", "event_type", "event_issue_id", "event_release_version", "evidence_path"]` (mirrors `append_issue_transition` at line 145).
      3. After `select_unblocked_candidates` (line 407), add `def load_flow_coverage(ledger_path: Path, flows_index: Path, issues_ledger: Path) -> list[FlowCoverage]`. The function:
         - Parses the 6-column markdown table in `flows_index` (rows split on `|`, stripped; columns in order: Flow ID, Name, Actor, Domain, Status, Source). Validates that Status ∈ `{"Active", "Deprecated"}`. Build a `dict[str, FlowRecord]` keyed on `flow_id`.
         - Reads `ledger_path` via `_read_ledger`; iterates rows; for each row, if it parses as `FlowRecord` add to the dict (canonical source overrides parse result on `flow_id` collision since `flows/index.md` is authoritative for identity); if it parses as `FlowEvent` append to a `dict[str, list[FlowEvent]]` keyed on `flow_id`.
         - For each flow in the canonical set, computes `discovered_status` (`"DISCOVERED"` iff any event has `event_type == "FLOW_DISCOVERED"`), `doc_status` (`"DOCUMENTED"` iff any event has `event_type == "FLOW_DOCUMENTED"`), `impl_status` (`"CONFIRMED_IMPLEMENTED"` iff any `FLOW_CONFIRMED_IMPLEMENTED`; else `"PARTIALLY_IMPLEMENTED"` iff any `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`; else `"UNCONFIRMED"`). Also tracks `last_referenced_by_issue_id` (latest `event_issue_id` from `FLOW_REFERENCED_BY_ISSUE`), `last_referenced_by_release_version` (latest `event_release_version` from `FLOW_INCLUDED_IN_RELEASE`), and `evidence_paths` (union of `evidence_path` from `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` and `FLOW_CONFIRMED_IMPLEMENTED`).
         - Computes `drift_flag` per the taxonomy: `("UNDISCOVERED", _, _)` → `PROMPT_ONLY_NO_CODE`; `("DISCOVERED", "UNDOCUMENTED", _)` → `DOC_ARTIFACT_ONLY`; `("DISCOVERED", "DOCUMENTED", "UNCONFIRMED")` → `DOCUMENTED_BUT_NOT_IMPLEMENTED`; `("DISCOVERED", "DOCUMENTED", "CONFIRMED_IMPLEMENTED")` with no `last_referenced_by_issue_id` → `IMPLEMENTED_BUT_UNDOCUMENTED`; flow in `ledger_path` but absent from `flows_index` → `ORPHANED_FLOW`; `_deprecated` status with no `FLOW_DEPRECATED` event → `STALE_DRIFT`; all checks pass → `OK`. Use a small private helper `_compute_drift_flag(flow_record, discovered, doc, impl, last_ref_issue, last_ref_release, has_deprecated_event) -> str` to keep the function readable.
         - Reads `issues_ledger` (best-effort — returns empty list if missing) and additionally populates `last_referenced_by_issue_id` from the latest `IssueRecord.flow_refs` mention whose `flow_refs` includes the target `flow_id` (i.e. forwards-pass reverse-index from issues ledger even when no `FLOW_REFERENCED_BY_ISSUE` event exists yet).
    - **Refactor**: Lift the drift-flag taxonomy into a `dict[tuple[str, str, str], str]` lookup table (the seven rows from `specs/explore/flow-ledger.md:128-132`) so the `_compute_drift_flag` helper is a single tuple-keyed lookup, not a chain of `if` branches.
    - **Edge Cases**: `ledger_path` missing → returns `FlowCoverage` rows for the canonical set with default `("UNDISCOVERED", "UNDOCUMENTED", "UNCONFIRMED")` state; `flows_index` missing → emits `FLOWS_INDEX_PARSE_FAILED` warning to `warnings.warn` and returns `[]`; `issues_ledger` missing → gracefully skipped; compound-key collision with different `timestamp` values → first-row-wins (the `_append_with_compound_key` helper's `False` return prevents the second write).
    - **Acceptance**: Both new test classes pass; existing 18+ tests still pass; `load_flow_coverage` returns a `list[FlowCoverage]` of length equal to the number of `FlowRecord` rows; `drift_flag` enumeration stays at exactly seven values (the `Literal[...]` Pydantic type makes additions a hard `ValidationError`).

---

## Phase 2: Explore-Post Seeding + Flow Coverage Report
**Goal**: Extend `deviate explore post` to (a) seed `specs/_product/flows.jsonl` from `specs/_product/flows/index.md` on first run, (b) reverse-index `FLOW_REFERENCED_BY_ISSUE` events from `specs/issues.jsonl::flow_refs`, and (c) render the six-column Flow Coverage Report via Rich with yellow-highlighted drift rows. This slice serves US-013-01 (operator story) and US-013-03 (release-goal enforceability) — the report is the only user-visible artifact in this issue.

### Tasks

- TSK-013-03: Add `_parse_flows_index`, `_seed_flow_ledger`, `_reverse_index_issue_flow_refs`, and `_render_flow_coverage_report` helpers in `cli/macro.py`
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_macro/test_explore.py::TestExploreCommand::test_explore_post_renders_flow_coverage_table tests/test_macro/test_explore.py::TestExploreCommand::test_explore_post_skips_orphaned_flow_refs -v`
  - **Estimated Time**: 60 minutes
  - **Flow References**: `[FLOW-01, FLOW-02, FLOW-03]`
  - **Files**:
    - `src/deviate/cli/macro.py`
    - `tests/test_macro/test_explore.py`
  - **Rationale**: US-013-01 demands a Flow Coverage Report inserted into `deviate explore post` output with columns `flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`; US-013-03 demands the report surface FLOW-04's `DOCUMENTED_BUT_NOT_IMPLEMENTED` drift (enforcing the v0.1.0 release-goal acceptance criterion at `specs/_product/release-next.md:58`). The four helpers in `macro.py` (a) parse the 6-column markdown at `flows/index.md`, (b) seed the JSONL via the helpers from TSK-013-02, (c) reverse-index from `specs/issues.jsonl::flow_refs`, and (d) render a Rich `Table` with yellow drift rows. The plan fixes the location in `macro.py` (not a separate `_product.py` module) to avoid module sprawl. This task serves FLOW-01 (canonical flow inventory surface) and FLOW-03 (release-goal drift signal) directly.
  - **Details**:
    - **Red**: In `tests/test_macro/test_explore.py`, append inside `TestExploreCommand`:
      1. `test_explore_post_renders_flow_coverage_table` — seed `tmp_path` with `.deviate/session.json` at phase `EXPLORE`, `specs/constitution.md`, `specs/explore/test-slug.md` (valid explore artifact), `specs/_product/flows/index.md` (4 flows in 6-column markdown table), and an empty `specs/_product/flows.jsonl`; invoke `runner.invoke(cli, ["explore", "post", "--slug", "test-slug"])`; assert exit code 0; assert stdout contains `FLOW-04`; assert stdout contains `DOCUMENTED_BUT_NOT_IMPLEMENTED`; assert `specs/_product/flows.jsonl` now exists with at least 4 `FlowRecord` rows.
      2. `test_explore_post_skips_orphaned_flow_refs` — seed the same workdir plus a `specs/issues.jsonl` row carrying `flow_refs: ["FLOW-99"]`; invoke `explore post`; assert exit code 0; assert stdout contains `ORPHANED_FLOW_REF` warning string; assert no `FlowRecord` is written for `FLOW-99` (only the 4 canonical flows are seeded).
    - **Green**: In `src/deviate/cli/macro.py`:
      1. Update the `from deviate.state.ledger import ...` line (line 45) to include `FlowRecord, FlowEvent, append_flow_record, append_flow_event, load_flow_coverage`.
      2. Add `from rich.table import Table` at the top imports.
      3. Add module-level constant `_FLOWS_INDEX_LEDGER_REL = "specs/_product/flows.jsonl"` and `_FLOWS_INDEX_MARKDOWN_REL = "specs/_product/flows/index.md"`.
      4. After `_explore_post` (line 886), add four helpers:
         - `def _parse_flows_index(path: Path) -> list[FlowRecord]`: reads the markdown file, validates the header row equals `| Flow ID | Name | Actor | Domain | Status | Source |` (6 columns, case-insensitive stripped), iterates body rows, splits on `|`, strips, validates `Status` ∈ `{"Active", "Deprecated"}`, returns `list[FlowRecord]`. On schema mismatch, emits `warnings.warn("FLOWS_INDEX_PARSE_FAILED ...")` and returns `[]`.
         - `def _seed_flow_ledger(ledger_path: Path, flows_index_path: Path) -> None`: parses the index, calls `append_flow_record` per missing flow, then for each flow appends `FLOW_DISCOVERED` + `FLOW_DOCUMENTED` events (both idempotent on compound key).
         - `def _reverse_index_issue_flow_refs(issues_ledger_path: Path, flows_ledger_path: Path, canonical_flow_ids: set[str]) -> None`: loads `issues_ledger_path` via `_read_ledger`; iterates each row that parses as `IssueRecord`; for each `flow_refs` token, if the token is in `canonical_flow_ids` appends a `FlowEvent(flow_id=token, event_type="FLOW_REFERENCED_BY_ISSUE", event_issue_id=record.issue_id, timestamp=record.created_at)`; else emits a `console.print(f"[yellow]ORPHANED_FLOW_REF[/] {token} (no FlowRecord for {token})")` warning (does NOT abort).
         - `def _render_flow_coverage_report(rows: list[FlowCoverage]) -> None`: builds a Rich `Table` titled `"Flow Coverage"` with six columns (`flow_id`, `Actor / Job / Trigger`, `Documented?`, `Implementation Evidence`, `Last Referenced By`, `Drift Flag`); for each row, sets `style="yellow"` when `drift_flag in {"DOCUMENTED_BUT_NOT_IMPLEMENTED", "IMPLEMENTED_BUT_UNDOCUMENTED", "ORPHANED_FLOW", "STALE_DRIFT"}`; prints via `console.print(table)`.
      5. Modify `explore_post` (line 240-282) to call the three helpers between `commit_artifact(...)` (line 272-276) and `_save_session(...)` (line 282):
         - `specs_root = _resolve_specs_root()` (already local).
         - `flows_index_path = specs_root / "_product" / "flows" / "index.md"`.
         - `flows_ledger_path = specs_root / "_product" / "flows.jsonl"`.
         - `if flows_index_path.exists():` block — call `_seed_flow_ledger(flows_ledger_path, flows_index_path)`; then load the seeded `FlowRecord` ids; then `_reverse_index_issue_flow_refs(specs_root / "issues.jsonl", flows_ledger_path, seeded_ids)`; then call `load_flow_coverage(flows_ledger_path, flows_index_path, specs_root / "issues.jsonl")` and pipe to `_render_flow_coverage_report(rows)`.
    - **Refactor**: Extract a small `_parse_index_header(line: str) -> list[str]` helper that strips `|`, splits, lowercases headers, validates the 6-column shape, returns the expected column names. The body row parser then only needs to look up `name` / `actor` / `domain` / `status` / `source` by index rather than re-parsing.
    - **Edge Cases**: `flows/index.md` missing → `console.print("[yellow]FLOWS_INDEX_MISSING[/] ...")` warning, skip seeding + report (do NOT halt `explore post`); `flows.jsonl` parent dir missing → `append_flow_record` creates it via `_append_record`'s `mkdir(parents=True, exist_ok=True)`; `issues.jsonl` missing → reverse-index skipped gracefully; `flow_refs` contains an empty string token → ignored silently.
    - **Acceptance**: Both new tests pass; existing 4 `test_explore.py` tests still pass; the report renders with six columns; `FLOW-04` row is highlighted yellow in the seeded scenario; orphaned `FLOW-99` reference logs a warning without aborting.

---

## Phase 3: Cross-Branch Merge Safety (`.gitattributes` Provisioning)
**Goal**: Provision `merge=union` for `specs/_product/flows.jsonl` in `DEVIATE_GITATTRIBUTES_SEED` (constitution v0.4.0 pattern) so concurrent feature branches appending to the new ledger never produce line-level conflicts. Mirrors the existing v0.4.0 rule for `specs/issues.jsonl` and `specs/**/tasks.jsonl`.

### Tasks

- TSK-013-04: Extend `DEVIATE_GITATTRIBUTES_SEED` with `specs/_product/flows.jsonl merge=union` + add the integration test
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test tests/test_cli/test_init.py -v -k flows_jsonl`
  - **Estimated Time**: 30 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `.gitattributes`
    - `tests/test_cli/test_init.py`
  - **Rationale**: US-013-04 demands `specs/_product/flows.jsonl merge=union` (parallel to the v0.4.0 rule for `specs/issues.jsonl`). This is enabling/infrastructure — the new rule is purely a config provisioner, no new behavior — so `**Flow References**: []` per the slice-over-step rule. The `DEVIATE_GITATTRIBUTES_SEED` constant (line 711-717) is the single source of truth — adding one line to the seed string auto-provisions downstream repos via `_ensure_root_gitattributes` (line 720). Mirroring the same line in the repo-root `.gitattributes` keeps the in-repo union rule consistent with what the helper provisions downstream (the plan explicitly calls out the double-write). The integration test is mandated by AC-05.
  - **Details**:
    - **Implementation**: Three edits:
      1. In `src/deviate/cli/__init__.py`, edit `DEVIATE_GITATTRIBUTES_SEED` (line 711-717) to add a third non-comment line `"specs/_product/flows.jsonl merge=union\n"` after the two existing entries. Update the comment header (lines 712-714) to mention the new ledger (e.g. add `flows.jsonl` to the list).
      2. In repo-root `.gitattributes`, append `specs/_product/flows.jsonl merge=union` after the two existing entries.
      3. In `tests/test_cli/test_init.py`, append a new test method `test_init_seeds_flows_jsonl_merge_union` inside the `TestSetup` class (the class housing the existing `test_init_writes_root_gitattributes_with_union_driver` at line 852). The test seeds an empty `tmp_path`, invokes `runner.invoke(cli, ["setup", "--agent", "opencode"])`, asserts exit code 0, reads the resulting `.gitattributes`, and asserts `specs/_product/flows.jsonl merge=union` is present.
    - **Refactor**: None — the existing `_ensure_root_gitattributes` (line 720) is already idempotent and uses `DEVIATE_GITATTRIBUTES_SEED.splitlines()` filtered to non-comment, non-empty lines, then appends only missing entries. No code change required in the provisioner itself.
    - **Edge Cases**: User-authored `.gitattributes` content (e.g. `# user content\n*.log binary\n`) is preserved by the existing `_ensure_root_gitattributes` logic (line 738-754). Re-running `deviate setup` is idempotent — line 887-901 already verifies this for the existing rules; the new test covers the flows.jsonl rule.
    - **Acceptance**: New `test_init_seeds_flows_jsonl_merge_union` passes; existing `test_init_writes_root_gitattributes_with_union_driver` / `test_init_root_gitattributes_idempotent_across_runs` / `test_init_root_gitattributes_union_driver_recognised_by_git` / `test_init_pre_writes_root_gitattributes` tests still pass (the new line is appended, not replacing existing entries); `DEVIATE_GITATTRIBUTES_SEED.splitlines()` contains exactly three non-comment non-empty lines after the change; repo-root `.gitattributes` file contains all three `merge=union` rules.

---

## Phase 4: Constitution Verification + CHANGELOG Discipline
**Goal**: Verify the constitution is at v0.7.0 (pre-staged by a prior commit on this branch — no edit required) and append a `CHANGELOG.md [Unreleased] → Added` bullet summarizing the new `specs/_product/flows.jsonl` ledger + drift-flag surface. This is the user-visible changelog surface that satisfies the AGENTS.md CHANGELOG Discipline cross-cutting rule and constitution §5 DoD item 7.

### Tasks

- TSK-013-05: Add `CHANGELOG.md [Unreleased] → Added` bullet and verify constitution v0.7.0
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run lint && mise run check`
  - **Estimated Time**: 30 minutes
  - **Flow References**: `[]`
  - **Files**:
    - `CHANGELOG.md`
    - `specs/constitution.md`
  - **Rationale**: AGENTS.md CHANGELOG Discipline cross-cutting rule (mirrored in `specs/constitution.md` §5 DoD item 7) mandates a `CHANGELOG.md [Unreleased]` update for any user-visible change — this issue ships (a) the new `specs/_product/flows.jsonl` file artifact, (b) the new `load_flow_coverage` derivation function, and (c) the new drift-flag surface in the `deviate explore post` Flow Coverage Report. Constitution verification is a no-op (the v0.7.0 bump was pre-staged in a prior commit on this branch — verified at `specs/constitution.md:3` and the §1 line 10 enumeration of `flows.jsonl`); the verification is included to prevent double-edits during GREEN. This is a docs/config change — no behavioral coupling to a specific flow — so `**Flow References**: []` per the slice-over-step rule.
  - **Details**:
    - **Implementation**:
      1. Verify `specs/constitution.md` is at v0.7.0 (line 3: `Version: 0.7.0`); line 10 enumerates `flows.jsonl` in §1 *Append-Only Ledger Protocol*; line 33 enumerates `specs/_product/flows.jsonl` in §2 *Database*; line 96 records the v0.7.0 version history. **No edit required** — re-read the file to confirm, abort the verification step if any of these is missing (signal of partial pre-stage), but do NOT modify.
      2. In `CHANGELOG.md`, add a new `### Added` subsection under the existing `## [Unreleased]` header (line 8), positioned before the existing `### Fixed` (line 9). Single bullet: `- \`**specs/_product/flows.jsonl*\` append-only ledger (identity \`FlowRecord\` + event \`FlowEvent\` rows) seeded by \`deviate explore post\` from \`specs/_product/flows/index.md\`; reverse-indexes \`FLOW_REFERENCED_BY_ISSUE\` events from \`specs/issues.jsonl::flow_refs\`; emits a Flow Coverage Report (six columns, drift rows in yellow) with the seven drift flags enumerated in \`specs/explore/flow-ledger.md:128-132\`. (\`src/deviate/state/ledger.py\`, \`src/deviate/cli/macro.py\`.)`.
    - **Refactor**: None — single-sentence bullet, no further structure.
    - **Edge Cases**: `CHANGELOG.md` already has `### Fixed` and `### Changed` under `[Unreleased]` (verified at lines 9 and 25) — the new `### Added` subsection is inserted between the `[Unreleased]` header and `### Fixed`. Follow Keep-a-Changelog ordering convention: `### Added`, `### Changed`, `### Fixed`, `### Removed` (the existing file orders `### Fixed` before `### Changed` — pre-existing deviation from canonical order, NOT corrected in this slice to avoid scope creep).
    - **Acceptance**: `CHANGELOG.md` contains the new bullet under `## [Unreleased]`; `specs/constitution.md` is verified at v0.7.0 with no edits; `mise run lint` and `mise run check` pass clean (no new ruff violations).

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-013-01 → TSK-013-02) — establish the substrate with Pydantic models + append helpers + derivation. Self-contained; verifies independently.
2. Phase 2 (TSK-013-03) — wire the substrate into `deviate explore post`. Depends on Phase 1 (imports the new models + helpers).
3. Phase 3 (TSK-013-04) — independent config change to `.gitattributes` + seed constant + integration test. Can be merged in parallel with Phase 1 / Phase 2 since it touches no shared code (only `DEVIATE_GITATTRIBUTES_SEED`).
4. Phase 4 (TSK-013-05) — last; no behavioral coupling, only docs/config. Run `mise run check` after all four phases are landed.

**Critical Dependency Chains**:
- TSK-013-01 must precede TSK-013-02 (the append helpers reference the Pydantic models).
- TSK-013-01 must precede TSK-013-03 (the macro.py integration imports the models).
- TSK-013-02 must precede TSK-013-03 (the macro.py integration calls the append helpers and `load_flow_coverage`).
- TSK-013-04 is independent (config only).
- TSK-013-05 is independent (docs only) but should run last for hygiene.

**Risk Hotspots**:
- Circular import between `state.ledger` and `cli.adhoc` (both already use the canonical `_FLOW_REF_PATTERN` independently). Mitigation: TSK-013-01 defines `_FLOW_REF_PATTERN` as a module-level constant in `state.ledger.py` with an explicit comment block referencing `src/deviate/cli/adhoc.py:19` as the canonical source. Defensive exclusion from the issue forbids modifying `adhoc.py:4,19`; keeping the regex in sync is achieved via the comment, not import.
- `deviate explore post` re-runs must remain idempotent. Mitigation: `append_flow_record` uses `_append_record` keyed on `flow_id`; `append_flow_event` uses `_append_with_compound_key` keyed on the five-tuple `(flow_id, event_type, event_issue_id, event_release_version, evidence_path)`. Both helpers return `False` on duplicate. Tested by `TestAppendFlowEvent::test_append_flow_event_idempotent` (TSK-013-02) and end-to-end by `test_explore_post_renders_flow_coverage_table` (TSK-013-03).
- Drift-flag taxonomy additions in future issues break JSONL re-parse. Mitigation: the `Literal[...]` for `drift_flag` enumerates exactly seven values this slice introduces. Pydantic `ValidationError` fires on a row carrying an unknown flag, which is a hard fail (per the edge-case note at issue line 139). New flags require a constitution bump — out of scope for this issue.
- `_parse_flows_index` schema breakage (column reorder, header rename). Mitigation: `_parse_index_header` helper validates the exact 6-column header shape and emits `FLOWS_INDEX_PARSE_FAILED` warning on mismatch; downstream seed step is skipped. Hard-fail is NOT used because the issue is "substrate ships", not "schema migration enforcement".
- Plan's "four canonical flows" count vs. advisory's "6 columns" shape — the count is 4 (FLOW-01..04) and the column count is 6 (Flow ID, Name, Actor, Domain, Status, Source). TSK-013-03 pins both via the `_parse_index_header` assertion.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: none directly (Phase 1 + Phase 2 both touch `src/deviate/state/ledger.py` only if `cli/macro.py` re-imports — they don't; the dependency flows one-way). The single `DEVIATE_GITATTRIBUTES_SEED` constant in `src/deviate/cli/__init__.py` is touched only by Phase 3.
- `tests/test_state/test_ledger.py` is touched only by Phase 1.
- `tests/test_macro/test_explore.py` is touched only by Phase 2.
- `tests/test_cli/test_init.py` is touched only by Phase 3.
- `CHANGELOG.md` and `specs/constitution.md` are touched only by Phase 4 (constitution is verify-only — no edit).

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[FLOW-01, FLOW-02, FLOW-03]`
- **Source**: `specs/adhoc/013-flow-ledger-canonical-source-of-truth/plan.md` (section `## Product Layer Anchors`)
- Downstream micro phases inherit this list per-task. Tasks with `**Flow References**: []` (TSK-013-04, TSK-013-05) are enabling/infrastructure and exempt from flow-anchored test requirements.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.

---

## Universal Flow-Reference Anchoring Rule (ALL TASKS WITH NON-EMPTY FLOW REFERENCES)

- Every task with non-empty `**Flow References**` MUST, in the **Rationale** field, cite which user-visible flow step the task serves (e.g. "serves FLOW-01 Step 3 — canonical flow inventory surface").
- Tests for these tasks MUST exercise behavior derivable from the parent flow's Trigger and Happy Path (per `specs/explore/flow-ledger.md:117-126`), not internal function signatures.
- A change that breaks or silently abandons a named flow MUST fail JUDGE with severity HIGH (per the Product-Layer Anchors invariant in `plan.md`).

## Universal Append-Only Ledger Discipline (ALL FLOW LEDGER TASKS)

- `FlowRecord` and `FlowEvent` are append-only — never mutate or delete an existing row from `specs/_product/flows.jsonl`. Re-running `deviate explore post` is idempotent (compound-key check returns `False` on duplicate, no second append).
- `FlowCoverage` is a derived view ONLY — never persisted. It is computed per-call from the JSONL + `flows/index.md` + `specs/issues.jsonl` per constitution §1 *Append-Only Ledger Protocol* (v0.7.0).
- The seven drift flags enumerated in `specs/explore/flow-ledger.md:128-132` are the complete vocabulary for this issue. New flags require a constitution bump and are out of scope.
