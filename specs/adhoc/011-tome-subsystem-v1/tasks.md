# Implementation Tasks: `feat/adhoc/011-tome-subsystem-v1`

> Source issue: `specs/adhoc/issues/011-tome-subsystem-v1.md` (ISS-ADH-011)
> Source plan: `specs/adhoc/011-tome-subsystem-v1/plan.md`
> Release trace: `specs/_product/release-next.md` AC-ADHOC-011-01 through AC-ADHOC-011-10
> v1 prompt-only constraint: no Python runtime, no `deviate tome <phase>` CLI surface (per `specs/_product/architecture.md:17,21`)

## Phase 1: C1 Classifier Skill Template (FLOW-04)
**Goal**: Author `tome-classify/SKILL.md` as the prompt-only classifier that ingests commit/branch evidence and emits a structured classification report naming the Diátaxis doc types required. C1 is the gating skill that selects which downstream writers (C2-C5) run.

### Tasks

- TSK-011-01: Author `tome-classify/SKILL.md` (C1 classifier, FLOW-04)
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `test -f src/deviate/prompts/skills/tome-classify/SKILL.md && uv run --project /Users/werner/Projects/tools/deviatdd python -c "import yaml,pathlib; t=pathlib.Path('src/deviate/prompts/skills/tome-classify/SKILL.md').read_text(); fm=yaml.safe_load(t.split('---',2)[1]); assert fm['name']=='tome-classify'; assert fm['category']=='deviatdd-tome-layer'; assert fm['version']=='1.0.0'; assert '/tome-classify' in fm['aliases']; assert 'spec:classify' in fm['aliases']; print('OK')"`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `src/deviate/prompts/skills/tome-classify/SKILL.md`
    - `specs/_product/architecture.md` (read-only source of truth for C1 contract)
    - `specs/_product/flows/flows-tome.md` (read-only source of truth for FLOW-04 happy/alternate paths)
    - `specs/_product/domain-model.md` (read-only entity vocabulary)
  - **Rationale**: US-011-01 + US-011-02 require the classifier skill to exist with C1's four input modes (default HEAD~1, `<sha>`, `--merge-base`, `--working-tree`), the action enum (`create`, `update`, `no-change`, `human-review`, `setup-required`), and the classification report schema (change summary, capability table, no-touch list). The skill must be discoverable via `discover_skills()` at `src/deviate/core/skills.py:20-26` and installable via `_install_skills_to_agents` at `src/deviate/cli/__init__.py:522-535` without any code change — adding the directory is sufficient. AC-ADHOC-011-01 (existence), AC-ADHOC-011-02 (body content), AC-ADHOC-011-12 (flow_refs trace).
  - **Details**:
    - **Implementation**: Create the directory `src/deviate/prompts/skills/tome-classify/` and write `SKILL.md` with canonical YAML frontmatter in the exact field order established at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11` (`name`, `description`, `category`, `version`, `aliases`). Use `category: deviatdd-tome-layer`, `version: 1.0.0`, and a flat YAML list for aliases (not inline `[...]`). Single-line `description:` string. Body sections: (a) Input Modes — default HEAD~1, explicit `<sha>`, `--merge-base`, `--working-tree`; (b) Action Enum — `create`, `update`, `no-change`, `human-review`, `setup-required`; (c) Gate Behaviors — `no-change` skips writers + verifier; `human-review` blocks writers; `setup-required` halts and points at FLOW-10; (d) Classification Report Schema — change summary + capability table (`capability/evidence/audience/doc_type/action/target_file/confidence`) + no-touch list. Reference `specs/_product/architecture.md:38-56` and `specs/_product/flows/flows-tome.md:1-47` as authoritative inputs.
    - **Refactor**: Match frontmatter field order and alias-list style exactly to the reference at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11`. Use kebab-case in directory name and `name:` field.
    - **Edge Cases**: Long descriptions must remain single-line strings; flat YAML list for aliases (parser compatibility per spec Edge Cases §`YAML alias list format`); preserve existing in-progress modification to `src/deviate/prompts/skills/deviate-flows/SKILL.md` (do NOT touch — unrelated workstream per spec Edge Cases §`Existing in-progress modification`).
    - **Acceptance**: File exists at the exact path; YAML parses cleanly; `name`/`category`/`version` match expected values; `/tome-classify` and `spec:classify` both present in `aliases`; body sections for input modes, action enum, gate behaviors, and classification report schema are all present; body references the Product-layer source-of-truth files.

