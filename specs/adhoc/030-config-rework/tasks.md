# Implementation Tasks: `feat/adhoc/030-config-rework`

## Phase 1: Graphite-Free Single-Timeout Config Schema
**Goal**: One consolidated timeout field (`timeout_seconds`) governs both the agent-process wall-clock and the test-command deadline. A stale top-level `graphite` key is rejected by `extra = "forbid"`. The `[models]` resolution order stays intact.

### Tasks

- TSK-030-01: Consolidate the timeout schema and reject a stale `graphite` key
  - **Type**: Bugfix
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_state/test_config.py tests/unit/test_core/test_agent.py tests/unit/test_cli/test_micro.py -q -k "consolidated or graphite or agent_config or invoke_agent or timeout"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/state/config.py`
    - `src/deviate/core/agent.py`
    - `src/deviate/cli/meso.py`
    - `src/deviate/cli/micro.py`
    - `.deviate/config.toml`
    - `tests/unit/test_state/test_config.py`
    - `tests/unit/test_core/test_agent.py`
    - `tests/unit/test_cli/test_micro.py`
  - **Rationale**: US-030-03 and `AC-PLAN-005` require exactly one timeout field: `DeviateConfig.timeout_seconds` (default 1800). `AC-PLAN-006` requires `DeviateConfig` to reject a stale literal `graphite` key via `extra = "forbid"`. `AC-PLAN-005` also requires `resolve_phase_model` to keep the phase key → `default` → backend-native order. Removing `AgentConfig.timeout` ripples into `AgentBackend.invoke` (`self.config.timeout` in `src/deviate/core/agent.py`), `_invoke_agent_phase` (meso), `_resolve_agent_timeout` and `_invoke_agent` (micro), and `.deviate/config.toml` (`[agent] timeout = 600`). `tests/unit/test_core/test_agent.py` (`TestAgentConfigModel`) and `tests/unit/test_cli/test_micro.py` (GH-87 `config.timeout`) assert the removed field and MUST be re-pointed so the full suite stays green (constitution §3). `tests/unit/test_state/test_config.py` owns the new consolidated and graphite-rejection pins. Constitution §1 and §2: config-driven model routing stays untouched; no Product-layer flow work (`flow_refs: []`).
  - **Details**:
    - **Red**: In `tests/unit/test_state/test_config.py` add `test_consolidated_timeout_field`: build `DeviateConfig()` and assert `timeout_seconds == 1800`; assert `AgentConfig.model_fields` carries no `timeout` key and `not hasattr(DeviateConfig(agent=AgentConfig()).agent, "timeout")`. Add `test_parse_stale_graphite_key_rejected`: `DeviateConfig(graphite=True)` and `DeviateConfig.model_validate({"graphite": True})` raise `ValidationError` because `extra = "forbid"`; assert no `graphite` value is accepted. Re-point `tests/unit/test_core/test_agent.py::TestAgentConfigModel` so it builds `AgentConfig` without `timeout=` and asserts the consolidated deadline, and re-point `tests/unit/test_cli/test_micro.py` (GH-87) so `_invoke_agent`'s `AgentConfig` carries no `timeout` argument. Keep `resolve_phase_model` order pins green (`AC-PLAN-005`).
    - **Green**: In `src/deviate/state/config.py` delete the `AgentConfig.timeout` field and its comment; keep `DeviateConfig.timeout_seconds: int = Field(default=1800, gt=0)`; keep `extra = "forbid"` on both models; keep `resolve_phase_model` unchanged. In `src/deviate/core/agent.py` `invoke`, route `effective_timeout` from the single consolidated value instead of `self.config.timeout`. In `src/deviate/cli/meso.py::_invoke_agent_phase`, build `AgentConfig(backend=backend_name)` without the removed `timeout=` from `[agent].timeout` and resolve the agent wall-clock from `timeout_seconds`. In `src/deviate/cli/micro.py`, point `_resolve_agent_timeout` at `timeout_seconds` (default 1800) instead of `[agent].timeout` (600) and drop the `timeout=` argument at the `AgentConfig(backend=...)` call. Remove `timeout = 600` under `[agent]` in `.deviate/config.toml`; keep the `[models]` block optional.
    - **Refactor**: Resolve the agent deadline at one site shared by meso and micro so the two callers cannot drift on the consolidated field.
    - **Edge Cases**: `timeout_seconds` keeps `gt=0` validation so a non-positive value still fails closed. A config with no `timeout_seconds` falls back to 1800. A stale `graphite` key is rejected, never silently dropped. Backends without `--model` still resolve unchanged (`resolve_phase_model`). Do not delete branches and do not reopen ISS-ADH-027's 600s `AgentConfig.timeout` semantics for the harness budget.
    - **Acceptance**: `config.toml` has exactly one timeout field (`timeout_seconds`). `[agent]` carries no `timeout`. `DeviateConfig` rejects a stale `graphite` key. Agent and test deadlines route from `timeout_seconds`. `resolve_phase_model` order is intact. `pytest` on the Phase 1 target files exits 0 and `uv run ruff check` is clean.
  - **Dependency**: none

---

## Phase 2: Per-Agent Install and Auto-Detection in `setup`
**Goal**: `setup --agent <name>` installs commands and skills only under that named agent. An omitted `--agent` calls `detect_agents` and targets exactly the installed agent directories. Unknown or uninstalled names fail closed with no partial install.

### Tasks

- TSK-030-02: Make `setup` install per-agent and auto-detect installed agents
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: Integration
  - **Verification**: `uv run pytest tests/unit/test_cli/test_init.py tests/test_integration/test_skill_installation.py -q -k "setup or install or auto_detect or agent"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `tests/unit/test_cli/test_setup.py`
    - `tests/test_integration/test_skill_installation.py`
  - **Rationale**: US-030-02 and `AC-PLAN-002` require `setup --agent opencode` to write command and skill files only under `.opencode/` and exit 0 with `INSTALL` printed. `AC-PLAN-003` requires `setup` with no `--agent` to target exactly the directories returned by `detect_agents` in `src/deviate/core/commands.py`. `AC-PLAN-004` requires `setup --agent <unknown>` to fail closed with a clear error and no partial install. `src/deviate/cli/__init__.py` owns `setup` and `_install_commands_to_agents` / `_install_deviatdd_skill` dispatch. `tests/test_integration/test_skill_installation.py` pins the `INSTALL` + exit 0 contract; `tests/unit/test_cli/test_setup.py` (new) carries the per-agent and auto-detect unit pins. Constitution §3 Testing Protocols: use `CliRunner` with `chdir(tmp_path)` and mock `_get_agent_command_dir` so the temp tree is the only write target.
  - **Details**:
    - **Red**: In `tests/unit/test_cli/test_setup.py` add `test_setup_single_agent_only`: create `.opencode/` and `.claude/`, mock `_get_agent_command_dir` to map to the temp tree, run `setup --agent opencode`, and assert command/skill files exist under `.opencode/` only and none under `.claude/`. Add `test_setup_auto_detect_installed_agents`: create `.claude/` and `.opencode/` only, run `setup` with no `--agent`, and assert files are written to exactly those two directories and to no other agent directory. Add `test_setup_unknown_agent_fails_closed`: run `setup --agent bogus` and assert a clear error, a non-zero exit, and no command or skill file written to any agent directory. Update `tests/test_integration/test_skill_installation.py` to keep `INSTALL` and exit code 0 for `setup --agent opencode`.
    - **Green**: In `src/deviate/cli/__init__.py::setup`, when `--agent` is given, validate the name and dispatch `_install_commands_to_agents` / `_install_deviatdd_skill` to that single agent only. When `--agent` is omitted, call `detect_agents(workdir)` and dispatch to exactly the returned installed agents; if none is detected, print a clear error and exit non-zero. Validate any `--agent` name against the installed dirs (or `AGENT_CHOICES`) and fail closed before any write. Keep the `[agent].backend` write unchanged.
    - **Refactor**: Extract a single `_resolve_setup_agents(workdir, selected_agent)` helper so the per-agent and auto-detect branches share one validation read.
    - **Edge Cases**: A name declared in `AGENT_TO_BACKEND` but with no `.claude/`-style directory installed is treated as uninstalled and fails closed. `droid` stays normalized to `factory` per `AGENT_TO_BACKEND`. A missing `detect_agents` result writes nothing. Re-running setup stays idempotent (`SKIP` on identical content).
    - **Acceptance**: `setup --agent opencode` writes only under `.opencode/` and prints `INSTALL` with exit 0. `setup` with no `--agent` writes only to installed agent dirs. `setup --agent <unknown>` fails closed with a clear error and no partial install.
  - **Dependency**: TSK-030-01

