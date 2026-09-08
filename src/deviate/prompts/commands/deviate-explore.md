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

Manual mode: run the lifecycle scripts yourself — the orchestrator will not.

1. Run `deviate explore pre` to emit the JSON contract on stdout.
2. Do the explore work in the core body above, writing `explore.md` to `specs/explore/<slug>.md`.
3. Run `deviate explore post` after the scan completes.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>