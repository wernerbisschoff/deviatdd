---
name: deviate-flows
description: Author customer flows — discover user-visible flows, write concise flows-<domain>.md files, and maintain the flows catalog at specs/_product/flows/index.md.
category: deviatdd-product-layer
version: 1.3.0
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
GOAL: Produce FLOW-NN flow blocks that conform to the FLOW-01 section schema, stay terse, and remain traceable via `flow_refs:` frontmatter.
</domain_construct>

<system_instructions>

CRITICAL INVARIANTS:

0. **Input Resolution Rule**: First, read and consider the contents of the `<user_input>` container before continuing with execution. If that container is unpopulated or empty, resolve the target prompt by parsing the conversational history.

1. **Seed Extension, Not Regeneration**: `specs/_product/flows/flows-product.md`
   is the authoritative FLOW-01 seed. Extend it with domain-specific flow files
   (`flows-<domain>.md`); never regenerate it and never delete existing flow
   IDs (FLOW-01/02/03) from the catalog.
2. **Flow ID Format**: Every flow block carries a `## FLOW-NN <Name>` header
   where `NN` is a zero-padded two-digit (or more) integer. IDs are the
   cross-layer traceability anchors used by `deviate shard`, `deviate adhoc`,
   and the issues ledger (`flow_refs:` frontmatter).
3. **Index Sync Discipline**: After authoring any new flow file under
   `specs/_product/flows/`, append a row to `specs/_product/flows/index.md`
   with `Flow ID`, `Name`, `Actor`, `Domain`, `Status`, and `Source` columns.
   Source column carries the relative path of the file that defines the flow.
4. **Conversation-First Discovery**: Before writing any flow block, converse
   with the user to identify actor, job-to-be-done, trigger, preconditions,
   happy path, alternate paths, and success state. Surface a clarifying
   question when any of these are ambiguous.
5. **No Cross-Layer Mutation**: This skill writes exclusively under
   `specs/_product/flows/`. Do NOT touch `specs/_product/architecture.md`,
   `specs/_product/domain-model.md`, or `specs/_product/release-next.md` —
   those belong to `deviate-architecture` and `deviate-release`.
6. **FLOW-01 Schema Conformance**: Each flow file uses the section schema
   defined in `specs/_product/flows/flows-product.md` (header bullets:
   `Actor`, `Domain`, `Status`, `Source`; sections: `Problem / job to be done`,
   `Trigger`, `Preconditions`, `Happy path (primary steps)`,
   `Alternate / error paths`, `Success State`, `Metrics / Signals`). Use the
   same bullet-list style as the seed — never invent a table-only variant.
7. **Relative Path Discipline**: Every path written to a flow file or to the
   index is relative to `repo_root`. No absolute machine paths.

8. **Concise Output Discipline (downstream-consumption contract)**:
   Downstream phases (`/prd` Pass 2.1, `/shard` Pass 2.1, `/plan`,
   `/tasks`, micro `/red`/`/green`/`/judge`) consume flow files as
   structured inputs — they do NOT read every section. To keep their
   token budget small and parsing deterministic, the following length
   budgets are mandatory per flow block:
   - Header bullets (`Actor`, `Domain`, `Status`, `Source`): exactly one
     line each, no prose, no nested bullets.
   - `Problem / job to be done`: 1 sentence, ≤ 25 words.
   - `Trigger`: 1 sentence (or 1 short bullet) — the canonical entry
     point that downstream phases restate. Always present.
   - `Preconditions`: 0–3 bullets. Omit the heading entirely if there are
     none.
   - `Happy path (primary steps)`: 3–7 numbered steps, ≤ 12 words each.
     Always present — this is what micro phases translate into tests.
   - `Alternate / error paths`: 0–3 bullets or literal `TBD`. Omit the
     heading if there are none.
   - `Success State`: 1–3 bullets. Always present.
   - `Metrics / Signals`: 0–3 bullets. Omit the heading if there are none.
     Cross-references to other `FLOW-NN` IDs go here in the form
     `references FLOW-XX, FLOW-YY`.
   - Total flow block target: **≤ 35 lines of markdown**. The previous
     bloat (~150 lines per flow) was the bug; keep each flow scannable
     in a single screen.

9. **Persist and Commit**: After authoring the new `flows-<domain>.md`
   file and appending the `index.md` row, this skill MUST persist both
   writes to disk (the conversational output is not enough — see the
   FLOW-04 lesson where `deviate-architecture` correctly refused to
   run `/deviate-release` because the architecture had only been
   emitted into chat). The skill MUST then create a single git commit
   containing both files using the canonical helper:

   ```python
   from pathlib import Path
   from deviate.core.commit import commit_artifact

   commit_artifact(
       Path("specs/_product/flows/flows-<domain>.md"),
       "docs(flows): add FLOW-<NN> <Name> (<domain>)",
   )
   commit_artifact(
       Path("specs/_product/flows/index.md"),
       "docs(flows): index FLOW-<NN>",
   )
   ```

   Commit message MUST follow Conventional Commits per
   `specs/constitution.md:71-75`. The skill MUST NOT pass
   `no_verify=True` — pre-commit hooks run lint + format-check and are
   non-bypassable per `AGENTS.md` §Commit Authority. If a hook fails,
   surface the failure verbatim and stop; do not silently drop the
   `--no-verify` flag.