---

  - **Judge Feedback**: GREEN attempt rejected for two HIGH violations; fix both before re-entering JUDGE.
1. src/deviate/cli/__init__.py::_install_deviatdd_skill dereferences target_dir
   without checking for None. For agent names outside ("claude", "opencode",
   "factory", "pi", "omp") — reachable via `--agent droid` in an empty
   workspace — this raises TypeError after partial provisioning. Add the same
   None-guard SKIP branch that _install_commands_to_agents already has.
2. tests/unit/test_cli/test_init.py still contains 7 tests asserting the removed
   install-to-all policy and unconditional droid support. Rewrite them to the
   plan contract: --agent installs to exactly that agent; no --agent installs
   to exactly detect_agents(workdir); declared-but-uninstalled agents exit
   code 1 with a clear error and zero command/skill files written. Do not
   delete coverage of the gitignore and config scenarios — they already pass.
Anchor: verify with pytest tests/unit/test_cli/test_init.py -q before resubmission.
## Phase 3: Git-Ignore `.deviate/` by Default
**Goal**: `deviate setup` provisions a git-ignore entry so `.deviate/` is untracked by default for new consumer projects, while preserving already-tracked history.

### Tasks

- TSK-030-03: Make `setup` git-ignore `.deviate/` by default
  - **Type**: Config
  - **Mode**: TDD
  - **Test Strategy**: Sociable_Unit
  - **Verification**: `uv run pytest tests/unit/test_cli/test_setup.py tests/unit/test_cli/test_init.py -q -k "gitignore or git_ignores or dotdeviate or ignore"`
  - **Estimated Time**: 60 minutes
  - **Flow References**: []
  - **Files**:
    - `src/deviate/cli/__init__.py`
    - `.gitignore`
    - `.deviate/.gitignore`
    - `tests/unit/test_cli/test_setup.py`
  - **Rationale**: US-030-01 and `AC-PLAN-001` require a fresh consumer `deviate setup` to resolve `.deviate/` as a git-ignored path via `git check-ignore .deviate/` and to show no untracked `.deviate/` candidate in `git status` on an empty working tree. `src/deviate/cli/__init__.py` owns `_ensure_root_gitignore` and `_ensure_gitignore`, which currently ignore subpaths but not `.deviate/` itself. `.gitignore` and `.deviate/.gitignore` are the provisioning targets. `tests/unit/test_cli/test_setup.py` owns the git-ignore pin run in a fresh temp git repo (`tmp_git_repo` + `_git_env()` from `tests/conftest.py`) per AO-030-01 Boundary that the change governs new provisioning only and never untracks already-tracked history. Constitution §1 Git Isolation: the test git runs stay inside the temp repo.
  - **Details**:
    - **Red**: In `tests/unit/test_cli/test_setup.py` add `test_setup_gitignores_dotdeviate`: use `tmp_git_repo` and `_git_env()`, create a `.deviate/` dir with a `config.toml`, run `deviate setup`, then `git check-ignore .deviate/` from the temp repo and assert it resolves; run `git status --porcelain` on an empty working tree and assert `.deviate/` is not an untracked candidate. Assert an already-tracked file inside `.deviate/` stays tracked (no deletion reported).
    - **Green**: In `src/deviate/cli/__init__.py`, extend `_ensure_root_gitignore` (or `_ensure_gitignore`) to provision a `.deviate/` entry so new consumer setups ignore the directory by default, and report the provisioning step on `deviate setup`. Guard against any retrospective untrack: do not `git rm` or delete an already-tracked `.deviate/...` file, and keep the ignores idempotent across re-runs.
    - **Refactor**: Share the ignore-entry upsert helper so the root and `.deviate/` gitignore writes use one idempotent merge path.
    - **Edge Cases**: A missing `.deviate/` directory is created by `_ensure_gitignore` with no error. Re-running setup does not duplicate the `.deviate/` entry. An already-tracked `.deviate/config.toml` in an existing consumer is untouched. `.env*` and secret files stay untracked.
    - **Acceptance**: `git check-ignore .deviate/` resolves after setup in a fresh temp consumer. `git status` shows no untracked `.deviate/` candidate on an empty tree. Already-tracked `.deviate/` history is preserved. Setup prints the git-ignore provisioning step and exits 0.
  - **Dependency**: TSK-030-02

