---
title: "[FR-004] Micro-Layer TDD Sandbox Execution — Manual & Automated Orchestration"
labels: ["epic:001-deviate-cli-python", "layer:micro"]
source_file: "specs/001-deviate-cli-python/prd.md"
blocked_by: ["ISS-005", "ISS-006"]
coordinates_with: []
issue_id: "ISS-004"
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Domain**: `001-deviate-cli-python`
- **Local File Path**: `specs/001-deviate-cli-python/issues/004-micro-layer-tdd-sandbox-execution.md`
- **Workstation Paths**:
  - `src/deviate/cli/micro.py` — Manual pre/post commands + `deviate micro` orchestration
  - `src/deviate/core/agent.py` — Agent backend abstraction (subprocess invocation via heredoc pipe)
  - `src/deviate/core/tamper.py` — Tamper Guard (git diff evaluation, git restore rollback)
  - `src/deviate/prompts/auto/` — Slimmed automated prompt templates
  - `src/deviate/prompts/skills/` — Existing manual verbose SKILL.md files (read-only reference)
  - `src/deviate/state/config.py` — DeviateConfig.agent_backend, micro phase transitions
  - `src/deviate/state/ledger.py` — TaskRecord status transitions (RED, GREEN, REFACTOR, COMPLETED)
  - `specs/constitution.md` — Injected as static prefix content in every automated prompt
  - `CLAUDE.md` — Injected alongside constitution as static governance context
  - `tests/test_micro/`
  - `tests/test_integration/test_micro_orchestration.py`

## [THE_PROBLEM_CONTRACT]
As a developer writing code, I need the CLI to execute the full micro-layer TDD cycle — RED, GREEN, YELLOW (conditional), JUDGE, REFACTOR (optional), E2E, EXECUTE, and HOTFIX — either step-by-step via manual pre/post commands or fully automated via a single `deviate micro` command that orchestrates agent subprocess calls, handles all ledger state transitions and git commits internally, and feeds the agent slim, functionally-targeted prompts with constitution/CLAUDE.md context injected as static prefix content.

## [ARCHITECTURAL_OVERVIEW]

### Dual-Path Design

```
                        ┌──────────────────────────┐
                        │     deviate micro         │
                        │   (automated pipeline)    │
                        │                           │
                        │  pre → slim prompt →      │
                        │  agent → verify → post    │
                        │  (repeats per phase)      │
                        └──────────────────────────┘
                                   │
                                   │ shares pre/post internals
                                   ▼
                        ┌──────────────────────────┐
                        │    deviate red/green/     │
                        │    refactor/e2e pre/post  │
                        │    (manual stepping)      │
                        │                           │
                        │  verbose SKILL.md prompts │
                        │  agent runs pre/post      │
                        └──────────────────────────┘
```

**Automated path**: CLI owns all orchestration — state transitions, git commits, validation gates, agent invocation. The agent receives slim prompts and only writes code.

**Manual path**: Agent runs individual `deviate <phase> pre` to get contract context, does creative work, then runs `deviate <phase> post` to commit. Uses existing verbose SKILL.md files for prompt context.

### Per-Task Micro Cycle

```
PENDING ──► RED ──► GREEN ──► YELLOW? ──► JUDGE ──► REFACTOR? ──► COMPLETED
               │        │          │           │           │
               │   agent writes  │      agent may      agent
               │   failing test  │    propose test    polishes
               │                 │    amendment        code
               │                 │
               ▼                 ▼
          CLI: pre           CLI: pre
          → slim prompt      → slim prompt
          → agent            → agent
          → verify FAIL      → verify PASS
          → post → commit    → Tamper Guard
                             → YELLOW check
                             → post → commit
```

### Constitution & Governance Context Injection

Every automated slim prompt MUST include at the head of the context block:
1. **`specs/constitution.md`** content — project-level architectural rules, testing mandates, tech stack constraints
2. **`CLAUDE.md`** content — agent governance rules, execution contracts, code style

These are read once per `deviate micro` invocation (not per phase — they are static for the project lifetime). They sit in the prompt's KV-cacheable prefix region.

## [SCOPE_BOUNDARIES]

### Hard Inclusions — Automated Orchestration

- **`deviate micro <TASK_ID>`** — Run a single task through the full RED→GREEN→JUDGE→REFACTOR cycle. CLI handles all admin; agent only writes code.
- **`deviate micro --all`** — Run ALL PENDING tasks sequentially through the full cycle.
- **`deviate micro --no-judge`** — Skip the JUDGE compliance gate.
- **`deviate micro --no-refactor`** — Skip the REFACTOR phase.
- **`deviate micro --agent <backend>`** — Override agent backend for this invocation (opencode | claude | droid).
- **Agent backend abstraction** (`src/deviate/core/agent.py`):
  - Subprocess invocation via heredoc pipe: `echo "$PROMPT" | <agent_cmd>`
  - Supported backends: `opencode run`, `claude -p`, `droid exec`
  - Aider is NOT included (covered by ISS-009)
  - Configurable via `.deviate/config.toml` `[agent]` section
  - Timeout per phase in seconds
  - Capture stdout, parse YAML handover manifest from agent output
  - Exit code handling: non-zero → abort phase, surface error
