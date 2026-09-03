---
title: "Single-Source Prompt Templates — Auto Canonical, Manual Derived at Install"
labels: [refactor, adhoc, vertical-slice, prompts, single-source]
blocked_by: []
coordinates_with: ["ISS-ADH-013"]
issue_id: ISS-ADH-016
flow_refs: []
---

## System Topology Mapping

- **Epic Target Domain**: `specs/adhoc/`
- **Local Issue File**: `specs/adhoc/issues/016-single-source-prompt-templates.md`
- **Primary Architectural Workstations**:
  - `src/deviate/prompts/assembly.py:48-107` — TARGET: `load_template` composes the auto prompt from `core/core.md` + `core/{layer}-shared.md` + `core/lifecycle-auto.md` + `core/style-ste.md` + `auto/{phase}.md`. The canonical per-phase body already lives in `auto/`; `load_template` is the auto derivation path and must keep emitting the core body only.
  - `src/deviate/core/commands.py:55-133` — TARGET: `compose_command_body` prepends core/layer/lifecycle-manual/style to a manual command body. This is the manual derivation path. Rewire so the manual slash-command body is derived from the canonical `auto/{phase}.md` + a per-phase manual overlay instead of a hand-maintained duplicate file.
  - `src/deviate/core/commands.py:189-243` — TARGET: `install_command` reads `commands/deviate-{phase}.md` source, composes, and writes to the agent command dir. Must instead read the canonical `auto/{phase}.md` and derive the manual body.
  - `src/deviate/prompts/auto/{red,green,refactor,judge,execute,plan,tasks,explore,research,prd,shard}.md` — CANONICAL SOURCE: the 11 overlapping phase bodies. These hold the single source of truth; reconcile the drifted middle to the auto semantics.
  - `src/deviate/prompts/commands/deviate-{red,green,refactor,judge,execute,plan,tasks,explore,research,prd,shard}.md` — STALE DUPLICATES: hand-maintained manual copies that drift from auto (17-68% identical-line rate). Their manual-only content (pre/post-script steps, rich handover manifest, `<context><user_input>`) becomes a derivation overlay; the duplicated middle body is removed from these files.
  - `src/deviate/prompts/core/lifecycle-auto.md` — REFERENCE: the auto lifecycle block ("orchestrator handles all lifecycle").
  - `src/deviate/prompts/core/lifecycle-manual.md` — REFERENCE: the manual lifecycle block ("run `deviate <phase> pre/post`").
  - `tests/unit/test_meso/test_auto_prompt_templates.py` — TARGET: pin canonical auto semantics; add drift-guard coverage.
  - `tests/unit/test_meso/test_prompt_assembly.py` — TARGET: verify auto composition still emits core only.
  - `tests/unit/test_core/test_commands.py` — TARGET: rework `install_command`/`compose_command_body` assertions to the derived-manual output; add a drift-guard asserting the derived manual equals the committed behavior and the middle stays identical across modes.
  - `CHANGELOG.md` — TARGET: append a bullet under `[Unreleased]` for the user-visible template-derivation change.
  - `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md` — TARGET: reflect the single-source prompt architecture and the derivation mechanism (spec-alignment mandate).
- **Upstream Evidence**:
  - Git `420f65f` (2026-08-18) — redesigned auto/red only: `status:"PASS"` + `failure_kind` discriminator routed to JUDGE; the manual `status:"FAIL"` never back-ported. Proves auto is the living behavior.
  - Git `64f9957` — per-epic issue-id change landed on `deviate-shard.md` only; auto/shard retained global ISS-NNN.
  - `src/deviate/cli/micro.py:211` — RED task state sourced from `tasks.jsonl` (`status == "PENDING"`), confirming ledger-authoritative wording.
  - `src/deviate/cli/meso.py:938`, `src/deviate/core/validation.py:260` — task-id validator enforces `TSK-\d{3}-\d{2}`, confirming the auto format over the manual's `T001`.
  - `src/deviate/prompts/commands/deviate-red.md` vs `src/deviate/prompts/auto/red.md` — representative pair showing the drift.

## The Problem Contract

DeviaTDD maintains two parallel prompt copies per phase (`auto/<phase>.md` for the CLI-orchestrated micro runner, `commands/deviate-<phase>.md` for manual slash commands). A drift audit found the copies disagree on 17%-68% of lines, including contradictory handover manifests (RED `status:"PASS"` vs `status:"FAIL"`) and contradictory role instructions (GREEN "write only production code" vs "maintain existing functional signatures"). The intended design is a shared middle body with only start/end lifecycle differing, but the copies have diverged badly because contributors edit both by hand. The micro runner is the only path the operator runs (manual phases are long-unused), so **auto is the living behavior**. This issue makes `auto/<phase>.md` the single canonical body, derives the manual slash-command from it at install time, reconciles the drifted middle to auto semantics, deletes the duplicated manual bodies, and adds a drift guard so the middle can never diverge again.

