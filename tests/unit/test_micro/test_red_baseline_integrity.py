"""Route GREEN test tampering separately from defective RED tests."""

import pytest

from deviate.core.agent import AgentBackend, HandoverManifest
from deviate.core.judge_policy import coerce_judge_action
from tests.helpers.cycle_driver import (
    CycleTask,
    green_test_tampering_steps,
    load_verdicts,
    red_files,
    run_scripted_cycle,
    seed_cycle_repo,
)


@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_green_test_tampering_retains_red(tmp_git_repo, monkeypatch, mode):
    task = CycleTask(
        task_id="TSK-160-01", description="Preserve valid RED tests", ac="AC-PLAN-001"
    )
    seeded = seed_cycle_repo(tmp_git_repo, tasks=[task])
    result = run_scripted_cycle(
        seeded,
        green_test_tampering_steps(task.task_id, ac=task.ac),
        monkeypatch,
        mode=mode,
    )
    assert result.error is None, result.output
    assert result.phases == ["RED", "GREEN", "JUDGE", "GREEN", "JUDGE", "REFACTOR"]
    for path, body in red_files(task.task_id).items():
        assert (tmp_git_repo / path).read_text() == body
    rejection = load_verdicts(tmp_git_repo, seeded.issue_id, task.task_id)[0]
    assert rejection["next_action"] == "revert_green"
    assert rejection["test_integrity"] == "FAIL"
    assert rejection["red_baseline_integrity"] == "PASS"
    assert result.statuses_for(task.task_id)[-1] == "COMPLETED"


@pytest.mark.parametrize(
    "baseline, integrity, failure_kind, expected",
    [
        ("PASS", "FAIL", "", "revert_green"),
        ("FAIL", "PASS", "", "revert_red"),
        (None, "FAIL", "", "revert_red"),
        ("PASS", "FAIL", "test_defect", "revert_red"),
        ("PASS", "FAIL", "no_failing_test", "revert_red"),
        ("FAIL", "FAIL", "mechanical", "revert_green"),
    ],
)
def test_baseline_classification_preserves_legacy_and_overlays(
    baseline, integrity, failure_kind, expected
):
    manifest = HandoverManifest(
        phase="JUDGE",
        status="FAILURE",
        next_action="revert_green",
        red_baseline_integrity=baseline,
        evaluation={"test_integrity": integrity},
    )
    assert (
        coerce_judge_action(manifest, "COMPLIANCE_VIOLATION", failure_kind=failure_kind)
        == expected
    )


def test_invalid_baseline_classification_is_a_manifest_error():
    manifest = AgentBackend.parse_output(
        "phase: JUDGE\nstatus: FAILURE\nred_baseline_integrity: maybe\n",
        "stub",
    )
    assert any("red_baseline_integrity" in error for error in manifest.parse_errors)
