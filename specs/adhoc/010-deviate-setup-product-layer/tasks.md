# Implementation Tasks: `ISS-ADH-010`

## Phase 1: Product-Layer Skill Template Scaffolding
**Goal**: Three new SKILL.md templates under `src/deviate/prompts/skills/` with canonical frontmatter, auto-discovered by existing `_install_skills_to_agents` path — no CLI or registration changes.

### Tasks

- TSK-010-01: Create three Product-layer skill templates (deviate-flows, deviate-architecture, deviate-release)
  - **Type**: Config
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/cli/test_init.py::test_init_creates_product_layer_skills tests/cli/test_init.py::test_init_product_layer_skills_idempotent -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/skills/deviate-flows/SKILL.md`
    - `src/deviate/prompts/skills/deviate-architecture/SKILL.md`
    - `src/deviate/prompts/skills/deviate-release/SKILL.md`
    - `tests/cli/test_init.py`
  - **Rationale**: AC-ADHOC-010-01 requires three new SKILL.md files with canonical frontmatter matching `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` format. US-010-01 through US-010-04 require auto-discovery via existing `_install_skills_to_agents`. Naming resolves the singular-vs-plural inconsistency flagged at `specs/explore/product-layer.md:68` — plural form `deviate-flows` chosen per `specs/_product/flows/flows-product.md:10,16` and `specs/_product/release-next.md:26`. Each SKILL.md body is a self-contained agent instruction referencing `specs/_product/flows/flows-product.md` and `specs/_product/release-next.md` as source-of-truth inputs.
  - **Details**:
    - **Red**: Write `test_init_creates_product_layer_skills` in `tests/cli/test_init.py` — assert all three SKILL.md files exist at `src/deviate/prompts/skills/<name>/SKILL.md`, parse as valid YAML via `yaml.safe_load`, carry `name:` matching directory name, `category: deviatdd-product-layer`, `version: 1.0.0`, and flat-list `aliases:` with slash-command forms. Write `test_init_product_layer_skills_idempotent` — re-run `deviate setup --agent claude` in a temp workdir where files already exist, assert `[yellow]SKIP[/]` log lines emitted, no duplicate errors.
    - **Green**: Create `src/deviate/prompts/skills/deviate-flows/SKILL.md` with frontmatter (`name: deviate-flows`, `description:` describing FLOW-01 flows definition, `category: deviatdd-product-layer`, `version: 1.0.0`, `aliases: [/deviate-flows, spec:flows]` — flat YAML list format per reference). Body: instructs agent to converse with user to identify core customer flows, reference `specs/_product/flows/flows-product.md` as seed to extend (not regenerate), write new files under `specs/_product/flows/flows-<domain>.md`, update `specs/_product/flows/index.md` per FLOW-01 Success State at `specs/_product/flows/flows-product.md:25-32`. Create `src/deviate/prompts/skills/deviate-architecture/SKILL.md` with frontmatter (`name: deviate-architecture`, `description:` describing FLOW-02 cross-epic architecture, `category: deviatdd-product-layer`, `version: 1.0.0`, `aliases: [/deviate-architecture, spec:architecture]`). Body: requires user flows to exist in `specs/_product/flows/` as precondition (FLOW-02 Preconditions at `specs/_product/flows/flows-product.md:46-47`), directs agent to produce/maintain `specs/_product/architecture.md` and `specs/_product/domain-model.md` (FLOW-02 Success State at `specs/_product/flows/flows-product.md:57-59`), applies Local/Context-Bridging/Context-Creating classification (FLOW-02 Metrics at `specs/_product/flows/flows-product.md:63`). Create `src/deviate/prompts/skills/deviate-release/SKILL.md` with frontmatter (`name: deviate-release`, `description:` describing FLOW-03 release planning, `category: deviatdd-product-layer`, `version: 1.0.0`, `aliases: [/deviate-release, spec:release]`). Body: requires architecture and flows to exist as preconditions (FLOW-03 Preconditions at `specs/_product/flows/flows-product.md:77-79`), accepts a release-goal description, writes/overrides `specs/_product/release-next.md` (FLOW-03 Success State at `specs/_product/flows/flows-product.md:90-91`).
    - **Refactor**: Verify frontmatter field ordering matches reference (`name`, `description`, `category`, `version`, `aliases`). Verify `description:` values are single-line YAML strings (no embedded newlines). Verify `aliases:` use flat YAML list format (not inline `[...]`). Run `mise run lint` — no violations on SKILL.md files.
    - **Edge Cases**: If SKILL.md directory already exists from prior partial implementation, idempotent rewrite (match existing `_scaffold_constitution` skip-on-exists logic at `src/deviate/cli/__init__.py:495-497`). Missing seed file at `specs/_product/flows/flows-product.md` does not block installation — failure surfaces at agent invocation time. `description:` values ≤ 200 chars and single-line for YAML parser compatibility.
    - **Acceptance**: `ls src/deviate/prompts/skills/deviate-flows/SKILL.md src/deviate/prompts/skills/deviate-architecture/SKILL.md src/deviate/prompts/skills/deviate-release/SKILL.md` succeeds. YAML frontmatter parse via `yaml.safe_load` passes for all three. `name:` equals directory name. `category:` equals `deviatdd-product-layer`. `version:` equals `1.0.0`. `aliases:` contains slash-command forms. `deviate setup --agent claude` in temp workdir creates `.claude/skills/deviate-flows/SKILL.md` etc. with byte-equal content. Idempotent re-run skips without errors.

---

## Phase 2: Data Model Extension — flow_refs Field + CLI Threading
**Goal**: Optional `flow_refs: list[str]` field on `IssueRecord` and `AdhocRecord` Pydantic models, threaded through `shard_post` (macro.py) and `adhoc pre` (adhoc.py) with `--flow-ref` CLI flag.

### Tasks

- TSK-010-02: Add flow_refs to IssueRecord and thread through shard_post
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_state/test_ledger.py::test_flow_refs_round_trip_on_issue_record tests/test_cli/test_macro.py -v -k shard_post`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `src/deviate/cli/macro.py`
  - **Rationale**: AC-ADHOC-010-13 requires `IssueRecord` to accept optional `flow_refs` field. AC-ADHOC-010-16 requires round-trip through `append_issue_record`. US-010-07 requires the issues ledger to carry flow traceability. The `shard_post` at `src/deviate/cli/macro.py:681-690` constructs `IssueRecord` from parsed manifest data — the `flow_refs` field must be threaded from `issue_data.get("flow_refs", [])` into the constructor. Pydantic's `Field(default_factory=list)` ensures legacy JSONL data (without `flow_refs`) deserializes without error.
  - **Details**:
    - **Red**: Write `test_flow_refs_round_trip_on_issue_record` in `tests/test_state/test_ledger.py` — construct `IssueRecord(...)` with `flow_refs=["FLOW-01", "FLOW-02"]`, call `model_dump_json()`, parse back with `IssueRecord.model_validate(json.loads(...))`, assert `flow_refs` list preserved unchanged. Write `test_issue_record_flow_refs_defaults_to_empty` — construct `IssueRecord(...)` without `flow_refs=`, assert `flow_refs` equals `[]`. Write `test_issue_record_flow_refs_rejects_non_list` — construct with `flow_refs="FLOW-01"` (string not list), assert `ValidationError`. Write `test_shard_post_threads_flow_refs` — mock manifest with `flow_refs`, verify `IssueRecord(...)` call includes the field.
    - **Green**: Add `flow_refs: list[str] = Field(default_factory=list)` to `IssueRecord` at `src/deviate/state/ledger.py:36` (before `model_config`). Add `flow_refs=issue_data.get("flow_refs", [])` to the `IssueRecord(...)` constructor at `src/deviate/cli/macro.py:681-690`. No changes to `_read_ledger`, `append_issue_record`, `resolve_issue_record`, or `_get_unblocked_backlog_features` — they operate on dicts and `model_validate()` transparently handles the new field.
    - **Refactor**: Verify Pydantic model config `{"extra": "forbid"}` remains intact — adding a declared field does not trigger it. Verify `model_dump_json()` serializes `flow_refs` as a JSON array. Verify round-trip with `model_validate_json()` preserves the field. Verify existing tests that construct `IssueRecord` without `flow_refs` still pass (default list).
    - **Edge Cases**: `flow_refs` missing from JSONL (legacy data) — `Field(default_factory=list)` provides empty list on deserialization. Empty list is valid per AC-ADHOC-010-11 (enabling-slice shards with zero flow-touching FRs). `issue_data` dict missing `"flow_refs"` key — `.get("flow_refs", [])` safely defaults to `[]`.
    - **Acceptance**: `IssueRecord(model_validate(json.loads(IssueRecord(..., flow_refs=["FLOW-01"]).model_dump_json()))).flow_refs == ["FLOW-01"]`. `append_issue_record` with `flow_refs` emits JSONL line containing `"flow_refs"`. Existing ledger tests pass unchanged.

