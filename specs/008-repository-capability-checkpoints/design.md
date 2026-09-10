# Repository Capability Boundary and Runtime Verification

## Recommended Architecture

[Summary]: Extend `Verification_Batch` inside the existing Micro queue. Keep `TDD` and ordinary `IMMEDIATE` dispatch unchanged. Add a dedicated `CHECKPOINT` invocation through `AgentBackend`. The runtime validates evidence, appends ledger events, and controls queue progress. Sources: S1, S2, S3, S4.

Preserve atomic task verification. Each issue ends with a verification batch covering its available test ladder. Add runtime commands only when repository evidence establishes their relevance to the acceptance contract. Intermediate checkpoints require completed dependencies that expose assembled behavior. Missing runtime capability produces `VERIFICATION_CAPABILITY_MISSING` and a test-only closing batch. Sources: S5, S6, S7.

The repository owns runtime commands, setup, and verification infrastructure. DeviaTDD discovers these capabilities and creates only missing minimum TDD wrappers. Preserve existing named commands and inexpensive legacy init fallbacks during migration. Implement checkpoint dispatch first, capability discovery second, and init narrowing third. Sources: S8, S9, S10.

Constitution 0.12.0 resolves the previous substrate violation through `ADR-001`. This design implements §1 orchestration boundaries, §2 `AgentBackend`, §3 test preservation, and §5 acceptance evidence. The earlier Aider quote in `explore.md` remains historical evidence. Source: C2.

[Module_Surface]:

| Surface | Proposed change | Source |
|---|---|---|
| `src/deviate/core/tasks_ledger.py`, `src/deviate/state/ledger.py` | Preserve parsed task type; extend existing task events and evidence with checkpoint fields. | S1, S3 |
| `src/deviate/cli/micro.py` | Dispatch checkpoints before mode dispatch; reuse queue dependency, isolation, completion, and failure handling. | S2, S4 |
| `src/deviate/core/agent.py` | Extend `HandoverManifest`; reuse existing backend invocation for checkpoints. | S3, S11, S21, C2 |
| `src/deviate/cli/_safe_commands.py` | Validate declared repository Mise task invocations; retain argv parsing and timeout controls. | S12 |
| `src/deviate/cli/meso.py`, `src/deviate/cli/init.py` | Supply ephemeral capability observations; preserve `verification_suites` and existing task merges. | S8, S9 |
| `src/deviate/prompts/auto/checkpoint.md` | Add the dedicated verification resource. | S13 |
| `src/deviate/prompts/assembly.py` | Route `checkpoint` into the Micro layer. | S14 |
| `src/deviate/prompts/auto/tasks.md` | Distinguish atomic tests from assembled verification; preserve the closing batch. | S5, S6 |
| `src/deviate/prompts/commands/deviate-init.md` | Separate minimum testing from optional repository capabilities. | S8, S10 |
| `src/deviate/prompts/commands/deviate-e2e.md` | Align the historical test-authoring label with read-only batch semantics. | S15 |
| `README.md`, `specs/DeviaTDD-api.md`, `specs/DeviaTDD-architecture.md`, `CHANGELOG.md` | Explain both verification levels; align behavior and migration in the implementation commit. | S16, C5 |
| Existing parser, Micro, prompt, and init tests under `tests/` | Preserve sibling behavior and verify checkpoint safety, evidence, discovery, and queue transitions. | S17, C3 |

[Rationale]: Reusing the task queue preserves one execution authority. A separate verification system duplicates dependency and failure handling. Reusing `EXECUTE` permits implementation and rollback, contrary to checkpoint semantics. Sources: S2, S4, S13.

### Floor controls

Every control below is `Required`. Each supports the requested flow, compatibility, or data integrity.

