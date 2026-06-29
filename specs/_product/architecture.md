# DeviaTDD Product Architecture — Tome Subsystem

**Classification**: Context-Creating (introduces 7 new components and 1 new output surface)
**Last Updated**: 2026-06-26
**Source Flows**: `specs/_product/flows/flows-tome.md` (FLOW-04..FLOW-10)

---

## 1. Scope

Tome is a manual post-merge documentation curator for Starlight docs sites. It classifies a commit (or a branch-level diff) against the four Diátaxis quadrants, then runs only the writer skills the classifier selects. The verifier performs a wider cross-doc pass after writers complete.

This document is Product-level — it covers components that span the seven Tome flows (FLOW-04..FLOW-10). Per-epic concerns belong in `specs/issues/`.

## 2. Out of Scope (Cross-Cutting)

- **Tome is prompt-only in v1**. Each Tome skill lives as a static `SKILL.md` text file under `src/deviate/prompts/skills/tome-*/`. No Python runtime is added in this iteration. DeviaTDD's own tech stack (Python 3.13 + Typer) is unchanged.
- **Tome output is decoupled from DeviaTDD's runtime stack**. Skill outputs (Starlight sites, `apps/docs/`, `content.config.ts`, `.astro` files) live in *target repos* that consume the skills, not in DeviaTDD's repo.
- **No shared contracts module**. Each skill inlines the schemas it needs. There is no `tome/contracts.py` or equivalent.
- **No JUDGE pattern**. The verifier (FLOW-09) emits a human-readable report. There is no `<judge_feedback>` auto-routing, no machine-parseable feedback, and no automated re-run of writers.
- **No `deviate tome <phase>` CLI surface in v1**. A future iteration may introduce a Typer sub-app under `src/deviate/cli/tome.py` for the phases that prove to need deterministic enforcement (likely C7 setup + path/frontmatter validation for C2-C5). v1 ships pure-prompt and gathers usage data first.

## 3. Components

| ID | Component | Skill | Flow | Responsibility | Self-verify | Writes to |
|---|---|---|---|---|---|---|
| C1 | Tome Classifier | `tome-classify` | FLOW-04 | Ingest commit/branch evidence; emit classification report | n/a (read-only) | nothing |
| C2 | Tome Writer — Tutorial | `tome-write-tutorial` | FLOW-05 | Produce one `tutorials/*.md` | yes | `apps/docs/src/content/docs/tutorials/` |
| C3 | Tome Writer — How-To | `tome-write-how-to` | FLOW-06 | Produce one `how-to/*.md` | yes | `apps/docs/src/content/docs/how-to/` |
| C4 | Tome Writer — Reference | `tome-write-reference` | FLOW-07 | Produce one `reference/*.md` | yes | `apps/docs/src/content/docs/reference/` |
| C5 | Tome Writer — Explanation | `tome-write-explanation` | FLOW-08 | Produce one `explanation/*.md` | yes | `apps/docs/src/content/docs/explanation/` |
| C6 | Tome Verifier | `tome-verify-docs` | FLOW-09 | Cross-doc pass: factual accuracy, path correctness, no cross-type contamination, valid Starlight location | n/a (read-only report) | nothing |
| C7 | Tome Setup | `tome-setup` | FLOW-10 | Idempotent bootstrap of `apps/docs/`, four quadrant dirs, `content.config.ts`, optional starter set | n/a | `apps/docs/` (in target repo) |

### 3.1 C1 — Tome Classifier (FLOW-04)

- **Skill path**: `src/deviate/prompts/skills/tome-classify/SKILL.md`
- **Input modes**:
  - default (no args) → HEAD~1 (previous commit)
  - `/tome-classify <sha>` → specific commit
  - `/tome-classify --merge-base` → `git diff $(git merge-base HEAD main)..HEAD` of current branch
  - `/tome-classify --working-tree` → uncommitted/staged changes
  - `/tome-classify --codebase` → entire working tree (no diff). The cold-start / retroactive path for bootstrapping docs on a project that has not yet been committed-to-doc convention. Walks manifests, source tree, CLI definitions, config schemas, and public API surface; emits an exhaustive capability table where every user-facing capability appears as a row (pre-existing valid docs are pre-marked `update`). Evidence-gathering procedure inlined in the C1 prompt under `<codebase_evidence>`; verifier (C6) handles the `codebase` evidence source by reading source files directly.
- **Inputs (per mode)**: commit SHA or branch diff, commit message(s), changed files, changed tests, optional `specs/` artifacts (issues, tasks, flows), existing `apps/docs/src/content/docs/` tree.
- **Outputs**: A classification report containing:
  1. brief change summary
  2. capability table (capability, evidence, audience, doc_type, action, target_file, confidence)
  3. no-touch list