- TSK-010-03: Add flow_refs to AdhocRecord and --flow-ref CLI flag
  - **Type**: Domain_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_state/test_ledger.py::test_flow_refs_round_trip_on_adhoc_record tests/test_cli/test_adhoc.py -v -k "flow_ref or adhoc_pre"`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/state/ledger.py`
    - `src/deviate/cli/adhoc.py`
  - **Rationale**: AC-ADHOC-010-13 requires `AdhocRecord` to accept optional `flow_refs` field. AC-ADHOC-010-14 requires `deviate adhoc pre --flow-ref FLOW-01,FLOW-02` to parse comma-separated IDs and thread into `AdhocRecord`. US-010-06 requires `--flow-ref` override capability. The `pre` command at `src/deviate/cli/adhoc.py:45-84` creates `AdhocRecord` — a new optional Typer parameter and parsing logic are added. `model_dump_json()` at line 74 automatically serializes the new field.
  - **Details**:
    - **Red**: Write `test_flow_refs_round_trip_on_adhoc_record` in `tests/test_state/test_ledger.py` — construct `AdhocRecord(...)` with `flow_refs=["FLOW-01"]`, serialize, deserialize, assert preserved. Write `test_adhoc_pre_flow_ref_flag` — invoke CLI with `--flow-ref FLOW-01,FLOW-02`, parse `specs/adhoc.jsonl`, assert `"flow_refs": ["FLOW-01", "FLOW-02"]`. Write `test_flow_ref_validation_rejects_malformed` — invoke with `--flow-ref FLOW-1`, assert exit code 1 and validation error message. Write `test_flow_ref_validation_rejects_lowercase` — invoke with `--flow-ref flow-01`, assert exit code 1. Write `test_adhoc_pre_flow_ref_strips_whitespace` — invoke with `--flow-ref "FLOW-01, FLOW-02"`, assert parsed as `["FLOW-01", "FLOW-02"]`.
    - **Green**: Add `flow_refs: list[str] = Field(default_factory=list)` to `AdhocRecord` at `src/deviate/state/ledger.py:296` (before `model_config`). Add `--flow-ref` Typer option to `pre` command in `src/deviate/cli/adhoc.py`: `flow_ref: str | None = typer.Option(None, "--flow-ref", help="Comma-separated FLOW-XX IDs (e.g. FLOW-01,FLOW-02)")`. Parse comma-separated string: `split(",")` → strip whitespace → validate each ID against `^FLOW-\d{2,}$` regex (min 2 digits, per edge case FLOW-IDs > 99). Reject malformed IDs with `typer.Exit(code=1)` and `[red]VALDIATION_ERROR[/]` message. Pass `flow_refs=parsed_list` to `AdhocRecord(...)` constructor. `model_dump_json()` at line 74 auto-serializes the field — no change needed.
    - **Refactor**: Extract flow-ref parsing to standalone `_parse_flow_refs(raw: str | None) -> list[str]` function for testability. Validate regex with `re.fullmatch` (not `re.match`) to reject partial matches. Use `deviate.core.validation` module pattern if one exists. Verify `_read_adhoc_ledger` at lines 20-37 round-trips the field via dict operations (no model parsing needed — it reads raw JSON dicts).
    - **Edge Cases**: Empty `--flow-ref` string → parse as `None` → default empty list. Comma-separated string with trailing comma (`"FLOW-01,"`) → strip empty entries. Duplicate IDs (`"FLOW-01,FLOW-01"`) → deduplicate. `--flow-ref` not passed → `AdhocRecord.flow_refs` defaults to `[]`. Regex `^FLOW-\d{2,}$` ensures `FLOW-1` (single digit) is rejected, `FLOW-100` (3 digits) is accepted.
    - **Acceptance**: `deviate adhoc pre "test desc" --flow-ref FLOW-01,FLOW-02` writes `AdhocRecord` with correct `flow_refs`. Malformed IDs (`FLOW-1`, `flow-01`) error before ledger write. Whitespace-normalized parsing produces clean list. Existing adhoc tests pass unchanged.

