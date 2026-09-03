# Exploration: ponytail-pruning

## Problem Definition

[Statement]: The operator wants to (1) adopt ideas from the viral "ponytail" coding skill to prune excessive code, deciding whether to fold those ideas into the existing `/deviate-review` command or create a new `/deviate-ponytail` command; and (2) verify `/deviate-pr` works, uses GitHub or GitLab to create PR/MR, and produces a title and body that adhere to the commit convention so the PR can squash-merge into a commit message.

[Scope]: In-scope structural components verified across the scan:
- The existing slash commands under `src/deviate/prompts/commands/` (notably `deviate-pr.md`, `deviate-review.md`, `deviate-prune.md`).
- The PR/MR implementation in `src/deviate/cli/meso.py` (`_pr_pre`, `_pr_run`, `_resolve_pr_platform`, `_gitlab_push_options`, `_run_gh_pr_create`, `_pr_title`).
- The commit-convention helpers in `src/deviate/core/convention.py`.
- The review CLI in `src/deviate/cli/review.py`.
- The prompt template tests that pin "ponytail smallest-change" (`tests/unit/test_meso/test_auto_prompt_templates.py`).
- The PR/MR test coverage (`tests/unit/test_meso/test_pr_platform.py`, `tests/unit/test_cli/test_meso.py`, `tests/unit/test_cli/test_meso_contracts.py`, `tests/test_integration/test_meso_layer.py::TestPrRun`).
- The commit convention documented in `CONTRIBUTING.md`.
- The `constitution.md` governance constraints.

[Exclusions]: Explicitly out-of-scope boundaries: architectural decisions, design trade-offs, risk analysis, data modeling, and failure-mode speculation. Whether ponytail ideas should fold into `/deviate-review` or become `/deviate-ponytail` is a design decision deferred to the downstream `deviate-research` or `deviate-adhoc` skill. This document catalogs only what exists.

## Discovery Audit Results

### Verified Dependencies
- `typer>=0.12`: declared in `pyproject.toml` `[project] dependencies`; used in `src/deviate/cli/*.py` for CLI entry points.
- `rich>=13.0`: declared in `pyproject.toml`; used across CLI modules (e.g. `deviate.cli._common.console`).
- `pydantic>=2.0`: declared in `pyproject.toml`; used for `IssueRecord` and ledger validation in `src/deviate/state/ledger.py` and `src/deviate/cli/meso.py`.
- `pyyaml>=6.0.3`: declared in `pyproject.toml`; used for structured handover manifests.
- `pytest>=9.0.3`: declared in `pyproject.toml` `[dependency-groups] dev`; used in `tests/`.
- `ruff>=0.15.16`: declared in `pyproject.toml` `[dependency-groups] dev`; used for lint and format.
- `mise` tasks: declared in `mise.toml`; the repo-wide task runner (`mise run check`, `mise run test`, `mise run test-e2e`).

### Ghost Dependencies
- `gh` (GitHub CLI): referenced and invoked in `src/deviate/cli/meso.py::_run_gh_pr_create` (`cmd = ["gh", "pr", "create", ...]`). Not declared in `pyproject.toml` or `mise.toml`. Present as a system binary at `/Users/werner/.local/share/mise/installs/gh/latest/gh_2.95.0_macOS_arm64/bin/gh`. Declarative finding only — the CLI shells out to an external binary rather than shipping a Python GitHub client.
- `git`: referenced throughout `src/deviate/cli/meso.py` and `src/deviate/core/commit.py` via `subprocess.run(["git", ...])`. Not declared in `pyproject.toml`; provided by the host system (`/opt/homebrew/bin/git`).
- `bats`: declared as the E2E runner in `specs/constitution.md` §3 and invoked via `mise run test-e2e`; not declared in `pyproject.toml`. Provisioned by `mise.toml`.
- There is no Python package dependency that provides GitHub or GitLab client functionality in `src/deviate`. All platform interaction is via external `gh` and `git` binaries.

### Manifest Files Observed
- `pyproject.toml`: Packaging and dependency manifest for the `deviatdd` package; declares the `deviate` console script entry point.
- `mise.toml`: Task runner manifest declaring `check`, `test`, `test-e2e`, `lint`, `format`, and lifecycle tasks.
- `uv.lock`: Lockfile for the `uv`/`pytest`/`ruff` dependency set.
- `.env.example`: Template for environment variables.
- `CONTRIBUTING.md`: Documents the commit convention and the pull-request workflow.
- `specs/constitution.md`: The authoritative governance contract quoted below.

