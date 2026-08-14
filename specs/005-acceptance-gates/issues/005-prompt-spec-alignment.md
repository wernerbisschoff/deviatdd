---
title: "Prompt Template and Specification Alignment"
labels: [enhancement, vertical-slice, acceptance-gates, docs]
source_file: "specs/005-acceptance-gates/issues/005-prompt-spec-alignment.md"
blocked_by: ["005-004"]
coordinates_with: ["005-003"]
issue_id: 005-005
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/005-acceptance-gates/`
- **Local Issue File**: `specs/005-acceptance-gates/issues/005-prompt-spec-alignment.md`
- **Primary Architectural Workstations**:
  - `src/deviate/prompts/commands/deviate-red.md` — MODIFY: state that RED completes on a passing test with a warning advisory; remove any statement that RED rejects a passing test.
  - `src/deviate/prompts/auto/red.md` — MODIFY: describe the checkpoint semantics; the phase completes and hands the advisory to GREEN.
  - `src/deviate/prompts/auto/green.md` — MODIFY: describe the blocking gate; a failing suite routes to JUDGE via `train_feedback`; the RED warning advisory does not block start.
  - `src/deviate/prompts/auto/refactor.md` — MODIFY: describe the regression gate; a non-zero post-polish test result fails the phase.
  - `specs/DeviaTDD-api.md` — MODIFY: document the `**Verification Mode**: <automated|manual|deferred>` contract line, the `TaskRecord.acceptance_criteria` field, the `RedHandoffAdvisory` handoff, and the GREEN/REFACTOR gate semantics (spec-alignment mandate, `AGENTS.md` `📐 Spec Alignment`).
  - `specs/DeviaTDD-architecture.md` — MODIFY: document the RED checkpoint, GREEN gate with JUDGE routing, and REFACTOR regression gate in the phase state machine (spec-alignment mandate).
  - `CHANGELOG.md` — MODIFY: append a bullet under `[Unreleased]` for the user-visible gate behavior changes (CHANGELOG discipline, constitution §5).
  - `tests/test_meso/test_auto_prompt_templates.py` — TARGET: extend or add checks that the red/green/refactor templates carry the new semantics and no stale rejection statements.
- **Upstream Evidence**:
  - `specs/005-acceptance-gates/prd.md:17` — Hard directive: update `src/deviate/prompts/commands/` and `src/deviate/prompts/auto/`.
  - `specs/005-acceptance-gates/prd.md:18` — Hard directive: update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit; append a `CHANGELOG.md` entry.
  - `specs/005-acceptance-gates/prd.md:164-175` — FR-005-06 acceptance outline: RED prompt states completion with warning; stale rejection statement fails review; CHANGELOG entry present.
  - `AGENTS.md` `📐 Spec Alignment` — both `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` must reflect CLI commands, phase workflows, and HITL gates in the same commit.
  - `AGENTS.md` `📝 Prompt Edit Discipline` — edit prompt templates in `src/deviate/prompts/` only; `~/.config/opencode/skills/` is a read-only install mirror and stays untouched.

## The Problem Contract

The gate behavior from issues `005-001` through `005-004` is implemented. This issue aligns the user-visible resources with that behavior: the RED, GREEN, and REFACTOR prompt templates must describe the checkpoint and gates exactly as the runners behave; the authoritative spec documents must reflect the new contracts and phase semantics; the changelog must record the user-visible change. Any stale statement that RED rejects a passing test, or that any phase passes an unchecked test result, fails review.

## Scope Boundaries

### Hard Inclusions

- `src/deviate/prompts/commands/deviate-red.md` states that RED completes on a passing test with a warning advisory.
- `src/deviate/prompts/auto/red.md`, `auto/green.md`, and `auto/refactor.md` describe the checkpoint and gates.
- `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` reflect the verification-mode contract, `acceptance_criteria` traceability, the `RedHandoffAdvisory` handoff, and the GREEN/REFACTOR gate semantics.
- `CHANGELOG.md` gains a bullet under `[Unreleased]` for the gate behavior changes.
- Tests pin the template content and detect stale rejection statements.

### Defensive Exclusions

- No new prompt template files; only the four existing templates are edited.
- No edits to `~/.config/opencode/skills/` (read-only install mirror) or any consumer-installed command directory.
- No flow-catalog work: `specs/_product/flows/`, `flows.jsonl`, and the flow index stay unchanged; `flow_refs: []` for this epic (no existing flow covers acceptance gates).
- No release scaffolding or workflow-ledger maintenance.
- No change to `src/deviate/cli/micro.py` runner behavior; the gates already landed in issues `005-003` and `005-004`.
- No change to `src/deviate/core/validation.py` or `src/deviate/core/tasks_ledger.py`; behavior landed in issues `005-001` and `005-002`.

## Upstream Requirement Tracing

- **FR-005-06**: Prompt Template and Specification Alignment
- **AC-005-06-01**: The RED prompt states the phase completes on a passing test with a warning; it no longer states rejection; happy path: templates and specs match runner behavior; error category: a stale rejection statement in any template fails review; boundary: CHANGELOG entry present under `[Unreleased]`.

## User Stories Ledger

- **US-005-11** (parent FR-005-06): As an agent running the RED phase, I read the prompt and know that a passing test completes the phase with a warning, so I never fight a stale rejection rule.
- **US-005-12** (parent FR-005-06): As a reviewer, I read `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` and find the gate semantics identical to the runner behavior, so the spec-alignment review passes.
- **US-005-13** (parent FR-005-06): As a changelog reader, I see the gate behavior changes under `[Unreleased]`, so the release notes state the behavior change.

## Acceptance Outline

- **AO-006** / `AC-005-06-01` / US-005-11: `src/deviate/prompts/commands/deviate-red.md` states that RED completes on a passing test with a warning advisory; no template in `src/deviate/prompts/auto/` states that RED rejects a passing test.
- **AO-006** / `AC-005-06-01` / US-005-12: `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` document the verification-mode contract, `acceptance_criteria` traceability, the `RedHandoffAdvisory` handoff, and the GREEN/REFACTOR gate semantics; no section contradicts the runner behavior.
- **AO-006** / `AC-005-06-01` / US-005-13: `CHANGELOG.md` carries a bullet under `[Unreleased]` describing the user-visible gate behavior changes.

## Edge Cases and Boundaries

- A stale rejection statement in any of the four templates fails the content checks.
- A template that omits the gate description entirely fails the content checks.
- The spec documents updated without the matching code commit fail the spec-alignment review; this issue lands after issues `005-001` through `005-004`.
- No flow matches the acceptance-gate domain in the existing catalog; `flow_refs` stays empty and no flow file is created.
- The `~/.config/opencode/skills/` install mirror must remain byte-identical before and after this issue.

## Performance Constraints

- No runtime performance impact: prompt and spec text changes only; no code paths change.
- Full test suite stays under 30 seconds (project execution contract).
- No new dependencies, external integrations, or database runtime.

## Multi-Tiered Verification Targets

- **Unit**: `tests/test_meso/test_auto_prompt_templates.py` — content checks on the red/green/refactor templates; reject stale rejection statements.
- **Static**: `grep` scans for forbidden phrases (see Demonstration Path).
- **Review**: spec-alignment review compares `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` against the runner behavior; changelog bullet presence checked.

## Demonstration Path

```bash
# 1. Template content checks — stale rejection statements must be absent
grep -rn "RED must author a failing test" src/deviate/prompts/commands/deviate-red.md src/deviate/prompts/auto/red.md
# expected: no match (or the phrase is rewritten to the checkpoint semantics)
grep -rn "**Verification Mode**" specs/DeviaTDD-api.md
# expected: at least one match documenting the contract line

# 2. Unit verification — prompt template content tests
uv run pytest tests/test_meso/test_auto_prompt_templates.py -v

# 3. Changelog discipline — bullet present under [Unreleased]
awk '/^## \[Unreleased\]/{f=1} f && /acceptance gate|Verification Mode|RED checkpoint|REFACTOR regression/{print; found=1} END{exit !found}' CHANGELOG.md

# 4. Install mirror untouched — no writes outside src/deviate/prompts/
git status --porcelain | grep -v "specs/005-acceptance-gates\|src/deviate/prompts/\|specs/DeviaTDD\|CHANGELOG.md"

# 5. Regression: full check bundle stays green
mise run check
```
