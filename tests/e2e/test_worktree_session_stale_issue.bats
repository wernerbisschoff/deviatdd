#!/usr/bin/env bats
#
# Leftover worktree session cannot empty the branch queue (ISS-ADH-024).
# AC-PLAN-001: leftover `active_issue_id` must not print `NO_PENDING_TASKS`
# when the branch issue still has unchecked tasks.
# AC-PLAN-002: empty branch-issue queue still prints `NO_PENDING_TASKS`
# and exits 0.
#
# Each test starts in a fresh tmpdir so `deviate` does not pick up the host
# repo's `.deviate/session.json` or `specs/` state. Git commands run only
# inside that tmpdir.

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    cd "$BATS_TEST_TMPDIR"
    unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR
}

teardown() {
    if [[ -n "$BATS_TEST_TMPDIR" && "$BATS_TEST_TMPDIR" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_TMPDIR"
    fi
}

_init_isolated_repo() {
    git init -q
    git config user.email "runner@test.local"
    git config user.name "Test Runner"
    git commit --allow-empty -q -m "initial"
    git checkout -q -b "feat/001-forge-layer/007-inventory-inspection"
}

_append_issue() {
    local issue_id="$1"
    local slug="$2"
    mkdir -p specs
    printf '%s\n' "{\"issue_id\": \"${issue_id}\", \"source_file\": \"specs/001-forge-layer/issues/${slug}.md\"}" >> specs/issues.jsonl
}

_seed_board() {
    local issue_id="$1"
    local slug="$2"
    local tid="$3"
    local status="$4"
    local feature_dir="specs/001-forge-layer/${slug}"
    mkdir -p "$feature_dir"
    if [[ "$status" == "COMPLETED" ]]; then
        printf '%s\n' "{\"id\": \"${tid}\", \"issue_id\": \"${issue_id}\", \"description\": \"done\", \"status\": \"COMPLETED\", \"execution_mode\": \"TDD\"}" > "${feature_dir}/tasks.jsonl"
        printf '%s\n' "# Tasks" "" "- [x] ${tid}: done" > "${feature_dir}/tasks.md"
    else
        printf '%s\n' "{\"id\": \"${tid}\", \"issue_id\": \"${issue_id}\", \"description\": \"pending\", \"status\": \"PENDING\", \"execution_mode\": \"TDD\"}" > "${feature_dir}/tasks.jsonl"
        printf '%s\n' "# Tasks" "" "- ${tid}: pending" > "${feature_dir}/tasks.md"
    fi
}

_write_leftover_session() {
    mkdir -p .deviate
    printf '%s\n' '{"current_phase": "IDLE", "active_issue_id": "001-006"}' > .deviate/session.json
}

@test "leftover session still consumes the branch issue queue" {
    _init_isolated_repo
    _append_issue "001-006" "006-spawn-form"
    _append_issue "001-007" "007-inventory-inspection"
    _seed_board "001-006" "006-spawn-form" "TSK-006-01" "PENDING"
    _seed_board "001-007" "007-inventory-inspection" "TSK-007-01" "PENDING"
    _write_leftover_session

    run deviate micro run --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" != *"NO_PENDING_TASKS"* ]]
    [[ "$output" == *"TSK-007-01"* ]]
}

@test "empty branch queue still prints NO_PENDING_TASKS and exits 0" {
    _init_isolated_repo
    _append_issue "001-006" "006-spawn-form"
    _append_issue "001-007" "007-inventory-inspection"
    _seed_board "001-006" "006-spawn-form" "TSK-006-01" "PENDING"
    _seed_board "001-007" "007-inventory-inspection" "TSK-007-01" "COMPLETED"
    _write_leftover_session

    run deviate micro run --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"NO_PENDING_TASKS"* ]]
}