---

## Phase 3: Skill Consumer Upgrades — shard + adhoc Consume _product Specs
**Goal**: Upgrade existing `deviate-shard` and `deviate-adhoc` SKILL.md bodies to read `specs/_product/` specs as authoritative context and emit `flow_refs:` frontmatter in generated issues.

### Tasks

- TSK-010-04: Upgrade deviate-shard SKILL.md to consume Product-layer specs and emit flow_refs
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test tests/test_core/test_skills.py -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/skills/deviate-shard/SKILL.md`
  - **Rationale**: AC-ADHOC-010-11 requires the shard skill to read `specs/_product/flows/`, `specs/_product/release-next.md`, `specs/_product/architecture.md`, `specs/_product/domain-model.md` as authoritative context and emit `flow_refs:` in shard frontmatter. US-010-05 requires flow coverage audits over `specs/issues.jsonl`. The shard skill body at lines 1-214 currently has no reference to `_product` specs. Adding invariant 11 instructs the agent to derive FR→flow mappings from `specs/_product/flows/flows-product.md` and propagate `flow_refs:` into each shard issue's YAML frontmatter.
  - **Details**:
    - **Implementation**: Add invariant 11 to the `<system_instructions>` block (after line 28): "11. **Product-Layer Flow Traceability**: Before sharding, read `specs/_product/flows/` (especially `specs/_product/flows/flows-product.md` and any domain-specific `flows-<domain>.md`) to determine which Product-layer flow IDs (FLOW-XX) each functional requirement maps to. Also read `specs/_product/release-next.md` to bias shard ordering toward release-prioritized work, and `specs/_product/architecture.md` and `specs/_product/domain-model.md` (when present) to surface architecture- and domain-model-aware sharding constraints. In the `## Internal ICoT Ledger` block, add a Pass 2.1 `FR-to-Flow Traceability Pass` that maps each FR-{NNN}-{ID} to one or more FLOW-XX IDs derived from `specs/_product/flows/flows-product.md` and domain-specific flow files. For every generated shard issue, emit `flow_refs: [FLOW-XX, ...]` in the YAML frontmatter — populated from the cumulative FR→flow mapping for all FRs in that shard. Emit `flow_refs: []` for enabling/infrastructure slices that touch zero Product-layer flows (per Vertical Slice Mandate)." Update `§issue_generation` (line 111): change "YAML frontmatter with `title`, `labels`, `source_file`, `blocked_by`, `coordinates_with`, `issue_id`" to include `flow_refs`. Update manifest JSON example at lines 140-169: add `"flow_refs": ["FLOW-01"]` to each issue entry. Update Pass 2 (Boundary Demarcation Pass, around line 28-29) to include flow-to-FR traceability as a coverage check. Add edge case at `<edge_case_handling>`: "No `specs/_product/` directory exists → emit `flow_refs: []` for all shards and note gap in manifest."
    - **Edge Cases**: `specs/_product/` directory absent → all shards emit `flow_refs: []` — no halt. `specs/_product/flows/flows-product.md` defines flows but user hasn't authored domain-specific extensions → use only `flows-product.md` as the flow catalog. FR maps to zero flows (enabling slice) → `flow_refs: []` per Vertical Slice Mandate. Single FR maps to multiple flows → emit all matching IDs in `flow_refs` list.
    - **Acceptance**: Existing `tests/test_core/test_skills.py` tests pass (frontmatter parse intact). Body contains `flow_refs` and `_product` references. Frontmatter schema reference at line 111 includes `flow_refs`. Manifest JSON examples at lines 140-169 include `"flow_refs"` fields.

