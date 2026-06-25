---
title: "Product Layer Skill Scaffolding — `deviate setup` Creates /deviate-flows, /deviate-architecture, /deviate-release"
labels: [enhancement, adhoc, vertical-slice, product-layer]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-010
flow_refs: [FLOW-01, FLOW-02, FLOW-03]
---

## System Topology Mapping
- **Epic Target Domain**: `specs/_product/` (Product-layer staging directory; seed artifacts already present)
- **Local Issue File**: `specs/adhoc/issues/010-deviate-setup-product-layer.md`
- **Primary Architectural Workstations**:
  - `src/deviate/prompts/skills/deviate-flows/SKILL.md` — NEW: Product-layer skill template for FLOW-01
  - `src/deviate/prompts/skills/deviate-architecture/SKILL.md` — NEW: Product-layer skill template for FLOW-02
  - `src/deviate/prompts/skills/deviate-release/SKILL.md` — NEW: Product-layer skill template for FLOW-03
  - `src/deviate/cli/__init__.py:518-531` — `_install_skills_to_agents` (existing, untouched): discovers + copies skills to agent skills directories
  - `src/deviate/cli/__init__.py:555-627` — `setup` command (existing, untouched): already invokes `_install_skills_to_agents` at line 621
  - `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` — REFERENCE: canonical YAML frontmatter schema (`name:`, `description:`, `category:`, `version:`, `aliases:`)
  - `tests/cli/test_init.py` — extend with `test_init_creates_product_layer_skills` verifying the three new SKILL.md files exist and pass frontmatter validation
- **Upstream Evidence**:
  - `specs/explore/product-layer.md` — High-complexity classification, "Files Likely Modified" list, naming inconsistency between `/deviate-flow` (singular) and `/deviate-flows` (plural)
  - `specs/_product/release-next.md:26` — Authoritative acceptance criterion: "`deviate setup` will create new /deviate-flows, /deviate-architecture, and /deviate-release skills"
  - `specs/_product/flows/flows-product.md:1-94` — Canonical flow definitions FLOW-01/02/03 (all use plural `/deviate-flows`)
  - `specs/adhoc/prd.md` §`FR-ADHOC-010` — Appended functional requirement with AC-ADHOC-010-01 through AC-ADHOC-010-10

## The Problem Contract
The Product layer's three canonical flows (`FLOW-01 Flows`, `FLOW-02 Architecture`, `FLOW-03 Release`) are fully specified as seed artifacts at `specs/_product/flows/flows-product.md` and a release acceptance criterion at `specs/_product/release-next.md:26` mandates that `deviate setup` must create `/deviate-flows`, `/deviate-architecture`, and `/deviate-release` as discoverable agent skills. Today, the skill-installation path (`_install_skills_to_agents` → `discover_skills()` → `install_skill()` at `src/deviate/cli/__init__.py:518-531`) auto-installs whatever lives under `src/deviate/prompts/skills/` — so adding three new directories with `SKILL.md` files using the canonical frontmatter format established at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` is the minimal, agent-centric delivery path. The full Typer sub-app wiring (FLOW-01 → flow_app, FLOW-02 → architecture_app, FLOW-03 → release_app) and constitution v0.3.0 update are explicitly out of scope per `specs/_product/release-next.md` ("Minimal cli implementation. Keep it agent-centric") and deferred to a follow-up issue per `specs/explore/product-layer.md:154-159`.

**Forward-looking goal (deferred to a follow-up issue)**: Once the Product-layer convention is established, `deviate shard` and `deviate adhoc` should populate a `flow_refs` field in the frontmatter of every issue file they emit, mirroring the convention introduced in this issue (`flow_refs: [FLOW-01, FLOW-02, FLOW-03]` at `specs/adhoc/issues/010-deviate-setup-product-layer.md:9`). This enables downstream tooling (release planning, cross-epic traceability, flow-coverage audits) to query the issues ledger by flow ID without parsing the issue body. The follow-up issue will need to: (a) extend `IssueRecord` in `src/deviate/state/ledger.py` with an optional `flow_refs: list[str] = []` field, (b) update the `deviate-shard` skill at `src/deviate/prompts/skills/deviate-shard/SKILL.md` to instruct the agent to emit `flow_refs:` in each shard's frontmatter based on which Product-layer flows the FRs map to, (c) update the `deviate-adhoc` skill (and `src/deviate/cli/adhoc.py` if adhoc ever generates issue files directly) to accept a `--flow-ref FLOW-01,FLOW-02` flag and propagate it to the issue frontmatter, and (d) extend `validate_yaml_frontmatter` in `src/deviate/cli/macro.py:41` to recognize `flow_refs` as a known frontmatter key. This issue establishes the convention but does not implement the propagation path.