---

## Phase 2: Quadrant Writer Skills — Tutorials + How-Tos (FLOW-05, FLOW-06)
**Goal**: Author C2 (`tome-write-tutorial`) and C3 (`tome-write-how-to`) writer skills. Each writer is strictly confined to its quadrant directory under `apps/docs/src/content/docs/` and rejects out-of-quadrant target paths. Together they cover the learning-by-doing and task-resolution quadrants of the Diátaxis model.

### Tasks

- TSK-011-02: Author `tome-write-tutorial/SKILL.md` and `tome-write-how-to/SKILL.md` (C2 + C3 writers, FLOW-05 + FLOW-06)
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `test -f src/deviate/prompts/skills/tome-write-tutorial/SKILL.md && test -f src/deviate/prompts/skills/tome-write-how-to/SKILL.md && uv run --project /Users/werner/Projects/tools/deviatdd python -c "import yaml,pathlib; [yaml.safe_load(pathlib.Path(f'src/deviate/prompts/skills/{n}/SKILL.md').read_text().split('---',2)[1]) for n in ['tome-write-tutorial','tome-write-how-to']]; print('OK')"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/skills/tome-write-tutorial/SKILL.md`
    - `src/deviate/prompts/skills/tome-write-how-to/SKILL.md`
    - `specs/_product/architecture.md` (read-only source for C2/C3 quadrant rules)
    - `specs/_product/flows/flows-tome.md` (read-only source for FLOW-05/FLOW-06)
  - **Rationale**: US-011-03 requires each writer skill to be confined to its quadrant directory and reject out-of-quadrant target paths. Tutorial writers (C2) capture the "learning by doing" quadrant; how-to writers (C3) capture "task-resolution" content. Both must inline the seven-field frontmatter schema (`title`, `description`, `doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`) and instruct the agent to set `doc_type` to the matching quadrant. AC-ADHOC-011-01, AC-ADHOC-011-03 (quadrant rule), AC-ADHOC-011-04 (frontmatter schema), AC-ADHOC-011-07 (every page carries valid frontmatter).
  - **Details**:
    - **Implementation**: Create both directories and SKILL.md files. Canonical frontmatter per Phase 1 pattern. C2 body sections: (a) Quadrant Rule — writes only to `apps/docs/src/content/docs/tutorials/`; (b) Tutorial Register — one happy path, concrete expected results at each step, beginner-safe, no prerequisites assumed; (c) Frontmatter Schema — all seven fields with `doc_type: tutorial`; (d) Boundary Violation Rule — target outside `tutorials/` → reject + surface violation + flag back to FLOW-04 for re-classification. C3 body sections mirror C2 but for `apps/docs/src/content/docs/how-to/`, with `doc_type: how-to` and the how-to register (prerequisites, exact steps, verification, troubleshooting for one operator/contributor task). C3 also carries the cross-type downgrade rule: explanation-style content → flag back to FLOW-04 for re-classification to FLOW-08. Reference `specs/_product/architecture.md:60-82` and `specs/_product/flows/flows-tome.md:49-123`.
    - **Refactor**: Hardcode the exact kebab-case plural directory names (`tutorials/`, `how-to/`) verbatim in both skill bodies to prevent quadrant drift; reuse the frontmatter schema block identically across both writers.
    - **Edge Cases**: Writers must reject (not silently correct) out-of-quadrant target paths; cross-type contamination must surface back to FLOW-04, not be auto-fixed (per `specs/_product/architecture.md:20`).
    - **Acceptance**: Both files exist and parse as YAML; each quadrant directory is hardcoded in the writer body; each writer rejects out-of-quadrant paths in its body instructions; both inline the seven-field frontmatter schema with the correct `doc_type` value.

---

## Phase 3: Quadrant Writer Skills — Reference + Explanation (FLOW-07, FLOW-08)
**Goal**: Author C4 (`tome-write-reference`) and C5 (`tome-write-explanation`) writer skills. C4 produces factual, skimmable reference material (tables for flags/fields/commands/defaults/constraints); C5 produces reflective explanation content (rationale, mental model, trade-offs, architectural meaning). Together with Phase 2 they complete the four-quadrant Diátaxis writer coverage.

