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

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/research.md` core — the single source of
truth for the RESEARCH instructions.

### Manual-Only Steps

The auto core covers the research analysis and adversarial audit. The manual
slash command adds these lifecycle steps around it:

1. Run `deviate research pre --slug "<explore-slug>"` to verify the
   prerequisite phase, move `explore.md` into the numbered epic bucket, and
   emit the JSON contract on stdout.
2. If `is_greenfield=true` and `constitution_path` is empty, run the
   `constitution_bootstrap` step to seed the constitution from exploration
   findings before the floor job.
3. Execute the research work described in the core body, writing
   `<design_target>` and `<data_model_target>`.
4. Run `reduce_phase` to merge the architecture and data-model fragments into
   the final artifacts.
5. Render the `html_artifact` review page when required.
6. Run `interactive_hitl_gate_1`: present the `## Pending HITL Decisions` rows
   to the human; do not proceed to the post-script until the human is
   satisfied (Gate 1).
7. Run `deviate research post` to validate the artifacts and create a single
   commit. Allocate a timeout of at least 180s (3 minutes): the post-script
   runs precommit hooks including the full test suite.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "RESEARCH"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>