## Scope Boundaries
### Hard Inclusions
- Create `src/deviate/prompts/skills/deviate-flows/SKILL.md` with canonical frontmatter (`name: deviate-flows`, `description:` describing FLOW-01 flows definition, `category: deviatdd-product-layer`, `version: 1.0.0`, `aliases: [/deviate-flows, spec:flows]`). Body directs the agent to converse with the user to identify core customer flows, write to `specs/_product/flows/flows-<domain>.md`, and update `specs/_product/flows/index.md`. Source: `specs/_product/flows/flows-product.md:1-32` FLOW-01.
- Create `src/deviate/prompts/skills/deviate-architecture/SKILL.md` with canonical frontmatter (`name: deviate-architecture`, `description:` describing FLOW-02 cross-epic architecture, `category: deviatdd-product-layer`, `version: 1.0.0`, `aliases: [/deviate-architecture, spec:architecture]`). Body requires user flows to exist as precondition, directs the agent to produce/maintain `specs/_product/architecture.md` and `specs/_product/domain-model.md`, and applies a Local/Context-Bridging/Context-Creating classification. Source: `specs/_product/flows/flows-product.md:34-64` FLOW-02.
- Create `src/deviate/prompts/skills/deviate-release/SKILL.md` with canonical frontmatter (`name: deviate-release`, `description:` describing FLOW-03 release planning, `category: deviatdd-product-layer`, `version: 1.0.0`, `aliases: [/deviate-release, spec:release]`). Body requires architecture and flows to exist as preconditions, accepts a release-goal description, and writes/overrides `specs/_product/release-next.md`. Source: `specs/_product/flows/flows-product.md:66-94` FLOW-03.
- Resolve the naming inconsistency flagged at `specs/explore/product-layer.md:68` (singular `/deviate-flow` vs plural `/deviate-flows`). The canonical form is plural: `deviate-flows` (matches both `specs/_product/flows/flows-product.md:10,16` and the AC at `specs/_product/release-next.md:26`). Skill directory name: `src/deviate/prompts/skills/deviate-flows/`.
- Extend `tests/cli/test_init.py` with at least one new test (`test_init_creates_product_layer_skills`) that asserts all three SKILL.md files exist under `src/deviate/prompts/skills/`, parse correctly via the existing frontmatter schema, and contain the required fields.
- Verify end-to-end that `deviate setup --agent claude` against a temp workdir produces `.claude/skills/deviate-flows/SKILL.md`, `.claude/skills/deviate-architecture/SKILL.md`, `.claude/skills/deviate-release/SKILL.md` with byte-equal content to the source templates.

