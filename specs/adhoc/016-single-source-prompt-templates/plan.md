## Plan Summary

- **Issue**: ISS-ADH-016 — Single-Source Prompt Templates — Auto Canonical, Manual Derived at Install
- **Implementation Strategy**: Make `src/deviate/prompts/auto/{phase}.md` the single canonical middle body for each of the 11 overlapping phases. Rewire `install_command`/`compose_command_body` so the manual slash command derives its body from the auto core plus a per-phase manual overlay (frontmatter, pre/post-script lifecycle, rich handover manifest, `<context><user_input>`), then delete the duplicated middle bodies from `commands/deviate-{phase}.md`. Add a drift-guard test asserting the derived manual middle stays byte-identical to the auto core.
- **Estimated Complexity**: Medium
- **Estimated Effort**: 4-6 hours

## Product Layer Anchors

- **Flow References**: `[]`
- **Source**: `specs/adhoc/issues/016-single-source-prompt-templates.md` (frontmatter field: `flow_refs`)
- **Release Context**: N/A — `specs/_product/release-next.md` Goal targets FLOW-04 (Live-Stream Agent Progress via RPC), which does not cover prompt templating.
- **Architecture Components Touched**: C1 — `deviate` CLI (owns phase prompts and slash-command installation). No dedicated prompt-templating component exists in `specs/_product/architecture.md` §3; the change extends C1's prompt-derivation behavior without touching RPC components C2-C6.

## Acceptance Contract

**Scenario AC-PLAN-001: Derive the manual slash-command body from the canonical auto core plus the manual overlay without a hand-maintained duplicate**
- **Source Outline**: `AO-016`
- **Upstream Traceability**: `US-016-01`, `FR-ADHOC-016`, `AC-ADHOC-016-01`
- **Current-Code Evidence**: `src/deviate/core/commands.py:55-133` (`compose_command_body` prepends core/layer/lifecycle-manual/style to a hand-maintained `raw` body parsed from `commands/deviate-{phase}.md`); `src/deviate/core/commands.py:189-243` (`install_command` reads `commands/deviate-{phase}.md` source, composes, writes to the agent command dir)
- **Given**: `compose_command_body` receives the canonical `auto/{phase}.md` core body, the `core_dir`, and a per-phase manual overlay carrying the frontmatter, the manual pre/post-script lifecycle, and the rich handover manifest
- **When**: `install_command("deviate-red", target_dir)` runs against the canonical `auto/red.md`
- **Then**: the installed `deviate-red.md` contains the auto middle body unchanged, the platform frontmatter (`name`/`description` only), the manual lifecycle block, and the rich handover manifest — with no content sourced from a separate hand-maintained duplicate middle file
- **Verification Mode**: automated

**Scenario AC-PLAN-002: Reconcile the drifted manual middle to the auto RED and GREEN semantics**
- **Source Outline**: `AO-016`
- **Upstream Traceability**: `US-016-02`, `FR-ADHOC-016`, `AC-ADHOC-016-02`
- **Current-Code Evidence**: `src/deviate/prompts/commands/deviate-red.md:69` (emits `status: "FAIL"` in the handover manifest); `src/deviate/prompts/auto/red.md:126` (declare "Use `PASS` ... NEVER use `FAIL`"); `src/deviate/prompts/auto/green.md:90` ("Write ONLY production code") vs `src/deviate/prompts/commands/deviate-green.md:109` ("Maintain existing functional signatures")
- **Given**: the shared middle body is reconciled to the auto semantics for all 11 overlapping phases
- **When**: the derived manual `deviate-red.md` and `deviate-green.md` are produced from their canonical auto cores
- **Then**: the derived RED no longer emits `status: "FAIL"` or instructs abort-on-passing-test, the derived GREEN instructs "write ONLY production code", and no contradictory role instruction or handover status remains in either derived body
- **Verification Mode**: automated

