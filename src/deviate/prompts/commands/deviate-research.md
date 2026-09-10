---
name: deviate-research
description: Architectural analysis — produce design.md (options, trade-offs, risk register) and data-model.md from explore.md.
category: deviatdd-macro-layer
version: 2.1.0
layer: macro
aliases:
  - /deviate-research
  - /research
  - spec:full:research
  - tools:research
---

## Manual Slash-Command Overlay

Manual mode: run the lifecycle scripts yourself — the orchestrator will not.

1. Run `deviate research pre --slug "<explore-slug>"` to verify the prerequisite phase and emit the JSON contract on stdout. When explore `NEXT_ACTION` / session is `attach_existing_epic`, pre **does not** allocate a new numbered bucket and **does not** move `explore.md` over the existing epic `explore.md`. If the contract has `attach_existing_epic=true`, halt — write the issue under `specs/{epic}/issues/` and reuse that epic's `prd.md`. Do not author a duplicate design/PRD. Otherwise pre moves `explore.md` into the new numbered epic bucket as usual.
2. If `is_greenfield=true` and `constitution_path` is empty, run `constitution_bootstrap` before the floor job.
3. Run `reduce_phase` to merge the architecture and data-model fragments into `<design_target>` and `<data_model_target>`.
4. Render the `html_artifact` review page when required.
5. Run `interactive_hitl_gate_1`: do not run the post-script until the human clears Gate 1.
6. Run `deviate research post`.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>