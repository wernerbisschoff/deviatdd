---
title: "Tome Subsystem v1 — Seven Prompt-Only Diátaxis Curation Skills"
labels: [enhancement, adhoc, vertical-slice, tome, documentation, diataxis]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-011
flow_refs: [FLOW-04, FLOW-05, FLOW-06, FLOW-07, FLOW-08, FLOW-09, FLOW-10]
---

## System Topology Mapping
- **Epic Target Domain**: `specs/_product/` (Product-layer artifacts already present: `architecture.md`, `domain-model.md`, `release-next.md`, `flows/flows-tome.md`)
- **Local Issue File**: `specs/adhoc/issues/011-tome-subsystem-v1.md`
- **Primary Architectural Workstations**:
  - `src/deviate/prompts/skills/tome-classify/SKILL.md` — NEW: C1 classifier (FLOW-04) — ingests commit/branch evidence, emits classification report
  - `src/deviate/prompts/skills/tome-write-tutorial/SKILL.md` — NEW: C2 writer (FLOW-05) — confined to `apps/docs/src/content/docs/tutorials/`
  - `src/deviate/prompts/skills/tome-write-how-to/SKILL.md` — NEW: C3 writer (FLOW-06) — confined to `apps/docs/src/content/docs/how-to/`
  - `src/deviate/prompts/skills/tome-write-reference/SKILL.md` — NEW: C4 writer (FLOW-07) — confined to `apps/docs/src/content/docs/reference/`
  - `src/deviate/prompts/skills/tome-write-explanation/SKILL.md` — NEW: C5 writer (FLOW-08) — confined to `apps/docs/src/content/docs/explanation/`
  - `src/deviate/prompts/skills/tome-verify-docs/SKILL.md` — NEW: C6 verifier (FLOW-09) — cross-doc pass, read-only report
  - `src/deviate/prompts/skills/tome-setup/SKILL.md` — NEW: C7 setup (FLOW-10) — idempotent Starlight + quadrant scaffold
  - `tests/cli/test_init.py` — extend with `test_init_creates_tome_skills` verifying all seven SKILL.md files exist and pass frontmatter validation
- **Upstream Evidence**:
  - `specs/explore/tome-subsystem.md` — Source explore scan (Status: SUCCESS, Complexity: Medium, Files Likely Modified: 7 new SKILL.md files)
  - `specs/_product/architecture.md:25-33` — 7 components C1-C7 with skill paths, flow refs, integration contracts
  - `specs/_product/architecture.md:38-82` — C1 input modes, C2-C5 quadrant rule, inlined frontmatter schema
  - `specs/_product/flows/flows-tome.md:1-278` — FLOW-04..FLOW-10 (Actor, Domain, Trigger, Preconditions, Happy Path, Alternate paths, Success State)
  - `specs/_product/domain-model.md` — 9 entities (Commit, ClassificationReport, Capability, DocType, Action, DocPage, TomeFrontmatter, VerificationReport, StarlightQuadrant)
  - `specs/_product/release-next.md` — 10 ACs for the Tome release; release plan mandates 7 prompt-only skills
  - `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` — Reference: canonical YAML frontmatter schema (`name:`, `description:`, `category:`, `version:`, `aliases:`)
  - `src/deviate/cli/__init__.py:518-531` — Existing skill installation path `_install_skills_to_agents` (untouched)
  - `specs/adhoc/prd.md` §`FR-ADHOC-011` — Appended functional requirement with AC-ADHOC-011-01 through AC-ADHOC-011-10

