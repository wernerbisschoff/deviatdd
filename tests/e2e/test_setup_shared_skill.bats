#!/usr/bin/env bats
#
# E2E suite — TSK-047-04 (ISS-ADH-047). Verifies the consolidated
# `deviate setup` skill export end-to-end through the real CLI:
#
#   1. AC-PLAN-001 — `setup --agent codex,pi` writes exactly one
#      `deviatdd/SKILL.md` under `.agents/skills/`, no `.pi` copy, exits 0.
#   2. AC-PLAN-002 — re-run over a seeded old two-copy layout converges
#      to one copy (stale `.pi/skills/deviatdd` removed).
#   3. AC-PLAN-003 — `setup --agent pi` writes only the `.pi` tree.
#   4. Unknown `--agent` values exit non-zero with no skill trees written.
#
# Each test starts in a fresh tmpdir so `deviate` does not read the host
# repo's state.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    cd "$BATS_TEST_TMPDIR"
}

teardown() {
    if [[ -n "$BATS_TEST_TMPDIR" && "$BATS_TEST_TMPDIR" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_TMPDIR"
    fi
}

# A global `uv tool install` can lag behind this worktree's source.
# Run the CLI through `uv run --project REPO_ROOT` so every assertion
# exercises the tree under test.
_deviate() {
    uv run --quiet --project "$REPO_ROOT" deviate "$@"
}

@test "setup --agent codex,pi writes one shared skill copy" {
    run _deviate setup --agent codex,pi
    [ "$status" -eq 0 ]

    [ -f .agents/skills/deviatdd/SKILL.md ]
    [ ! -e .pi/skills/deviatdd ]

    [ "$(find . -path '*deviatdd/SKILL.md' 2>/dev/null | wc -l | tr -d ' ')" -eq 1 ]
}

@test "re-run over old two-copy layout converges to one copy" {
    mkdir -p .agents/skills/deviatdd .pi/skills/deviatdd
    echo "shared-body" > .agents/skills/deviatdd/SKILL.md
    echo "stale-body" > .pi/skills/deviatdd/SKILL.md

    run _deviate setup --agent codex,pi
    [ "$status" -eq 0 ]

    [ -f .agents/skills/deviatdd/SKILL.md ]
    [ ! -e .pi/skills/deviatdd ]

    [ "$(find . -path '*deviatdd/SKILL.md' 2>/dev/null | wc -l | tr -d ' ')" -eq 1 ]
}

@test "setup --agent pi writes only the .pi tree" {
    run _deviate setup --agent pi
    [ "$status" -eq 0 ]

    [ -f .pi/skills/deviatdd/SKILL.md ]
    [ ! -e .agents/skills/deviatdd ]
}

@test "setup --agent unknown fails closed with no skill trees" {
    run _deviate setup --agent not-an-agent
    [ "$status" -ne 0 ]

    [ -z "$(find . -path '*deviatdd/SKILL.md' 2>/dev/null)" ]
}
