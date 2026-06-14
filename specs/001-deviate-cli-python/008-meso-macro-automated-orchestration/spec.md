# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/008-meso-macro-automated-orchestration/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: `001-deviate-cli-python`
- **Issue ID**: `ISS-001-008`
- **Issue Title**: `[FR-008] Meso/Macro Automated Orchestration Layer`
- **Upstream PRD Source**: `specs/001-deviate-cli-python/prd.md`
- **Blocked By**: `ISS-001-004` (Micro-layer TDD Sandbox)
- **Coordinates With**: None
- **Workstation Paths**:
  - `src/deviate/cli/meso.py` — Add `meso` command with automated specify→tasks pipeline
  - `src/deviate/cli/macro.py` — Add `macro` command with automated explore→research→prd→shard pipeline
  - `src/deviate/core/agent.py` — Reuse agent backend from ISS-001-004
  - `src/deviate/prompts/auto/` — Add slim prompt templates for meso/macro phases
  - `src/deviate/state/config.py` — Session state transitions for automated pipelines
  - `tests/test_integration/test_meso_orchestration.py`
  - `tests/test_integration/test_macro_orchestration.py`
  - `tests/test_meso/test_meso_orchestration.py`
  - `tests/test_macro/test_macro_orchestration.py`
  - `tests/test_integration/test_full_meso_pipeline.py`
  - `tests/test_integration/test_full_macro_pipeline.py`

## THE_PROBLEM_CONTRACT

As a developer driving the full DeviaTDD workflow, I need the CLI to automatically orchestrate the meso-layer (specify→tasks) and macro-layer (explore→research→prd→shard) pipelines — running each phase's pre-flight checks, invoking the agent with slim prompts, validating outputs, committing, and advancing state — without manually stepping through `deviate <phase> pre` and `deviate <phase> post` commands for each phase.

The automated pipeline reuses the same internal pre/post functions already implemented in the manual commands (ISS-001-005). It sequences them automatically and interposes agent invocations with slim prompt templates that follow the static-prefix + dynamic-suffix KV-cacheable pattern established in ISS-001-004.

## SCOPE_BOUNDARIES

### Hard Inclusions

- **`deviate meso`** — Automated specify→tasks pipeline.
  - `--issue ISS-NNN` — Target a specific issue (default: next unblocked BACKLOG).
  - `--dry-run` — Emit prompts and contracts without invoking agent or committing.
  - Discovers next unblocked issue from ledger if no `--issue` given.
  - Aborts if issue has unresolved blocking dependencies.
  - If issue is already COMPLETED, aborts with error.
  - If issue is in PROGRESS state, resets to SPECIFY phase and re-runs from scratch, discarding stale progress.
  - Respects `--force` semantics from underlying pre/post commands.
- **`deviate macro`** — Automated explore→research→prd→shard pipeline.
  - `--target <slug>` — Target a specific feature bucket slug.
  - `--from <phase>` — Resume from a specific phase (explore | research | prd | shard).
  - `--from <phase>` force-regenerates from the requested phase, ignoring upstream artifact staleness.
  - `--dry-run` — Emit prompts and contracts without invoking agent or committing.
  - Validates upstream artifact existence at each phase boundary.
- **Slim prompt templates** (`src/deviate/prompts/auto/`):
  - `explore.md` — Problem → codebase scan report
  - `research.md` — Explore output → design + data-model
  - `prd.md` — Design + data-model → product requirements document
  - `shard.md` — PRD → shard issue files
  - `specify.md` — Issue body + PRD reqs → spec.md with Gherkin
  - `tasks.md` — Spec.md → tasks.md with TDD task decomposition
  - Each follows the same static-prefix + dynamic-suffix pattern as ISS-001-004 slim prompts.
- **Agent backend reuse**: Uses `src/deviate/core/agent.py` from ISS-001-004 — same heredoc pipe invocation, same YAML handover manifest parsing, same timeout handling.
- **Constitution & Governance Injection**: `specs/constitution.md` and `CLAUDE.md` are read once at pipeline start and injected into every slim prompt's static KV-cacheable prefix.
- **Session state**: Phase transitions tracked in `.deviate/session.json`. Pipeline resumes correctly if interrupted (e.g., detect existing spec.md → skip SPECIFY, proceed to TASKS). Completed phases are skipped idempotently on re-run.
- **Error recovery**: If a phase fails (agent non-zero exit, validation failure, commit failure), abort pipeline, surface error with phase context, leave state at last successful phase.
- **`--dry-run` mode**: No state mutations (session not advanced, no artifacts written, no commits). Contracts and slim prompts are emitted to stdout only.

### Defensive Exclusions