## The Problem Contract
The Tome Subsystem is a manual post-merge documentation curator for Starlight docs sites that classifies a commit (or a branch-level diff) against the four Diátaxis quadrants and runs only the writer skills the classifier selects. The release plan at `specs/_product/release-next.md` mandates seven prompt-only skills (no Python runtime, no `deviate tome <phase>` CLI surface) — one per component C1-C7 declared in `specs/_product/architecture.md:25-33`. v1 ships pure-prompt and gathers usage data before any deterministic-enforcement iteration. The seven skills form one coherent release slice: the classifier (C1) gates which of the four quadrant writers (C2-C5) run, the verifier (C6) performs a cross-doc pass after writers complete, and the setup skill (C7) bootstraps the Starlight `apps/docs/` site when `apps/docs/` is absent. Each new SKILL.md uses a new `category: deviatdd-tome-layer` to distinguish the documentation-curation layer from the existing macro/meso/micro/product layers, and inlines the schemas, action enums, gate behaviors, and quadrant rules declared in the Product-layer artifacts — there is no shared `tome/contracts.py` module in v1 per `specs/_product/architecture.md:19`. The existing skill installation path `_install_skills_to_agents` at `src/deviate/cli/__init__.py:518-531` is generic and treats all skills uniformly, so adding seven new directories with `SKILL.md` files using the canonical frontmatter format is the minimal, agent-centric delivery path. The release's 10 acceptance criteria (per `specs/_product/release-next.md`) and the seven flows FLOW-04..FLOW-10 (per `specs/_product/flows/flows-tome.md`) trace through this issue as `flow_refs: [FLOW-04, FLOW-05, FLOW-06, FLOW-07, FLOW-08, FLOW-09, FLOW-10]` in both the issue frontmatter and the `ISS-ADH-011` ledger entry.