| Decision | Floor behavior | Source |
|---|---|---|
| D1: Identity | Persist `task_type`; retain `Verification_Batch` → `IMMEDIATE`. Recover legacy type from the exact task block. Ambiguous historical batches halt for review. | S1, S15 |
| D2: Discovery | Read repository-scoped Mise declarations. Treat `verify` and `verify:*` as candidates. Require documented behavior before calling a candidate runtime proof. | S7, S9, S18 |
| D3: Placement | Map checkpoint commands to `AC-PLAN-NNN`. Require completed dependencies for intermediate batches. Keep one terminal batch with applicable tests. | S5, S6, S19 |
| D4: Execution | Invoke the dedicated prompt with task, issue, contract, commands, worktree, documentation, and capabilities. Use existing phase model resolution for `checkpoint`. | S13, C1 |
| D5: Verification-only role | The prompt directs the agent to execute declared commands, report evidence, and leave implementation, tests, configuration, and workflow state unchanged. | S13, S21 |
| D6: Proof | Validate exact task identity, `CHECKPOINT`, `PASS`/`FAIL`, command coverage, criterion coverage, and execution evidence. Runtime proof requires observable behavior. | S3, S7, S19 |
| D7: State | Runtime appends `CHECKPOINT_STARTED`, then `COMPLETED` or `CHECKPOINT_FAILED`. Preserve predecessor completion. Halt on failure or uncertain execution. | S4, S20, C1 |
| D8: Compatibility | Preserve normal task tests, TDD session continuity, ordinary immediate execution, and existing init commands. | S1, S8, C1 |

D5 is a prompt-level responsibility, rather than a new enforcement layer. Reuse existing backend permissions and command validation. Repository commands retain their expected runtime effects, including logs and browser traces. Sources: S12, S18, S21.

V1 trusts the checkpoint agent to follow its verification-only prompt. Checkpoint-specific sandboxes, write monitors, and unsupported-profile gates remain outside the floor. Failure ends checkpoint execution. The operator directs separate repair work through normal implementation gates, then requests verification again. Sources: S13, S20, S21.

Discovery records availability, rather than health. Revalidate declared commands at execution time. A missing optional capability during planning degrades gracefully. A missing command already required by a checkpoint fails that checkpoint. Sources: S7, S18.

`CHECKPOINT_STARTED` acts as the task's in-progress claim. Acquire that claim under the existing task/worktree isolation boundary. A second claimant halts. An interrupted checkpoint remains unresolved until explicit operator action. Automatic replay can repeat external effects; this design keeps replay explicit. Sources: S4, S18, S20.

The agent reports evidence. The runtime owns workflow writes and phase-boundary commits. Checkpoint commits include only runtime-owned ledger/evidence changes through explicit paths. Existing implementation commits remain intact. Sources: S2, S20, C1.

## Options Matrix

| Option | Complexity | Testability | Constitutional Alignment | Reversibility | Blast Radius | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| A: Typed batch dispatch, ephemeral capabilities, existing `AgentBackend` | M: extends existing models (S1, S3) | H: preserves queue seams (S4, S17) | Aligned: C1–C3 | Easy: additive fields (S3) | Module: parser, queue, prompts (S16) | Recommended |
| B: Same typed dispatch with a persistent capability registry | H: adds freshness ownership (S18) | H: adds stale-record cases (S7) | Aligned if stored through §2 JSON/TOML (C2) | Hard: introduces stored contracts (S9) | Module: discovery and storage (S9) | Rejected: V1 needs current observations, rather than a new source of truth (S7, S18) |

## Rejected Options

- Reuse `EXECUTE` with a verification instruction: its implementation instruction and staging path conflict with read-only verification. Sources: S2, S13.
- Add a separate checkpoint queue or skill controller: this duplicates the existing failure boundary. Sources: S4, S20.
- Require RepoReady metadata: this replaces capability discovery with product identity. Source: S10.
- Persist a V1 capability registry: runtime revalidation remains necessary; the optional future manifest belongs in the bracket. Sources: S7, S18.

## Design Trade-Offs

| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| Persist type, retain mode | Adds one discriminator while preserving existing modes. | Mode alone merges batches with implementation tasks (S1, S2). |
| Add checkpoint states to the existing ledger | Requires queue-reader updates rather than a second task system. | Explicit interrupted and failed states preserve completed work (S20, C1). |
| Reuse `HandoverManifest` and `TaskEvidenceBundle` | Adds typed verification results while preserving JUDGE evidence. | Existing evidence has test and implementation citations, rather than runtime observations (S3). |
| Discover rather than provision | Some repositories provide test-only proof. | Optional runtime capability stays repository-owned (S7, S10). |
| Prompt-only verification role | Keeps existing backend compatibility; relies on agent compliance. | The operator selects separate repairs and rejects checkpoint-specific protection machinery (S21). |
| Require a terminal batch | Adds a test-only batch in new issues where old specifications omit a sweep. | The operator approves mandatory closing batches for new issues (S5, S15, S21). |
| Keep legacy init fallbacks during rollout | Temporarily retains generic doctor generation. | The proposal explicitly requests staged extraction (S8, S10). |

## Contrarian Viewpoints

- A `verify:*` task can be a static check rather than runtime proof. Require documented observations and report ambiguous capability semantics. `Required`. Sources: S7, S18.
- Verification can create files, sessions, or database rows. The prompt distinguishes application edits from repository-owned runtime effects. `Required`. Sources: S18, S21.
- A historical batch can mean E2E authoring. Reclassifying it silently can omit required test creation. Halt ambiguous historical tasks for review. `Required`. Sources: S1, S15.
- Prompt instructions cannot guarantee file immutability. The operator accepts this limitation for V1; existing backend permissions remain active. `Required`: state this limitation accurately. Sources: S11, S21.

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation | Scope Status | Owner | Source Anchor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | Parser loses batch identity. | H | H | Persist type and test legacy block recovery; halt ambiguity. | Required | Task parser | S1: `IMMEDIATE_TASK_TYPES = frozenset({"Verification_Batch"})` |
| RSK-002 | Agent ignores its verification-only role and edits files. | M | H | State prompt-only restrictions and separate repair ownership; retain existing backend permissions. V1 accepts residual agent-compliance risk. | Required | Checkpoint prompt | S21: “Report failure; repair separately”; S11: `"pi": "pi -p",` |
| RSK-003 | Command name is mistaken for empirical proof. | H | H | Require scenario relevance and runtime observations. | Required | Tasks / checkpoint validation | S18: “Expected observation” |
| RSK-004 | Capability disappears between planning and execution. | M | M | Rediscover before execution; fail a missing declared command. | Required | Micro discovery | S7: “Runtime checkpoints should only be generated when an appropriate repository capability actually exists.” |
| RSK-005 | Two processes run one checkpoint or replay external effects. | M | H | Claim under task isolation; keep interrupted attempts unresolved until operator review. | Required | Micro ledger writer | C1: “Every task loop executes on a clean git branch or worktree.” |
| RSK-006 | Invalid success advances the queue. | M | H | Validate identity, command results, criterion coverage, and reported evidence against the declaration. V1 trusts agent observations. | Required | Handover validation | S3: `parse_errors: list[str] = []`; S21: “Report failure; repair separately” |
| RSK-007 | Failure resets completed implementation. | M | H | Append only checkpoint failure; use the existing queue halt boundary. | Required | Micro queue | S20: “Do not reset previous tasks.” |
| RSK-008 | Historical E2E batch loses its authoring purpose. | M | H | Resolve old task intent before dispatch; update conflicting prompt/spec labels. | Required | Parser / documentation | S15: “the E2E-authoring task” |
| RSK-009 | Missing capability expands an application issue into setup work. | M | M | Emit `VERIFICATION_CAPABILITY_MISSING`; preserve test-only completion. | Required | Tasks | S7: “For V1, prefer graceful degradation rather than blocking normal TDD work.” |
| RSK-010 | Evidence exposes secrets or machine-specific paths. | M | H | Redact credentials and store concise observations with repository-relative artifact references. | Required | Evidence validation | S18: “HTTP responses”; “application logs” |
| RSK-011 | Global or inherited Mise tasks cross repository ownership. | M | H | Retain source provenance and accept definitions within the repository trust boundary. | Required | Capability discovery | S18: “Tasks from all parent directories are merged into this list.” |
| RSK-012 | New states disappear from old status readers. | M | H | Test parsing, dependency selection, completion aggregation, resume, and `--all` against checkpoint events. | Required | Ledger / queue | S3: existing status enumeration; S4: `any_failed = True` |

