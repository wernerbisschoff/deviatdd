"""Keep/drop pins for post-COMPLETED ``/deviate-prune`` (FR-ADHOC-033)."""

from __future__ import annotations

from pathlib import Path

from deviate.core.prune import (
    apply_prune,
    build_prune_plan,
    classify_test,
    extract_plan_ac_tokens,
    is_ledger_rewrite_request,
    snapshot_ledgers,
)


def test_classify_test_keeps_behavioral_and_ac_over_spy() -> None:
    assert classify_test("test_behavioral_returns_ok") == "keep"
    assert classify_test("test_ac_adhoc_033_01") == "keep"
    assert classify_test("test_spy_internal_method") == "drop"
    assert classify_test("test_impl_calls_helper") == "drop"
    assert classify_test("test_impact_is_public") == "keep"
    assert classify_test("test_public_contract", {"spy"}) == "drop"
    assert classify_test("test_spy_wrapped", {"behavioral"}) == "keep"
    assert classify_test("test_spy_wrapped", {"ac"}) == "keep"


def test_extract_plan_ac_tokens_reads_plan_and_adhoc_forms() -> None:
    text = (
        "### AC-PLAN-001: visible\nUpstream: AC-ADHOC-033-01\nAlso AC-PLAN-001 again\n"
    )
    assert extract_plan_ac_tokens(text) == ["AC-PLAN-001", "AC-ADHOC-033-01"]


def test_ledger_rewrite_request_is_rejected() -> None:
    assert is_ledger_rewrite_request("please compact specs/issues.jsonl")
    assert is_ledger_rewrite_request("squash the tasks.jsonl audit trail")
    assert is_ledger_rewrite_request("rewrite flows.jsonl")
    assert not is_ledger_rewrite_request("prune ISS-ADH-033 after COMPLETED")


def _seed_completed_issue(root: Path, *, encode_ac: bool = True) -> Path:
    issue_dir = root / "specs" / "adhoc" / "099-prune-fixture"
    issue_dir.mkdir(parents=True)
    (root / "specs" / "adhoc" / "issues").mkdir(parents=True)
    (root / "specs" / "adhoc" / "issues" / "099-prune-fixture.md").write_text(
        "# ISS-ADH-099 fixture\n", encoding="utf-8"
    )
    (root / "specs" / "adhoc" / "explore.md").write_text(
        "# explore\n", encoding="utf-8"
    )
    (root / "specs" / "adhoc" / "prd.md").write_text("# prd\n", encoding="utf-8")
    (issue_dir / "plan.md").write_text(
        "## Acceptance Contract\n\n**Scenario AC-ADHOC-099-01: keep**\n",
        encoding="utf-8",
    )
    (issue_dir / "tasks.md").write_text("# tasks\n", encoding="utf-8")
    (issue_dir / "design.md").write_text("# leftover design\n", encoding="utf-8")
    (issue_dir / "data-model.md").write_text("# leftover model\n", encoding="utf-8")
    (issue_dir / "tasks.jsonl").write_text(
        '{"id":"TSK-099-01","status":"COMPLETED"}\n', encoding="utf-8"
    )
    (root / "specs" / "issues.jsonl").write_text(
        '{"issue_id":"ISS-ADH-099","type":"feature","title":"prune fixture",'
        '"status":"COMPLETED","timestamp":"2026-08-27T00:00:00Z",'
        '"source_file":"specs/adhoc/issues/099-prune-fixture.md",'
        '"blocked_by":[],"coordinates_with":[]}\n',
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    if encode_ac:
        keep_body = (
            "def test_behavioral_ac_adhoc_099_01():\n"
            "    # ISS-ADH-099 public contract AC-ADHOC-099-01\n"
            "    assert True\n"
        )
    else:
        keep_body = (
            "def test_behavioral_public_surface():\n"
            "    # ISS-ADH-099 public contract without the plan token\n"
            "    assert True\n"
        )
    (tests / "test_099_behavioral.py").write_text(keep_body, encoding="utf-8")
    (tests / "test_099_spy.py").write_text(
        "def test_spy_internal_call():\n"
        "    # ISS-ADH-099 implementation probe\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return issue_dir


def test_completed_issue_drops_cycle_markdown_and_spies(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    before = snapshot_ledgers(tmp_path)
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status == "READY"
    apply_prune(tmp_path, plan)

    assert not (issue_dir / "plan.md").exists()
    assert not (issue_dir / "tasks.md").exists()
    assert not (issue_dir / "design.md").exists()
    assert not (issue_dir / "data-model.md").exists()
    assert (issue_dir / "tasks.jsonl").is_file()
    assert (tmp_path / "specs" / "adhoc" / "explore.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "prd.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "issues" / "099-prune-fixture.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert (tmp_path / "tests" / "test_099_behavioral.py").is_file()
    assert snapshot_ledgers(tmp_path) == before
    assert not (tmp_path / "specs" / "_product" / "flows.jsonl").exists()


def test_in_flight_issue_is_noop_for_spec_deletion(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    ledger = tmp_path / "specs" / "issues.jsonl"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace('"COMPLETED"', '"SPECIFIED"'),
        encoding="utf-8",
    )
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status == "IN_FLIGHT"
    apply_prune(tmp_path, plan)
    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert (tmp_path / "tests" / "test_099_behavioral.py").is_file()


def test_unmatched_plan_acs_halt_without_spec_deletes(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path, encode_ac=False)
    before = snapshot_ledgers(tmp_path)
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status == "ACS_NOT_ENCODED"
    assert plan.unmatched_acs == ["AC-ADHOC-099-01"]
    apply_prune(tmp_path, plan)
    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()
    assert snapshot_ledgers(tmp_path) == before


def test_completed_without_plan_skips_ac_gate(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    (issue_dir / "plan.md").unlink()
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status == "READY"
    apply_prune(tmp_path, plan)
    assert not (issue_dir / "tasks.md").exists()


def test_empty_issue_dir_is_removed_after_deletes(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    (issue_dir / "tasks.jsonl").unlink()
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    apply_prune(tmp_path, plan)
    assert not issue_dir.exists()


def test_compact_intent_rejects_without_mutations(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    before = snapshot_ledgers(tmp_path)
    plan = build_prune_plan(
        tmp_path, "ISS-ADH-099", intent="compact specs/issues.jsonl"
    )
    assert plan.status == "LEDGER_REWRITE_REJECTED"
    apply_prune(tmp_path, plan)
    assert (issue_dir / "plan.md").is_file()
    assert (tmp_path / "tests" / "test_099_spy.py").is_file()
    assert snapshot_ledgers(tmp_path) == before
