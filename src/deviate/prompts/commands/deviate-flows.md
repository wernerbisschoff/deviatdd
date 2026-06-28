---
name: deviate-flows
description: FLOW-01 flows authoring — discover customer flows, write flows-<domain>.md, and maintain specs/_product/flows/index.md.
category: deviatdd-product-layer
version: 1.1.0
aliases:
  - flows
  - /deviate-flows
  - spec:flows
  - spec.flows
---

<inputs>
  <input name="user_input" required="true">Free-text user request describing actor, domain, job-to-be-done, or trigger.</input>
  <input name="existing_seed_path" required="false">Absolute or repo-relative path to `specs/_product/flows/flows-product.md` if already populated.</input>
  <input name="existing_index_path" required="false">Absolute or repo-relative path to `specs/_product/flows/index.md`.</input>
</inputs>

<outputs>
  <output name="flow_file_path" type="string">Path to the newly authored `flows-<domain>.md`.</output>
  <output name="index_rows_added" type="integer">Count of rows appended to index.md.</output>
  <output name="flow_id" type="string">Assigned FLOW-NN identifier matching `^FLOW-\d{2,}$`.</output>
</outputs>

<domain_construct>
SCOPE: DeviaTDD Product-layer FLOW-01 (Flows) authoring.
WRITES: `specs/_product/flows/flows-<domain>.md` files and `specs/_product/flows/index.md`.
DOES NOT WRITE: `specs/_product/architecture.md`, `specs/_product/domain-model.md`, `specs/_product/release-next.md`.
SEED: `specs/_product/flows/flows-product.md` is read-only; extend, never regenerate.
GOAL: Produce FLOW-NN flow blocks that conform to the FLOW-01 section schema and remain traceable via `flow_refs:` frontmatter.
</domain_construct>

<system_instructions>

CRITICAL INVARIANTS:

0. **Input Resolution Rule**: First, read and consider the contents of the `<user_input>` container before continuing with execution. If that container is unpopulated or empty, resolve the target prompt by parsing the conversational history.

1. **Seed Extension, Not Regeneration**: `specs/_product/flows/flows-product.md`
   is the authoritative FLOW-01 seed. Treat it as the foundation to extend with
   domain-specific flow files (`flows-<domain>.md`); never regenerate it from
   scratch and never delete existing flow IDs (FLOW-01, FLOW-02, FLOW-03) from
   the catalog.
2. **Flow ID Format**: Every flow block MUST carry a `## FLOW-NN <Name>` header
   where `NN` is a zero-padded two-digit (or more) integer. Flow IDs are the
   cross-layer traceability anchors used by `deviate shard`, `deviate adhoc`,
   and the issues ledger (`flow_refs:` frontmatter).
3. **Index Sync Discipline**: After authoring any new flow file under
   `specs/_product/flows/`, append a row to `specs/_product/flows/index.md`
   with `Flow ID`, `Name`, `Actor`, `Domain`, `Status`, and `Source` columns.
   Source column must be the relative path of the file that defines the flow.
4. **Conversation-First Discovery**: Before writing any flow block, converse
   with the user to identify the actor, the job-to-be-done, the trigger, the
   preconditions, the happy path, the alternate paths, and the success state.
   Surface a clarifying question when any of these are ambiguous.
5. **No Cross-Layer Mutation**: This skill writes exclusively under
   `specs/_product/flows/`. Do NOT touch `specs/_product/architecture.md`,
   `specs/_product/domain-model.md`, or `specs/_product/release-next.md` —
   those belong to `deviate-architecture` and `deviate-release` respectively.
6. **FLOW-01 Schema Conformance**: Each flow file uses the section schema
   established at `specs/_product/flows/flows-product.md:1-32`: Actor,
   Domain, Status, Problem / job to be done, Trigger, Preconditions, Happy
   path, Alternate / error paths, Success State, Metrics / Signals.
7. **Relative Path Discipline**: Every path written to a flow file or to the
   index MUST be relative to `repo_root`. No absolute machine paths.

</system_instructions>

<execution_sequence>

## 1. Discovery Conversation

