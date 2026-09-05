---
title: "Consolidate skill export to one shared directory for Pi and Codex"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-047
---

## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/047-consolidate-skill-export.md`
- **Primary Architectural Workstation**: `src/deviate/cli/__init__.py`, `src/deviate/core/agent.py`

## The Problem Contract
Setup for Codex plus Pi writes two copies of the `deviatdd` skill. Pi discovers both `.agents/skills/` and `.pi/skills/`. Pi then warns about duplicate skills. One shared copy removes the warning.

## Scope Boundaries
### Hard Inclusions
- Single shared skill export used when Codex and Pi are both selected
- Compatibility handling so existing single-agent paths keep working
- Pi duplicate-skill warning gone after setup with both agents

### Defensive Exclusions
- No change to slash-command install paths
- No change to global export layout beyond the skill directory
- No change to agent spawn flags or model routing

## Upstream Requirement Tracing
- **Requirements Tokens**: `FR-ADHOC-047`
- **Acceptance Criteria Tokens**: `AC-ADHOC-047-01`, `AC-ADHOC-047-02`
- **Data Model Entities**: none

## User Stories Ledger
- **US-047-01**: As a developer running setup for Codex and Pi, I want one shared skill copy so that Pi stops warning about duplicate skills. *(Ref: FR-ADHOC-047)*
- **US-047-02**: As an operator with only Pi or only Codex selected, I want setup to keep working unchanged so that single-agent flows never break. *(Ref: FR-ADHOC-047)*

## Acceptance Outline
- **AO-047-01** *(Ref: AC-ADHOC-047-01, US-047-01)*: Setup with Codex plus Pi writes one skill copy under the shared directory and Pi reports no duplicate-skill warning.
  - **Happy Path**: Both agents resolve skills; one copy exists on disk.
  - **Error Category**: Stale duplicate copy remains and warning persists.
  - **Boundary Category**: Re-run of setup over an old two-copy layout converges to one copy.
- **AO-047-02** *(Ref: AC-ADHOC-047-02, US-047-02)*: Setup with a single agent installs exactly as today.
  - **Happy Path**: Single-agent layout unchanged; no extra directories appear.
  - **Error Category**: Missing skill for the selected agent.
  - **Boundary Category**: Global export mode still resolves the correct home-tree directory.

## Edge Cases and Boundaries
- Re-run over a workdir with the old two-copy layout removes or links the stale copy.
- Unknown agents never resolve to the shared directory.
- Source: `src/deviate/cli/__init__.py` `_get_agent_skill_dir` maps codex to `.agents/skills` and pi to `.pi/skills`.
- Source: `specs/explore/skills-export-agents.md` records Pi discovery of `.pi/skills/`, `.pi/agent/skills/`, and `.agents/skills/`.

## Performance Constraints
- L_max: 500ms init overhead budget unchanged
- Throughput: setup writes at most one extra filesystem link per skill

## Multi-Tiered Verification Targets
- **Unit Sandbox Targets**: `tests/` setup skill-install tests covering `_get_agent_skill_dir` and `_install_deviatdd_skill`
- **Integration Sandbox Targets**: `deviate setup` with codex plus pi on a temp workdir, then assert one skill copy and no duplicate warning

## Demonstration Path
```bash
uv run deviate setup --agent codex,pi && find .agents .pi -path '*deviatdd/SKILL.md'
```
