# FEATURE_SPECIFICATION: specs/002-deviatdd-gap-analysis/004-governance-inspection/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/004-governance-inspection.md`
- **Branch**: `feat/002-deviatdd-gap-analysis/004-governance-inspection`

### Workstation Paths

| Path | Action |
|------|--------|
| `src/deviate/cli/constitution.py` | NEW — `constitution pre` and `constitution post <manifest>` CLI |
| `src/deviate/core/constitution.py` | MODIFY — add `validate_placeholders()` |
| `src/deviate/cli/inspect.py` | NEW — `deviate tasks list` and `deviate issues list` commands |
| `src/deviate/state/ledger.py` | MODIFY — add `LedgerFilter` model, query helpers |
| `src/deviate/prompts/constitution_seed.md` | MODIFY — audit and patch all 6 `${VARIABLE}` placeholders |

## THE_PROBLEM_CONTRACT

**User Journey**: A developer runs `deviate constitution pre` to validate `specs/constitution.md` and extract test/lint/typecheck commands. The output is a JSON contract with extracted commands. Then `deviate constitution post <manifest>` validates constitution sections and commits. Separately, a developer wants to see all issues: `deviate issues list --json` parses `specs/issues.jsonl` bottom-up and emits a JSON array. `deviate tasks list --status PENDING` shows only pending tasks in a Rich table. During `deviate init`, placeholders in `constitution_seed.md` are validated to ensure all 6 `${VARIABLE}` tokens are present.

**System Response**: `constitution pre` reads `specs/constitution.md`, validates sections, extracts `test_command`, `lint_command`, `typecheck_command` from `## TESTING_PROTOCOLS`. Missing constitution → `FAILURE` with reason. Missing sections → `FAILURE` with missing sections listed. `constitution post` validates section structure and commits. `issues list` parses `specs/issues.jsonl` bottom-up with `--type`, `--status`, `--json` filters. For SPECIFIED issues, branch existence on remote is checked via `git ls-remote --heads`. Remote reachable + branch missing → `🟡 ORPHAN_CLAIM` + `"orphan_claim": true`. Remote reachable + branch exists → `"orphan_claim": false`. Remote unreachable → `"orphan_claim": null`. `tasks list` parses active issue's `tasks.jsonl` with status derivation. Missing ledger → empty result set (not error). Malformed JSONL → fail on first malformed line. `validate_placeholders()` checks all 6 variables.

## SCOPE_BOUNDARIES

### Hard Inclusions

- `deviate constitution pre` — validate constitution, extract test/lint/typecheck commands, emit JSON contract
- Missing constitution file → `status: FAILURE` with descriptive `reason`
- Missing sections (e.g. `## TESTING_PROTOCOLS`) → `status: FAILURE` with missing sections listed in `reason`
- `deviate constitution post <manifest>` — validate constitution section structure, commit
- `validate_placeholders(seed_path)` — audit all 6 `${VARIABLE}` placeholders in seed template
- `deviate issues list [--type] [--status] [--json]` — parse `specs/issues.jsonl` bottom-up, Rich table or JSON
- For each issue with `status=SPECIFIED`, derive branch name as `feat/<epic_slug>/<issue_slug>` via `_resolve_bucket_dir`/`_source_stem` logic
- Check remote branch via `git ls-remote --heads <remote> <branch>`; remote auto-detected via `detect_remote()`
- Remote reachable + branch missing → `🟡 ORPHAN_CLAIM` in Rich table, `"orphan_claim": true` in JSON
- Remote reachable + branch exists → no badge, `"orphan_claim": false` in JSON
- Remote unreachable → `"orphan_claim": null` in JSON, no badge in Rich table
- `deviate tasks list [--type] [--status] [--json]` — parse active issue's `tasks.jsonl`, Rich table or JSON
- Missing ledger → empty result set (not error)
- Malformed JSONL line → fail with error on first malformed line
- `--json` mode emits valid JSON array even when empty
- Constitution seed audit: verify all 6 placeholders present; patch missing ones

### Defensive Exclusions

- NO changes to micro-layer TDD cycle or phase dispatch
- NO changes to `deviate init` scaffolding beyond placeholder validation
- NO changes to session state machine
- NO migration of existing ledger data — only forward reads
- NO changes to constitution content beyond seed template patching

