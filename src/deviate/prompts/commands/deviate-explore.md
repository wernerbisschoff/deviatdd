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
2. Do the explore work in the core body above, deriving `<slug>` from the content semantics (never a filename) and writing `explore.md` to `specs/explore/<slug>.md`.
3. Run `deviate explore post` after the scan completes.

Human routing override (optional, from `<user_input>`): `attach <epic-slug>`, `new epic`, or `adhoc`. Write it into Status Summary `HITL_OVERRIDE` (and `ATTACH_EPIC` when attaching). A `## Pending HITL Decisions` row with Status `PENDING` / `RESOLVED` also works. This is process routing, not an architecture recommendation.

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>