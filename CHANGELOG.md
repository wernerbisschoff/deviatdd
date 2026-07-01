# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Tome parser out of sync with the v1.2.0 IA-extended schema**: `src/deviate/tome/parser.py` declared `_EXPECTED_COLUMNS = 7` while the schema in `src/deviate/prompts/commands/tome-classify.md` and `specs/_product/architecture.md:143` requires 11 columns (the original seven plus the four IA fields `layer_order`, `parent`, `next`, `group`). Every v1.2.0-format report was silently parsed as zero rows, so `deviate tome write --from-report <path>` exited with `DONE 0` on a real report. The parser now expects 11 columns, exposes the four IA fields on `CapabilityRow` (writers and the verifier consume them), and remains backward-compatible with older 7-column reports.
- **Tome fan-out unkillable on Ctrl+C**: `src/deviate/tome/{batch,dispatch}.py` left worker threads running until each subprocess hit its 600-second per-row timeout; a single Ctrl+C during a long fan-out could leave the user waiting ten minutes before the process exited. The dispatch module now wraps every backend invocation in `subprocess.Popen` and tracks each Popen in a module-level `_RUNNING_PROCS` set, the batch module installs a SIGINT handler that sets a cancellation flag and calls `kill_all_running_procs()` (best-effort `proc.kill()` on every tracked handle), the dispatch loop polls the flag and breaks early, and the executor drains via `shutdown(wait=True, cancel_futures=True)`. The CLI surfaces a clear `INTERRUPTED` summary line and exits **130** (POSIX SIGINT convention) instead of 0.
- **Tome writer templates fence their own output**: `src/deviate/prompts/commands/tome-{classify,verify-docs,write-tutorial,write-how-to,write-reference,write-explanation}.md` wrapped their output templates in ` ```markdown ... ``` ` fences inside `<output_format>` blocks, causing the writer agents to mimic the fence and emit the markdown page as a fenced code block instead of as raw markdown. The fences are now removed; each template leads with "Present the final response as the raw markdown page (no surrounding fenced code block)".

### Changed
- `deviate setup` on the `tome` branch re-installs the seven `/tome-*` slash commands (C1–C7) to all four supported agent directories (`.claude/commands/`, `.opencode/commands/`, `.factory/commands/`, `.pi/prompts/`) and rewrites the project-root `.gitignore` with the matching `*/commands/tome-*.md` and `*/prompts/tome-*.md` exclusions so the installed files are not committed. Mirrors the `main` behaviour for the core `deviate-*` family and keeps the Tome subsystem fully integrated into the `deviate setup` flow on this branch.
### Removed
- Tome subsystem from `main`: the seven `/tome-*` slash commands (`tome-classify`, `tome-setup`, `tome-verify-docs`, `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation`) and their agent-mirror copies under `.claude/commands/`, `.factory/commands/`, `.pi/prompts/`; the pure-Tome specs (`specs/_product/architecture.md`, `domain-model.md`, `release-next.md`, `flows/flows-tome.md`), exploration notes (`specs/explore/tome-subsystem.md`), the `011-tome-subsystem-v1` issue file and plan dir; the FLOW-04..FLOW-10 entries in `_product/flows/index.md`; the `_ensure_root_gitignore` Tome patterns; the Feature issue template Tome checkbox; the `_TOME_LAYER_SKILLS` test trio in `tests/test_cli/test_init.py`; the Tome fixture path in `tests/test_micro/test_judge.py`; and the Tome illustrative examples in `deviate-review` (canonical + 3 agent mirrors). Tome work continues on the `tome` branch.
### Added
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) running ruff lint,
  ruff format check, and pytest on push to `main` and on pull requests.
- Bats end-to-end smoke suite at `tests/e2e/` covering the installed `deviate`
  CLI binary: `--version`, `--help`, macro / meso / micro subcommand
  discoverability, and unknown-command rejection.
- Issue templates (`.github/ISSUE_TEMPLATE/bug.md`,
  `.github/ISSUE_TEMPLATE/feature.md`) and a pull request template
  (`.github/PULL_REQUEST_TEMPLATE.md`) to standardize contributions.