## PERFORMANCE_CONSTRAINTS

- `constitution pre`: L_max <= 100ms (file read + regex extraction)
- `constitution post`: L_max <= 200ms (section validation + git commit)
- `validate_placeholders()`: L_max <= 50ms (file read + regex match)
- `issues list`: L_max <= 200ms for 50 issues (file parse + optional git ls-remote)
- `tasks list`: L_max <= 100ms for 20 tasks (file parse + Rich table render)
- `git ls-remote --heads`: L_max <= 5s per remote per invocation (indeterminate due to network)

## MULTI_TIERED_VERIFICATION_TARGETS

| Tier | Target | Command |
|------|--------|---------|
| Unit | `tests/test_cli/test_constitution.py` | `pytest tests/test_cli/test_constitution.py -v` |
| Unit | `tests/test_cli/test_inspect.py` | `pytest tests/test_cli/test_inspect.py -v` |
| Unit | `tests/test_core/test_constitution.py` | `pytest tests/test_core/test_constitution.py -v` |
| Unit | `tests/test_state/test_ledger.py` | `pytest tests/test_state/test_ledger.py -v` |

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-ConstitutionPre: Constitution Pre CLI — Validation & Command Extraction

* **Upstream Requirement Traceability**: FR-005

1. **Scenario: Valid constitution extracts commands**
   **Given** `specs/constitution.md` exists with valid sections including `## TESTING_PROTOCOLS`
   **When** `deviate constitution pre` is executed
   **Then** a JSON contract is emitted on stdout containing `test_command`, `lint_command`, and `typecheck_command` derived from `## TESTING_PROTOCOLS`
   **And** exit code is 0

2. **Scenario: Missing constitution file returns FAILURE**
   **Given** `specs/constitution.md` does not exist
   **When** `deviate constitution pre` is executed
   **Then** the command exits with `status: FAILURE`
   **And** a descriptive `reason` field explains the file is missing
   **And** exit code is non-zero

3. **Scenario: Missing TESTING_PROTOCOLS section returns FAILURE with details**
   **Given** `specs/constitution.md` exists but lacks the `## TESTING_PROTOCOLS` section
   **When** `deviate constitution pre` is executed
   **Then** the command exits with `status: FAILURE`
   **And** the `reason` field lists `## TESTING_PROTOCOLS` as a missing required section
   **And** exit code is non-zero

### US-002-ConstitutionPost: Constitution Post CLI — Section Validation & Commit

* **Upstream Requirement Traceability**: FR-005

1. **Scenario: Valid constitution manifest commits changes**
   **Given** a valid constitution manifest JSON with all required sections present
   **When** `deviate constitution post <manifest>` is executed
   **Then** the constitution section structure is validated
   **And** changes are committed via git
   **And** exit code is 0

2. **Scenario: Invalid manifest with missing sections fails validation**
   **Given** a constitution manifest referencing a non-existent or malformed section
   **When** `deviate constitution post <manifest>` is executed
   **Then** section validation fails
   **And** no git commit is performed
   **And** exit code is non-zero

### US-003-IssuesList: Issues List Ledger Inspection

* **Upstream Requirement Traceability**: FR-006

1. **Scenario: --json flag emits valid JSON array**
   **Given** `specs/issues.jsonl` contains 3 issue records
   **When** `deviate issues list --json` is executed
   **Then** a valid JSON array of issue objects is emitted on stdout
   **And** each object contains at minimum `issue_id`, `title`, `status`, and `type` fields
   **And** exit code is 0

2. **Scenario: Empty ledger returns empty array**
   **Given** `specs/issues.jsonl` does not exist or is empty
   **When** `deviate issues list --json` is executed
   **Then** a valid empty JSON array `[]` is emitted on stdout
   **And** exit code is 0

3. **Scenario: SPECIFIED issue with no remote branch flagged as orphan**
   **Given** `specs/issues.jsonl` contains a SPECIFIED issue with `source_file` `specs/002-deviatdd-gap-analysis/issues/004-governance-inspection.md`
   **And** remote `origin` is reachable via `git ls-remote`
   **And** the branch `feat/002-deviatdd-gap-analysis/004-governance-inspection` does NOT exist on remote
   **When** `deviate issues list --json` is executed
   **Then** the SPECIFIED issue entry contains `"orphan_claim": true`
   **And** in Rich table mode, the issue shows a `🟡 ORPHAN_CLAIM` badge
   **And** exit code is 0

