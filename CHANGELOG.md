# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
