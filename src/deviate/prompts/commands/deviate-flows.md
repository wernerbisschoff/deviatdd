---
name: deviate-flows
description: Author customer flows — discover user-visible flows, write concise flows-<domain>.md files, and maintain the flows catalog at specs/_product/flows/index.md.
category: deviatdd-product-layer
version: 1.4.0
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

9. **Commit at Sign-Off (end-of-session atomic commit)**:
   This skill splits into two phases. Phase A (draft) writes every
   flow file and `index.md` row to disk as it goes so the user can
   see progress; Phase B (commit) fires exactly once after the user
   explicitly approves the final state. The full protocol:

   **Phase A — Draft.** For each new flow, write the
   `flows-<domain>.md` block and append the matching row to
   `specs/_product/flows/index.md` immediately via the `write` tool.
   No commit fires during Phase A — the working tree stays dirty but
   uncommitted so the user can review with `git diff`. The FLOW-04
   lesson applies: chat-only output is not enough; the files MUST
   land on disk.

   **Phase B — Sign-off and one commit.** When the user signals
   they are happy with the full set of changes ("commit",
   "looks good", "done", "ship it", "approve", "lgtm", "yes", or
   any unambiguous affirmative — silence is not sign-off), the
   skill MUST:
   1. Render a final summary of every `flows-<domain>.md` written
      this session plus the appended `index.md` rows.
   2. Run `git diff --cached --name-only`; if any cached path is
      outside the session-owned file set, halt and surface the
      staged list (do NOT auto-unstage).
   3. Invoke `deviate.core.commit.stage_and_commit` EXACTLY ONCE
      with `files=` listing every session-authored flow file plus
      `specs/_product/flows/index.md`. Pass a Conventional Commits
      subject (`docs(flows): add FLOW-NN[, FLOW-MM, ...] and update
      index`, or `docs(flows): update index` when no flow files
      were added). Do NOT call `commit_artifact(path, msg)` here —
      that helper commits one path per call and would emit one
      commit per file. Do NOT use `git add -A` or
      `git commit --only`.
   4. Never pass `no_verify=True`; if a pre-commit hook fails,
      surface stderr verbatim and stop.

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

## 5. Confirm Sign-Off (Phase B gate)
Surface a final summary of every flow written this session and
request explicit user approval before committing. Silence is not
sign-off; if the user asks for revisions, return to step 3. See
invariant 9 for the full Phase B protocol.

## 6. Atomic Commit (Phase B, exactly once)
Per invariant 9, invoke `stage_and_commit` exactly once with the
session-owned file list. Do not call `commit_artifact`, do not
run `git add -A`, do not pass `--no-verify`.

## 7. Cross-Layer Signal
Inform the user that the new `FLOW-NN` ID(s) are now available for
downstream `deviate shard` invocations to reference via
`flow_refs: [FLOW-NN]`.



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
| `stage_and_commit` reports a pre-commit hook failure | Surface hook stderr verbatim; do not pass `no_verify=True`; halt the session and surface the failure so the user can fix the lint or format violation and re-trigger sign-off |

</edge_case_handling>

<!-- CACHE BREAKPOINT: insert session UUID here -->

<runtime_payload>
  <!-- Dynamic content injected per invocation lives below this line. -->
  <user_turn />
</runtime_payload>

<context>
<user_input>$ARGUMENTS</user_input>
</context>