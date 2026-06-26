# Release: Tome Subsystem

## Goal
- Ship Tome, a manual post-merge documentation curator for Starlight docs sites that classifies each commit (or branch-level diff) against the four Diátaxis quadrants and runs only the writer skills the classifier selects.
- v1 introduces seven prompt-only skills under `src/deviate/prompts/skills/tome-*/`; the DeviaTDD repo's Python 3.13 + Typer stack is preserved without modification.

## Constraints
- Prompt-only in v1: each Tome skill lives as a static `SKILL.md` under `src/deviate/prompts/skills/tome-*/`. Python modules, Typer sub-apps, and runtime code remain out of scope for this iteration.
- The CLI surface (`deviate tome <phase>`) is deferred to a future iteration; v1 is prompt-only and gathers usage data first (per `specs/_product/architecture.md:21`).
- `FLOW-09` (Tome Verify Docs) emits a human-readable report. Verifier outputs are not auto-routed back to writers; humans drive the verification loop (per `specs/_product/architecture.md:20`).
- Each skill inlines the schemas it needs. v1 ships without a shared contracts module (`tome/contracts.py` or equivalent) (per `specs/_product/architecture.md:19`).
- Writer quadrant discipline: each of `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation` is confined to its assigned quadrant. Writers that need to touch a different quadrant flag back to `tome-classify` for re-classification (per `specs/_product/architecture.md:64`).
- Tome output is decoupled from DeviaTDD's runtime stack. Skill outputs (Starlight sites, `apps/docs/`, `content.config.ts`, `.astro` files) live in target repos that consume the skills, not in the DeviaTDD repo (per `specs/_product/architecture.md:18`).
- Frontmatter schema parity: the field set declared in `apps/docs/src/content.config.ts` agrees field-for-field with the inline schema in the C2-C5 prompts. Drift between the two surfaces as a `FLOW-09` finding (per `specs/_product/architecture.md:149`).
- The DeviaTDD repo keeps its Python 3.13 + Typer stack; new skills ship as static `SKILL.md` files under `src/deviate/prompts/skills/tome-*/` and introduce no `package.json`, `astro.config.mjs`, or Node toolchain (per `specs/_product/architecture.md:17` and `:212`).

## Included Flows
| Flow ID | Name | Notes |
|---|---|---|
| FLOW-04 | Tome Classify | Entry ticket for writers and `FLOW-09`; emits capability table with `doc_type` and action enum |
| FLOW-05 | Tome Write Tutorial | Quadrant writer for `tutorials/` |
| FLOW-06 | Tome Write How-To | Quadrant writer for `how-to/` |
| FLOW-07 | Tome Write Reference | Quadrant writer for `reference/` |
| FLOW-08 | Tome Write Explanation | Quadrant writer for `explanation/` |
| FLOW-09 | Tome Verify Docs | Cross-doc verifier; runs only after at least one of `FLOW-05..FLOW-08` produced a file |
| FLOW-10 | Tome Setup | Idempotent scaffold of `apps/docs/`; gates `FLOW-04` |

## Included Work
| Title | Type | Flow Refs | Status |
|---|---|---|---|
| Tome Subsystem | ADHOC | [FLOW-04, FLOW-05, FLOW-06, FLOW-07, FLOW-08, FLOW-09, FLOW-10] | planned |

## Deferred Epics
- `deviate tome <phase>` CLI surface — likely candidates after v1 usage data: C7 setup plus path and frontmatter validation for C2-C5 (per `specs/_product/architecture.md:21`)
- `<judge_feedback>` auto-routing from `tome-verify-docs` back to writers; the verifier remains a human-readable report only in v1 (per `specs/_product/architecture.md:20`)
- Shared `tome/contracts.py` (or equivalent) centralizing the schemas currently inlined in each skill prompt (per `specs/_product/architecture.md:19`)
- Per-quadrant sub-skills inside C2-C5 if v1 usage data shows writer outputs are too large for a single skill prompt
- LLM-driven constitution-style metadata for `apps/docs/` (out of scope for v1)
- `--merge-base` and `--working-tree` mode coverage in automated e2e tests; manual coverage only in v1