### Defensive Exclusions
- Do NOT register any new Typer sub-app (no `flow_app`, `architecture_app`, or `release_app` added to `src/deviate/cli/__init__.py`). The release-next.md constraint "Minimal cli implementation. Keep it agent-centric" (`specs/_product/release-next.md:7`) explicitly mandates this — agents invoke skills directly via `/deviate-flows` etc.
- Do NOT modify `_VALID_PHASES` at `src/deviate/state/config.py:21-39`, `_PHASE_ORDER` at `src/deviate/cli/macro.py:747`, or any state model. The Product layer operates above the Macro layer via agent skill invocation, not via the DeviaTDD phase registry.
- Do NOT update `specs/constitution.md` (remains at v0.2.0). Adding a fourth layer above the existing three-layer architecture is a constitutional change owned by the research phase (per `specs/explore/product-layer.md:154-159`). This issue is a deliverable that does not require a constitution bump.
- Do NOT update `specs/DeviaTDD-api.md` or `specs/DeviaTDD-architecture.md` in this issue. Spec alignment is part of the follow-up issue that wires the new layer into the CLI tree.
- Do NOT modify `_install_skills_to_agents` (`src/deviate/cli/__init__.py:518-531`), `discover_skills`, or `install_skill`. The existing skill-installation path is generic and treats all skills uniformly — adding three new directories is sufficient.
- Do NOT bundle LLM-specific behavior into the skill templates. Each SKILL.md is an agent instruction document, not a Python module. Prompt content lives in the SKILL.md body and references `specs/_product/flows/flows-product.md` + `specs/_product/release-next.md` as source-of-truth inputs.
- Do NOT regenerate `specs/_product/flows/flows-product.md` or `specs/_product/release-next.md`. These are user-authored seed artifacts — the SKILL.md bodies reference them as inputs.
- Do NOT add Graphite integration, libref config changes, or `[models]` config changes for these new skills. Default model routing applies (`opencode/deepseek-v4-flash` per `.deviate/config.toml`).
- Do NOT add CLI tests for `_install_skills_to_agents` end-to-end — extend `tests/cli/test_init.py` only with targeted frontmatter assertions on the source SKILL.md files (the existing init flow is already covered).
- Do NOT add tests that invoke `_run_pytest` from inside `runner.invoke(...)` without mocking `deviate.cli.micro._run_pytest` — per AGENTS.md mandate.
- Do NOT update `deviate shard` or `deviate adhoc` to emit `flow_refs` in the frontmatter of issues they create. The `flow_refs` field is established as a convention by this issue's own frontmatter (line 9); propagation across all issue-emitting paths is a forward-looking goal tracked in §`The Problem Contract` and deferred to a follow-up issue that touches `src/deviate/cli/macro.py:41` (`validate_yaml_frontmatter`), `src/deviate/cli/adhoc.py`, `src/deviate/prompts/skills/deviate-shard/SKILL.md`, and the `IssueRecord` schema in `src/deviate/state/ledger.py`.

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-010`
- **Acceptance Criteria Tokens**: `AC-ADHOC-010-01` through `AC-ADHOC-010-10`
- **Data Model Entities**: None new (no Pydantic models added; existing `DeviateConfig` and `SessionState` are untouched)
- **Spec Source Anchors**:
  - `specs/_product/release-next.md:26` — AC mandate
  - `specs/_product/flows/flows-product.md:1-94` — FLOW-01/02/03 definitions
  - `specs/explore/product-layer.md:129-147` — File registry (skill template format reference)
  - `src/deviate/cli/__init__.py:518-531` — Existing skill installation path
  - `src/deviate/cli/__init__.py:555-627` — Existing `setup` command

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **US-010-01**: As a DeviaTDD operator running `deviate setup` in a fresh workdir, I want the three Product-layer skill templates (`/deviate-flows`, `/deviate-architecture`, `/deviate-release`) automatically installed into my agent's skills directory so that I can invoke them with a slash command in my agent of choice without manually copying files. *(Ref: FR-ADHOC-010)*
- **US-010-02**: As a Product Architect defining cross-epic architecture, I want `/deviate-architecture` available as an agent skill so that I can use it from my existing agent workflow (claude/opencode/factory) to maintain `specs/_product/architecture.md` and `specs/_product/domain-model.md` without learning a new CLI invocation pattern. *(Ref: FR-ADHOC-010)*
- **US-010-03**: As a Release Manager planning the next coherent product release, I want `/deviate-release` available as an agent skill so that I can pass a release-goal description and have the agent update `specs/_product/release-next.md` as a guiding compass for downstream `/explore` invocations. *(Ref: FR-ADHOC-010)*
- **US-010-04**: As a DeviaTDD maintainer extending the framework, I want the three new Product-layer skills to flow through the existing `_install_skills_to_agents` path without any CLI changes so that the "minimal cli implementation, agent-centric" constraint (`specs/_product/release-next.md:7`) is upheld and the change surface stays minimal. *(Ref: FR-ADHOC-010)*

## ATDD Acceptance Criteria
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

**Scenario 010-01**: Three new Product-layer skill templates exist under `src/deviate/prompts/skills/`
**Given** the canonical skill frontmatter schema at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` (`name:`, `description:`, `category:`, `version:`, `aliases:`)
**When** `ls src/deviate/prompts/skills/deviate-flows/SKILL.md src/deviate/prompts/skills/deviate-architecture/SKILL.md src/deviate/prompts/skills/deviate-release/SKILL.md` is executed
**Then** all three files exist; each parses as valid YAML frontmatter; the `name:` field equals `deviate-flows`, `deviate-architecture`, `deviate-release` respectively; the `category:` field equals `deviatdd-product-layer` on each; the `version:` field equals `1.0.0` on each; the `aliases:` block contains the kebab-case slash-command (`/deviate-flows`, `/deviate-architecture`, `/deviate-release`) and the `spec:<skill>` invocation form.

