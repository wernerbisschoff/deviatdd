## Plan Summary
- **Issue**: ISS-ADH-010 — Product Layer Skill Scaffolding — `deviate setup` Creates /deviate-flows, /deviate-architecture, /deviate-release
- **Implementation Strategy**: Two-phase delivery: (1) author three new SKILL.md templates under `src/deviate/prompts/skills/` with canonical frontmatter so the existing `_install_skills_to_agents` path auto-discovers them; (2) upgrade the two existing issue-emitting skills (`deviate-shard`, `deviate-adhoc`) and their backing data models (`IssueRecord`, `AdhocRecord`) to consume Product-layer specs and emit `flow_refs` frontmatter for downstream traceability.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 3-5 hours

## Workstation Mapping
- **src/deviate/prompts/skills/deviate-flows/SKILL.md**: NEW — skill body instructing agent to converse with user, identify core customer flows, write to `specs/_product/flows/flows-<domain>.md`, and update `specs/_product/flows/index.md`. Source anchor: `specs/_product/flows/flows-product.md:1-32` FLOW-01.
  - **Current State**: Does not exist.
  - **Changes Required**: Create file with canonical frontmatter (`name: deviate-flows`, `category: deviatdd-product-layer`, `version: 1.0.0`, aliases including `/deviate-flows`, `spec:flows`). Body references `specs/_product/flows/flows-product.md` as seed to extend, directs output to `specs/_product/flows/` + index update.
  - **Integration Surface**: `_install_skills_to_agents` at `src/deviate/cli/__init__.py:518-531` auto-discovers via file system enumeration; no import or registration required.

- **src/deviate/prompts/skills/deviate-architecture/SKILL.md**: NEW — skill body instructing agent to produce/maintain `specs/_product/architecture.md` and `specs/_product/domain-model.md`, requiring user flows as precondition, applying Local/Context-Bridging/Context-Creating classification. Source anchor: `specs/_product/flows/flows-product.md:34-64` FLOW-02.
  - **Current State**: Does not exist.
  - **Changes Required**: Create file with canonical frontmatter (`name: deviate-architecture`, `category: deviatdd-product-layer`, aliases including `/deviate-architecture`, `spec:architecture`). Body enforces flow-existence precondition, directs output to architecture/domain-model files.
  - **Integration Surface**: Same as deviate-flows — file-system discovery via `_install_skills_to_agents`.

- **src/deviate/prompts/skills/deviate-release/SKILL.md**: NEW — skill body requiring architecture + flows as preconditions, accepting release-goal description, writing/overriding `specs/_product/release-next.md`. Source anchor: `specs/_product/flows/flows-product.md:66-94` FLOW-03.
  - **Current State**: Does not exist.
  - **Changes Required**: Create file with canonical frontmatter (`name: deviate-release`, `category: deviatdd-product-layer`, aliases including `/deviate-release`, `spec:release`). Body enforces preconditions, accepts release-goal argument, directs output to `specs/_product/release-next.md`.
  - **Integration Surface**: Same as above.

- **src/deviate/state/ledger.py (IssueRecord + AdhocRecord)**: EXTEND — both Pydantic models gain an optional `flow_refs: list[str]` field.
  - **Current State**: `IssueRecord` at lines 25-36 has `issue_id`, `type`, `title`, `status`, `source_file`, `blocked_by`, `coordinates_with`, `timestamp`, `created_at`. `AdhocRecord` at lines 289-296 has `issue_id`, `description`, `execution_mode`, `status`, `timestamp`. Both use `model_config = {"extra": "forbid"}`.
  - **Changes Required**: Add `flow_refs: list[str] = Field(default_factory=list)` to both models. The `model_config = {"extra": "forbid"}` means no other code changes are needed — existing callers who don't pass `flow_refs` get the default empty list.
  - **Integration Surface**: `IssueRecord.flow_refs` consumed by `append_issue_record` (line 196), `append_issue_transition` (line 147), `resolve_issue_record` (line 184), `_get_unblocked_backlog_features` (line 313). `AdhocRecord.flow_refs` consumed by `adhoc pre` (line 64, `src/deviate/cli/adhoc.py`), `_read_adhoc_ledger` (line 20).

