#!/usr/bin/env bats
#
# E2E suite — TSK-030-05 (ISS-ADH-030). Verifies the reworked
# `deviate setup` provisioning end-to-end through the real CLI:
#
#   1. AC-PLAN-002 — `setup --agent opencode` installs commands and
#      skills only under `.opencode/`, prints INSTALL, exits 0.
#   2. AC-PLAN-003 — `setup` with no --agent auto-detects installed
#      agents and targets exactly those directories.
#   3. AC-PLAN-004 — setup fails closed on an uninstalled agent
#      without any partial install.
#   4. AC-PLAN-001 — setup provisions a root ignore entry so
#      `git check-ignore .deviate/` resolves and `.deviate/` never
#      appears as an untracked candidate.
#   5. AC-PLAN-005 / AC-PLAN-006 — the config schema has one
#      consolidated `timeout_seconds`, no `[agent] timeout`, no
#      `graphite` key, rejects a stale `graphite` key via extra=forbid,
#      and keeps the phase key → default → backend-native model order.
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

@test "setup --agent opencode installs only under .opencode/" {
    mkdir .claude .opencode

    run _deviate setup --agent opencode
    [ "$status" -eq 0 ]
    [[ "$output" == *"INSTALL"* ]]

    [ -f .opencode/commands/deviate-red.md ]
    [ -f .opencode/skills/deviatdd/SKILL.md ]

    # No other agent directory receives command or skill files.
    [ -z "$(find .claude \( -name 'deviate-*' -o -name 'deviatdd' \) 2>/dev/null)" ]
}

@test "setup with no --agent auto-detects exactly the installed agents" {
    mkdir .claude .opencode

    run _deviate setup
    [ "$status" -eq 0 ]
    [[ "$output" == *"INSTALL"* ]]

    # Both detected agents receive command files...
    [ -f .claude/commands/deviate-red.md ]
    [ -f .opencode/commands/deviate-red.md ]
    # ...and skills land under both detected agents.
    [ -f .claude/skills/deviatdd/SKILL.md ]
    [ -f .opencode/skills/deviatdd/SKILL.md ]

    # Undetected agent directories were never created by setup.
    [ ! -d .factory ]
    [ ! -d .pi ]
    [ ! -d .omp ]
}

@test "setup fails closed on an uninstalled agent without partial install" {
    mkdir .claude .opencode

    run _deviate setup --agent factory
    [ "$status" -eq 1 ]
    [[ "$output" == *"AGENT_NOT_INSTALLED"* ]]

    # No partial install: no command or skill files anywhere.
    [ -z "$(find .claude .opencode \( -name 'deviate-*' -o -name 'SKILL.md' \) 2>/dev/null)" ]
}

@test "setup git-ignores .deviate/ in a fresh consumer repo" {
    git init -q .

    run _deviate setup --agent opencode
    [ "$status" -eq 0 ]

    # The root ignore entry resolves .deviate/ as ignored.
    run git check-ignore .deviate/
    [ "$status" -eq 0 ]
    [[ "$output" == *".deviate/"* ]]

    grep -q "^\.deviate/$" .gitignore

    # .deviate/ is not reported as an untracked candidate.
    git add -A
    run git status --porcelain
    [[ "$output" != *".deviate"* ]]
}

@test "config schema has single timeout, no graphite, intact model routing" {
    run uv run --quiet --project "$REPO_ROOT" python -c '
from pydantic import ValidationError

from deviate.state.config import AgentConfig, DeviateConfig, resolve_phase_model

cfg = DeviateConfig()
assert cfg.timeout_seconds == 1800, cfg.timeout_seconds
assert "timeout" not in AgentConfig.model_fields, list(AgentConfig.model_fields)

try:
    DeviateConfig(graphite=True)
except ValidationError:
    pass
else:
    raise SystemExit("stale graphite key was silently accepted")

assert resolve_phase_model("judge", {"judge": "m1", "default": "m2"}) == "m1"
assert resolve_phase_model("red", {"default": "m2"}) == "m2"
assert resolve_phase_model("red", {}) is None
print("SCHEMA_OK")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"SCHEMA_OK"* ]]
}