- **Action enum** (inlined in C1 prompt): `create`, `update`, `no-change`, `human-review`, `setup-required`.
- **Gate behavior**:
  - All changes internal-only → `no-change`; downstream writers and C6 are skipped.
  - Classifier uncertain → `human-review`; writers blocked until human confirms.
  - `apps/docs/` absent → `setup-required`; classifier halts and points at C7.
  - Target file collides with existing page in wrong quadrant → `human-review` with collision flagged.
  - Merge-base diff → branch-level classification covering all commits since divergence from main; capability table is scoped to the cumulative change set.
- **Flow ref**: FLOW-04.

### 3.2 C2-C5 — Tome Writers (FLOW-05..FLOW-08)

- **Skill paths**:
  - C2: `src/deviate/prompts/skills/tome-write-tutorial/SKILL.md`
  - C3: `src/deviate/prompts/skills/tome-write-how-to/SKILL.md`
  - C4: `src/deviate/prompts/skills/tome-write-reference/SKILL.md`
  - C5: `src/deviate/prompts/skills/tome-write-explanation/SKILL.md`
- **Strict quadrant rule**: Each writer is confined to its own Diátaxis quadrant directory. C2 → `tutorials/`, C3 → `how-to/`, C4 → `reference/`, C5 → `explanation/`. A writer that needs to touch a different quadrant must flag back to C1 for re-classification.
- **Per-writer self-verify** (built into each prompt, not a separate output):
  - target file path is in the writer's quadrant
  - frontmatter is valid Tome schema (`title`, `description`, `doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`)
  - content stays in the writer's doc_type register (e.g., C2 does not produce step-by-step instructions, C6 territory)
  - existing valid content is preserved where possible
- **Frontmatter schema** (inlined in each writer prompt):
  ```yaml
  ---
  title: ...
  description: ...
  doc_type: tutorial | how-to | reference | explanation
  status: draft | reviewed
  last_verified_at: YYYY-MM-DD
  verified_sha: abc1234
  related_issues:
    - ISS-123
  ---
  ```
- **Out-of-scope for writers**: `index.md`, `_meta/`, `content.config.ts`, `package.json`, `astro.config.mjs`. These are C7's territory or out of scope.
- **Flow refs**: FLOW-05, FLOW-06, FLOW-07, FLOW-08.

### 3.3 C6 — Tome Verifier (FLOW-09)

- **Skill path**: `src/deviate/prompts/skills/tome-verify-docs/SKILL.md`
- **Trigger**: Developer runs `/tome-verify-docs` after at least one writer (C2-C5) has produced an updated file.
- **Cross-doc checks** (system-level, not single-doc):
  - Factual consistency: each updated doc's claims match the commit diff, changed tests, and `specs/` artifacts.
  - Path correctness: each updated file lives in the quadrant its `doc_type` claims.
  - Command/config/API accuracy: examples in updated docs match current code.
  - No cross-type contamination: tutorial content inside a how-to, etc.
  - Valid Starlight location: file is under `apps/docs/src/content/docs/<quadrant>/`.
- **Output format**: Human-readable markdown report with:
  - PASS items
  - FAIL items
  - Boundary violations
  - Recommended files to commit
- **No auto-routing**: Verifier does not call back to writers. Human reads the report, manually re-runs the relevant writer with updated evidence if needed.
- **Flow ref**: FLOW-09.

### 3.4 C7 — Tome Setup (FLOW-10)

- **Skill path**: `src/deviate/prompts/skills/tome-setup/SKILL.md`
- **Trigger**: Developer runs `/tome-setup` once per repo; subsequent runs are idempotent.
- **Inputs**: confirmation that the repo accepts a Starlight app under `apps/docs/` (or developer confirms override).
- **Scaffold**:
  1. `apps/docs/` with Starlight
  2. Four quadrant dirs under `apps/docs/src/content/docs/` (tutorials, how-to, reference, explanation) + `index.md` + `_meta/`
  3. `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`)
  4. Optional starter set (one architecture explanation, one config reference, one first-task how-to, one first-run tutorial) — controlled by an opt-out flag
- **Idempotency**: Re-runs produce zero diff against committed state. Missing quadrant dirs are added; existing files are preserved.
- **Precondition for C1**: C1 refuses to propose target files until C7 has produced `apps/docs/`. Classifier emits `setup-required` action and halts.
- **Flow ref**: FLOW-10.

## 4. Integration Contracts

### 4.1 C1 → C2-C5 contract

