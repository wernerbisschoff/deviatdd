"""CLI + prompt pins for ``deviate prune`` / ``/deviate-prune`` (FR-ADHOC-033)."""

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
    (tests / "test_099_behavioral.py").write_text(
        "def test_behavioral_ac_adhoc_099_01():\n"
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


def test_prune_post_completed_fixture_enforces_keep_drop(tmp_path: Path) -> None:
    _seed_completed_issue(tmp_path)
    before = snapshot_ledgers(tmp_path)
    with chdir(tmp_path):
        result = runner.invoke(cli, ["prune", "post", "--issue", "ISS-ADH-099"])
    assert result.exit_code == 0, result.output
    contract = json.loads(result.stdout)
    assert contract["status"] == "READY"
    assert contract["ledger_untouched"] is True
    issue_dir = tmp_path / "specs" / "adhoc" / "099-prune-fixture"
    assert not (issue_dir / "plan.md").exists()
    assert not (issue_dir / "tasks.md").exists()
    assert (issue_dir / "tasks.jsonl").is_file()
    assert (tmp_path / "specs" / "adhoc" / "explore.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "prd.md").is_file()
    assert (tmp_path / "specs" / "adhoc" / "issues" / "099-prune-fixture.md").is_file()
    assert not (tmp_path / "tests" / "test_099_spy.py").exists()
    assert (tmp_path / "tests" / "test_099_behavioral.py").is_file()
    assert snapshot_ledgers(tmp_path) == before
    assert not (tmp_path / "specs" / "_product" / "flows.jsonl").exists()


def test_prune_pre_in_flight_reports_noop(tmp_path: Path) -> None:
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


def test_prune_prompt_names_spec_test_cleanup_and_forbids_ledgers() -> None:
    text = _PROMPT.read_text(encoding="utf-8")
    assert "post-completed spec+test cleanup" in text.lower()
    assert "spy" in text and "impl" in text
    assert "behavioral" in text
    assert "ac" in text
    assert "plan.md" in text and "tasks.md" in text
    assert "issues.jsonl" in text
    assert "never" in text.lower() or "must not" in text.lower()
    assert "compact" in text.lower()
    assert "explore.md" in text
    assert "issues/*.md" in text or "issues/<" in text
    fm = text.split("---\n", 2)[1]
    assert "post-completed" in fm.lower()
    assert "stale test" not in fm


def test_skill_and_readme_describe_post_completed_cleanup() -> None:
    skill = _SKILL.read_text(encoding="utf-8")
    row = next(line for line in skill.splitlines() if "| `/deviate-prune`" in line)
    assert "stale test" not in row
    assert "COMPLETED" in row
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "post-COMPLETED spec+test cleanup" in readme
