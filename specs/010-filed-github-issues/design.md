## Recommended Architecture

[Summary]
- Keep the existing CLI, agent, and JSONL ledger boundaries.
- Centralize task-state selection and transition deduplication in the existing state layer.
- Make JUDGE evaluate the current GREEN diff and current requirements only.
- Make GREEN post clear stale rejection metadata after a successful transition.

[Module_Surface]
- Modify `src/deviate/cli` for phase-entry and postcondition handling. [SRC-CLI]
- Modify the existing agent/JUDGE path in `src/deviate/core/agent.py`. [SRC-AGENT]
- Modify task-ledger transition handling for retry ordering and deduplication. [SRC-LEDGER]
- Modify existing tests under `tests/` for the four issue scenarios. [SRC-TEST]
- No new module, persistence model, or external integration. [SRC-SCOPE]

[Rationale]
- The issues describe lifecycle defects across JUDGE, RED retry, and GREEN post.
- Existing boundaries already cover CLI, agent execution, and JSONL state. [SRC-BASELINES]
- The constitution requires append-only task state and the Micro phase sequence. [SRC-CONST-LEDGER]
- The floor therefore changes decision rules inside existing boundaries instead of adding persistence.

## Options Matrix
| Option | Complexity | Testability | Constitutional Alignment | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| Option A: Repair existing lifecycle boundaries | M | H | Aligned | Recommended: preserves JSONL state and current phase architecture. [SRC-CONST-ARCH] |
| Option B: Add a separate recovery state machine | H | M | Tension | Rejected: duplicates task-ledger state and increases transition ambiguity. [SRC-CONST-LEDGER] |
| Option C: Replace JSONL state with a database | H | M | Violation | Rejected: conflicts with the JSONL ledger standard and requires unrequested persistence. [SRC-CONST-DB] |

## Rejected Options
- Option B: duplicates the authoritative task state. [SRC-CONST-LEDGER]
- Option C: violates the declared JSONL state model. [SRC-CONST-DB]

## Design Trade-Offs
| Decision | Trade-off | Why This Side |
| :--- | :--- | :--- |
| Use current task ledger as authority | Less isolated recovery logic vs. one canonical state | Append-only JSONL is the declared state model. [SRC-CONST-LEDGER] |
| Compare JUDGE against current diff | Less historical context vs. fewer false rejections | Issue #242 identifies retained behavior absent from the GREEN diff. [SRC-242] |
| Deduplicate equivalent transitions | Less event detail vs. stable retries | Issue #244 identifies repeated RED/PENDING cycles. [SRC-244] |
| Clear stale rejection metadata on GREEN success | Less retained diagnostic context vs. correct completed state | Issue #243 identifies stale rejection fields after successful GREEN post. [SRC-243] |

## Contrarian Viewpoints
- A current-diff rule can miss required behavior preserved outside GREEN. The implementation must retain explicit preservation requirements in the active task contract. [SRC-242]
- Transition deduplication can hide a real retry if equality ignores the task identity or phase. The deduplication key must include both. [SRC-244]

## Risk Register
| Risk ID | Risk | Likelihood | Impact | Mitigation | Scope Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| RSK-001 | Concurrent or repeated ledger events select an older task state. | H | H | Select the sequentially derived latest state and append one valid transition. [SRC-244] | Required |
| RSK-002 | Successful GREEN work remains marked for retraining. | H | H | Clear stale rejection fields in the successful GREEN post transition. [SRC-243] | Required |
| RSK-003 | JUDGE rejects behavior that the current diff does not change. | H | H | Separate changed behavior from preservation requirements before verdict evaluation. [SRC-242] | Required |
| RSK-004 | Oscillating requirements cause repeated contradictory verdicts. | M | H | Detect repeated incompatible requirement interpretations and stop with a stable contradiction result. [SRC-245] | Required |

## Deferred
- Persistent recovery snapshots. [SRC-SCOPE]
- New database storage. [SRC-SCOPE]
- Generic metrics, alerts, and circuit breakers. [SRC-SCOPE]

## Constitutional Alignment Audit
| Constitutional Clause | Architectural Decision | Alignment | Notes |
| :--- | :--- | :--- | :--- |
| Three-Layer Architecture | Repair RED, GREEN, and JUDGE within Micro. | Aligned | Preserves the required phase sequence. [SRC-CONST-ARCH] |
| Append-Only Ledger Protocol | Append transitions and derive latest state sequentially. | Aligned | No existing ledger line changes. [SRC-CONST-LEDGER] |
| Micro-Layer Scope | Limit implementation changes to existing source paths and tests. | Aligned | No persistence or workflow scaffolding is added. [SRC-CONST-SCOPE] |
| Testing Protocols | Add pytest coverage for all four issue scenarios. | Aligned | The constitution names pytest and `tests/`. [SRC-CONST-TEST] |

## Pending HITL Decisions

<!-- HITL_DECISIONS -->
<!-- No pending decisions. The design follows the explore brief and existing constitution. -->

| Decision ID | Question | Context | Impact | Recommended Resolution | Status |
|---|---|---|---|---|---|

## Status Summary
| Metric | Value |
| :--- | :--- |
| STATUS | AWAITING_HITL_GATE_1 |
| FEATURE_SLUG | 010-filed-github-issues |
| NEXT_ACTION | Human reviews design.md + data-model.md, then invokes the prd skill |

### Source Registry
- [SRC-CLI] `specs/010-filed-github-issues/explore.md`: `src/deviate/cli` contains CLI modules.
- [SRC-AGENT] `specs/010-filed-github-issues/explore.md`: `class AgentBackend:`.
- [SRC-LEDGER] `specs/constitution.md`: `All state transitions in issues.jsonl and tasks.jsonl are append-only.`
- [SRC-BASELINES] `specs/010-filed-github-issues/explore.md`: routing, agent, state, and quality baselines.
- [SRC-SCOPE] `specs/010-filed-github-issues/explore.md`: `New Modules Required | No` and `New Persistence / Data Models | No`.
- [SRC-CONST-ARCH] `specs/constitution.md`: `Three-Layer Architecture`.
- [SRC-CONST-DB] `specs/constitution.md`: `all state tracked in JSONL ledgers and TOML config`.
- [SRC-CONST-SCOPE] `specs/constitution.md`: `GREEN phase writes only to src/ and permitted implementation paths.`
- [SRC-CONST-TEST] `specs/constitution.md`: `Test framework: pytest` and `Test root: tests/`.
- [SRC-242] `specs/010-filed-github-issues/explore.md`: issue #242 evidence.
- [SRC-243] `specs/010-filed-github-issues/explore.md`: issue #243 evidence.
- [SRC-244] `specs/010-filed-github-issues/explore.md`: issue #244 evidence.
- [SRC-245] `specs/010-filed-github-issues/explore.md`: issue #245 evidence.
