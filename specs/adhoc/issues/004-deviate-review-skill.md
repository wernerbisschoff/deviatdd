---
title: "DeviaTDD Code Review Skill — /deviate-review with Constitution & PRD Anchoring"
labels: [enhancement, adhoc, vertical-slice]
blocked_by: []
coordinates_with: []
issue_id: ISS-ADH-004
---

## [SYSTEM_TOPOLOGY_MAPPING]
- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `issues/004-deviate-review-skill.md`
- **Primary Architectural Workstation**:
  - `src/deviate/prompts/skills/deviate-review/SKILL.md` — NEW: prompt skill for structured code review
  - `src/deviate/cli/review.py` — NEW: Typer subcommand module with review pre/post commands
  - `src/deviate/cli/__init__.py` — MODIFY: register review subcommand
  - `.claude/skills/deviate-review/SKILL.md` — installed via `deviate init` skill discovery

## [THE_PROBLEM_CONTRACT]
The existing code review workflow (`~/.claude/skills/tools-review/`) relies on a standalone bash orchestrator (`tools-review.sh`) that is decoupled from the DeviaTDD governance stack. When reviewing DeviaTDD-managed code, the review must verify constitution compliance and PRD traceability — domains that the generic `tools-review` skill does not enforce. A new `deviate-review` skill is needed that: (1) follows the DeviaTDD pre/post CLI command pattern, (2) always reads `specs/constitution.md` and enforces its invariants, (3) resolves and reads the appropriate PRD (epic-level first, adhoc fallback), (4) produces structured reports with machine-parseable `Fix Instructions` for cheaper model handoff, and (5) auto-discovers via `discover_skills()` into agent directories during `deviate init`.

## [SCOPE_BOUNDARIES]
### Hard Inclusions
- `src/deviate/prompts/skills/deviate-review/SKILL.md` — full prompt skill with system instructions, execution sequence (pre → domain analysis → report generation → user selection → implementation → post), domain rubrics (Security, Pragmatism, Idiomacy, Clean Code, Constitution, PRD), output schemas, edge case handling, and integration with the DeviaTDD ecosystem
- `src/deviate/cli/review.py` — `deviate review pre` (git state gathering, diff generation, governance file discovery with PRD resolution: epic first, adhoc fallback, JSON contract emission) and `deviate review post` (review report persistence, staging)
- `src/deviate/cli/__init__.py` — add `cli.add_typer(review_app, name="review")` to register the review subcommand
- PRD anchoring logic: resolves PRD in priority order — (1) branch-derived epic PRD at `specs/{EPIC}/prd.md`, (2) adhoc PRD at `specs/adhoc/prd.md`
- Review domains must include `Constitution` and `PRD` alongside Security/Pragmatism/Idiomacy/CleanCode

### Defensive Exclusions
- Do NOT modify any existing phase skills (red, green, yellow, judge, refactor, prune, e2e, execute, hotfix)
- Do NOT modify `specs/constitution.md` — review is advisory, not a governance phase
- Do NOT modify agent backend, prompt assembly, or the TDD cycle body in `micro.py`
- Do NOT add review as a phase in `_PHASE_MAP` or `_SKILL_NAMES` — review is a standalone skill, not a TDD cycle phase
- Do NOT modify `specs/DeviaTDD-api.md` or `specs/DeviaTDD-architecture.md` — review is an optional tool, not part of the core pipeline
- Do NOT create new data models or ledger entries for review — the output is a plain markdown report file
- Do NOT add dependencies beyond what's already in `pyproject.toml`

## [UPSTREAM_REQUIREMENT_TRACING]
- **Requirements Tokens**: `FR-ADHOC-004`
- **Acceptance Criteria Tokens**: `AC-ADHOC-004-01`, `AC-ADHOC-004-02`
- **Data Model Entities**: None (review does not introduce new data models)

## [MULTI_TIERED_VERIFICATION_TARGETS]
- **Unit Sandbox Targets**:
  - `tests/test_cli/test_review.py::test_review_pre_emits_contract` — verify pre command emits valid JSON contract
  - `tests/test_cli/test_review.py::test_review_pre_finds_constitution` — verify constitution_path in contract
  - `tests/test_cli/test_review.py::test_review_pre_resolves_prd_epic_first` — verify epic PRD preferred over adhoc PRD
  - `tests/test_cli/test_review.py::test_review_pre_falls_back_to_adhoc_prd` — verify adhoc PRD used when epic PRD absent
  - `tests/test_cli/test_review.py::test_review_post_persists_report` — verify review-report.md written and staged
  - `tests/test_cli/test_review.py::test_review_post_no_artifact` — verify graceful handling when no report provided
- **Integration Sandbox Targets**:
  - `tests/test_integration/test_review_cycle.py::test_review_full_cycle` — full pre→(agent review)→post cycle with mock agent

## [DEMONSTRATION_PATH]
```bash
# Unit tests
pytest tests/test_cli/test_review.py -v

# Integration test
pytest tests/test_integration/test_review_cycle.py -v -k "full_cycle"

# Manual: verify CLI works
deviate review pre --json

# Manual: verify skill auto-discovers
python -c "from deviate.core.skills import discover_skills; print([s for s in discover_skills() if 'review' in s])"
```
