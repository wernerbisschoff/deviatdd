---
title: "Flow Ledger as Canonical Source of Truth — `specs/_product/flows.jsonl` + Flow Coverage Report in `explore.md`"
labels: [enhancement, adhoc, vertical-slice, product-layer, ledger]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-013
flow_refs: [FLOW-01, FLOW-02, FLOW-03]
---

## System Topology Mapping
- **Epic Target Domain**: `specs/_product/` (Product-layer staging directory; seed artifacts already present at `specs/_product/flows/`, `architecture.md`, `domain-model.md`, `release-next.md`).
- **Local Issue File**: `specs/adhoc/issues/013-flow-ledger-canonical-source-of-truth.md`
- **Primary Architectural Workstations**:
  - `src/deviate/state/ledger.py:10-15, 35, 114-142` — REFERENCE: append-only ledger protocol + Pydantic `model_config = {"extra": "forbid"}` enforcement and `_append_with_compound_key` compound-key idempotency. New Pydantic models `FlowRecord`, `FlowEvent`, `FlowCoverage` follow this pattern.
  - `src/deviate/cli/adhoc.py:19` — REFERENCE: canonical `_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")` flow-ID regex. Reused unchanged for `FlowRecord.flow_id` Pydantic validation.
  - `src/deviate/cli/macro.py:672-708` — `deviate shard post` constructs `IssueRecord(...)` with `flow_refs=issue_data.get("flow_refs", [])`. Reference for the forward-pointer pattern that the new ledger derives in reverse.
  - `src/deviate/cli/explore.py` — TARGET: extend `deviate explore post` to emit the Flow Coverage Report derived from `specs/_product/flows.jsonl` + `specs/_product/flows/index.md` + `specs/issues.jsonl`.
  - `src/deviate/cli/__init__.py:675` — REFERENCE: `_ensure_root_gitattributes` provisions `merge=union` for `specs/issues.jsonl` and `specs/**/tasks.jsonl` (constitution v0.4.0). Extend to seed `specs/_product/flows.jsonl merge=union`.
  - `src/deviate/core/validation.py:104-115` — REFERENCE: `validate_yaml_frontmatter` lenient validator; the Flow Coverage Report relies on the same lenient frontmatter parsing for `flow_refs:` ingestion.
  - `specs/_product/flows/index.md:5-8` — REFERENCE: canonical flow-ID inventory (`FLOW-01 Flows`, `FLOW-02 Architecture`, `FLOW-03 Release`, `FLOW-04 Live-Stream Agent Progress via RPC`). Source-of-truth for the `FlowRecord` seed.
  - `specs/constitution.md:10` — REFERENCE: "Append-Only Ledger Protocol" declaring `issues.jsonl` and `tasks.jsonl`. New `flows.jsonl` ledger extends this protocol.
  - `.gitattributes` — TARGET: add `specs/_product/flows.jsonl merge=union` rule (parallel to `specs/issues.jsonl merge=union`).
  - `specs/_product/flows.jsonl` — NEW: append-only JSONL ledger, one `FlowRecord` per flow plus an ordered stream of `FlowEvent` rows.
- **Upstream Evidence**:
  - `specs/explore/flow-ledger.md:5` — User-supplied problem statement declaring the request
  - `specs/explore/flow-ledger.md:128-132` — Drift-flag taxonomy (`PROMPT_ONLY_NO_CODE`, `DOC_ARTIFACT_ONLY`, `DOCUMENTED_BUT_NOT_IMPLEMENTED`, with future flags `IMPLEMENTED_BUT_UNDOCUMENTED`, `ORPHANED_FLOW`, `STALE_DRIFT`)
  - `specs/explore/flow-ledger.md:117-126` — Reference Flow Coverage Report table format (`flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`)
  - `specs/_product/release-next.md:58` — Release acceptance criterion: "Flow Coverage review dimension surfaces FLOW-04 with full coverage on the epic-tasks ledger entries (`flow_refs: [FLOW-04]`)"
  - `specs/_product/architecture.md:18-67` — Code-evidenced flows C2-C6 that the new ledger surfaces as `DOCUMENTED_BUT_NOT_IMPLEMENTED` drift