**Scenario AC-PLAN-003: Enforce the identical-middle invariant with a drift guard**
- **Source Outline**: `AO-016`
- **Upstream Traceability**: `US-016-03`, `FR-ADHOC-016`, `AC-ADHOC-016-03`
- **Current-Code Evidence**: `tests/unit/test_meso/test_auto_prompt_templates.py:58-61` (`test_composed_template_has_context_marker` currently pins composition markers for slim templates only); `src/deviate/prompts/auto/red.md` vs `src/deviate/prompts/commands/deviate-red.md` (representative drift pair 17-68% divergence)
- **Given**: a drift-guard test invokes `install_command` against a `tmp_path` so the installed `deviate-{phase}.md` exists on disk
- **When**: the test compares the installed manual middle body against the canonical `auto/{phase}.md` middle body
- **Then**: the two middle bodies are byte-identical for every one of the 11 overlapping phases, and the test fails with a diff when an unrelated line is added to an auto middle body
- **Verification Mode**: automated

**Scenario AC-PLAN-004: Preserve the on-disk idempotency contract and the auto-only core emission of `load_template`**
- **Source Outline**: `AO-016`
- **Upstream Traceability**: `US-016-01`, `FR-ADHOC-016`, `AC-ADHOC-016-01`
- **Current-Code Evidence**: `src/deviate/core/commands.py:239-240` (`if target_path.exists() and target_path.read_text(...) == composed: return False` idempotency); `src/deviate/prompts/assembly.py:48-107` (`load_template` emits core + layer + lifecycle-auto + style + phase)
- **Given**: `install_command` derived a command body and wrote it to the target path
- **When**: `install_command` runs again with the same canonical templates and no file change to the target
- **Then**: `install_command` returns `False`, the target file is unchanged, and `load_template` still emits the auto core body with no manual-overlay leakage
- **Verification Mode**: automated

## Workstation Mapping

- `src/deviate/prompts/auto/red.md`: Canonical per-phase source for the RED phase. The drifted middle is reconciled to the auto semantics (`status: "PASS"` + `failure_kind`); this file remains the single source of truth for the middle body. The current file already implements the auto semantics — the manual derivation must stop contradicting it.
  - **Current State**: Contains the canonical auto RED body with `status: "PASS"` + `failure_kind` discriminator routing to JUDGE. Lacks the manual overlay content.
  - **Changes Required**: None for the middle body semantics (already canonical). It becomes the derivation input for the manual RED slash command.
  - **Integration Surface**: Consumed by `load_template` (auto path) and by the reworked `compose_command_body`/`install_command` (manual derivation path).
- `src/deviate/prompts/auto/green.md`: Canonical per-phase source for GREEN. The middle body's role language ("write ONLY production code") stays canonical; the manual derivation must no longer contradict it.
  - **Current State**: Contains canonical auto GREEN body with "write ONLY production code", "Maintain existing functional signatures" at line 65, and the scope-boundary / ORCHESTRATOR LIFECYCLE content.
  - **Changes Required**: None to the canonical middle — it is the single source of truth that the manual overlay no longer overrides.
  - **Integration Surface**: Consumed by `load_template` and the manual derivation path.
- `src/deviate/core/commands.py`: The rewrite target for the derivation mechanism. `compose_command_body` (lines 55-133) and `install_command` (lines 189-243) are reworked so the manual slash-command body derives from `auto/{phase}.md` + a per-phase manual overlay instead of a hand-maintained duplicate.
  - **Current State**: `compose_command_body` prepends core/layer/lifecycle-manual/style around a `raw` body read from `commands/deviate-{phase}.md`. `install_command` resolves the source in `commands/`, composes, strips frontmatter, and writes idempotently to the agent command dir.
  - **Changes Required**: Route the canonical middle from `auto/{phase}.md`; splice the per-phase manual overlay (frontmatter, manual pre/post-script lifecycle, rich handover manifest, `<context><user_input>`) around it; keep the constitution injection and graphite routing (for `deviate-pr`) intact; keep the idempotency contract.
  - **Integration Surface**: Called by `deviate setup` (via `discover_commands` iteration) and by tests in `tests/unit/test_core/test_commands.py`.
