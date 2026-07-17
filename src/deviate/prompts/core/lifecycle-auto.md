<lifecycle mode="auto">

**Orchestrator Lifecycle**: The CLI orchestrator handles ALL pre/post lifecycle for this phase — it injects context, stages files, runs pre-commit hooks (lint, format-check, tests), updates the task ledger, and commits. Do NOT run `deviate <phase> pre` or `deviate <phase> post` directly, and do NOT use `git add` / `git commit` directly. The orchestrator runs `deviate <phase> pre` before your response (the JSON contract becomes available context, with layer-specific fields listed in the per-phase template below) and runs `deviate <phase> post` after your response to validate and commit.

**HITL Gate Handoff**: After the orchestrator validates your output and returns status, terminate. Do NOT auto-advance to the next phase. The phase terminates at a HITL (Human In The Loop) gate — the human decides when to proceed.

</lifecycle>