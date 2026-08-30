#!/usr/bin/env bats
#
# Installed Gate 3 review is comments-only (ISS-ADH-035). Unclaimed plan ACs
# stay in the contract as comment input (ISS-ADH-028 uncovered list). A brief
# with no named checks emits exactly `brief incomplete`.
# Constitution §3 E2E command: bats tests/e2e/.
#
# Each test starts in a fresh tmpdir so `deviate` does not pick up the host
# repo's `.deviate/session.json` or `specs/` state. Git commands run only
# inside that tmpdir. No agent. No `_run_pytest`.

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
    git checkout -q -b main
    git commit --allow-empty -q -m "initial"
}

_seed_issue_ledger() {
    mkdir -p specs/adhoc/issues
    printf '%s\n' '{"issue_id": "ISS-ADH-028", "source_file": "specs/adhoc/issues/028-coverage.md"}' > specs/issues.jsonl
    printf '%s\n' "# coverage issue" "AC-ADHOC-028-01 named check" > specs/adhoc/issues/028-coverage.md
}

_seed_plan() {
    mkdir -p specs/adhoc/028-coverage
    printf '%s\n' \
        "**Scenario AC-PLAN-001: first**" \
        "**Scenario AC-PLAN-002: second**" \
        > specs/adhoc/028-coverage/plan.md
}

_seed_completed_claim() {
    local task_id="$1"
    local token="$2"
    mkdir -p specs/adhoc/028-coverage
    printf '%s\n' "{\"id\": \"${task_id}\", \"issue_id\": \"ISS-ADH-028\", \"description\": \"${task_id}\", \"status\": \"COMPLETED\", \"execution_mode\": \"TDD\", \"acceptance_criteria\": [{\"criterion_id\": \"${token}\", \"verification_mode\": \"manual\"}]}" >> specs/adhoc/028-coverage/tasks.jsonl
}

_seed_pending_claim() {
    local task_id="$1"
    local token="$2"
    mkdir -p specs/adhoc/028-coverage
    printf '%s\n' "{\"id\": \"${task_id}\", \"issue_id\": \"ISS-ADH-028\", \"description\": \"${task_id}\", \"status\": \"PENDING\", \"execution_mode\": \"TDD\", \"acceptance_criteria\": [{\"criterion_id\": \"${token}\", \"verification_mode\": \"manual\"}]}" >> specs/adhoc/028-coverage/tasks.jsonl
}

_checkout_issue_branch() {
    git checkout -q -b "feat/adhoc/028-coverage"
}

_contract_field() {
    local field="$1"
    printf '%s' "$output" | python3 -c "import json,sys; print(json.load(sys.stdin)['${field}'])"
}

@test "no brief emits brief incomplete on installed review pre" {
    _init_isolated_repo

    run deviate review pre
    [ "$status" -ne 0 ]
    [ "$output" = "brief incomplete" ]
}

@test "full this-issue COMPLETED claims keep installed review pre READY" {
    _init_isolated_repo
    _checkout_issue_branch
    _seed_issue_ledger
    _seed_plan
    _seed_completed_claim "TSK-028-01" "AC-PLAN-001"
    _seed_completed_claim "TSK-028-02" "AC-PLAN-002"

    run deviate review pre
    [ "$status" -eq 0 ]
    status_value="$(_contract_field status)"
    [[ "$status_value" == "READY" || "$status_value" == "PASS" ]]
    [ "$(_contract_field coverage_complete)" = "True" ]
}

@test "unclaimed plan AC is comment input on installed review pre" {
    _init_isolated_repo
    _checkout_issue_branch
    _seed_issue_ledger
    _seed_plan
    _seed_completed_claim "TSK-028-01" "AC-PLAN-001"
    _seed_pending_claim "TSK-028-02" "AC-PLAN-002"

    run deviate review pre
    [ "$status" -eq 0 ]
    [ "$(_contract_field status)" = "READY" ]
    [[ "$output" == *"AC-PLAN-002"* ]]
    [ "$(_contract_field coverage_complete)" = "False" ]
}
