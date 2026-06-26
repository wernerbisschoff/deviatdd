## FLOW-04 Tome Classify Commit

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Decide which Diátaxis doc types (tutorial, how-to, reference, explanation) a merged commit requires so only the necessary writer prompts run and the docs site does not bloat with redundant cross-type regeneration.

### Trigger
- Developer runs `/tome-classify-commit` on demand, supplying a commit SHA or merged diff.

### Preconditions
- A commit SHA, merged diff, or working-tree diff is supplied
- Optional: relevant `specs/` artifacts (issues, tasks, flows) are reachable for semantic context
- Optional: existing docs tree at `apps/docs/src/content/docs/` is readable
- The classifier may emit `no-change` when no public docs need updating
- `apps/docs/` is not required to exist; absence triggers the `setup-required` action

### Happy path (primary steps)
1. Developer runs `/tome-classify-commit <sha>` after a merge
2. Classifier ingests the commit message, changed files, changed tests, and merged diff
3. Classifier optionally reads `specs/` flow, issue, and task artifacts as semantic anchors
4. Classifier optionally scans `apps/docs/src/content/docs/` to identify target candidates
5. Classifier emits a change summary, a capability table (capability, evidence, audience, doc_type, action, target_file, confidence), and a list of docs that must not be touched
6. Developer reviews the action column and proceeds with the writer prompts indicated by `create` or `update`

### Alternate / error paths
- All changes internal-only → action column reads `no-change`; downstream writers and `FLOW-09` are skipped
- Classifier is uncertain on doc type or target file → action reads `human-review`; writer prompts are blocked until human confirms
- No `apps/docs/` directory present → action reads `setup-required` and points at `FLOW-10`; classifier halts without proposing targets
- Required target file collides with an existing page in the wrong quadrant → action reads `human-review` with the collision flagged

### Success State
- A classification report naming the required Diátaxis types, target files, action per file, and confidence
- The report is the entry ticket for `FLOW-05` through `FLOW-08` and gates `FLOW-09`

### Metrics / Signals
- Share of commits classified as `no-change` rises over time as documentation coverage matures
- Confidence distribution skews high (>0.8) for reference and how-to classifications
- Human-review escalations feed back into classifier heuristics
- Cross-reference: `FLOW-10` is invoked when the classifier emits `setup-required`
- Cross-reference: `FLOW-09` runs only when at least one of `FLOW-05` through `FLOW-08` produced a file

## FLOW-05 Tome Write Tutorial

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one tutorial page in `apps/docs/src/content/docs/tutorials/` when `FLOW-04` selects tutorial as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-tutorial` after `FLOW-04` emits a tutorial action with a target file.

### Preconditions
- `FLOW-04` classification indicates tutorial is required
- Target file path is supplied (default: `apps/docs/src/content/docs/tutorials/<name>.md`)
- Tutorial scope stays beginner-safe with one happy path and concrete expected results at each step

### Happy path (primary steps)
1. Developer runs `/tome-write-tutorial <target_file>` after the classifier report
2. Writer reads the classifier output, commit evidence, and existing target file (if any)
3. Writer composes a tutorial that preserves valid existing content
4. Writer emits full markdown including Tome frontmatter (`title`, `description`, `doc_type: tutorial`, `status`, `last_verified_at`, `verified_sha`, `related_issues`)
5. Developer reads the diff and proceeds to the next required writer or to `FLOW-09`

### Alternate / error paths
- Tutorial would absorb reference material or how-to steps → writer downgrades scope and flags back to `FLOW-04` for re-classification
- Target file lives outside the `tutorials/` quadrant → writer rejects the path and surfaces a boundary violation

### Success State
- One new or updated tutorial file under `apps/docs/src/content/docs/tutorials/` with valid Tome frontmatter
- File is in scope for `FLOW-09`

### Metrics / Signals
- Tutorial coverage rate for changed beginner flows stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Cross-reference: `FLOW-04` provides the action and target file
- Cross-reference: `FLOW-09` performs factual and boundary checks on this output

## FLOW-06 Tome Write How-To

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one how-to page in `apps/docs/src/content/docs/how-to/` when `FLOW-04` selects how-to as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-how-to` after `FLOW-04` emits a how-to action with a target file.