## The Problem Contract
The DeviaTDD Product layer currently records flow identity in `specs/_product/flows/index.md` as a static markdown table and forwards `flow_refs: [FLOW-XX, ...]` from `IssueRecord` / `AdhocRecord` rows in `specs/issues.jsonl` (the source file is at `src/deviate/state/ledger.py:35`). There is no separate, append-only ledger that records *how* each flow was discovered, documented, referenced by issues, included in releases, or evidenced by implementation. The release-goal acceptance criterion at `specs/_product/release-next.md:58` ("Flow Coverage review dimension surfaces FLOW-04 with full coverage on the epic-tasks ledger entries") is currently unenforceable at scan time — it depends on a reviewer manually cross-referencing `flows/index.md` against `specs/issues.jsonl` at PR-review. This issue delivers (a) the event-sourced `flows.jsonl` ledger as a canonical substrate, (b) the Flow Coverage Report rendered inside `explore.md` so the reconciliation pass surfaces drift before shard/architecture/release consume stale state, and (c) the constitutional and `.gitattributes` plumbing so concurrent branches merge append-only rows without conflict markers.

## Scope Boundaries

### Hard Inclusions
- Add three new Pydantic models to `src/deviate/state/ledger.py`:
  - `FlowRecord(BaseModel)` — identity row: `flow_id: str` (validated against `r"^FLOW-\d{2,}$"` matching `_FLOW_REF_PATTERN` at `src/deviate/cli/adhoc.py:19`), `name: str`, `actor: str`, `domain: str`, `source: str` (path to the canonical `flows-<domain>.md`), `status: Literal["Active", "Deprecated"] = "Active"`, `first_discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))`, `model_config = {"extra": "forbid"}`.
  - `FlowEvent(BaseModel)` — append-only event row: `flow_id: str` (validates against the same regex), `event_type: Literal["FLOW_DISCOVERED", "FLOW_DOCUMENTED", "FLOW_IMPLEMENTATION_EVIDENCE_ADDED", "FLOW_CONFIRMED_IMPLEMENTED", "FLOW_REFERENCED_BY_ISSUE", "FLOW_INCLUDED_IN_RELEASE", "FLOW_DEPRECATED"]`, `event_issue_id: str | None = None`, `event_release_version: str | None = None`, `evidence_path: str | None = None`, `timestamp: datetime`, `model_config = {"extra": "forbid"}`. Compound-key idempotency: `(flow_id, event_type, event_issue_id, event_release_version, evidence_path)` matches `_append_with_compound_key` at `src/deviate/state/ledger.py:114-142`.
  - `FlowCoverage(BaseModel)` — derived view: `flow_id: str`, `discovered_status: Literal["DISCOVERED", "UNDISCOVERED"]`, `doc_status: Literal["DOCUMENTED", "UNDOCUMENTED"]`, `impl_status: Literal["CONFIRMED_IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "UNCONFIRMED"]`, `drift_flag: Literal["PROMPT_ONLY_NO_CODE", "DOC_ARTIFACT_ONLY", "DOCUMENTED_BUT_NOT_IMPLEMENTED", "IMPLEMENTED_BUT_UNDOCUMENTED", "ORPHANED_FLOW", "STALE_DRIFT", "OK"]`, `last_referenced_by_issue_id: str | None = None`, `last_referenced_by_release_version: str | None = None`, `evidence_paths: list[str] = Field(default_factory=list)`. Derived only — never persisted.