---

## Phase 4: Spec, Governance, and Changelog Alignment
**Goal**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `AGENTS.md`, and `CHANGELOG.md` mirror the per-agent install, auto-detect, git-ignore-by-default, and single-timeout rework in the same change set.

### Tasks

- TSK-030-04: Align api/architecture specs, remove the AGENTS.md Graphite section, and append the changelog bullet
  - **Type**: Config
  - **Mode**: IMMEDIATE
  - **Verification**: `uv run pytest tests/unit/test_state/test_config.py tests/unit/test_cli/test_setup.py tests/unit/test_cli/test_init.py tests/test_integration/test_skill_installation.py -q && uv run ruff check .`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `specs/DeviaTDD-api.md`
    - `specs/DeviaTDD-architecture.md`
    - `AGENTS.md`
    - `CHANGELOG.md`
  - **Rationale**: AGENTS.md Spec Alignment and constitution §5 Definition of Done require the api and architecture specs to document the setup behavior change (per-agent install, auto-detect, `.deviate/` git-ignore-by-default, single `timeout_seconds`) and the CHANGELOG to carry a user-visible `[Unreleased]` bullet in the same implementation commit. US-030-01, US-030-02, and US-030-03 are the user-visible changes. `AGENTS.md` line 96 still documents a `graphite = true` workflow that is removed from active config; the section is deleted. `flow_refs: []`, so no Product-layer flows are authored or synchronized.
  - **Details**:
    - **Implementation**: In `specs/DeviaTDD-api.md`, document that `setup --agent <name>` installs commands and skills only to that named agent, an omitted `--agent` auto-detects installed agents via `detect_agents`, `.deviate/` is git-ignored by default for new consumers, and `.deviate/config.toml` exposes one `timeout_seconds` with no `[agent] timeout` and no `graphite` surface.
    - **Implementation**: In `specs/DeviaTDD-architecture.md`, update the config schema and setup provisioning sections to the single-timeout, Graphite-free schema and the per-agent/auto-detect install behavior, keeping the `[models]` resolution order (phase key → `default` → backend-native).
    - **Implementation**: Delete the `AGENTS.md` Graphite section (line 96) and confirm `grep -rn "graphite" src/ AGENTS.md` returns no active matches.
    - **Implementation**: Append one `[Unreleased]` bullet to `CHANGELOG.md` recording the setup provisioning rework and the consolidated single-timeout schema as a user-visible change.
    - **Refactor**: Reuse the existing spec wording for config-driven model routing; do not add a second timeout constant or a second Graphite reference.
    - **Edge Cases**: Docs still say the `[models]` block is optional and readable. Docs still say an installed agent directory (not a merely declared backend) drives auto-detection. `flow_refs` stays `[]`.
    - **Acceptance**: api and architecture specs reflect the per-agent install, auto-detect, git-ignore-by-default, and single-timeout behavior. `AGENTS.md` has no Graphite section. `CHANGELOG.md` `[Unreleased]` has the ISS-ADH-030 bullet. `uv run pytest` on the Phase 1-3 pins and `uv run ruff check .` pass.
  - **Dependency**: TSK-030-03

