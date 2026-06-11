---
title: Governance and Inspection — Constitution CLI, Ledger Inspection, Seed Placeholder Audit
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-002", "ISS-002-003"]
coordinates_with: []
issue_id: ISS-002-004
epic_id: ISS-002
type: feature
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/004-governance-inspection.md`
- **Workstation Paths**:
  - `src/deviate/cli/constitution.py` — NEW: `constitution pre` (validate, extract commands) and `constitution post <manifest>` (section validation, commit)
  - `src/deviate/core/constitution.py` — MODIFY: `validate_constitution()`, add `validate_placeholders()`
  - `src/deviate/cli/inspect.py` — NEW: `deviate tasks list` and `deviate issues list` with filtering
  - `src/deviate/state/ledger.py` — MODIFY: add `LedgerFilter` model, query helpers
  - `src/deviate/prompts/constitution_seed.md` — MODIFY: audit and patch all 6 `${VARIABLE}` placeholders

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer runs `deviate constitution pre` to validate `specs/constitution.md` and extract test/lint/typecheck commands. The output is a JSON contract with extracted commands. Then `deviate constitution post <manifest>` validates constitution sections and commits. Separately, a developer wants to see all issues: `deviate issues list --json` parses `specs/issues.jsonl` bottom-up and emits a JSON array. `deviate tasks list --status PENDING` shows only pending tasks in a Rich table. During `deviate init`, placeholders in `constitution_seed.md` are validated to ensure all 6 `${VARIABLE}` tokens are present.

**System Response**: `constitution pre` reads `specs/constitution.md`, validates sections, extracts `test_command`, `lint_command`, `typecheck_command` from `## TESTING_PROTOCOLS`. Missing constitution → `FAILURE` with reason. `constitution post` validates section structure and commits. `issues list` parses `specs/issues.jsonl` bottom-up with `--type`, `--status`, `--json` filters. `tasks list` parses active issue's `tasks.jsonl` with status derivation. Missing ledger → empty result set (not error). `validate_placeholders()` checks all 6 variables are present in the seed template.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `deviate constitution pre` — validate constitution, extract test/lint/typecheck commands, emit JSON contract
- `deviate constitution post <manifest>` — validate sections, commit
- `validate_placeholders(seed_path)` — audit all 6 `${VARIABLE}` placeholders in seed template
- `deviate issues list [--type] [--status] [--json]` — parse `specs/issues.jsonl` bottom-up, Rich table or JSON
- `deviate tasks list [--type] [--status] [--json]` — parse active issue's `tasks.jsonl`, Rich table or JSON
- Missing ledger → empty result set (not error)
- Malformed JSONL lines → skip with stderr warning
- `--json` mode emits valid JSON array even when empty
- Constitution seed audit: patch missing placeholders with surrounding context

### Defensive Exclusions
- NO changes to micro-layer TDD cycle or phase dispatch
- NO changes to `deviate init` scaffolding beyond placeholder validation
- NO changes to session state machine
- NO migration of existing ledger data — only forward reads
- NO changes to constitution content beyond seed template patching

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-005 | Constitution Pre/Post CLI | FR-005-ConstitutionCLI |
| FR-006 | Ledger Inspection Commands | FR-006-Inspect |
| FR-014 | Constitution Seed Placeholder Audit | FR-014-ConstitutionSeedPlaceholderAudit |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-005-01 | `constitution pre` with valid constitution emits JSON with `test_command`, `lint_command`, `typecheck_command` |
| AC-005-02 | `constitution pre` with missing constitution → `status: FAILURE` with descriptive reason |
| AC-006-01 | `issues list --json` with 3 issues → valid JSON array on stdout |
| AC-006-02 | `tasks list --status PENDING` → only PENDING tasks in Rich table |
| AC-014-01 | `validate_placeholders()` confirms all 6 variables present in `constitution_seed.md` |

### Data Model Entities
- `LedgerFilter` — `src/deviate/state/ledger.py` (transient query parameter)

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_cli/test_constitution.py` — `test_constitution_pre_emits_commands`, `test_constitution_pre_missing_file`
- `tests/test_cli/test_inspect.py` — `test_issues_list_json`, `test_tasks_list_status_filter`, `test_issues_list_empty_ledger`
- `tests/test_core/test_constitution.py` — `test_validate_placeholders_all_present`, `test_validate_placeholders_missing_var`
- `tests/test_state/test_ledger.py` — `test_ledger_filter_query`, `test_ledger_filter_empty`

## [DEMONSTRATION_PATH]

```bash
# Verify constitution pre extracts commands
deviate constitution pre 2>/dev/null | uv run python -c "
import sys, json
contract = json.load(sys.stdin)
assert 'test_command' in contract
assert 'lint_command' in contract
print(f'Constitution OK: test={contract[\"test_command\"]}')
"

# Verify issues list (json mode)
deviate issues list --json 2>/dev/null | uv run python -c "
import sys, json
issues = json.load(sys.stdin)
print(f'{len(issues)} issues loaded')
"

# Verify placeholder validation
uv run python -c "
from deviate.core.constitution import validate_placeholders
result = validate_placeholders('src/deviate/prompts/constitution_seed.md')
assert result.all_present
print(f'Placeholders OK: {len(result.variables)} variables present')
"

# Run tests
pytest tests/test_cli/test_constitution.py tests/test_cli/test_inspect.py tests/test_core/test_constitution.py -v --no-header -q
```