- **Slimmed prompt templates** (`src/deviate/prompts/auto/`):
  - `red.md` — ~200 words: role, constraints, task context, test framework → "write a failing test"
  - `green.md` — ~200 words: role, constraints, test file, task context, lint command → "write code to pass the test"
  - `refactor.md` — ~150 words: role, constraints, files to refactor, test command → "refactor, keep tests green"
  - `judge.md` — ~100 words: role, diff, spec.md → "compliance verdict"
  - `yellow.md` — ~150 words: role, test changes, justification needed → "accept or revert"
  - Each template has:
    - **Static prefix** (KV-cacheable): role definition, systemic constraints, output format schema, constitution excerpt, CLAUDE.md governance rules
    - **Dynamic suffix** (not cached): task-specific context (task description, spec.md excerpt, file paths, test command)
- **Constitution & governance injection**:
  - `specs/constitution.md` read once at start of `deviate micro`, injected into every slim prompt's static prefix
  - `CLAUDE.md` read once at start, injected alongside constitution
  - Both files live in the KV-cacheable region of each prompt
- **Automated phase sequencing per task**:
  1. RED: run `_red_pre` internally → build slim prompt → invoke agent → verify test file exists + test FAILS → run `_red_post` → commit test
  2. GREEN: run `_green_pre` internally → build slim prompt → invoke agent → verify tests PASS → run Tamper Guard → YELLOW check (did agent modify tests?) → run `_green_post` → commit implementation
  3. YELLOW (conditional): If GREEN agent modified test files, invoke YELLOW agent to justify. If approved, keep changes. If rejected, `git restore` tests and re-run GREEN.
  4. JUDGE: Evaluate `git diff` against `spec.md` for compliance violations, security issues, structural drift. If violations: abort or surface. If clean: proceed.
  5. REFACTOR (optional): run `_refactor_pre` → build slim prompt → invoke agent → verify tests still PASS → run `_refactor_post` → commit
  6. Mark task COMPLETED in ledger
- **Tamper Guard**: After each agent invocation, evaluate `git diff --name-only`. If `tests/`, `specs/`, or config files appear in diff (outside of expected RED-phase test creation and GREEN-phase minor test adjustments approved by YELLOW), trigger `git restore` rollback and surface `TAMPER_DETECTED`.
- **Session state**: Track active `TaskRecord`, current micro phase (RED/GREEN/REFACTOR), update after each phase commit.
- **Ledger updates**: Atomic `TaskRecord` status transitions appended to `specs/**/tasks.jsonl` after each phase commit.

### Hard Inclusions — Manual Stepping Commands

- **`deviate red pre [--task <id>]`** — Find next PENDING task (or use specified ID), emit JSON contract with task context, test command, lint command, spec_dir.
- **`deviate red post`** — Validate test file exists, validate test FAILS (must fail due to missing implementation), stage test file, commit with `--no-verify` (intentionally failing test).
- **`deviate green pre [--task <id>]`** — Load active RED task, emit JSON contract with task context, test file path, lint command.
- **`deviate green post`** — Validate tests PASS (exit code 0), run Tamper Guard, stage implementation files, precommit hooks, commit.
- **`deviate refactor pre [--task <id>]`** — Load active GREEN task, emit JSON contract.
- **`deviate refactor post`** — Validate tests still PASS (test invariance), stage refactored files, precommit hooks, commit.
- **`deviate judge pre`** — Evaluate `git diff` against `spec.md`, emit compliance report.
- **`deviate yellow pre`** — Emit YELLOW contract with test changes for amendment proposal.
- **`deviate execute pre [--task <id>]`** — For non-TDD tasks (execution_mode=DIRECT), discover workflow context, emit contract.
- **`deviate execute post <manifest>`** — Validate completion, precommit hooks, commit.
- **`deviate e2e pre`** — Verify all tasks in issue are completed, discover E2E tests, emit contract.
- **`deviate e2e post`** — Execute E2E tests, commit results.
- **`deviate hotfix pre`** — Discover bug context, emit contract (bypasses RED phase).
- **`deviate hotfix post <manifest>`** — Commit hotfix.
- **`deviate run <TASK_ID>`** — Existing stub: dispatch single task by execution_mode (kept for backward compat).
- **`deviate run --all`** — Existing stub: process all PENDING tasks (kept for backward compat).

### Defensive Exclusions

- Macro or Meso layer orchestration (covered by ISS-005, ISS-008).
- Core module implementations (repo, ledger, contract, commit, constitution, epic, validation, worktree, issues, prd, skills — covered by ISS-005).
- Aider integration (covered by ISS-009).
- Direct modification of `tests/`, `specs/`, or configuration files by the agent sandbox (strictly read-only outside of expected RED test creation and GREEN YELLOW-approved amendments, enforced by Tamper Guard).

