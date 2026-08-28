"""CLI + prompt pins for manual ``deviate prune`` / ``/deviate-prune``."""

from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.prune import snapshot_ledgers

runner = CliRunner()

_PROMPT = Path("src/deviate/prompts/commands/deviate-prune.md")
_SKILL = Path("src/deviate/prompts/skills/deviatdd/SKILL.md")
_AUTO_RED = Path("src/deviate/prompts/auto/red.md")
_MANUAL_RED = Path("src/deviate/prompts/commands/deviate-red.md")
_MICRO = Path("src/deviate/cli/micro.py")


def _seed_completed_issue(root: Path) -> None:
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
    (tests / "test_099_keep.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.behavioral\n"
        "def test_public_ac_adhoc_099_01():\n"
        "    # ISS-ADH-099 public contract AC-ADHOC-099-01\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (tests / "test_099_spy.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.spy\n"
        "def test_internal_probe():\n"
        "    # ISS-ADH-099 implementation probe\n"
        "    assert True\n",
        encoding="utf-8",
    )


def test_prune_post_thins_tests_and_keeps_cycle_markdown(tmp_path: Path) -> None:
    _seed_completed_issue(tmp_path)
    before = snapshot_ledgers(tmp_path)
    with chdir(tmp_path):
        result = runner.invoke(cli, ["prune", "post", "--issue", "ISS-ADH-099"])
    assert result.exit_code == 0, result.output
    contract = json.loads(result.stdout)
    assert contract["status"] == "READY"
    assert contract["spec_deletes"] == []
    assert contract["ledger_untouched"] is True
    issue_dir = tmp_path / "specs" / "adhoc" / "099-prune-fixture"
    assert (issue_dir / "plan.md").is_file()
    assert (issue_dir / "tasks.md").is_file()
    assert (issue_dir / "tasks.jsonl").is_file()
    assert (tmp_path / "specs" / "adhoc" / "explore.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "prd.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "issues" / "099-prune-fixture.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert (tmp_path / "tests" / "test_099_keep.py").is_file()
    assert snapshot_ledgers(tmp_path) == before
    assert not (tmp_path / "specs" / "_product" / "flows.jsonl").exists()


def test_prune_pre_in_flight_reports_and_lists_no_spec_deletes(
    tmp_path: Path,
) -> None:
    _seed_completed_issue(tmp_path)
    ledger = tmp_path / "specs" / "issues.jsonl"
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace('"COMPLETED"', '"BACKLOG"'),
        encoding="utf-8",
    )
    with chdir(tmp_path):
        result = runner.invoke(cli, ["prune", "pre", "--issue", "ISS-ADH-099"])
    assert result.exit_code == 0, result.output
    contract = json.loads(result.stdout)
    assert contract["status"] == "IN_FLIGHT"
    assert contract["spec_deletes"] == []
    assert "BACKLOG" in contract["reason"]


def test_prune_post_rejects_ledger_compaction(tmp_path: Path) -> None:
    _seed_completed_issue(tmp_path)
    before = snapshot_ledgers(tmp_path)
    with chdir(tmp_path):
        result = runner.invoke(
            cli, ["prune", "post", "--issue", "ISS-ADH-099", "compact"]
        )
    assert result.exit_code == 1
    contract = json.loads(result.stdout)
    assert contract["status"] == "LEDGER_REWRITE_REJECTED"
    assert (tmp_path / "specs" / "adhoc" / "099-prune-fixture" / "plan.md").is_file()
    assert snapshot_ledgers(tmp_path) == before


def test_prune_prompt_is_manual_honeycomb_and_forbids_spec_deletes() -> None:
    text = _PROMPT.read_text(encoding="utf-8")
    assert "manual" in text.lower()
    assert "spy" in text and "impl" in text
    assert "behavioral" in text
    assert "ac" in text
    assert "pytest.mark" in text
    assert "untagged" in text.lower() or "no mark" in text.lower()
    assert "issues.jsonl" in text
    assert "never" in text.lower() or "must not" in text.lower()
    assert "compact" in text.lower()
    assert "explore.md" in text
    assert "plan.md" in text and "tasks.md" in text
    assert "must not delete" in text.lower() or "do not delete" in text.lower()
    assert "do not hook" in text.lower() or "manual invoke" in text.lower()
    fm = text.split("---\n", 2)[1]
    assert "stale test" not in fm
    assert "delete" not in fm.lower() or "cycle markdown" not in fm.lower()


def test_skill_and_readme_describe_manual_prune_not_auto_loop() -> None:
    skill = _SKILL.read_text(encoding="utf-8")
    row = next(line for line in skill.splitlines() if "| `/deviate-prune`" in line)
    assert "stale test" not in row
    assert "leftover `plan.md`" not in row
    assert "manual" in row.lower()
    success_loop = skill.split("## What NOT to do")[0]
    assert "deviate prune" not in success_loop
    assert (
        "/deviate-prune" not in success_loop.split("## Dispatch to slash commands")[0]
    )
    not_to_do = skill.split("## What NOT to do", 1)[1]
    assert "prune" in not_to_do.lower()
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "plan.md" in readme
    assert "manual" in readme.lower()


def test_red_prompts_stamp_honeycomb_marks() -> None:
    auto = _AUTO_RED.read_text(encoding="utf-8")
    assert "@pytest.mark.behavioral" in auto
    assert "@pytest.mark.spy" in auto
    assert "@pytest.mark.impl" in auto
    assert "Most RED tests" in auto or "most RED tests" in auto
    manual = _MANUAL_RED.read_text(encoding="utf-8")
    assert "auto/red.md" in manual


def test_micro_and_all_do_not_auto_invoke_prune() -> None:
    micro = _MICRO.read_text(encoding="utf-8")
    assert "apply_prune" not in micro
    assert "prune_app" not in micro
    assert "deviate prune" not in micro