### Preconditions
- `FLOW-04` classification indicates how-to is required
- Target file path is supplied (default: `apps/docs/src/content/docs/how-to/<name>.md`)
- How-to scope covers prerequisites, exact steps, verification, and troubleshooting for one operator or contributor task

### Happy path (primary steps)
1. Developer runs `/tome-write-how-to <target_file>` after the classifier report
2. Writer reads the classifier output, commit evidence, and existing target file (if any)
3. Writer composes a how-to focused on a single task with prerequisites and verification steps
4. Writer emits full markdown including Tome frontmatter (`doc_type: how-to`)
5. Developer reads the diff and proceeds to the next required writer or to `FLOW-09`

### Alternate / error paths
- Required broad conceptual explanation exceeds how-to scope → writer flags back to `FLOW-04` to escalate to `FLOW-08`
- Target file lives outside the `how-to/` quadrant → writer rejects the path and surfaces a boundary violation

### Success State
- One new or updated how-to file under `apps/docs/src/content/docs/how-to/` with valid Tome frontmatter
- File is in scope for `FLOW-09`

### Metrics / Signals
- How-to coverage rate for changed operator and contributor tasks stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Cross-reference: `FLOW-04` provides the action and target file
- Cross-reference: `FLOW-09` performs factual and boundary checks on this output

