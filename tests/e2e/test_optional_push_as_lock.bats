#!/usr/bin/env bats
#
# Optional push-as-lock CLI surface — verifies that the installed `deviate`
# binary exposes `--local` on specify / meso run / run, `--no-claim-remote`
# on setup, keeps `--no-setup` as a distinct meso-run flag, and rejects
# `--no-local`. Behavioral claim/push tests live in pytest.
#
# Each test starts in a fresh tmpdir so `deviate` does not pick up the host
# repo's `.deviate/session.json` or `specs/` state.

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    cd "$BATS_TEST_TMPDIR"
}

teardown() {
    if [[ -n "$BATS_TEST_TMPDIR" && "$BATS_TEST_TMPDIR" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_TMPDIR"
    fi
}

# Typer sets force_terminal when GITHUB_ACTIONS (or FORCE_COLOR) is set, so CI
# help is colorized. Rich then styles the two dashes of each option as separate
# SGR runs (`ESC[1;36m-ESC[0mESC[1;36m-local`), so a raw substring `--local` is
# absent even though the visual text has the flag. Pytest already strips SGR in
# tests/test_cli/test_top_level_run.py for the same reason.
_plain() {
    printf '%s' "$output" | sed $'s/\x1b\\[[0-9;]*m//g'
}

@test "deviate specify --help exits 0 and prints --local" {
    run deviate specify --help
    [ "$status" -eq 0 ]
    [[ "$(_plain)" == *"--local"* ]]
}

@test "deviate meso run --help exits 0 and prints --local" {
    run deviate meso run --help
    [ "$status" -eq 0 ]
    [[ "$(_plain)" == *"--local"* ]]
}

@test "deviate run --help exits 0 and prints --local" {
    run deviate run --help
    [ "$status" -eq 0 ]
    [[ "$(_plain)" == *"--local"* ]]
}

@test "deviate setup --help exits 0 and prints --no-claim-remote" {
    run deviate setup --help
    [ "$status" -eq 0 ]
    [[ "$(_plain)" == *"--no-claim-remote"* ]]
}

@test "deviate meso run --help still prints --no-setup as a separate flag" {
    run deviate meso run --help
    [ "$status" -eq 0 ]
    [[ "$(_plain)" == *"--no-setup"* ]]
    [[ "$(_plain)" == *"--local"* ]]
}

@test "deviate run --no-local exits non-zero" {
    run deviate run --no-local
    [ "$status" -ne 0 ]
}