### Test Runner Configuration
- `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths = ["tests"]`.
- `specs/constitution.md` §3: "Test command: `pytest tests/ -v`", "Lint command: `ruff check .`", "E2E command: `bats tests/e2e/`".

### Manifest-Constitution Divergence
- None observed between the `[tool.pytest.ini_options] testpaths = ["tests"]` manifest entry and the constitution §3 "Test root: `tests/`" line. Both quote `tests/` consistently.
- The commit-convention template in `CONTRIBUTING.md` declares `<type>(<scope>): <description>` with no emoji marker. `src/deviate/core/convention.py` supports an emoji prefix (gitmoji) but returns a no-op (`detect_uses_emojis` → `False`) for this repository because `CONTRIBUTING.md` contains no Unicode emoji. Both behave consistently; no adjudication is made here.

## Constitution Quotes

Constitution excerpts quoted verbatim. No interpretation, inference, or classification. The `deviate-research` skill owns interpretation.
- **Architectural Principles**: "Four-Layer Architecture: Product (optional cross-product framing: Flows → Architecture → Release), Macro (feature scoping: Explore → Research → PRD → Shard), Meso (issue engineering: Plan → Tasks), Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR)."
- **Architectural Principles** (Git Isolation): "Every task loop executes on a clean git branch or worktree. Commits are automatic at each phase boundary."
- **Tech Stack Standards** (Backend): "Target: CLI application (`deviate`); Framework: Typer (CLI entry points) with Rich for terminal I/O."
- **Tech Stack Standards** (Database): "No persistent database runtime (all state tracked in JSONL ledgers and TOML config)."
- **Tech Stack Standards** (Tooling): "Package manager: `uv`; Test runner: `pytest`; Linter: `ruff` (lint + format); E2E testing: `bats` (Bash automated test system); Task runner: `mise` (see `mise.toml` for all tasks); Code quality gate: `mise run check`."
- **Testing Protocols**: "Test command: `pytest tests/ -v`; Lint command: `ruff check .`; E2E command: `bats tests/e2e/`."
- **Development Workflow** (Commit Convention): "Format: `<type>(<scope>): <description>`; Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`; Scope is the task ID (e.g., `T001`); Body wraps at 72 characters."
- **Development Workflow** (Review Process): "PR descriptions must reference the spec.md acceptance criteria."
- **Definition of Done**: "Committed with conventional message format (`test:`, `feat:`, `refactor:`, `docs:`)".

## Architectural Baselines

