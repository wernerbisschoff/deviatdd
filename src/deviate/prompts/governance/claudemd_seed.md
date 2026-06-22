## DeviaTDD Orchestration Rules

### Three-Layer Architecture
- **Macro Layer** — Feature scoping: `/explore` → `/research` → `/prd` → `/shard`. Each phase has a deterministic output artifact. HITL Gate 1 (Design Approval) gates transition to Meso.
- **Meso Layer** — Issue engineering: `/specify` → `/tasks`. Converts issue contracts into functional specs and granular tasks. HITL Gate 2 (Contract Sign-Off) gates transition to Micro.
- **Micro Layer** — TDD sandbox: RED → GREEN → YELLOW → JUDGE → REFACTOR. Each task executes as an isolated vertical slice across a complete R-G-R cycle.

### Append-Only Ledger Protocol
- All state transitions in `specs/issues.jsonl` and `specs/**/tasks.jsonl` are append-only.
- No existing line is ever modified or overwritten.
- Canonical state is derived by sequential ledger parsing.

### Git Isolation Principle
- Every task loop executes on a clean git branch or worktree.
- Commits are automatic at each phase boundary.
- NEVER delete a branch — whether by merging, closing, or any other means — unless the user has explicitly requested branch deletion.

### Tamper Guard & Micro-Sandboxing
- GREEN phase resets test directories to post-RED commit state before evaluation.
- Micro-layer LLM execution is strictly sandboxed: write access is granted **only** to files matching `src/**/*.py`.
- All `tests/`, `specs/`, and configuration files are strictly read-only during Micro-layer execution.
- Any mutation outside this allow-list triggers an immediate rollback.

### Human-in-the-Loop (HITL) Gates
- **Gate 1** (Design Approval): After `/research`, before `/prd` — human approves design and data model.
- **Gate 2** (Contract Sign-Off): After `/specify`, before `/tasks` — human approves functional contract.
- **Gate 3** (Final Merge Audit): After all tasks complete — human approves merge.
- No gate may be programmatically bypassed.

### Model Tiering
| Model | Phases |
|-------|--------|
| DeepSeek V4 Flash | `/explore`, RED, GREEN, REFACTOR |
| DeepSeek V4 Pro | JUDGE, YELLOW, `/specify`, `/tasks` |
| Qwen 3.7+ [Thinking] | `/research`, `/prd`, `/shard`, `/adhoc` |

### Session Continuity
- Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR phases.
- Model switching mid-task is prohibited.
- JUDGE phase runs in an isolated V4 Pro session for compliance verification.

### Task Execution Reference
Use `mise run <task>` for all execution:

| Task | Purpose |
|------|---------|
| `mise run test` | Run unit tests |
| `mise run test-e2e` | Run E2E tests via bats |
| `mise run lint` | Lint Python |
| `mise run lint-fix` | Apply lint fixes |
| `mise run format` | Format Python |
| `mise run format-check` | Check formatting |
| `mise run check-types` | Type check |
| `mise run fix` | Format + lint fix |
| `mise run check` | All validation checks |
| `mise run setup` | Install deps + hooks |
| `mise run clean` | Remove artifacts |
| `mise run help` | List tasks |

### Code Quality & Conventions

- **Docstrings**: Every public function, method, and class MUST have a docstring. Private helpers should have docstrings when their purpose isn't obvious from the name. Use the language's standard docstring format.
- **Typing**: All function signatures MUST have type annotations. Use strict typing where the language supports it. Typed code is self-documenting and catches errors at definition time.
- **Clean code**: Prefer early returns and guard clauses over deep nesting. Keep functions small and single-purpose. Favor readability over cleverness. Use descriptive names — code is written once, read many times.
- **Pragmatism**: Don't over-abstract. No features beyond what was asked. No abstractions for single-use code. If it can be 50 lines instead of 200, write 50 lines.
- **Imports**: Follow language conventions for import grouping (stdlib → third-party → local). Use absolute imports where idiomatic.
- **Testing**: All new code must have corresponding tests.

