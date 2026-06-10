# FEATURE_SPECIFICATION: specs/001-deviate-cli-python/004-micro-layer-tdd-sandbox-execution/spec.md

## SYSTEM_TOPOLOGY_MAPPING

- **Epic Domain**: `001-deviate-cli-python`
- **Layer**: Micro (TDD Sandbox)
- **Issue**: `ISS-004` — Micro-Layer TDD Sandbox Execution — Manual & Automated Orchestration
- **Execution Mode**: TDD (Red-Green-Refactor via deviate cycle)
- **Blocked By**: `ISS-005` (Core Module Implementations), `ISS-006` (Ledger & State Config)

### Component Map

| Component | Path | Role |
|-----------|------|------|
| Automated orchestration | `src/deviate/cli/micro.py` | `deviate micro` pipeline — state transitions, git commits, validation, agent invocation |
| Agent backend | `src/deviate/core/agent.py` | Subprocess abstraction (heredoc pipe), YAML handover manifest parsing, timeout handling |
| Tamper Guard | `src/deviate/core/tamper.py` | `git diff` evaluation, `git restore` rollback on unauthorized test/spec/config mutations |
| Slim prompt templates | `src/deviate/prompts/auto/` | `red.md`, `green.md`, `refactor.md`, `judge.md`, `yellow.md` — KV-cacheable static prefixes + dynamic task suffixes |
| Manual pre/post commands | `src/deviate/cli/micro.py` | `deviate red/green/refactor/judge/yellow/execute/e2e/hotfix pre/post` |
| Config model | `src/deviate/state/config.py` | `AgentConfig` (backend, timeout) within `DeviateConfig` |
| Ledger | `src/deviate/state/ledger.py` | `TaskRecord` status transitions — PENDING, RED, GREEN, REFACTOR, COMPLETED |
| Constitution governance | `specs/constitution.md` | Injected as static prefix in every automated prompt |
| Agent governance | `CLAUDE.md` | Injected alongside constitution as static governance context |
| Test suite | `tests/test_micro/` | Unit tests per micro phase |
| Integration tests | `tests/test_integration/` | Full-cycle, Tamper Guard, Mise Check Gate, agent backend |

### Execution Topology (Automated Path)

```
deviate micro <TASK_ID> / --all
  │
  ├── 1. RED:   build slim prompt → invoke agent → verify test FAILS → commit test
  ├── 2. GREEN: build slim prompt → invoke agent → verify tests PASS
  │              ├── Tamper Guard check
  │              ├── If agent emitted structured JSON requesting test mods →
  │              │   YELLOW phase (amend tests) → back to GREEN
  │              └── Else → commit implementation
  ├── 3. YELLOW: (conditional) evaluate test amendments, approve/reject → return to GREEN
  ├── 4. JUDGE:  evaluate git diff against spec.md → compliance verdict
  ├── 5. REFACTOR: (optional) polish → verify tests still PASS → commit
  └── 6. Mark COMPLETED in ledger
```

### Execution Topology (Manual Path)

```
deviate <phase> pre → agent receives verbose SKILL.md prompt →
  agent does creative work → deviate <phase> post → validate → commit
  Supported phases: red, green, refactor, judge, yellow, execute, e2e, hotfix
```

## THE_PROBLEM_CONTRACT

As a developer writing code, I need the deviate CLI to execute the full micro-layer TDD cycle (RED, GREEN, YELLOW conditional, JUDGE, REFACTOR optional, E2E, EXECUTE, HOTFIX) either step-by-step via manual pre/post commands or fully automated via a single `deviate micro` command. The automated path must:

1. Handle all ledger state transitions and git commits internally (agent only writes code).
2. Feed the agent slim, functionally-targeted prompts with constitution/`CLAUDE.md` context injected as static KV-cacheable prefixes.
3. Include a Tamper Guard that prevents unauthorized modifications to `tests/`, `specs/`, or configuration files.
4. Provide a structured YELLOW handover protocol: when GREEN detects it needs to modify test files, it emits structured JSON describing the changes, deviate parses this, executes YELLOW to amend tests, then returns to GREEN.
5. Handle agent timeouts with a single retry-and-30s-backoff strategy, failing hard on second timeout.
6. Handle `--all` pipeline failures with retry-once-then-abort semantics.
7. Abstract three agent backends (opencode, claude, droid) via heredoc-pipe subprocess invocation.