4. **Scenario: SPECIFIED issue with matching remote branch has no orphan flag**
   **Given** `specs/issues.jsonl` contains a SPECIFIED issue with a valid `source_file`
   **And** remote `origin` is reachable
   **And** the derived branch exists on remote
   **When** `deviate issues list --json` is executed
   **Then** the issue entry contains `"orphan_claim": false`
   **And** no `ORPHAN_CLAIM` badge appears in Rich table mode
   **And** exit code is 0

5. **Scenario: Remote unreachable produces null orphan_claim**
   **Given** `specs/issues.jsonl` contains a SPECIFIED issue
   **And** remote `origin` is unreachable (network error)
   **When** `deviate issues list --json` is executed
   **Then** the issue entry contains `"orphan_claim": null`
   **And** no `ORPHAN_CLAIM` badge appears in Rich table mode
   **And** exit code is 0

6. **Scenario: --type and --status filters narrow results**
   **Given** `specs/issues.jsonl` contains issues of type `feature` with mixed statuses
   **When** `deviate issues list --type feature --status BACKLOG` is executed
   **Then** only issues with `type=feature` and `status=BACKLOG` are displayed
   **And** exit code is 0

7. **Scenario: Malformed JSONL line fails immediately**
   **Given** `specs/issues.jsonl` contains a malformed JSON line
   **When** `deviate issues list --json` is executed
   **Then** the command fails with an error on the first malformed line
   **And** exit code is non-zero

### US-004-TasksList: Tasks List Ledger Inspection

* **Upstream Requirement Traceability**: FR-006

1. **Scenario: --status PENDING shows only pending tasks**
   **Given** a valid `tasks.jsonl` in the active feature directory with PENDING, IN_PROGRESS, and COMPLETED tasks
   **When** `deviate tasks list --status PENDING` is executed
   **Then** only PENDING tasks are displayed in a Rich table
   **And** exit code is 0

2. **Scenario: --json flag emits valid JSON array**
   **Given** a valid `tasks.jsonl` with 3 task records
   **When** `deviate tasks list --json` is executed
   **Then** a valid JSON array of task objects is emitted on stdout
   **And** exit code is 0

3. **Scenario: Missing tasks.jsonl returns empty result set**
   **Given** the active issue has no `tasks.jsonl` file
   **When** `deviate tasks list` is executed
   **Then** an empty Rich table is displayed (not an error)
   **And** exit code is 0

### US-005-PlaceholderAudit: Constitution Seed Placeholder Validation

* **Upstream Requirement Traceability**: FR-014

1. **Scenario: All 6 variables present in seed template**
   **Given** `src/deviate/prompts/constitution_seed.md`
   **When** `validate_placeholders(path)` is called
   **Then** the result indicates `all_present=True`
   **And** `result.variables` contains all 6 variables: `PROJECT_NAME`, `REPO_ROOT`, `TARGET_BACKEND_FRAMEWORK`, `TARGET_PACKAGE_MANAGER`, `TARGET_TEST_RUNNER`, `TARGET_COVERAGE_MINIMUM`
   **And** all variables are correctly formatted as `${VARIABLE_NAME}`

2. **Scenario: Missing variable detected**
   **Given** a seed template missing one or more required `${VARIABLE}` tokens
   **When** `validate_placeholders(path)` is called
   **Then** the result indicates `all_present=False`
   **And** `result.missing` lists the absent variable(s)

3. **Scenario: Seed file not found raises error**
   **Given** a non-existent seed file path
   **When** `validate_placeholders(path)` is called
   **Then** a `FileNotFoundError` is raised

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|----------|-------|
| STATUS | DRAFT |
| EPIC_SLUG | 002-deviatdd-gap-analysis |
| ISSUE_SLUG | 004-governance-inspection |
| BRANCH_NAME | feat/002-deviatdd-gap-analysis/004-governance-inspection |
| SPEC_PATH | specs/002-deviatdd-gap-analysis/004-governance-inspection/spec.md |
| ISSUE_ID | ISS-002-004 |
| CONSTITUTION_PATH | specs/constitution.md |
| NEXT_ACTION | HITL Gate 2 — Human reviews spec.md; then run `deviate tasks pre` |
