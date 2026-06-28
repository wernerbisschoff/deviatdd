# DeviaTDD

<p align="center">
<img src="logo.png" alt="DeviaTDD logo" width="480"/>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20with-uv-purple.svg)](https://docs.astral.sh/uv/)
[![Tests](https://img.shields.io/badge/tests-820%20collected%20%E2%9C%93-brightgreen.svg)](#development)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-orange.svg)](https://docs.astral.sh/ruff/)

> **An agent-orchestration framework that runs your entire TDD loop — explore, spec, red, green, refactor — with three mandatory human-in-the-loop gates.**

DeviaTDD is a Python CLI (`deviate`) that coordinates AI coding agents across the full Test-Driven Development lifecycle, from problem framing through documentation. It ships with a three-layer architecture, append-only JSONL ledgers, worktree isolation, and tamper-guarded test execution. The system is **agent-agnostic** — Claude Code, OpenCode, Pi, and Droid are first-class backends today.

---

## Why DeviaTDD?

Most AI coding agents stop at "write code that passes." DeviaTDD goes further — it runs the entire engineering loop:

| Without DeviaTDD | With DeviaTDD |
|------------------|---------------|
| Agent writes code, you review after | Three mandatory human gates: design, contract, merge |
| Test edits slip in silently during "GREEN" | Tamper Guard detects and rejects unauthorized test edits |
| Lost track of which task is in which state | Append-only JSONL ledgers derive canonical state |
| Branch drift between parallel features | Worktree isolation + append-only ledger merge driver |
| Locked to one agent vendor | First-class support for Claude, OpenCode, Pi, Droid |
| Specs drift from implementation | Spec-aligned issue files with FR traceability |

---

## Quickstart

```bash
# Install (requires Python 3.13+ and uv)
uv tool install deviate

# Bootstrap a new project + install slash commands into your agent of
# choice. Does it all in one shot: scaffolds .deviate/, specs/constitution.md,
# governance blocks, and installs /deviate-* slash commands for every
# supported agent. The `--agent` flag picks the default backend persisted
# to .deviate/config.toml (slash commands themselves are installed to all
# four agent directories regardless).
deviate setup --agent claude     # or: opencode | pi | droid
```

Once setup is done, drive the entire lifecycle from inside your agent:

```
/deviate-explore "Add user authentication via OAuth2"
/deviate-research
/deviate-prd
/deviate-shard
/deviate-plan
/deviate-tasks
/deviate-red T001          # starts the strict TDD loop
/deviate-green             # after the failing test is committed
/deviate-judge             # gate decision
/deviate-refactor          # once green is approved
```

> **Don't run `deviate <phase>` directly.** The CLI subcommands are the engine the slash commands drive — invoking them by hand skips contract emission, validation, commits, and ledger transitions.

The full lifecycle takes you from a problem statement to merged, tested code with a documented audit trail. See [`specs/DeviaTDD-architecture.md`](specs/DeviaTDD-architecture.md) for the canonical state machine.

---

## Architecture: Three Layers, Three Gates

```mermaid
flowchart TB
subgraph Macro["Macro Layer — Feature Scoping"]
E[explore] --> R[research]
R --> P[prd]
P --> S[shard]
end

S -.->|HITL Gate 2| Pl

subgraph Meso["Meso Layer — Issue Engineering"]
Pl[plan] --> T[tasks]
end

subgraph Micro["Micro Layer — TDD Sandbox"]
T --> Re[red]
Re --> G[green]
G --> J{judge}
J -->|violation| Y[yellow]
Y --> G
J -->|pass| Rf[refactor]
Rf -.->|HITL Gate 3| Done[merged]
end

style E fill:#e1f5e1
style R fill:#e1f5e1
style P fill:#e1f5e1
style S fill:#e1f5e1
style Pl fill:#e1e7f5
style T fill:#e1e7f5
style Re fill:#f5e1e1
style G fill:#f5e1e1
style J fill:#f5e1e1
style Y fill:#f5e1e1
style Rf fill:#f5e1e1
```

### Layers

- **Macro** — `explore → research → prd → shard`. Scopes a feature into spec-enriched issue files (`shard` produces them directly — no separate `specify` step). Outputs land in `specs/issues.jsonl` (append-only ledger).
- **Meso** — `plan → tasks`. Decomposes an issue into executable tasks with DAG dependencies. Tasks live at `specs/{epic}/tasks.jsonl`.
- **Micro** — `red → green → [yellow?] → judge → refactor`. The strict TDD sandbox. Micro-layer agents are sandboxed: they can write **only** to `src/**/*.py`. Test/spec mutations trigger an immediate rollback.

### Gates (no programmatic bypass)

- **Gate 1** — After `/deviate-research`, before `/deviate-prd`: design + data-model sign-off.
- **Gate 2** — After `/deviate-shard`, before `/deviate-plan`: spec-enriched issue approval.
- **Gate 3** — Final merge audit after all tasks complete.

### Append-Only Ledger Protocol

All state lives in JSONL ledgers (`specs/issues.jsonl`, `specs/**/tasks.jsonl`). Existing lines are never modified. `.gitattributes` configures `merge=union` so concurrent feature branches don't conflict at merge time. Canonical state is derived by sequential parsing.

---

## Agent Backends

DeviaTDD is agent-agnostic. Configure one or more in `.deviate/config.toml`:

```toml
[models]
default = "sonnet"
explore = "haiku"
plan = "opus"
```

| Backend | Mode | Skills Path |
|---------|------|-------------|
| **Claude Code** | Native | `~/.claude/skills/deviate-*/` |
| **OpenCode** | Native | `~/.config/opencode/skills/deviate-*/` |
| **Pi** | Print + opt-in RPC | `<workdir>/.pi/skills/deviate-*/` |
| **Droid** | Native | `~/.factory/skills/deviate-*/` |

Per-phase model routing is enforced via `src/deviate/state/config.py::resolve_phase_model`. Resolution order: phase-specific key → `default` → backend default.

---

## Slash Commands

DeviaTDD's user-facing interface is the library of `/deviate-*` slash commands installed by `deviate setup`. Each command emits a `pre` contract, the agent authors the artifact, then invokes a `post` command to validate, commit, and advance the ledger. **The CLI subcommands (`deviate explore`, `deviate plan`, etc.) are the engine beneath these prompts — never invoke them directly.**

### Bootstrap (run once per project / agent)

| Command | Purpose |
|---------|---------|
| `deviate setup --agent <name>` | One-shot bootstrap: scaffolds `.deviate/`, `specs/constitution.md`, governance blocks, and installs `/deviate-*` slash commands for every supported agent (`claude` \| `opencode` \| `factory` \| `pi`). The `--agent` flag sets the default backend. |
| `deviate feature create` | Create a feature worktree with isolated branch |

> Note: `deviate init` exists as the engine backing the `/deviate-init` slash command (see `src/deviate/cli/init.py`). It is **not** a user-facing shell command — use `deviate setup` instead.

### Macro (Feature Scoping)

`/deviate-explore` · `/deviate-research` · `/deviate-prd` · `/deviate-shard` · `/deviate-adhoc`

Scopes a feature into spec-enriched issue files. `deviate shard` now produces the spec-enriched issue files directly — there is no separate `specify` step. Outputs land in `specs/issues.jsonl` (append-only ledger).

### Meso (Issue Engineering)

`/deviate-plan` · `/deviate-tasks` · `/deviate-pr` · `/deviate-review`

Decomposes a spec-enriched issue into executable tasks with DAG dependencies. Tasks live at `specs/{epic}/tasks.jsonl`. `/deviate-review` is HITL Gate 3 — the structured PR scan before merge.

### Micro (TDD Sandbox)

`/deviate-red` · `/deviate-green` · `/deviate-yellow` · `/deviate-judge` · `/deviate-refactor` · `/deviate-e2e`

The strict TDD cycle. Micro-layer agents are sandboxed: they can write **only** to `src/**/*.py`. Test/spec mutations trigger an immediate rollback. Use `/deviate-execute` instead for low-complexity tasks, trivial changes, or refactors with existing coverage (no TDD cycle).

### Inspection & Maintenance

`/deviate-triage` · `/deviate-constitution` · `/deviate-hotfix` · `/deviate-prune` · `/deviate-flows` · `/deviate-architecture` · `/deviate-release`

The full library lives at `src/deviate/prompts/commands/` — 29 prompts spanning Macro, Meso, Micro, and the Tome subsystem.

---

## The Tome Subsystem (Documentation Curator)

DeviaTDD ships with **Tome** — a post-merge documentation curator that classifies your commits into Diátaxis quadrants (tutorial, how-to, reference, explanation) and routes them to the right writer skill. Output is a Starlight docs site at `apps/docs/`.

```
Commit → tome-classify → [tome-write-tutorial | tome-write-how-to |
                          tome-write-reference | tome-write-explanation]
                       → tome-verify-docs
```

Tome is **prompt-only** in v1 — no Python runtime added. Configure it in any target repo via `deviate setup`.

---

## Documentation

- **Authoritative specs**: [`specs/DeviaTDD-api.md`](specs/DeviaTDD-api.md) and [`specs/DeviaTDD-architecture.md`](specs/DeviaTDD-architecture.md) define the contract every implementation must satisfy.
- **Project constitution**: [`specs/constitution.md`](specs/constitution.md) — governance, tech stack, testing protocols, definition of done.
- **Skill prompts**: [`src/deviate/prompts/commands/`](src/deviate/prompts/commands/) — the markdown instructions each agent invokes.

---

## Development

### Setup

```bash
git clone https://github.com/wbisschoff13/deviatdd.git
cd deviatdd
mise run setup        # installs deps + configures git hooks
```

### Tasks (via `mise`)

| Task | Purpose |
|------|---------|
| `mise run test` | Run unit tests (`pytest tests/ -v`) |
| `mise run lint` | Lint with ruff |
| `mise run format` / `format-check` | Format / verify formatting |
| `mise run check` | Lint + format-check (pre-commit gate) |
| `mise run dev <args>` | Run the CLI in dev mode |
| `mise run clean` | Remove caches and build artifacts |

### Performance contract

- CLI init: **≤ 500ms** (measured: ~120ms median)
- Per-agent skill export: **≤ 200ms**
- Full test suite (820 tests): **< 25s**

### Test performance discipline

`src/deviate/cli/micro.py::_run_pytest` invokes pytest as a subprocess (~5s per call). Tests that exercise CLI commands internally calling `_run_pytest` MUST mock `deviate.cli.micro._run_pytest` with a `subprocess.CompletedProcess` fixture to keep the full suite under budget.

- Full test suite (820 tests): **< 30s**

## Project Status

DeviaTDD v2.0.0 is **production-ready** for individual developer workflows and small-team adoption. The three-layer architecture is stable; the public CLI surface and append-only ledger protocol are committed contracts.

**Known constraints** (will be addressed in subsequent releases):

- No public CI yet — runners are local; tests are green on the maintainer's machine at every release.
- No hosted service / SaaS layer.
- Multi-language code intelligence is limited to Python (full AST), with signature-level support for TypeScript, Rust, Go, C++, Elixir, C#, Markdown, Bash, JSON, TOML, YAML, HTML, CSS, SQL, Dockerfile, Terraform, Kotlin, Swift.

---

## Contributing

We welcome contributions. Open an issue first for non-trivial changes — DeviaTDD is itself dogfooded, so significant work usually goes through the same `/deviate-explore → /deviate-shard → /deviate-plan → /deviate-tasks → /deviate-red` lifecycle the framework prescribes.

Before opening a PR:

```bash
mise run check       # lint + format must be clean
mise run test        # all tests must pass
```

See [`specs/constitution.md`](specs/constitution.md) for the full execution contract.

---

## License

[MIT](LICENSE) © 2026 Werner Bisschoff
