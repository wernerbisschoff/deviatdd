<lifecycle mode="auto">

**Orchestrator Lifecycle**: The CLI orchestrator handles ALL pre/post lifecycle for this phase. Do NOT run `deviate <phase> pre` or `deviate <phase> post` directly, and do NOT use `git add` / `git commit` directly. The orchestrator runs `deviate <phase> pre` before your response (the JSON contract becomes available context, with layer-specific fields listed in the per-phase template below) and runs `deviate <phase> post` after your response to validate and commit.

**HITL Gate Handoff**: After the orchestrator validates your output and returns status, terminate. Do NOT auto-advance to the next phase. The phase terminates at a HITL (Human In The Loop) gate — the human decides when to proceed.

</lifecycle>

<mandate>
STDOUT OUTPUT MANDATE: When the per-phase template defines a `<handover_manifest>` section, your final stdout response must be EXACTLY that YAML block. No conversational text, no analysis, no commentary, no markdown formatting, no file content on stdout. Write artifact files to their target paths only (not to stdout). The caller parses your stdout as raw YAML.
</mandate>