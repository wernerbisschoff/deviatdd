from __future__ import annotations

import contextlib
import io
import json
from contextlib import chdir
from pathlib import Path
import pytest


def _capture_stdout(func, *args, **kwargs) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            func(*args, **kwargs)
        except SystemExit:
            pass
    return buf.getvalue()


class TestParseWorkstationPaths:
    """_parse_workstation_paths extracts file paths from issue topology mapping."""

    def test_extracts_simple_paths(self) -> None:
        from deviate.cli.meso import _parse_workstation_paths

        content = """---
title: Test
issue_id: ISS-001
---

## System Topology Mapping
- **Primary Architectural Workstations**:
  - `src/module.py` — Python module
  - `src/utils.ts` — TypeScript utilities

## Problem
Test
"""
        paths = _parse_workstation_paths(content)
        assert paths == ["src/module.py", "src/utils.ts"]

    def test_handles_descriptions_with_colons(self) -> None:
        from deviate.cli.meso import _parse_workstation_paths

        content = """## System Topology Mapping
- **Primary Architectural Workstations**:
  - `src/core/treesitter.py` — new module: language-agnostic parser
  - `src/cli/micro.py:1108-1137` — _run_judge_phase()

## Problem
"""
        paths = _parse_workstation_paths(content)
        assert "src/core/treesitter.py" in paths
        assert "src/cli/micro.py:1108-1137" in paths

    def test_missing_section_returns_empty_list(self) -> None:
        from deviate.cli.meso import _parse_workstation_paths

        content = "## Problem\nNo topology here.\n"
        assert _parse_workstation_paths(content) == []

    def test_missing_workstations_bullet_returns_empty_list(self) -> None:
        from deviate.cli.meso import _parse_workstation_paths

        content = """## System Topology Mapping
- **Epic Target Domain**: `specs/adhoc/`

## Problem
"""
        assert _parse_workstation_paths(content) == []

    def test_ignores_non_code_path_items(self) -> None:
        from deviate.cli.meso import _parse_workstation_paths

        content = """## System Topology Mapping
- **Primary Architectural Workstations**:
  - `src/module.py` — real file
  - some text without backticks

## Problem
"""
        paths = _parse_workstation_paths(content)
        assert paths == ["src/module.py"]