- `src/deviate/prompts/commands/deviate-{phase}.md` (11 files: red, green, refactor, judge, execute, plan, tasks, explore, research, prd, shard): The stale manual duplicates. The duplicated middle bodies are deleted; only the frontmatter + manual overlay (pre/post-script steps, rich handover manifest, `<context><user_input>`, per-phase manual-only steps) remain as the overlay applied at derivation.
  - **Current State**: Hand-maintained copies that diverge from auto by 17-68% (contradictory RED handover status, GREEN role language, field-name drift `plan_target` vs `{plan_path}`, `T001` vs `TSK-{NNN}-{NN}`).
  - **Changes Required**: Delete the duplicated middle bodies. Retain only the frontmatter block and the manual-only overlay content that must not leak into the auto core.
  - **Integration Surface**: The overlay is consumed by the reworked `install_command`/`compose_command_body`; the frontmatter `name`/`description`/`layer` drives the platform frontmatter emitted on install.
- `src/deviate/prompts/assembly.py`: Keeps `load_template` emitting the auto core body only — no behavior change to the auto path.
  - **Current State**: Composes core + layer + lifecycle-auto + style + phase for the auto runner; `_LAYER_MAP` routes each phase to its shared preamble.
  - **Changes Required**: None functionally — the auto path stays the canonical emitter. Confirm no manual-overlay content leaks in.
  - **Integration Surface**: `load_template` and `assemble_prompt` are consumed by the micro runner and the CLI.
- `tests/unit/test_core/test_commands.py`: Reworked to assert the derived-manual output and the idempotency contract against the new derivation.
  - **Current State**: Asserts `install_command`/`compose_command_body` against the hand-maintained `commands/` source, graphite routing for `deviate-pr`, platform frontmatter, constitution injection, product-layer lifecycle routing.
  - **Changes Required**: Update `install_command`/`compose_command_body` assertions to the derived-manual output (middle equals auto core + overlay). Add a drift-guard asserting the derived manual equals the committed manual behavior and the middle stays identical across modes.
  - **Integration Surface**: Directly imports `compose_command_body`, `install_command`, `discover_commands`, `resolve_command` from `deviate.core.commands`.
- `tests/unit/test_meso/test_auto_prompt_templates.py`: Extended with the drift-guard and auto-semantics pinning coverage.
  - **Current State**: Pins slim-template existence, composition markers, consumer-repository boundaries, product-flow boundaries.
  - **Changes Required**: Add `test_auto_and_manual_middle_identical` (drift guard over the 11 overlapping phases), `test_auto_red_uses_pass_failure_kind`, `test_manual_red_matches_auto_semantics`.
  - **Integration Surface**: Reads `deviate.prompts.auto` and `deviate.prompts.commands` resources via `importlib.resources`.
- `tests/unit/test_meso/test_prompt_assembly.py`: Verifies `load_template` still emits the auto core body only.
  - **Current State**: Covers `load_template` success/missing, `inject_constitution` injection/missing.
  - **Changes Required**: Add a composition test asserting no manual-overlay leakage into the auto core body.
  - **Integration Surface**: Imports `load_template` and `inject_constitution` from `deviate.prompts.assembly`.
- `CHANGELOG.md`: Records the user-visible template-derivation change.
  - **Current State**: Existing `[Unreleased]` backlog.
  - **Changes Required**: Append a bullet under `[Unreleased]` describing the single-source prompt derivation and the manual-mid reconciliation.
  - **Integration Surface**: Human-readable changelog consumed at release.
- `specs/DeviaTDD-api.md`: Reflects the single-source prompt architecture.
  - **Current State**: Documents the CLI phase workflows and model routing.
  - **Changes Required**: Document the auto-canonical / manual-derived prompt architecture and the derivation mechanism.
  - **Integration Surface**: Authoritative CLI/spec reference mirroring the implementation in the same commit (spec-alignment mandate).
- `specs/DeviaTDD-architecture.md`: Reflects the single-source prompt architecture.
  - **Current State**: Documents the three-layer architecture and phase model.
  - **Changes Required**: Document the single-source prompt derivation and the deletion of the duplicated manual middle bodies.
  - **Integration Surface**: Authoritative architecture reference mirroring the implementation in the same commit.

## Implementation Strategy

