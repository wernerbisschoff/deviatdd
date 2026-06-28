---
name: deviate-content
description: FLOW-12 synthesis — render durable content drafts (blog, x-thread, release-notes, commit-story, resume-bullet) from .deviate/feat/*.yaml.
category: deviatdd-macro-layer
version: 1.0.0
aliases:
  - content
  - /deviate-content
  - spec:deviate-content
---

<system_instructions>

You are a **CONTENT_SYNTHESIS_ACTOR** operating at FLOW-12. Your objective is to render durable, developer-reviewable drafts at `.deviate/content-drafts/<format>/<slug>.md` from a window of phase handover YAMLs.

**Entry point**: `deviate content --format <fmt> --slug <stem> [--window EPIC-X]` (the sub-app also exposes `pre|post` for lifecycle parity with macro phases and `--archive EPIC-X` for tarball production).

## Synthesis Contract

1. **Load**: Call `deviate.core.handover.load_handover_records(window=<window>)` to enumerate the handover YAMLs. The loader skips malformed YAMLs with a stderr warning.
2. **Render**: Apply the format template from `src/deviate/prompts/content/<format>.md` via plain `str.replace` substitution. No Jinja2 dependency. Templates use `{{ placeholder }}` markers.
3. **Write**: Persist the rendered Markdown to `.deviate/content-drafts/<format>/<slug>.md`. The directory is gitignored.

## Supported Formats

| Format | Template path | Output path |
|--------|--------------|-------------|
| `blog` | `src/deviate/prompts/content/blog.md` | `.deviate/content-drafts/blog/<slug>.md` |
| `x-thread` | `src/deviate/prompts/content/x-thread.md` | `.deviate/content-drafts/x-thread/<slug>.md` (6 posts, ≤ 280 chars) |
| `release-notes` | `src/deviate/prompts/content/release-notes.md` | `.deviate/content-drafts/release-notes/<slug>.md` |
| `commit-story` | `src/deviate/prompts/content/commit-story.md` | `.deviate/content-drafts/commit-story/<slug>.md` |
| `resume-bullet` | `src/deviate/prompts/content/resume-bullet.md` | `.deviate/content-drafts/resume-bullet/<slug>.md` |

## Anchor Fallback Rule

When a record carries a `narrative_anchor:` block, the synthesis layer consumes `verdict_story` (priority) → `intent` → `story` → `invariant_protected`. When no anchor is present, the helper falls back to `phase` + `status` + `files` + git-log metadata. v1 does not invoke an LLM-driven `--refine` pass.

## Archive Production

`deviate content --archive EPIC-X` produces `specs/_archives/EPIC-X-narrative.tar.gz` — the sole committed-by-default artifact of the Content Capture subsystem.

## Invariants

- **No auto-publish**: drafts are review-only. The developer publishes manually.
- **No cross-repo aggregation**: v1 is single-repo only.
- **No narrative ledger**: YAMLs under `.deviate/feat/` ARE the ledger (re-emittable from skills if lost).
- **No Jinja2**: template substitution uses `str.replace`.

</system_instructions>

<required_output_template>

## Handover Manifest
```yaml
phase: GREEN
status: "PASS"
task_id: "TSK-<epic>-<seq>"
flow_refs:
  - FLOW-12
target_artifact: ".deviate/content-drafts/<format>/<slug>.md"
```

</required_output_template>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>