- Add `append_flow_record(ledger_path: Path, record: FlowRecord)` and `append_flow_event(ledger_path: Path, event: FlowEvent)` helpers in `src/deviate/state/ledger.py` modelled on the existing `_append_with_compound_key` pattern. Add `load_flow_coverage(ledger_path: Path, flows_index: Path, issues_ledger: Path) -> list[FlowCoverage]` derivation function.
- Seed `specs/_product/flows.jsonl` as an empty JSONL file at issue-acceptance time (no rows pre-written). Seed paths: append `FlowRecord` rows for `FLOW-01..04` from `specs/_product/flows/index.md:5-8` only when `deviate explore post` runs and the ledger is empty.
- Extend `src/deviate/cli/explore.py` so `deviate explore post` (a) parses `specs/_product/flows/index.md`, (b) loads any existing `specs/_product/flows.jsonl`, (c) appends any missing `FLOW_DISCOVERED` / `FLOW_DOCUMENTED` events with compound-key idempotency, (d) re-derives `FlowCoverage` for every flow, and (e) renders a Rich-formatted table to stdout with the six report columns (`flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`). Rows where `drift_flag in {"DOCUMENTED_BUT_NOT_IMPLEMENTED", "IMPLEMENTED_BUT_UNDOCUMENTED", "ORPHANED_FLOW", "STALE_DRIFT"}` are highlighted in yellow.
- Add `merge=union` for `specs/_product/flows.jsonl` in `.gitattributes`. Extend `_ensure_root_gitattributes` at `src/deviate/cli/__init__.py:675` to seed the new rule alongside the existing `specs/issues.jsonl merge=union` and `specs/**/tasks.jsonl merge=union` lines (constitution v0.4.0).
- **Constitution bump to v0.7.0 in this same commit** (`specs/constitution.md` §1 *Append-Only Ledger Protocol* + v0.7.0 version history). The new `flows.jsonl` ledger extends the append-only protocol; the constitution is currently silent on it (`specs/explore/flow-ledger.md:61`). Required edits: (a) add `flows.jsonl` to the §1 enumeration alongside `issues.jsonl` / `tasks.jsonl`, (b) add v0.7.0 entry to the version history describing the substrate addition. Source: `specs/explore/flow-ledger.md:143` ("(a) `specs/constitution.md` v0.7.0 to enumerate `flows.jsonl` alongside `issues.jsonl` / `tasks.jsonl`"). Do NOT punt the bump to a research track — the slice ships the constitution change as part of "ledger added".
- **CHANGELOG.md `[Unreleased] → Added` bullet in this same commit** declaring the new `flows.jsonl` ledger and the `deviate explore post` Flow Coverage Report as user-visible artifacts. AGENTS.md §CHANGELOG Discipline (mirrored in `specs/constitution.md` §5 DoD) flags this as mandatory for new command behavior and new file artifacts. Bullet body must summarize (a) the new file (`specs/_product/flows.jsonl` append-only ledger), (b) the new derivation (`load_flow_coverage` + reverse indexing from `specs/issues.jsonl`), and (c) the new drift flag surface in the Flow Coverage Report.
- Extend `tests/state/test_ledger.py` with three new tests:
  - `test_flow_record_validates_against_canonical_regex` — `FlowRecord(flow_id="FLOW-1")` raises `ValidationError`; `FlowRecord(flow_id="FLOW-04")` succeeds. Mirrors the existing regex test pattern at `src/deviate/cli/adhoc.py:19`.
  - `test_append_flow_event_idempotent` — append `FlowEvent(flow_id="FLOW-04", event_type="FLOW_REFERENCED_BY_ISSUE", event_issue_id="ISS-ADH-012")` twice with the same `timestamp`; only one row is persisted. Mirrors `_append_with_compound_key` test.
  - `test_load_flow_coverage_detects_documented_but_not_implemented` — seed ledger with `FLOW_DISCOVERED` + `FLOW_DOCUMENTED` for `FLOW-04` (no `FLOW_CONFIRMED_IMPLEMENTED`); assert `FlowCoverage.drift_flag == "DOCUMENTED_BUT_NOT_IMPLEMENTED"`.
- Extend `tests/cli/test_explore.py` with one new test:
  - `test_explore_post_renders_flow_coverage_table` — against a temp workdir with `flows/index.md` (4 flows) and `flows.jsonl` (seeded with discovery events); invoke `deviate explore post`; assert stdout contains `FLOW-04` and the substring `DOCUMENTED_BUT_NOT_IMPLEMENTED`.
- The new code MUST reuse `_FLOW_REF_PATTERN = re.compile(r"^FLOW-\d{2,}$")` at `src/deviate/cli/adhoc.py:19` (no new regex introduced) — call out the source path in a comment block.
- Round-trip serialization test: parse `specs/_product/flows.jsonl` with `model_validate_json`, re-emit, byte-equal (parallel to `IssueRecord` round-trip).

