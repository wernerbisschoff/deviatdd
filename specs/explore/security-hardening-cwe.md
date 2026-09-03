---
status: explore
phase: EXPLORE
epic_id: security-hardening-cwe
slug: security-hardening-cwe
timestamp: 2026-08-02T14:39:46
---

# Explore: Security Hardening — CWE Mapping, Security Gate, /deviate-security Phase

## Problem Definition

[Statement]: Explore the existing security tooling and controls inside the DeviaTDD
workflow to determine where CWE mapping belongs, whether a mandated
linter/type-check security gate already exists, and whether a dedicated
`/deviate-security` phase is present or warranted during/after review.

[Scope]: Catalog the security-relevant structural components that currently exist —
the JUDGE flat security scan, the `SecurityProfile` ledger model, the `security_checks`
manifest field, the Plan-phase Security Profile section, and the Review-phase cross-task
Security domain. Catalog the absences: CWE identifiers, SAST/type-check tooling, and any
dedicated security phase or command. Record the constitution quotes verbatim.

[Exclusions]: Architectural decisions, design or trade-off recommendations, vulnerability
adjudication, and failure-mode speculation are deferred to the `deviate-research` skill.
This document catalogues what exists and what does not — it does not recommend.

## Discovery Audit Results

### Verified Dependencies

- `pydantic>=2.0` — declared in `pyproject.toml`; used by `SecurityProfile` (src/deviate/state/ledger.py:61) and all ledger models
- `typer>=0.12` — declared in `pyproject.toml`; CLI entry-point framework (dev dependency surface is sa/deviate entrypoints under `src/deviate/cli/`)
- `rich>=13.0` — declared in `pyproject.toml`; terminal I/O
- `pyyaml>=6.0.3` — declared in `pyproject.toml`; YAML config parsing
- Dev group: `pytest>=8.0`, `ruff>=0.4`, `pytest-testmon>=2.2` — declared in `pyproject.toml` `[project.optional-dependencies] dev`

### Ghost Dependencies

- `mypy` — a `.mypy_cache/` removal entry appears in `mise.toml` task "clean", but no `mypy`
  declarable in `pyproject.toml` `dependencies`, `[project.optional-dependencies]`, or `[dependency-groups]`.
  Reference excerpt:
  ```
  run = "rm -rf .ruff_cache/ .pytest_cache/ __pycache__/ .mypy_cache/ dist/ build/ *.egg-info/"
  ```

### Manifest Files Observed

- `pyproject.toml`: [Python project manifest; declares CLI script `deviate = "deviate.main:app"`, runtime and dev dependencies, ruff target]
- `mise.toml`: [Task-runner manifest; declares `check` (depends), `clean`, `publish`, and test/lint task definitions]
- `specs/constitution.md`: [Authoritative governance; defines Architectural Principles, Tech Stack Standards, Testing Protocols, Definition of Done]

### Test Runner Configuration

- `specs/constitution.md` §3: test root `tests/`, command `pytest tests/ -v`, lint `ruff check .`, E2E `bats tests/e2e/`
- `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths = ["tests"]`
- `specs/constitution.md` §3: code quality gate `mise run check`

### Manifest-Constitution Divergence

- **Tooling — SAST/type-checker not declared**: `specs/constitution.md` §2 Tooling names `ruff` (lint + format) as the single linter and `pytest` as the test runner. No SAST tool (`bandit`, `semgrep`, `safety`, `pip-audit`) and no type checker (`mypy`, `pyright`) is declared in the constitution or in `pyproject.toml`. The `mise.toml` clean task references `.mypy_cache/` without a manifest-declared mypy dependency. Quote BOTH verbatim. Do not adjudicate.
  - Constitution §2 Tooling: "Linter: `ruff` (lint + format)"
  - `mise.toml` clean: "run = "rm -rf .ruff_cache/ .pytest_cache/ __pycache__/ .mypy_cache/ dist/ build/ *.egg-info/"" — the `.mypy_cache/` token implies a type checker that has no declarable in the project manifests.

## Constitution Quotes

- **Architectural Principles**: "Micro (TDD sandbox: RED → GREEN → JUDGE → REFACTOR) ... The Product layer is skipped in single-feature repos; the remaining three layers have strict phase gates — no layer may be skipped." AND "Human-in-the-Loop (HITL): Two remaining mandatory gates (Design Approval after research, Final Merge Audit after micro) prevent autonomous drift. Gate 2 (post-Tasks approval) was removed ... No remaining gate may be programmatically bypassed."
- **Tech Stack Standards**: "Backend: Python 3.13 / Target: CLI application (`deviate`) / Framework: Typer (CLI entry points) with Rich for terminal I/O / Database: No persistent database runtime (all state tracked in JSONL ledgers and TOML config) / Micro-sandbox: Aider Python API (`aider.coders.Coder`) as LLM execution substrate / Tooling: Package manager `uv`; Test runner `pytest`; Linter `ruff` (lint + format); E2E testing `bats`; Task runner `mise`; Code quality gate `mise run check`"
- **Testing Protocols**: "Test framework: pytest / Test root: `tests/` / Test extension: `.py` / Test command: `pytest tests/ -v` / Lint command: `ruff check .` / E2E command: `bats tests/e2e/` / Coverage target: >= 80%"
- **Definition of Done**: "[ ] Tests passing (pytest with clean exit code 0) / [ ] Lint passing (ruff check with no violations) / [ ] Judge phase passed (git diff validated against the authoritative plan acceptance contract) / [ ] No governance violations (constitution rules upheld, no remaining HITL gates bypassed; Gate 2 was removed)"