**Scenario 010-02**: `discover_skills()` enumerates 23 skills after the three are added
**Given** the existing 20 skill directories under `src/deviate/prompts/skills/*/SKILL.md`
**When** `discover_skills()` is called after adding `deviate-flows`, `deviate-architecture`, `deviate-release`
**Then** the returned iterable contains exactly 23 skill names (the original 20 plus the three new ones); each new name appears once.

**Scenario 010-03**: `deviate setup --agent claude` installs the three skills into `.claude/skills/`
**Given** a fresh workdir with `.deviate/config.toml` setting `agent.backend = "claude"`
**When** `deviate setup` runs to completion
**Then** `workdir/.claude/skills/deviate-flows/SKILL.md`, `workdir/.claude/skills/deviate-architecture/SKILL.md`, and `workdir/.claude/skills/deviate-release/SKILL.md` exist; each is byte-equal to its source template under `src/deviate/prompts/skills/`.

**Scenario 010-04**: `deviate setup` is idempotent for the new Product-layer skills
**Given** a workdir where `.claude/skills/deviate-flows/SKILL.md` already exists (from a prior setup run)
**When** `deviate setup --agent claude` runs again
**Then** no errors are raised; the existing files are detected as present and skipped; the [yellow]SKIP[/] log line is emitted for each present skill (per existing `_install_skills_to_agents` skip logic at `src/deviate/cli/__init__.py:531`).

**Scenario 010-05**: `deviate setup --agent opencode` installs the three skills into `.opencode/skills/`
**Given** a fresh workdir with `.deviate/config.toml` setting `agent.backend = "opencode"`
**When** `deviate setup` runs to completion
**Then** `workdir/.opencode/skills/deviate-flows/SKILL.md`, `workdir/.opencode/skills/deviate-architecture/SKILL.md`, and `workdir/.opencode/skills/deviate-release/SKILL.md` exist with byte-equal content to source templates.

**Scenario 010-06**: `deviate-flows` skill body references FLOW-01 seed
**Given** the new `src/deviate/prompts/skills/deviate-flows/SKILL.md` body
**When** an agent invokes `/deviate-flows`
**Then** the prompt instructs the agent to (a) converse with the user to determine core customer flows, (b) reference `specs/_product/flows/flows-product.md` as the existing FLOW-01 seed to extend (not regenerate), (c) write new files under `specs/_product/flows/flows-<domain>.md`, (d) update `specs/_product/flows/index.md` per FLOW-01 Success State at `specs/_product/flows/flows-product.md:25-32`.

**Scenario 010-07**: `deviate-architecture` skill body references FLOW-02 preconditions
**Given** the new `src/deviate/prompts/skills/deviate-architecture/SKILL.md` body
**When** an agent invokes `/deviate-architecture`
**Then** the prompt (a) requires user flows to exist in `specs/_product/flows/` before invocation (per FLOW-02 Preconditions at `specs/_product/flows/flows-product.md:46-47`), (b) directs the agent to produce or maintain `specs/_product/architecture.md` and `specs/_product/domain-model.md` (per FLOW-02 Success State at `specs/_product/flows/flows-product.md:57-59`), (c) applies Local/Context-Bridging/Context-Creating classification to the change (per FLOW-02 Metrics at `specs/_product/flows/flows-product.md:63`).

**Scenario 010-08**: `deviate-release` skill body references FLOW-03 preconditions
**Given** the new `src/deviate/prompts/skills/deviate-release/SKILL.md` body
**When** an agent invokes `/deviate-release <release-goal-description>`
**Then** the prompt (a) requires architecture and flows to exist as preconditions (per FLOW-03 Preconditions at `specs/_product/flows/flows-product.md:77-79`), (b) accepts a release-goal description from the user, (c) writes or overrides `specs/_product/release-next.md` (per FLOW-03 Success State at `specs/_product/flows/flows-product.md:90-91`).

