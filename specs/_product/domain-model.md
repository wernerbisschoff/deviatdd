# DeviaTDD Product Domain Model

**Last Updated**: 2026-06-26
**Source**: `specs/_product/architecture.md` §3 (Tome Subsystem)

---

## Entities

### Commit
- **Attributes**: `sha`, `message`, `changed_files[]`, `changed_tests[]`, `merged_diff` (or `branch_diff` for merge-base mode)
- **Relationships**:
  - has many `Capability` (1..n) — what changes the commit introduces that may need docs
  - input to `ClassificationReport`

### ClassificationReport
- **Attributes**: `change_summary`, `capabilities[]` (Capability list), `no_touch_list[]` (file paths), `mode` (commit | sha | merge-base | working-tree), `target_sha`
- **Relationships**:
  - produced by C1 (Tome Classifier)
  - consumed by C2-C5 (writers, via human handoff)
  - consumed by C6 (verifier, for boundary reconciliation)

### Capability
- **Attributes**: `capability` (string), `evidence` (string), `audience` (user | operator | contributor | internal), `doc_type` (DocType), `action` (Action), `target_file` (path), `confidence` (0.0-1.0)
- **Relationships**:
  - belongs to one `ClassificationReport`
  - routes to one writer (C2-C5) based on `doc_type`

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

### DocPage
- **Attributes**: `path` (relative to `apps/docs/src/content/docs/`), `frontmatter` (TomeFrontmatter), `content` (markdown body), `last_verified_at`, `verified_sha`, `related_issues[]`
- **Relationships**:
  - lives in one `StarlightQuadrant`
  - produced/updated by exactly one writer (C2-C5) based on `doc_type`

### TomeFrontmatter
- **Attributes**: `title`, `description`, `doc_type` (DocType), `status` (draft | reviewed), `last_verified_at` (date), `verified_sha`, `related_issues[]`
- **Relationships**:
  - embedded in every `DocPage`
  - schema declared in two places: C7's `content.config.ts` (Starlight-side) and inline in C2-C5 prompts (LLM-side)

### VerificationReport
- **Attributes**: `pass_items[]`, `fail_items[]`, `boundary_violations[]`, `recommended_files[]`
- **Relationships**:
  - produced by C6 (Tome Verifier)
  - consumed by humans (no auto-routing to writers)

### StarlightQuadrant (enum)
- **Values**: `tutorials`, `how-to`, `reference`, `explanation`
- **Cardinality**: 1:1 with writer components C2-C5
- **Ownership**: directory path under `apps/docs/src/content/docs/<quadrant>/`

## Entity-Relationship Summary

```
Commit ──1..n──> Capability ──1──> DocType ──1──> Writer (C2-C5) ──1──> DocPage
                       │
                       └──> Action ──> routes to writer | halts C1 | no-op

ClassificationReport ──1──> Capability[]  (transient)
DocPage ──1──> TomeFrontmatter
DocPage ──1──> StarlightQuadrant
VerificationReport (transient, output of C6)
```

## Delta from Prior Version

- **Added**: `Commit`, `ClassificationReport`, `Capability`, `DocType`, `Action`, `DocPage`, `TomeFrontmatter`, `VerificationReport`, `StarlightQuadrant` — all 9 entities are new in this version, introduced by the Tome subsystem.
- **Removed**: none.
- **Modified**: none.
- **Total entity count**: 9 new.

`[yellow]DOMAIN_MODEL_DELTA[/]` — flagged for HITL review per architecture-skill invariant 5.
