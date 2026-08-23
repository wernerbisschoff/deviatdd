---
name: deviate-explore
description: Read-only structural scan of the codebase; emits raw explore.md (what exists, not what to do).
category: deviatdd-macro-layer
version: 2.0.0
layer: macro
aliases:
  - /deviate-explore
  - /explore
  - spec:full:explore
---

## Manual Slash-Command Overlay

This command runs as a manual slash command. The CLI orchestrator does not
run lifecycle hooks; you run the scripts yourself. The middle body above is
derived from the canonical `auto/explore.md` core — the single source of
truth for the EXPLORE instructions.

1. Run `deviate explore pre` to emit the JSON contract on stdout.
2. Execute the explore (read-only structural scan) work described in the core
   body, writing `explore.md` to `specs/explore/<slug>.md`.
3. Run `deviate explore post` after the scan completes. The command validates
   the sections, updates the flow ledger, and commits.

### Rich Handover Manifest

Emit the handover manifest as a single YAML block delimited by ```yaml and
```. All string values are double-quoted.

```yaml
phase: "EXPLORE"
status: "PASS"
task_id: "{TASK_ID}"
```

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>