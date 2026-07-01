# DeviaTDD Product Domain Model

**Last Updated**: 2026-06-30
**Source**: `specs/_product/architecture.md` §3 (Tome Subsystem)

---

## Entities

### Commit
- **Attributes**: `sha`, `message`, `changed_files[]`, `changed_tests[]`, `merged_diff` (or `branch_diff` for merge-base mode)
- **Relationships**:
  - has many `Capability` (1..n) — what changes the commit introduces that may need docs
  - input to `ClassificationReport`

### ClassificationReport
- **Attributes**: `change_summary`, `capabilities[]` (Capability list, ordered by `layer_order` within group), `no_touch_list[]` (file paths), `mode` (`commit` | `sha` | `merge-base` | `working-tree` | `codebase`), `target_sha` (commit SHA for diff modes; `codebase:<head-short-sha>` for the `codebase` mode)
- **Relationships**:
  - produced by C1 (Tome Classifier)
  - consumed by C2-C5 (writers, via human handoff; consume the IA columns to set `prev`/`next` frontmatter and to honor theme sub-dir `target_file` paths)
  - consumed by C6 (verifier, for boundary reconciliation; verifier also re-derives IA relationships from on-disk `_meta/<theme>.yml` files)

### Capability
- **Attributes**:
  - `capability` (string) — user-facing capability name
  - `evidence` (string) — file paths or commit messages that justify the row
  - `audience` (`user` | `operator` | `contributor` | `internal`)
  - `doc_type` (DocType)
  - `action` (Action)
  - `target_file` (path; may include a theme sub-dir like `how-to/tdd-micro-cycle/red.md`)
  - `confidence` (0.0-1.0)
  - **`layer_order`** (int) — the page's position within the canonical phase order for its quadrant; emitted by C1, consumed by C2-C5 (writers use it to order `prev`/`next` when the chain is not explicit) and by C6 (verifier uses it to detect reader-flow drift)
  - **`parent`** (path | null) — the prior page in the reading order; `null` for quadrant intros and the first page in a theme
  - **`next`** (path | null) — the next page in the reading order; `null` for the last page in a theme
  - **`group`** (ThemeGroup | null) — the theme sub-dir the writer should target; `null` when the capability does not map to a known theme, in which case `target_file` is flat
- **Relationships**:
  - belongs to one `ClassificationReport`
  - routes to one writer (C2-C5) based on `doc_type`
  - may be linked to a sibling `Capability` via `parent` / `next` (the IA sequence)
  - may be linked to a `ThemeGroup` via `group` (the IA theme bucket)

### DocType (enum)
- **Values**: `tutorial`, `how-to`, `reference`, `explanation`
- **Cardinality**: 1:1 with writer components C2-C5

### Action (enum)
- **Values**: `create`, `update`, `no-change`, `human-review`, `setup-required`
- **Semantics**:
  - `create` / `update` → triggers a writer (C2-C5)
  - `no-change` → no writer runs; C6 also skipped
  - `human-review` → human reviews before any writer runs
  - `setup-required` → C7 must run before C1 can proceed

### ThemeGroup (enum, new in this iteration)
- **Values per quadrant** (the canonical mapping C1 uses):
  - `how-to`: `getting-started`, `feature-lifecycle`, `issue-execution`, `tdd-micro-cycle`, `recovery`
  - `reference`: `cli`, `slash-commands`, `config`, `state-and-ledger`, `tome`
  - `explanation`: `architecture`, `data-and-governance`, `process-and-safety`
  - `tutorial`: none today (flat quadrant; may grow to a `ThemeGroup` when ≥5 single-entry pages would justify one)
- **Cardinality**: a `Capability` in the `how-to`, `reference`, or `explanation` quadrants MAY carry a `ThemeGroup`; a `Capability` in the `tutorial` quadrant cannot (its `group` is `null`).
- **Semantics**: a theme is a sub-directory under a quadrant that groups pages with a common audience or use case. C1 maps a capability to a `ThemeGroup` deterministically (e.g., `deviate explore` → `feature-lifecycle`); C2-C5 honor the `target_file` path that includes the theme sub-dir. C7 pre-creates the theme sub-dirs, the per-quadrant `<quadrant>/index.md` landing page, the per-quadrant `<quadrant>/_meta.yml` sidebar manifest, and the per-theme `<quadrant>/<theme>/_meta.yml` ordering files on first scaffold. C6 re-derives the IA from the on-disk `_meta.yml` files to detect drift between the classifier-emitted ordering and the rendered sidebar. The per-quadrant `<quadrant>/_meta.yml` MUST have `index.md` as its first `pages:` entry (the `index-first` ordering invariant).