## Acceptance Criteria
- `deviate setup` installs the seven Tome skill directories under `src/deviate/prompts/skills/`: `tome-classify/`, `tome-write-tutorial/`, `tome-write-how-to/`, `tome-write-reference/`, `tome-write-explanation/`, `tome-verify-docs/`, `tome-setup/`, each containing a `SKILL.md` (per `specs/_product/architecture.md:36-116` and `specs/_product/domain-model.md:10-84`).
- `tome-setup` scaffolds `apps/docs/` with the four quadrant directories (`tutorials/`, `how-to/`, `reference/`, `explanation/`), `index.md`, `_meta/`, and `src/content.config.ts` extending `docsSchema()` with Tome frontmatter fields (`doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`); re-runs produce zero diff against committed state (per `specs/_product/flows/flows-tome.md:240-278` and `specs/_product/architecture.md:108-115`).
- `tome-setup`'s optional starter set (one architecture explanation, one config reference, one first-task how-to, one first-run tutorial) seeds by default and is suppressible via an opt-out flag (per `specs/_product/flows/flows-tome.md:267`).
- `tome-classify` in default `HEAD~1` mode emits a classification report whose capability table contains exactly the columns `capability`, `evidence`, `audience`, `doc_type`, `action`, `target_file`, `confidence` and whose `action` column is restricted to the enum `create | update | no-change | human-review | setup-required` (per `specs/_product/flows/flows-tome.md:22-28` and `specs/_product/architecture.md:46-55`).
- `tome-classify` accepts `<sha>`, `--merge-base`, and `--working-tree` modes; `--merge-base` produces a branch-level classification scoped to the cumulative diff from `main`'s merge-base to `HEAD` (per `specs/_product/flows/flows-tome.md:12-13` and `:35`).
- `tome-classify` emits a row whose `action` is `setup-required` and halts without proposing target files when `apps/docs/` is absent; emits `no-change` when all changes in the diff are internal-only; emits `human-review` when the target file collides with an existing page in the wrong quadrant (per `specs/_product/flows/flows-tome.md:31-34` and `specs/_product/architecture.md:50-54`).
- `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, and `tome-write-explanation` write exclusively to `apps/docs/src/content/docs/tutorials/`, `how-to/`, `reference/`, and `explanation/` respectively; each writer rejects any target path outside its quadrant and surfaces a boundary violation (per `specs/_product/flows/flows-tome.md:73-76`, `:113`, `:151`, `:189` and `specs/_product/architecture.md:64`).
- Every file emitted by a writer carries valid Tome frontmatter with the fields `title`, `description`, `doc_type`, `status`, `last_verified_at`, `verified_sha`, `related_issues`; the `doc_type` value matches the quadrant directory the file lives in (e.g., `tutorial` only inside `tutorials/`) (per `specs/_product/architecture.md:70-83` and `specs/_product/flows/flows-tome.md:70-80`).
- The field set in `apps/docs/src/content.config.ts` agrees field-for-field with the inline Tome frontmatter schema in the C2-C5 prompts; any drift between the two is flagged by `tome-verify-docs` as a finding (per `specs/_product/architecture.md:149`).
- `tome-verify-docs` runs after at least one of `FLOW-05..FLOW-08` has produced a file; emits a report with PASS items, FAIL items, boundary violations, and recommended files to commit; does not auto-route failures back to writers (per `specs/_product/flows/flows-tome.md:218-228` and `specs/_product/architecture.md:96-102`).
- All seven Tome skills run as LLM-mediated prompts; the DeviaTDD repo's Python 3.13 + Typer stack is preserved and no `package.json`, `astro.config.mjs`, or Node toolchain is added (per `specs/_product/architecture.md:17-21` and `:212`).