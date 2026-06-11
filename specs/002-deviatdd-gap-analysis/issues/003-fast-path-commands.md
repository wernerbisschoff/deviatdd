---
title: Fast-Path Commands — Adhoc Task Fast-Path and Feature Workspace Scaffold
labels: ["feature", "ISS-002", "P1"]
source_file: specs/002-deviatdd-gap-analysis/prd.md
blocked_by: ["ISS-002-001"]
coordinates_with: []
issue_id: ISS-002-003
epic_id: ISS-002
type: feature
---

## [SYSTEM_TOPOLOGY_MAPPING]

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/003-fast-path-commands.md`
- **Workstation Paths**:
  - `src/deviate/cli/adhoc.py` — NEW: `adhoc pre <description>` and `adhoc post <manifest>` CLI commands
  - `src/deviate/core/complexity.py` — NEW: `ComplexityGate.classify(description)` — LLM-based LOW/MEDIUM/HIGH classification
  - `src/deviate/state/ledger.py` — MODIFY: `AdhocRecord` model (if not present)
  - `src/deviate/cli/__init__.py` — MODIFY: register `adhoc` app
  - `src/deviate/cli/meso.py` — MODIFY: `specify pre` calls feature creation logic internally if no active workspace
  - `src/deviate/cli/feature.py` or `__init__.py` — NEW: `deviate feature create <title> [--slug]` standalone command

## [THE_PROBLEM_CONTRACT]

**User Journey**: A developer has a small task—"Fix typo in README". They run `deviate adhoc pre "Fix typo in README"`. The complexity gate classifies it as LOW (`execution_mode=DIRECT`), appends an `AdhocRecord` to `specs/adhoc.jsonl`, and emits a JSON contract with the execution plan. They execute the fix directly and run `deviate adhoc post <manifest>` to register completion. For a new feature, they run `deviate feature create "auth overhaul"` which creates `specs/auth-overhaul/`, creates a `feat/auth-overhaul` branch, and updates the session. When `deviate specify pre` is called without an existing workspace, it internally invokes feature creation before scaffolding.

**System Response**: LOW complexity → `DIRECT` mode, contract emitted, no TDD cycle required. MEDIUM/HIGH → `TDD` mode, proceeds through full TDD pipeline. HIGH tasks without `--skip-gates` halt with `COMPLEXITY_GATE_REJECTION`. Feature creation derives a URL-safe kebab-case slug, creates `specs/{SLUG}/` directory, initializes git branch `feat/{SLUG}`, updates session. If branch exists, skip and return existing info.

## [SCOPE_BOUNDARIES]

### Hard Inclusions
- `deviate adhoc pre <description>` — complexity gate → classification → `AdhocRecord` append → JSON contract
- `deviate adhoc post <manifest>` — validate → transition → commit
- `ComplexityGate.classify(description)` — LLM-based with LOW/MEDIUM/HIGH tiers
- `specs/adhoc.jsonl` — auto-created on first append
- HIGH complexity → requires `--skip-gates` flag
- `deviate feature create <title> [--slug]` — slug derivation → branch → directory → session
- `specify pre` — internal call to feature creation if no session exists
- `AdhocRecord` schema: `issue_id`, `description`, `execution_mode`, `status`, `timestamp`

### Defensive Exclusions
- NO changes to micro-layer TDD cycle or phase dispatch
- NO changes to existing `specify pre` logic beyond the feature creation call
- NO changes to context sync or AGENTS.md alignment
- Feature branch naming: `feat/{SLUG}` convention — no custom branch prefix
- Adhoc complexity is LLM-based with confidence threshold — no file-count heuristic fallback

## [UPSTREAM_REQUIREMENT_TRACING]

### Functional Requirements
| ID | Title | PRD Section |
|----|-------|-------------|
| FR-003 | Adhoc Task Fast-Path | FR-003-Adhoc |
| FR-004 | Feature Workspace Scaffold | FR-004-FeatureCreate |

### Acceptance Criteria
| ID | Description |
|----|-------------|
| AC-003-01 | `adhoc pre "Fix typo"` with LOW complexity → `AdhocRecord` appended (execution_mode=DIRECT, status=PENDING) |
| AC-003-02 | `adhoc pre` with HIGH complexity without `--skip-gates` → halts with `COMPLEXITY_GATE_REJECTION` |
| AC-003-03 | `adhoc post <manifest>` with valid PENDING record → transitions to COMPLETED, session returns to IDLE |
| AC-004-01 | `feature create "auth overhaul"` → `specs/auth-overhaul/` exists, branch `feat/auth-overhaul` created, session updated |
| AC-004-02 | `specify pre` without active session → internally calls feature creation logic |

### Data Model Entities
- `AdhocRecord` — `src/deviate/state/ledger.py`

## [MULTI_TIERED_VERIFICATION_TARGETS]

- `tests/test_cli/test_adhoc.py` — `test_adhoc_pre_low_complexity`, `test_adhoc_pre_high_complexity_rejected`, `test_adhoc_post_completes_record`
- `tests/test_core/test_complexity.py` — `test_complexity_gate_classify_low`, `test_complexity_gate_classify_high`
- `tests/test_state/test_ledger.py` — `test_adhoc_record_schema`, `test_adhoc_record_status_transitions`
- `tests/test_cli/test_feature.py` — `test_feature_create_scaffold`, `test_feature_create_existing_branch`
- `tests/test_cli/test_meso.py` — `test_specify_pre_invokes_feature_create`

## [DEMONSTRATION_PATH]

```bash
# Verify adhoc pre with LOW complexity (mock LLM)
uv run python -c "
from deviate.core.complexity import ComplexityGate
# Stub the LLM call
result = ComplexityGate.classify('Fix typo in README', _stub='LOW')
assert result.execution_mode == 'DIRECT'
print(f'Adhoc classification OK: {result.execution_mode}')
"

# Verify adhoc pre with HIGH complexity rejection
uv run python -c "
from deviate.core.complexity import ComplexityGate
result = ComplexityGate.classify('Build authentication system with OAuth, JWT, sessions, RBAC', _stub='HIGH')
assert result.execution_mode == 'TDD'
assert result.level == 'HIGH'
print(f'High complexity OK: {result.level}')
"

# Run tests
pytest tests/test_cli/test_adhoc.py tests/test_core/test_complexity.py tests/test_state/test_ledger.py -v --no-header -q
```