## Scope Boundaries

### Hard Inclusions
- **Auto is canonical** for all 11 overlapping phases. Reconcile each pair's drifted middle to the auto semantics. GREEN role language resolves to auto: "write ONLY production code (minimal change so that RED works)" — not "maintain existing functional signatures".
- Rewire `install_command`/`compose_command_body` so the manual slash-command body is derived from `auto/{phase}.md` + a per-phase manual overlay (pre/post-script lifecycle steps, rich handover manifest, `<context><user_input>` block), not from a hand-maintained duplicate.
- `load_template` keeps emitting the auto core body only (unchanged middle).
- Delete the 11 duplicated middle bodies from `commands/deviate-{phase}.md` (the overlapping set). Retain only the frontmatter + manual overlay, or remove the files if the overlay lives elsewhere.
- Add a drift-guard test asserting: (a) the derived manual command equals the committed manual behavior, and (b) the shared middle body is identical between auto and manual composition.
- Update `specs/DeviaTDD-api.md` and `specs/DeviaTDD-architecture.md` in the same commit (spec-alignment mandate).
- Append a `CHANGELOG.md` `[Unreleased]` bullet for the user-visible template-derivation change.

### Defensive Exclusions
- Do NOT change the 15 commands-only prompts (adhoc, architecture, constitution, e2e, flows, hotfix, html, init, merge, pr, prune, release, review, triage, walkthrough). They have no auto counterpart and stay hand-maintained.
- Do NOT change the micro-runner behavior in `src/deviate/cli/micro.py` — the runner already consumes `auto/` templates.
- Do NOT modify `core/{layer}-shared.md`, `core/core.md`, or `core/style-ste.md` shared preambles.
- Do NOT regenerate `specs/_product/` flow artifacts; `flow_refs: []` (no existing flow covers prompt templating).
- Do NOT touch `~/.config/opencode/skills/` or any consumer-installed command directory (read-only install mirrors).
- Do NOT upgrade the product/governance command bodies or Graphite integration.
- Do NOT add tests that invoke `deviate.cli.micro._run_pytest` without mocking it (AGENTS.md test-performance mandate).
- Do NOT add `prompt`- or LLM-backed content generation during derivation — the manual overlay is static text, deterministic string composition only.

## Upstream Requirement Tracing

- **Requirements Tokens**: `FR-ADHOC-016`
- **Acceptance Criteria Tokens**: `AC-ADHOC-016-01` through `AC-ADHOC-016-04`
- **Data Model Entities**: none (no new persistent ledger models)
- **Spec Source Anchors**:
  - `specs/constitution.md:10` — Append-Only Ledger Protocol (unaffected)
  - `src/deviate/cli/micro.py:211` — RED task state sourced from `tasks.jsonl`
  - `src/deviate/cli/meso.py:938`, `src/deviate/core/validation.py:260` — `TSK-\d{3}-\d{2}` task-id validator

## User Stories Ledger

- **US-016-01**: As a DeviaTDD maintainer, I want a single canonical per-phase prompt body (auto) with the manual slash-command derived at install time, so I edit the middle body once instead of maintaining two drift-prone copies. *(Ref: FR-ADHOC-016)*
- **US-016-02**: As a DeviaTDD maintainer, I want the drifted middle reconciled to auto semantics (including GREEN "write only production code" and the PASS/failure_kind RED handover), so both modes no longer instruct contradictory behavior. *(Ref: FR-ADHOC-016)*
- **US-016-03**: As a DeviaTDD maintainer, I want a drift-guard test that fails when the auto and manual middle bodies diverge, so the identical-middle invariant is enforced rather than trusted. *(Ref: FR-ADHOC-016)*

## Acceptance Outline

- **AO-016** *(Ref: AC-ADHOC-016-01, US-016-01)*: For every one of the 11 overlapping phases, `install_command` derives the manual slash-command body from `auto/{phase}.md` plus the manual overlay, with a middle body identical to the auto core.
  - **Happy Path**: `deviate setup` produces a `deviate-{phase}.md` whose middle (role, mandates, execution steps, edge cases) matches `auto/{phase}.md`; only the lifecycle start/end (pre/post scripts), the contract-input substitution, and the rich handover manifest differ.
  - **Error Category**: A phase pair whose middle diverges fails the drift-guard test with a diff.
  - **Boundary Category**: The derivation composes static text deterministically; no LLM or `prompt` content generation.