## SCOPE_BOUNDARIES

### Hard Inclusions

1. **`deviate micro <TASK_ID>`** — Run a single task through full RED→GREEN→JUDGE→REFACTOR cycle. CLI handles all admin; agent only writes code.
2. **`deviate micro --all`** — Run ALL PENDING tasks sequentially. If a task fails, retry once (entire task from RED). If second attempt also fails, abort pipeline. No subsequent tasks execute.
3. **`deviate micro --no-judge`** — Skip the JUDGE compliance gate.
4. **`deviate micro --no-refactor`** — Skip the REFACTOR phase.
5. **`deviate micro --agent <backend>`** — Override agent backend for this invocation (opencode | claude | droid).
6. **Agent backend abstraction** (`src/deviate/core/agent.py`):
   - Subprocess via heredoc pipe: `echo "$PROMPT" | <agent_cmd>`
   - Supported backends: `opencode run`, `claude -p`, `droid exec`
   - Configurable via `.deviate/config.toml` `[agent]` section
   - Timeout per phase in seconds (default 600s)
   - Capture stdout, parse YAML handover manifest from agent output
   - **Timeout recovery**: Retry once after 30s backoff. Second timeout → abort phase, mark task FAILED in ledger.
   - Structured YELLOW handover: GREEN agent may emit `{"yellow_trigger": true, "test_changes": {...}, "rationale": "..."}` in its YAML manifest. Deviate detects this → invokes YELLOW pre → agent amends tests → YELLOW post → re-enters GREEN phase.
7. **Slimmed prompt templates** (`src/deviate/prompts/auto/`):
   - Each template has a static KV-cacheable prefix (role, constraints, constitution excerpt, CLAUDE.md governance) and a dynamic task-specific suffix.
   - `red.md` (~200 words): "write a failing test"
   - `green.md` (~200 words): "write code to pass the test"
   - `refactor.md` (~150 words): "refactor, keep tests green"
   - `judge.md` (~100 words): "compliance verdict on diff"
   - `yellow.md` (~150 words): "justify or revert test amendments"
8. **Constitution & governance injection**: `specs/constitution.md` and `CLAUDE.md` read once per `deviate micro` invocation, injected as static prefix content in every slim prompt.
9. **Automated phase sequencing**:
   - RED: build slim prompt → invoke agent → verify test file exists + test FAILS → commit test
   - GREEN: build slim prompt → invoke agent → verify tests PASS → Tamper Guard → YELLOW check → commit
   - YELLOW (conditional): if GREEN agent requested test modifications via structured manifest → invoke YELLOW agent to justify → approve or `git restore` → return to GREEN
   - JUDGE: evaluate `git diff` against `spec.md` for compliance violations → pass or abort
   - REFACTOR (optional): build slim prompt → invoke agent → verify tests still PASS → commit
   - Mark task COMPLETED in ledger
10. **Tamper Guard**: After each agent invocation, check `git diff --name-only`. If `tests/`, `specs/`, or config files appear in diff outside expected RED-phase test creation or GREEN YELLOW-approved amendments → `git restore` rollback + `TAMPER_DETECTED` surface.
11. **Manual stepping commands**: `deviate red/green/refactor/judge/yellow/execute/e2e/hotfix pre/post`.
12. **Session state**: Track active `TaskRecord`, current micro phase, update after each phase commit.
13. **Ledger updates**: Atomic `TaskRecord` status transitions appended to `specs/**/tasks.jsonl` after each phase commit.

### Defensive Exclusions

- Macro-layer orchestration (feature scoping, `/explore`, `/research`, `/prd`, `/shard`) — covered by `ISS-005`, `ISS-008`.
- Meso-layer orchestration (issue engineering, `/specify`, `/tasks`) — covered by `ISS-005`, `ISS-008`.
- Core module implementations (repo, ledger, contract, commit, constitution, epic, validation, worktree, issues, prd, skills) — covered by `ISS-005`.
- Aider integration — covered by `ISS-010`.
- Direct modification of `tests/`, `specs/`, or configuration files by agent sandbox (strictly read-only outside of RED test creation and GREEN+ YELLOW-approved amendments, enforced by Tamper Guard).
- Web or GUI frontend — CLI-only application.