First, read and consider the contents of the `<user_input>` container before continuing.

Ask the user targeted questions to clarify:
- Who is the actor (Developer, End-User, Operator, External System)?
- What is the domain (Software Engineering, DevOps, Customer Support, etc.)?
- What is the job-to-be-done (single sentence, in actor's voice)?
- What triggers the flow (slash command, event, schedule, manual)?
- What preconditions must hold before the flow starts?
- What is the happy path (3-7 primary steps)?
- What alternate or error paths exist?

If the user already has `specs/_product/flows/flows-product.md` populated, read
it first to avoid asking redundant discovery questions about FLOW-01/02/03.

## 2. Determine Flow ID
Scan existing flow IDs in `specs/_product/flows/index.md`. Assign the next
sequential `FLOW-NN` ID, padding to at least two digits. If the user provides
an explicit ID, validate format `^FLOW-\d{2,}$`.

## 3. Write Flow File
Write to `specs/_product/flows/flows-<domain>.md` (or `flows.md` if no domain
qualifier is needed). Use the FLOW-01 section schema verbatim. Embed at least
two cross-references to other flow IDs in the Metrics / Signals block.

## 4. Update Index
Append a row to `specs/_product/flows/index.md` with the new flow's metadata.
If the index file does not yet exist, create it with a markdown table header.

## 5. Cross-Layer Signal
Inform the user that the new flow ID is now available for downstream
`deviate shard` invocations to reference via `flow_refs: [FLOW-NN]`.

</execution_sequence>

<!-- FEW-SHOT EXEMPLARS: injected -->
<examples>
  <example>
    <name>FLOW-04 Provision Developer Environment</name>
    <input>User: "I need a flow for a new developer running the test suite on first clone."</input>
    <output>

````markdown
## FLOW-04 Provision Developer Environment

| Field | Value |
|---|---|
| Actor | Developer |
| Domain | Onboarding |
| Status | Active |
| Source | specs/_product/flows/flows-onboarding.md |

**Problem / job to be done**: As a Developer, I need a reproducible local environment so I can run the test suite without manual setup.

**Trigger**: `deviate onboard` slash command.

**Preconditions**: Repository cloned; `.deviate/` directory present.

**Happy path**: 1. Run `deviate onboard`. 2. Skill provisions mise tasks. 3. Skill installs git hooks. 4. Skill reports green status.

**Alternate / error paths**: If mise binary missing → abort with diagnostic link; offer manual fallback.

**Success State**: `mise run check` exits 0 within 30s.

**Metrics / Signals**: setup_time_seconds ≤ 30; references FLOW-01, FLOW-02.
````

    </output>
  </example>
  <example>
    <name>index.md row appended by FLOW-04</name>
    <input>User: append row to specs/_product/flows/index.md after writing FLOW-04.</input>
    <output>

````markdown
| Flow ID | Name | Actor | Domain | Status | Source |
|---|---|---|---|---|---|
| FLOW-04 | Provision Developer Environment | Developer | Onboarding | Active | specs/_product/flows/flows-onboarding.md |
````

    </output>
  </example>
</examples>

<edge_case_handling>

| Condition | Action |
|---|---|
| `specs/_product/flows/` directory missing | Create the directory; emit a `[yellow]NOTICE[/] no Product-layer flows dir; created` log line |
| `flows-product.md` missing | Surface a clarifying question: "FLOW-01 seed is absent — recreate from template or skip?" |
| User provides no domain qualifier | Use the default `flows.md` filename |
| Duplicate flow ID detected | Refuse to overwrite; surface a collision error and prompt the user for the next ID |
| Index file is malformed (not a markdown table) | Append the new row as a markdown table; preserve the existing malformed header verbatim |
| Cross-layer file referenced | Refuse and route to the appropriate skill (`deviate-architecture` or `deviate-release`) |

</edge_case_handling>

<!-- CACHE BREAKPOINT: insert session UUID here -->

<runtime_payload>
  <!-- Dynamic content injected per invocation lives below this line. -->
  <user_turn />
</runtime_payload>

<context>
<user_input>$ARGUMENTS</user_input>
</context>