## Deferred

These named extras form the maximal bracket. `Deferred` items supply zero additional floor fields or PRD requirements.

- `Deferred`: Optional capability-manifest consumption. Promote when repositories publish a stable product-independent contract. Source: S18: “Do not make this mandatory for V1.”
- `Deferred`: Automatic repair-task synthesis and checkpoint replay. Promote through a separate recovery design. Source: proposal §19: “it is not part of this change.”
- `Deferred`: Removing every legacy doctor fallback. Promote after the staged compatibility extraction. Source: proposal §6: “Existing doctor generation can remain temporarily for backwards compatibility”.
- `Deferred`: Persistent capability history and verification dashboards. Current observations and existing evidence cover the floor. Sources: S3, S9.
- `Deferred`: Checkpoint-specific sandboxing and write monitoring. Promote only through a separate protection requirement. Source: S21.

## Constitutional Alignment Audit

Quotes below come from `specs/constitution.md` 0.12.0. Each row evaluates the relevant D1–D8 decisions.

| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| §1: “The three layers have strict phase gates — no layer may be skipped.” | D3, D4 retain Macro → Meso → Micro. | Aligned | A checkpoint is a Micro task subtype, rather than a replacement layer. Sources: C1, S1. |
| §1: “It never gates execution, writes no ledger, and defines no `flow_refs` contract” | D2 uses repository commands and acceptance contracts. | Aligned | Product artifacts remain standalone. Source: C1. |
| §1: “RED must encode the issue's user scenarios” | D3, D8 preserve implementation tests; checkpoints supplement them. | Aligned | Read-only batches inspect previously implemented behavior. Sources: C1, S5. |
| §1: “Canonical state is derived by sequential ledger parsing.” | D1, D7 append typed events under existing task IDs. | Aligned | Preserve both issue-ID formats and historical rows. Sources: C1, S3. |
| §1: “Commits are automatic at each phase boundary.” | D5, D7 let the runtime commit only workflow outputs. | Aligned | Preserve task/worktree isolation and completed implementation commits. Sources: C1, S2. |
| §1: “Any mutation outside this allow-list is flagged by the JUDGE phase as a scope violation.” | D8 preserves GREEN/JUDGE scope checks. | Aligned | D5 sets a separate prompt-only verification role. Sources: C1, S13, S21. |
| §1: “No remaining gate may be programmatically bypassed.” | D7 preserves design and final merge approval. | Aligned | The operator resolves the research decisions explicitly; final merge approval remains required. Sources: C1, S21. |
| §1: “Model switching mid-task is prohibited.” | D4, D8 preserve each TDD session; a checkpoint has its own invocation. | Aligned | A checkpoint ends at PASS or FAIL. Sources: C1, S13. |
| §1: “V4 Flash for high-frequency phases” | D8 preserves existing named phase assignments. | Aligned | `checkpoint` uses existing config resolution rather than a hard-coded tier. Source: C1. |
| §1: “phase-specific key → `default` key → no model flag” | D4 resolves `checkpoint` using the existing resolver. | Aligned | Preserve backend-specific model and reasoning behavior. Sources: C1, C2. |
| §2: “the current execution contract uses `AgentBackend`.” | D4 reuses `AgentBackend`. | Aligned | `ADR-001` supersedes the prior Aider objection. Source: C2. |
| §2: “No persistent database runtime” | D1, D2, D7 use existing JSONL plus ephemeral discovery. | Aligned | Python/Pydantic extensions remain inside existing storage boundaries. Source: C2. |
| §3: “Test framework: pytest”; “Test root: `tests/`”; “Test extension: `.py`” | Verify D1–D8 through Python regression tests. | Aligned | Preserve parser, ordinary task, init, and checkpoint coverage. Sources: C3, S17. |
| §3: “Test command: `pytest tests/ -v`”; “Lint command: `ruff check .`”; “E2E command: `bats tests/e2e/`” | Run unit, lint, and applicable CLI integration checks. | Aligned | Use repository Mise wrappers; full-suite verification remains separate from `check`. Sources: C3, S17. |
| §3: “Coverage target: >= 80%” | Verify D1–D8 including negative and interrupted paths. | Aligned | Require measured coverage at implementation completion. Source: C3. |
| §3: “GREEN phase must pass all tests; JUDGE verifies GREEN only modified allowed files” | D8 preserves TDD gates. | Aligned | D4 dispatches only typed batches outside that implementation cycle. Sources: C3, S1. |
| §3: “REFACTOR phase runs regression gate: tests must re-pass after polish” | D8 retains the TDD regression gate. | Aligned | Checkpoint success supplements task proof. Source: C3. |
| §4: “All commits must reference the task ID” | Preserve implementation commit naming and final merge review. | Aligned | Existing task IDs remain canonical. Source: C4. |
| §5: “Judge phase passed (git diff validated against the authoritative plan acceptance contract)” | Preserve JUDGE for implementation; validate checkpoint evidence separately. | Aligned | Checkpoints author zero implementation; issue completion retains JUDGE-proven implementation tasks. Sources: C5, S13. |
| §5: “CHANGELOG.md updated under `[Unreleased]` for user-visible changes” | Update documentation and changelog with implementation. | Aligned | Research writes only the two declared artifacts. Sources: C5, S16. |