## PERFORMANCE_CONSTRAINTS

| Constraint | Target | Measurement |
|-----------|--------|-------------|
| `deviate micro` pre-phase overhead | L_max <= 200ms | Time from command invocation to agent prompt delivery (excluding agent runtime) |
| Tamper Guard evaluation | L_max <= 100ms | Time from `git diff --name-only` to verdict (pass/tamper) |
| Slim prompt assembly | L_max <= 50ms | Template loading + variable interpolation + constitution/CLAUDE.md injection |
| Agent timeout default | 600s | Configurable via `.deviate/config.toml` `[agent].timeout` |
| Retry backoff delay | 30s | Between first agent timeout and retry attempt |
| YAML manifest parsing | L_max <= 50ms | From captured stdout to structured `HandoverManifest` model |
| Session state write | L_max <= 20ms | Serialization + write to `.deviate/session.json` |
| Ledger append | L_max <= 20ms | Append one line to `tasks.jsonl` |

## MULTI_TIERED_VERIFICATION_TARGETS

### Unit Tests

| Test Module | Target | Verification |
|------------|--------|--------------|
| `tests/test_micro/test_red.py` | RED pre/post commands | Contract emission, test failure validation, commit |
| `tests/test_micro/test_green.py` | GREEN pre/post commands | Test pass validation, Tamper Guard integration, YELLOW handover detection |
| `tests/test_micro/test_refactor.py` | REFACTOR pre/post commands | Test invariance, commit |
| `tests/test_micro/test_judge.py` | JUDGE pre/post commands | Compliance report, violation detection |
| `tests/test_micro/test_yellow.py` | YELLOW pre/post commands | Amendment proposal, approval/rejection |
| `tests/test_micro/test_execute.py` | EXECUTE pre/post | Direct execution workflow, manifest handling |
| `tests/test_micro/test_e2e.py` | E2E pre/post | Completion verification, test execution |
| `tests/test_micro/test_hotfix.py` | HOTFIX pre/post | Bug context discovery, bypass RED |
| `tests/test_micro/test_orchestration.py` | Full micro cycle orchestration | Phase sequencing, state transitions |
| `tests/test_core/test_agent.py` | Agent backend abstraction | Heredoc subprocess, YAML parsing, timeout, retry |
| `tests/test_core/test_tamper.py` | Tamper Guard | `git diff` evaluation, `git restore` rollback |

### Integration Tests

| Test Module | Target | Verification |
|------------|--------|--------------|
| `tests/test_integration/test_micro_orchestration.py` | Automated `deviate micro` full pipeline | End-to-end RED→GREEN→JUDGE→REFACTOR |
| `tests/test_integration/test_tamper_guard.py` | Tamper Guard in real git context | Unauthorized mod → restore; authorized mod → pass |
| `tests/test_integration/test_mise_check_gate.py` | Post-commit mise check | `mise run check` passes after each commit |
| `tests/test_integration/test_full_cycle.py` | Complete issue lifecycle | From RED through COMPLETED |
| `tests/test_integration/test_agent_backend.py` | All three backends | opencode, claude, droid invocation |

### Verification Commands

```bash
# Unit tests
pytest tests/test_micro/ -v
pytest tests/test_core/test_agent.py -v
pytest tests/test_core/test_tamper.py -v

# Integration tests
pytest tests/test_integration/test_micro_orchestration.py -v
pytest tests/test_integration/test_tamper_guard.py -v
pytest tests/test_integration/test_full_cycle.py -v

# Full gate
mise run check
```

### TEST_ISOLATION_CONSTRAINTS

**Git Isolation Mandatory**: Any test that invokes git operations (init, add, commit, branch, worktree, checkout, log, status, diff, restore, push) MUST operate on a temporary directory initialized as a fresh git repo. Use the `tmp_git_repo` fixture from `tests/conftest.py` which creates a clean repo in `tmp_path` with a test user (`Test Runner <runner@test.local>`) and an initial commit. All git-subprocess calls MUST pass `cwd=<tmp_git_repo>` and strip `GIT_*` env vars via `_git_env()` to prevent ambient leakage from the real repo.

**Fixture pattern**:
```python
def test_something(self, tmp_git_repo: Path):
    with chdir(tmp_git_repo):
        # All git ops scoped to tmp_git_repo
        result = runner.invoke(cli, [...])
        assert result.exit_code == 0
```