- **AO-016** *(Ref: AC-ADHOC-016-02)*: The drifted middle is reconciled to auto semantics.
  - **Happy Path**: RED manual no longer states `status:"FAIL"`/abort-on-passing-test; it matches auto's `status:"PASS"` + `failure_kind`. GREEN manual matches auto's "write only production code".
  - **Error Category**: Any residual contradictory role instruction or handover status fails review.
- **AO-016** *(Ref: AC-ADHOC-016-03)*: The drift-guard test exists and fails on divergence.
  - **Happy Path**: Adding an unrelated line to an auto middle body makes the drift-guard test fail until the manual derivation is updated.
  - **Boundary Category**: The 15 commands-only prompts are exempt from the identical-middle invariant.

## Edge Cases and Boundaries

- **Manual-only phase steps**: The manual overlay (pre/post-script, rich manifest, `<context><user_input>`) must live outside the shared middle so it does not leak into the auto core.
- **Meso/macro structural divergence**: plan/tasks use `<step>` structure in auto but numbered steps in manual; research manual has `reduce_phase`/`interactive_hitl_gate_1`/`constitution_bootstrap`/`html_artifact` steps auto lacks. Reconcile per-phase before deriving — do not uniform-inject.
- **Field-name drift**: plan auto `{plan_path}` vs manual `plan_target`; tasks auto `TSK-{NNN}-{NN}` vs manual `T001`. Resolve to the runner-enforced format (`TSK-\d{3}-\d{2}` per `meso.py:938`).
- **Command-only frontmatter**: the manual files carry `name`/`description`/`layer` frontmatter the auto files lack. Preserve frontmatter in the derived manual output.
- **Idempotent install**: `install_command` must return `False` when the on-disk derived command already matches, preserving the existing idempotency contract (`test_install...` graphite suite).
- **Greenfield constitution absence**: derivation must tolerate a missing `specs/constitution.md` exactly as today (non-fatal).

## Performance Constraints

- **L_max (`deviate setup` install)**: ≤ 500ms above existing `deviate setup` init (matches AGENTS.md L_max ≤ 500ms init gate). Derivation is deterministic string composition — no I/O beyond reading the canonical template and writing the derived command.
- **Full test suite**: `mise run test` remains < 30s per AGENTS.md performance mandate. New drift-guard test must read the two source files + invoke `install_command` against a `tmp_path` (no `_run_pytest`).
- **File size impact**: net reduction — the 11 duplicated middle bodies (each 5-30KB) shrink to overlays.

## Multi-Tiered Verification Targets

- **Unit Sandbox Targets**:
  - `tests/unit/test_core/test_commands.py` — rework `install_command`/`compose_command_body` tests to assert the *derived* manual output (middle equals auto core + overlay), and that the on-disk idempotency contract (`False` on unchanged reinstall) still holds.
  - `tests/unit/test_meso/test_auto_prompt_templates.py` — extend with: `test_auto_and_manual_middle_identical` (drift guard) asserting the shared middle body is byte-identical between the auto core and the derived manual; `test_auto_red_uses_pass_failure_kind` asserting auto red's `failure_kind` semantics; `test_manual_red_matches_auto_semantics` asserting the derived red no longer emits `status:"FAIL"`/abort-on-passing-test.
  - `tests/unit/test_meso/test_prompt_assembly.py` — verify `load_template` still emits the auto core body only (core + layer + lifecycle-auto + style + phase), no manual overlay leakage.
- **Integration Sandbox Targets**:
  - `tests/cli/test_setup.py` (if present) — verify `deviate setup` installs a derived `deviate-red.md` matching the expected composed body.
  - `tests/e2e/` (bats) — optional smoke test: run install, assert derived manual middle equals auto core.

## Demonstration Path
```bash
# 1. Run the drift audit on the current pair (before migration requires auto canonical)
diff <(tr -s ' \n' < src/deviate/prompts/auto/red.md) \
     <(sed '1,/^---$/d' src/deviate/prompts/commands/deviate-red.md | tr -s ' \n') | head

# 2. After wiring, prove the derived manual middle equals the auto core
uv run python -c "
from deviate.core.commands import install_command
import tempfile, pathlib
d = tempfile.mkdtemp()
install_command('deviate-red', pathlib.Path(d))
print((pathlib.Path(d)/'deviate-red.md').exists())
"

# 3. Run the drift-guard and loader tests
mise run test tests/unit/test_core/test_commands.py -v
mise run test tests/unit/test_meso/test_auto_prompt_templates.py -v
mise run test tests/unit/test_meso/test_prompt_assembly.py -v

# 4. Lint and format
mise run lint
mise run format-check

# 5. Full suite
mise run test
```
