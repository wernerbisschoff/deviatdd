---
title: Fast-Path Commands — Adhoc Task Pipeline & Feature Create
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-001"]
coordinates_with: ["ISS-002-002"]
issue_id: ISS-002-003
epic_id: ISS-002
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/003-fast-path-commands.md`
- **Workstation Paths**:
  - `src/deviate/cli/adhoc.py` — NEW: Typer app with `adhoc pre <description>`, `adhoc post <manifest>`
  - `src/deviate/core/complexity.py` — NEW: `ComplexityGate.classify()` with LLM-based classification
  - `src/deviate/cli/macro.py` — MODIFY: add `feature create <title>` command
  - `src/deviate/cli/meso.py` — MODIFY: `specify pre` calls feature creation if no workspace
  - `src/deviate/state/ledger.py` — MODIFY: add `AdhocRecord` model
  - `src/deviate/cli/__init__.py` — MODIFY: register `adhoc_app`

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer notices a typo in the README and runs `deviate adhoc pre "Fix typo in README"`. The complexity gate classifies it as LOW, creates an `AdhocRecord` in `specs/adhoc.jsonl` with `execution_mode=DIRECT`, and emits a contract. The developer fixes the typo, runs `deviate adhoc post <manifest>` to register completion. For a larger feature, they run `deviate feature create "auth overhaul"` which derives the slug `auth-overhaul`, creates branch `feat/auth-overhaul`, scaffolds `specs/auth-overhaul/`, and updates the session.

**System Response**: Complexity gate uses LLM to classify LOW/MEDIUM/HIGH (LOW→DIRECT, MEDIUM/HIGH→TDD). HIGH complexity requires `--skip-gates` flag. Adhoc records are append-only JSONL with PENDING→IN_PROGRESS→COMPLETED|FAILED lifecycle. Feature create derives URL-safe slug, creates git branch, scaffolds directory, and integrates with `specify pre` as internal fallback.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `cli/adhoc.py` with `adhoc pre <description>` and `adhoc post <manifest>`
- `core/complexity.py` with `ComplexityGate.classify()` — LLM-based classification
- `specs/adhoc/` directory auto-creation on first use
- `AdhocRecord` model in `state/ledger.py` with `extra = "forbid"`
- `feature create <title> [--slug]` in `cli/macro.py`
- `specify pre` internal fallback to feature creation if no workspace
- `--skip-gates` flag for HIGH complexity bypass

### Defensive Exclusions
- NO changes to context sync or constitution validation
- NO changes to profile dispatch
- NO changes to cache discipline
- NO changes to skill files
- NO changes to inspect/ledger listing commands
- NO deep integration with the micro-layer TDD cycle

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-003 | Adhoc Task Fast-Path | FR-003-Adhoc |
| FR-004 | Feature Workspace Scaffold | FR-004-FeatureCreate |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-003-01 | `adhoc pre "Fix typo"` with LOW complexity appends record with `execution_mode=DIRECT`, `status=PENDING` |
| AC-003-02 | `adhoc pre` with HIGH complexity halts with `COMPLEXITY_GATE_REJECTION` unless `--skip-gates` |
| AC-003-03 | `adhoc post <manifest>` transitions pending record to `COMPLETED`, session returns to `IDLE` |
| AC-004-01 | `feature create "auth overhaul"` creates `specs/auth-overhaul/`, branch `feat/auth-overhaul`, updates session |
| AC-004-02 | `specify pre` without active workspace calls feature creation internally |

### Data Model Entities
- `AdhocRecord` — `src/deviate/state/ledger.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_cli/test_adhoc.py` — `test_adhoc_pre_low`, `test_adhoc_pre_medium`, `test_adhoc_pre_high_rejected`, `test_adhoc_pre_high_skip_gates`, `test_adhoc_post`
- `tests/test_core/test_complexity.py` — `test_complexity_gate_classify_low`, `test_complexity_gate_classify_high`, `test_complexity_gate_threshold`
- `tests/test_cli/test_macro.py` — `test_feature_create_basic`, `test_feature_create_with_slug`, `test_feature_create_existing_branch`
- `tests/test_cli/test_meso.py` — `test_specify_pre_calls_feature_create`
- `tests/test_state/test_ledger.py` — `test_adhoc_record_model`, `test_adhoc_record_validation`

## [DEMONSTRATION_PATH]

```bash
# Verify adhoc pre with LOW complexity
uv run deviate adhoc pre "Fix typo in README" --json 2>/dev/null | python -c "
import sys, json
c = json.load(sys.stdin)
assert c['execution_mode'] == 'DIRECT'
assert c['status'] == 'PENDING'
print('Adhoc LOW classification OK')
"

# Verify feature create
uv run deviate feature create "test-feature" --json 2>/dev/null | python -c "
import sys, json
c = json.load(sys.stdin)
assert 'specs/test-feature' in str(c)
print('Feature create OK')
"

# Verify HIGH complexity rejection
uv run deviate adhoc pre "Rewrite entire authentication system with 15 files" 2>&1 | grep -q 'COMPLEXITY_GATE_REJECTION' && echo 'HIGH rejection OK'

# Run verification tests
pytest tests/test_cli/test_adhoc.py tests/test_core/test_complexity.py tests/test_cli/test_macro.py -v --no-header -q
```
