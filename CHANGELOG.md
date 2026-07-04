# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.4.0] - 2026-07-04
### Changed
- `/deviate-architecture` discovery step now follows "grill with docs"
  discipline: one question at a time with a recommended answer,
  dependency-ordered (components before contracts before ownership),
  and at most one term-challenge per turn when the user's language
  conflicts with existing `domain-model.md` or `architecture.md`
  definitions.
- `/deviate-flows` discovery step now follows the same one-question-at-a-time
  discipline with recommended answers, dependency-ordered (Actor before
  Domain before Trigger before Happy Path).
- `/deviate-architecture` now produces Architectural Decision Records (ADRs)
  as a `## Architectural Decision Records` section within `architecture.md`.
  ADRs are one-paragraph entries gated on three criteria: hard to reverse,
  surprising without context, and the result of a real tradeoff. No ADR is
  written when any criterion is missing.

## [2.3.0] - 2026-07-04
### Added
- `deviate merge` command (`/deviate-merge` slash command) for marking issues
  COMPLETED in the ledger after an external merge (e.g. the `/squash-merge`
  skill). Writes a full IssueRecord with all required fields, unlike bare
  `{issue_id, status, timestamp}` transitions that are silently dropped by
  `resolve_issue_record`. Supports `--delete-branch` and `--delete-worktree`
  flags for post-merge cleanup.

### Fixed
- `resolve_issue_record` now tolerates sparse/bare ledger transitions (e.g.
  `{"issue_id":"ISS-001","status":"COMPLETED","timestamp":"..."}`) by merging
  them with the last fully-resolved record instead of silently dropping them.
  Previously, bare COMPLETED entries written by external tools like
  `/squash-merge` caused `_is_issue_completed` to return `False`, blocking
  downstream issues that depend on the completed one.

### Changed
- `deviate setup` now ensures a symlink relationship between `CLAUDE.md` and
  `AGENTS.md` via `_linkify_governance_files`. If neither file exists, an empty
  `CLAUDE.md` is created and `AGENTS.md` is symlinked to it. If exactly one
  exists, the other is symlinked to it. If both exist as regular files, they are
  left unchanged. Governance seed writes (libref, graphite) now target only the
  canonical file to avoid double-writing through symlinks. The `deviate init pre`
  command uses the same shared helper.
- Commit messages from `deviate` phase commands (`explore post`, `research post`,
  `prd post`, `shard post`, `plan post`, `tasks post`, `constitution post`) now
  respect the project's emoji convention. A new `convention.py` module detects
  emoji usage from CONTRIBUTING.md (or `.commit-convention.md`) and falls back
  to sampling recent git history. When detected, the appropriate emoji is
  prepended to the conventional-commit message (e.g. `📚 docs(epic): create prd.md`).
- `deviate specify` claim commit now respects the project's emoji convention
  via `format_commit_message()`, matching the behavior of all other phase
  commits (e.g. `🔧 chore(001-001): claim ISS-001` when emoji prefixes are
  detected).
- Micro-layer commit messages (`deviate red post`, `deviate green post`,
  `deviate refactor post`, `deviate execute post`, `deviate e2e post`,
  `deviate hotfix post`, and judge feedback commits) now respect the project's
  emoji convention via `format_commit_message()` in `_commit_phase()`, matching
  the behavior already present in macro and meso layer commits.
- `/deviate-prd` now explicitly forbids intermediate `git add`/`git commit` between
  `prd_generation` and `post_script`; the post-script is the sole commit authority.
  The `IMPORTANT` note in the `post_script` step also corrected: pre-commit hooks run
  ruff only, not the test suite — timeout guidance updated from 180s to 60s.

## [2.2.0] - 2026-07-02

### Removed
- Tome subsystem from `main`: the seven `/tome-*` slash commands (`tome-classify`, `tome-setup`, `tome-verify-docs`, `tome-write-tutorial`, `tome-write-how-to`, `tome-write-reference`, `tome-write-explanation`) and their agent-mirror copies under `.claude/commands/`, `.factory/commands/`, `.pi/prompts/`; the pure-Tome specs (`specs/_product/architecture.md`, `domain-model.md`, `release-next.md`, `flows/flows-tome.md`), exploration notes (`specs/explore/tome-subsystem.md`), the `011-tome-subsystem-v1` issue file and plan dir; the FLOW-04..FLOW-10 entries in `_product/flows/index.md`; the `_ensure_root_gitignore` Tome patterns; the Feature issue template Tome checkbox; the `_TOME_LAYER_SKILLS` test trio in `tests/test_cli/test_init.py`; the Tome fixture path in `tests/test_micro/test_judge.py`; and the Tome illustrative examples in `deviate-review` (canonical + 3 agent mirrors). Tome work continues on the `tome` branch.
- YELLOW phase and Tamper Guard: removed the conditional YELLOW test-amendment phase, `TamperGuard`/`TamperContext`/`TamperVerdict` classes, `yellow_pre`/`yellow_post` commands, `deviate-yellow` skill, auto yellow prompt, `yellow_trigger` field from `HandoverManifest`, `yellow_triggered` from `SessionState`, and YELLOW/YELLOW_APPROVED/YELLOW_REJECTED from `TaskRecord.status`. JUDGE now handles scope verification — GREEN may only write to `src/` and permitted paths; modifications to `tests/`, `specs/`, or config files are flagged as scope violations.

