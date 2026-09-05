## Plan Summary
- **Issue**: ISS-ADH-047 — Consolidate skill export to one shared directory for Pi and Codex
- **Implementation Strategy**: Parse comma-separated `--agent` values, then write one shared `deviatdd` skill copy under `.agents/skills/` when Codex and Pi are both selected and point Pi lean-skill injection at the shared copy.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 2-4 hours

## Acceptance Contract
**Scenario AC-PLAN-001: Setup with Codex plus Pi writes one shared skill copy**
- **Source Outline**: `AO-047-01`
- **Upstream Traceability**: `US-047-01`, `FR-ADHOC-047`, `AC-ADHOC-047-01`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_get_agent_skill_dir`
- **Given**: Workdir has no skill copies and operator selects Codex plus Pi
- **When**: Operator runs setup with both agents selected
- **Then**: Exactly one `deviatdd/SKILL.md` copy exists under the shared `.agents/skills/` directory and no stale `.pi/skills/deviatdd` copy remains
- **Verification Mode**: automated
**Scenario AC-PLAN-002: Re-run over old two-copy layout converges to one copy**
- **Source Outline**: `AO-047-01`
- **Upstream Traceability**: `US-047-01`, `FR-ADHOC-047`, `AC-ADHOC-047-01`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_install_deviatdd_skill`
- **Given**: Workdir holds the old two-copy layout under `.agents/skills/` and `.pi/skills/`
- **When**: Operator re-runs setup with Codex plus Pi selected
- **Then**: Stale `.pi/skills/deviatdd` copy is removed or linked and Pi reports no duplicate-skill warning
- **Verification Mode**: automated
**Scenario AC-PLAN-003: Setup with a single agent installs exactly as today**
- **Source Outline**: `AO-047-02`
- **Upstream Traceability**: `US-047-02`, `FR-ADHOC-047`, `AC-ADHOC-047-02`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_resolve_install_agents`
- **Given**: Operator selects only Pi or only Codex
- **When**: Operator runs setup with the single agent
- **Then**: Skill installs to that agent directory only and no extra agent directories appear
- **Verification Mode**: automated
**Scenario AC-PLAN-004: Global export mode still resolves the correct home-tree directory**
- **Source Outline**: `AO-047-02`
- **Upstream Traceability**: `US-047-02`, `FR-ADHOC-047`, `AC-ADHOC-047-02`
- **Current-Code Evidence**: `src/deviate/cli/__init__.py:_agent_install_root`
- **Given**: Operator runs setup in global export mode with a single agent
- **When**: Setup resolves the install root
- **Then**: Skill lands under the user home tree for that agent and no workdir copy appears
- **Verification Mode**: automated

## Workstation Mapping
- **src/deviate/cli/__init__.py**: owns agent selection, skill-dir mapping, and skill install
  - **Current State**: `--agent` validates one name from `AGENT_CHOICES`; `_get_agent_skill_dir` maps codex to `.agents/skills` and pi to `.pi/skills`; `_install_deviatdd_skill` writes one copy per agent
  - **Changes Required**: Accept comma-separated `--agent` list; add shared-copy branch so codex+pi writes once under `.agents/skills/` and removes stale `.pi/skills/deviatdd`
  - **Integration Surface**: `_validate_agent_choice`, `_resolve_install_agents`, `_get_agent_skill_dir`, `_install_deviatdd_skill`, `setup` command
- **src/deviate/core/agent.py**: owns Pi lean-skill injection at spawn time
  - **Current State**: `PI_DEVIATDD_SKILL` points at `.pi/skills/deviatdd/SKILL.md` and `_pi_lean_flags` injects it when present
  - **Changes Required**: Resolve the shared copy first (`.agents/skills/deviatdd/SKILL.md` when both agents installed) with fallback to the legacy `.pi/skills/` path for single-Pi setups
  - **Integration Surface**: `PI_DEVIATDD_SKILL`, `_pi_lean_flags`, Pi spawn flags

## Implementation Strategy
- **Phase 1**: Multi-agent selection plus shared skill install
  - **Files**: `src/deviate/cli/__init__.py`, `src/deviate/core/agent.py`
  - **Approach**: Split `--agent` on commas and validate each name; in `_install_deviatdd_skill` dedupe codex+pi to one write under `.agents/skills/` and delete stale `.pi/skills/deviatdd`; update `PI_DEVIATDD_SKILL` resolution to prefer the shared path with legacy fallback
  - **Verification**: Unit tests for `_get_agent_skill_dir` and `_install_deviatdd_skill`; `CliRunner` setup run on temp workdir asserts one copy; re-run over two-copy fixture converges

## Data Flow Analysis
- Input: `--agent codex,pi` string plus export mode (`local` or `global`); transform: split and validate names, resolve install root, dedupe codex+pi skill targets to `.agents/skills/deviatdd/SKILL.md`, remove stale `.pi/skills/deviatdd`; output: one `SKILL.md` on disk plus `INSTALL` console line; storage: project workdir (local) or user home tree (global); Pi spawn reads the shared path via `_pi_lean_flags`

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Comma-separated `--agent` breaks single-agent callers | High | Low | Keep single value working unchanged; split only on comma |
| Pi spawn misses skill after path move | High | Medium | Prefer shared path with legacy `.pi/skills/` fallback in `agent.py` |
| Stale-copy removal deletes user content | Medium | Low | Remove only `deviatdd/SKILL.md` under `.pi/skills/` written by setup |

## Security Profile
Risk surfaces: file paths, subprocess
Negative tests: unknown agent names fail closed with no writes; stale-copy cleanup never touches paths outside `.pi/skills/deviatdd`
Constraints: no new dependencies; no writes outside the selected agent skill dirs and home-tree global root

## Integration Points
- **`deviate setup --agent`**: accepts `codex,pi` comma list; single values behave as today
- **Pi lean-skill injection**: `_pi_lean_flags` resolves shared `.agents/skills/deviatdd/SKILL.md` first, legacy `.pi/skills/` second
- **Global export mode**: single-agent global paths unchanged; shared-copy dedupe applies to local dual-agent setup only

## Constitutional Alignment
- **Architecture**: Meso plan for one adhoc issue; Micro RED encodes user scenarios as failing tests before GREEN writes `src/` only
- **Testing**: pytest via `tests/`; unit pins for dir mapping and install plus temp-workdir integration run; coverage target >= 80%
- **Git Isolation**: Work happens on the dedicated issue worktree branch; orchestrator commits at phase boundaries
- **User Scenarios**: `AC-PLAN-001` and `AC-PLAN-002` encode `US-047-01` plus ATDD; `AC-PLAN-003` and `AC-PLAN-004` encode `US-047-02`; RED turns those into failing tests