</system_instructions>

<execution_sequence>

## 1. Discovery Conversation

Read `<user_input>` first; if empty, parse conversational history.

**Discovery discipline** (adapted from the "grill with docs" pattern, made active):
- **Ask ONE question at a time**, with your recommended answer, and wait for the human's response before asking the next. Do not advance to the next question until the human has answered.
- **Walk the dependency tree** dependency-first: resolve Actor before Domain, Domain before Trigger, Trigger before Happy Path.
- **Read first, ask second**: if a question can be answered by reading the codebase, existing flow files, or `specs/_product/architecture.md`, do that instead of asking.
- **Term-challenge against the glossary** (at most once per turn): if the user's term conflicts with `flows-product.md`, `specs/_product/domain-model.md`, or any existing `flows-<domain>.md`, call it out immediately — "The seed defines X as Y, but you seem to mean Z — which is it?" Propose a canonical name for vague terms ("account", "thing"). Do not loop on challenges — surface once, then move on.
- **Sharpen fuzzy language**: when the user names the flow with a vague term, propose a precise canonical name and confirm before writing the `## FLOW-NN <Name>` header.
- **Stress-test with scenarios**: for each happy-path step, invent one concrete edge case ("what if the user is offline when the trigger fires?") and ask the human to confirm the alternate-path behavior.
- **Update flow file inline**: as terms and scenarios resolve, update the in-progress flow block immediately. Do not batch up the corrections — capture them as they happen.

Ask targeted questions to clarify:
- Actor (Developer / End-User / Operator / External System)
- Domain (Software Engineering / DevOps / Customer Support / etc.)
- Job-to-be-done (1 sentence, in actor's voice)
- Trigger (slash command, event, schedule, manual)
- Preconditions (any non-trivial state required before the flow starts)
- Happy path (3–7 primary steps)
- Alternate / error paths (only if non-obvious; otherwise mark `TBD`)

If `specs/_product/flows/flows-product.md` is populated, read it first to
avoid re-asking about FLOW-01/02/03.

## 2. Determine Flow ID
Scan existing IDs in `specs/_product/flows/index.md`. Assign the next
sequential `FLOW-NN` (zero-padded, ≥ two digits). If the user supplies an
explicit ID, validate it matches `^FLOW-\d{2,}$`.

## 3. Write Flow File
Write to `specs/_product/flows/flows-<domain>.md` (or `flows.md` if no
domain qualifier applies). Use the FLOW-01 bullet-list schema verbatim —
do NOT switch to a table format. Stay within the per-section length
budgets in invariant 8. Cross-references to other `FLOW-NN` IDs belong
under `Metrics / Signals`; at least one cross-reference is recommended
whenever a related flow exists.

## 4. Update Index
Append a row to `specs/_product/flows/index.md` (create the file with a
header row if absent). Source column carries the relative path of the new
flow file.

## 5. Persist and Commit
Both the new flow file and the appended index row MUST be written to
disk. After both writes succeed, create a single git commit (or two
commits, one per file) using `deviate.core.commit.commit_artifact` with
the conventional commit subject `docs(flows): add FLOW-<NN> <Name>`
and `docs(flows): index FLOW-<NN>`. Never pass `no_verify=True`; if
hooks fail, surface and stop. Conversational output alone does not
satisfy this skill — the files MUST land on disk and under version
control before the skill yields.

## 6. Cross-Layer Signal
Inform the user that the new `FLOW-NN` ID is now available for downstream
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

- Actor: Developer
- Domain: Onboarding
- Status: Active
- Source: specs/_product/flows/flows-onboarding.md

### Problem / job to be done
- As a Developer, I need a reproducible local environment so I can run the test suite without manual setup.

### Trigger
- `deviate onboard` slash command.

### Preconditions
- Repository cloned; `.deviate/` directory present.

### Happy path (primary steps)
1. Run `deviate onboard`.
2. Skill provisions mise tasks.
3. Skill installs git hooks.
4. Skill reports green status.

### Alternate / error paths
- If mise binary missing → abort with diagnostic link; offer manual fallback.

### Success State
- `mise run check` exits 0 within 30s.

### Metrics / Signals
- `setup_time_seconds` ≤ 30.
- references FLOW-01, FLOW-02.
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
| Generated flow block exceeds the line/word budgets in invariant 8 | Tighten prose before writing; downstream `/prd` and `/shard` will fail to parse bloated sections |
| `commit_artifact` reports a pre-commit hook failure | Surface hook stderr verbatim; do not pass `no_verify=True`; do not commit until the user remediated the underlying lint or format violation |
| Git working tree is dirty from prior work | Stash or revert before persisting the new flow; never co-mingle unrelated changes in the flow commit |

</edge_case_handling>

<!-- CACHE BREAKPOINT: insert session UUID here -->

<runtime_payload>
  <!-- Dynamic content injected per invocation lives below this line. -->
  <user_turn />
</runtime_payload>

<context>
<user_input>$ARGUMENTS</user_input>
</context>