### DocPage
- **Attributes**: `path` (relative to `apps/docs/src/content/docs/`; for content pages this is `<quadrant>/[<theme>/]<name>.md`; for the per-quadrant landing page this is `<quadrant>/index.md` — the per-quadrant navigation pivot, NOT a legacy `<quadrant>/intro.md`), `frontmatter` (TomeFrontmatter, now nine fields including `prev` / `next`), `content` (markdown body), `last_verified_at`, `verified_sha`, `related_issues[]`
- **Relationships**:
  - lives in one `StarlightQuadrant` (root or theme sub-dir)
  - produced/updated by exactly one writer (C2-C5) based on `doc_type`
  - linked to adjacent `DocPage`s in the same theme via frontmatter `prev` / `next`

### TomeFrontmatter
- **Attributes** (nine fields; the two new in this iteration are bolded):
  - `title` (string)
  - `description` (string)
  - `doc_type` (DocType)
  - `status` (`draft` | `reviewed`)
  - `last_verified_at` (date)
  - `verified_sha` (string)
  - `related_issues[]` (list of issue IDs)
  - **`prev`** (path | null) — prior page in the reading order; `null` for the per-quadrant `<quadrant>/index.md` (one per quadrant; navigation pivot), the first page in a theme, or other cross-cutting pages
  - **`next`** (path | null) — next page in the reading order; `null` for the last page in a theme
- **Relationships**:
  - embedded in every `DocPage`
  - schema declared in two places: C7's `content.config.ts` (Starlight-side) and inline in C2-C5 prompts (LLM-side); both must declare the same nine fields
  - `prev` / `next` are emitted by C2-C5 from the `Capability` row's `parent` / `next` fields; verified by C6 against the on-disk `<quadrant>/_meta.yml` (per-quadrant) AND `<quadrant>/<theme>/_meta.yml` (per-theme) `pages:` ordering

### VerificationReport
- **Attributes**: `pass_items[]`, `fail_items[]` (per-check, including `[FAIL-LENGTH]`, `[FAIL-IA]`, and `[FAIL-INDEX-FIRST]` for `_meta.yml` index-first ordering drift), `boundary_violations[]`, `recommended_files[]`
- **Relationships**:
  - produced by C6 (Tome Verifier)
  - consumed by humans (no auto-routing to writers)

### StarlightQuadrant (enum)
- **Values**: `tutorials`, `how-to`, `reference`, `explanation`
- **Cardinality**: 1:1 with writer components C2-C5
- **Ownership**: directory path under `apps/docs/src/content/docs/<quadrant>/` (root or theme sub-dir). The per-quadrant `<quadrant>/index.md` is the navigation pivot (C2-C5 own the content; C7 only scaffolds a minimal landing on first run). The per-quadrant `<quadrant>/_meta.yml` is C7's territory (the canonical sidebar manifest). The per-theme `<quadrant>/<theme>/_meta.yml` is C7-created but C2-C5 append to its `pages:` list when they add a page.

## Entity-Relationship Summary

```
Commit ──1..n──> Capability ──1──> DocType ──1──> Writer (C2-C5) ──1──> DocPage
                       │              │                                    │
                       │              │                                    ▼
                       │              │                              TomeFrontmatter
                       │              │                              (nine fields,
                       │              │                               incl. prev/next)
                       │              ▼
                       ├──> Action ──> routes to writer | halts C1 | no-op
                       │
                       ├──> ThemeGroup (when group ≠ null; writer writes under <quadrant>/<group>/)
                       │
                       ├──> parent ──> Capability (prior page in reading order; null for intros/first-in-theme)
                       │
                       └──> next   ──> Capability (next page in reading order; null for last-in-theme)

ClassificationReport ──1──> Capability[]  (transient; ordered by layer_order within group)
DocPage ──1──> TomeFrontmatter
DocPage ──1──> StarlightQuadrant
DocPage ──prev/next──> DocPage  (within the same theme; bidirectional pointer)
VerificationReport (transient, output of C6)
```

## Delta from Prior Version

- **Added**: `ThemeGroup` (new enum; one per quadrant grouping; backs the IA contract introduced in `specs/_product/architecture.md` §3.1 and §3.2)
- **Modified**: `Capability` (gains `layer_order`, `parent`, `next`, `group`); `DocPage` (gains theme sub-dir path semantics); `TomeFrontmatter` (gains `prev` / `next`; now nine fields, was seven); `VerificationReport.fail_items` (gains `[FAIL-LENGTH]` and `[FAIL-IA]` finding kinds)
- **Removed**: none
- **Total entity count**: 9 entities + 1 new enum = 10 entities; 2 of 9 entities modified

`[yellow]DOMAIN_MODEL_DELTA[/]` — flagged for HITL review per architecture-skill invariant 5.