### Tasks

- TSK-011-03: Author `tome-write-reference/SKILL.md` and `tome-write-explanation/SKILL.md` (C4 + C5 writers, FLOW-07 + FLOW-08)
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `test -f src/deviate/prompts/skills/tome-write-reference/SKILL.md && test -f src/deviate/prompts/skills/tome-write-explanation/SKILL.md && uv run --project /Users/werner/Projects/tools/deviatdd python -c "import yaml,pathlib; [yaml.safe_load(pathlib.Path(f'src/deviate/prompts/skills/{n}/SKILL.md').read_text().split('---',2)[1]) for n in ['tome-write-reference','tome-write-explanation']]; print('OK')"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/skills/tome-write-reference/SKILL.md`
    - `src/deviate/prompts/skills/tome-write-explanation/SKILL.md`
    - `specs/_product/architecture.md` (read-only source for C4/C5 quadrant rules)
    - `specs/_product/flows/flows-tome.md` (read-only source for FLOW-07/FLOW-08)
  - **Rationale**: US-011-03 + US-011-07 require reference and explanation writers to round out the four-quadrant Diátaxis coverage. Reference material is information-oriented (describes the machinery); explanation material is understanding-oriented (discusses the machinery). Both must confine writes to their quadrant and inline the same frontmatter schema as Phase 2. C4 catches tutorial-style narrative contamination; C5 catches step-by-step instruction contamination. AC-ADHOC-011-01, AC-ADHOC-011-03, AC-ADHOC-011-04, AC-ADHOC-011-07.
  - **Details**:
    - **Implementation**: Create both directories and SKILL.md files. C4 body sections: (a) Quadrant Rule — writes only to `apps/docs/src/content/docs/reference/`; (b) Reference Register — factual, skimmable, tables for flags/fields/commands/defaults/constraints; (c) Frontmatter Schema with `doc_type: reference`; (d) Cross-type Downgrade — tutorial-style narrative → flag back to FLOW-04 for re-classification to FLOW-05. C5 body sections mirror C4 but for `apps/docs/src/content/docs/explanation/`, with `doc_type: explanation` and the explanation register (rationale, mental model, trade-offs, architectural meaning). C5 cross-type downgrade: step-by-step instructions → flag back to FLOW-04 for re-classification to FLOW-06. Reference `specs/_product/architecture.md:60-82` and `specs/_product/flows/flows-tome.md:125-199`.
    - **Refactor**: Reuse the frontmatter schema block identically across all four writers (C2-C5) — only the `doc_type` value, quadrant directory, register, and cross-type downgrade target differ.
    - **Edge Cases**: Reference writers must prioritize skimmable table layouts over narrative paragraphs; explanation writers must avoid prescriptive step lists that belong in how-to.
    - **Acceptance**: Both files exist and parse as YAML; each quadrant directory is hardcoded in the writer body; both inline the seven-field frontmatter schema; cross-type downgrade rules point at the correct flow ref.

---

## Phase 4: Verifier + Setup Skills (FLOW-09, FLOW-10)
**Goal**: Author C6 (`tome-verify-docs`) verifier skill and C7 (`tome-setup`) setup skill. C6 performs the read-only cross-doc pass after writers complete; C7 performs idempotent bootstrap of the Starlight `apps/docs/` site when absent in target repos.

### Tasks