---

## Phase 5: CLI E2E
**Goal**: The installed `deviate setup` performs per-agent install, auto-detects installed agents, git-ignores `.deviate/`, and the installed config exposes exactly one `timeout_seconds` with no `[agent] timeout`.

### Tasks

- TSK-030-05: [E2E] Verify installed `setup` per-agent install, auto-detect, git-ignore, and single-timeout
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: Integration
  - **Verification**: `bats tests/e2e/`
  - **Estimated Time**: 30-90 minutes
  - **Flow References**: []
  - **Files**:
    - `tests/e2e/test_setup_rework.bats`
    - `tests/e2e/test_red_hang_timeout_rollback.bats`
  - **Rationale**: US-030-01, US-030-02, and US-030-03 are the user-visible CLI happy paths for `deviate setup`: per-agent install to exactly the `--agent` target, auto-detection to installed agent dirs, `.deviate/` git-ignored by default (`AC-PLAN-001`, `AC-PLAN-002`, `AC-PLAN-003`), and a single consolidated timeout (`AC-PLAN-005`). `test_red_hang_timeout_rollback.bats` still asserts `AgentConfig().timeout == 600`, which the Phase 1 consolidation removes; that assertion is re-pointed to the consolidated field. Constitution §3 E2E command is `bats tests/e2e/`. Files stay under `tests/e2e/`.
  - **Details**:
    - **Implementation**: Add `tests/e2e/test_setup_rework.bats`. Happy path: in a fresh tmpdir with `.claude/` and `.opencode/` present, run the installed `deviate setup` with no `--agent` and assert it exits 0, prints `INSTALL`, and writes command/skill files under both detected directories only.
    - **Implementation**: Critical-failure path in the same bats file: run `deviate setup --agent bogus` in a fresh tmpdir and assert a clear error, a non-zero exit, and no command or skill file under any agent directory (`AC-PLAN-004`).
    - **Implementation**: Add a git-ignore path: initialize the tmpdir as a git repo, run `deviate setup`, run `git check-ignore .deviate/`, and assert it resolves; assert `git status --porcelain` shows no untracked `.deviate/` candidate on an empty tree (`AC-PLAN-001`).
    - **Implementation**: Update `tests/e2e/test_red_hang_timeout_rollback.bats` to drop the `AgentConfig().timeout == 600` assertion and instead assert the installed `DeviateConfig().timeout_seconds == 1800` and that `[agent]` carries no `timeout` (`AC-PLAN-005`).
    - **Refactor**: Reuse the bats tmpdir setup/teardown and `_installed_python`-style helper from the existing e2e suite.
    - **Edge Cases**: Start each test in a fresh tmpdir so the host repo `.deviate/session.json` and tracked config are unused. Do not sleep on live `pi -p` children; do not delete branches in the host repo.
    - **Acceptance**: `bats tests/e2e/` exits 0. Installed `setup` performs per-agent install and auto-detect, fails closed on an unknown agent, git-ignores `.deviate/`, and exposes one `timeout_seconds` with no `[agent] timeout`.
  - **Dependency**: TSK-030-04

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5

