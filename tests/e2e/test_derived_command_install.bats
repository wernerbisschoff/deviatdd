#!/usr/bin/env bats
#
# E2E smoke suite — TSK-016-05. Verifies the single-source prompt derivation
# end-to-end through the real CLI install path:
#
#   1. `deviate setup` installs the derived manual slash commands whose middle
#      body stays byte-identical to the canonical `auto/{phase}.md` core.
#   2. Re-running `deviate setup` rewrites nothing (idempotency contract).
#
# Repo-level drift guards re-invoking `install_command` live in
# `tests/test_meso/test_auto_prompt_templates.py`; this suite adds no pytest.
# The 11 overlapping phases (`_OVERLAPPING_PHASES` in `commands.py`) have an
# auto counterpart; the 15 commands-only prompts are exempt.
#
# Each test starts in a fresh tmpdir so `deviate setup` provisions the agent
# command dirs from scratch and never reads the host repo's state.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
AUTO_ROOT="$REPO_ROOT/src/deviate/prompts/auto"
OVERLAPPING_PHASES=(red green refactor judge execute plan tasks explore research prd shard)

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    cd "$BATS_TEST_TMPDIR"
}

teardown() {
    if [[ -n "$BATS_TEST_TMPDIR" && "$BATS_TEST_TMPDIR" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_TMPDIR"
    fi
}

@test "deviate setup installs derived commands whose middle equals the auto core" {
    run deviate setup --agent claude
    [ "$status" -eq 0 ]
    [ -f .claude/commands/deviate-red.md ]

    for phase in "${OVERLAPPING_PHASES[@]}"; do
        auto_len=$(wc -c < "$AUTO_ROOT/$phase.md")
        awk '/^<system_instructions>/{f=1} f{print}' ".claude/commands/deviate-$phase.md" \
            | head -c "$auto_len" > "$BATS_TEST_TMPDIR/middle"
        cmp -s "$BATS_TEST_TMPDIR/middle" "$AUTO_ROOT/$phase.md" || {
            echo "deviate-$phase.md middle diverged from auto/$phase.md"
            false
        }
    done

    grep -q "<context>" .claude/commands/deviate-red.md
    grep -q 'status: "PASS"' .claude/commands/deviate-red.md
    # auto/red.md mentions `status: "FAIL"` only as a "NEVER use"
    # instruction; the derived file must not emit it as a standalone line.
    if awk '/^[[:space:]]*status: "FAIL"[[:space:]]*$/{found=1}
        END { if (found) exit 1 }' .claude/commands/deviate-red.md; then
        :
    else
        echo "deviate-red.md emits a standalone status: \"FAIL\" handover line"
        false
    fi
}

@test "deviate setup reinstall is idempotent (SKIP, file unchanged)" {
    run deviate setup --agent claude
    [ "$status" -eq 0 ]
    cp .claude/commands/deviate-red.md "$BATS_TEST_TMPDIR/before.md"

    run deviate setup --agent claude
    [ "$status" -eq 0 ]
    [[ "$output" != *"INSTALL"* ]]
    [[ "$output" == *"SKIP"* ]]
    cmp -s "$BATS_TEST_TMPDIR/before.md" .claude/commands/deviate-red.md
}