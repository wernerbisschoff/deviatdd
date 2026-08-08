# Guildwright Rewrite Documentation Set

This index defines the source documents for the Guildwright Rust TUI rewrite.

Guildwright is a retargeting of DeviaTDD. It is not a redesign of the development method.

## Documents

1. [`guildwright-current-system.md`](guildwright-current-system.md) — current DeviaTDD flows, artifacts, runners, prompts, state, and output.
2. [`guildwright-git-state-model.md`](guildwright-git-state-model.md) — Git-backed state invariants, branch claims, append-only ledgers, and revert semantics.
3. [`guildwright-rust-tui-requirements.md`](guildwright-rust-tui-requirements.md) — required Rust architecture, TUI boundaries, configuration, and migration decisions.
4. [`guildwright-gap-register.md`](guildwright-gap-register.md) — missing requirements, current contradictions, and decisions required before implementation.

## Authority Order

When sources disagree, use this order:

1. `specs/constitution.md`
2. `specs/DeviaTDD-api.md`
3. `specs/DeviaTDD-architecture.md`
4. Current implementation under `src/deviate/`
5. Tests
6. Historical issue and task documents

Record every disagreement in the [gap register](guildwright-gap-register.md). Do not silently select a behavior.

## Core Rewrite Invariant

The checked-out Git commit and branch define durable workflow state. Guildwright derives runtime state from tracked ledgers and artifacts at `HEAD`. A Git revert or checkout must therefore restore the matching runner state without a separate migration or repair step.

`.guildwright/` can contain caches, locks, logs, and UI preferences. It must not contain workflow truth.