**Critical Dependency Chains**:
- TSK-030-01 must precede TSK-030-02 (the `[agent] timeout` removal is a precondition for the per-agent config writer)
- TSK-030-02 must precede TSK-030-03 (per-agent dispatch and the git-ignore entry both edit `src/deviate/cli/__init__.py::setup`)
- TSK-030-03 must precede TSK-030-04 (specs mirror the implementation in the same change)
- TSK-030-04 must precede TSK-030-05 (the closing E2E re-points the timeout assertion the earlier phases changed)

**Risk Hotspots**:
- Removing `AgentConfig.timeout` breaks `tests/unit/test_core/test_agent.py::TestAgentConfigModel` and `tests/unit/test_cli/test_micro.py` (GH-87) and `tests/e2e/test_red_hang_timeout_rollback.bats`; all must be re-pointed to the single `timeout_seconds` in the same phase.
- Install-to-all → per-agent dispatch can regress the pinned `tests/test_integration/test_skill_installation.py` contract; preserve `INSTALL` + exit 0.
- Auto-detection can confuse an installed directory with a merely declared backend; target only `detect_agents` results and fail closed on unknown/uninstalled names.
- Git-ignoring `.deviate/` must apply to new provisioning only and never untrack already-tracked history per AO-030-01 Boundary.
- Live agent children, un-mocked `_run_pytest`, or a real 1800s timeout would blow the 30s suite budget; mock `deviate.cli.micro._run_pytest` and patch short deadlines.

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/__init__.py` (Phase 2 and Phase 3), `tests/unit/test_cli/test_setup.py` (Phase 2 and Phase 3). Phase 1 owns `config.py` / `agent.py` / `meso.py` / `micro.py`. Phase 4 owns specs, `AGENTS.md`, `CHANGELOG.md`. Phase 5 owns `tests/e2e/`.

**Product-Layer Anchors** (mirrored from plan.md):
- **Flow References**: `[]`
- **Source**: `specs/adhoc/030-config-rework/plan.md`
- Downstream micro phases inherit this list per-task. Empty references mean no matching existing flow, not permission for enabling, setup, tooling, skill, release, or workflow-ledger tasks.

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.
- **Suite Budget**: Any test that would drive `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` so the full suite stays under 30 seconds (AGENTS.md; constitution §3). Timeout pins MUST patch short deadlines and mock `Popen` / `invoke`. Do not sleep 1800s and do not spawn live `pi -p` children.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