### Defensive Exclusions
- Do NOT modify `IssueRecord`, `AdhocRecord`, `TaskRecord`, or `RollbackSnapshot` Pydantic models. The forward-pointer (`flow_refs: list[str]`) at `src/deviate/state/ledger.py:35` is sufficient — the new ledger derives the reverse direction from it. Only NEW Pydantic models (`FlowRecord`, `FlowEvent`, `FlowCoverage`) are added in this issue.
- Do NOT add CLI commands (`deviate flow post`, `deviate flow coverage`, etc.) — the drift-flag taxonomy, event-type vocabulary, and CLI command shape are owned by `/deviate-research` per the explore exclusions at `specs/explore/flow-ledger.md:19`. This issue is the substrate + report only.
- Do NOT modify `_FLOW_REF_PATTERN`, `_FLOW_REF_FORMAT_HINT`, or `_parse_flow_refs` at `src/deviate/cli/adhoc.py:4, 19`. The canonical regex and helper are reused unchanged.
- Do NOT modify `validate_yaml_frontmatter` at `src/deviate/core/validation.py:104-115`. The lenient validator (`accepts any well-formed YAML block; does not enumerate known/unknown keys`) is correct as-is — `flow_refs:` is already accepted.
- Do NOT introduce drift-flag values outside the seven enumerated (`PROMPT_ONLY_NO_CODE`, `DOC_ARTIFACT_ONLY`, `DOCUMENTED_BUT_NOT_IMPLEMENTED`, `IMPLEMENTED_BUT_UNDOCUMENTED`, `ORPHANED_FLOW`, `STALE_DRIFT`, `OK`). New flags would require a constitution bump and are out of scope.
- **Research-track deferrals (verbatim from `specs/explore/flow-ledger.md:19` `[Exclusions]`)**: the following are intentionally OUT of this slice and are owned by the `deviate-research` skill. This issue implements the substrate; architectural decisions, design trade-offs, risk analysis, and lifecycle integration proposals are deferred. Specifically: (a) architectural decisions and design trade-offs for the ledger, (b) risk analysis, (c) ledger schema proposals beyond the `FlowRecord` / `FlowEvent` / `FlowCoverage` models enumerated here, (d) extended event-type vocabulary beyond the seven enumerated (`FLOW_DISCOVERED`, `FLOW_DOCUMENTED`, `FLOW_IMPLEMENTATION_EVIDENCE_ADDED`, `FLOW_CONFIRMED_IMPLEMENTED`, `FLOW_REFERENCED_BY_ISSUE`, `FLOW_INCLUDED_IN_RELEASE`, `FLOW_DEPRECATED`), (e) extended derivation rules for `discovered_status` / `doc_status` / `impl_status` beyond the rules anchoring AC-ADHOC-013-02 / AC-ADHOC-013-04 / AC-ADHOC-013-05, (f) extended drift-flag semantics beyond the seven enumerated, (g) lifecycle integration of `deviate-flow` as a CLI command versus a skill, (h) failure-mode speculation. The ACs that pin specific values (drift_flag taxonomy, derivation rules, event types) define the FLOOR for this slice; extending the vocabulary requires a follow-up research track.
- Do NOT upgrade `src/deviate/prompts/commands/deviate-{flows,architecture,release}.md` skill bodies in this issue. Emitting `FLOW_DISCOVERED` / `FLOW_DOCUMENTED` events from skills is a follow-up concern owned by the meso/micro layer; this issue implements the substrate (writes can be invoked programmatically, not via skill bodies).
- Do NOT regenerate `specs/_product/flows/index.md`, `flows-product.md`, `flows-streaming.md`, `architecture.md`, `domain-model.md`, or `release-next.md`. These are user-authored seed artifacts — the new ledger derives from them as inputs.
- Do NOT add Graphite integration or `[models]` config changes. Default model routing applies.
- Do NOT add tests that invoke `_run_pytest` from inside `runner.invoke(...)` without mocking `deviate.cli.micro._run_pytest` — AGENTS.md test-performance mandate.
- Do NOT add `prompt` or LLM-backed flow-discovering logic in this issue. The Flow Coverage Report derivation is deterministic (string parsing + ledger replay), not LLM-driven.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-013`
- **Acceptance Criteria Tokens**: `AC-ADHOC-013-01` through `AC-ADHOC-013-07`
- **Data Model Entities**:
  - `FlowRecord` — identity row (Pydantic, `extra=forbid`)
  - `FlowEvent` — append-only event row (Pydantic, `extra=forbid`)
  - `FlowCoverage` — derived view (Pydantic, never persisted)
- **Spec Source Anchors**:
  - `specs/explore/flow-ledger.md:5` — User-supplied problem statement
  - `specs/explore/flow-ledger.md:128-132` — Drift-flag taxonomy
  - `specs/_product/release-next.md:58` — Release acceptance criterion (`Flow Coverage review dimension surfaces FLOW-04 with full coverage`)
  - `specs/_product/flows/index.md:5-8` — Canonical flow-ID inventory
  - `src/deviate/state/ledger.py:35` — Forward-pointer precedent (`flow_refs: list[str]`)
  - `src/deviate/cli/adhoc.py:19` — `_FLOW_REF_PATTERN` canonical regex (reused)
  - `specs/constitution.md:10` — Append-Only Ledger Protocol declaration

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **US-013-01**: As a DeviaTDD operator running `deviate explore` against a fresh or existing repo, I want a Flow Coverage Report inserted into `explore.md` (table columns: `flow_id | actor/job/trigger | documented? | implementation evidence? | last referenced by issue/release? | drift flag`) so I can spot documented-but-unbuilt, built-but-undocumented, and orphaned flows before shard/architecture/release consume stale state. *(Ref: FR-ADHOC-013)*
- **US-013-02**: As a DeviaTDD maintainer, I want a `specs/_product/flows.jsonl` append-only ledger (parallel to `specs/issues.jsonl`) with `FlowRecord` + `FlowEvent` Pydantic models enforcing `model_config = {"extra": "forbid"}` and `^FLOW-\d{2,}$` regex validation, so that flow identity, documentation events, and implementation-evidence events are event-sourced and replayable by any tool with read access to the JSONL file. *(Ref: FR-ADHOC-013)*
- **US-013-03**: As a Release Manager verifying the FLOW-04 release-goal acceptance criterion at `specs/_product/release-next.md:58` ("Flow Coverage review dimension surfaces FLOW-04 with full coverage on the epic-tasks ledger entries (`flow_refs: [FLOW-04]`)"), I want `flow_refs: [FLOW-04]` on epic tasks to map to a `flows.jsonl` identity row carrying `FLOW_CONFIRMED_IMPLEMENTED` evidence so the criterion is enforceable at scan time rather than only at PR-review. *(Ref: FR-ADHOC-013)*
- **US-013-04**: As a concurrent contributor working on a feature branch that emits new flow events, I want `specs/_product/flows.jsonl merge=union` in `.gitattributes` (parallel to the constitution v0.4.0 rule for `specs/issues.jsonl`) so cross-branch merges of append-only rows proceed without conflict markers. *(Ref: FR-ADHOC-013)*

## ATDD Acceptance Criteria

**Scenario 01**: Seed flow records from canonical index
**Given** `specs/_product/flows/index.md` lists `FLOW-01..04` with `Active` status and `specs/_product/flows.jsonl` does not exist
**When** `deviate explore post` runs against the empty workdir
**Then** the new `specs/_product/flows.jsonl` file contains exactly four `FlowRecord` rows (one per `FLOW-01..04`) and a `FLOW_DISCOVERED` + `FLOW_DOCUMENTED` event per flow

**Scenario 02**: Coverage derivation flags FLOW-04 as documented-but-not-implemented
**Given** `specs/_product/flows.jsonl` contains `FlowRecord(flow_id="FLOW-04")` plus `FLOW_DISCOVERED` and `FLOW_DOCUMENTED` events but no `FLOW_CONFIRMED_IMPLEMENTED` event
**When** `load_flow_coverage(ledger_path, flows_index, issues_ledger)` runs
**Then** the returned `FlowCoverage` row for `FLOW-04` carries `doc_status == "DOCUMENTED"`, `impl_status == "UNCONFIRMED"`, and `drift_flag == "DOCUMENTED_BUT_NOT_IMPLEMENTED"`

**Scenario 03**: Reverse indexing from `specs/issues.jsonl` populates `FLOW_REFERENCED_BY_ISSUE`
**Given** `specs/issues.jsonl` carries the existing rows including `ISS-ADH-012` with `flow_refs: ["FLOW-04"]`
**When** `deviate explore post` runs the derivation step
**Then** `specs/_product/flows.jsonl` contains one `FLOW_REFERENCED_BY_ISSUE` event per `flow_refs` mention with `event_issue_id` matching the source issue ID and the timestamp equals the source issue's `created_at`

**Scenario 04**: Compound-key idempotency prevents duplicate events on replay
**Given** `specs/_product/flows.jsonl` already contains `FlowEvent(flow_id="FLOW-04", event_type="FLOW_REFERENCED_BY_ISSUE", event_issue_id="ISS-ADH-012", timestamp=T0)`
**When** the derivation is replayed with identical inputs (`replay == False`)
**Then** zero new rows are appended (compound-key uniqueness enforces idempotency)

**Scenario 05**: Concurrent merge of append-only rows succeeds without conflict
**Given** `.gitattributes` declares `specs/_product/flows.jsonl merge=union` and two feature branches each append a new `FlowEvent` row for `FLOW-04`
**When** the branches merge
**Then** the resulting `specs/_product/flows.jsonl` contains rows from both branches (union merge) with no conflict markers

**Scenario 06**: Frontmatter parser accepts `flow_refs:` without warning
**Given** `validate_yaml_frontmatter` at `src/deviate/core/validation.py:104-115` accepts any well-formed YAML block
**When** an issue frontmatter declares `flow_refs: [FLOW-04]` and is posted via `deviate shard post`
**Then** no `[yellow]SHARD_WARNING[/] invalid YAML frontmatter` is emitted at `src/deviate/cli/macro.py:659-661` and the row's `flow_refs` field is preserved through JSONL round-trip

**Scenario 07**: Report highlights drift rows in yellow
**Given** `derive_flow_coverage(...)` returns four rows including one with `drift_flag == "DOCUMENTED_BUT_NOT_IMPLEMENTED"`
**When** `deviate explore post` renders the Flow Coverage Report
**Then** stdout contains a Rich-formatted table with six columns and the `DOCUMENTED_BUT_NOT_IMPLEMENTED` row is rendered with yellow styling

## Edge Cases and Boundaries

- **Empty `flows.jsonl`**: When `specs/_product/flows.jsonl` does not exist or is empty, `deviate explore post` must seed `FlowRecord` rows from `specs/_product/flows/index.md` rather than failing. Tested by `test_explore_post_renders_flow_coverage_table` (empty starting state).
- **Flow present in `flows.jsonl` but absent from `index.md`**: `FlowCoverage.drift_flag == "ORPHANED_FLOW"` (matched on flow_id). The drift flag is emitted but the row is NOT removed from `flows.jsonl` (append-only invariant).
- **Flow removed from `index.md` but present in `flows.jsonl`**: Same as above — `ORPHANED_FLOW`. Removal requires a `FLOW_DEPRECATED` event.
- **`flow_refs` references unknown flow ID**: When `IssueRecord.flow_refs == ["FLOW-99"]` and no `FlowRecord` exists for `FLOW-99`, the Flow Coverage Report logs a warning ("orphaned flow_refs reference") and skips the event-append step. The issue row's `flow_refs` is preserved unchanged.
- **Compound-key collision with different timestamps**: Two events with the same `(flow_id, event_type, event_issue_id, event_release_version, evidence_path)` but different `timestamp` values are considered duplicates and both are deduplicated to the row with the earliest `timestamp`. Tested by `test_append_flow_event_idempotent`.
- **Concurrent merges of the same branch**: When two branches both append `FLOW_REFERENCED_BY_ISSUE` events for `ISS-ADH-012` (same issue, same event_type), the union merge preserves both rows. Downstream consumers must tolerate duplicates (idempotency is best-effort).
- **`specs/_product/flows.jsonl` deleted or corrupted**: `deviate explore post` re-seeds from `flows/index.md` (append-only invariant applies to *rows*, not files — the file can be re-created via re-seeding). Tested at the exploration boundary.
- **Drift flag values introduced by future issues**: New flags must be added to `FlowCoverage.drift_flag` `Literal[...]` *before* the issue that emits them lands; otherwise Pydantic `ValidationError` fires on re-parse. The seven flags enumerated at `specs/explore/flow-ledger.md:128-132` are the complete vocabulary for this issue.
- **`FlowEvent` with `event_issue_id=None`, `event_release_version=None`, `evidence_path=None`**: Valid only for `FLOW_DISCOVERED` / `FLOW_DOCUMENTED` / `FLOW_DEPRECATED`. Cross-validated inside `FlowEvent` Pydantic validator: at least one of the three reference fields must be non-None for `FLOW_REFERENCED_BY_ISSUE` / `FLOW_INCLUDED_IN_RELEASE` / `FLOW_IMPLEMENTATION_EVIDENCE_ADDED` / `FLOW_CONFIRMED_IMPLEMENTED`.

## Performance Constraints

- **L_max (Flow Coverage derivation)**: ≤ 200ms for up to 100 `FlowRecord` rows and 10,000 `FlowEvent` rows (measured on macOS / ext4 / apfs). Acceptable budget because derivation is a single linear pass over each ledger.
- **L_max (`deviate explore post` total)**: ≤ 500ms above existing init (matches the AGENTS.md L_max ≤ 500ms init gate). The Flow Coverage Report add ≤ 200ms derived.
- **Throughput**: Ledger parse via `model_validate_json(line)` of 10,000 rows completes in ≤ 1s on commodity hardware. Append via `_append_with_compound_key` is O(N) per call (in-memory set check + append), acceptable for ≤ 100 rows per `deviate explore post` invocation.
- **Round-trip cost**: Parse + re-emit `flows.jsonl` must round-trip byte-equal (no whitespace drift). Tested explicitly.
- **Table render cost**: Rich `Table` rendering of 4 rows (current scale) is sub-millisecond; remains under 50ms even at 100 rows.
- **Test suite budget**: `mise run test tests/state/test_ledger.py` adds ≤ 3 new tests, each ≤ 200ms (mocked ledger paths, no I/O). Full suite `mise run test` remains < 30s per AGENTS.md performance mandate.
- **File size**: `specs/_product/flows.jsonl` initial seed is ≤ 4KB (4 identity rows + ~7 events per flow × 4 = ~28 event rows ≈ 4KB total). Grows linearly with flow churn; bounded by repo activity.
- **Lint budget**: `mise run lint` (ruff check) reports zero violations on the three new Pydantic models and the new test functions; `mise run format-check` passes with the default ruff format.

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/state/test_ledger.py::test_flow_record_validates_against_canonical_regex` — assert `FlowRecord(flow_id="FLOW-1")` raises `ValidationError`; `FlowRecord(flow_id="FLOW-04")` succeeds; `FlowRecord(flow_id="flow-04")` raises `ValidationError`. Reuses the canonical `_FLOW_REF_PATTERN` regex from `src/deviate/cli/adhoc.py:19`.
  - `tests/state/test_ledger.py::test_append_flow_event_idempotent` — seed `flows.jsonl` with one `FLOW_REFERENCED_BY_ISSUE` event; re-append with identical `(flow_id, event_type, event_issue_id, timestamp)`; assert zero net appends.
  - `tests/state/test_ledger.py::test_load_flow_coverage_detects_documented_but_not_implemented` — seed ledger with discovery + document events only; assert `FlowCoverage.drift_flag == "DOCUMENTED_BUT_NOT_IMPLEMENTED"`.
  - `tests/state/test_ledger.py::test_flow_event_requires_reference_field_for_linked_events` — assert `FlowEvent(event_type="FLOW_REFERENCED_BY_ISSUE", event_issue_id=None)` raises `ValidationError`; same for `FLOW_INCLUDED_IN_RELEASE` / `FLOW_CONFIRMED_IMPLEMENTED` with all-None references.
  - `tests/state/test_ledger.py::test_flow_record_round_trip_byte_equal` — parse, re-emit, compare bytes (no whitespace drift).
  - `tests/cli/test_explore.py::test_explore_post_renders_flow_coverage_table` — temp workdir with seeded `flows/index.md` (4 flows) + `flows.jsonl` (empty); invoke `deviate explore post`; assert stdout contains `FLOW-04` and `DOCUMENTED_BUT_NOT_IMPLEMENTED`.
  - `tests/cli/test_explore.py::test_explore_post_skips_orphaned_flow_refs` — issue row with `flow_refs: ["FLOW-99"]` (no matching `FlowRecord`); assert command exits 0 and emits a warning rather than appending an event.