The attack finds zero constitutional violations. Floor design and data-model definitions agree on `task_type`, checkpoint states, evidence fields, and storage ownership.

## Pending HITL Decisions

<!-- HITL_DECISIONS -->

| Decision ID | Question | Context | Impact | Recommended Resolution | Status |
|---|---|---|---|---|---|
| HITL-002 | Which checkpoint failure and protection policy applies? | The operator rejects in-depth protection and selects “Report failure; repair separately” (S21). | V1 trusts prompt compliance and existing backend permissions. Failure halts; the operator directs separate repair work. | Use prompt-only verification restrictions and preserve normal implementation gates for repairs. | RESOLVED |
| HITL-003 | Should new issues always receive a closing batch? | The operator states “New issues should get a closing batch I think” (S21). | New issues receive test-only or runtime-enriched closing batches. Historical rows retain their existing evidence and require review when ambiguous (S15). | Require closing batches for new issues; preserve the conservative legacy handling. | RESOLVED |

`HITL-001` is resolved by `specs/constitution.md` `ADR-001` and version 0.12.0. The operator resolves `HITL-002` and `HITL-003` during research review. Source: S21.

## Source Registry

Each source contains a verbatim excerpt of at most 10 lines. Proposal references identify fields in the supplied research `context.user_input`.

