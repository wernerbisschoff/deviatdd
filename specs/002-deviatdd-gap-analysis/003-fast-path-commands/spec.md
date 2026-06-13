# FEATURE_SPECIFICATION: specs/002-deviatdd-gap-analysis/003-fast-path-commands/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: 002 — DeviaTDD Docs-to-Code Gap Resolution
- **Local Issue File**: `specs/002-deviatdd-gap-analysis/issues/003-fast-path-commands.md`
- **Issue ID**: ISS-002-003
- **Epic ID**: ISS-002
- **Subsystem A — Adhoc Task Fast-Path**:
  - `src/deviate/cli/adhoc.py` — NEW: `adhoc pre <description>` and `adhoc post <manifest>` CLI commands
  - `src/deviate/core/complexity.py` — NEW: `ComplexityGate.classify(description)` — LLM-based LOW/MEDIUM/HIGH classification
  - `src/deviate/state/ledger.py` — MODIFY: `AdhocRecord` model (appended to `specs/adhoc.jsonl`)
- **Subsystem B — Feature Workspace Scaffold**:
  - `src/deviate/cli/feature.py` or `__init__.py` — NEW: `deviate feature create <title> [--slug]` standalone command
  - `src/deviate/cli/meso.py` — MODIFY: `specify pre` calls feature creation logic internally if no active workspace
- **Shared dependency**: `src/deviate/cli/__init__.py` — MODIFY: register `adhoc` and `feature` sub-apps

## THE_PROBLEM_CONTRACT

**User Journey — Adhoc**: A developer has a small task—"Fix typo in README". They run `deviate adhoc pre "Fix typo in README"`. The complexity gate classifies it as LOW (`execution_mode=DIRECT`), appends an `AdhocRecord` to `specs/adhoc.jsonl`, and emits a JSON contract with the execution plan. They execute the fix directly and run `deviate adhoc post <manifest>` to register completion. MEDIUM complexity also routes to DIRECT mode. HIGH complexity without `--skip-gates` halts with `COMPLEXITY_GATE_REJECTION`.

**User Journey — Feature**: A developer needs to scaffold a new feature workspace. They run `deviate feature create "auth overhaul"`. The command derives a URL-safe kebab-case slug (`auth-overhaul`), creates `specs/auth-overhaul/`, creates branch `feat/auth-overhaul`, and updates the session. If the branch already exists, it skips and returns existing info. An explicit `--slug` flag overrides the derivation. When `deviate specify pre` is called without a session, it internally invokes feature creation before scaffolding.

**System Contract**: Two independent fast-path commands that bypass the full orchestration pipeline. Both share a common pattern: `pre` → validate/classify/scaffold → emit contract → `post` → validate/record/commit. Neither modifies the micro-layer TDD cycle.

## SCOPE_BOUNDARIES

### Hard Inclusions

- `deviate adhoc pre <description>` — complexity gate → classification → `AdhocRecord` append → JSON contract
- `deviate adhoc post <manifest>` — validate → transition → commit
- `ComplexityGate.classify(description)` — LLM-based with LOW/MEDIUM/HIGH tiers
- `specs/adhoc.jsonl` — auto-created on first append
- LOW complexity → `DIRECT` mode, contract emitted, no TDD cycle required
- MEDIUM complexity → `DIRECT` mode (same as LOW)
- HIGH complexity → `TDD` mode; requires `--skip-gates` flag to proceed without rejection
- HIGH complexity without `--skip-gates` → halts with `COMPLEXITY_GATE_REJECTION`
- `deviate feature create <title> [--slug]` — slug derivation → branch → directory → session
- `specify pre` — internal call to feature creation if no session exists
- `AdhocRecord` schema: `issue_id`, `description`, `execution_mode`, `status`, `timestamp`
- `adhoc post <manifest>` with non-existent manifest ID → error `MANIFEST_NOT_FOUND`, non-zero exit
- `feature create --slug` → explicit slug overrides derived slug from title
- Feature branch naming: `feat/{SLUG}` convention

### Defensive Exclusions

- NO changes to micro-layer TDD cycle or phase dispatch
- NO changes to existing `specify pre` logic beyond the feature creation call
- NO changes to context sync or AGENTS.md alignment
- NO file-count heuristic fallback for complexity classification
- NO custom branch prefix support
- NO changes to `deviate init`, `deviate context`, or constitution generation

## PERFORMANCE_CONSTRAINTS