- TSK-011-04: Author `tome-verify-docs/SKILL.md` and `tome-setup/SKILL.md` (C6 + C7, FLOW-09 + FLOW-10)
  - **Type**: Feature_Batch
  - **Mode**: IMMEDIATE
  - **Verification**: `test -f src/deviate/prompts/skills/tome-verify-docs/SKILL.md && test -f src/deviate/prompts/skills/tome-setup/SKILL.md && uv run --project /Users/werner/Projects/tools/deviatdd python -c "import yaml,pathlib; [yaml.safe_load(pathlib.Path(f'src/deviate/prompts/skills/{n}/SKILL.md').read_text().split('---',2)[1]) for n in ['tome-verify-docs','tome-setup']]; print('OK')"`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `src/deviate/prompts/skills/tome-verify-docs/SKILL.md`
    - `src/deviate/prompts/skills/tome-setup/SKILL.md`
    - `specs/_product/architecture.md` (read-only source for C6 verifier contract and C7 setup contract)
    - `specs/_product/flows/flows-tome.md` (read-only source for FLOW-09/FLOW-10)
  - **Rationale**: US-011-04 requires the verifier to surface factual inconsistencies, path mistakes, frontmatter schema violations, and cross-type contamination; US-011-05 requires the setup skill to materialize the Starlight scaffold + quadrant directories + `content.config.ts` + starter set idempotently. Both skills complete the seven-skill v1 release. AC-ADHOC-011-05 (verifier body content), AC-ADHOC-011-06 (setup body content), AC-ADHOC-011-09 (deviate setup installs all seven).
  - **Details**:
    - **Implementation**: Create both directories and SKILL.md files. C6 body sections: (a) Verifier Checks — factual consistency vs commit diff + changed tests; path correctness vs Starlight content tree; command/config/API accuracy; no cross-type contamination; valid Starlight location; (b) PASS/FAIL/human-review emit format; (c) Recommended-files-to-commit summary. C7 body sections: (a) Scaffold `apps/docs/` with Starlight; (b) Create four quadrant directories under `apps/docs/src/content/docs/` plus `index.md` and `_meta/`; (c) Add `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`); (d) Seed starter set (one explanation, one reference, one how-to, one tutorial); (e) Skip-no-op if `apps/docs/` already exists. Reference `specs/_product/architecture.md:32-33` and `specs/_product/flows/flows-tome.md:201-278`.
    - **Refactor**: C7's frontmatter field set must match exactly what the writers (C2-C5) emit — declare the same seven fields when extending `docsSchema()`.
    - **Edge Cases**: C6 emits reports only (no auto-routing back to writers per `specs/_product/architecture.md:20`); C7 must skip-no-op on existing `apps/docs/` to preserve idempotency.
    - **Acceptance**: Both files exist and parse as YAML; C6 body inlines all five verifier checks + PASS/FAIL/human-review emit format; C7 body inlines all five bootstrap steps + the skip-no-op guard; C7's frontmatter field set matches the writers' schema.

---

## Phase 5: Test Coverage — Existence + Idempotency
**Goal**: Extend `tests/test_cli/test_init.py` with the `_TOME_LAYER_SKILLS` constant and the first two of three new test methods, mirroring the FR-ADHOC-010 product-layer test pattern at `tests/test_cli/test_init.py:354-468`. This task proves all seven SKILL.md files exist, carry valid frontmatter, and install idempotently via the existing `_install_skills_to_agents` path.

### Tasks

