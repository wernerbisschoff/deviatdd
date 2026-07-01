## FLOW-04 Tome Classify

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Decide which Diátaxis doc types (tutorial, how-to, reference, explanation) a commit (or a branch-level diff) requires so only the necessary writer prompts run and the docs site does not bloat with redundant cross-type regeneration.
- Emit an information-architecture (IA) contract for every capability row — `layer_order` (int), `parent` (path | null), `next` (path | null), `group` (ThemeGroup | null) — derived deterministically from the capability name, so the emitted pages sit in a reader-flow sequence under per-quadrant theme sub-directories with per-page `prev` / `next` frontmatter.

### Trigger
- Developer runs `/tome-classify` on demand.
- Default mode: HEAD~1 (the previous commit).
- Alternative modes: `/tome-classify <sha>`, `/tome-classify --merge-base` (diff from main merge base to HEAD), `/tome-classify --working-tree` (uncommitted/staged changes), `/tome-classify --codebase` (whole-codebase walk for cold-start / retroactive docs).

### Preconditions
- One of: HEAD~1 (default), an explicit `<sha>`, the merge-base diff of the current branch, or a working-tree diff is in scope
- Optional: relevant `specs/` artifacts (issues, tasks, flows) are reachable for semantic context
- Optional: existing docs tree at `apps/docs/src/content/docs/` is readable
- The classifier may emit `no-change` when no public docs need updating
- `apps/docs/` is not required to exist; absence triggers the `setup-required` action

### Happy path (primary steps)
1. Developer runs `/tome-classify` after a commit (default = HEAD~1) or with a flag for `--merge-base` / `--working-tree` / `--codebase`
2. Classifier ingests the commit message(s), changed files, changed tests, and the diff (single-commit, branch-level, working-tree, or full codebase)
3. Classifier optionally reads `specs/` flow, issue, and task artifacts as semantic anchors
4. Classifier optionally scans `apps/docs/src/content/docs/` to identify target candidates and the per-theme `_meta/<theme>.yml` ordering files
5. Classifier derives, for every row, the IA fields from the capability name using the canonical phase order and the ThemeGroup mapping in `specs/_product/domain-model.md` §ThemeGroup; a capability that does not map to a known theme emits `group: null` and a flat `target_file`
6. Classifier emits a change summary, a capability table (capability, evidence, audience, doc_type, action, target_file, confidence, **layer_order**, **parent**, **next**, **group**), and a list of docs that must not be touched
7. Developer reviews the action column and proceeds with the writer prompts indicated by `create` or `update`; the writer consumes the IA columns to set `prev` / `next` frontmatter and to honor theme sub-dir `target_file` paths

### Alternate / error paths
- All changes internal-only → action column reads `no-change`; downstream writers and `FLOW-09` are skipped
- Classifier is uncertain on doc type or target file → action reads `human-review`; writer prompts are blocked until human confirms
- No `apps/docs/` directory present → action reads `setup-required` and points at `FLOW-10`; classifier halts without proposing targets
- Required target file collides with an existing page in the wrong quadrant → action reads `human-review` with the collision flagged
- Classifier runs against merge-base diff → emits a branch-level classification covering all commits since divergence from main; the capability table is scoped to the cumulative change set, not a single commit
- Classifier would need to invent a new theme (capability does not map to any `ThemeGroup`) → escalates to `human-review` with `[NEW-THEME]` flagged for the developer to confirm; the classifier does NOT invent theme sub-dirs

### Success State
- A classification report naming the required Diátaxis types, target files, action per file, confidence, and the four IA fields per row
- The report is the entry ticket for `FLOW-05` through `FLOW-08` and gates `FLOW-09`

### Metrics / Signals
- Share of classifier runs classified as `no-change` rises over time as documentation coverage matures
- Confidence distribution skews high (>0.8) for reference and how-to classifications
- Human-review escalations feed back into classifier heuristics
- Default mode (HEAD~1) is the most-used path; merge-base mode is typically pre-PR; codebase mode is cold-start
- IA column coverage: 100% of rows carry `layer_order`, `parent`, `next`, `group` (with the latter `null` for non-themed capabilities)
- Cross-reference: `FLOW-10` is invoked when the classifier emits `setup-required`
- Cross-reference: `FLOW-09` runs only when at least one of `FLOW-05` through `FLOW-08` produced a file