| Constraint | Target | Notes |
|---|---|---|
| `adhoc pre` classification (with LLM stub) | L_max <= 100ms | Stub response, no network |
| `adhoc pre` classification (with real LLM) | L_max <= 3000ms | Network-bound, timeout at 10s |
| `adhoc post` validation | L_max <= 200ms | Local file read + state transition |
| `feature create` scaffolding | L_max <= 300ms | Directory + branch + session write |
| `specify pre` internal feature create | L_max <= 500ms | Includes branch creation |
| `specs/adhoc.jsonl` append | L_max <= 50ms | Single-line append |
| Test suite contribution | < 5s total | All new tests combined |

## MULTI_TIERED_VERIFICATION_TARGETS

| Tier | Target | Command |
|---|---|---|
| Unit — Complexity Gate | `tests/test_core/test_complexity.py` — `test_complexity_gate_classify_low`, `test_complexity_gate_classify_medium`, `test_complexity_gate_classify_high` | `pytest tests/test_core/test_complexity.py -v --no-header -q` |
| Unit — AdhocRecord | `tests/test_state/test_ledger.py` — `test_adhoc_record_schema`, `test_adhoc_record_status_transitions` | `pytest tests/test_state/test_ledger.py -v --no-header -q` |
| Unit — Adhoc CLI | `tests/test_cli/test_adhoc.py` — `test_adhoc_pre_low_complexity`, `test_adhoc_pre_medium_complexity`, `test_adhoc_pre_high_complexity_rejected`, `test_adhoc_pre_high_complexity_skip_gates`, `test_adhoc_post_completes_record`, `test_adhoc_post_missing_manifest` | `pytest tests/test_cli/test_adhoc.py -v --no-header -q` |
| Unit — Feature Create | `tests/test_cli/test_feature.py` — `test_feature_create_scaffold`, `test_feature_create_existing_branch`, `test_feature_create_explicit_slug` | `pytest tests/test_cli/test_feature.py -v --no-header -q` |
| Integration — Meso | `tests/test_cli/test_meso.py` — `test_specify_pre_invokes_feature_create` | `pytest tests/test_cli/test_meso.py -v --no-header -q` |
| Full verification | Constitution lint + test | `ruff check . && pytest tests/ -v --no-header -q` |

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-AdhocLowComplexity: Adhoc Pre with LOW Complexity → DIRECT Mode

- **Upstream Requirement Traceability**: FR-003 (Adhoc Task Fast-Path)
- **Scenario 1**: User runs `adhoc pre` with a LOW-complexity description
  - **Given** the `ComplexityGate` classifies the description as `LOW`
  - **When** the user executes `deviate adhoc pre "Fix typo in README"`
  - **Then** an `AdhocRecord` is appended to `specs/adhoc.jsonl` with `execution_mode=DIRECT` and `status=PENDING`
  - **And** a JSON contract is emitted on stdout
  - **And** exit code is 0

### US-002-AdhocMediumComplexity: Adhoc Pre with MEDIUM Complexity → DIRECT Mode

- **Upstream Requirement Traceability**: FR-003 (Adhoc Task Fast-Path)
- **Scenario 1**: User runs `adhoc pre` with a MEDIUM-complexity description
  - **Given** the `ComplexityGate` classifies the description as `MEDIUM`
  - **When** the user executes `deviate adhoc pre "Add form validation with 3 fields"`
  - **Then** the record is created with `execution_mode=DIRECT` and `status=PENDING`
  - **And** no `--skip-gates` flag is required
  - **And** exit code is 0

### US-003-AdhocHighComplexityRejected: Adhoc Pre with HIGH Complexity Rejects Without Flag

- **Upstream Requirement Traceability**: FR-003 (Adhoc Task Fast-Path)
- **Scenario 1**: User runs `adhoc pre` with a HIGH-complexity description and no `--skip-gates`
  - **Given** the `ComplexityGate` classifies the description as `HIGH`
  - **When** the user executes `deviate adhoc pre "Build authentication system with OAuth, JWT, RBAC"`
  - **Then** the command halts with error `COMPLEXITY_GATE_REJECTION`
  - **And** no record is appended to `specs/adhoc.jsonl`
  - **And** exit code is non-zero

### US-004-AdhocHighComplexitySkipGates: Adhoc Pre with HIGH Complexity Proceeds With Flag