### Added
- `deviate setup` now installs slash commands to `.omp/commands/` (Oh-My-Pi),
  in addition to the existing `.claude/commands/`, `.opencode/commands/`,
  `.factory/commands/`, and `.pi/prompts/` targets. `omp` is now a valid
  `--agent` choice and maps to the `pi` backend.
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
- `mise run test-affected` task: runs only tests touched by current changes
  via `pytest --testmon-forceselect`. Companion to the existing
  `mise run test` full-suite task; the populated `.testmondata` file
  makes the selection fast on every subsequent run.

### Changed
- Removed all references to flows (FLOW-04..FLOW-10, `specs/_product/flows/flows-tome.md`) from the seven Tome subsystem prompt bodies under `src/deviate/prompts/commands/tome-*.md`. Flows remain as documentation artifacts under `specs/_product/`; the prompts now reference `/tome-classify`, `/tome-write-tutorial`, `/tome-write-how-to`, `/tome-write-reference`, `/tome-write-explanation`, `/tome-verify-docs`, and `/tome-setup` directly, and read source-of-truth inputs only from `specs/_product/architecture.md` and `specs/_product/domain-model.md`.
- Stripped the framework-internal `FLOW-01/02/03` phase identifiers from the three Product-layer slash-command descriptions (`/deviate-flows`, `/deviate-architecture`, `/deviate-release`) and rewrote them as end-user action phrases ("Author customer flows…", "Author the cross-epic architecture contract…", "Plan the next coherent release…"). Generic terminology that any project would call on — the `flow_refs:` issue-frontmatter field, the `--flow-ref` CLI flag, the `**Flow References**` task anchor, the `Flow Coverage` review domain — is preserved verbatim. Internal anchors in `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, and prompt bodies remain unchanged.
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
- README `Why Each Phase Exists` rationale now annotates each architectural
  claim with inline article citations (Agile-V/SCOPE-V, IACDM, PRIME,
  State Contamination, SDD, Spec Kit, Mise en Place, Runtime Decomp, TDAD,
  TDFlow, TDDev, TDD Governance, TDAID, Red-Green-Refactor Agents, TDD
  Agent Dev, Definitive SDD 2026, Acceptance Test Gen, LLM BDD, Vibe vs
  Agentic, UCCI, RoBatch, Agentic AI Survey) and adds a `## References`
  section consolidating 21 source URLs. DeviaTDD-original claims (Yellow
  test-amendment gate, Product layer optionality, Flows / Architecture /
  Release triad, 4–8 task count, three-gate count, append-only ledger
  rationale, `flow_refs:` frontmatter convention, ledger-derived IDs,
  per-issue Plan cadence, Adhoc complexity classifier, deriving CLI state
  from the ledger) are tagged `_(design proposal)_` and grouped under
  `References § Gaps` for transparency.
- Pre-commit hook (`.githooks/pre-commit`) now lints and format-checks
  only the staged + unstaged `.py` files (was: whole repo via
  `mise run check`). Early-exits cleanly on docs-only, prompt-only, or
  non-Python commits. Adds `set -o pipefail` and the `GIT_DIR` env-var
  guard.
- Pre-push hook (`.githooks/pre-push`) now lints, format-checks, and
  runs `mise run test-affected` against the `.py` files changed since
  the upstream branch (was: full test suite via `mise run test`).
  Adds the `GIT_DIR` env-var guard that the previous script was
  missing, plus `set -o pipefail`.
- `mise run test` and the CI pytest step now pass `--testmon-noselect`
  to pin full-suite behavior. Without the flag, `pytest-testmon`'s
  default selection would silently narrow both commands once
  `.testmondata` exists. New dev dep `pytest-testmon>=2.2` added to
  both `[project.optional-dependencies].dev` and
  `[dependency-groups].dev`; `.testmondata` added to `.gitignore`.
- Phase prompts now prefer the codebase-index MCP tools (`codebase_search`,
  `codebase_peek`, `implementation_lookup`, `call_graph`) over `grep` /
  `glob` for semantic code discovery, symbol location, and call-graph
  traversal. A new universal invariant #9 in
  `src/deviate/prompts/core/core.md` propagates the mandate to every
  `auto/*` phase via `load_template`; the discovery-bearing command
  variants (`deviate-adhoc`, `deviate-explore`, `deviate-hotfix`,
  `deviate-plan`) and the meso `Deterministic Discovery` discipline now
  lead with codebase-index tools, with `grep` / `glob` / `Read` demoted
  to a documented last-mile fallback when the MCP is unavailable. 10 prompt files affected.
- `/deviate-research` now dispatches two sequential subagent stages instead of three parallel ones. The former Alpha (architecture options) and Beta (data modeling) subagents are merged into a single **AlphaBeta** subagent that produces the architecture and data-model fragments in one coherent pass, with data modeling explicitly deriving from the recommended architecture (not from `explore.md` in isolation). The adversarial **Gamma** subagent now runs strictly AFTER AlphaBeta returns and consumes its full fragment output, fixing a latent bug where Gamma was instructed to read Alpha/Beta outputs that ran in parallel with it. Updated files: `src/deviate/prompts/commands/deviate-research.md` (subagent blueprint directory, `map_phase_sequential_fork` step, `reduce_phase` merge language, intro) and `src/deviate/prompts/auto/research.md` (`sequential_fork` step, intro). Command prompt version bumped 2.0.0 → 2.1.0.

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
