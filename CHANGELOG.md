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

### Changed
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