**`repo_path` parameter mandate**: Every git-interacting function in core/module code MUST accept `repo_path: Path | None = None` defaulting to `Path.cwd()`. Tests MUST pass `repo_path=tmp_git_repo` explicitly. Never reference `Path.cwd()` or the real repo root from test code.

**Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution. All tests are TDD and run repeatedly; accidental mutations corrupt the development workflow.

## ATDD_ACCEPTANCE_CRITERIA_LEDGER

### US-004-1: Agent backend abstraction with heredoc-pipe invocation
* **Upstream Requirement Traceability**: FR-004-AGENT
* **Scenario 1.1: Successful agent invocation**
  `**Given**` the `AgentConfig` specifies `backend = "opencode"` and `timeout = 600`
  `**When**` the `AgentBackend` invokes `echo "$PROMPT" | opencode run`
  `**Then**` the subprocess stdout is captured, exit code is 0, and a `HandoverManifest` is parsed from the output

* **Scenario 1.2: Agent timeout triggers retry with backoff**
  `**Given**` the agent subprocess has not returned output within the configured timeout
  `**When**` `AgentBackend` executes
  `**Then**` it waits 30s and retries once; if the second attempt also times out, it raises `AgentTimeoutError` and marks the task FAILED

* **Scenario 1.3: YAML manifest parsing failure**
  `**Given**` the agent outputs malformed or missing YAML
  `**When**` `AgentBackend.parse_output()` runs
  `**Then**` it raises `MalformedHandoverManifestError` with a diagnostic message

* **Scenario 1.4: Non-zero exit code propagation**
  `**Given**` the agent subprocess exits with code 1 and an error message on stderr
  `**When**` `AgentBackend` executes
  `**Then**` it captures the error message and surfaces it as `AgentSubprocessError` with the exit code

### US-004-2: Slim prompt templates with constitution injection
* **Upstream Requirement Traceability**: FR-004-SLIM-PROMPTS, FR-004-CONSTITUTION-INJECTION
* **Scenario 2.1: Static prefix contains constitution and CLAUDE.md**
  `**Given**` a slim prompt template for RED phase
  `**When**` the prompt is assembled
  `**Then**` the content begins with the `specs/constitution.md` excerpt followed by the `CLAUDE.md` governance rules, before any task-specific dynamic suffix

* **Scenario 2.2: KV-cacheable region isolation**
  `**Given**` the static prefix is defined as the first N tokens of the prompt
  `**When**` the dynamic suffix varies across different task IDs
  `**Then**` the static prefix tokens are identical regardless of task context

* **Scenario 2.3: Each template is under ~200 words**
  `**Given**` each template in `src/deviate/prompts/auto/`
  `**When**` word-count is measured (excluding constitution and CLAUDE.md injected content)
  `**Then**` `red.md`, `green.md` are <= 200 words, `refactor.md` <= 150 words, `judge.md` <= 100 words, `yellow.md` <= 150 words

### US-004-3: Automated RED phase — failing test generation
* **Upstream Requirement Traceability**: FR-004-RED
* **Scenario 3.1: RED phase writes a failing test**
  `**Given**` a task in PENDING state with a known test command
  `**When**` the RED phase runs (via `deviate micro` automated or `deviate red pre/post` manual)
  `**Then**` a test file is created in `tests/` and `pytest <test_file> -v` fails with `AssertionError` or `NotImplementedError` (not a syntax error)

* **Scenario 3.2: RED validation rejects passing tests**
  `**Given**` an agent produces a test that passes (exit code 0)
  `**When**` RED post-validation runs
  `**Then**` validation fails with `RedMustFailError` and the phase is aborted

* **Scenario 3.3: RED validation rejects syntax errors**
  `**Given**` an agent produces a test with a syntax error (import error, indentation error, etc.)
  `**When**` RED post-validation runs
  `**Then**` validation fails with `SyntaxCrashRejected` and the phase is aborted

### US-004-4: Automated GREEN phase — implementation and Tamper Guard
* **Upstream Requirement Traceability**: FR-004-GREEN, FR-004-TAMPER
* **Scenario 4.1: GREEN writes passing implementation**
  `**Given**` a failing test exists from the RED phase
  `**When**` the GREEN phase runs
  `**Then**` `pytest <test_file> -v` exits with code 0 and all tests pass