- TSK-010-05: Upgrade deviate-adhoc SKILL.md to consume Product-layer specs and emit flow_refs
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `mise run test tests/test_core/test_skills.py -v`
  - **Estimated Time**: 30 minutes
  - **Files**:
    - `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`
  - **Rationale**: AC-ADHOC-010-12 requires the adhoc skill to read `specs/_product/flows/` and `specs/_product/release-next.md` to infer flow references, accept `--flow-ref` CLI override, and emit `flow_refs:` in issue frontmatter. US-010-06 requires flow traceability preservation from ad-hoc work. The adhoc skill body at lines 1-197 currently has no reference to `_product` specs. Adding invariant 11 instructs the agent to consume Product-layer context and propagate `flow_refs:`.
  - **Details**:
    - **Implementation**: Add invariant 11 to the `<system_instructions>` block (after line 28): "11. **Product-Layer Flow Traceability**: Before generating the issue, read `specs/_product/flows/` (especially `specs/_product/flows/flows-product.md` and any domain-specific `flows-<domain>.md`) and `specs/_product/release-next.md` to understand the Product-layer flow landscape. Infer which FLOW-XX IDs the user's natural-language task touches. If no flows clearly match, surface a clarifying question in the discovery audit block before proceeding. Accept an explicit `--flow-ref FLOW-01,FLOW-02` CLI override (propagated through the underlying Typer command) — when present, use the explicit value verbatim instead of inferred mapping. Emit `flow_refs: [FLOW-XX, ...]` in the YAML frontmatter of the generated issue file at `specs/adhoc/issues/{NNN}-{slug}.md`, populated from either the explicit flag or the agent's inferred mapping." Update the output format schema at lines 130-170: add `flow_refs: [FLOW-XX, ...]` to the issue frontmatter template. Update the ledger registration JSON example at line 170 to include `"flow_refs"`. Add edge case at `<edge_case_handling>`: "`specs/_product/` directory absent → emit `flow_refs: []` for the issue and note gap."
    - **Edge Cases**: `specs/_product/` directory absent → emit `flow_refs: []` — no halt. User task description mentions no flows → `flow_refs: []`. `--flow-ref` override present → use verbatim, skip inference. User passes `--flow-ref` with IDs not in `flows-product.md` → warn but accept (the user may be defining a new flow). No `flows-product.md` exists but `flows-<domain>.md` files exist → scan domain files for flow IDs.
    - **Acceptance**: Existing `tests/test_core/test_skills.py` tests pass. Body contains `flow_refs` and `_product` references. Output format schema includes `flow_refs:` in frontmatter template. Ledger registration JSON includes `"flow_refs"` field.