class TestPlanPreContract:
    """_plan_pre contract still emits the core fields after tree-sitter removal."""

    @staticmethod
    def _setup_environment(
        tmp_path: Path,
        issue_id: str = "ISS-TEST-001",
        issue_content: str | None = None,
    ) -> None:
        (tmp_path / ".deviate").mkdir()
        session = {"current_phase": "SPECIFY", "active_issue_id": issue_id}
        (tmp_path / ".deviate" / "session.json").write_text(json.dumps(session))

        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "constitution.md").write_text("# Constitution\n")

        record = {
            "issue_id": issue_id,
            "type": "feature",
            "title": "Test Issue",
            "status": "BACKLOG",
            "source_file": f"specs/test/issues/{issue_id}.md",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        (tmp_path / "specs" / "issues.jsonl").write_text(json.dumps(record) + "\n")

        issue_dir = tmp_path / "specs" / "test" / "issues"
        issue_dir.mkdir(parents=True)

        if issue_content is None:
            issue_content = f"""---
title: "Test Issue"
issue_id: {issue_id}
labels: [test]
blocked_by: []
coordinates_with: []
---

## System Topology Mapping
- **Epic Target Domain**: `specs/test/`
- **Primary Architectural Workstations**:
  - `src/module.py` — Python module

## The Problem Contract
Test description

## Scope Boundaries
### Hard Inclusions
- Nothing

## Edge Cases and Boundaries
- Nothing
"""
        (issue_dir / f"{issue_id}.md").write_text(issue_content)

    @staticmethod
    def _extract_contract(output: str) -> dict:
        start = output.index("{")
        end = output.rindex("}") + 1
        return json.loads(output[start:end])

    def _invoke_plan_pre(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        issue_id: str = "ISS-TEST-001",
    ) -> dict:
        from deviate.cli.meso import _plan_pre

        monkeypatch.setattr(
            "deviate.cli.meso._is_linked_worktree", lambda cwd=None: True
        )

        class MockResult:
            stdout = "test-branch\n"
            returncode = 0

        monkeypatch.setattr(
            "deviate.cli.meso.subprocess.run", lambda *a, **kw: MockResult()
        )

        with chdir(tmp_path):
            output = _capture_stdout(_plan_pre, issue_id=issue_id)

        return self._extract_contract(output)

    def test_no_file_structure_key(self, tmp_path: Path, monkeypatch) -> None:
        """Plan pre contract no longer emits file_structure (tree-sitter removed)."""
        self._setup_environment(tmp_path)
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "file_structure" not in contract, (
            "Plan pre contract should NOT include file_structure after "
            "tree-sitter removal"
        )

    def test_plan_target_still_present(self, tmp_path: Path, monkeypatch) -> None:
        self._setup_environment(tmp_path)
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "plan_target" in contract
        assert contract["plan_target"].endswith("plan.md")


class TestPlanAcceptanceContract:
    _setup_environment = staticmethod(TestPlanPreContract._setup_environment)
    _extract_contract = staticmethod(TestPlanPreContract._extract_contract)

    def test_plan_post_rejects_missing_acceptance_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from deviate.cli import cli

        self._setup_environment(tmp_path)
        plan_dir = tmp_path / "specs" / "test" / "ISS-TEST-001"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan.md").write_text("## Plan Summary\n- Strategy\n")
        monkeypatch.setattr(
            "deviate.cli.meso._is_linked_worktree", lambda cwd=None: True
        )

        with chdir(tmp_path):
            result = CliRunner().invoke(cli, ["plan", "post"])

        assert result.exit_code == 1, result.output
        assert "PLAN_ACCEPTANCE_CONTRACT_MISSING" in result.output

    def test_tasks_pre_rejects_plan_without_acceptance_contract(
        self, tmp_path: Path
    ) -> None:
        from typer.testing import CliRunner

        from deviate.cli import cli

        self._setup_environment(tmp_path)
        session_path = tmp_path / ".deviate" / "session.json"
        session = json.loads(session_path.read_text())
        session["current_phase"] = "TASKS"
        session_path.write_text(json.dumps(session))
        plan_dir = tmp_path / "specs" / "test" / "ISS-TEST-001"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan.md").write_text("## Plan Summary\n- Strategy\n")

        with chdir(tmp_path):
            result = CliRunner().invoke(cli, ["tasks", "pre"])

        assert result.exit_code == 0, result.output
        contract = self._extract_contract(result.output)
        assert contract["status"] == "PLAN_ACCEPTANCE_CONTRACT_MISSING"

    def test_tasks_pre_accepts_plan_acceptance_contract(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from deviate.cli import cli

        self._setup_environment(tmp_path)
        session_path = tmp_path / ".deviate" / "session.json"
        session = json.loads(session_path.read_text())
        session["current_phase"] = "TASKS"
        session_path.write_text(json.dumps(session))
        plan_dir = tmp_path / "specs" / "test" / "ISS-TEST-001"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan.md").write_text(
            "## Acceptance Contract\n"
            "**Scenario AC-PLAN-001: Valid input succeeds**\n"
            "- **Source Outline**: AO-001\n"
            "- **Upstream Traceability**: FR-001-DEMO, AC-001-DEMO-01\n"
            "- **Current-Code Evidence**: src/demo.py:run\n"
            "- **Given**: A configured repository\n"
            "- **When**: The command runs\n"
            "- **Then**: It succeeds\n"
            "- **Verification Mode**: automated\n"
        )

        with chdir(tmp_path):
            result = CliRunner().invoke(cli, ["tasks", "pre"])

        assert result.exit_code == 0, result.output
        contract = self._extract_contract(result.output)
        assert contract["status"] == "READY"