## [AGENT_BACKEND_SPECIFICATION]

### Configuration

```toml
# .deviate/config.toml
[agent]
backend = "opencode"        # opencode | claude | droid
timeout = 600               # seconds per phase
```

Extend `DeviateConfig` with:

```python
class AgentConfig(BaseModel):
    backend: Literal["opencode", "claude", "droid"] = "opencode"
    timeout: int = Field(default=600, gt=0)

class DeviateConfig(BaseModel):
    # ... existing fields ...
    agent: AgentConfig = Field(default_factory=AgentConfig)
```

### Invocation Pattern

All backends use heredoc pipe — no temp files:

```
echo "$PROMPT" | opencode run
echo "$PROMPT" | claude -p
echo "$PROMPT" | droid exec
```

The `AgentBackend` class:
- Takes config, builds prompt, invokes subprocess
- Captures stdout, checks exit code
- Parses YAML handover manifest from output
- Returns structured result: `{status, files_touched, verification_result, manifest}`
- Raises `AgentTimeoutError` if subprocess exceeds timeout

### Output Parsing

Every slim prompt instructs the agent to emit a YAML handover manifest:

```yaml
phase: RED
status: TEST_WRITTEN_FAILING
test_file: tests/test_foo.py
verification_command: pytest tests/test_foo.py -v
expected_failure: NameError: name 'FooService' is not defined
assertions_established:
  - assert FooService().bar() == expected
```

The CLI parses this manifest to:
- Confirm the expected file was written
- Extract verification commands
- Determine next phase
- Detect YELLOW conditions (test modifications in GREEN phase)

## [UPSTREAM_REQUIREMENT_TRACING]

- **FR-004-AGENT**: Agent backend abstraction with heredoc-pipe subprocess invocation for opencode, claude, and droid; structured output parsing via YAML handover manifests.
- **FR-004-MICRO-ORCHESTRATION**: `deviate micro <TASK_ID>` and `deviate micro --all` fully automated pipeline handling all state transitions, git commits, validation gates, and agent invocation internally.
- **FR-004-SLIM-PROMPTS**: Slimmed, functionally-targeted prompt templates in `src/deviate/prompts/auto/` with KV-cacheable static prefixes (constitution, CLAUDE.md, constraints) and dynamic task-specific suffixes.
- **FR-004-CONSTITUTION-INJECTION**: `specs/constitution.md` and `CLAUDE.md` injected into every automated prompt's static prefix region.
- **FR-004-RED**: Manual `deviate red pre/post` and automated RED phase — generate failing test, validate failure, commit.
- **FR-004-GREEN**: Manual `deviate green pre/post` and automated GREEN phase — write passing code, validate tests pass, commit.
- **FR-004-YELLOW**: Conditional YELLOW phase triggered when GREEN agent modifies tests — propose amendment, JUDGE approves or rejects, rollback on rejection.
- **FR-004-JUDGE**: Isolated compliance gate evaluating `git diff` against `spec.md` for security and structural violations. Runs after GREEN, before REFACTOR.
- **FR-004-REFACTOR**: Optional manual `deviate refactor pre/post` and automated REFACTOR phase — polish implementation, validate test invariance, commit.
- **FR-004-EXECUTE**: `deviate execute pre/post` for non-TDD direct-execution tasks.
- **FR-004-E2E**: `deviate e2e pre/post` for end-to-end verification after all tasks complete.
- **FR-004-HOTFIX**: `deviate hotfix pre/post` for bug fixes bypassing RED phase.
- **FR-004-TAMPER**: Tamper Guard — `git diff` evaluation + `git restore` rollback if `tests/`, `specs/`, or config files are modified outside expected boundaries.

## [MULTI_TIERED_VERIFICATION_TARGETS]

- **Unit Tests**: `tests/test_micro/test_red.py`, `tests/test_micro/test_green.py`, `tests/test_micro/test_refactor.py`, `tests/test_micro/test_judge.py`, `tests/test_micro/test_yellow.py`, `tests/test_micro/test_execute.py`, `tests/test_micro/test_e2e.py`, `tests/test_micro/test_hotfix.py`, `tests/test_micro/test_orchestration.py`, `tests/test_core/test_agent.py`, `tests/test_core/test_tamper.py`
- **Integration Tests**: `tests/test_integration/test_micro_orchestration.py`, `tests/test_integration/test_tamper_guard.py`, `tests/test_integration/test_mise_check_gate.py`, `tests/test_integration/test_full_cycle.py`, `tests/test_integration/test_agent_backend.py`

## [DEMONSTRATION_PATH]

```bash
# Verify manual pre/post commands
pytest tests/test_micro/test_red.py tests/test_micro/test_green.py -v

# Verify automated orchestration
pytest tests/test_integration/test_micro_orchestration.py -v

# Verify agent backend
pytest tests/test_core/test_agent.py -v

# Verify Tamper Guard
pytest tests/test_integration/test_tamper_guard.py -v

# Verify full cycle
pytest tests/test_integration/test_full_cycle.py -v

mise run check
```