- **Form**: Classification report (inlined markdown in C1's output, consumed by humans who then run the relevant C2-C5 skill).
- **Schema** (inlined in both C1 and each C2-C5 prompt):
  ```markdown
  # Classification Report — <sha-or-mode>

  ## Summary
  <one-paragraph change summary>

  ## Capabilities
  | capability | evidence | audience | doc_type | action | target_file | confidence |
  |------------|----------|----------|----------|--------|-------------|------------|
  | ...        | ...      | ...      | ...      | ...    | ...         | ...        |

  ## No-Touch List
  - <files that must not be modified>
  ```
- **DocType values**: `tutorial`, `how-to`, `reference`, `explanation`.
- **Action values**: `create`, `update`, `no-change`, `human-review`, `setup-required`.

### 4.2 C2-C5 → C6 contract

- **Form**: Updated files at the path declared in C1's `target_file` column, with valid Tome frontmatter.
- **No machine-parseable handoff**: C2-C5 emit markdown; C6 reads markdown. No structured metadata file is shared.

### 4.3 C7 → C1 contract

- **Form**: C1 reads the existence of `apps/docs/src/content/docs/` to decide whether to emit `setup-required` or proceed.
- **Tome frontmatter schema is declared in two places**: C7's `content.config.ts` (Starlight-side) and inline in C2-C5 prompts (LLM-side). Both must agree; drift between them is a verifier (C6) finding.

## 5. Data Ownership Boundaries

| Owner | Owns | Reads | Writes |
|---|---|---|---|
| C1 | Classification report (transient) | commit, diff, `specs/`, `apps/docs/src/content/docs/` (read-only) | nothing |
| C2 | `apps/docs/src/content/docs/tutorials/*.md` | commit, classification report | `tutorials/` |
| C3 | `apps/docs/src/content/docs/how-to/*.md` | commit, classification report | `how-to/` |
| C4 | `apps/docs/src/content/docs/reference/*.md` | commit, classification report | `reference/` |
| C5 | `apps/docs/src/content/docs/explanation/*.md` | commit, classification report | `explanation/` |
| C6 | Verification report (transient) | updated docs, commit, classification report | nothing |
| C7 | `apps/docs/` (scaffold, content config, starter set) | target repo state | `apps/docs/` |

**Quadrant directory is the structural seam**: C2-C5 must not write outside their assigned quadrant. C7 is the only writer of `content.config.ts`, `index.md`, and `_meta/`. C1 and C6 are read-only.

## 6. Dependency Graph

```
FLOW-10 (C7 Setup) ──── gates ────> FLOW-04 (C1 Classify)
                                       │
                                       ├──> FLOW-05 (C2 Write Tutorial)
                                       ├──> FLOW-06 (C3 Write How-To)
                                       ├──> FLOW-07 (C4 Write Reference)
                                       └──> FLOW-08 (C5 Write Explanation)
                                                          │
                                                          └──> FLOW-09 (C6 Verify)
```

- **C7 is the only prerequisite for C1**. Until C7 has produced `apps/docs/`, C1 emits `setup-required` and halts.
- **C1 is the only prerequisite for C2-C5**. Each writer runs only when C1's capability table contains a row with that writer's `doc_type` and a `create` or `update` action.
- **C2-C5 are independent of each other** — no cross-writer coordination.
- **C6 runs only after at least one of C2-C5 has produced a file**. C6 is not blocking on the full set of writers; the developer can verify after each writer or after the whole set.
- **No CLI execution layer in v1**. All work is LLM-mediated through the skill prompts. A `deviate tome <phase>` CLI surface is deferred to a future iteration once v1 usage data shows which phases need deterministic enforcement.

## 7. Flow Traceability

| Component | Flow IDs |
|---|---|
| C1 | FLOW-04 |
| C2 | FLOW-05 |
| C3 | FLOW-06 |
| C4 | FLOW-07 |
| C5 | FLOW-08 |
| C6 | FLOW-09 |
| C7 | FLOW-10 |

| Flow ID | Component |
|---|---|
| FLOW-04 | C1 |
| FLOW-05 | C2 |
| FLOW-06 | C3 |
| FLOW-07 | C4 |
| FLOW-08 | C5 |
| FLOW-09 | C6 |
| FLOW-10 | C7 |

No orphans. Every flow maps to exactly one component; every component maps to at least one flow.

## 8. Constitution Cross-Check

- §2 Frontend (None, CLI-only) — **Satisfied**. Tome skills are markdown prompts in `src/deviate/prompts/skills/`. No web/GUI runtime is added to DeviaTDD itself.
- §2 Backend (Python 3.13, Typer) — **Satisfied**. No new Python modules or runtime code.
- §2 Tech stack standards — **Satisfied**. No `package.json`, `astro.config.mjs`, or Node toolchain is added to DeviaTDD's repo. Skill *output* may include these files in target repos; that is out of scope for this constitution.
- §1 Architectural principles — **Satisfied**. Tome operates purely at the prompt layer, layered on top of DeviaTDD's three-layer architecture without modifying it.

No `[red]CONSTITUTION_CONFLICT[/]`. No amendment required.

## 9. Cross-Layer Signal

Downstream `deviate shard` invocations will emit `flow_refs:` for any issue derived from this architecture, keyed to the component→flow map in §7. The `Tome Subsystem` epic (or its equivalent) will derive its issue set from the seven flows FLOW-04..FLOW-10 plus the architectural seams identified in §4 and §5.
