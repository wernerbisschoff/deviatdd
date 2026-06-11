---
title: Governance & Inspection — Constitution CLI, Ledger List Commands, Seed Audit
labels: ["feature", "ISS-002", "P2"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-003", "ISS-002-002"]
coordinates_with: []
issue_id: ISS-002-004
epic_id: ISS-002
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/004-governance-inspection.md`
- **Workstation Paths**:
  - `src/deviate/cli/constitution.py` — NEW: Typer app with `constitution pre`, `constitution post`
  - `src/deviate/cli/inspect.py` — NEW: `tasks list`, `issues list` commands
  - `src/deviate/core/constitution.py` — MODIFY: add `validate_placeholders()`
  - `src/deviate/state/ledger.py` — MODIFY: add `LedgerFilter` model
  - `src/deviate/cli/__init__.py` — MODIFY: register `constitution_app`, wire inspect commands
  - `src/deviate/prompts/constitution_seed.md` — MODIFY: audit/add missing placeholders

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer runs `deviate constitution pre` to validate the project's `specs/constitution.md` exists and extracts test/lint/typecheck commands. They run `deviate tasks list --json` to see all task records in the active worktree, filtered by status. They run `deviate issues list --status BACKLOG --json` to see pending issues. The constitution seed template (`constitution_seed.md`) is audited to ensure all 6 `${VARIABLE}` placeholders are present.

**System Response**: `constitution pre` parses `specs/constitution.md` and emits a JSON contract with extracted commands. `constitution post` validates sections and commits. List commands parse JSONL ledgers with status/type filters and render Rich tables (or JSON with `--json` flag). `validate_placeholders()` scans the seed template and reports coverage.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `cli/constitution.py` with `constitution pre` (validate, extract commands, emit JSON) and `constitution post <manifest>` (validate sections, commit)
- `cli/inspect.py` with `tasks list [--type] [--status] [--json]` and `issues list [--type] [--status] [--json]`
- `validate_placeholders()` in `core/constitution.py`
- Add missing placeholders to `constitution_seed.md`
- Missing constitution file emits `status: FAILURE` with reason
- Missing ledger files return empty results (not errors)
- Malformed JSONL lines skipped with warnings

### Defensive Exclusions
- NO changes to the TDD cycle or phase dispatch
- NO changes to context sync or profile execution
- NO changes to skill files
- NO changes to AGENTS.md or CLAUDE.md
- NO changes to the session state machine
- NO deep integration with micro-layer rollback or cache

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-005 | Constitution Pre/Post | FR-005-ConstitutionCLI |
| FR-006 | Ledger Inspection Commands | FR-006-Inspect |
| FR-014 | Constitution Seed Placeholder Audit | FR-014-ConstitutionSeedPlaceholderAudit |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-005-01 | `deviate constitution pre` emits JSON with `test_command`, `lint_command`, `typecheck_command` |
| AC-005-02 | `deviate constitution pre` without constitution emits `status: FAILURE` with reason |
| AC-006-01 | `deviate issues list --json` emits valid JSON array from `issues.jsonl` |
| AC-006-02 | `deviate tasks list --status PENDING` displays only PENDING tasks in Rich table |
| AC-014-01 | All 6 variables present and correctly formatted in `constitution_seed.md` |

### Data Model Entities
- `LedgerFilter` — `src/deviate/state/ledger.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_cli/test_constitution.py` — `test_constitution_pre_valid`, `test_constitution_pre_missing`, `test_constitution_post`
- `tests/test_cli/test_inspect.py` — `test_tasks_list_json`, `test_tasks_list_status_filter`, `test_issues_list_json`, `test_issues_list_empty_ledger`, `test_issues_list_malformed_jsonl`
- `tests/test_core/test_constitution.py` — `test_validate_placeholders_all_present`, `test_validate_placeholders_missing`, `test_validate_placeholders_not_found`
- `tests/test_state/test_ledger.py` — `test_ledger_filter_model`

## [DEMONSTRATION_PATH]

```bash
# Verify constitution pre emits commands
uv run deviate constitution pre --json 2>/dev/null | python -c "
import sys, json
c = json.load(sys.stdin)
assert 'test_command' in c
assert 'lint_command' in c
print('Constitution pre OK:', c['status'])
"

# Verify issues list with JSON output
uv run deviate issues list --json 2>/dev/null | python -c "
import sys, json
data = json.load(sys.stdin)
assert isinstance(data, list)
print(f'Issues list OK: {len(data)} issues')
"

# Verify placeholder audit
uv run python -c "
from deviate.core.constitution import validate_placeholders
result = validate_placeholders()
all_vars = {'PROJECT_NAME', 'REPO_ROOT', 'TARGET_BACKEND_FRAMEWORK', 'TARGET_PACKAGE_MANAGER', 'TARGET_TEST_RUNNER', 'TARGET_COVERAGE_MINIMUM'}
assert all_vars.issubset(result['present']), f'Missing: {all_vars - set(result[\"present\"])}'
print(f'Placeholder audit OK: {len(result[\"present\"])}/{len(all_vars)} present')
"

# Run verification tests
pytest tests/test_cli/test_constitution.py tests/test_cli/test_inspect.py tests/test_core/test_constitution.py -v --no-header -q
```