## FLOW-07 Tome Write Reference

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one reference page in `apps/docs/src/content/docs/reference/` when `FLOW-04` selects reference as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-reference` after `FLOW-04` emits a reference action with a target file.

### Preconditions
- `FLOW-04` classification indicates reference is required
- Target file path is supplied (default: `apps/docs/src/content/docs/reference/<name>.md`)
- Reference scope stays factual, skimmable, and complete for the changed surface (commands, config, API, schema, flags)

### Happy path (primary steps)
1. Developer runs `/tome-write-reference <target_file>` after the classifier report
2. Writer reads the classifier output, commit evidence, and existing target file (if any)
3. Writer composes a reference page using tables for flags, fields, commands, defaults, and constraints
4. Writer emits full markdown including Tome frontmatter (`doc_type: reference`)
5. Developer reads the diff and proceeds to the next required writer or to `FLOW-09`

### Alternate / error paths
- Required tutorial-style narrative exceeds reference scope → writer flags back to `FLOW-04` to escalate to `FLOW-05`
- Target file lives outside the `reference/` quadrant → writer rejects the path and surfaces a boundary violation

### Success State
- One new or updated reference file under `apps/docs/src/content/docs/reference/` with valid Tome frontmatter
- File is in scope for `FLOW-09`

### Metrics / Signals
- Reference coverage rate for changed commands, configs, APIs, and schemas stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Cross-reference: `FLOW-04` provides the action and target file
- Cross-reference: `FLOW-09` performs factual and boundary checks on this output

## FLOW-08 Tome Write Explanation

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Produce or update exactly one explanation page in `apps/docs/src/content/docs/explanation/` when `FLOW-04` selects explanation as the required Diátaxis type.

### Trigger
- Developer runs `/tome-write-explanation` after `FLOW-04` emits an explanation action with a target file.

### Preconditions
- `FLOW-04` classification indicates explanation is required
- Target file path is supplied (default: `apps/docs/src/content/docs/explanation/<name>.md`)
- Explanation scope stays in the why/how-it-works register: rationale, mental model, trade-offs, architectural meaning

### Happy path (primary steps)
1. Developer runs `/tome-write-explanation <target_file>` after the classifier report
2. Writer reads the classifier output, commit evidence, and existing target file (if any)
3. Writer composes an explanation of rationale, mental model, and trade-offs for the changed surface
4. Writer emits full markdown including Tome frontmatter (`doc_type: explanation`)
5. Developer reads the diff and proceeds to `FLOW-09`

### Alternate / error paths
- Writer drifts into step-by-step instructions → writer flags back to `FLOW-04` to escalate to `FLOW-06`
- Target file lives outside the `explanation/` quadrant → writer rejects the path and surfaces a boundary violation

### Success State
- One new or updated explanation file under `apps/docs/src/content/docs/explanation/` with valid Tome frontmatter
- File is in scope for `FLOW-09`

### Metrics / Signals
- Explanation coverage rate for changed architecture and rationale stays aligned with `FLOW-04` selections
- Cross-type contamination rate from `FLOW-09` verifier feedback trends toward zero
- Cross-reference: `FLOW-04` provides the action and target file
- Cross-reference: `FLOW-09` performs factual and boundary checks on this output

## FLOW-09 Tome Verify Docs

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Verify that writer outputs from `FLOW-05` through `FLOW-08` are factually consistent with the commit, accurately placed in the Starlight content tree, and respect Diátaxis boundaries.

### Trigger
- Developer runs `/tome-verify-docs` after at least one writer prompt has completed for the current commit.

### Preconditions
- One or more of `FLOW-05` through `FLOW-08` has produced an updated file in `apps/docs/src/content/docs/`
- The merged commit diff and changed tests are accessible for cross-checking
- The original `FLOW-04` classification report is available for boundary reconciliation

### Happy path (primary steps)
1. Developer runs `/tome-verify-docs` after writers complete
2. Verifier reads each updated doc, the commit diff, the changed tests, and the `FLOW-04` classification
3. Verifier checks factual consistency, file path correctness, command/config/API accuracy, no cross-type contamination, and valid Starlight location
4. Verifier emits PASS items, FAIL items, boundary violations, and final recommended files to commit
5. Developer commits the PASS-only set and resolves any FAIL items before merge

### Alternate / error paths
- Verifier finds a boundary violation (e.g., tutorial content inside a how-to) → routes the affected file back to its writer with `<judge_feedback>` injection, mirroring `FLOW-01`'s JUDGE pattern
- Verifier finds a factual inconsistency (wrong command, outdated default, mismatched path) → rejects the file and prompts developer to either re-run the writer with updated evidence or escalate to human review

### Success State
- PASS-only verifier output
- Recommended files cleared for commit

### Metrics / Signals
- Verifier pass rate rises as classifier heuristics mature
- Cross-type contamination rate trends toward zero after iteration
- Average writer iterations per file drops as `FLOW-04` accuracy improves
- Cross-reference: `FLOW-04` classification gates which files enter verification
- Cross-reference: `FLOW-05` through `FLOW-08` produce the files being verified

## FLOW-10 Tome Setup

- Actor: Developer
- Domain: Documentation
- Status: Draft

### Problem / job to be done
- Bootstrap the Starlight docs site and Diátaxis quadrant structure in `apps/docs/` so `FLOW-04` through `FLOW-09` can resolve target files on first use.

### Trigger
- Developer runs `/tome-setup` once per repo; subsequent runs are idempotent.

### Preconditions
- The repo accepts a Starlight app under `apps/docs/` (or developer confirms override)
- Developer is comfortable with the canonical content root `apps/docs/src/content/docs/`

### Happy path (primary steps)
1. Developer runs `/tome-setup` in the repo root
2. Setup scaffolds `apps/docs/` with Starlight
3. Setup creates the four quadrant directories under `apps/docs/src/content/docs/` (tutorials, how-to, reference, explanation) plus `index.md` and `_meta/`
4. Setup adds `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`)
5. Setup seeds a small starter set: one architecture explanation, one config reference, one first-task how-to, one first-run tutorial
6. Setup logs the canonical content root and signals readiness for `FLOW-04`

### Alternate / error paths
- `apps/docs/` already exists → setup is idempotent: skips scaffold, preserves existing files, only adds missing quadrant dirs and config fields
- Starlight dependency conflict → setup halts with a clear remediation message; no partial state is left behind
- Developer wants to skip the starter set → an opt-out flag suppresses the seed step without affecting the rest of the scaffold

### Success State
- `apps/docs/src/content/docs/` exists with quadrant dirs, `index.md`, `_meta/`, and `content.config.ts`
- Starter set is present (or developer explicitly opted out)
- Subsequent `FLOW-04` runs can resolve target paths

### Metrics / Signals
- Time-to-first-doc after setup drops as the starter set matures
- Idempotent re-runs produce zero diff
- Cross-reference: `FLOW-04` emits `setup-required` and points at this flow when `apps/docs/` is absent
- Cross-reference: `FLOW-05` through `FLOW-08` rely on the quadrant dirs created here