- **Integration Sandbox Targets**:
  - `tests/cli/test_init.py::test_init_seeds_flows_jsonl_merge_union` — assert `.gitattributes` declared by `deviate setup` contains `specs/_product/flows.jsonl merge=union` after the run.
  - `tests/e2e/test_flow_coverage.bats` — end-to-end BATS test: initialize temp workdir, run `deviate explore post` against populated `specs/_product/flows/`, assert file rows match expected counts and stdout contains the yellow-highlighted drift row.

## Demonstration Path
```bash
# 1. Verify FlowRecord + FlowEvent import against the canonical regex
uv run python -c "
from datetime import datetime, timezone
from deviate.state.ledger import FlowRecord, FlowEvent
fr = FlowRecord(flow_id='FLOW-04', name='Live-Stream Agent Progress via RPC', actor='Developer', domain='Agent Integration', source='specs/_product/flows/flows-streaming.md')
print(fr.model_dump_json(indent=2))
fe = FlowEvent(flow_id='FLOW-04', event_type='FLOW_DOCUMENTED', timestamp=datetime.now(timezone.utc))
print(fe.model_dump_json(indent=2))
"

# 2. Seed flows.jsonl from canonical flow index
deviate explore post

# 3. Inspect the resulting ledger
cat specs/_product/flows.jsonl | uv run python -c "
import sys, json
for line in sys.stdin:
    obj = json.loads(line)
    print(obj.get('flow_id', '?'), obj.get('event_type', obj.get('name', '?')))
"

# 4. Derive coverage and render the report
uv run python -c "
from pathlib import Path
from deviate.state.ledger import load_flow_coverage
rows = load_flow_coverage(Path('specs/_product/flows.jsonl'), Path('specs/_product/flows/index.md'), Path('specs/issues.jsonl'))
for r in rows:
    print(r.flow_id, r.drift_flag)
"

# 5. Verify reverse indexing from existing issues
grep -oE '\"flow_refs\":\[[^\]]*\]' specs/issues.jsonl | sort -u

# 6. Run the new unit tests
mise run test tests/state/test_ledger.py::test_flow_record_validates_against_canonical_regex -v
mise run test tests/state/test_ledger.py::test_append_flow_event_idempotent -v
mise run test tests/state/test_ledger.py::test_load_flow_coverage_detects_documented_but_not_implemented -v
mise run test tests/cli/test_explore.py::test_explore_post_renders_flow_coverage_table -v

# 7. Run the full exploration + init integration test
mise run test tests/cli/test_init.py::test_init_seeds_flows_jsonl_merge_union -v
mise run test tests/e2e/test_flow_coverage.bats -v

# 8. Manual smoke test: render the report in a fresh workdir
tmpdir=$(mktemp -d)
cd "$tmpdir"
git init -q && git config user.email "test@test" && git config user.name "Test"
mkdir -p specs/_product/flows
cp /Users/werner/Projects/tools/deviatdd/specs/_product/flows/index.md specs/_product/flows/index.md
uv run --project /Users/werner/Projects/tools/deviatdd deviate explore post
ls -la specs/_product/flows.jsonl

# 9. Lint and format check
mise run lint
mise run format-check
```
