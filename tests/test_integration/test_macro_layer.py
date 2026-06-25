from __future__ import annotations

import json
from contextlib import chdir
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from deviate.state.config import SessionState

runner = CliRunner()


class TestExplorePre:
    def test_explore_pre_creates_explore_dir(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")
            spec_root = Path("specs")
            spec_root.mkdir(parents=True)
            (spec_root / "constitution.md").write_text(
                "# Constitution\n", encoding="utf-8"
            )

            result = runner.invoke(
                cli,
                ["explore", "pre", "Implement authentication", "--slug", "test-slug"],
            )
            assert result.exit_code == 0, result.output

            explore_dir = spec_root / "explore"
            assert explore_dir.is_dir(), f"Explore dir {explore_dir} should exist"
            assert (explore_dir / "test-slug.md").parent.exists(), (
                f"Explore file test-slug.md parent {explore_dir} should exist"
            )

            ledger_path = spec_root / "issues.jsonl"
            assert not ledger_path.exists(), (
                "explore pre should not append to issues ledger"
            )

    def test_explore_pre_rejects_missing_constitution(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="IDLE")
            session.save(dot_dir / "session.json")

            result = runner.invoke(
                cli,
                ["explore", "pre", "No constitution", "--slug", "no-const"],
            )
            assert result.exit_code != 0
            assert (
                "CONSTITUTION" in result.output.upper()
                or "HALTED" in result.output.upper()
            )


class TestResearchPre:
    def test_research_pre_gates_on_explore_md(self, mock_workspace: Path) -> None:
        spec_root = mock_workspace / "specs"
        explore_dir = spec_root / "explore"
        explore_dir.mkdir(parents=True)

        dot_dir = mock_workspace / ".deviate"
        session = SessionState(current_phase="EXPLORE")
        session.save(dot_dir / "session.json")

        assert not (explore_dir / "no-such-slug.md").exists()

        result = runner.invoke(cli, ["research", "pre", "--slug", "no-such-slug"])
        assert result.exit_code != 0
        assert "explore.md" in result.output or "HALTED" in result.output.upper()

    def test_research_pre_accepts_when_explore_md_exists(
        self, mock_workspace: Path
    ) -> None:
        spec_root = mock_workspace / "specs"
        explore_dir = spec_root / "explore"
        explore_dir.mkdir(parents=True)
        (explore_dir / "test-research.md").write_text(
            "# Explore results\n", encoding="utf-8"
        )
        (spec_root / "constitution.md").write_text("# Constitution\n", encoding="utf-8")

        dot_dir = mock_workspace / ".deviate"
        session = SessionState(current_phase="EXPLORE")
        session.save(dot_dir / "session.json")

        result = runner.invoke(cli, ["research", "pre", "--slug", "test-research"])
        assert result.exit_code == 0, result.output
        loaded = SessionState.load(dot_dir / "session.json")
        assert loaded.current_phase == "RESEARCH"


class TestPrdPost:
    def test_prd_post_validates_manifest(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            bucket_dir = spec_root / "test-prd"
            bucket_dir.mkdir(parents=True)
            prd_content = (
                "# PRD\nFR-001: Test requirement\nFR-002: Another requirement\n"
            )
            (bucket_dir / "prd.md").write_text(prd_content, encoding="utf-8")
            (spec_root / "constitution.md").write_text(
                "# Constitution\n", encoding="utf-8"
            )

            manifest = bucket_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {"epic_slug": "test-prd", "prd_requirements": ["FR-001", "FR-002"]}
                ),
                encoding="utf-8",
            )

            result = runner.invoke(cli, ["prd", "post", str(manifest)])
            assert result.exit_code == 0, result.output

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "PRD"

    def test_prd_post_halts_on_invalid_gherkin(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="PRD")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            bucket_dir = spec_root / "test-prd"
            bucket_dir.mkdir(parents=True)
            prd_content = (
                "# PRD\n"
                "**AC-1-01: AC missing the When clause**\n"
                "\n"
                "- **Given**: A precondition\n"
                "- **Then**: An outcome\n"
            )
            (bucket_dir / "prd.md").write_text(prd_content, encoding="utf-8")
            (spec_root / "constitution.md").write_text(
                "# Constitution\n", encoding="utf-8"
            )

            manifest = bucket_dir / "manifest.json"
            manifest.write_text(
                json.dumps({"epic_slug": "test-prd", "prd_requirements": []}),
                encoding="utf-8",
            )

            result = runner.invoke(cli, ["prd", "post", str(manifest)])
            assert result.exit_code != 0, result.output
            assert "PRD_HALTED" in result.output
            assert "When" in result.output

    def test_prd_post_rejects_invalid_manifest(self, mock_workspace: Path) -> None:
        spec_root = mock_workspace / "specs"
        bucket_dir = spec_root / "test-prd"
        bucket_dir.mkdir(parents=True)

        dot_dir = mock_workspace / ".deviate"
        session = SessionState(current_phase="PRD")
        session.save(dot_dir / "session.json")

        manifest = bucket_dir / "manifest.json"
        manifest.write_text("not valid json", encoding="utf-8")

        result = runner.invoke(cli, ["prd", "post", str(manifest)])
        assert result.exit_code != 0