## Scope Boundaries
### Hard Inclusions
- Create `src/deviate/prompts/skills/tome-classify/SKILL.md` with canonical frontmatter (`name: tome-classify`, `description:` describing FLOW-04 classifier behavior, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-classify, spec:tome-classify]`). Body inlines the four input modes (default HEAD~1, `<sha>`, `--merge-base`, `--working-tree`), the action enum (`create`, `update`, `no-change`, `human-review`, `setup-required`), the gate behaviors (`no-change` skips writers + verifier; `human-review` blocks writers; `setup-required` halts and points at FLOW-10), and the classification report schema (change summary, capability table with `capability/evidence/audience/doc_type/action/target_file/confidence`, no-touch list). Source: `specs/_product/architecture.md:38-56` C1 + `specs/_product/flows/flows-tome.md:1-47` FLOW-04.
- Create `src/deviate/prompts/skills/tome-write-tutorial/SKILL.md` with canonical frontmatter (`name: tome-write-tutorial`, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-write-tutorial, spec:tome-write-tutorial]`). Body inlines the C2 quadrant rule (writes only to `apps/docs/src/content/docs/tutorials/`), the frontmatter schema, the tutorial-style register (one happy path, concrete expected results at each step, beginner-safe), and the boundary-violation rejection rule (target outside `tutorials/` → reject + surface violation). Source: `specs/_product/architecture.md:60-82` C2 + `specs/_product/flows/flows-tome.md:49-85` FLOW-05.
- Create `src/deviate/prompts/skills/tome-write-how-to/SKILL.md` with canonical frontmatter (`name: tome-write-how-to`, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-write-how-to, spec:tome-write-how-to]`). Body inlines the C3 quadrant rule (writes only to `apps/docs/src/content/docs/how-to/`), the how-to register (prerequisites, exact steps, verification, troubleshooting for one operator/contributor task), and the cross-type downgrade rule (explanation-style content → flag back to FLOW-04 for re-classification to FLOW-08). Source: `specs/_product/architecture.md:60-82` C3 + `specs/_product/flows/flows-tome.md:87-123` FLOW-06.
- Create `src/deviate/prompts/skills/tome-write-reference/SKILL.md` with canonical frontmatter (`name: tome-write-reference`, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-write-reference, spec:tome-write-reference]`). Body inlines the C4 quadrant rule (writes only to `apps/docs/src/content/docs/reference/`), the reference register (factual, skimmable, tables for flags/fields/commands/defaults/constraints), and the cross-type downgrade rule (tutorial-style narrative → flag back to FLOW-04 for re-classification to FLOW-05). Source: `specs/_product/architecture.md:60-82` C4 + `specs/_product/flows/flows-tome.md:125-161` FLOW-07.
- Create `src/deviate/prompts/skills/tome-write-explanation/SKILL.md` with canonical frontmatter (`name: tome-write-explanation`, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-write-explanation, spec:tome-write-explanation]`). Body inlines the C5 quadrant rule (writes only to `apps/docs/src/content/docs/explanation/`), the explanation register (rationale, mental model, trade-offs, architectural meaning), and the cross-type downgrade rule (step-by-step instructions → flag back to FLOW-04 for re-classification to FLOW-06). Source: `specs/_product/architecture.md:60-82` C5 + `specs/_product/flows/flows-tome.md:163-199` FLOW-08.
- Create `src/deviate/prompts/skills/tome-verify-docs/SKILL.md` with canonical frontmatter (`name: tome-verify-docs`, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-verify-docs, spec:tome-verify-docs]`). Body inlines the C6 verifier checks (factual consistency vs commit diff + changed tests; path correctness vs Starlight content tree; command/config/API accuracy; no cross-type contamination; valid Starlight location), the PASS/FAIL/human-review emit format, and the recommended-files-to-commit summary. Source: `specs/_product/architecture.md:32` C6 + `specs/_product/flows/flows-tome.md:201-238` FLOW-09.
- Create `src/deviate/prompts/skills/tome-setup/SKILL.md` with canonical frontmatter (`name: tome-setup`, `category: deviatdd-tome-layer`, `version: 1.0.0`, `aliases: [/tome-setup, spec:tome-setup]`). Body inlines the C7 idempotent bootstrap contract: scaffold `apps/docs/` with Starlight; create the four quadrant directories under `apps/docs/src/content/docs/` plus `index.md` and `_meta/`; add `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`); seed a starter set (one explanation, one reference, one how-to, one tutorial); skip-no-op if `apps/docs/` already exists. Source: `specs/_product/architecture.md:33` C7 + `specs/_product/flows/flows-tome.md:240-278` FLOW-10.
- All seven SKILL.md files use the canonical frontmatter field order (`name`, `description`, `category`, `version`, `aliases`) established at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` and a flat YAML list for aliases (not inline `[...]` syntax) for parser compatibility.
- Extend `tests/cli/test_init.py` with at least one new test (`test_init_creates_tome_skills`) that asserts all seven SKILL.md files exist under `src/deviate/prompts/skills/tome-*/`, parse correctly via the existing frontmatter schema, carry `category: deviatdd-tome-layer`, carry `version: 1.0.0`, and include the slash-command aliases.
- Verify end-to-end that `deviate setup --agent claude` against a fresh temp workdir produces `.claude/skills/tome-{classify,write-tutorial,write-how-to,write-reference,write-explanation,verify-docs,setup}/SKILL.md` with byte-equal content to the source templates.

### Defensive Exclusions
- Do NOT add any Python module. v1 is prompt-only per `specs/_product/architecture.md:17`. No `src/deviate/tome/`, no `tome/contracts.py`, no `src/deviate/cli/tome.py`.
- Do NOT register a `deviate tome <phase>` Typer sub-app. The v1 deferred-CLI decision at `specs/_product/architecture.md:21` is explicit: a future iteration may add a Typer sub-app, but not now.
- Do NOT modify `_VALID_PHASES` (`src/deviate/state/config.py:21-39`), `_PHASE_ORDER` (`src/deviate/cli/macro.py:747`), or any state model. The Tome layer operates via agent skill invocation, not via the DeviaTDD phase registry.
- Do NOT update `specs/constitution.md` (remains at v0.2.0). Adding a fifth layer (tome) above the existing three-layer architecture is a constitutional change owned by a follow-up research-phase issue, not this additive skill-scaffolding work.
- Do NOT update `specs/DeviaTDD-api.md` or `specs/DeviaTDD-architecture.md` in this issue. The Product-layer architecture.md is the source of truth for Tome; the framework-level architecture docs remain unchanged in v1.
- Do NOT modify `_install_skills_to_agents` (`src/deviate/cli/__init__.py:518-531`), `discover_skills`, or `install_skill`. The existing skill installation path is generic and treats all skills uniformly — adding seven new directories is sufficient.
- Do NOT bundle LLM-specific behavior into the skill templates. Each SKILL.md is an agent instruction document, not a Python module. Prompt content lives in the SKILL.md body and references `specs/_product/architecture.md`, `flows-tome.md`, and `domain-model.md` as source-of-truth inputs.
- Do NOT regenerate `specs/_product/architecture.md`, `specs/_product/flows/flows-tome.md`, `specs/_product/domain-model.md`, or `specs/_product/release-next.md`. These are user-authored seed artifacts — the SKILL.md bodies reference them as inputs.
- Do NOT upgrade `src/deviate/prompts/skills/deviate-flows/SKILL.md`, `deviate-architecture/SKILL.md`, or `deviate-release/SKILL.md` in this issue. Those Product-layer skills are scoped to FLOW-01/02/03 (per FR-ADHOC-010); the Tome skills are a separate layer (FLOW-04..FLOW-10) and don't require consumer-side upgrades in v1.
- Do NOT extend `IssueRecord`, `AdhocRecord`, or `validate_yaml_frontmatter` for Tome-specific fields. The existing `flow_refs: list[str] = Field(default_factory=list)` field on `IssueRecord` (added by FR-ADHOC-010) is sufficient to carry `[FLOW-04..FLOW-10]` — no schema change needed.
- Do NOT add Graphite integration, libref config changes, or `[models]` config changes for these new skills. Default model routing applies (`opencode/deepseek-v4-flash` per `.deviate/config.toml`).
- Do NOT add CLI tests for `_install_skills_to_agents` end-to-end — extend `tests/cli/test_init.py` only with targeted frontmatter assertions on the source SKILL.md files (the existing init flow is already covered).
- Do NOT add tests that invoke `_run_pytest` from inside `runner.invoke(...)` without mocking `deviate.cli.micro._run_pytest` — per AGENTS.md mandate.
- Do NOT create `apps/docs/` in this repo. The setup skill (C7) targets `apps/docs/` in *target repos* that consume the skills, not in DeviaTDD's own repo (per `specs/_product/architecture.md:18`).

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-011`
- **Acceptance Criteria Tokens**: `AC-ADHOC-011-01` through `AC-ADHOC-011-10`
- **Data Model Entities** (referenced by skills, not implemented in v1): `Commit`, `ClassificationReport`, `Capability`, `DocType`, `Action`, `DocPage`, `TomeFrontmatter`, `VerificationReport`, `StarlightQuadrant` (per `specs/_product/domain-model.md`)
- **Spec Source Anchors**:
  - `specs/_product/architecture.md:25-33` — 7 components C1-C7 with skill paths, flow refs, integration contracts
  - `specs/_product/architecture.md:38-82` — C1 input modes, C2-C5 quadrant rule, inlined frontmatter schema
  - `specs/_product/flows/flows-tome.md:1-278` — FLOW-04..FLOW-10 happy paths + alternate paths + success states
  - `specs/explore/tome-subsystem.md` — Source explore scan (Medium complexity, 7 same-kind files)
  - `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` — Reference frontmatter schema
  - `src/deviate/cli/__init__.py:518-531` — Existing skill installation path