- Individual pre/post command implementation (covered by ISS-001-005).
- Micro-layer TDD execution (covered by ISS-001-004).
- Aider integration (covered by ISS-ADH-002).
- Core module implementations (covered by ISS-001-005).
- State persistence and concurrency safety (covered by ISS-001-006).
- Prompt scaffolding and user-editable overrides (covered by ISS-001-009).
- Web or GUI frontend for pipeline visualization.

## PERFORMANCE_CONSTRAINTS

- `L_max <= 500ms` for pipeline discovery and contract emission (pre-flight before agent invocation).
- `L_max <= 200ms` per agent prompt assembly (static prefix + dynamic suffix concatenation).
- Pipeline overhead (sequencing, state checks, validation) must not exceed 300ms cumulative per phase.
- Agent invocation time is excluded from constraint — governed by external LLM backend.

## MULTI_TIERED_VERIFICATION_TARGETS

- **Unit Tests**:
  - `tests/test_meso/test_meso_orchestration.py` — Meso pipeline discovery, sequencing, error handling
  - `tests/test_macro/test_macro_orchestration.py` — Macro pipeline sequencing, `--from` resume, `--dry-run`
- **Integration Tests**:
  - `tests/test_integration/test_meso_orchestration.py` — Full meso pipeline with mocked agent
  - `tests/test_integration/test_macro_orchestration.py` — Full macro pipeline with mocked agent
  - `tests/test_integration/test_full_meso_pipeline.py` — End-to-end meso with actual agent invocation (optional, excluded from CI gate)
  - `tests/test_integration/test_full_macro_pipeline.py` — End-to-end macro with actual agent invocation (optional, excluded from CI gate)

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-001-MESO: `deviate meso` executes full specify→tasks automated pipeline

* **Upstream Requirement Traceability**: FR-008-MESO

1. **Given** an unblocked BACKLOG issue exists in `specs/issues.jsonl`
   **When** the user executes `deviate meso`
   **Then** the CLI discovers the issue, runs specify pre, invokes the agent with a slim specify prompt, validates spec.md, commits, advances to TASKS, runs tasks pre, invokes the agent with a slim tasks prompt, validates tasks.md, commits, and advances session to IDLE.

2. **Given** a specific issue ID `ISS-001-004`
   **When** the user executes `deviate meso --issue ISS-001-004`
   **Then** the pipeline targets only `ISS-001-004`, skipping automatic issue discovery.

3. **Given** an issue with status PROGRESS (partially completed)
   **When** the user executes `deviate meso --issue ISS-001-004`
   **Then** the pipeline resets the issue state to SPECIFY and re-runs from scratch, discarding stale progress artifacts.

4. **Given** an issue with status COMPLETED
   **When** the user executes `deviate meso --issue ISS-001-004`
   **Then** the CLI aborts with an `ISSUE_COMPLETED` error and does not modify any state.

5. **Given** an issue with unresolved blocking dependencies
   **When** the user executes `deviate meso`
   **Then** the CLI skips the blocked issue and attempts to discover the next unblocked issue.

6. **Given** no unblocked issues exist in the ledger
   **When** the user executes `deviate meso`
   **Then** the CLI exits with a `NO_UNBLOCKED_ISSUES` error and surfaces the ledger state.

### US-002-MACRO: `deviate macro` executes full explore→research→prd→shard automated pipeline

* **Upstream Requirement Traceability**: FR-008-MACRO

1. **Given** `specs/constitution.md` exists and is valid
   **When** the user executes `deviate macro --target my-feature`
   **Then** the CLI runs the full explore→research→prd→shard pipeline: invokes the agent at each phase with slim prompts, commits artifacts, registers shard issues in the ledger, and advances session through all four phases back to IDLE.

2. **Given** an interrupted pipeline where `explore.md` and `design.md` exist but `prd.md` does not
   **When** the user executes `deviate macro --target 001-deviate-cli-python --from prd`
   **Then** the pipeline resumes at PRD, skipping explore and research phases, and force-regenerates prd.md (ignoring staleness of upstream artifacts).

3. **Given** a feature bucket slug that does not exist in the ledger
   **When** the user executes `deviate macro --target nonexistent-slug`
   **Then** the CLI exits with a `BUCKET_NOT_FOUND` error.

4. **Given** an invalid `--from` phase value (e.g., `--from invalid_phase`)
   **When** the user executes `deviate macro --target my-feature --from invalid_phase`
   **Then** the CLI exits with an `INVALID_PHASE` error listing valid phase options.

5. **Given** a phase boundary where the required upstream artifact is missing (e.g., no explore.md when entering RESEARCH)
   **When** the automated pipeline reaches that phase boundary
   **Then** the CLI emits `UPSTREAM_MISSING` with the missing artifact path and aborts the pipeline.

### US-003-SLIM-PROMPTS: Slim prompt templates exist for all six meso/macro phases

* **Upstream Requirement Traceability**: FR-008-SLIM-PROMPTS