- **Phase 1**: Isolate the derivation mechanism and manually reconcile the drifted middles.
  - **Files**: `src/deviate/core/commands.py`, `src/deviate/prompts/commands/deviate-{red,green,refactor,judge,execute,plan,tasks,explore,research,prd,shard}.md`
  - **Approach**: For each of the 11 overlapping phases, diff the auto core against the manual file, reconcile the manual middle to the auto semantics (RED `status: "PASS"` + `failure_kind`, GREEN "write ONLY production code"), and reduce the manual file to its frontmatter + manual-only overlay (pre/post-script steps, rich handover manifest, `<context><user_input>`, per-phase manual-only steps such as `reduce_phase`/`interactive_hitl_gate_1`/`html_artifact` for research). Add a deterministic `_manual_phase_mapping` that routes each phase to its auto core file. Splice the overlay deterministically — no LLM or `prompt` content generation.
  - **Verification**: `mise run test tests/unit/test_meso/test_prompt_assembly.py` and manual review of the reduced manual files.
- **Phase 2**: Rewire `install_command`/`compose_command_body` to derive from the canonical auto core + overlay.
  - **Files**: `src/deviate/core/commands.py`, `src/deviate/prompts/assembly.py`
  - **Approach**: Rework `compose_command_body` to take the auto core body and the manual overlay instead of a raw hand-maintained duplicate. Keep the constitution injection, the product-layer lifecycle branch, the platform frontmatter emission, and the graphite routing for `deviate-pr`. Preserve the idempotency contract (`False` on unchanged reinstall).
  - **Verification**: `mise run test tests/unit/test_core/test_commands.py`.
- **Phase 3**: Add the drift-guard and auto-semantics pinning tests.
  - **Files**: `tests/unit/test_core/test_commands.py`, `tests/unit/test_meso/test_auto_prompt_templates.py`
  - **Approach**: Add `test_auto_and_manual_middle_identical` asserting the installed derived middle equals the auto core byte-for-byte across all 11 phases; `test_auto_red_uses_pass_failure_kind` and `test_manual_red_matches_auto_semantics` asserting the derived RED no longer emits `status: "FAIL"`/abort-on-passing-test. Mock nothing — tests read the two source files and invoke `install_command` against a `tmp_path` (no `deviate.cli.micro._run_pytest` subprocess).
  - **Verification**: `mise run test tests/unit/test_meso/test_auto_prompt_templates.py` with a deliberate auto-middle edit to confirm the guard fails.
- **Phase 4**: Update documentation, specs, and changelog; full suite.
  - **Files**: `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md`
  - **Approach**: Append the `[Unreleased]` changelog bullet for the user-visible derivation change; reflect the single-source prompt architecture and derivation mechanism in both spec documents in the same commit.
  - **Verification**: `mise run check`, `mise run lint`, `mise run format-check`, `mise run test`.

## Data Flow Analysis

- **Input**: The canonical per-phase body at `src/deviate/prompts/auto/{phase}.md`, the shared core preambles (`core/core.md`, `core/{layer}-shared.md`, `core/style-ste.md`), the manual lifecycle block (`core/lifecycle-manual.md`), and the per-phase manual overlay (frontmatter + manual-only steps) extracted from the reduced `commands/deviate-{phase}.md`.
- **Transformation**: `compose_command_body` splices the manual overlay around the auto core: it prepends constitution (optional), universal core, layer-shared preamble, lifecycle-manual block, and style, then appends the phase body. The derived manual middle equals the auto core; only the lifecycle start/end, the contract-input substitution, and the rich handover manifest differ.
- **Output**: The on-disk derived slash-command at `<workdir>/.<agent>/commands/deviate-{phase}.md`, with platform frontmatter (`name`/`description` only, internal `layer`/`category` stripped) and no hand-maintained duplicate middle.
- **Storage**: No persistent ledger model introduced; state remains files on disk written by `deviate setup` idempotently (`False` when the target already matches the composed output).
- **Terminal**: `deviate setup` reads the canonical resources from the installed package and writes the derived commands to the consumer's agent command directories. Divergence in the auto middle fails the drift-guard test before release.

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Field-name and structural drift between auto and manual per phase (plan `{plan_path}` vs `plan_target`; tasks `TSK-{NNN}-{NN}` vs `T001`; research manual-only steps) | Medium | High | Reconcile each pair per-phase before deriving — resolve to the runner-enforced format (`TSK-\d{3}-\d{2}` per `src/deviate/cli/meso.py:938`, `src/deviate/core/validation.py:260`); do not uniform-inject structure across phases. |
| Manual-overlay content leaks into the auto core and changes auto-runner behavior | High | Medium | `load_template` keeps emitting the auto core body only; add a `test_prompt_assembly.py` assertion that no overlay markers appear in the auto composition. |
| `deviate setup` install idempotency contract regresses (returns `True` on unchanged reinstall) | Medium | Medium | Keep `target_path == composed` short-circuit returning `False`; re-run the graphite idempotency suite in `tests/unit/test_core/test_commands.py`. |
| Greenfield `specs/constitution.md` absence breaks derivation | Medium | Low | Keep constitution injection best-effort and non-fatal (current `OSError`-tolerant path in `install_command`). |
| Drift-guard test invokes `deviate.cli.micro._run_pytest` and slows the suite past 30s | Medium | Medium | The drift guard reads the two source files and calls `install_command` against a `tmp_path` only — no subprocess, per the AGENTS.md performance mandate. |
| FLOW_CONTEXT_UNAVAILABLE — no existing flow mapping covers prompt templating | Medium | Low | Preserve empty flow references and plan the application's requested single-source derivation behavior without creating flow or DeviaTDD setup work. |

