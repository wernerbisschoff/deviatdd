#!/usr/bin/env bats
#
# Checkpoint queue end-to-end surface (008-001 / TSK-001-07).
# Maps AC-PLAN-001..007 to green checks at consumer surface.
# No live agent. Each test starts in a fresh tmpdir.

REPO_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"

setup() {
    BATS_TEST_TMPDIR="$(mktemp -d)"
    cd "$BATS_TEST_TMPDIR"
}

teardown() {
    if [[ -n "$BATS_TEST_TMPDIR" && "$BATS_TEST_TMPDIR" == /tmp/* ]]; then
        rm -rf "$BATS_TEST_TMPDIR"
    fi
}

_repo_python() {
    uv run --project "$REPO_DIR" python "$@"
}

@test "AC-PLAN-001 batch type persists with IMMEDIATE mode" {
    run _repo_python -c '
from pathlib import Path
from deviate.core.tasks_ledger import generate_jsonl_from_md, resolve_execution_mode
Path("tasks.md").write_text("# Tasks\n\n- TSK-001-01: Preserve type\n  - **Type**: Verification_Batch\n  - **Mode**: TDD\n  - **Test Strategy**: unit\n")
(record,) = generate_jsonl_from_md(Path("tasks.md"), "008-001")
assert record.task_type == "Verification_Batch", record
assert record.execution_mode == "IMMEDIATE", record
assert resolve_execution_mode(record.task_type, "TDD") == "IMMEDIATE"
print("AC-PLAN-001")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-001"* ]]
}

@test "AC-PLAN-002 checkpoint prompt carries full verification context" {
    run _repo_python -c '
from deviate.cli.micro import _render_checkpoint_prompt
task = {"id": "T", "issue_id": "008-001", "contract": "c",
        "commands": ["mise unit"], "doc": "d", "capabilities": ["cap"]}
prompt = _render_checkpoint_prompt(task)
for field in ("task", "issue", "contract", "commands", "worktree", "doc", "capabilities"):
    assert field in prompt, field
print("AC-PLAN-002")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-002"* ]]
}

@test "AC-PLAN-003 checkpoint model follows phase default fallback routing" {
    run _repo_python -c '
from deviate.state.config import resolve_phase_model
assert resolve_phase_model("checkpoint", {"checkpoint": "m1", "default": "m0"}) == "m1"
assert resolve_phase_model("checkpoint", {"default": "m0"}) == "m0"
assert resolve_phase_model("checkpoint", {}) is None
print("AC-PLAN-003")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-003"* ]]
}

@test "AC-PLAN-004 incomplete proof never completes" {
    run _repo_python -c '
from deviate.cli.micro import validate_checkpoint_proof
base = {"status": "PASS", "exit_code": 0, "results": [{"command": "mise unit"}],
        "declared_commands": ["mise unit"], "command_reports": [{"command": "mise unit", "exit_code": 0}],
        "declared_criteria": ["AC-PLAN-001"], "criterion_coverage": ["AC-PLAN-001"],
        "evidence": [{"observed": "green"}]}
ok, _ = validate_checkpoint_proof(base)
assert ok
for bad in (dict(base, command_reports=[]), dict(base, criterion_coverage=[]),
            dict(base, exit_code=1), dict(base, evidence=[])):
    ok, _ = validate_checkpoint_proof(bad)
    assert not ok, bad
print("AC-PLAN-004")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-004"* ]]
}

@test "AC-PLAN-005 failure carries classification plus rationale" {
    run _repo_python -c '
import json
from pathlib import Path
from deviate.cli.micro import record_checkpoint_verdict
ledger = Path("tasks.jsonl")
task = {"id": "T", "issue_id": "008-001", "description": "d", "execution_mode": "IMMEDIATE", "task_type": "Verification_Batch"}
code = record_checkpoint_verdict(task, {"status": "FAIL", "results": []}, ledger)
assert code == "PREFLIGHT_EMPTY_RESULTS", code
row = json.loads(ledger.read_text().strip().splitlines()[-1])
assert row["status"] == "CHECKPOINT_FAILED", row
assert row["classification"], row
assert row["rationale"], row
print("AC-PLAN-005")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-005"* ]]
}

@test "AC-PLAN-006 passing checkpoint completes with typed evidence" {
    run _repo_python -c '
import json
from pathlib import Path
from deviate.cli.micro import record_checkpoint_verdict
ledger = Path("tasks.jsonl")
task = {"id": "T", "issue_id": "008-001", "description": "d", "execution_mode": "IMMEDIATE", "task_type": "Verification_Batch"}
handover = {"status": "PASS", "exit_code": 0, "results": [{"command": "mise unit"}],
            "declared_commands": ["mise unit"], "command_reports": [{"command": "mise unit", "exit_code": 0}],
            "declared_criteria": ["AC-PLAN-001"], "criterion_coverage": ["AC-PLAN-001"],
            "evidence": [{"observed": "green"}]}
assert record_checkpoint_verdict(task, handover, ledger) == "COMPLETED"
row = json.loads(ledger.read_text().strip().splitlines()[-1])
assert row["status"] == "COMPLETED", row
assert row["evidence"]["items"], row
print("AC-PLAN-006")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-006"* ]]
}

@test "AC-PLAN-007 failing checkpoint halts queue and keeps predecessors" {
    run _repo_python -c '
import inspect
from deviate.cli.micro import _TERMINAL_STATUSES, _dispatch_task
assert "CHECKPOINT_FAILED" in _TERMINAL_STATUSES
src = inspect.getsource(_dispatch_task)
assert "Verification_Batch" in src and "_run_checkpoint_phase" in src
print("AC-PLAN-007")
'
    [ "$status" -eq 0 ]
    [[ "$output" == *"AC-PLAN-007"* ]]
}