* **Scenario 4.2: Tamper Guard detects unauthorized test modification**
  `**Given**` the GREEN agent modifies a test file outside the YELLOW handover protocol
  `**When**` Tamper Guard evaluates `git diff --name-only`
  `**Then**` the modification is detected, `git restore` is triggered on the modified file, and `TAMPER_DETECTED` is surfaced

* **Scenario 4.3: GREEN agent may emit structured YELLOW handover**
  `**Given**` the GREEN agent determines it needs to modify test files to pass the implementation
  `**When**` the agent includes `{"yellow_trigger": true, "test_changes": {...}}` in its YAML handover manifest
  `**Then**` deviate detects the trigger, invokes the YELLOW phase to amend tests, then re-enters GREEN

* **Scenario 4.4: Tamper Guard passes for authorized modifications**
  `**Given**` the GREEN agent creates a new implementation file under `src/` that does not touch `tests/`, `specs/`, or config
  `**When**` Tamper Guard evaluates `git diff --name-only`
  `**Then**` no rollback is triggered and the phase proceeds

### US-004-5: YELLOW conditional phase — test amendment protocol
* **Upstream Requirement Traceability**: FR-004-YELLOW
* **Scenario 5.1: YELLOW triggered by GREEN handover manifest**
  `**Given**` the GREEN phase detected a YELLOW trigger in the agent's output manifest
  `**When**` the YELLOW pre command runs
  `**Then**` a YELLOW contract is emitted describing the proposed test changes and rationale

* **Scenario 5.2: YELLOW amendment accepted**
  `**Given**` the YELLOW agent proposes test amendments with sufficient rationale
  `**When**` the YELLOW post command validates and commits the amendments
  `**Then**` the test changes are committed and control returns to the GREEN phase

* **Scenario 5.3: YELLOW amendment rejected**
  `**Given**` the YELLOW agent's justification is insufficient or the changes violate spec.md invariants
  `**When**` JUDGE evaluates the YELLOW proposal
  `**Then**` the test changes are reverted via `git restore` and the GREEN phase is re-run without test modifications

### US-004-6: JUDGE compliance gate
* **Upstream Requirement Traceability**: FR-004-JUDGE
* **Scenario 6.1: Clean diff passes JUDGE**
  `**Given**` the GREEN or REFACTOR phase completed with only expected changes
  `**When**` JUDGE evaluates `git diff` against `spec.md` invariants
  `**Then**` a `COMPLIANCE_PASS` verdict is returned and the pipeline proceeds

* **Scenario 6.2: Structural drift detected by JUDGE**
  `**Given**` the diff introduces changes that violate `spec.md` structural constraints (e.g., modifying a protected module interface, bypassing a mandatory gate)
  `**When**` JUDGE evaluates
  `**Then**` a `COMPLIANCE_VIOLATION` verdict is returned with specific violation details, and the pipeline aborts

* **Scenario 6.3: `--no-judge` skips the gate**
  `**Given**` `deviate micro --no-judge` is invoked
  `**When**` the pipeline reaches the JUDGE phase
  `**Then**` the gate is skipped and the pipeline proceeds directly to REFACTOR (or COMPLETED)

### US-004-7: REFACTOR phase — test-invariant polish
* **Upstream Requirement Traceability**: FR-004-REFACTOR
* **Scenario 7.1: REFACTOR polishes without breaking tests**
  `**Given**` the implementation is passing all tests after GREEN
  `**When**` the REFACTOR phase runs
  `**Then**` the implementation files are improved structurally, and `pytest tests/ -v` still exits with code 0

* **Scenario 7.2: Regression gate rolls back on test failure**
  `**Given**` the REFACTOR agent's changes cause a test to fail
  `**When**` the regression gate runs `pytest tests/ -v`
  `**Then**` the changes are rolled back and `RefactorRegressionError` is surfaced

* **Scenario 7.3: `--no-refactor` skips the phase**
  `**Given**` `deviate micro --no-refactor` is invoked
  `**When**` the pipeline reaches the REFACTOR phase
  `**Then**` the phase is skipped and the task transitions directly to COMPLETED