**Scenario 010-09**: No new Typer sub-app or phase is added
**Given** the bounded scope of this issue (skill scaffolding only)
**When** `git diff src/deviate/cli/__init__.py src/deviate/cli/_common.py src/deviate/state/config.py src/deviate/cli/macro.py` is computed post-implementation
**Then** no new `cli.add_typer(...)` calls are added; `_VALID_PHASES` is unchanged; `_PHASE_ORDER` is unchanged; the diff is empty.

**Scenario 010-10**: Constitution remains at v0.2.0
**Given** the constitution bump is deferred to a follow-up issue
**When** `head -5 specs/constitution.md` is read post-implementation
**Then** the version line still reads `Version: 0.2.0`; no §`Architectural Principles` modification has occurred.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **SKILL.md body references missing seed file**: If a SKILL.md prompt body references a seed file that does not exist (e.g., `specs/_product/flows/flows-product.md` is deleted), the skill still installs cleanly via the existing path — the failure surfaces at agent invocation time when the prompt template is loaded. The setup-time check does not validate seed-file presence; that responsibility belongs to the agent runtime.
- **Existing skill directory collision**: If `src/deviate/prompts/skills/deviate-flows/` already exists from a previous partial implementation, the new SKILL.md creation must not silently overwrite the prior content. The implementation must detect the existing directory and either update the SKILL.md deterministically (idempotent rewrite) or skip and emit a log line — adopt the idempotent-rewrite pattern matching the existing `_scaffold_constitution` skip-on-exists logic at `src/deviate/cli/__init__.py:495-497`.
- **Frontmatter field ordering**: The reference at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` orders fields as `name`, `description`, `category`, `version`, `aliases`. The three new SKILL.md files must use this same field order to maintain template uniformity — the existing `discover_skills()` parser (or any future parser) may be sensitive to field ordering.
- **YAML alias list format**: The reference uses a flat YAML list (`aliases:\n  - /deviate-constitution`). The three new skills must use the same flat-list format (not inline `[...]` syntax) for parser compatibility.
- **`category: deviatdd-product-layer`**: This is a new category value (existing categories observed: `deviatdd-macro-layer` at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:4`, `deviatdd-meso-layer`, `deviatdd-micro-layer`). No downstream consumer filters on `category:` today, so introducing a new category is safe — but the value must be lowercase, hyphenated, and consistent across all three new skills.
- **Long description strings**: YAML frontmatter `description:` values must be single-line (no embedded newlines) to parse correctly with `yaml.safe_load`. Multi-sentence descriptions are allowed but must use single-line string format.
- **Skill body length**: Each SKILL.md body is a long prompt document (the existing `deviate-constitution` skill body is ~215 lines per the file read). Three new skills at similar length is acceptable — total addition ~600 lines of prompt content under `src/deviate/prompts/skills/`. No content-length guardrail required.
- **Re-running setup on a populated workdir**: Idempotent installation is guaranteed by the existing `_install_skills_to_agents` logic at `src/deviate/cli/__init__.py:518-531`. The three new skills inherit this idempotency without modification.
- **Missing or malformed `version:` field**: `discover_skills()` may or may not validate the `version:` field. The new SKILL.md files must declare `version: 1.0.0` explicitly to match the reference at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:5`.
- **Agent platform not in `_get_agent_skill_dir`**: The existing helper at `src/deviate/cli/__init__.py:508-515` returns `None` for unknown agents and the install flow emits `[yellow]SKIP[/] Unknown agent: <name>` at line 525. The three new skills inherit this skip behavior without modification — unknown agents simply do not get the skills installed.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **L_max (deviate setup cold)**: ≤ 500ms total (existing `deviate setup` performance gate at `AGENTS.md`; three additional SKILL.md copies add < 50ms combined on macOS/Linux filesystem)
- **L_max (single SKILL.md copy)**: ≤ 10ms per file on macOS ext4/apfs (3 files × 10ms = 30ms worst-case added overhead)
- **L_max (frontmatter parse in test)**: ≤ 5ms per file via `yaml.safe_load` (3 files × 5ms = 15ms test overhead)
- **Throughput**: `discover_skills()` enumeration of 23 skills (was 20) must complete in ≤ 5ms (existing benchmark for 20 skills; 3-skill addition is negligible)
- **Test suite budget**: Re-running `mise run test tests/cli/test_init.py::test_init_creates_product_layer_skills -v` completes in < 5s (single-test invocation); full suite `mise run test` remains < 18s per AGENTS.md performance mandate
- **Lint budget**: `mise run lint` (ruff check) reports zero violations on the three new SKILL.md files and the new test function — SKILL.md files are Markdown and typically not ruff-scanned, but the test function must pass ruff's default Python rules
- **File size**: Each new SKILL.md ≤ 10KB (matches the reference deviate-constitution skill at ~6KB); total addition across three files ≤ 30KB
- **Idempotency cost**: Re-running `deviate setup` on a populated workdir completes in ≤ 200ms (existing idempotent-skip path is O(skills) with filesystem stat only, no copy)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/cli/test_init.py::test_init_creates_product_layer_skills` — assert all three new SKILL.md files exist under `src/deviate/prompts/skills/`, parse as valid YAML frontmatter, carry `name:` matching directory name, carry `category: deviatdd-product-layer`, carry `version: 1.0.0`, and include slash-command aliases
  - `tests/cli/test_init.py::test_init_product_layer_skills_idempotent` — re-run `deviate setup` against a workdir where the three SKILL.md files are already installed; assert no errors, no duplicate files, `[yellow]SKIP[/]` log lines emitted for each present skill
  - `tests/cli/test_init.py::test_init_discover_skills_enumerates_product_layer` — call `discover_skills()` post-implementation; assert it returns 23 names including `deviate-flows`, `deviate-architecture`, `deviate-release`
