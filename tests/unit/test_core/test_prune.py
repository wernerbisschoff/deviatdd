"""Keep/drop pins for manual ``/deviate-prune`` honeycomb thinning (FR-ADHOC-033)."""

from __future__ import annotations

from pathlib import Path

import pytest

from deviate.core.prune import (
    apply_prune,
    build_prune_plan,
    classify_test,
    extract_plan_ac_tokens,
    is_ledger_rewrite_request,
    snapshot_ledgers,
)


def test_classify_test_prefers_marks_and_name_tags() -> None:
    assert classify_test("test_behavioral_returns_ok") == "keep"
    assert classify_test("test_ac_adhoc_033_01") == "keep"
    assert classify_test("test_spy_internal_method") == "drop"
    assert classify_test("test_impl_calls_helper") == "drop"
    assert classify_test("test_public_contract", {"spy"}) == "drop"
    assert classify_test("test_spy_wrapped", {"behavioral"}) == "keep"
    assert classify_test("test_spy_wrapped", {"ac"}) == "keep"


def test_classify_test_untagged_does_not_auto_keep() -> None:
    assert classify_test("test_impact_is_public") == "drop"
    assert classify_test("test_something_generic") == "drop"
    assert classify_test("test_foo", body="def test_foo():\n    pass\n") == "drop"


def test_classify_test_untagged_body_drops_internal_probes() -> None:
    spy_body = "def test_foo():\n    helper.assert_called_with(1)\n"
    assert classify_test("test_foo", body=spy_body) == "drop"
    private_body = "def test_foo():\n    assert obj._state == 1\n"
    assert classify_test("test_foo", body=private_body) == "drop"
    patch_private = (
        "def test_foo():\n"
        "    with patch('mod._helper') as mocked:\n"
        "        mocked.return_value = 1\n"
    )
    assert classify_test("test_foo", body=patch_private) == "drop"
    mocker_spy = "def test_foo(mocker):\n    mocker.spy(mod, 'helper')\n"
    assert classify_test("test_foo", body=mocker_spy) == "drop"


def test_classify_test_untagged_body_keeps_public_io_and_ac() -> None:
    ac_body = (
        "def test_foo():\n"
        "    # AC-ADHOC-033-01 public contract\n"
        "    assert public_api(1) == 2\n"
    )
    assert classify_test("test_foo", body=ac_body) == "keep"
    public_io = (
        "def test_foo():\n"
        "    result = public_api(input_value)\n"
        "    assert result == expected\n"
    )
    assert classify_test("test_foo", body=public_io) == "keep"
    raises_io = (
        "def test_foo():\n    with pytest.raises(ValueError):\n        public_api(-1)\n"
    )
    assert classify_test("test_foo", body=raises_io) == "keep"


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
            "import pytest\n\n"
            "@pytest.mark.behavioral\n"
            "def test_public_ac_adhoc_099_01():\n"
            "    # ISS-ADH-099 public contract AC-ADHOC-099-01\n"
            "    assert True\n"
        )
    else:
        keep_body = (
            "import pytest\n\n"
            "@pytest.mark.behavioral\n"
            "def test_public_surface():\n"
            "    # ISS-ADH-099 public contract without the plan token\n"
            "    assert True\n"
        )
    (tests / "test_099_keep.py").write_text(keep_body, encoding="utf-8")
    (tests / "test_099_spy.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.spy\n"
        "def test_internal_call():\n"
        "    # ISS-ADH-099 implementation probe\n"
        "    helper.assert_called_with(1)\n",
        encoding="utf-8",
    )
    (tests / "test_099_untagged_spy.py").write_text(
        "def test_untagged_private_state():\n"
        "    # ISS-ADH-099 untagged private probe\n"
        "    assert widget._state == 1\n",
        encoding="utf-8",
    )
    (tests / "test_099_untagged_keep.py").write_text(
        "def test_untagged_public_io():\n"
        "    # ISS-ADH-099 untagged public input to output\n"
        "    result = public_api(1)\n"
        "    assert result == 2\n",
        encoding="utf-8",
    )
    return issue_dir


