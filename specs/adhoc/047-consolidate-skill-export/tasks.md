# Implementation Tasks: `feat/adhoc/047-consolidate-skill-export`

## Phase 1: Shared Skill Copy for Codex plus Pi
**Goal**: `deviate setup --agent codex,pi` writes one shared `deviatdd` skill copy and Pi resolves it first

### Tasks

- TSK-047-01: Accept comma-separated `--agent` list and resolve install targets
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_cli/test_setup.py`
    - `src/deviate/cli/__init__.py`
  - **Rationale**: `US-047-02` needs single-agent selection working unchanged (`AC-PLAN-003`); `US-047-01` needs `codex,pi` accepted as one selection (`AC-PLAN-001`). The test file pins the selection contract. `src/deviate/cli/__init__.py` owns `_validate_agent_choice` and `_resolve_install_agents`, the only production code this behavior touches.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/test_setup.py` only — forbid `tests/test_integration/` and `tests/e2e/` in this RED. Assert `_validate_agent_choice("codex,pi")` returns the pair, single values pass through unchanged, `_resolve_install_agents` returns both names in order with duplicates removed, and unknown names fail closed with no writes.
    - **Green**: Split `--agent` on commas in `_validate_agent_choice` and validate each name against `AGENT_CHOICES`; extend `_resolve_install_agents` to wrap the ordered deduped list. Keep single-value behavior byte-identical.
    - **Refactor**: Reuse the existing `AGENT_CHOICES` join for the error message; no new dependencies.
    - **Edge Cases**: Handle whitespace around commas; handle empty segments by failing closed; handle `droid` alias resolution unchanged for single values.
    - **Acceptance**: `mise unit` passes; `setup --agent pi` and `setup --agent codex` behave exactly as today.

- TSK-047-02: Write one shared skill copy for codex plus Pi and converge stale layouts
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/test_cli/test_setup.py`
    - `src/deviate/cli/__init__.py`
  - **Rationale**: `US-047-01` demands one shared copy with no stale duplicate (`AC-PLAN-001`, `AC-PLAN-002`); `US-047-02` demands single-agent and global installs unchanged (`AC-PLAN-003`, `AC-PLAN-004`). The test file pins the on-disk contract. `src/deviate/cli/__init__.py` owns `_get_agent_skill_dir`, `_agent_install_root`, and `_install_deviatdd_skill`, the only production code this behavior touches.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/test_cli/test_setup.py` only — forbid `tests/test_integration/` and `tests/e2e/` in this RED. Assert installing for `["codex", "pi"]` writes exactly one `deviatdd/SKILL.md` under `.agents/skills/` with identical body, removes the stale `.pi/skills/deviatdd` tree, preserves existing command trees, and that single-agent plus global-root resolution still lands under the agent home tree with no workdir copy.
    - **Green**: Dedupe codex plus pi skill targets to `.agents/skills/` in `_install_deviatdd_skill` and delete only `.pi/skills/deviatdd` after the shared write. Leave `_agent_install_root` global behavior unchanged.
    - **Refactor**: Share one target-path computation between the skip check and the write path; no new dependencies.
    - **Edge Cases**: Handle re-run over the old two-copy layout by converging to one copy; handle cleanup touching only `.pi/skills/deviatdd`, never sibling skills; handle identical-body reruns reporting SKIP.
    - **Acceptance**: `mise unit` passes; dual-agent local setup leaves exactly one `deviatdd/SKILL.md` and no `.pi/skills/deviatdd` copy.
  - **Dependency**: `TSK-047-01`

- TSK-047-03: Resolve the shared skill copy first in Pi lean-skill injection
  - **Type**: Feature_Batch
  - **Mode**: TDD
  - **Test Strategy**: unit
  - **Verification**: `mise unit`
  - **Estimated Time**: 60 minutes
  - **Files**:
    - `tests/unit/core/test_agent.py`
    - `src/deviate/core/agent.py`
  - **Rationale**: `US-047-01` needs Pi spawn to find the moved skill with no duplicate warning (`AC-PLAN-002`). The test file pins the spawn-flag contract. `src/deviate/core/agent.py` owns `PI_DEVIATDD_SKILL` and `_pi_lean_flags`, the only production code this behavior touches.
  - **Details**:
    - **Red**: Write failing unit tests in `tests/unit/core/test_agent.py` only — forbid `tests/test_integration/` and `tests/e2e/` in this RED. Assert `_pi_lean_flags` injects the shared `.agents/skills/deviatdd/SKILL.md` path when it exists, falls back to the legacy `.pi/skills/deviatdd/SKILL.md` for single-Pi setups, injects no skill flag when neither copy exists, and preserves the existing `--tools` plus `--no-skills` flag sequence.
    - **Green**: Resolve the shared path first with legacy fallback in `_pi_lean_flags`, keeping `PI_DEVIATDD_SKILL` as the legacy constant. Scoped to workstation files required by those scenarios.
    - **Refactor**: Keep the path constants beside `PI_DEVIATDD_SKILL`; reuse the existing `skill_root` computation.
    - **Edge Cases**: Handle both copies present by preferring shared; handle missing copies by emitting no `--skill` flag; handle `cwd=None` defaulting to current directory.
    - **Acceptance**: `mise unit` passes; Pi spawn reports no duplicate-skill warning on the converged layout.
  - **Dependency**: `TSK-047-02`