class TestShardPost:
    def test_shard_post_registers_backlog_issues(self, tmp_git_repo: Path) -> None:
        with chdir(tmp_git_repo):
            dot_dir = Path(".deviate")
            dot_dir.mkdir(parents=True)
            session = SessionState(current_phase="SHARD")
            session.save(dot_dir / "session.json")

            spec_root = Path("specs")
            bucket_dir = spec_root / "test-shard"
            bucket_dir.mkdir(parents=True)

            issues_data = [
                {
                    "issue_id": "ISS-ADH-002",
                    "type": "feature",
                    "title": "Sharded issue 1",
                    "status": "DRAFT",
                    "source_file": "specs/test-shard/issues/issue-1.md",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "issue_id": "ISS-ADH-001",
                    "type": "feature",
                    "title": "Sharded issue 2",
                    "status": "DRAFT",
                    "source_file": "specs/test-shard/issues/issue-2.md",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            ]
            manifest = bucket_dir / "manifest.json"
            manifest.write_text(json.dumps({"issues": issues_data}), encoding="utf-8")

            result = runner.invoke(cli, ["shard", "post", str(manifest)])
            assert result.exit_code == 0, result.output

            ledger_path = spec_root / "issues.jsonl"
            assert ledger_path.exists(), "ledger should exist after shard post"
            lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
            backlog_lines = [
                ln for ln in lines if json.loads(ln).get("status") == "BACKLOG"
            ]
            assert len(backlog_lines) >= 2, (
                f"expected at least 2 BACKLOG issues, got {len(backlog_lines)}"
            )

            loaded = SessionState.load(dot_dir / "session.json")
            assert loaded.current_phase == "IDLE", (
                f"expected session reset to IDLE, got {loaded.current_phase}"
            )

    def test_shard_post_with_zero_issues(self, mock_workspace: Path) -> None:
        spec_root = mock_workspace / "specs"
        bucket_dir = spec_root / "test-shard"
        bucket_dir.mkdir(parents=True)

        dot_dir = mock_workspace / ".deviate"
        session = SessionState(current_phase="SHARD")
        session.save(dot_dir / "session.json")

        manifest = bucket_dir / "manifest.json"
        manifest.write_text(json.dumps({"issues": []}), encoding="utf-8")

        result = runner.invoke(cli, ["shard", "post", str(manifest)])
        assert result.exit_code != 0, result.output
        assert "SHARD_HALTED" in result.output
        assert "issues" in result.output

    def test_shard_post_halts_on_missing_issues_field(
        self, mock_workspace: Path
    ) -> None:
        spec_root = mock_workspace / "specs"
        bucket_dir = spec_root / "test-shard"
        bucket_dir.mkdir(parents=True)

        dot_dir = mock_workspace / ".deviate"
        session = SessionState(current_phase="SHARD")
        session.save(dot_dir / "session.json")

        manifest = bucket_dir / "manifest.json"
        manifest.write_text(json.dumps({"epic_slug": "test-shard"}), encoding="utf-8")

        result = runner.invoke(cli, ["shard", "post", str(manifest)])
        assert result.exit_code != 0, result.output
        assert "SHARD_HALTED" in result.output