## Architectural Baselines

[Pattern_Over_Instance]: Representative security-control examples are listed, not every occurrence. All paths are strictly relative to `repo_root`.

- **Existing Architectural Patterns**: The micro-loop is RED → GREEN → JUDGE → REFACTOR (constitution §1). Security is expressed as a constraint inside the JUDGE phase. Representative evidence in `src/deviate/prompts/auto/judge.md`:
  ```
  4. **Security Violation**: Hardcoded credentials/tokens, environment variable leakage, unsafe
  deserialization (e.g., `pickle.loads`, unsafe `yaml.load`), command injection vectors
  (unsanitized input to `subprocess.run` / `os.system` / `eval`), or path-traversal via
  unsanitized path construction.
  ```
- **Infrastructure & Operations**: CLI-only local execution; no containerization (constitution §2). Security-relevant operation is a prompt-level scan — no SAST or type-checker tool declared.
- **Data & State Management**: All state is append-only JSONL ledgers + TOML config. The per-task security context is a Pydantic model on the task record — `src/deviate/state/ledger.py:61`:
  ```
  class SecurityProfile(BaseModel):
      """Optional per-task security profile body.
      Single-field model: ``body`` holds the verbatim markdown body of the
      ``## Security Profile`` section from ``plan.md``. The JUDGE prompt reads
      this as supplementary context when populating the ``security_checks``
      field on the verdict manifest.
      body: str | None = None
      model_config = {"extra": "forbid"}
  ```
- **Quality, Safety & Observability**: The JUDGE manifest carries a mandatory `security_checks: pass | fail | warn` field. Representative evidence in `src/deviate/prompts/auto/judge.md`:
  ```
  | Security Checks | Critical | The `security_checks` field on the manifest is **mandatory** — emitted as
  `pass | fail | warn` based on the existing flat security scan (secrets, injection,
  deserialization, path traversal, log leakage) plus any `security_profile.body` content
  from the task. Absence of the field is a Judge rejection, not a soft warning. |
  ```
- **External Integrations**: `deviate review` is a real CLI command (`src/deviate/cli/review.py:18`, `review_app = typer.Typer(...)`) running at HITL Gate 3; it performs cross-task Security aggregation. Representative evidence in `src/deviate/prompts/commands/deviate-review.md`:
  ```
  You are a **PR_REVIEW_SCANNER** at **HITL Gate 3 (Final Merge Audit)**. ... Your scan is
  purpose-built to catch what JUDGE missed:
  3. **Aggregate signals**: Scope creep, missing features, security composition across tasks
  ```

## Ecosystem Research

[Web_Discovery]: Factual cataloging of industry-standard CWE and static-analysis conventions relevant to the problem domain. Sources via `libref` where available.

- **Best Practices**: CWE (Common Weakness Enumeration) is the standard taxonomy for software weaknesses and is the mapping target for findings from both OWASP Top 10 and SAST tools. OWASP security guidance maps web-application risks (SQLi, XSS, injection) to CWE identifiers as stable, cross-tool reference tokens. [Source: OWASP + MITRE CWE reference documentation via `libref`/web — see findings in `ai-code-security-in-deviatdd-phoenix` synthesis which maps A01–A10 and LLM01–LLM10 to concrete CWE codes.]
- **Common Use Cases & Pitfalls**: A common pitfall is maintaining ad-hoc, prose-only security finding labels (e.g., "injection", "deserialization") that cannot be aggregated, grepped, or compared across tasks. Mapping findings to a deterministic CWE identifier enables cross-task aggregation and automated review gates. A second pitfall is a single tool channel (LLM scan only) with no deterministic SAST/type-check complement — defense-in-depth expects a mechanical gate alongside the LLM judgement.
- **Standard Tooling**: Standard Python SAST tools are `bandit` and `semgrep`; dependency auditing is `safety` / `pip-audit`; type checking is `mypy` / `pyright`. None of these are declared in `pyproject.toml` or named in `specs/constitution.md` §2 Tooling. No CWE token appears anywhere in `src/`, `specs/`, or `tests/`.

## File Registry