## FLOW-05 Tome Write Tutorial

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one tutorial page in `apps/docs/src/content/docs/tutorials/` (root or theme sub-dir per classifier) when `FLOW-04` selects tutorial as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-tutorial` after `FLOW-04` emits a tutorial action with a target file.

### Preconditions
- `FLOW-04` classification indicates tutorial is required
- Target file path is supplied (default: `apps/docs/src/content/docs/tutorials/<name>.md`; the classifier may override with a theme sub-dir)
- Tutorial scope stays beginner-safe with one happy path and concrete expected results at each step
- Length budget: ≤ 120 lines (per `FLOW-09` Check 7)

### Happy path (primary steps)
1. Developer runs `/tome-write-tutorial <target_file>` after the classifier report
2. Writer reads the classifier output (including the IA columns), commit evidence, and existing target file (if any)
3. Writer composes a tutorial that preserves valid existing content
4. Writer emits full markdown including Tome frontmatter (`title`, `description`, `doc_type: tutorial`, `status`, `last_verified_at`, `verified_sha`, `related_issues`, **`prev`**, **`next`** — derived from the classifier's `parent` / `next` fields; `null` for quadrant intros and the first/last page in a theme)
5. Developer reads the diff and proceeds to the next required writer or to `FLOW-09`

### Alternate / error paths
- Tutorial would absorb reference material or how-to steps → writer downgrades scope and flags back to `FLOW-04` for re-classification
- Target file lives outside the `tutorials/` quadrant → writer rejects the path and surfaces a boundary violation
- Page length exceeds 120 lines → writer self-verify fails; writer trims and re-emits

### Success State
- One new or updated tutorial file under `apps/docs/src/content/docs/tutorials/` with valid Tome frontmatter (nine fields)
- File is in scope for `FLOW-09`
- File's `prev` / `next` match the classifier-emitted `parent` / `next`

### Metrics / Signals
- Tutorial coverage rate for changed beginner flows stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Tutorial page length stays within the 120-line budget
- Cross-reference: `FLOW-04` provides the action, target file, and IA columns
- Cross-reference: `FLOW-09` performs factual, boundary, IA, and length checks on this output

## FLOW-06 Tome Write How-To

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one how-to page in `apps/docs/src/content/docs/how-to/` (root or theme sub-dir per classifier) when `FLOW-04` selects how-to as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-how-to` after `FLOW-04` emits a how-to action with a target file.

### Preconditions
- `FLOW-04` classification indicates how-to is required
- Target file path is supplied (default: `apps/docs/src/content/docs/how-to/<name>.md`; the classifier may override with a theme sub-dir like `how-to/tdd-micro-cycle/red.md`)
- How-to scope covers prerequisites, exact steps, verification, and troubleshooting for one operator or contributor task
- Length budget: ≤ 80 lines (per `FLOW-09` Check 7)

