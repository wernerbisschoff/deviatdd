---
title: "[FR-008] Meso/Macro Automated Orchestration Layer"
labels: ["epic:001-deviate-cli-python", "layer:meso", "layer:macro"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-004"]
coordinates_with: []
issue_id: "ISS-008"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/008-meso-macro-automated-orchestration.md`
- **Workstation Paths**:
  - `src/deviate/cli/meso.py` — Add `meso` command with automated specify→tasks pipeline
  - `src/deviate/cli/macro.py` — Add `macro` command with automated explore→research→prd→shard pipeline
  - `src/deviate/core/agent.py` — Reuse agent backend from ISS-004
  - `src/deviate/prompts/auto/` — Add slim prompt templates for meso/macro phases
  - `src/deviate/state/config.py` — Session state transitions for automated pipelines
  - `tests/test_integration/test_meso_orchestration.py`
  - `tests/test_integration/test_macro_orchestration.py`

## [THE_PROBLEM_CONTRACT]
As a developer driving the full DeviaTDD workflow, I need the CLI to automatically orchestrate the meso-layer (specify→tasks) and macro-layer (explore→research→prd→shard) pipelines — running each phase's pre-flight checks, invoking the agent with slim prompts, validating outputs, committing, and advancing state — without the agent manually stepping through `deviate <phase> pre` and `deviate <phase> post` commands.

## [ARCHITECTURAL_OVERVIEW]

### Relationship to Manual Path

The automated pipeline reuses the same internal pre/post functions already implemented in the manual commands. It just sequences them automatically and interposes agent invocations:

```
Manual path:                Automated path:
  deviate specify pre         deviate meso
  [agent writes spec.md]        ├─ _specify_pre() (internal)
  deviate specify post          ├─ build slim specify prompt
                                ├─ invoke agent → spec.md
                                ├─ _specify_post() (internal)
                                ├─ _tasks_pre() (internal)
                                ├─ build slim tasks prompt
                                ├─ invoke agent → tasks.md
                                └─ _tasks_post() (internal)
```

### `deviate meso` Pipeline

```
deviate meso [--issue ISS-NNN] [--dry-run]
  │
  ├─ Discover next unblocked BACKLOG issue (or use --issue)
  │
  ├─ SPECIFY ─────────────────────────────────────────
  │  _specify_pre()        → contract + worktree + claim
  │  build slim prompt     → issue body + PRD reqs + constitution
  │  invoke agent          → write spec.md to worktree
  │  validate              → Gherkin syntax, FR traceability
  │  _specify_post()       → commit spec.md, advance session to TASKS
  │
  └─ TASKS ──────────────────────────────────────────
     _tasks_pre()           → contract + worktree detection + spec discovery
     build slim prompt      → spec.md content + design/data-model refs
     invoke agent           → write tasks.md with task checklist
     validate               → task ID format, execution modes, unchecked tasks
     _tasks_post()          → commit tasks.md, advance session to IDLE
```

### `deviate macro` Pipeline

```
deviate macro [--target <slug>] [--from <phase>] [--dry-run]
  │
  ├─ EXPLORE ────────────────────────────────────────
  │  _explore_pre()        → allocate feature bucket, emit contract
  │  build slim prompt     → problem description + repo structure context
  │  invoke agent          → write explore.md
  │  _explore_post()       → validate explore.md, commit
  │
  ├─ RESEARCH ───────────────────────────────────────
  │  _research_pre()       → gate on explore.md, emit contract
  │  build slim prompt     → explore.md content + constitution
  │  invoke agent          → write design.md + data-model.md
  │  _research_post()      → validate both artifacts, constitutional scan, commit
  │
  ├─ PRD ────────────────────────────────────────────
  │  _prd_pre()            → discover epic, resolve upstream, emit contract
  │  build slim prompt     → design.md + data-model.md content
  │  invoke agent          → write prd.md
  │  _prd_post()           → validate PRD against manifest, commit
  │
  └─ SHARD ──────────────────────────────────────────
     _shard_pre()          → discover epic, resolve PRD, compute next issue ID
     build slim prompt     → prd.md content + issue template
     invoke agent          → write shard issue files + register in ledger
     _shard_post()         → register issues in issues.jsonl, commit
```

### Constitution & Governance Injection

Same as ISS-004: `specs/constitution.md` and `CLAUDE.md` are read once at pipeline start and injected into every slim prompt's static KV-cacheable prefix.

## [SCOPE_BOUNDARIES]

### Hard Inclusions

- **`deviate meso`** — Automated specify→tasks pipeline.
  - `--issue ISS-NNN` — Target a specific issue (default: next unblocked BACKLOG).
  - `--dry-run` — Emit prompts and contracts without invoking agent or committing.
  - Discovers next unblocked issue from ledger if no `--issue` given.
  - Aborts if issue is already COMPLETED or has unresolved blocking dependencies.
  - Respects `--force` semantics from underlying pre/post commands.
- **`deviate macro`** — Automated explore→research→prd→shard pipeline.
  - `--target <slug>` — Target a specific feature bucket slug.
  - `--from <phase>` — Resume from a specific phase (explore | research | prd | shard).
  - `--dry-run` — Emit prompts and contracts without invoking agent or committing.
  - Validates upstream artifact existence at each phase boundary.
- **Slim prompt templates** (`src/deviate/prompts/auto/`):
  - `explore.md` — Problem → codebase scan report
  - `research.md` — Explore output → design + data-model
  - `prd.md` — Design + data-model → product requirements document
  - `shard.md` — PRD → shard issue files
  - `specify.md` — Issue body + PRD reqs → spec.md with Gherkin
  - `tasks.md` — Spec.md → tasks.md with TDD task decomposition
  - Each follows the same static-prefix + dynamic-suffix pattern as ISS-004 slim prompts.
- **Agent backend reuse**: Uses `src/deviate/core/agent.py` from ISS-004 — same heredoc pipe invocation, same YAML handover manifest parsing, same timeout handling.
- **Session state**: Phase transitions tracked in `.deviate/session.json`. Pipeline resumes correctly if interrupted (e.g., detect existing spec.md → skip SPECIFY, proceed to TASKS).
- **Error recovery**: If a phase fails (agent non-zero exit, validation failure, commit failure), abort pipeline, surface error with phase context, leave state at last successful phase.

### Defensive Exclusions

- Individual pre/post command implementation (already covered by ISS-005).
- Micro-layer TDD execution (covered by ISS-004).
- Aider integration (covered by ISS-009).
- Core module implementations (covered by ISS-005).
- State persistence and concurrency (covered by ISS-006).

## [UPSTREAM_REQUIREMENT_TRACING]

- **FR-008-MESO**: `deviate meso` automates the specify→tasks pipeline — discovers issue, runs pre→agent→post for both phases, handles all state and commit operations internally.
- **FR-008-MACRO**: `deviate macro` automates the explore→research→prd→shard pipeline — runs pre→agent→post for all four phases, handles bucket allocation, ledger registration, and state transitions.
- **FR-008-SLIM-PROMPTS**: Slim prompt templates for all six meso/macro phases following the same static-prefix + dynamic-suffix KV-cacheable pattern established in ISS-004.
- **FR-008-CONSTITUTION**: Constitution and CLAUDE.md injected into every automated meso/macro prompt.
- **FR-008-RECOVERY**: Pipeline resumes at correct phase on interruption; completed phases are skipped idempotently.

## [MULTI_TIERED_VERIFICATION_TARGETS]

- **Unit Tests**: `tests/test_meso/test_meso_orchestration.py`, `tests/test_macro/test_macro_orchestration.py`
- **Integration Tests**: `tests/test_integration/test_meso_orchestration.py`, `tests/test_integration/test_macro_orchestration.py`, `tests/test_integration/test_full_meso_pipeline.py`, `tests/test_integration/test_full_macro_pipeline.py`

## [DEMONSTRATION_PATH]

```bash
# Verify meso orchestration
pytest tests/test_integration/test_meso_orchestration.py -v

# Verify macro orchestration
pytest tests/test_integration/test_macro_orchestration.py -v

# Run full meso pipeline (dry-run)
deviate meso --dry-run

# Run full macro pipeline (dry-run)
deviate macro --dry-run

mise run check
```