1. **Given** the package resource directory `src/deviate/prompts/auto/`
   **When** the CLI enumerates available prompt templates
   **Then** six files exist: `explore.md`, `research.md`, `prd.md`, `shard.md`, `specify.md`, `tasks.md`.

2. **Given** any slim prompt template in `src/deviate/prompts/auto/`
   **When** inspected for structure
   **Then** the template follows the static-prefix (role definitions, systemic constraints) + dynamic-suffix (volatile runtime attributes in `<context>`) pattern, matching the established pattern from ISS-001-004.

3. **Given** a slim prompt template file that is missing or unreadable
   **When** the pipeline attempts to load it during prompt assembly
   **Then** the CLI exits with `TEMPLATE_MISSING` including the expected template path.

### US-004-CONSTITUTION: Constitution and CLAUDE.md injected into every automated prompt

* **Upstream Requirement Traceability**: FR-008-CONSTITUTION

1. **Given** `specs/constitution.md` and `CLAUDE.md` exist in the repo root
   **When** `deviate meso` or `deviate macro` builds any slim prompt for agent invocation
   **Then** both files' content is injected into the prompt's static KV-cacheable prefix region.

2. **Given** `specs/constitution.md` is missing or unreadable
   **When** the automated pipeline initializes
   **Then** the CLI emits a `CONSTITUTION_MISSING` warning but continues execution (non-fatal).

3. **Given** `CLAUDE.md` is missing
   **When** the automated pipeline initializes
   **Then** the CLI skips the CLAUDE.md injection silently and continues execution.

### US-005-RECOVERY: Pipeline resumes at correct phase on interruption

* **Upstream Requirement Traceability**: FR-008-RECOVERY

1. **Given** an interrupted meso pipeline where spec.md is committed but tasks.md does not exist
   **When** the user re-runs `deviate meso --issue ISS-001-004`
   **Then** the pipeline detects the existing spec.md, skips the SPECIFY phase, and proceeds directly to the TASKS phase.

2. **Given** an interrupted macro pipeline where explore.md and design.md are committed but prd.md does not exist
   **When** the user re-runs `deviate macro --target my-feature`
   **Then** the pipeline detects completed phases from session state, skips explore and research, and resumes at PRD.

3. **Given** a phase fails due to agent non-zero exit during a meso pipeline
   **When** the agent returns a non-zero exit code
   **Then** the pipeline aborts, surfaces the agent's stderr with phase context (`SPECIFY failed: agent exited with code 1`), and leaves session state at the last successful phase boundary.

4. **Given** a phase fails due to validation failure (e.g., spec.md missing Gherkin blocks)
   **When** the validation gate runs
   **Then** the pipeline aborts with a `VALIDATION_FAILED` error including diagnostic details, and does not advance session state.

### US-006-DRY-RUN: `--dry-run` flag emits prompts and contracts without side effects

* **Upstream Requirement Traceability**: FR-008-MESO (parent: FR-008)

1. **Given** any valid initial state for meso or macro
   **When** the user executes `deviate meso --dry-run` or `deviate macro --dry-run`
   **Then** pre-flight contracts and assembled slim prompts are emitted to stdout, but no agents are invoked, no artifacts are written, and no session state is advanced (session remains at the initial phase).

2. **Given** a `deviate meso --dry-run` execution targeting a specific issue
   **When** the command completes
   **Then** the output includes the discovered contract and the assembled specify prompt text, but the worktree is not created and the issue remains in its original ledger state.

3. **Given** a `deviate macro --dry-run` execution
   **When** the command completes
   **Then** the output includes the feature bucket allocation contract and the assembled explore prompt text, but no files are created and the ledger is not modified.

### US-007-FORCE-SEMANTICS: Pipeline supports `--force` to bypass pre-flight guards

* **Upstream Requirement Traceability**: FR-008-MESO (parent: FR-008)

1. **Given** a pre-flight check fails (e.g., push-to-claim failure for a worktree)
   **When** the user re-runs with `--force`
   **Then** the pipeline bypasses the failing pre-flight guard and proceeds to the next step.

2. **Given** a pipeline phase that previously failed validation
   **When** the user re-runs with `--force` after fixing the validation issue
   **Then** the pipeline proceeds from the phase where validation previously failed.

## SYSTEM_STATUS_SUMMARY

| Variable | Value |
|---|---|
| **STATUS** | SPECIFY |
| **EPIC_SLUG** | `001-deviate-cli-python` |
| **BRANCH_NAME** | `feat/001-deviate-cli-python/008-meso-macro-automated-orchestration` |
| **SPEC_PATH** | `specs/001-deviate-cli-python/008-meso-macro-automated-orchestration/spec.md` |
| **ISSUE_ID** | `ISS-001-008` |
| **NEXT_ACTION** | TASKS |