| ID | Type | Source / Path | Verbatim excerpt and relevance |
| :--- | :--- | :--- | :--- |
| S1 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Architectural Baselines / File Registry | `IMMEDIATE_TASK_TYPES = frozenset({"Verification_Batch"})`; “`_TaskBlock.task_type` holds the parsed type.” |
| S2 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Architectural Baselines | `1. Implement the task using minimal, focused modifications`; `subprocess.run(["git", "add", "-A"], cwd=root, env=_git_env(), check=False)` |
| S3 | Codebase_File | `src/deviate/state/ledger.py:124-171`; `src/deviate/core/agent.py:62-91` | `class TaskEvidenceBundle(BaseModel):`; `evidence: TaskEvidenceBundle | None = None`; `parse_errors: list[str] = []`; `model_config = {"extra": "forbid"}` |
| S4 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Quality, Safety & Observability / Sibling Flow Inventory | `any_failed = True`; `if _phase_already_done(ledger_path, tid, "COMPLETED"):` |
| S5 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Manifest-Constitution Divergence | “It is always `Verification_Batch` / `IMMEDIATE`” |
| S6 | Contract field | `context.user_input`, proposal §§10, 13 | “Generate a checkpoint only when enough implementation exists for meaningful assembled behaviour to be observed.”; “Preserve the existing mandatory closing Verification_Batch.” |
| S7 | Contract field | `context.user_input`, proposal §§12, 15 | “Runtime checkpoints should only be generated when an appropriate repository capability actually exists.”; “For V1, prefer graceful degradation rather than blocking normal TDD work.” |
| S8 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Infrastructure & Operations / File Registry | `if name not in existing`; `"doctor:unit": unit_check,` |
| S9 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, External Integrations | `"verification_suites": existing_verification_suites(repo_root),` |
| S10 | Contract field | `context.user_input`, proposal §§3, 27, 36 | “The integration boundary is therefore based on capabilities, not product identity.”; “Phase 1 — checkpoint support”; “Phase 2 — capability discovery”; “Phase 3 — extraction”; “Phase 4 — narrow init” |
| S11 | Codebase_File | `src/deviate/core/agent.py:177-194` | `"pi": "pi -p",`; `"codex": "codex exec --sandbox workspace-write --approve-for-me",` |
| S12 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Quality, Safety & Observability | “This module replaces that boundary with a strict allowlist.”; `TEST_TIMEOUT_EXIT_CODE: int = 124` |
| S13 | Contract field | `context.user_input`, proposal §§9, 16, 18 | “modifies no code”; “modifies no tests”; “Add: src/deviate/prompts/auto/checkpoint.md”; “invoke AgentRunner with auto/checkpoint.md” |
| S14 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, File Registry | `"execute": "micro",` |
| S15 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Manifest-Constitution Divergence | “else no extra sweep.”; “the E2E-authoring task” |
| S16 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, Scope Sizing | “Parsing, queue dispatch, command safety, failure evidence, initialization, and prompt composition” |
| S17 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, File Registry / Test Runner Configuration | `assert resolve_execution_mode("Verification_Batch", "TDD") == "IMMEDIATE"`; `depends = ["lint", "format-check"]` |
| S18 | Explore_MD | `specs/008-repository-capability-checkpoints/explore.md`, RepoReady Context / Ecosystem Research | “Expected observation”; “What stable state proves success?”; “screenshots”; “HTTP responses”; “application logs”; “Do not make this mandatory for V1.”; “Tasks from all parent directories are merged into this list.” |
| S19 | Codebase_File | `src/deviate/state/ledger.py:88-122` | `criterion_id: str`; `verification_mode: Literal["automated", "manual", "deferred"]`; `test_ref: str | None = None` |
| S20 | Contract field | `context.user_input`, proposal §§20, 21 | “Do not reset previous tasks.”; “T004 CHECKPOINT_STARTED”; “T004 CHECKPOINT_FAILED”; “Devia runtime: validate manifest write ledger mark complete halt/continue” |
| S21 | Operator decision | Research review, `HITL-002` / `HITL-003` | “No in depth protection for checkpoints I think.”; “New issues should get a closing batch I think”; selected option: “Report failure; repair separately” — “Prompt-only verification restrictions. Runtime halts; operator directs a separate repair task. Recommended V1.” |
| C1 | Constitution | `specs/constitution.md`, §1 | “Canonical state is derived by sequential ledger parsing.”; “Model switching mid-task is prohibited.”; “No remaining gate may be programmatically bypassed.” |
| C2 | Constitution | `specs/constitution.md`, §2 / ADR-001 | “the current execution contract uses `AgentBackend`.”; “No persistent database runtime”; “Python 3.13” |
| C3 | Constitution | `specs/constitution.md`, §3 | “Coverage target: >= 80%”; “REFACTOR phase runs regression gate: tests must re-pass after polish” |
| C4 | Constitution | `specs/constitution.md`, §4 | “All commits must reference the task ID”; “All code must pass `mise run check` before merge” |
| C5 | Constitution | `specs/constitution.md`, §5 | “Judge phase passed (git diff validated against the authoritative plan acceptance contract)”; “CHANGELOG.md updated under `[Unreleased]` for user-visible changes” |

## Status Summary

| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 008-repository-capability-checkpoints |
| NEXT_ACTION | Run `deviate research post` after the approved revisions; retain human control over starting `/prd`. |