- **src/deviate/cli/macro.py (shard_post, ~lines 681-691)**: EXTEND — thread `flow_refs` from issue_data dict into `IssueRecord` constructor.
  - **Current State**: `IssueRecord(...)` constructor at line 681-690 does not include `flow_refs=` argument. The parsed `issue_data` dict comes from the shard manifest JSON; if the shard skill emits `flow_refs:` in the manifest issue entries, the dict will contain the key but it's silently dropped.
  - **Changes Required**: Add `flow_refs=issue_data.get("flow_refs", [])` to the `IssueRecord(...)` constructor call at line 681.
  - **Integration Surface**: Downstream ledger consumers (`_read_ledger`, `resolve_issue_record`, `_get_unblocked_backlog_features`) will transparently pick up the new field via `IssueRecord.model_validate()`.

- **src/deviate/cli/adhoc.py (pre command, lines 45-84)**: EXTEND — add `--flow-ref` Typer option, parse comma-separated values, thread into `AdhocRecord`.
  - **Current State**: `pre` command (line 45-84) accepts `description` argument and `--skip-gates` flag. Creates `AdhocRecord` with `issue_id`, `description`, `execution_mode`, `status`.
  - **Changes Required**: Add `--flow-ref` `typer.Option(None, ...)` parameter. Parse comma-separated string into `list[str]`, validate each ID matches `FLOW-\d{2,}` pattern. Pass `flow_refs=...` to `AdhocRecord(...)` constructor.
  - **Integration Surface**: `AdhocRecord.model_dump_json()` automatically serializes the new field. The `_read_adhoc_ledger` function at lines 20-37 naively round-trips all dict keys.

- **src/deviate/core/validation.py (validate_yaml_frontmatter, line 104)**: No changes needed. The function at lines 104-115 validates that content has valid YAML frontmatter format — it does not enumerate known/unknown keys. Any frontmatter key (including `flow_refs`) passes validation as long as the YAML block is valid syntax. The warning at `src/deviate/cli/macro.py:659-661` fires on structurally invalid YAML, not on unrecognized keys. **No code change required** — `flow_refs` is a recognized key by nature of the validator accepting all YAML.

- **src/deviate/prompts/skills/deviate-shard/SKILL.md**: UPGRADE — instruct agent to read `specs/_product/flows/`, `specs/_product/release-next.md`, `specs/_product/architecture.md`, `specs/_product/domain-model.md` as authoritative context, and emit `flow_refs: [FLOW-XX, ...]` in each shard's YAML frontmatter.
  - **Current State**: 214 lines; §5 defines the issue ID format and frontmatter schema. No reference to `_product` specs or `flow_refs`.
  - **Changes Required**: Add an instruction invariant directing agent to (a) scan `specs/_product/` for context, (b) derive FR→flow mapping from `specs/_product/flows/flows-product.md`, (c) emit `flow_refs:` in the frontmatter of each shard issue. Add `flow_refs` to the frontmatter schema reference and manifest YAML examples.
  - **Integration Surface**: The shard post-script (`src/deviate/cli/macro.py:681-691`) already reads `issue_data` from the manifest and threads it to `IssueRecord` — after the `flow_refs=` argument is added to the constructor.

- **src/deviate/prompts/skills/deviate-adhoc/SKILL.md**: UPGRADE — instruct agent to read `specs/_product/flows/` and `specs/_product/release-next.md` to infer flow references for tasks, surface `--flow-ref` CLI override, emit `flow_refs:` in issue frontmatter.
  - **Current State**: 197 lines; 10 instruction invariants. No reference to `_product` specs or `flow_refs`.
  - **Changes Required**: Add instruction invariant directing agent to (a) read `specs/_product/` for flow context, (b) infer which flows the user's task touches, (c) accept `--flow-ref FLOW-01,FLOW-02` override from the CLI, (d) emit `flow_refs:` in the generated issue's YAML frontmatter.
  - **Integration Surface**: The adhoc pre command at `src/deviate/cli/adhoc.py:45-84` already creates `AdhocRecord` — after `flow_refs` is added to the model and `--flow-ref` flag is added.