- This `CHANGELOG.md`.
- Community health files: `CONTRIBUTING.md` (derived from
  `specs/constitution.md` and `AGENTS.md`, covering setup, branch
  strategy, commit conventions, PR workflow, test discipline, spec
  alignment, and slash-command edit policy), `CODE_OF_CONDUCT.md`
  (Contributor Covenant v2.1), and `SECURITY.md` (private disclosure
  via GitHub Security Advisories, supported-versions policy, 90-day
  coordinated-disclosure window, and explicit in-scope / out-of-scope
  threat model).
- `/tome-classify --codebase` mode for whole-codebase ingest (cold-start / retroactive docs). Walks manifests, source tree, CLI definitions, config schemas, and public API surface; emits an exhaustive capability table; pre-marks existing valid docs as `update`. Documented in `specs/_product/architecture.md` §3.1 and `specs/_product/domain-model.md` `ClassificationReport.mode`; verifier (C6) handles the new evidence source by reading source files directly.
- **Tome IA landing-page contract** (C2-C5 / C6 / C7 lockstep): every quadrant now has a per-quadrant landing page at `<quadrant>/index.md` (Starlight convention; the per-quadrant navigation pivot). The per-quadrant sidebar manifest lives at `<quadrant>/_meta.yml` (Starlight's canonical location) with `pages: [index.md, ...theme-dirs]` — the `index-first` ordering invariant. The root `apps/docs/src/content/docs/index.md` leads with an intro section and a `## Quadrants` section that links to each `<quadrant>/index.md`. C2-C5 (writers) own the content of `<quadrant>/index.md` and may append to the per-theme `<quadrant>/<theme>/_meta.yml` `pages:` list when they add a page; C7 (`/tome-setup`) is the only writer of the quadrant-level `<quadrant>/_meta.yml`, the root `index.md`, and `content.config.ts`. The verifier (`/tome-verify-docs`) enforces the contract via three new sub-checks in Check 6 (IA reachability) and a new `[FAIL-INDEX-FIRST]` finding kind for `_meta.yml` ordering drift. On idempotent re-runs, `/tome-setup` migrates legacy `<root>/_meta/<quadrant>.yml` files to `<quadrant>/_meta.yml` and renames legacy `<quadrant>/intro.md` files to `<quadrant>/index.md` (preserving content). All seven Tome prompts and the four `specs/_product/*.md` contract files (`architecture.md`, `domain-model.md`, `flows-tome.md`, `release-next.md`) were updated in lockstep; none of the on-disk `apps/docs/src/content/docs/` pages were touched.
- **Documentation site scaffold at `apps/docs/`** (Astro 7 + `@astrojs/starlight`
  0.41). The 56 markdown pages previously committed under
  `apps/docs/src/content/docs/{tutorials,how-to,reference,explanation}/` now
  render as a static site served from `apps/docs/dist/`. The `docs` content
  collection is schema-validated against `apps/docs/src/content.config.ts`,
  which declares Diátaxis `doc_type`, `status`, and provenance fields
  (`last_verified_at`, `verified_sha`, `related_issues`); `docsLoader()` from
  `@astrojs/starlight/loaders` is wired for the Astro Content Layer. Root
  `mise.toml` exposes four aggregator tasks — `docs` (dev server),
  `docs:install`, `docs:build`, `docs:preview` — that delegate to the
  per-directory `apps/docs/mise.toml`. Verified locally: 56 pages built,
  Pagefind search index generated, sitemap emitted. The `/deviate-*/tome-*`
  slash commands remain unaffected; this is renderer-only and orthogonal to
  the CLI surface documented in Part 1 of `specs/DeviaTDD-api.md`.
- **Docs audit pass: 19 broken internal links rewritten and the deprecated
  `apps/docs/src/content/docs/how-to/specify.md` page removed.** Each broken
  cross-link (typo `/how-to/ad-hoc` → `/how-to/adhoc` ×3, plus redirects
  to the closest existing page where no clean substitute existed for
  `/explanation/hitl-gate-{1,2,3}` → `/explanation/hitl-gates`,
  `/reference/deviate-*-cli` → `/reference/cli`,
  `/explanation/{complexity-gate,vertical-slice-mandate}` →
  `/explanation/three-layer-architecture`, and plain-text strips where no
  good substitute existed) lands as a meaningful navigation surface for
  the reader. `specify.md` was removed because the SPECIFY phase was
  deprecated in v2.0 (absorbed into `/deviate-shard`); its two reverse
  links in `how-to/adhoc.md` and `how-to/intro.md` were rewritten to
  `/how-to/plan` with an inline pointer to the v2.0 CHANGELOG note.
  Verified by re-running `astro build`: 56 HTML pages emit, zero
  link-internal-broken warnings.

### Fixed
- **Missing landing page at `apps/docs/src/content/docs/index.md`** —
  discovered during the first `mise run docs` session: the root URL
  `/` 404'd because none of the four Diátaxis quadrant directories
  carry an `index.md` at the docs root. Added a Diátaxis-oriented
  landing page that links into the four quadrant intros and documents
  the `verified_sha` / `related_issues` provenance contract. Verified
  via `npm run build`: 57 HTML pages now emit (was 56); `curl -I http://localhost:4321/` returns 200 after dev-server hot reload.

### Changed
- Removed all references to flows (FLOW-04..FLOW-10, `specs/_product/flows/flows-tome.md`) from the seven Tome subsystem prompt bodies under `src/deviate/prompts/commands/tome-*.md`. Flows remain as documentation artifacts under `specs/_product/flows/`; the prompts now reference `/tome-classify`, `/tome-write-tutorial`, `/tome-write-how-to`, `/tome-write-reference`, `/tome-write-explanation`, `/tome-verify-docs`, and `/tome-setup` directly, and read source-of-truth inputs only from `specs/_product/architecture.md` and `specs/_product/domain-model.md`.
- README reframed around the four-layer architecture (Product · Macro ·

  Meso · Micro). The Product layer (FLOW-01 flows → FLOW-02 architecture →
  FLOW-03 release) was previously absent from the README; it is now
  presented as an optional layer above Macro and reachable through
  `/deviate-flows`, `/deviate-architecture`, and `/deviate-release`.
  The Macro section now surfaces the dual path (full `explore → research
  → prd → shard` *or* `adhoc` shortcut); the Micro section surfaces the
  TDD cycle *or* `/deviate-execute` alternative, including the
  Green → Judge → Green TRAIN loop on `JUDGE_REJECTED`. The "Workflow at
  a Glance" table enumerates every phase with its slash command, the
  artifact committed, and what the human reviews at each gate —
  including the `tasks.md` execution blueprint produced by
  `/deviate-tasks`. Prompt-count claim corrected from 29 to 31
  (24 `deviate-*` + 7 `tome-*`).
- `specs/DeviaTDD-architecture.md` and `specs/DeviaTDD-api.md` aligned with
  the four-layer framing and the corrected Green → Judge → Green TRAIN
  semantics. Architecture spec: Section 1 ASCII diagram now includes the
  Product layer above Macro; Section 2.3 JUDGE/TRAIN phase block describes
  the `git reset --hard <red_sha>` rollback + `force_transition_to("GREEN")`
  retry flow (replacing the prior incorrect `git revert` description);
  Section 3.5 EDD rewritten to call out the Green → Judge → Green loop by
  name; Section 4 micro cycle diagram carries the explicit JUDGE → GREEN
  TRAIN arrow distinct from the YELLOW → GREEN (rejected) branch; new
  Section 5.0 Product Layer Phase Prompts documents FLOW-01..FLOW-03 with
  precondition gates (`[red]FLOWS_MISSING[/]`,
  `[red]ARCH_OR_FLOWS_MISSING[/]`); Section 6 gates diagram shows the
  Product-layer conversational checkpoints as soft gates; Section 8.5
  invariant tightened to the loop name. API spec: command count corrected
  from 32 to 31 in three places (Bootstrap description, output artifacts
  list, file tree blueprint — `deviate-content` removed since it is not
  in the canonical commands directory); new Section 1.5 Product Layer
  documents the three agent-skill commands and their downstream
  `flow_refs:` consumption; `IssueRecord.flow_refs` field documented in
  Section 3 with the `^FLOW-\d{2,}$` validation rule; `deviate run`
  description now uses the Green → Judge → Green loop name and spells
  out the feedback source precedence; `deviate execute pre/post`
  documented with the EXECUTE → JUDGE → EXECUTE retry pattern.
- Bats suite relocated from `tests/test_e2e/` to the canonical `tests/e2e/`
  path referenced by `mise run test-e2e` and `specs/constitution.md`. The
  stale macro-workflow tests have been replaced with a focused CLI smoke
  suite that matches the current `pre|post` subcommand shape.
- `AGENTS.md` now mandates a `## 📝 CHANGELOG Discipline` rule (mirrored
  in `specs/constitution.md` §5 Definition of Done and the PR template's
  CHANGELOG checkbox): user-visible changes must append a bullet to
  `[Unreleased]` in the same commit. Exempts docs-only, test-only,
  CI/tooling, and behavior-preserving refactors. Constitution bumped to
  0.5.0.
- README onboarding flow corrected: the user-facing entrypoint is the
  `/deviate-<phase>` slash commands installed by `deviate setup`, not
  direct `deviate <phase>` CLI invocations. Quickstart rewritten to
  show `deviate setup --agent <name>` → `/deviate-*`; the `Commands`
  section replaced with a `Slash Commands` section grouped by layer.
  Removed stale references to `deviate specify` (deprecated; the SPECIFY
  phase was absorbed into `deviate shard` per
  `src/deviate/cli/meso.py::_specify_legacy` and `specs/DeviaTDD-api.md`)
  and dropped the `M[specify]` node from the architecture mermaid.
  Quickstart also no longer shows `deviate init` — `deviate init` is the
  engine backing the `/deviate-init` slash command, not a user-facing
  shell command; `deviate setup --agent <name>` is the single one-shot
  bootstrap that scaffolds `.deviate/`, `specs/constitution.md`,
  governance blocks, and installs `/deviate-*` slash commands.
- **Tome subsystem IA contract: reader-flow and theme sub-dirs across all four quadrants.** `/tome-classify` now emits four new IA columns on every capability row — `layer_order` (int), `parent` (path | null), `next` (path | null), and `group` (ThemeGroup | null) — derived deterministically from the capability name (e.g., `deviate explore` → `layer_order: 1, group: feature-lifecycle, parent: null, next: how-to/feature-lifecycle/research.md`). `/tome-write-{tutorial,how-to,reference,explanation}` consume those columns to emit `prev` / `next` Starlight frontmatter on every page and to honor `target_file` paths that may include a theme sub-dir (e.g., `how-to/tdd-micro-cycle/red.md`). Per-writer length budgets enforced: how-to ≤ 80 lines, tutorial ≤ 120, explanation ≤ 90; reference = tables dominate with no narrative paragraph > 2 sentences. `/tome-setup` pre-creates the canonical theme sub-dirs under each quadrant and the per-theme `_meta/<theme>.yml` ordering files. `/tome-verify-docs` gains two new checks: IA reachability (every page MUST appear in its quadrant's `_meta/<theme>.yml` ordering; every page MUST carry `prev` / `next` or be a navigation pivot like `intro.md` or `index.md`) and length budget (drift beyond budget is a `[FAIL-LENGTH]` finding). See `specs/_product/architecture.md` §3.1 / §3.2 / §3.3 / §3.4 and `specs/_product/domain-model.md` §Capability / §ThemeGroup for the full contract.

## [2.0.0] - 2026-06-28

### Added
- Three-layer agent orchestration framework: Macro (Explore → Research →
  PRD → Shard), Meso (Plan → Tasks), Micro (RED → GREEN → JUDGE →
  REFACTOR). Strict phase gates; no layer may be skipped.
- 30 slash commands spanning macro, meso, micro, and Tome subsystems
  (`src/deviate/prompts/commands/`).
- Tome subsystem v1: seven prompt-only Diátaxis-aware documentation
  curation skills (FLOW-04 .. FLOW-10).
- Multi-agent backend support: opencode, claude, droid, pi.
- Append-only JSONL ledger protocol with `merge=union` in
  `.gitattributes` for safe concurrent feature branches.
- HITL gates at three checkpoints (Gate 1: design approval; Gate 2:
  contract sign-off; Gate 3: final merge audit). No programmatic bypass.
- Per-phase model routing via `.deviate/config.toml [models]` with
  `default` key + phase-specific overrides.
- Constitution and governance bootstrap via `deviate init` / `deviate setup`.
- Pre-commit (`mise run check`) and pre-push (`mise run test`) git hooks.
- `LICENSE` (MIT), `README.md` with architecture diagram and quickstart.

### Notes
- v2.0 ships a v0.x-quality codebase with a governance-first approach;
  expect rapid iteration under the new CHANGELOG + CI discipline.
- Repo transitioned from internal solo development to public launch
  readiness in June 2026.