| Path (Strictly Relative to Repo Root) | Type | Purpose | Verbatim Snippet (≤10 lines) |
| :--- | :--- | :--- | :--- |
| `src/deviate/state/ledger.py` | Codebase_File | Defines `SecurityProfile` model and `TaskRecord.security_profile` optional field | `class SecurityProfile(BaseModel):` / `    body: str | None = None` / `    model_config = {"extra": "forbid"}` |
| `src/deviate/state/ledger.py` | Codebase_File | `TaskRecord` carries the optional security profile field | `    security_profile: SecurityProfile | None = None` |
| `src/deviate/prompts/auto/judge.md` | Codebase_File | Declares Security Violation as category 4 of Judge violations | `4. **Security Violation**: Hardcoded credentials/tokens, environment variable leakage, unsafe deserialization (e.g., 'pickle.loads', unsafe 'yaml.load'), command injection vectors (unsanitized input to 'subprocess.run' / 'os.system' / 'eval'), or path-traversal via unsanitized path construction.` |
| `src/deviate/prompts/auto/judge.md` | Codebase_File | Declares mandatory `security_checks` manifest field vocabulary | `| Security Checks | Critical | The 'security_checks' field on the manifest is **mandatory** — emitted as 'pass \| fail \| warn' based on the existing flat security scan (secrets, injection, deserialization, path traversal, log leakage) plus any 'security_profile.body' content from the task.` |
| `src/deviate/prompts/auto/judge.md` | Codebase_File | Defines the flat security scan executed by Judge | `4. **Security scan**: hardcoded secrets, 'subprocess.run' / 'os.system' / 'eval' with unsanitized input, unsafe 'pickle.loads' / 'yaml.load', path construction from user input, secrets in log / print calls.` |
| `src/deviate/prompts/commands/deviate-plan.md` | Codebase_File | Plan-phase Security Profile prose template consumed by Judge | `## Security Profile` / `List the risk surfaces this task touches (auth, secrets, PII, outbound HTTP, deserialization, subprocess, file paths, SQL/ORM, eval) and the negative tests the planner expects RED to write.` |
| `src/deviate/prompts/commands/deviate-review.md` | Codebase_File | Gate 3 review includes cross-task Security aggregation domain | `### 1. Security (Cross-Task Aggregation)` / `- Attack surface composition: do individually-safe changes create a combined vulnerability?` |
| `src/deviate/cli/review.py` | Codebase_File | Implements the real `deviate review` CLI command | `review_app = typer.Typer(no_args_is_help=True)` |
| `tests/unit/test_state/test_security_profile.py` | Test | Pins the SecurityProfile ledger contract (5 tests) | `class TestSecurityProfile:` / `    def test_security_profile_default_construction(self):` / `        """Empty SecurityProfile() yields body=None."""` |
| `tests/unit/test_micro/test_judge.py` | Test | Pins the security_checks manifest field requirement | `class TestJudgeSecurityChecksField:` / `    """The JUDGE prompt must declare 'security_checks' as a required manifest field.` |
| `pyproject.toml` | Manifest | Declares runtime + dev dependencies and test config | `dev = [` / `    "pytest>=8.0",` / `    "ruff>=0.4",` / `    "pytest-testmon>=2.2",` / `]` |
| `mise.toml` | Manifest | Declares clean/check/publish task definitions | `run = "rm -rf .ruff_cache/ .pytest_cache/ __pycache__/ .mypy_cache/ dist/ build/ *.egg-info/"` |
| `specs/constitution.md` | Config | Governance: Tooling, Testing Protocols, Definition of Done | `## 2. Tech Stack Standards` / `Linter: 'ruff' (lint + format)` / `## 3. Testing Protocols` / `Test command: 'pytest tests/ -v'` |
| `specs/004-per-task-security-profile/issues/001-security-profile-and-judge-checks.md` | Config | Spec issue defining the already-landed SecurityProfile contract | `## [SYSTEM_TOPOLOGY_MAPPING]` / `- 'src/deviate/state/ledger.py' — MODIFY: add 'SecurityProfile' Pydantic model + 'TaskRecord.security_profile' field` |

## Scope Sizing

| Metric | Value |
| :--- | :--- |
| Estimated Complexity | Medium |
| Files Likely Modified | 2–4: `src/deviate/prompts/auto/judge.md`, `src/deviate/prompts/commands/deviate-plan.md`, `src/deviate/state/ledger.py` (if `SecurityProfile` gains structured CWE fields), optionally `specs/constitution.md` |
| New Modules Required | No |
| New Persistence / Data Models | Conditional: only if `SecurityProfile` is upgraded from prose `body` to structured CWE-carrying fields; the ledger JSONL persists it either way |
| New External Integrations | Conditional: only if a SAST tool (`bandit`/`semgrep`) or type checker (`mypy`) is adopted as a declared gate |
| Upstream / Cross-Cutting Concerns | A dedicated `/deviate-security` CLI phase would be a new command surface in `src/deviate/cli/` and a new `##`-style step in the constitution — no such command or phase exists today |
| Rationale | The repo has security present as a Judge constraint + a Review aggregation domain, and a prose-only `SecurityProfile` ledger field, but no CWE identifiers, no SAST/type-check tooling declaration, and no dedicated security phase or CLI command. Any hardening work is one or two bounded additions rather than a rewrite. |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | SUCCESS |
| EXPLORE_SLUG | security-hardening-cwe |
| GIT_BRANCH | main |
| SPEC_TARGET | `specs/explore/security-hardening-cwe.md` |
| NEXT_ACTION | Low/Medium complexity → run `/deviate-adhoc` with the same problem statement; `explore.md` is on disk and will be auto-consumed |