- **tests/cli/test_init.py**: EXTEND — add tests verifying the three new SKILL.md files exist and carry valid frontmatter.
  - **Current State**: 677 lines; comprehensive `TestInitCommand` class with 10+ tests. No Product-layer skill tests.
  - **Changes Required**: Add `test_init_creates_product_layer_skills` — verifies all three SKILL.md files exist at package path, parse as valid YAML frontmatter, carry `name:`, `category: deviatdd-product-layer`, `version: 1.0.0`, and include slash-command aliases. Add `test_init_product_layer_skills_idempotent` — re-run setup, assert no duplicate errors. Add `test_init_discover_skills_enumerates_product_layer` — call `discover_skills()` and assert 23 names returned.
  - **Integration Surface**: Tests import from `deviate.core.skills` (`discover_skills`, `resolve_skill`), use `CliRunner` with `chdir(tmp_path)` pattern matching existing tests.

- **tests/test_cli/test_adhoc.py / tests/test_state/test_ledger.py**: EXTEND — add tests for `flow_refs` field round-trip and `--flow-ref` CLI parsing.
  - **Current State**: Test files exist; need new test cases.
  - **Changes Required**: `test_flow_refs_round_trip` — construct `IssueRecord` and `AdhocRecord` with `flow_refs=`, serialize, deserialize, assert list preserved. `test_adhoc_pre_flow_ref_flag` — invoke CLI with `--flow-ref FLOW-01,FLOW-02`, assert `AdhocRecord.flow_refs` populated in `specs/adhoc.jsonl`. `test_flow_ref_validation_rejects_malformed` — assert validation error for malformed IDs.
  - **Integration Surface**: Standard pytest patterns; `AdhocRecord` import from `deviate.state.ledger`.

## Implementation Strategy
- **Phase 1 — Core Scaffolding**: Create three new SKILL.md files under `src/deviate/prompts/skills/` (deviate-flows, deviate-architecture, deviate-release).
  - **Files**: `src/deviate/prompts/skills/deviate-flows/SKILL.md`, `src/deviate/prompts/skills/deviate-architecture/SKILL.md`, `src/deviate/prompts/skills/deviate-release/SKILL.md`
  - **Approach**: Author each SKILL.md with canonical YAML frontmatter matching `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` format (flat YAML list for aliases, single-line description, ordered fields: name, description, category, version, aliases). Each body is a self-contained agent instruction referencing `specs/_product/flows/flows-product.md` and `specs/_product/release-next.md` as source-of-truth inputs. Naming is plural (`deviate-flows`) per seed artifacts. No CLI changes — the existing `_install_skills_to_agents` at `src/deviate/cli/__init__.py:518-531` auto-discovers via file-system enumeration at `src/deviate/core/skills.py:20-26`.
  - **Verification**: `ls src/deviate/prompts/skills/deviate-flows/SKILL.md` (and architecture, release); `uv run python -c "import yaml; ..."` frontmatter validation; `pytest tests/test_core/test_skills.py -v` (existing discover_skills test extended).

- **Phase 2 — Data Model Extension**: Add `flow_refs` field to `IssueRecord` and `AdhocRecord`, thread through `shard_post` and `adhoc pre`.
  - **Files**: `src/deviate/state/ledger.py` (both models), `src/deviate/cli/macro.py` (shard_post `IssueRecord` constructor), `src/deviate/cli/adhoc.py` (pre command with `--flow-ref` flag)
  - **Approach**: Add `flow_refs: list[str] = Field(default_factory=list)` to both `IssueRecord` and `AdhocRecord`. `model_config = {"extra": "forbid"}` already present — no migration needed. Add `flow_refs=issue_data.get("flow_refs", [])` to the `IssueRecord(...)` constructor in `shard_post` at line 681. Add `--flow-ref` Typer option to `adhoc pre`, parse comma-separated into list, validate each ID with regex `^FLOW-\d{2,}$`, pass to `AdhocRecord(flow_refs=...)`.
  - **Verification**: `pytest tests/test_state/test_ledger.py -v -k flow_refs`; `pytest tests/test_cli/test_adhoc.py -v -k flow_ref`; round-trip: construct model, dump JSON, validate_json, assert field preserved.