## Security Profile

Risk surfaces: file paths (derivation reads canonical resources and writes derived commands to the agent command dir), local filesystem I/O only. No auth, no secrets, no PII, no outbound HTTP, no deserialization, no subprocess, no eval. The derivation is deterministic static string composition — no LLM or `prompt`-backed content generation.

Negative tests: the drift-guard test fails when a divergent middle body is introduced (an unrelated line added to an auto middle fails `test_auto_and_manual_middle_identical`); the derived manual RED must not leak `status: "FAIL"` or abort-on-passing-test; `load_template` must not leak manual-overlay markers into the auto core.

Constraints: no new dependencies without checksum; no hardcoded secrets; no LLM content generation during derivation; no tests invoking `deviate.cli.micro._run_pytest` without mocking it; do not modify `core/{layer}-shared.md`, `core/core.md`, or `core/style-ste.md`; do not touch consumer-installed command directories (`~/.config/opencode/skills/` or `<workdir>/.<agent>/commands/`).

## Integration Points

- **`deviate setup`**: Iterates `discover_commands` over the package `commands/` root and calls `install_command` for each found name; expected to install the derived slash commands to every agent platform's command dir.
- **`deviate.prompts.assembly.load_template`**: Auto path stays canonical — emits core + layer + lifecycle-auto + style + phase; the manual path must not alter its output.
- **`deviate.core.commands.compose_command_body` / `install_command`**: The rewritten derivation entry points; they consume the canonical auto core and the per-phase manual overlay.
- **`src/deviate/cli/micro.py:211`**: RED task state sourced from `tasks.jsonl` — the derived RED prompt must match auto's ledger-authoritative wording.
- **`src/deviate/cli/meso.py:938` / `src/deviate/core/validation.py:260`**: `TSK-\d{3}-\d{2}` task-id validator — the derived tasks prompt must use the auto format, not the manual `T001`.

## Constitutional Alignment

- **Architecture**: Aligns with the three-layer model — prompt derivation is Meso/Micro application behavior; the middle body is the single source of truth, with auto as the living behavior for the micro layer. No layer is skipped.
- **Testing**: pytest under `tests/` with ruff lint/format; the drift-guard and auto-semantics tests run through `mise run test`. Coverage target >= 80% retained; GREEN phase writes only to the allow-listed prompt/command/tests paths.
- **Git Isolation**: All work happens on the dedicated issue branch in this worktree; commits use conventional format referencing the task id; no branch-mutating git commands run from the micro layer.
- **Product Layer**: `flow_refs: []` — no existing user-visible flow covers prompt templating. The implemented application behavior (single-source prompt derivation, reconciled manual middles, drift guard) preserves the existing flows named in `## Product Layer Anchors` (none) and introduces no flow-catalog, release, or DeviaTDD-setup deliverable. It extends C1 (the `deviate` CLI) only.
