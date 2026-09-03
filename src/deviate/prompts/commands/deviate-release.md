---
name: deviate-release
description: Plan the next coherent release — compile from existing flows and architecture and write specs/_product/release-next.md.
category: deviatdd-product-layer
layer: product
version: 2.0.0
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

1. **No Mandatory Flow or Architecture Precondition**: This skill does NOT refuse to run when `specs/_product/architecture.md` is missing or `specs/_product/flows/` is empty. Release authoring only needs the operator's goal; flows and architecture are optional inputs that the release may reference when present. If the goal names a flow or component that isn't yet catalogued, surface a `[yellow]WARN[/]` and recommend the relevant skill only when the operator's request actually depends on it.
2. **Goal-First Composition**: The release MUST be expressed as a coherent
   slice of flows and epics that makes sense to users and to the business. The
   user supplies a release-goal description; the agent derives the Included
   Flows table, the Included Work table, and the Acceptance Criteria from that
   goal plus the existing flow and architecture artifacts when they exist.
3. **Acceptance Criteria Mandate**: `specs/_product/release-next.md` MUST end
   with an `## Acceptance Criteria` section enumerating concrete, testable
   statements. Acceptance criteria describe the user-visible capability the
   release delivers, not DeviaTDD setup internals.
4. **Flow Reference Discipline**: Entries in the Included Work table MAY name the `FLOW-NN` IDs they relate to as prose. There is no `Flow Refs` column contract and no `flow_refs` frontmatter — references are for human readers only.
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
8. **No Product-Layer Command Modification**: This skill MUST NOT create, edit,
   or delete any file under `src/deviate/prompts/commands/`. Commands are the
   agent invocation surface, not the release artifact surface.
9. **Persist and Commit**: After composing `release-next.md`, this skill
   MUST persist the file to disk via the `write` tool and create a
   single git commit via the canonical helper:

   ```python
   from pathlib import Path
   from deviate.core.commit import commit_artifact

   commit_artifact(
       Path("specs/_product/release-next.md"),
       "docs(release): <one-line summary of the release goal>",
   )
   ```

   The commit message MUST follow Conventional Commits per
   `specs/constitution.md:71-75`. The skill MUST NOT pass
   `no_verify=True` per `AGENTS.md` §Commit Authority. If a pre-commit
   hook fails, surface the failure verbatim and stop — do not retry
   with `--no-verify`. Conversational output alone is not sufficient —
   this invariant is grounded in the prior session's bug where the
   release was emitted into chat but never written to disk, leaving
   `/deviate-explore` (the recommended next step) without a guiding
   compass file to read.
10. **No Ledger Grounding**: There is no flow ledger (`flows.jsonl`), no coverage helper, and no drift taxonomy. Ground the release in the operator's goal plus the flow catalog (`index.md`) and `architecture.md` when they exist. When absent, proceed with the goal alone.


</system_instructions>

<workflow>

## 1. Precondition Check
If `specs/_product/release-next.md` already exists, surface
`[yellow]RELEASE_OVERRIDE[/]` and stage a diff preview before overwriting.
Flows and architecture are optional inputs — proceed without them when
absent.
## 2. Read Catalogs
Load the flow catalog from `specs/_product/flows/index.md` and the component descriptions from `specs/_product/architecture.md` when they exist. Flows and architecture are optional inputs — proceed with the operator's goal alone when absent.


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
- **Included Work table** — epics, ADHOCs, or infra items the release covers.
- **Deferred Epics section** — epics the user explicitly defers (default
  `N/A`).

- **Acceptance Criteria section** — concrete, testable statements.

## 5. Override or Create
If `specs/_product/release-next.md` exists, surface `[yellow]RELEASE_OVERRIDE[/]`
before overwriting. Compare Acceptance Criteria and surface any omissions.

## 6. Write Release File
Compose the release content per the schema in step 4. Step 7 handles
the actual disk write and git commit; this step focuses on content
correctness. Use the schema established at `release-next.md:1-26` as
the canonical structure (Goal, Constraints, Included Flows, Included
Work, Deferred Epics, Acceptance Criteria).

## 7. Persist and Commit
`specs/_product/release-next.md` MUST be written to disk via the `write`
tool. After the write succeeds, create a single git commit using
`deviate.core.commit.commit_artifact` with the conventional commit
subject `docs(release): <one-line summary of the release goal>`. Never
pass `no_verify=True`. The conversational output of this skill MUST
NOT be considered complete until the file is on disk and committed —
`/deviate-explore` may read `release-next.md` from disk as an optional
guiding compass.

## 8. Recommend Next Step
Inform the user that `/deviate-explore` should now be invoked against the
release file as the guiding compass. Do NOT trigger exploration automatically.


</workflow>

<edge_case_handling>

| Condition | Action |
|---|---|
| `architecture.md` missing | Proceed without component→flow map; surface `[yellow]NO_ARCH_YET[/]` only if the release references an unnamed component |
| No flow files under `specs/_product/flows/` | Proceed without flow catalog; surface `[yellow]NO_FLOWS_YET[/]` only if the release references an unnamed flow |
| Release file already exists | Surface `[yellow]RELEASE_OVERRIDE[/]`; show diff before write |
| Prior release had non-trivial ACs that new release omits | Surface `[yellow]WARN[/]` listing dropped ACs |
| User goal references no flows | Surface clarifying question: "Which flows should this release serve?" |
| File write to `release-next.md` fails | Halt and surface the write error verbatim; do not commit a partial tree |
| `commit_artifact` reports a pre-commit hook failure | Surface hook stderr verbatim; do not pass `no_verify=True`; do not commit until the user remediates the underlying violation |

</edge_case_handling>

<context>
<user_input>
$ARGUMENTS
</user_input>
</context>