## User Stories Ledger
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **US-011-01**: As a developer who just merged a commit touching a public API, I want `/tome-classify` to read the diff and emit a classification report naming the Diátaxis doc types required so I know which writers to invoke without re-reading the diff myself. *(Ref: FR-ADHOC-011)*
- **US-011-02**: As a developer running `/tome-classify --merge-base` before opening a PR, I want the report to scope to the cumulative change set from main to HEAD so I can prepare docs for the entire branch in one pass. *(Ref: FR-ADHOC-011)*
- **US-011-03**: As a developer invoking `/tome-write-tutorial`, `/tome-write-how-to`, `/tome-write-reference`, or `/tome-write-explanation` after the classifier report, I want each writer confined to its own quadrant directory (`tutorials/`, `how-to/`, `reference/`, `explanation/`) and to reject out-of-quadrant target paths so cross-type contamination cannot enter the docs tree. *(Ref: FR-ADHOC-011)*
- **US-011-04**: As a developer running `/tome-verify-docs` after writers complete, I want a verifier report surfacing factual inconsistencies, path mistakes, frontmatter schema violations, and cross-type contamination so I can fix failing files before merge. *(Ref: FR-ADHOC-011)*
- **US-011-05**: As a developer running `/tome-setup` for the first time in a target repo, I want the Starlight scaffold + four quadrant directories + `content.config.ts` + starter set materialized idempotently so FLOW-04 can resolve target paths on first invocation. *(Ref: FR-ADHOC-011)*
- **US-011-06**: As a DeviaTDD maintainer extending the framework, I want the seven new Tome skills to flow through the existing `_install_skills_to_agents` path without any CLI changes so the change surface stays minimal and the prompt-only constraint (`specs/_product/architecture.md:17`) is upheld. *(Ref: FR-ADHOC-011)*
- **US-011-07**: As a docs consumer browsing the target repo, I want every doc page to carry valid Tome frontmatter (`title`, `description`, `doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`) so I can filter docs by quadrant and check freshness at a glance. *(Ref: FR-ADHOC-011)*

## ATDD Acceptance Criteria
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