---

## Phase 4: Integration Verification + Enumeration
**Goal**: Verify `discover_skills()` enumerates 23 skills, full init+export cycle installs Product-layer skills to agent directories with byte-equal content.

### Tasks

- TSK-010-06: discover_skills enumeration and full-cycle integration verification
  - **Type**: Infra_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `mise run test tests/cli/test_init.py::test_init_discover_skills_enumerates_product_layer tests/test_cli/test_init_export_cycle.py -v`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `tests/cli/test_init.py`
    - `tests/test_cli/test_init_export_cycle.py`
  - **Rationale**: AC-ADHOC-010-02 requires `discover_skills()` to return 23 skill names (existing 20 + 3 new). AC-ADHOC-010-03 and AC-ADHOC-010-05 require byte-equal content verification when `deviate setup --agent claude` and `--agent opencode` install skills to `.claude/skills/` and `.opencode/skills/`. AC-ADHOC-010-04 requires idempotent setup re-run. Tests extend `tests/cli/test_init.py` with enumeration assertion and `tests/test_cli/test_init_export_cycle.py` with content-equality checks for all three new skills across both agent backends.
  - **Details**:
    - **Red**: Write `test_init_discover_skills_enumerates_product_layer` in `tests/cli/test_init.py` — call `discover_skills()` from `deviate.core.skills`, assert result count `>= 23` (forward-compatible per risk assessment), assert `"deviate-flows" in result`, `"deviate-architecture" in result`, `"deviate-release" in result`. Write `test_init_export_cycle_installs_product_layer_skills_claude` in `tests/test_cli/test_init_export_cycle.py` — run `deviate setup --agent claude` in temp workdir, assert `.claude/skills/deviate-flows/SKILL.md` exists with `read_text()` content matching `src/deviate/prompts/skills/deviate-flows/SKILL.md` byte-for-byte. Repeat for deviate-architecture and deviate-release. Write `test_init_export_cycle_installs_product_layer_skills_opencode` with same assertions for `.opencode/skills/`. Write `test_init_export_cycle_product_layer_skills_idempotent` — re-run setup, assert no errors, assert `[yellow]SKIP[/]` emitted for each already-present skill.
    - **Green**: No production code changes needed. The existing `discover_skills()` at `src/deviate/core/skills.py:20-26` and `_install_skills_to_agents` at `src/deviate/cli/__init__.py:518-531` operate generically on any directory under `src/deviate/prompts/skills/` containing a `SKILL.md`. Adding three new directories in TSK-010-01 is sufficient. Integration tests verify the auto-discovery behavior.
    - **Refactor**: Use `pathlib.Path.read_text()` for content comparison (byte-level). Mock `Path.cwd()` to temp directory pattern from existing integration tests. Follow `tmp_git_repo` fixture pattern if test requires git operations. Ensure test isolation — no mutation of real repository's `.claude/skills/` or `.opencode/skills/`.
    - **Edge Cases**: `discover_skills()` returns exact count 23 today — use `>= 23` assertion for forward-compatibility when more skills are added later. Agent backend unsupported (`--agent unknown`) — verify `install_skill` skip behavior inherited from existing logic at `src/deviate/cli/__init__.py:525`. Workdir missing `.deviate/config.toml` — setup command should still install skills (default config). Race condition: two concurrent setup runs — the existing skip-on-exists logic handles idempotency.
    - **Acceptance**: `discover_skills()` returns >= 23 names including all three new skills. `deviate setup --agent claude` creates byte-equal `.claude/skills/deviate-flows/SKILL.md`. `deviate setup --agent opencode` creates byte-equal `.opencode/skills/deviate-flows/SKILL.md`. Idempotent re-run skips without error. Full test suite `mise run test` completes < 18s.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (TSK-010-01) → Phase 2 (TSK-010-02 → TSK-010-03) → Phase 3 (TSK-010-04 → TSK-010-05) → Phase 4 (TSK-010-06)