[Pattern_Over_Instance]: Only representative examples or base classes are listed, not every instance. All paths are strictly relative to `repo_root`.
- **Existing Architectural Patterns**: The CLI is a Typer application with per-command sub-apps in `src/deviate/cli/`. The `/deviate-pr` command is wired as `cli.command(name="pr", ...)(pr)` and `/deviate-review` as `review_app`. Commands live as markdown package resources under `src/deviate/prompts/commands/`. The `deviate-pr.md` frontmatter declares `name: deviate-pr`, `category: deviatdd-meso-layer`, `version: 2.0.0`.
- **Infrastructure & Operations**: GitHub is the remote (`origin https://github.com/wernerbisschoff/deviatdd.git`); `gh` 2.95.0 and `git` are installed host binaries. CI workflows exist under `.github/workflows/`. `mise.toml` declares `check`, `test`, `test-e2e` tasks.
- **Data & State Management**: State lives in JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`) and `.deviate/session.json`. `src/deviate/cli/meso.py::_pr_run` appends the COMPLETED transition to `specs/issues.jsonl` before pushing the branch.
- **Quality, Safety & Observability**: pytest under `tests/` with per-domain dirs (`tests/unit/test_meso/`, `tests/unit/test_cli/`, `tests/test_integration/`), ruff lint, `bats` E2E, and a review-coverage module `src/deviate/core/review_coverage.py` used by `src/deviate/cli/review.py::pre`.
- **External Integrations**: GitHub via the `gh` CLI (`_run_gh_pr_create` calls `gh pr create --title --body-file [--merge|--auto-merge]`); GitLab via `git push -o merge_request.create/target/title/description` push options (`_gitlab_push_options`); platform auto-detected from the `origin` remote hostname (`_resolve_pr_platform`).

## Ecosystem Research

[Web_Discovery]: Factual cataloging of industry best practices, common use cases, and standard tools relevant to the problem domain. Web search returned results; this section catalogues them without architectural recommendation.
- **Best Practices**: The ponytail skill constrains the agent with a "pre-write ladder" that selects the first satisfied minimal option. Source: DietrichGebert/ponytail. Snippet: "ponytail pre-write ladder — first rung that holds, wins: 1. Does this need to exist? -> no: skip it (YAGNI); 2. Stdlib does it? -> yes: use it; 3. Native platform feature? -> yes: use it (# <input type=\"date\">); 4. Already-installed dep? -> yes: use it; 5. Fits in one line? -> yes: one line; 6. Otherwise: the minimum that works".
- **Best Practices** (benchmark): Source: DietrichGebert/ponytail README. Snippet: "| vs no-skill baseline | LOC | tokens | cost | time | safe | ... | ponytail | -54% | -22% | -20% | -27% | 100% |". The viral claim was 80-94% LOC reduction; the project's own measured number is 54%.
- **Common Use Cases & Pitfalls**: The skill is a "lazy senior dev" mode that removes unnecessary code. Sources: blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/ ("Ponytail delivered -10.3% cost reduction with p=0.004"), learnagentic.substack.com ("Its original benchmark claimed 80 to 94% less code, but a public critique showed the baseline was a chatty bare model, not a real agent"), reddit.com/r/vibecoding ("in almost all cases I'd rather prefer a 'base' ..."). Independent tests found the honest reduction is narrower than the viral claim.
- **Standard Tooling**: The ponytail project publishes adapters for many agents (Claude Code, Codex, Cursor, Copilot, Grok Build, Gemini) as a `skill`/`plugin`. Sources: DietrichGebert/ponytail repo folder listing (`.claude-plugin`, `.codex-plugin`, `.cursor/rules`, `.grok-plugin`, `.openclaw/skills`, `.opencode`, `skills/`), infoq.com/news/2026/08/ponytail-agent-skill-benchmark ("Ponytail is a coding agent skill that reviews your code for over-engineering"). It is a constraint/pre-write practice, not a code-only tool.

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `specs/constitution.md` | Config | Governance contract pinned by the pre-script; §2/§3/§4/§5 define tech stack, testing, commit convention, and DoD. | "### Backend\n- Python 3.13\n- Target: CLI application (`deviate`)\n- Framework: Typer (CLI entry points) with Rich for terminal I/O" |
| `specs/constitution.md` | Config | Commit convention authoritative clause for PR-title and squash-commit-body adherence. | "### Commit Convention\n- Format: `<type>(<scope>): <description>`\n- Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`\n- Scope is the task ID (e.g., `T001`)\n- Body wraps at 72 characters" |
| `src/deviate/prompts/commands/deviate-pr.md` | Config (command) | The `/deviate-pr` slash command (v2.0.0) documenting the final meso gate that opens a GitHub PR or GitLab MR. | "description: Mark the issue COMPLETED, push the branch, and optionally open a GitHub PR or GitLab MR from the current worktree branch.\ncategory: deviatdd-meso-layer\nversion: 2.0.0" |
| `src/deviate/prompts/commands/deviate-pr.md` | Config (command) | Documents the dual-purpose PR body that is also a squash-merge commit body. | "The PR body MUST serve dual purpose: a good PR description AND a good squash-merge commit body.\n\n```markdown\n{SUMMARY}\n\n{CHANGES}\n\n{CLOSES}\n```" |
| `src/deviate/prompts/commands/deviate-review.md` | Config (command) | The `/deviate-review` command (v3.1.0) — HITL Gate 3 PR review, the candidate host for folding in ponytail pruning. | "description: HITL Gate 3 PR review — JUDGE-aware scan focused on architectural coherence, cross-task drift, and bug catching, with light-sniff on JUDGE-validated domains.\ncategory: deviatdd-meso-layer\nversion: 3.1.0" |
| `src/deviate/prompts/commands/deviate-prune.md` | Config (command) | The existing `/deviate-prune` command (v1.0.0) — a TDD PRUNE phase that removes implementation-coupled and redundant tests while preserving public behavioral contracts. | "description: TDD PRUNE phase — remove implementation-coupled and redundant tests while preserving public behavioral contracts.\ncategory: deviattd-macro-layer\nversion: 1.0.0" |
| `src/deviate/prompts/commands/deviate-prune.md` | Config (command) | Documents the `[REMOVE]`/`[CONSOLIDATE]`/`[RETAIN]` heuristics for test pruning. | "Assign `[REMOVE]` to tests that:\n- Assert a specific internal method was called\n- Mock internal sibling functions or classes within the same domain boundary\n- Assert on internal state mutations\n- Mock internal domain logic, pure functions, DTOs/models, or ORM/database clients" |
| `src/deviate/cli/meso.py` | Codebase_File | Platform detection for PR vs MR creation. | "def _resolve_pr_platform(repo: Path, override: str | None = None) -> str:\n    ...\n    if override in (\"github\", \"gitlab\"):\n        return override\n    ...\n    url = (result.stdout or \"\").strip().lower()\n    return \"gitlab\" if \"gitlab\" in url else \"github\"" |
| `src/deviate/cli/meso.py` | Codebase_File | GitLab MR creation via git push options (no separate MR CLI). | "opts = [\"-o\", \"merge_request.create\", \"-o\", f\"merge_request.target={base_branch}\", \"-o\", f\"merge_request.title={title}\"]\n    if body.strip():\n        opts += [\"-o\", f\"merge_request.description={body.strip()}\"]\n    return opts" |
| `src/deviate/cli/meso.py` | Codebase_File | GitHub PR creation via the `gh` CLI. | "cmd = [\"gh\", \"pr\", \"create\", \"--title\", title, \"--body-file\", str(body_file)]\n    if merge:\n        cmd.append(\"--merge\")\n    elif auto_merge:\n        cmd.append(\"--auto-merge\")" |
| `src/deviate/cli/meso.py` | Codebase_File | Conventional-commit PR title built from the issue record. | "commit_type = TYPE_MAP.get(record_type, \"feat\")\n    desc = re.sub(r\"^\\[[A-Z]+-\\d+\\]\\s*\", \"\", record_title).strip()\n    return f\"{commit_type}({commit_scope(issue_id)}): {desc}\"" |
| `src/deviate/cli/meso.py` | Codebase_File | The `deviate pr pre` JSON contract generator. | "git_state = gather_git_state(repo=repo_root)\n...\npr_title, pr_body, base_branch = _derive_pr_metadata(\n    branch_name, issue_id, record.title, record.type\n)" |
| `src/deviate/cli/meso.py` | Codebase_File | The `deviate pr run` orchestration: mark COMPLETED, commit, push, open PR/MR. | "completed = record.model_copy(update={\"status\": \"COMPLETED\", \"timestamp\": datetime.now(timezone.utc)})\n    appended = append_issue_transition(completed, ledger_path)\n    ...\n    push_cmd = [\"git\", \"push\", \"-u\", \"origin\", \"HEAD\"]" |
| `src/deviate/core/convention.py` | Codebase_File | Canonical commit scope; strips the legacy `ISS-` prefix. | "def commit_scope(identifier: str) -> str:\n    \"\"\"Return the canonical commit scope for an issue or task identifier.\"\"\"\n    if identifier.startswith(\"ISS-\"):\n        return identifier[4:]\n    return identifier" |
| `src/deviate/core/convention.py` | Codebase_File | Emoji detection: a no-op unless a convention file declares emoji. | "def detect_uses_emojis(repo: Path) -> bool:\n    ...\n    convention_content = _read_convention_file(repo)\n    if convention_content is None:\n        return False\n    return _file_has_emojis(convention_content)" |
| `src/deviate/cli/review.py` | Codebase_File | The `/deviate-review` CLI; gathers diff, constitution path, and PRD path. | "diff = _compute_diff(repo, resolved_base, target)\n    constitution_path = _resolve_constitution_path(repo)\n    prd_path, prd_warning = _resolve_prd(branch_name, repo)\n    ...\n    coverage = evaluate_review_coverage(repo, resolve_review_issue_id(repo, branch_name))" |
| `tests/unit/test_meso/test_pr_platform.py` | Test | Pins platform detection and GitLab push-option generation. | "def test_github_remote(self, tmp_path):\n    with patch(\"deviate.cli.meso.subprocess.run\") as mock_run:\n        mock_run.return_value.stdout = \"https://github.com/owner/repo.git\\n\"\n        assert _resolve_pr_platform(tmp_path) == \"github\"" |
| `tests/unit/test_cli/test_meso.py` | Test | Pins the conventional-commit PR title generation. | "assert _pr_title(\"ISS-001-001\", \"Feature\") == \"feat(001-001): Feature\"\nassert _pr_title(\"ISS-ADH-001\", \"Fix\", \"bug\") == \"fix(ADH-001): Fix\"" |
| `tests/unit/test_cli/test_meso_contracts.py` | Test | Pins the `deviate pr pre` JSON contract fields. | "def test_pr_pre_contract_has_required_fields(self, tmp_path: Path) -> None:\n    ..." |
| `tests/test_integration/test_meso_layer.py` | Test | Pins the `deviate pr run` end-to-end PR/MR behavior. | "Pinned by `tests/test_integration/test_meso_layer.py::TestPrRun`" (CHANGELOG reference) — class `TestPrRun` exercises the PR run path. |
| `tests/unit/test_meso/test_auto_prompt_templates.py` | Test | Pins the "Ponytail smallest-change" decision: folded into existing GREEN / REFACTOR / review lines, no new Constraints or Minimality heading. | "class TestSmallestChangeFoldedIntoExistingPrompts:\n    \"\"\"GH-92 (rescoped): Ponytail smallest-change lives in existing GREEN /\n    REFACTOR / review lines — no new Constraints or Minimality heading.\"\"\"" |
| `tests/unit/test_meso/test_auto_prompt_templates.py` | Test | Pins review behavior: keep over-engineering signals, do not promote helper extraction. | "def test_review_keeps_overengineering_and_does_not_promote_helpers(self):\n    text = self._read_review()\n    assert \"Cross-task over-engineering\" in text\n    assert \"into a shared helper\" not in text\n    assert \"## Constraints\" not in text" |
| `pyproject.toml` | Manifest | Declares package name, Python 3.13, CLI script, and runtime dependencies. | "dependencies = [\"typer>=0.12\", \"rich>=13.0\", \"pydantic>=2.0\", \"pyyaml>=6.0.3\"]\n\n[project.scripts]\ndeviate = \"deviate.main:app\"" |
| `pyproject.toml` | Manifest | Declares pytest test path configuration. | "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]" |
| `CONTRIBUTING.md` | Config | Declares the commit convention and the pull-request workflow. | "## Commit convention\n\n```\n<type>(<scope>): <description>\n\n[optional body, wrapped at 72 chars]\n\n[optional footer, e.g. Fixes #N, Refs #N]\n```" |
| `CONTRIBUTING.md` | Config | Documents squash/rebase before merge and HITL Gate 3. | "7. **Squash or rebase** before merge once approved. `main`'s history must stay linear.\n\nA maintainer performs **HITL Gate 3** (final merge audit) before merge" |
| `.github/PULL_REQUEST_TEMPLATE.md` | Config | PR template referencing spec file, task IDs, and phase checkboxes. | "## Summary\n<!-- 1–3 bullets. What changed and why. -->\n-\n\n## Related\n<!-- Issue(s), spec file(s), task ID(s). Use \"Fixes #N\" / \"Refs #N\" syntax. -->" |
| `CHANGELOG.md` | Config | Records the `/deviate-pr` PR/MR behavior change with pinned tests. | "- **`/deviate-pr` now marks the issue COMPLETED before it pushes, and opens a PR/MR only on request.** ... Pinned by `tests/test_integration/test_meso_layer.py::TestPrRun` and `tests/unit/test_meso/test_pr_platform.py`." |
| `mise.toml` | Manifest | Declares the repo task runner tasks (check, test, test-e2e). | "Task runner: `mise` (see `mise.toml` for all tasks)" (constitution §2 Tooling; `mise.toml` holds the task definitions). |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 2-5; strongest candidates: `src/deviate/prompts/commands/deviate-review.md` (if ponytail pruning folds in), or a new `src/deviate/prompts/commands/deviate-ponytail.md` (if a new command is created), plus `tests/unit/test_meso/test_auto_prompt_templates.py`. The `/deviate-pr` concern is already implemented; any change is verification or a small fix in `src/deviate/cli/meso.py` and `tests/unit/test_meso/test_pr_platform.py`. |
| New Modules Required | No (both concerns map to existing modules: `src/deviate/cli/meso.py` hosts PR; prompt-layer changes live in `src/deviate/prompts/commands/`). |
| New Persistence / Data Models | No (uses existing JSONL ledgers and `.deviate/` session state). |
| New External Integrations | No (GitHub via existing `gh` binary; GitLab via existing `git` push options; both already implemented). |
| Upstream / Cross-Cutting Concerns | The `constitution.md` §2 Tooling and `CONTRIBUTING.md` commit-convention clauses constrain any PR-title/body change; a new slash command must be installed to `<workdir>/.agent/commands/` via the existing prompt-install mechanism and reflected in `specs/DeviaTDD-api.md`/`specs/DeviaTDD-architecture.md` for any user-visible change. |
| Rationale | The `/deviate-pr` GitHub/GitLab path is implemented, tested, and documented (`meso.py` platform helpers, `test_pr_platform.py`, `TestPrRun`), so that concern is mostly verification. The ponytail-pruning concern is a prompt-layer decision already precedented by GH-92, which folded "smallest-change" into existing prompts rather than adding a new command; the change surface is small (prompt markdown plus tests), hence Medium. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | ponytail-pruning |
| GIT_BRANCH | main |
| SPEC_TARGET | specs/explore/ponytail-pruning.md |
| NEXT_ACTION | Run `/deviate-adhoc` (Low/Medium complexity) — see `## Scope Sizing` |
