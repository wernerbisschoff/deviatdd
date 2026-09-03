#!/usr/bin/env bats
#
# E2E suite — TSK-033-05 (ISS-ADH-033). Verifies manual prune on a
# fixture issue through the real CLI:
#
#   1. AC-PLAN-001 (US-033-01) happy path — spy/impl thinned,
#      behavioral stays, plan.md/tasks.md/ledgers intact.
#   2. AC-PLAN-005 (US-033-02) critical failure — ledger-compaction
#      intent rejected with LEDGER_REWRITE_REJECTED, non-zero exit,
#      zero writes.
#
# Each test starts in a fresh tmpdir so `deviate` never touches the
# real repo. No test is skipped: a missing binary fails loud.

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"

setup() {
    command -v uv >/dev/null || { echo "uv binary missing — cannot run deviate" >&2; return 1; }
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

seed_fixture() {
    mkdir -p specs/adhoc/issues specs/adhoc/099-prune-fixture tests
    printf '# ISS-ADH-099 fixture\n' > specs/adhoc/issues/099-prune-fixture.md
    printf '## Acceptance Contract\n\n**Scenario AC-ADHOC-099-01: keep**\n' > specs/adhoc/099-prune-fixture/plan.md
    printf '# tasks\n' > specs/adhoc/099-prune-fixture/tasks.md
    printf '# leftover cycle markdown\n' > specs/adhoc/099-prune-fixture/design.md
    printf '{"id":"TSK-099-01","status":"COMPLETED"}\n' > specs/adhoc/099-prune-fixture/tasks.jsonl
    printf '{"issue_id":"ISS-ADH-099","type":"feature","title":"prune fixture","status":"COMPLETED","timestamp":"2026-08-27T00:00:00Z","source_file":"specs/adhoc/issues/099-prune-fixture.md","blocked_by":[],"coordinates_with":[]}\n' > specs/issues.jsonl
    printf 'import pytest\n\n@pytest.mark.behavioral\ndef test_public_ac_adhoc_099_01():\n    # ISS-ADH-099 public contract AC-ADHOC-099-01\n    assert True\n' > tests/test_099_keep.py
    printf 'import pytest\n\n@pytest.mark.spy\ndef test_internal_call():\n    # ISS-ADH-099 implementation probe\n    helper.assert_called_with(1)\n' > tests/test_099_spy.py
    printf 'def test_untagged_private_state():\n    # ISS-ADH-099 untagged private probe\n    assert widget._state == 1\n' > tests/test_099_untagged_spy.py
    printf 'def test_untagged_public_io():\n    # ISS-ADH-099 untagged public input to output\n    result = public_api(1)\n    assert result == 2\n' > tests/test_099_untagged_keep.py
}

@test "prune happy path thins spies and keeps behavioral, plan, tasks, ledgers" {
    seed_fixture
    before_issues="$(sha256sum specs/issues.jsonl | cut -d' ' -f1)"
    before_tasks="$(sha256sum specs/adhoc/099-prune-fixture/tasks.jsonl | cut -d' ' -f1)"

    run _deviate prune pre --issue ISS-ADH-099
    [ "$status" -eq 0 ]

    run _deviate prune post --issue ISS-ADH-099
    [ "$status" -eq 0 ]

    [ ! -e tests/test_099_spy.py ]
    [ ! -e tests/test_099_untagged_spy.py ]
    [ -f tests/test_099_keep.py ]
    [ -f tests/test_099_untagged_keep.py ]
    [ -f specs/adhoc/099-prune-fixture/plan.md ]
    [ -f specs/adhoc/099-prune-fixture/tasks.md ]
    [ "$(sha256sum specs/issues.jsonl | cut -d' ' -f1)" = "$before_issues" ]
    [ "$(sha256sum specs/adhoc/099-prune-fixture/tasks.jsonl | cut -d' ' -f1)" = "$before_tasks" ]
}

@test "prune rejects ledger-compaction intent with zero writes" {
    seed_fixture
    before_issues="$(sha256sum specs/issues.jsonl | cut -d' ' -f1)"
    before_tasks="$(sha256sum specs/adhoc/099-prune-fixture/tasks.jsonl | cut -d' ' -f1)"

    run _deviate prune pre --issue ISS-ADH-099 compact specs/issues.jsonl
    [ "$status" -ne 0 ]
    [[ "$output" == *"LEDGER_REWRITE_REJECTED"* ]]

    run _deviate prune post --issue ISS-ADH-099 compact specs/issues.jsonl
    [ "$status" -ne 0 ]
    [[ "$output" == *"LEDGER_REWRITE_REJECTED"* ]]

    [ -f tests/test_099_spy.py ]
    [ -f tests/test_099_untagged_spy.py ]
    [ -f tests/test_099_keep.py ]
    [ -f tests/test_099_untagged_keep.py ]
    [ "$(sha256sum specs/issues.jsonl | cut -d' ' -f1)" = "$before_issues" ]
    [ "$(sha256sum specs/adhoc/099-prune-fixture/tasks.jsonl | cut -d' ' -f1)" = "$before_tasks" ]
}