- **Upstream Requirement Traceability**: FR-003 (Adhoc Task Fast-Path)
- **Scenario 1**: User runs `adhoc pre` with a HIGH-complexity description and `--skip-gates`
  - **Given** the `ComplexityGate` classifies the description as `HIGH`
  - **When** the user executes `deviate adhoc pre --skip-gates "Build auth system with OAuth, JWT, RBAC"`
  - **Then** an `AdhocRecord` is appended with `execution_mode=TDD` and `status=PENDING`
  - **And** exit code is 0

### US-005-AdhocPostCompletes: Adhoc Post Completes a Valid PENDING Record

- **Upstream Requirement Traceability**: FR-003 (Adhoc Task Fast-Path)
- **Scenario 1**: User runs `adhoc post` with a manifest ID matching a PENDING record
  - **Given** a PENDING `AdhocRecord` exists in `specs/adhoc.jsonl` with `issue_id=<manifest>`
  - **When** the user executes `deviate adhoc post <manifest>`
  - **Then** the record transitions to `status=COMPLETED`
  - **And** the session returns to `IDLE`
  - **And** exit code is 0

### US-006-AdhocPostMissingManifest: Adhoc Post Fails on Non-Existent Manifest

- **Upstream Requirement Traceability**: FR-003 (Adhoc Task Fast-Path)
- **Scenario 1**: User runs `adhoc post` with a manifest ID not found in `specs/adhoc.jsonl`
  - **Given** no record exists in `specs/adhoc.jsonl` with `issue_id=<manifest>`
  - **When** the user executes `deviate adhoc post nonexistent-manifest`
  - **Then** the command errors with `MANIFEST_NOT_FOUND`
  - **And** exit code is non-zero

### US-007-FeatureCreateScaffold: Feature Create Creates Directory, Branch, and Session

- **Upstream Requirement Traceability**: FR-004 (Feature Workspace Scaffold)
- **Scenario 1**: User creates a new feature workspace
  - **Given** no existing branch named `feat/auth-overhaul`
  - **When** the user executes `deviate feature create "auth overhaul"`
  - **Then** a directory `specs/auth-overhaul/` is created
  - **And** a git branch `feat/auth-overhaul` is created
  - **And** the session is updated with the new feature context
  - **And** exit code is 0

### US-008-FeatureCreateExisting: Feature Create Skips When Branch Already Exists

- **Upstream Requirement Traceability**: FR-004 (Feature Workspace Scaffold)
- **Scenario 1**: User tries to create a feature with a title whose branch already exists
  - **Given** a branch named `feat/auth-overhaul` already exists
  - **When** the user executes `deviate feature create "auth overhaul"`
  - **Then** the command skips branch creation
  - **And** returns existing feature info without error
  - **And** exit code is 0

### US-009-FeatureCreateExplicitSlug: Feature Create Honors Explicit --slug

- **Upstream Requirement Traceability**: FR-004 (Feature Workspace Scaffold)
- **Scenario 1**: User provides an explicit `--slug` that differs from the derived slug
  - **Given** no existing branch named `feat/user-auth`
  - **When** the user executes `deviate feature create "auth overhaul" --slug user-auth`
  - **Then** the slug used is `user-auth` (overrides derived `auth-overhaul`)
  - **And** directory `specs/user-auth/` is created
  - **And** branch `feat/user-auth` is created
  - **And** exit code is 0

### US-010-SpecifyPreFeatureCreate: Specify Pre Invokes Feature Create When No Session

- **Upstream Requirement Traceability**: FR-004 (Feature Workspace Scaffold)
- **Scenario 1**: User runs `deviate specify pre` without an active session
  - **Given** no active session exists in `.deviate/session.json`
  - **When** the user executes `deviate specify pre`
  - **Then** feature creation logic is invoked internally (prompting for title or using default)
  - **And** a new feature workspace is scaffolded before spec processing
  - **And** exit code is 0

## SYSTEM_STATUS_SUMMARY

| Parameter | Value |
|---|---|
| **STATUS** | `SPECIFIED` |
| **EPIC_SLUG** | `002-deviatdd-gap-analysis` |
| **BRANCH_NAME** | `feat/002-deviatdd-gap-analysis/003-fast-path-commands` |
| **SPEC_PATH** | `specs/002-deviatdd-gap-analysis/003-fast-path-commands/spec.md` |
| **ISSUE_ID** | `ISS-002-003` |
| **NEXT_ACTION** | `/deviate-tasks` — decompose spec.md into task decomposition (tasks.md) |
