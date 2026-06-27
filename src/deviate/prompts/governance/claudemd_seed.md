## 🛠 DeviaTDD Phase Architecture

### Three-Layer Model

| Layer | Phases | Output Artifact |
|-------|--------|-----------------|
| **Macro** | explore → research → prd → shard | spec-enriched issue files |
| **Meso** | (HITL Gate 2) → plan → tasks → review | `plan.md`, `tasks.md` |
| **Micro** | red → green → yellow? → judge → refactor | passing test + ledger entry |

### HITL Gates (no programmatic bypass)

- **Gate 1**: after `/research`, before `/prd` — design + data-model approval
- **Gate 2**: after `/shard`, before `/plan` — spec-enriched issue sign-off
- **Gate 3**: after all tasks — final merge audit

### Model Tiering

| Tier | Phases |
|------|--------|
| V4 Flash (low-cost) | explore, red, green, refactor |
| V4 Pro (cached/compliance) | plan, tasks, yellow, judge |
| Qwen 3.7+ [Thinking] | research, prd, shard, adhoc |

Per-phase overrides: `.deviate/config.toml` → `[models]` → `default` + phase keys. Resolution: `src/deviate/state/config.py::resolve_phase_model`.

### Append-Only Ledger Protocol

`specs/issues.jsonl` and `specs/**/tasks.jsonl` are append-only. Canonical state is derived by sequential parsing.

### Git Isolation Principle

Every task loop runs on a clean branch/worktree. Commits happen at phase boundaries. **Never delete a branch unless the user explicitly requests it.**

### Tamper Guard & Micro-Sandboxing

GREEN resets `tests/` to post-RED state before evaluation. Micro-layer agents write **only** to `src/**/*.py`; mutations elsewhere trigger an immediate rollback.

### Session Continuity

Micro-layer tasks reuse a single LLM session across RED → GREEN → REFACTOR (no model switches). JUDGE runs in an isolated V4 Pro session.