**Scenario 011-01**: Seven new Tome skill templates exist under `src/deviate/prompts/skills/`
**Given** the canonical skill frontmatter schema at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` (`name:`, `description:`, `category:`, `version:`, `aliases:`)
**When** `ls src/deviate/prompts/skills/tome-classify/SKILL.md src/deviate/prompts/skills/tome-write-tutorial/SKILL.md src/deviate/prompts/skills/tome-write-how-to/SKILL.md src/deviate/prompts/skills/tome-write-reference/SKILL.md src/deviate/prompts/skills/tome-write-explanation/SKILL.md src/deviate/prompts/skills/tome-verify-docs/SKILL.md src/deviate/prompts/skills/tome-setup/SKILL.md` is executed
**Then** all seven files exist; each parses as valid YAML frontmatter; the `name:` field equals `tome-classify`, `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation`, `tome-verify-docs`, `tome-setup` respectively; the `category:` field equals `deviatdd-tome-layer` on each; the `version:` field equals `1.0.0` on each; the `aliases:` block contains the kebab-case slash-command (`/tome-classify`, etc.) and the `spec:tome-<skill>` invocation form.

**Scenario 011-02**: `tome-classify` body inlines C1 input modes and action enum
**Given** the C1 input modes and gate behaviors at `specs/_product/architecture.md:38-56`
**When** `src/deviate/prompts/skills/tome-classify/SKILL.md` body is read
**Then** it contains sections inlining: (a) the four input modes (default HEAD~1, `<sha>`, `--merge-base`, `--working-tree`), (b) the action enum (`create`, `update`, `no-change`, `human-review`, `setup-required`), (c) the gate behaviors for `no-change` (skip writers + verifier), `human-review` (block writers), and `setup-required` (halt + point at FLOW-10), and (d) the classification report schema (change summary, capability table with `capability/evidence/audience/doc_type/action/target_file/confidence`, no-touch list).

**Scenario 011-03**: Each writer skill rejects out-of-quadrant target paths
**Given** the strict quadrant rule at `specs/_product/architecture.md:64`
**When** any of `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation` is invoked with a target file path outside its quadrant directory
**Then** the prompt instructs the agent to reject the write, surface a boundary violation, and flag back to FLOW-04 for re-classification.

**Scenario 011-04**: Each writer skill inlines the frontmatter schema
**Given** the frontmatter schema at `specs/_product/architecture.md:71-82`
**When** any writer prompt runs
**Then** it instructs the agent to emit full markdown with all seven frontmatter fields (`title`, `description`, `doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`) and to set `doc_type:` to `tutorial`, `how-to`, `reference`, or `explanation` matching the writer's quadrant.

**Scenario 011-05**: `tome-verify-docs` body inlines C6 verifier checks
**Given** the C6 verifier responsibilities at `specs/_product/architecture.md:32` and `specs/_product/flows/flows-tome.md:201-238`
**When** `src/deviate/prompts/skills/tome-verify-docs/SKILL.md` body is read
**Then** it contains sections inlining: (a) the verifier checks (factual consistency vs commit diff + changed tests; path correctness vs Starlight content tree; command/config/API accuracy; no cross-type contamination; valid Starlight location), (b) the PASS/FAIL/human-review emit format, and (c) the recommended-files-to-commit summary.

**Scenario 011-06**: `tome-setup` body inlines C7 idempotent bootstrap contract
**Given** the C7 bootstrap contract at `specs/_product/flows/flows-tome.md:240-278`
**When** `src/deviate/prompts/skills/tome-setup/SKILL.md` body is read
**Then** it instructs the agent to (a) scaffold `apps/docs/` with Starlight, (b) create four quadrant directories under `apps/docs/src/content/docs/` plus `index.md` and `_meta/`, (c) add `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`), (d) seed a starter set (one explanation, one reference, one how-to, one tutorial), and (e) skip-no-op if `apps/docs/` already exists.

**Scenario 011-07**: v1 prompt-only constraint upheld — no Python modules added
**Given** the v1 prompt-only constraint at `specs/_product/architecture.md:17`
**When** `git diff src/deviate/` is computed post-implementation
**Then** no new Python modules are added (no `src/deviate/tome/`, no `tome/contracts.py`, no `src/deviate/cli/tome.py`); no new Typer sub-app is registered (`grep -r "cli.add_typer" src/deviate/cli/__init__.py` shows no new lines); no new phase appears in `_VALID_PHASES` (`src/deviate/state/config.py:21-39`) or `_PHASE_ORDER` (`src/deviate/cli/macro.py:747`).

**Scenario 011-08**: `discover_skills()` enumerates 30 skills post-implementation
**Given** the existing 23 skill directories under `src/deviate/prompts/skills/*/SKILL.md` (20 base + 3 Product-layer per FR-ADHOC-010)
**When** `discover_skills()` is called after adding the seven Tome skills
**Then** the returned iterable contains exactly 30 skill names; each Tome name (`tome-classify`, `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation`, `tome-verify-docs`, `tome-setup`) appears once.

**Scenario 011-09**: `deviate setup --agent claude` installs the seven Tome skills
**Given** a fresh workdir with `.deviate/config.toml` setting `agent.backend = "claude"`
**When** `deviate setup` runs to completion
**Then** `workdir/.claude/skills/tome-classify/SKILL.md`, `workdir/.claude/skills/tome-write-tutorial/SKILL.md`, `workdir/.claude/skills/tome-write-how-to/SKILL.md`, `workdir/.claude/skills/tome-write-reference/SKILL.md`, `workdir/.claude/skills/tome-write-explanation/SKILL.md`, `workdir/.claude/skills/tome-verify-docs/SKILL.md`, and `workdir/.claude/skills/tome-setup/SKILL.md` exist; each is byte-equal to its source template under `src/deviate/prompts/skills/`.

**Scenario 011-10**: New unit test verifies all seven Tome SKILL.md files exist
**Given** the existing `tests/cli/test_init.py` test file
**When** `pytest tests/cli/test_init.py::test_init_creates_tome_skills -v` runs
**Then** the test asserts all seven Tome SKILL.md files exist, parse as valid YAML frontmatter, carry `category: deviatdd-tome-layer`, carry `version: 1.0.0`, and include slash-command aliases; the test completes in < 1s; full suite `mise run test` remains < 18s; `mise run lint` reports zero ruff violations on the new test.

**Scenario 011-11**: Constitution remains at v0.2.0
**Given** the constitution bump is deferred to a follow-up research-phase issue
**When** `head -5 specs/constitution.md` is read post-implementation
**Then** the version line still reads `Version: 0.2.0`; no §`Architectural Principles` modification has occurred.

**Scenario 011-12**: Issue registered in `specs/issues.jsonl` with `flow_refs: [FLOW-04..FLOW-10]`
**Given** the `ISS-ADH-011` ledger record appended at implementation time
**When** `tail -1 specs/issues.jsonl | python -c "import json,sys; print(json.loads(sys.stdin.read()))"` runs
**Then** the JSONL line parses; `issue_id` equals `ISS-ADH-011`; `type` equals `adhoc`; `flow_refs` equals `[FLOW-04, FLOW-05, FLOW-06, FLOW-07, FLOW-08, FLOW-09, FLOW-10]`; `source_file` equals `specs/adhoc/issues/011-tome-subsystem-v1.md`; `status` equals `BACKLOG`.

## Edge Cases and Boundaries
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **SKILL.md body references missing seed file**: If a SKILL.md prompt body references a seed file that does not exist (e.g., `specs/_product/architecture.md` is deleted), the skill still installs cleanly via the existing `_install_skills_to_agents` path — the failure surfaces at agent invocation time when the prompt template is loaded. Setup-time checks do not validate seed-file presence; that responsibility belongs to the agent runtime.
- **Existing skill directory collision**: If `src/deviate/prompts/skills/tome-classify/` already exists from a previous partial implementation, the new SKILL.md creation must not silently overwrite prior content. The implementation must detect the existing directory and either update the SKILL.md deterministically (idempotent rewrite) or skip and emit a log line — adopt the idempotent-rewrite pattern matching the existing `_scaffold_constitution` skip-on-exists logic at `src/deviate/cli/__init__.py:495-497`.
- **Frontmatter field ordering**: The reference at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` orders fields as `name`, `description`, `category`, `version`, `aliases`. The seven new SKILL.md files must use this same field order to maintain template uniformity — the existing `discover_skills()` parser (or any future parser) may be sensitive to field ordering.
- **YAML alias list format**: The reference uses a flat YAML list (`aliases:\n  - /deviate-constitution`). The seven new skills must use the same flat-list format (not inline `[...]` syntax) for parser compatibility.
- **`category: deviatdd-tome-layer`**: This is a new category value (existing categories observed: `deviatdd-macro-layer` at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:4`, `deviatdd-meso-layer`, `deviatdd-micro-layer`, `deviatdd-product-layer` at FR-ADHOC-010). No downstream consumer filters on `category:` today, so introducing a new category is safe — but the value must be lowercase, hyphenated, and consistent across all seven new skills.
- **Long description strings**: YAML frontmatter `description:` values must be single-line (no embedded newlines) to parse correctly with `yaml.safe_load`. Multi-sentence descriptions are allowed but must use single-line string format.
- **Skill body length**: Each SKILL.md body is a long prompt document (the existing `deviate-constitution` skill body is ~215 lines per the file read, and `deviate-flows/SKILL.md` is comparable). Seven new skills at similar length is acceptable — total addition ~1500 lines of prompt content under `src/deviate/prompts/skills/`. No content-length guardrail required.
- **Quadrant directory naming**: The four quadrant directories under `apps/docs/src/content/docs/` use kebab-case plural forms (`tutorials/`, `how-to/`, `reference/`, `explanation/`). The writer prompts must hardcode these exact directory names — drift between writer prompts and the C7 setup-created dirs is a C6 verifier finding.
- **Action enum consistency**: The five action values (`create`, `update`, `no-change`, `human-review`, `setup-required`) are inlined in C1's prompt. The verifier (C6) and writers (C2-C5) must reference the same enum string-by-string — drift between C1 and C2-C6 prompts is a verifier-level finding.
- **Frontmatter field set consistency**: All seven frontmatter fields (`title`, `description`, `doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`) are inlined in every writer prompt. The C7 setup prompt must declare the same field set when extending `docsSchema()` — drift between writer prompts and `content.config.ts` is a Starlight-side validation failure.
- **Re-running setup on a populated workdir**: Idempotent installation is guaranteed by the existing `_install_skills_to_agents` logic at `src/deviate/cli/__init__.py:518-531`. The seven new skills inherit this idempotency without modification.
- **Missing or malformed `version:` field**: `discover_skills()` may or may not validate the `version:` field. The new SKILL.md files must declare `version: 1.0.0` explicitly to match the reference at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:5`.
- **Agent platform not in `_get_agent_skill_dir`**: The existing helper at `src/deviate/cli/__init__.py:508-515` returns `None` for unknown agents and the install flow emits `[yellow]SKIP[/] Unknown agent: <name>` at line 525. The seven new skills inherit this skip behavior without modification — unknown agents simply do not get the skills installed.
- **Existing in-progress modification to `deviate-flows/SKILL.md`**: A pre-existing uncommitted modification to `src/deviate/prompts/skills/deviate-flows/SKILL.md` is observed at session start (`git status` shows ` M src/deviate/prompts/skills/deviate-flows/SKILL.md`). This modification is unrelated to the Tome Subsystem and must NOT be touched by this issue — it belongs to a separate in-progress workstream.

## Performance Constraints
<!-- Canonical format reference: src/deviate/prompts/skills/deviate-shard/SKILL.md -->

- **L_max (deviate setup cold)**: ≤ 500ms total (existing `deviate setup` performance gate at `AGENTS.md`; seven additional SKILL.md copies add < 120ms combined on macOS/Linux filesystem)
- **L_max (single SKILL.md copy)**: ≤ 10ms per file on macOS ext4/apfs (7 files × 10ms = 70ms worst-case added overhead)
- **L_max (frontmatter parse in test)**: ≤ 5ms per file via `yaml.safe_load` (7 files × 5ms = 35ms test overhead)
- **Throughput**: `discover_skills()` enumeration of 30 skills (was 23) must complete in ≤ 8ms (existing benchmark for 23 skills at ~5ms; 7-skill addition is negligible)
- **Test suite budget**: Re-running `mise run test tests/cli/test_init.py::test_init_creates_tome_skills -v` completes in < 5s (single-test invocation); full suite `mise run test` remains < 18s per AGENTS.md performance mandate
- **Lint budget**: `mise run lint` (ruff check) reports zero violations on the new test function — SKILL.md files are Markdown and not ruff-scanned
- **File size**: Each new SKILL.md ≤ 10KB (matches the reference deviate-constitution skill at ~6KB); total addition across seven files ≤ 70KB
- **Idempotency cost**: Re-running `deviate setup` on a populated workdir completes in ≤ 200ms (existing idempotent-skip path is O(skills) with filesystem stat only, no copy)

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**:
  - `tests/cli/test_init.py::test_init_creates_tome_skills` — assert all seven new SKILL.md files exist under `src/deviate/prompts/skills/tome-*/`, parse as valid YAML frontmatter, carry `name:` matching directory name, carry `category: deviatdd-tome-layer`, carry `version: 1.0.0`, and include slash-command aliases
  - `tests/cli/test_init.py::test_init_tome_skills_idempotent` — re-run `deviate setup` against a workdir where the seven SKILL.md files are already installed; assert no errors, no duplicate files, `[yellow]SKIP[/]` log lines emitted for each present skill
  - `tests/cli/test_init.py::test_init_discover_skills_enumerates_tome` — call `discover_skills()` post-implementation; assert it returns 30 names including the seven Tome names
- **Integration Sandbox Targets**:
  - `tests/cli/test_init_export_cycle.py` — full setup cycle with `--agent claude` against a temp workdir; assert all seven `.claude/skills/tome-*/SKILL.md` exist with byte-equal content to source templates
  - `tests/cli/test_init_export_cycle.py` — full setup cycle with `--agent opencode`; assert all seven `.opencode/skills/tome-*/SKILL.md` exist with byte-equal content

## Demonstration Path
```bash
# 1. Verify the seven new skill templates exist in source tree
ls src/deviate/prompts/skills/tome-classify/SKILL.md \
   src/deviate/prompts/skills/tome-write-tutorial/SKILL.md \
   src/deviate/prompts/skills/tome-write-how-to/SKILL.md \
   src/deviate/prompts/skills/tome-write-reference/SKILL.md \
   src/deviate/prompts/skills/tome-write-explanation/SKILL.md \
   src/deviate/prompts/skills/tome-verify-docs/SKILL.md \
   src/deviate/prompts/skills/tome-setup/SKILL.md