- **Phase 3 — Skill Consumer Upgrades**: Upgrade `deviate-shard` and `deviate-adhoc` SKILL.md to consume `_product` specs and emit `flow_refs` frontmatter.
  - **Files**: `src/deviate/prompts/skills/deviate-shard/SKILL.md`, `src/deviate/prompts/skills/deviate-adhoc/SKILL.md`
  - **Approach**: Amend each SKILL.md body with additional instruction invariants. For `deviate-shard`: add invariant requiring the agent to read `specs/_product/flows/`, `specs/_product/release-next.md`, `specs/_product/architecture.md`, `specs/_product/domain-model.md` as authoritative context; derive FR→flow mapping from `specs/_product/flows/flows-product.md`; emit `flow_refs: [FLOW-XX, ...]` in each shard's YAML frontmatter (empty list for zero-flow slices). Update frontmatter schema reference and manifest YAML examples to include `flow_refs`. For `deviate-adhoc`: add invariant requiring agent to read `specs/_product/flows/` and `specs/_product/release-next.md`; infer flow references; surface `--flow-ref FLOW-01,FLOW-02` CLI override option; emit `flow_refs:` in generated issue frontmatter.
  - **Verification**: Read updated SKILL.md files, grep for `flow_refs` and `_product` references; `pytest tests/test_core/test_skills.py -v` (existing shard skill tests still pass).

- **Phase 4 — Test Coverage**: Add unit tests and integration verification.
  - **Files**: `tests/cli/test_init.py`, `tests/test_state/test_ledger.py`
  - **Approach**: Three new test functions in `tests/cli/test_init.py`: (1) `test_init_creates_product_layer_skills` — assert files exist, parse frontmatter, validate fields; (2) `test_init_product_layer_skills_idempotent` — re-run setup, assert SKIP output; (3) `test_init_discover_skills_enumerates_product_layer` — call `discover_skills()`, assert 23 names. Two new test functions in `tests/test_state/test_ledger.py`: (1) `test_flow_refs_round_trip_on_issue_record`; (2) `test_flow_refs_round_trip_on_adhoc_record`. All tests follow existing mock/runner patterns.
  - **Verification**: `mise run test tests/cli/test_init.py::test_init_creates_product_layer_skills -v`; `mise run test tests/test_state/test_ledger.py -v`; full suite `mise run test` completes < 18s.

## Data Flow Analysis
1. **Skill Template Creation**: Developer authors three SKILL.md files → filesystem at `src/deviate/prompts/skills/<name>/SKILL.md` → `discover_skills()` enumerates directories → `_install_skills_to_agents` copies to agent skills dirs (`.claude/skills/`, `.opencode/skills/`, `.factory/skills/`).
2. **Agent Invocation**: Agent invokes `/deviate-flows` → reads SKILL.md body → references `specs/_product/flows/flows-product.md` → converses with user → writes `specs/_product/flows/flows-<domain>.md` → updates `specs/_product/flows/index.md`.
3. **Flow Traceability Chain**: Product-layer specs at `specs/_product/` → `deviate-shard` reads flows/architecture docs → derives FR→flow mapping → emits `flow_refs: [FLOW-XX]` in shard frontmatter → `shard_post` parses manifest → `IssueRecord(flow_refs=...)` → `append_issue_record` writes to `specs/issues.jsonl` → downstream consumers read ledger for flow coverage audits.
4. **Adhoc Flow Override**: User runs `deviate adhoc pre "desc" --flow-ref FLOW-01,FLOW-02` → CLI parses comma-separated string → validates against `^FLOW-\d{2,}$` → `AdhocRecord(flow_refs=["FLOW-01", "FLOW-02"])` → serialized to `specs/adhoc.jsonl` → agent reads `AdhocRecord.flow_refs` from contract → emits issue with `flow_refs: [FLOW-01, FLOW-02]` in frontmatter.

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Naming inconsistency (singular `/deviate-flow` vs plural `/deviate-flows`) causes downstream confusion | Low | Low | Resolved: plural form `deviate-flows` chosen per seed artifacts at `specs/_product/flows/flows-product.md:10,16` and AC at `specs/_product/release-next.md:26`. Skill directory name matches. |
| `IssueRecord.flow_refs` field rejected by `model_config = {"extra": "forbid"}` | High | None | Adding a declared field (not undeclared extra) is the standard Pydantic pattern. `model_config = {"extra": "forbid"}` applies to undeclared keys in input data, not to explicitly typed fields. No risk. |
| `validate_yaml_frontmatter` rejects `flow_refs` as unknown key | Low | None | The validator at `src/deviate/core/validation.py:104-115` validates YAML syntax, not key names. Any valid YAML frontmatter passes. The `[yellow]SHARD_WARNING[/]` at `src/deviate/cli/macro.py:659-661` fires on invalid YAML structure (no `---` delimiters, parse errors), not on unknown keys. No code change needed. |
| `_install_skills_to_agents` fails to discover new skills if directory exists without SKILL.md | Low | Low | `discover_skills()` at `src/deviate/core/skills.py:20-26` only returns `d.name` when `(d / "SKILL.md").exists()`. Creating directories alone is insufficient — SKILL.md must exist. Mitigation: create SKILL.md atomically with directory creation in implementation. |
| Adhoc `--flow-ref` validation rejects valid IDs due to regex mismatch with future FLOW-IDs > 99 | Low | Low | Use `^FLOW-\d{2,}$` regex accepting 2+ digits. Future FLOW-IDs with 3 digits (e.g., FLOW-100) pass. Two-digit minimum prevents `FLOW-1`. |
| Test suite exceeds 18s budget from new tests | Low | Low | New tests are unit-level (frontmatter parse, model construction, CLI flag parsing) — no subprocess, no network. Estimated overhead < 500ms. |
| `discover_skills()` count test breaks when more skills are added later | Medium | Medium | Use `>= 23` assertion instead of exact `== 23` so the test remains valid as the skill set grows. |

