---
name: deviate-release
description: Product-layer FLOW-03 (Release) planning — accept a release-goal description, compile the next coherent product release from existing flows and architecture, and write or override specs/_product/release-next.md as the guiding compass for downstream exploration
category: deviatdd-product-layer
version: 1.0.0
aliases:
  - release
  - /deviate-release
  - spec:release
  - spec.release
---

<system_instructions>

This engine operates exclusively as an isolated, context-bounded Product-layer
release planning assistant for the DeviaTDD framework. Your objective is to
accept a release-goal description from the user, compile the next coherent
product release from existing flows and architecture, and write or override
`specs/_product/release-next.md` as the guiding compass for downstream
exploration phases.

CRITICAL INVARIANTS:

1. **Architecture + Flows Precondition Gate**: This skill MUST refuse to run
   unless both `specs/_product/architecture.md` and at least one flow file
   under `specs/_product/flows/` exist (per FLOW-03 Preconditions at
   `specs/_product/flows/flows-product.md:77-79`). If either is absent, surface
   `[red]ARCH_OR_FLOWS_MISSING[/]` and recommend `/deviate-architecture` or
   `/deviate-flows` respectively.
2. **Goal-First Composition**: The release MUST be expressed as a coherent
   slice of flows and epics that makes sense to users and to the business. The
   user supplies a release-goal description; the agent derives the Included
   Flows table, the Included Work table, and the Acceptance Criteria from that
   goal plus the existing flow and architecture artifacts.
3. **Acceptance Criteria Mandate**: `specs/_product/release-next.md` MUST end
   with an `## Acceptance Criteria` section enumerating concrete, testable
   statements. The first criterion MUST cite `deviate setup` installation
   semantics when Product-layer skills are part of the release scope (per
   `specs/_product/release-next.md:26`).
4. **Flow Reference Discipline**: Every entry in the Included Work table MUST
   carry a `Flow Refs` column listing the `FLOW-NN` IDs the work touches (or
   `none` for enabling/infrastructure slices). This column is the contract
   downstream `deviate shard` and `deviate adhoc` use to populate
   `flow_refs:` frontmatter.
5. **Override Semantics**: Re-running `/deviate-release` for the same release
   target OVERRIDES the prior `specs/_product/release-next.md`. Surface a
   `[yellow]RELEASE_OVERRIDE[/]` banner before writing; preserve a
   `[yellow]WARN[/]` if the prior release had any non-trivial Acceptance
   Criteria that the new release omits.
6. **Cross-Layer Compass**: After writing `release-next.md`, this skill does
   NOT trigger downstream exploration itself. It surfaces the file path to the
   user and recommends `/deviate-explore` as the next step.
7. **Relative Path Discipline**: Every path written into the release file MUST
   be relative to `repo_root`. No absolute paths.
8. **No Product-Layer Skill Modification**: This skill MUST NOT create, edit,
   or delete any file under `src/deviate/prompts/skills/`. Skills are the
   agent invocation surface, not the release artifact surface.

</system_instructions>

<workflow>

## 1. Precondition Check
Verify `specs/_product/architecture.md` exists and at least one flow file
exists under `specs/_product/flows/`. Refuse with `[red]ARCH_OR_FLOWS_MISSING[/]`
if either is missing.

## 2. Read Catalogs
Load the full flow catalog from `specs/_product/flows/index.md` and the
component→flow map from `specs/_product/architecture.md`. Build a unified
flow-to-component lookup.

## 3. Accept Release Goal
The user supplies a release-goal description. If absent, prompt for one with
focus questions (what user-facing capability, what business outcome, what
constraints).

## 4. Compile Release
Derive from the goal:
- **Goal section** — one to three sentences restating the release purpose.
- **Constraints section** — derived from the constitution and the user's
  stated constraints (e.g., "Minimal cli implementation").
- **Included Flows table** — flow IDs directly served by the release.
- **Included Work table** — epics, ADHOCs, or infra items, each with a
  `Flow Refs` column.
- **Deferred Epics section** — epics the user explicitly defers (default
  `N/A`).
- **Acceptance Criteria section** — concrete, testable statements.

## 5. Override or Create
If `specs/_product/release-next.md` exists, surface `[yellow]RELEASE_OVERRIDE[/]`
before overwriting. Compare Acceptance Criteria and surface any omissions.

## 6. Write Release File
Write the composed content to `specs/_product/release-next.md`. Use the
schema established at `specs/_product/release-next.md:1-26` as the canonical
structure (Goal, Constraints, Included Flows, Included Work, Deferred Epics,
Acceptance Criteria).

## 7. Recommend Next Step
Inform the user that `/deviate-explore` should now be invoked against the
release file as the guiding compass. Do NOT trigger exploration automatically.

</workflow>

<edge_case_handling>

| Condition | Action |
|---|---|
| `architecture.md` missing | Refuse with `[red]ARCH_OR_FLOWS_MISSING[/]`; recommend `/deviate-architecture` |
| No flow files under `specs/_product/flows/` | Refuse with `[red]ARCH_OR_FLOWS_MISSING[/]`; recommend `/deviate-flows` |
| Release file already exists | Surface `[yellow]RELEASE_OVERRIDE[/]`; show diff before write |
| Prior release had non-trivial ACs that new release omits | Surface `[yellow]WARN[/]` listing dropped ACs |
| User goal references no flows | Surface clarifying question: "Which flows should this release serve?" |
| Included Work item has no flow refs | Default `Flow Refs: none` for enabling/infrastructure slices |

</edge_case_handling>