2. TSK-010-02 and TSK-010-03 modify the same file (`src/deviate/state/ledger.py`) — execute sequentially
3. Phase 3 tasks are independent of each other but depend on Phase 1 completing (to understand frontmatter patterns)
4. Phase 4 depends on Phase 1 (skills must exist to discover/enumerate)

**Critical Dependency Chains**:
- TSK-010-02 must precede TSK-010-03 (both add fields to Pydantic models in `src/deviate/state/ledger.py`)
- TSK-010-01 must precede TSK-010-04 and TSK-010-05 (upgraded skills reference the new template patterns)
- TSK-010-01 must precede TSK-010-06 (discovery/enumeration requires skills to exist)

**Risk Hotspots**:
- `src/deviate/state/ledger.py` is modified by both TSK-010-02 and TSK-010-03 — merge conflict risk if executed in parallel. Execute sequentially.
- `tests/cli/test_init.py` is extended by TSK-010-01 (Red phase) and TSK-010-06 (Red phase) — coordinate test function naming and position to avoid conflicts.
- `validate_yaml_frontmatter` at `src/deviate/core/validation.py:104-115` does NOT need modification — the function validates YAML syntax only (not key names). The concern in the issue at line 49 is addressed: `flow_refs` as a frontmatter key passes the existing validator because it checks structural validity, not known/unknown keys. No code change required.
- Naming inconsistency (singular `/deviate-flow` vs plural `/deviate-flows`): resolved to plural form `deviate-flows` per `specs/_product/flows/flows-product.md:10,16` and `specs/_product/release-next.md:26`. Skill directory name matches: `src/deviate/prompts/skills/deviate-flows/`.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/cli/test_init.py` (TSK-010-01 + TSK-010-06), `src/deviate/state/ledger.py` (TSK-010-02 + TSK-010-03), `src/deviate/prompts/skills/deviate-shard/SKILL.md` (TSK-010-04 only), `src/deviate/prompts/skills/deviate-adhoc/SKILL.md` (TSK-010-05 only)

**Defensive Exclusion Compliance**:
- No new Typer sub-app (`flow_app`, `architecture_app`, `release_app`) — AC-ADHOC-010-09
- No modification to `_VALID_PHASES`, `_PHASE_ORDER`, or any state model — AC-ADHOC-010-09
- No constitution update (`specs/constitution.md` stays v0.2.0) — AC-ADHOC-010-10
- No modification to `_install_skills_to_agents`, `discover_skills`, or `install_skill` — auto-discovery handles new directories
- No modification to `specs/DeviaTDD-api.md` or `specs/DeviaTDD-architecture.md`
- No modification to `specs/_product/flows/flows-product.md` or `specs/_product/release-next.md` — referenced as inputs only

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.

## Micro-Layer Test Performance Constraint (ALL TASKS)

Never call `_run_pytest()` (in `src/deviate/cli/micro.py`) in tests. Tests that invoke CLI commands which internally call `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with an appropriate `subprocess.CompletedProcess` return value. All tasks in this issue add unit-level tests (frontmatter parse, model construction, CLI flag parsing) — no subprocess invocations, no `_run_pytest` calls. Estimated test overhead < 500ms per task, full suite remains < 18s.