def test_apply_prune_thins_tests_and_never_unlinks_specs(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    before = snapshot_ledgers(tmp_path)
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status == "READY"
    assert plan.spec_deletes == []
    apply_prune(tmp_path, plan)

    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()
    assert (issue_dir / "design.md").is_file()
    assert (issue_dir / "data-model.md").is_file()
    assert (issue_dir / "tasks.jsonl").is_file()
    assert (tmp_path / "specs" / "adhoc" / "explore.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "prd.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "issues" / "099-prune-fixture.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert not (tmp_path / "tests" / "test_099_untagged_spy.py").exists()
    assert (tmp_path / "tests" / "test_099_keep.py").is_file()
    assert (tmp_path / "tests" / "test_099_untagged_keep.py").is_file()
    assert snapshot_ledgers(tmp_path) == before


def test_in_flight_issue_still_thins_tests_and_keeps_specs(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    ledger = tmp_path / "specs" / "issues.jsonl"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace('"COMPLETED"', '"SPECIFIED"'),
        encoding="utf-8",
    )
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status == "IN_FLIGHT"
    assert plan.spec_deletes == []
    apply_prune(tmp_path, plan)
    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert (tmp_path / "tests" / "test_099_keep.py").is_file()


def test_unmatched_plan_acs_do_not_block_or_delete_specs(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path, encode_ac=False)
    before = snapshot_ledgers(tmp_path)
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    assert plan.status != "ACS_NOT_ENCODED"
    apply_prune(tmp_path, plan)
    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert snapshot_ledgers(tmp_path) == before


def test_ready_does_not_remove_issue_dir(tmp_path: Path) -> None:
    issue_dir = _seed_completed_issue(tmp_path)
    (issue_dir / "tasks.jsonl").unlink()
    plan = build_prune_plan(tmp_path, "ISS-ADH-099")
    apply_prune(tmp_path, plan)
    assert issue_dir.is_dir()
    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()


def test_parse_other_language_tests_go_and_js(tmp_path: Path) -> None:
    """Regex fallback classifies non-Python test files (Go, JS) language-agnostically."""
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    go_file = tests / "main_test.go"
    go_file.write_text(
        "package main\n\n"
        "func TestBehavioral_ISS_099(t *testing.T) {\n"
        "    result := Add(1, 2)\n"
        "    if result != 3 { t.Fail() }\n"
        "}\n\n"
        "func TestSpyInternal(t *testing.T) {\n"
        "    helper.assert_called_with(1)\n"
        "}\n",
        encoding="utf-8",
    )
    js_file = tests / "thing.spec.js"
    js_file.write_text(
        "describe('thing', () => {\n"
        "    it('keeps public io', () => {\n"
        "        expect(publicApi(1)).toBe(2)\n"
        "    })\n"
        "})\n",
        encoding="utf-8",
    )
    from deviate.core.prune import _parse_other_test_items

    go_items = _parse_other_test_items(Path("main_test.go"), go_file.read_text())
    js_items = _parse_other_test_items(Path("thing.spec.js"), js_file.read_text())
    by_name = {item.name: item.kind for item in go_items}
    assert by_name.get("TestBehavioral_ISS_099") == "keep"
    assert by_name.get("TestSpyInternal") == "drop"
    assert len(js_items) >= 1


@pytest.mark.behavioral
def test_classify_marks_keep_drop_ac_plan_001() -> None:
    """AC-PLAN-001: spy/impl marks drop; behavioral/ac marks keep; keep-wins."""
    assert classify_test("test_neutral", {"behavioral"}) == "keep"
    assert classify_test("test_neutral", {"ac"}) == "keep"
    assert classify_test("test_neutral", {"spy"}) == "drop"
    assert classify_test("test_neutral", {"impl"}) == "drop"
    assert classify_test("test_spy_probe", {"behavioral", "spy"}) == "keep"
    assert classify_test("test_impl_helper", {"ac", "impl"}) == "keep"


@pytest.mark.behavioral
def test_classify_unknown_mark_falls_through_ac_plan_002() -> None:
    """AC-PLAN-002: unknown marks never auto-keep; body heuristics decide."""
    public = "def test_foo():\n    assert public_api(1) == 2\n"
    bare = "def test_foo():\n    pass\n"
    assert classify_test("test_foo", {"slow"}, body=public) == "keep"
    assert classify_test("test_foo", {"slow"}, body=bare) == "drop"
    assert classify_test("test_foo", {"slow"}, body="") == "drop"


@pytest.mark.behavioral
def test_classify_sibling_mocks_drop_ac_plan_002() -> None:
    """AC-PLAN-002: untagged sibling mocks drop even with a public assert."""
    magic = (
        "def test_foo():\n"
        "    helper = MagicMock()\n"
        "    result = helper(1)\n"
        "    assert result == 2\n"
    )
    assert classify_test("test_foo", body=magic) == "drop"
    sibling_patch = (
        "def test_foo():\n"
        '    with patch("sibling.helper") as mocked:\n'
        "        mocked.return_value = 1\n"
        "        assert mocked(1) == 1\n"
    )
    assert classify_test("test_foo", body=sibling_patch) == "drop"


@pytest.mark.behavioral
def test_classify_empty_and_bare_bodies_drop_ac_plan_002() -> None:
    """AC-PLAN-002: empty or bare bodies never auto-keep."""
    assert classify_test("test_foo", body="") == "drop"
    assert classify_test("test_foo", body="   \n") == "drop"
    assert classify_test("test_foo", body="def test_foo():\n    x = 1\n") == "drop"