- TSK-011-05: Add `_TOME_LAYER_SKILLS` constant and existence + idempotency tests to `tests/test_cli/test_init.py`
  - **Judge Feedback**: JUDGE rejected without rationale — re-verify spec compliance
  - **Judge Feedback**: JUDGE rejected without rationale — re-verify spec compliance
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_cli/test_init.py::test_init_creates_tome_skills tests/test_cli/test_init.py::test_init_tome_skills_idempotent -v`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/test_cli/test_init.py`
  - **Rationale**: The FR-ADHOC-010 product-layer tests at `tests/test_cli/test_init.py:354-468` established the canonical pattern for verifying skill template existence and frontmatter validity. Extending the test file with parallel tests for the seven Tome skills upholds Spec Scenario 011-01 (existence + frontmatter), Spec Scenario 011-09 (idempotent re-setup), and the Performance Constraint §`Lint budget` (zero ruff violations on the new tests). The existing `_install_skills_to_agents` path at `src/deviate/cli/__init__.py:518-531` provides the idempotency guarantee — the tests assert its observable behavior, no code change required. AC-ADHOC-011-10.
  - **Details**:
    - **Red**: Add `_TOME_LAYER_SKILLS = ("tome-classify", "tome-write-tutorial", "tome-write-how-to", "tome-write-reference", "tome-write-explanation", "tome-verify-docs", "tome-setup")` constant near line 16 (next to `_PRODUCT_LAYER_SKILLS`). Add `test_init_creates_tome_skills` — iterates the seven names, asserts each `src/deviate/prompts/skills/<name>/SKILL.md` exists, parses as valid YAML frontmatter via `yaml.safe_load`, asserts `name:` equals the directory name, `category:` equals `deviatdd-tome-layer`, `version:` equals `1.0.0`, aliases is a non-empty flat YAML list containing `/<name>` and `spec:<short-name>`, description is a single-line string. Add `test_init_tome_skills_idempotent` — monkey-patches `_get_agent_skill_dir`, runs `deviate setup --agent claude` twice against a fresh `tmp_path`, asserts first invocation installs all seven files, second invocation emits `SKIP` log lines for all seven.
    - **Green**: No production code change required — the existing `_install_skills_to_agents` and `discover_skills` already handle arbitrary skill directories. The test passes once Phases 1-4 ship the seven SKILL.md files.
    - **Refactor**: Mirror the docstring style and assertion patterns of `test_init_creates_product_layer_skills` (line 354) and `test_init_product_layer_skills_idempotent` (line 407) — each test carries a `TSK-011-0N:` reference in its docstring, source citation to the spec, and per-skill assertion error messages that include the skill name for easy debugging.
    - **Edge Cases**: Use `monkeypatch.setattr("deviate.cli._get_agent_skill_dir", lambda agent, _workdir: tmp_path / f".{agent}" / "skills")` to avoid touching the real user's home directory; use `chdir(tmp_path)` per the AGENTS.md Git Isolation Mandate; the pre-existing in-progress modification to `src/deviate/prompts/skills/deviate-flows/SKILL.md` must remain untouched.
    - **Acceptance**: Both tests pass in < 1s combined; full suite `mise run test` remains < 18s; `mise run lint` reports zero ruff violations on the new test methods; the `_TOME_LAYER_SKILLS` tuple sits next to `_PRODUCT_LAYER_SKILLS` at line 16.

---

## Phase 6: Test Coverage — Discover + E2E Smoke
**Goal**: Add the third test method (`test_init_discover_skills_enumerates_tome`) asserting `discover_skills()` enumerates the seven new Tome skills, then perform the end-to-end manual smoke test verifying `deviate setup --agent claude` produces byte-equal copies of all seven SKILL.md files in `workdir/.claude/skills/`.

### Tasks

- TSK-011-06: Add `test_init_discover_skills_enumerates_tome` test and run E2E smoke verification
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `mise run test tests/test_cli/test_init.py::test_init_discover_skills_enumerates_tome -v && mise run test tests/test_integration/test_init_export_cycle.py -v && mise run lint`
  - **Estimated Time**: 45 minutes
  - **Files**:
    - `tests/test_cli/test_init.py`
  - **Rationale**: Spec Scenario 011-08 requires `discover_skills()` to return the seven new Tome names. Spec Scenario 011-09 requires `deviate setup --agent claude` to install all seven with byte-equal content. The existing `test_init_discover_skills_enumerates_product_layer` at `tests/test_cli/test_init.py:442` and `tests/test_integration/test_init_export_cycle.py` provide the assertion patterns and the integration smoke harness — this task extends them. AC-ADHOC-011-10.
  - **Details**:
    - **Red**: Add `test_init_discover_skills_enumerates_tome` — calls `discover_skills()` from `deviate.core.skills`, asserts `len(skills) >= 30` (forward-compatible per FR-ADHOC-010 pattern; current count is 24 + 7 = 31), asserts each of the seven Tome names appears exactly once via `skills.count(skill_name) == 1`. Reuse the `_TOME_LAYER_SKILLS` constant added in TSK-011-05.
    - **Green**: No production code change required — `discover_skills()` at `src/deviate/core/skills.py:20-26` already enumerates any directory under `src/deviate/prompts/skills/` containing a `SKILL.md`. The test passes once the seven new directories are in place.
    - **Refactor**: Match the docstring style of `test_init_discover_skills_enumerates_product_layer` at line 442 — include a `TSK-011-06:` reference and source citation. Run `mise run test tests/test_integration/test_init_export_cycle.py -v` to confirm the existing integration smoke test still passes (it should, since `_install_skills_to_agents` is generic). Run `mise run lint` to confirm zero ruff violations on the new test method. Manual smoke: in a fresh `tmp_path` workdir with `git init` + `.deviate/config.toml`, run `uv run --project /Users/werner/Projects/tools/deviatdd deviate setup --agent claude` and `diff` each installed `.claude/skills/tome-*/SKILL.md` against its source — diffs must be empty.
    - **Edge Cases**: Use `>= 30` rather than `== 30` for forward-compatibility (matches FR-ADHOC-010 `>= 23` pattern at line 456 — see Risk Hotspots); do not modify `tests/test_integration/test_init_export_cycle.py` (existing coverage suffices).
    - **Acceptance**: New test passes; integration test still passes; zero lint violations; manual smoke diff returns empty for all seven Tome skills; full suite `mise run test` remains < 18s.

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 (`TSK-011-01`) → Phase 2 (`TSK-011-02`) → Phase 3 (`TSK-011-03`) → Phase 4 (`TSK-011-04`) → Phase 5 (`TSK-011-05`) → Phase 6 (`TSK-011-06`)