### Happy path (primary steps)
1. Developer runs `/tome-write-how-to <target_file>` after the classifier report
2. Writer reads the classifier output (including the IA columns), commit evidence, and existing target file (if any)
3. Writer composes a how-to focused on a single task with prerequisites, numbered steps, verification, and troubleshooting
4. Writer emits full markdown including Tome frontmatter (`doc_type: how-to`, plus **`prev`**, **`next`** — derived from the classifier's `parent` / `next` fields)
5. Developer reads the diff and proceeds to the next required writer or to `FLOW-09`

### Alternate / error paths
- Required broad conceptual explanation exceeds how-to scope → writer flags back to `FLOW-04` to escalate to `FLOW-08`
- Target file lives outside the `how-to/` quadrant → writer rejects the path and surfaces a boundary violation
- Page length exceeds 80 lines → writer self-verify fails; writer trims and re-emits

### Success State
- One new or updated how-to file under `apps/docs/src/content/docs/how-to/` with valid Tome frontmatter (nine fields)
- File is in scope for `FLOW-09`
- File's `prev` / `next` match the classifier-emitted `parent` / `next`

### Metrics / Signals
- How-to coverage rate for changed operator and contributor tasks stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- How-to page length stays within the 80-line budget
- Cross-reference: `FLOW-04` provides the action, target file, and IA columns
- Cross-reference: `FLOW-09` performs factual, boundary, IA, and length checks on this output

## FLOW-07 Tome Write Reference

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one reference page in `apps/docs/src/content/docs/reference/` (root or theme sub-dir per classifier) when `FLOW-04` selects reference as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-reference` after `FLOW-04` emits a reference action with a target file.

### Preconditions
- `FLOW-04` classification indicates reference is required
- Target file path is supplied (default: `apps/docs/src/content/docs/reference/<name>.md`; the classifier may override with a theme sub-dir like `reference/cli/flags.md`)
- Reference scope stays factual, skimmable, and complete for the changed surface (commands, config, API, schema, flags)
- Length budget: tables dominate; no narrative paragraph longer than 2 sentences (per `FLOW-09` Check 7)

### Happy path (primary steps)
1. Developer runs `/tome-write-reference <target_file>` after the classifier report
2. Writer reads the classifier output (including the IA columns), commit evidence, and existing target file (if any)
3. Writer composes a reference page using tables for flags, fields, commands, defaults, and constraints
4. Writer emits full markdown including Tome frontmatter (`doc_type: reference`, plus **`prev`**, **`next`** — derived from the classifier's `parent` / `next` fields)
5. Developer reads the diff and proceeds to the next required writer or to `FLOW-09`

### Alternate / error paths
- Required tutorial-style narrative exceeds reference scope → writer flags back to `FLOW-04` to escalate to `FLOW-05`
- Target file lives outside the `reference/` quadrant → writer rejects the path and surfaces a boundary violation
- Page contains narrative paragraphs longer than 2 sentences → writer self-verify fails; writer trims and re-emits

### Success State
- One new or updated reference file under `apps/docs/src/content/docs/reference/` with valid Tome frontmatter (nine fields)
- File is in scope for `FLOW-09`
- File's `prev` / `next` match the classifier-emitted `parent` / `next`

### Metrics / Signals
- Reference coverage rate for changed commands, configs, APIs, and schemas stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Reference page narrative density stays under the 2-sentence budget
- Cross-reference: `FLOW-04` provides the action, target file, and IA columns
- Cross-reference: `FLOW-09` performs factual, boundary, IA, and length checks on this output

## FLOW-08 Tome Write Explanation

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one explanation page in `apps/docs/src/content/docs/explanation/` (root or theme sub-dir per classifier) when `FLOW-04` selects explanation as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-explanation` after `FLOW-04` emits an explanation action with a target file.

### Preconditions
- `FLOW-04` classification indicates explanation is required
- Target file path is supplied (default: `apps/docs/src/content/docs/explanation/<name>.md`; the classifier may override with a theme sub-dir like `explanation/architecture/three-layer.md`)
- Explanation scope stays in the why/how-it-works register: rationale, mental model, trade-offs, architectural meaning
- Length budget: ≤ 90 lines (per `FLOW-09` Check 7)

### Happy path (primary steps)
1. Developer runs `/tome-write-explanation <target_file>` after the classifier report
2. Writer reads the classifier output (including the IA columns), commit evidence, and existing target file (if any)
3. Writer composes an explanation of rationale, mental model, and trade-offs for the changed surface
4. Writer emits full markdown including Tome frontmatter (`doc_type: explanation`, plus **`prev`**, **`next`** — derived from the classifier's `parent` / `next` fields)
5. Developer reads the diff and proceeds to `FLOW-09`

### Alternate / error paths
- Writer drifts into step-by-step instructions → writer flags back to `FLOW-04` to escalate to `FLOW-06`
- Target file lives outside the `explanation/` quadrant → writer rejects the path and surfaces a boundary violation
- Page length exceeds 90 lines → writer self-verify fails; writer trims and re-emits

### Success State
- One new or updated explanation file under `apps/docs/src/content/docs/explanation/` with valid Tome frontmatter (nine fields)
- File is in scope for `FLOW-09`
- File's `prev` / `next` match the classifier-emitted `parent` / `next`

### Metrics / Signals
- Explanation coverage rate for changed architecture and rationale stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Explanation page length stays within the 90-line budget
- Cross-reference: `FLOW-04` provides the action, target file, and IA columns
- Cross-reference: `FLOW-09` performs factual, boundary, IA, and length checks on this output

## FLOW-09 Tome Verify Docs

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Verify that writer outputs from `FLOW-05` through `FLOW-08` are factually consistent with the commit, accurately placed in the Starlight content tree, respect Diátaxis boundaries, fit the per-writer length budget, and reach the IA contract (`prev` / `next` and theme sub-dir membership).

### Trigger
- Developer runs `/tome-verify-docs` after at least one writer prompt has completed for the current commit.

### Preconditions
- One or more of `FLOW-05` through `FLOW-08` has produced an updated file in `apps/docs/src/content/docs/`
- The merged commit diff and changed tests are accessible for cross-checking
- The original `FLOW-04` classification report is available for boundary and IA reconciliation
- The quadrant's `_meta/<theme>.yml` ordering files are readable (for the IA reachability check)

### Happy path (primary steps)
1. Developer runs `/tome-verify-docs` after writers complete
2. Verifier reads each updated doc, the commit diff, the changed tests, the `FLOW-04` classification, and the per-theme `_meta/<theme>.yml` files
3. Verifier runs seven checks per file: factual consistency, path correctness, command/config/API accuracy, no cross-type contamination, valid Starlight location, **IA reachability** (new in this iteration), and **length budget** (new in this iteration)
4. Verifier emits PASS items, FAIL items (per-check, with `[FAIL-LENGTH]` and `[FAIL-IA]` for the two new checks), boundary violations, and final recommended files to commit
5. Developer commits the PASS-only set and resolves any FAIL items before merge

### Alternate / error paths
- Verifier finds a boundary violation (e.g., tutorial content inside a how-to) → routes the affected file back to its writer with `<judge_feedback>` injection, mirroring `FLOW-01`'s JUDGE pattern
- Verifier finds a factual inconsistency (wrong command, outdated default, mismatched path) → rejects the file and prompts developer to either re-run the writer with updated evidence or escalate to human review
- Verifier finds a page is missing from its theme's `_meta/<theme>.yml` ordering → `[FAIL-IA]` finding; the page is excluded from the recommended-files list
- Verifier finds a page is missing `prev` / `next` frontmatter (or has stale `prev` / `next`) → `[FAIL-IA]` finding
- Verifier finds a page exceeds its length budget → `[FAIL-LENGTH]` finding; the page is excluded from the recommended-files list

### Success State
- PASS-only verifier output
- Recommended files cleared for commit
- All updated files match the IA contract (theme sub-dir membership, `prev` / `next` chain integrity)

### Metrics / Signals
- Verifier pass rate rises as classifier heuristics mature
- Cross-type contamination rate trends toward zero after iteration
- Average writer iterations per file drops as `FLOW-04` accuracy improves
- Length-budget compliance rate (no `[FAIL-LENGTH]` findings) trends toward 100% as writers learn the budget
- IA reachability rate (no `[FAIL-IA]` findings) trends toward 100% as classifier-theme-mapping matures
- Cross-reference: `FLOW-04` classification gates which files enter verification
- Cross-reference: `FLOW-05` through `FLOW-08` produce the files being verified

## FLOW-10 Tome Setup

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Bootstrap the Starlight docs site and Diátaxis quadrant structure in `apps/docs/`, including the per-quadrant theme sub-directories and per-theme `_meta/<theme>.yml` ordering files, so `FLOW-04` through `FLOW-09` can resolve target files on first use and the IA contract has a scaffold to grow into.

### Trigger
- Developer runs `/tome-setup` once per repo; subsequent runs are idempotent.

### Preconditions
- The repo accepts a Starlight app under `apps/docs/` (or developer confirms override)
- Developer is comfortable with the canonical content root `apps/docs/src/content/docs/`

### Happy path (primary steps)
1. Developer runs `/tome-setup` in the repo root
2. Setup scaffolds `apps/docs/` with Starlight
3. Setup creates the four quadrant directories under `apps/docs/src/content/docs/` (tutorials, how-to, reference, explanation) plus per-quadrant `<quadrant>/index.md` (the navigation pivot, one per quadrant, at the canonical Starlight path) and per-quadrant `<quadrant>/_meta.yml` (the per-quadrant sidebar manifest at the canonical Starlight path — NOT the legacy `<root>/_meta/<quadrant>.yml` location)
4. Setup pre-creates the per-theme sub-directories under each quadrant:
   - `how-to/`: `getting-started/`, `feature-lifecycle/`, `issue-execution/`, `tdd-micro-cycle/`, `recovery/`
   - `reference/`: `cli/`, `slash-commands/`, `config/`, `state-and-ledger/`, `tome/`
   - `explanation/`: `architecture/`, `data-and-governance/`, `process-and-safety/`
   - `tutorials/`: flat (only two pages today; flat until ≥5 single-entry pages would justify a theme)
5. Setup creates per-theme `<quadrant>/<theme>/_meta.yml` ordering files (one per theme sub-dir); Starlight reads these to drive sidebar ordering within the theme, and `FLOW-09`'s IA reachability check verifies every page under a theme is listed. The per-quadrant `<quadrant>/_meta.yml` (created in step 3) carries `pages: [index.md, ...theme-dirs]` so the per-quadrant landing page renders first in the sidebar.
6. Setup adds `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`, **`prev`**, **`next`**); on idempotent re-runs the existing schema is patched (not replaced) to add the two new fields without disturbing existing declarations
7. **Step 4½ — legacy-layout migration (re-run only)**: any legacy `<root>/_meta/<quadrant>.yml` is moved to `<quadrant>/_meta.yml`; any legacy `<quadrant>/intro.md` is renamed to `<quadrant>/index.md` (preserving content). Every migration action logs `[MIGRATE]`.
8. Setup seeds a small starter set: one architecture explanation, one config reference, one first-task how-to, one first-run tutorial — the starter set is rewritten to live under theme sub-dirs (e.g., `how-to/getting-started/starter-first-task.md`)
9. **Step 7 — root index rewrite**: setup writes or rewrites the root `apps/docs/src/content/docs/index.md` with an intro section first and a `## Quadrants` section linking to each `<quadrant>/index.md`. On re-run, only the `## Quadrants` section is rewritten (the intro paragraph is preserved).
10. Setup logs the canonical content root and signals readiness for `FLOW-04`

### Alternate / error paths
- `apps/docs/` already exists → setup is idempotent: skips scaffold, preserves existing files, only adds missing quadrant dirs, missing per-quadrant `<quadrant>/index.md` files, missing per-quadrant `<quadrant>/_meta.yml` files, missing theme sub-dirs, missing per-theme `<quadrant>/<theme>/_meta.yml` files, runs the Step 4½ migration if legacy files are present, and patches the existing `content.config.ts` to add the new `prev` / `next` fields without overwriting
- Starlight dependency conflict → setup halts with a clear remediation message; no partial state is left behind
- Developer wants to skip the starter set → an opt-out flag suppresses the seed step without affecting the rest of the scaffold

### Success State
- `apps/docs/src/content/docs/` exists with quadrant dirs, per-quadrant `<quadrant>/index.md` (navigation pivot, at the canonical Starlight path), per-quadrant `<quadrant>/_meta.yml` (canonical sidebar manifest with `pages: [index.md, ...]`), per-theme sub-dirs, per-theme `<quadrant>/<theme>/_meta.yml` files, a root `index.md` with an intro + `## Quadrants` section linking to each `<quadrant>/index.md`, and `content.config.ts` declaring the nine Tome frontmatter fields
- Starter set is present (or developer explicitly opted out)
- Subsequent `FLOW-04` runs can resolve target paths and the IA contract has a scaffold to grow into

### Metrics / Signals
- Time-to-first-doc after setup drops as the starter set matures
- Idempotent re-runs produce zero diff
- Per-theme `<quadrant>/<theme>/_meta.yml` files are present and list the expected pages (C6 verifies on each verify-docs pass). Per-quadrant `<quadrant>/_meta.yml` files list `index.md` as the first `pages:` entry (the `index-first` ordering invariant; C6 surfaces drift as `[FAIL-INDEX-FIRST]`).
- Cross-reference: `FLOW-04` emits `setup-required` and points at this flow when `apps/docs/` is absent
- Cross-reference: `FLOW-05` through `FLOW-08` rely on the per-quadrant `<quadrant>/index.md` (navigation pivot), per-theme sub-dirs, and per-theme `<quadrant>/<theme>/_meta.yml` files created here to honor the IA contract. Writers (C2-C5) own the content of `<quadrant>/index.md` and append to the per-theme `<quadrant>/<theme>/_meta.yml` `pages:` list when they add a page.
