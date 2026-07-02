---
title: "Run /deviate-yellow"
description: "How to evaluate and approve or reject the test amendments /deviate-green proposed via /deviate-yellow, returning the task to GREEN or advancing to JUDGE."
doc_type: how-to
status: draft
last_verified_at: 2026-07-01
verified_sha: ce05af8
related_issues:
  - ISS-001-003
prev: green.md
next: false
---

This how-to covers the micro-layer `/deviate-yellow` phase: evaluating the test amendments the GREEN agent emitted in its handover manifest when it decided the failing test could not be satisfied without modifying `tests/**/test_*.py`. YELLOW is the conditional amendment gate — APPROVED advances the task to JUDGE, REJECTED restores the worktree via `git restore .` and forces the session back to GREEN.

## Prerequisites

- A `GREEN` ledger row for the active `TSK-NNN-NN` whose handover manifest carries `yellow_trigger: true` and a `test_changes` payload (auto-emitted by `/deviate-green` or surfaced by TamperGuard)
- Cwd inside the issue worktree created by `deviate feature start <ISS-XXX>`; `git status --porcelain` shows the pending test amendments
- The agent backend dispatched in **isolated V4 Pro mode** — YELLOW runs in a fresh session with no shared RED/GREEN context, by design, to preserve compliance integrity
- `deviate-yellow` prompt installed under `.claude/commands/`, `.opencode/commands/`, `.factory/commands/`, or `.pi/prompts/` (run `deviate setup` if absent)

## Steps

### 1. Run the pre-script for the JSON contract

From inside the issue worktree, invoke the pre-script with the target task ID:

```bash
deviate yellow pre --task TSK-001-03
```

It runs `git status --porcelain` to detect the uncommitted test amendments, enumerates `tests/**/test_*.py` files, and emits a JSON contract with `proposed_changes`, `rationale`, and `test_files`. Capture the file list so the agent can read each amendment before voting.

### 2. Invoke `/deviate-yellow` in the agent

In the agent's chat on the feature branch, run:

```text
/deviate-yellow
```

The slash command runs in an isolated V4 Pro session. It parses the GREEN handover's `test_changes` block, cross-references each amendment against `spec.md` `FR-[ID]` and `AC-[ID]` criteria, and emits an APPROVE or REJECT verdict scored on necessity, scope, spec alignment, and rationale sufficiency.

### 3. Run the post-script with the verdict

Run the post-script with the matching flag — they are mutually exclusive:

```bash
deviate yellow post --approved
```

```bash
deviate yellow post --rejected
```

`--approved` commits the amendments (`feat: YELLOW phase - approved amendments`), appends a `YELLOW_APPROVED` transition to `tasks.jsonl`, and force-transitions `.deviate/session.json` to `JUDGE`. `--rejected` runs `git restore .` to drop the amendments, appends `YELLOW_REJECTED`, and force-transitions the session back to `GREEN`.

### 4. Verify the change

```bash
git log --oneline -1
cat .deviate/session.json | jq -r '.current_phase'
grep -E '"status": "YELLOW_(APPROVED|REJECTED)"' specs/<epic>/<issue>/tasks.jsonl
```

Expected: the latest commit message starts with `feat: YELLOW phase` (approved path) or no new commit lands (rejected path; the amendments are dropped), `current_phase` reads `"JUDGE"` (approved) or `"GREEN"` (rejected), and the `tasks.jsonl` row ends with a matching `YELLOW_*` status entry.

## Troubleshooting

### `NO_CHANGES_PROPOSED` from `deviate yellow post`

`git status --porcelain` came back clean — the amendments were already committed, reverted, or never written. Re-run `/deviate-yellow` only when there is a real proposal to evaluate; otherwise close the session and resume from `/deviate-green`.

### `MUTUALLY_EXCLUSIVE` from `deviate yellow post`

Both `--approved` and `--rejected` were passed. Pick the verdict that matches the agent's last response and re-invoke the post-script with a single flag.

### `MISSING_GREEN_PHASE` when the GREEN row cannot be found

The latest task in `tasks.jsonl` has no `GREEN` transition, so the YELLOW post-script cannot resolve a target row. Re-run `/deviate-green` so the GREEN commit and ledger entry land first, then re-trigger `/deviate-yellow`.

### Session stays in `GREEN` after `--rejected`

`YELLOW_REVERTED` printed but `current_phase` still reads `"GREEN"` from a stale read. Reload `.deviate/session.json` and confirm the file's mtime advanced; if not, re-run `deviate yellow post --rejected` to overwrite the session file.

## Next Steps

- [How to run /deviate-judge](/how-to/tdd-micro-cycle/judge) — verify the approved amendments against the spec contract
- [How to run /deviate-green](/how-to/tdd-micro-cycle/green) — re-run GREEN after a rejection to satisfy the test without amendments
- [Reference: deviate yellow flags and contract fields](/reference/cli/yellow) — full flag list for `yellow pre` / `yellow post`
- [Why YELLOW runs in an isolated V4 Pro session](/explanation/micro-layer-purpose) — design rationale for the cache-sacrifice compliance gate