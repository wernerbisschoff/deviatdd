from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from deviate.prompts.assembly import load_template


def _capture_stdout(func, *args, **kwargs) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            func(*args, **kwargs)
        except SystemExit:
            pass
    return buf.getvalue()


class TestPlanMDFileStructure:
    """plan.md template must reference the injected file structure appendix."""

    def test_plan_template_references_target_file_structure(self) -> None:
        content = load_template("plan")
        assert "## Target File Structure" in content, (
            "plan.md should contain a ## Target File Structure consumption section"
        )


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


class TestPlanPreFileStructure:
    """_plan_pre contract must include file_structure key with per-file data."""

    REQUIRED_CONTRACT_FIELDS = frozenset(
        {
            "issue_id",
            "spec_path",
            "plan_target",
            "worktree_full",
            "branch_name",
            "constitution_path",
            "constitution_test_command",
            "constitution_lint_command",
            "timestamp",
            "status",
            "phase",
        }
    )

    @staticmethod
    def _setup_environment(
        tmp_path: Path,
        issue_id: str = "ISS-TEST-001",
        session_phase: str = "SPECIFY",
        issue_content: str | None = None,
        workstation_files: dict[str, str] | None = None,
    ) -> None:
        (tmp_path / ".deviate").mkdir()
        session = {"current_phase": session_phase, "active_issue_id": issue_id}
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

        if workstation_files:
            for wpath, content in workstation_files.items():
                file_path = tmp_path / wpath
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)

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

        with contextlib.chdir(tmp_path):
            output = _capture_stdout(_plan_pre, issue_id=issue_id)

        return self._extract_contract(output)

    def test_injects_file_structure_key(self, tmp_path: Path, monkeypatch) -> None:
        ws_files = {
            "src/module.py": "class MyClass:\n    pass\n\ndef my_func():\n    pass\n",
        }
        self._setup_environment(tmp_path, workstation_files=ws_files)
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "file_structure" in contract, (
            "Plan pre contract should include a file_structure key"
        )
        fs = contract["file_structure"]
        assert isinstance(fs, dict), "file_structure should be a dict keyed by filepath"
        assert "src/module.py" in fs, (
            "Each workstation file should appear in file_structure"
        )
        entry = fs["src/module.py"]
        assert isinstance(entry, dict), "Each file_structure entry should be a dict"
        assert "language" in entry, "Entry should declare the detected language"
        assert "symbols" in entry, "Entry should list extracted symbols"

    def test_missing_workstation_file_skipped(self, tmp_path, monkeypatch) -> None:
        issue_content = """---
title: "Missing File"
issue_id: ISS-TEST-001
labels: [test]
blocked_by: []
coordinates_with: []
---

## System Topology Mapping
- **Primary Architectural Workstations**:
  - `src/missing.py` — does not exist on disk

## The Problem Contract
Test
"""
        self._setup_environment(tmp_path, issue_content=issue_content)
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "file_structure" in contract
        fs = contract["file_structure"]
        assert "src/missing.py" not in fs or fs["src/missing.py"] == {}, (
            "Non-existent workstation files should be skipped"
        )

    def test_mixed_languages(self, tmp_path: Path, monkeypatch) -> None:
        ws_files = {
            "src/module.py": "class PyClass:\n    pass\n",
            "src/app.ts": "interface AppProps {\n  name: string;\n}\n",
            "src/lib.rs": "pub fn helper() -> i32 { 42 }\n",
        }
        issue_content = """---
title: "Multi-Lang"
issue_id: ISS-TEST-001
labels: [test]
blocked_by: []
coordinates_with: []
---

## System Topology Mapping
- **Primary Architectural Workstations**:
  - `src/module.py` — Python module
  - `src/app.ts` — TypeScript service
  - `src/lib.rs` — Rust library

## The Problem Contract
Test
"""
        self._setup_environment(
            tmp_path, issue_content=issue_content, workstation_files=ws_files
        )
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "file_structure" in contract
        fs = contract["file_structure"]
        assert "src/module.py" in fs
        assert "src/app.ts" in fs
        assert "src/lib.rs" in fs

    def test_no_topology_section_omits_key(self, tmp_path: Path, monkeypatch) -> None:
        issue_content = """---
title: "No Topology"
issue_id: ISS-TEST-001
labels: [test]
blocked_by: []
coordinates_with: []
---

## The Problem Contract
Test without any topology mapping section
"""
        self._setup_environment(tmp_path, issue_content=issue_content)
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "file_structure" not in contract, (
            "Contract should omit file_structure when issue has no "
            "System Topology Mapping section"
        )

    def test_plan_target_still_present(self, tmp_path: Path, monkeypatch) -> None:
        self._setup_environment(tmp_path)
        contract = self._invoke_plan_pre(tmp_path, monkeypatch)

        assert "plan_target" in contract
        assert contract["plan_target"].endswith("plan.md")