### US-004-8: Automated orchestration (`deviate micro`)
* **Upstream Requirement Traceability**: FR-004-MICRO-ORCHESTRATION
* **Scenario 8.1: Single task full cycle**
  `**Given**` a task with status PENDING exists in the ledger
  `**When**` `deviate micro ISS-004-1` runs
  `**Then**` RED → GREEN → JUDGE → REFACTOR execute sequentially, and the task transitions to COMPLETED

* **Scenario 8.2: `deviate micro --all` processes all PENDING tasks**
  `**Given**` multiple PENDING tasks exist in the ledger
  `**When**` `deviate micro --all` runs
  `**Then**` each task is processed sequentially through the full cycle; if a task fails, it is retried once and on second failure the pipeline aborts

* **Scenario 8.3: `--all` retry-once then abort**
  `**Given**` a task fails during its first RED phase (or any phase)
  `**When**` `--all` is running
  `**Then**` the CLI retries the entire task from RED once; if the retry also fails, the pipeline aborts with a diagnostic error, and no further tasks execute

* **Scenario 8.4: Session state tracks active phase**
  `**Given**` a `deviate micro` invocation is in progress
  `**When**` the session file is read
  `**Then**` it contains the active `TaskRecord`, current micro phase, and last commit hash

* **Scenario 8.5: Ledger updated after each phase commit**
  `**Given**` a phase completes successfully
  `**When**` the phase post-command runs
  `**Then**` a `TaskRecord` status transition is appended to `specs/**/tasks.jsonl`

### US-004-9: Manual phase stepping commands
* **Upstream Requirement Traceability**: FR-004-RED, FR-004-GREEN, FR-004-REFACTOR, FR-004-EXECUTE, FR-004-E2E, FR-004-HOTFIX
* **Scenario 9.1: Manual RED pre/post cycle**
  `**Given**` a PENDING task
  `**When**` `deviate red pre` runs, then after agent work `deviate red post` runs
  `**Then**` a failing test is committed and the ledger marks the task as RED

* **Scenario 9.2: Manual GREEN pre/post cycle**
  `**Given**` a task in RED state with a failing test
  `**When**` `deviate green pre` runs, then after agent work `deviate green post` runs
  `**Then**` passing implementation code is committed and the ledger marks the task as GREEN

* **Scenario 9.3: Manual EXECUTE pre/post for DIRECT tasks**
  `**Given**` a task with `execution_mode=DIRECT`
  `**When**` `deviate execute pre` runs, then after agent work `deviate execute post <manifest>` runs
  `**Then**` the work is committed and the task is marked COMPLETED (bypassing RED/GREEN/REFACTOR)

* **Scenario 9.4: Manual E2E pre/post**
  `**Given**` all tasks in the issue are COMPLETED
  `**When**` `deviate e2e pre` runs, then E2E tests execute, then `deviate e2e post` runs
  `**Then**` E2E test results are committed

* **Scenario 9.5: Manual HOTFIX pre/post**
  `**Given**` a bug report with no existing test
  `**When**` `deviate hotfix pre` runs, then after agent work `deviate hotfix post <manifest>` runs
  `**Then**` the hotfix is committed (bypassing RED phase)

### US-004-10: Agent backend configuration and override
* **Upstream Requirement Traceability**: FR-004-AGENT
* **Scenario 10.1: Backend configured via config.toml**
  `**Given**` `.deviate/config.toml` contains `[agent]\nbackend = "claude"\ntimeout = 300`
  `**When**` `AgentBackend` is initialized
  `**Then**` it uses `claude -p` as the subprocess command with a 300s timeout

* **Scenario 10.2: `--agent` flag overrides config**
  `**Given**` `.deviate/config.toml` specifies `backend = "claude"`
  `**When**` `deviate micro --agent droid` runs
  `**Then**` the backend uses `droid exec` for this invocation only, without modifying config.toml

## SYSTEM_STATUS_SUMMARY

| Parameter | Value |
|-----------|-------|
| STATUS | SPECIFY |
| EPIC_SLUG | 001-deviate-cli-python |
| BRANCH_NAME | feat/001-deviate-cli-python/004-micro-layer-tdd-sandbox-execution |
| SPEC_PATH | specs/001-deviate-cli-python/004-micro-layer-tdd-sandbox-execution/spec.md |
| ISSUE_ID | ISS-004 |
| NEXT_ACTION | decompose into TDD tasks via `/deviate-tasks` |