- TSK-047-04: End-to-end setup run over dual-agent and stale layouts
  - **Type**: Verification_Batch
  - **Mode**: IMMEDIATE
  - **Test Strategy**: e2e
  - **Verification**: `mise unit && mise integration && mise e2e`
  - **Estimated Time**: 30-90 minutes
  - **Files**:
    - `tests/e2e/test_setup_config_rework.bats`
    - `tests/e2e/test_setup_shared_skill.bats`
  - **Rationale**: `US-047-01` happy path (`AO-047-01`: dual-agent setup writes one copy, re-run converges, no duplicate warning) plus `US-047-02` critical-failure guard (`AO-047-02`: single-agent setup writes only its own tree) need a real-CLI proof beyond unit pins. Both files live under `tests/e2e/`; the stale two-copy fixture is seeded inline by the bats run itself.
  - **Details**:
    - **Implementation**: Add a bats case running `deviate setup --agent codex,pi` in a fresh tmpdir asserting exactly one `deviatdd/SKILL.md` under `.agents/skills/`, no `.pi/skills/deviatdd` copy, and exit 0; add a case seeding the old two-copy layout inline then re-running setup and asserting convergence; add a case asserting `setup --agent pi` writes only the `.pi` tree.
    - **Refactor**: Reuse the existing `_deviate` helper and tmpdir `setup`/`teardown` pattern from `test_setup_config_rework.bats`.
    - **Edge Cases**: Handle unknown `--agent` values exiting non-zero with no skill trees written.
    - **Acceptance**: `mise e2e` passes for the new cases; `mise unit` stays green.
  - **Dependency**: `TSK-047-03`

---

## Implementation Strategy
**Execution Order**:
1. Phase 1 `TSK-047-01` -> `TSK-047-02` -> `TSK-047-03` -> `TSK-047-04`

**Critical Dependency Chains**:
- `TSK-047-01` must precede `TSK-047-02` (agent list resolution before shared-copy install)
- `TSK-047-02` must precede `TSK-047-03` (on-disk layout before Pi spawn resolution)
- `TSK-047-03` must precede `TSK-047-04` (unit behavior before end-to-end proof)

**Risk Hotspots**:
- Comma split breaks single-agent callers; mitigated by single-value passthrough tests (`TSK-047-01`)
- Pi spawn misses the moved skill; mitigated by shared-first plus legacy fallback (`TSK-047-03`)
- Stale-copy removal deletes user content; mitigated by scoping cleanup to `.pi/skills/deviatdd` only (`TSK-047-02`)

**Merge Conflict Boundaries**:
- Files touched by multiple phases: `src/deviate/cli/__init__.py`, `tests/unit/test_cli/test_setup.py` (`TSK-047-01` and `TSK-047-02` append to the same files; land `TSK-047-01` first)

---

## Universal Test Constraints (ALL TASKS)

- **Git Isolation Mandatory**: Any test that invokes git operations MUST operate on a temporary directory initialized as a fresh git repo. Tests MUST NOT run git commands within the real repository's working tree.
- **Implementation Pattern**: Use a shared `tmp_git_repo` fixture from `tests/conftest.py`. Pass `repo=tmp_git_repo` to all git-interacting functions. Never reference `Path.cwd()` or the real repo root.
- **Rationale**: Prevent accidental commits, branch creation, or state mutation in the actual project repo during test execution.

## Universal API Design Constraint (ALL CORE MODULES)

Every git-interacting function in core modules MUST accept an optional `repo_path: Path | None = None` parameter. When `None`, default to `Path.cwd()`.