- **Integration Sandbox Targets**:
  - `tests/cli/test_init_export_cycle.py` — full setup cycle with `--agent claude` against a temp workdir; assert `.claude/skills/deviate-flows/SKILL.md` etc. exist with byte-equal content to source templates
  - `tests/cli/test_init_export_cycle.py` — full setup cycle with `--agent opencode`; assert `.opencode/skills/deviate-flows/SKILL.md` etc. exist with byte-equal content

## Demonstration Path
```bash
# 1. Verify the three new skill templates exist in source tree
ls src/deviate/prompts/skills/deviate-flows/SKILL.md \
   src/deviate/prompts/skills/deviate-architecture/SKILL.md \
   src/deviate/prompts/skills/deviate-release/SKILL.md

# 2. Verify frontmatter parses correctly
uv run python -c "
import yaml, pathlib
for name in ['deviate-flows', 'deviate-architecture', 'deviate-release']:
    text = pathlib.Path(f'src/deviate/prompts/skills/{name}/SKILL.md').read_text()
    fm = yaml.safe_load(text.split('---')[1])
    assert fm['name'] == name, f'{name}: name mismatch'
    assert fm['category'] == 'deviatdd-product-layer', f'{name}: category mismatch'
    assert fm['version'] == '1.0.0', f'{name}: version mismatch'
    print(f'  [OK] {name} frontmatter valid')
"

# 3. Run the new unit tests
mise run test tests/cli/test_init.py::test_init_creates_product_layer_skills -v
mise run test tests/cli/test_init.py::test_init_product_layer_skills_idempotent -v
mise run test tests/cli/test_init.py::test_init_discover_skills_enumerates_product_layer -v

# 4. Run the full init + export cycle integration test
mise run test tests/cli/test_init_export_cycle.py -v

# 5. Manual smoke test: run deviate setup in a temp workdir
tmpdir=$(mktemp -d)
cd "$tmpdir"
git init -q && git config user.email "test@test" && git config user.name "Test"
uv run --project /Users/werner/Projects/tools/deviatdd deviate setup --agent claude
ls -la .claude/skills/deviate-flows/ .claude/skills/deviate-architecture/ .claude/skills/deviate-release/

# 6. Verify byte-equal content between source and installed
diff src/deviate/prompts/skills/deviate-flows/SKILL.md .claude/skills/deviate-flows/SKILL.md
diff src/deviate/prompts/skills/deviate-architecture/SKILL.md .claude/skills/deviate-architecture/SKILL.md
diff src/deviate/prompts/skills/deviate-release/SKILL.md .claude/skills/deviate-release/SKILL.md

# 7. Lint and format check
mise run lint
mise run format-check
```