# 2. Verify frontmatter parses correctly
uv run python -c "
import yaml, pathlib
names = ['tome-classify','tome-write-tutorial','tome-write-how-to',
        'tome-write-reference','tome-write-explanation',
        'tome-verify-docs','tome-setup']
for name in names:
    text = pathlib.Path(f'src/deviate/prompts/skills/{name}/SKILL.md').read_text()
    fm = yaml.safe_load(text.split('---')[1])
    assert fm['name'] == name, f'{name}: name mismatch'
    assert fm['category'] == 'deviatdd-tome-layer', f'{name}: category mismatch'
    assert fm['version'] == '1.0.0', f'{name}: version mismatch'
    print(f'  [OK] {name} frontmatter valid')
"

# 3. Run the new unit tests
mise run test tests/cli/test_init.py::test_init_creates_tome_skills -v
mise run test tests/cli/test_init.py::test_init_tome_skills_idempotent -v
mise run test tests/cli/test_init.py::test_init_discover_skills_enumerates_tome -v

# 4. Run the full init + export cycle integration test
mise run test tests/cli/test_init_export_cycle.py -v

# 5. Manual smoke test: run deviate setup in a temp workdir
tmpdir=$(mktemp -d)
cd "$tmpdir"
git init -q && git config user.email "test@test" && git config user.name "Test"
uv run --project /Users/werner/Projects/tools/deviatdd deviate setup --agent claude
ls -la .claude/skills/tome-classify/ .claude/skills/tome-write-tutorial/ \
       .claude/skills/tome-write-how-to/ .claude/skills/tome-write-reference/ \
       .claude/skills/tome-write-explanation/ .claude/skills/tome-verify-docs/ \
       .claude/skills/tome-setup/

# 6. Verify byte-equal content between source and installed
for skill in tome-classify tome-write-tutorial tome-write-how-to \
             tome-write-reference tome-write-explanation \
             tome-verify-docs tome-setup; do
  diff src/deviate/prompts/skills/$skill/SKILL.md .claude/skills/$skill/SKILL.md
done

# 7. Confirm v1 prompt-only constraint upheld
test ! -f src/deviate/tome/__init__.py && echo "[OK] no tome/ Python module"
test ! -f src/deviate/tome/contracts.py && echo "[OK] no tome/contracts.py"
! grep -q "tome_app" src/deviate/cli/__init__.py && echo "[OK] no tome Typer sub-app"

# 8. Lint and format check
mise run lint
mise run format-check
```