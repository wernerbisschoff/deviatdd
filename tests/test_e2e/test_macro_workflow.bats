setup() {
    export BATS_TEST_DIRNAME=$(mktemp -d)
    cd "$BATS_TEST_DIRNAME"
    mkdir -p .deviate specs/001-deviate-cli-python
    echo '{"current_phase":"IDLE","timestamp":"2026-01-01T00:00:00Z"}' > .deviate/session.json
}

teardown() {
    if [[ -n "$BATS_TEST_DIRNAME" && "$BATS_TEST_DIRNAME" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_DIRNAME"
    fi
}

assert_session_phase() {
    local expected="$1"
    local actual
    actual=$(jq -r '.current_phase' .deviate/session.json)
    [[ "$actual" == "$expected" ]]
}

assert_ledger_count() {
    local expected="$1"
    local actual
    actual=$(wc -l < specs/issues.jsonl 2>/dev/null || echo 0)
    actual=${actual// /}
    [[ "$actual" -eq "$expected" ]]
}

scaffold_artifacts() {
    local spec_dir="specs/001-deviate-cli-python"
    for name in "$@"; do
        echo "# $name" > "$spec_dir/$name"
    done
}

run_full_cycle() {
    local epic_slug="${1:-001-deviate-cli-python}"
    run deviate cli explore "$epic_slug"
    [ "$status" -eq 0 ] || return 1
    run deviate cli research "$epic_slug"
    [ "$status" -eq 0 ] || return 1
    run deviate cli prd "$epic_slug"
    [ "$status" -eq 0 ] || return 1
    run deviate cli shard "$epic_slug"
    [ "$status" -eq 0 ] || return 1
}

@test "deviate explore accepts --help" {
    run deviate cli explore --help
    [ "$status" -eq 0 ]
}

@test "explore transitions state to EXPLORE" {
    run deviate cli explore 001-deviate-cli-python
    [ "$status" -eq 0 ]
    assert_session_phase "EXPLORE"
}

@test "prd with missing research.md fails with HALTED" {
    scaffold_artifacts "explore.md"
    echo '{"current_phase":"RESEARCH","timestamp":"2026-01-01T00:00:00Z"}' > .deviate/session.json

    run deviate cli prd 001-deviate-cli-python
    [ "$status" -ne 0 ]
    echo "$output" | grep -q "PRD_HALTED"
    echo "$output" | grep -q "research.md"
}

@test "full cycle produces ledger entry" {
    scaffold_artifacts "explore.md" "research.md" "prd.md"
    run_full_cycle
    assert_session_phase "IDLE"
    [ -f specs/issues.jsonl ]
    assert_ledger_count 1
    run jq -r '.status' specs/issues.jsonl
    [ "$output" = "SHARDED" ]
}

@test "session state survives across CLI invocations" {
    scaffold_artifacts "explore.md"

    run deviate cli explore 001-deviate-cli-python
    [ "$status" -eq 0 ]
    assert_session_phase "EXPLORE"

    scaffold_artifacts "research.md"

    run deviate cli research 001-deviate-cli-python
    [ "$status" -eq 0 ]
    assert_session_phase "RESEARCH"
}

@test "shard idempotently skips duplicate" {
    scaffold_artifacts "explore.md" "research.md" "prd.md"
    run_full_cycle
    assert_ledger_count 1
    assert_session_phase "IDLE"

    echo '{"current_phase":"PRD","timestamp":"2026-01-01T00:00:00Z"}' > .deviate/session.json

    run deviate cli shard 001-deviate-cli-python
    [ "$status" -eq 0 ]
    echo "$output" | grep -q "LEDGER_IDEMPOTENT"
    assert_ledger_count 1
}

@test "handle missing .deviate directory gracefully" {
    rm -rf .deviate
    run deviate cli explore 001-deviate-cli-python
    [ "$status" -ne 0 ]
    echo "$output" | grep -q "EXPLORE_HALTED"
    echo "$output" | grep -q ".deviate"
}

@test "handle non-ASCII project path characters" {
    local epic_slug="001-déviate-cli-python"
    local spec_dir="specs/$epic_slug"
    mkdir -p "$spec_dir"
    echo "# explore.md" > "$spec_dir/explore.md"
    echo "# research.md" > "$spec_dir/research.md"
    echo "# prd.md" > "$spec_dir/prd.md"

    run deviate cli explore "$epic_slug"
    [ "$status" -eq 0 ]

    run deviate cli research "$epic_slug"
    [ "$status" -eq 0 ]

    run deviate cli prd "$epic_slug"
    [ "$status" -eq 0 ]

    run deviate cli shard "$epic_slug"
    [ "$status" -eq 0 ]
    assert_session_phase "IDLE"
}