Phases 1-4 can run in parallel against separate worktrees if desired — each produces an independent SKILL.md artifact. Phases 5-6 must run after Phases 1-4 since the tests assert on the shipped artifacts.

**Critical Dependency Chains**:
- `TSK-011-05` must follow `TSK-011-01` through `TSK-011-04` (the existence test fails if any of the seven SKILL.md files is missing).
- `TSK-011-06` must follow `TSK-011-05` (the discover test reuses the `_TOME_LAYER_SKILLS` constant introduced there).

**Risk Hotspots**:
- **Frontmatter field-ordering drift** (Low impact, Medium likelihood): All seven new SKILL.md files must use the identical field order `name`, `description`, `category`, `version`, `aliases` matching `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11`. The `test_init_creates_tome_skills` test asserts `name`/`category`/`version` explicitly, surfacing drift as a test failure. The four writer skills (C2-C5) must inline the same frontmatter schema block verbatim except for `doc_type` and quadrant directory — keep this schema block as a copy-paste invariant.
- **`_TOME_LAYER_SKILLS` constant + in-progress `deviate-flows/SKILL.md` collision** (Medium impact, Low likelihood): The pre-existing `M src/deviate/prompts/skills/deviate-flows/SKILL.md` modification (observed at session start) is unrelated to Tome and must NOT be reverted or staged. The new constant lives in `tests/test_cli/test_init.py:16-17`; the test additions touch `tests/test_cli/test_init.py` only — no interaction with `deviate-flows/SKILL.md` content.
- **`discover_skills()` count assertion brittleness** (Medium impact, Medium likelihood): Use `>= 30` (not `== 30`) to allow forward-compatible additions, matching the FR-ADHOC-010 `>= 23` pattern at `tests/test_cli/test_init.py:456`. All seven Tome names must appear exactly once via `skills.count(skill_name) == 1`.
- **v1 prompt-only constraint regression** (High impact, Low likelihood): No `src/deviate/tome/`, no `tome/contracts.py`, no `src/deviate/cli/tome.py`, no `cli.add_typer` lines, no entries added to `_VALID_PHASES` or `_PHASE_ORDER`. After all phases ship, `git diff src/deviate/` should show only the seven new directories under `src/deviate/prompts/skills/tome-*/`. If `src/deviate/cli/__init__.py` appears in the diff, a regression has occurred.
- **Quadrant directory naming drift between writers (C2-C5) and setup (C7)** (Medium impact, Low likelihood): Hardcode the exact kebab-case plural directory names (`tutorials/`, `how-to/`, `reference/`, `explanation/`) identically in all four writer bodies and the C7 setup body. Drift between writer prompts and `content.config.ts` field set is a Starlight-side validation failure (C6 verifier finding) — the unit tests cannot catch this directly per the issue's Defensive Exclusions §`apps/docs/`.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `tests/test_cli/test_init.py` is touched by both Phase 5 (`TSK-011-05`) and Phase 6 (`TSK-011-06`). To minimize conflict surface, Phase 5 adds the constant + two tests; Phase 6 adds the third test method only. Sequential execution avoids any merge conflict.
- The seven new directories under `src/deviate/prompts/skills/tome-*/` are mutually exclusive — Phases 1-4 cannot conflict.
- The four Product-layer artifact files (`specs/_product/architecture.md`, `flows/flows-tome.md`, `domain-model.md`, `release-next.md`) are read-only inputs across all six phases and must never be modified by this issue (per the spec's Defensive Exclusions).

**Commits**:
- One commit per phase (six commits total) following the conventional commit format:
  - `feat(TSK-011-01): add tome-classify SKILL.md (C1 classifier, FLOW-04)`
  - `feat(TSK-011-02): add tome-write-tutorial + tome-write-how-to SKILL.md (C2+C3 writers, FLOW-05+FLOW-06)`
  - `feat(TSK-011-03): add tome-write-reference + tome-write-explanation SKILL.md (C4+C5 writers, FLOW-07+FLOW-08)`
  - `feat(TSK-011-04): add tome-verify-docs + tome-setup SKILL.md (C6+C7, FLOW-09+FLOW-10)`
  - `test(TSK-011-05): add tome-layer existence + idempotency tests`
  - `test(TSK-011-06): add tome-layer discover test + e2e smoke verification`
- Commits land on the existing `feat/adhoc/011-tome-subsystem-v1` worktree branch (HEAD at commit `1213c0b`, the `chore(adhoc-011): claim ISS-ADH-011` ledger-append commit).

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use the `tmp_path` pytest fixture (built-in) plus `chdir(tmp_path)` to redirect filesystem operations to a sandbox workdir. The existing `tests/test_cli/test_init.py` patterns at lines 354, 407, 442 already follow this convention — replicate it.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. The `monkeypatch.setattr("deviate.cli._get_agent_skill_dir", lambda agent, _workdir: tmp_path / f".{agent}" / "skills")` pattern redirects agent skill installation to the sandbox workdir without touching `~/.claude/` or `~/.opencode/`.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.

This issue does NOT modify any core module. The seven new SKILL.md files are static prompt artifacts consumed by `discover_skills()` (filesystem enumeration, no git interaction) and `install_skill()` (filesystem copy, no git interaction). The existing `_install_skills_to_agents` path at `src/deviate/cli/__init__.py:518-531` is unchanged.

---

## Universal Skill Frontmatter Invariant (ALL 7 SKILL.md FILES)

Every new `src/deviate/prompts/skills/tome-*/SKILL.md` MUST declare the frontmatter in this exact field order, matching the reference at `src/deviate/prompts/skills/deviate-constitution/SKILL.md:1-11`:

```yaml
---
name: <kebab-case-skill-name>
description: <single-line description, no embedded newlines>
category: deviatdd-tome-layer
version: 1.0.0
aliases:
  - /<skill-name>
  - spec:<short-name>
  - <other aliases if needed>
---
```

- `name` MUST equal the directory name (e.g., `tome-classify` for `src/deviate/prompts/skills/tome-classify/`).
- `description` MUST be a single-line string (no `\n` characters).
- `category` MUST equal `deviatdd-tome-layer` for all seven new skills.
- `version` MUST equal `1.0.0`.
- `aliases` MUST be a flat YAML list (not inline `[...]` syntax) including the slash-command form (`/<skill-name>`) and the `spec:<short-name>` form.

## Performance Targets (Recap)

- Each new SKILL.md ≤ 10KB (reference `deviate-constitution` is ~6KB / 215 lines).
- `discover_skills()` enumeration of 30+ skills ≤ 8ms.
- `deviate setup --agent claude` cold-path ≤ 500ms (7 × 10ms file copy overhead within gate).
- `deviate setup --agent claude` warm-path (idempotent re-run) ≤ 200ms.
- Full test suite `mise run test` ≤ 18s.
- `mise run lint` reports zero ruff violations on the new test methods.

## Ledger Discipline Notes

- `tasks.jsonl` is append-only: each state transition (RED → GREEN → JUDGE → COMPLETED) is a separate appended line per `specs/constitution.md:1` Append-Only Ledger Protocol. Existing lines are NEVER mutated.
- `created_at` timestamps may repeat for transitions batched within the same execution run (e.g. RED + GREEN + COMPLETED landing in the same `mise run test` invocation). The JUDGE transition typically carries a distinct timestamp because it runs in an isolated session per the constitution. Strictly monotonic per-task `created_at` is NOT a ledger invariant; downstream consumers that need a single canonical timestamp per task should pick the latest appended line for that `id`.
- `specs/issues.jsonl` follows the same rule. Multiple entries for the same `issue_id` are valid; canonical state is derived by sequential parsing, last-wins.