## Integration Points
- **`_install_skills_to_agents` / `discover_skills` / `install_skill`**: No modification required. These functions operate generically on any directory under `src/deviate/prompts/skills/` containing a `SKILL.md`. Adding three new directories is sufficient — no integration point change.
- **`shard_post` → `IssueRecord`**: The `IssueRecord(...)` constructor at `src/deviate/cli/macro.py:681-690` is extended with `flow_refs=issue_data.get("flow_refs", [])`. This thread-together of the new field is the sole integration change needed on the macro layer.
- **`adhoc pre` → `AdhocRecord`**: The `--flow-ref` Typer option is parsed at `src/deviate/cli/adhoc.py:45-84` and threaded into `AdhocRecord(flow_refs=...)`. The existing `model_dump_json()` call at line 74 automatically serializes the new list field.
- **`specs/issues.jsonl` consumers**: Any downstream code reading the issues ledger via `_read_ledger()` and `IssueRecord.model_validate()` will transparently receive `flow_refs` from the JSONL data. No integration change needed for consumers — Pydantic's default `Field(default_factory=list)` handles missing keys in legacy data.

## Constitutional Alignment
- **Architecture**: This issue adds Product-layer skill templates as agent instructions, not as DeviaTDD phase entries. The constitution at `specs/constitution.md:9` declares a three-layer Macro/Meso/Micro architecture. The Product layer operates above Macro via agent skill invocation (slash commands), not via the phase registry — no constitutional amendment is required. The defensive exclusion at `specs/adhoc/issues/010-deviate-setup-product-layer.md:51-54` explicitly forbids modifying `_VALID_PHASES`, `_PHASE_ORDER`, or the constitution version.
- **Testing**: New tests follow existing pytest patterns (`CliRunner`, `chdir(tmp_path)`, `monkeypatch`). Tests verify (a) SKILL.md file existence and frontmatter validity, (b) data model field round-trip serialization, (c) CLI flag parsing. No tests invoke `_run_pytest` — all are fast unit assertions. Coverage extends to `src/deviate/state/ledger.py` (new field), `src/deviate/cli/adhoc.py` (new flag), `src/deviate/cli/macro.py` (thread-through).
- **Git Isolation**: Tests use `chdir(tmp_path)` with `tmp_path` fixture — operations are isolated from the real repository. Production code (`_install_skills_to_agents`) uses `Path.cwd()` at runtime (existing pattern, not modified by this issue). No branch-switching commands are invoked.
