#!/usr/bin/env bats
#
# CLI smoke suite — verifies that the installed `deviate` binary is on PATH,
# reports the expected version, and that every documented subcommand accepts
# `--help`. Pure installation / packaging smoke; behavioral tests live in
# `tests/` (pytest). Runs in CI under `.github/workflows/ci.yml`.
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

@test "deviate --version exits 0 and prints semver" {
    run deviate --version
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^deviate\ [0-9]+\.[0-9]+\.[0-9]+$ ]]
}

@test "deviate --help exits 0 and shows DeviaTDD brand" {
    run deviate --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"DeviaTDD"* ]]
}

@test "every documented macro-layer subcommand is on PATH" {
    for cmd in explore research prd shard; do
        run deviate "$cmd" --help
        [ "$status" -eq 0 ] || { echo "deviate $cmd --help failed"; false; }
    done
}

@test "every documented micro-layer subcommand is on PATH" {
    for cmd in red green yellow judge refactor execute; do
        run deviate "$cmd" --help
        [ "$status" -eq 0 ] || { echo "deviate $cmd --help failed"; false; }
    done
}

@test "every documented meso-layer subcommand is on PATH" {
    for cmd in specify plan tasks pr; do
        run deviate "$cmd" --help
        [ "$status" -eq 0 ] || { echo "deviate $cmd --help failed"; false; }
    done
}

@test "explore pre and post subcommands are reachable" {
    run deviate explore pre --help
    [ "$status" -eq 0 ]
    run deviate explore post --help
    [ "$status" -eq 0 ]
}

@test "deviate rejects unknown subcommand with non-zero exit" {
    run deviate this-command-does-not-exist
    [ "$status" -ne 0 ]
}
