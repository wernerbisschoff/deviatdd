from __future__ import annotations

from contextlib import chdir
from pathlib import Path
from unittest.mock import MagicMock, patch


def _write_spec_with_workstations(
    spec_file: Path,
    file_paths: list[str],
) -> None:
    """Write a spec file mimicking an issue with System Topology Mapping."""
    lines = [
        "# Test Issue: AST Phase Prioritization",
        "",
        "## System Topology Mapping",
        "- **Epic Target Domain**: `specs/adhoc/`",
        "- **Local Issue File**: `issues/008-ast-phase-prioritization.md`",
        "- **Primary Architectural Workstations**:",
    ]
    for fp in file_paths:
        lines.append(f"  - `{fp}` — target module")
    lines.extend(
        [
            "- **Upstream Evidence**: `specs/explore/ast-tree-sitter.md`",
            "",
        ]
    )
    spec_file.write_text("\n".join(lines))


def _write_python_source(base: Path, target_dir: str, files: dict[str, str]) -> Path:
    src_dir = base / target_dir
    src_dir.mkdir(parents=True)
    for name, content in files.items():
        (src_dir / name).write_text(content)
    return src_dir


class TestFileStructureInjection:
    """Verify PLAN phase injects file structure appendix into the agent prompt.

    AC-ADHOC-008-02: File structure injected into PLAN prompt
    US-008-02: Pre-extracted file structure appendix for target workstation files
    """

    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_appendix_in_prompt_contract(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Contract dict must include 'file_structure_appendix' key.

        The _invoke_agent_phase function enriches the plan-phase contract
        with a tree-sitter-extracted file structure appendix and injects it
        into the prompt so the PLAN agent has pre-extracted symbol signatures
        for target workstation files.
        """
        from deviate.cli.meso import _invoke_agent_phase

        mock_build.return_value = "test prompt base"
        mock_invoke.return_value = MagicMock(status="PASS")

        spec_dir = tmp_path / "specs" / "adhoc" / "008-ast-phase-prioritization"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "issues" / "008-ast-phase-prioritization.md"
        spec_file.parent.mkdir(parents=True)
        _write_spec_with_workstations(
            spec_file,
            ["src/deviate/core/treesitter.py", "src/deviate/core/somefile.py"],
        )

        tree_sitter_content = (
            "from __future__ import annotations\n"
            "\n"
            "def get_parser() -> object: ...\n"
            "\n"
            "class TreeParser:\n"
            "    def parse(self, source: str) -> object: ...\n"
        )
        _write_python_source(
            tmp_path,
            "src/deviate/core",
            {
                "treesitter.py": tree_sitter_content,
                "somefile.py": "def helper() -> str:\n    return 'ok'\n",
            },
        )

        contract: dict[str, str] = {
            "issue_id": "ISS-ADH-008",
            "issue_title": "AST Phase Prioritization",
            "epic_slug": "adhoc",
            "issue_slug": "008-ast-phase-prioritization",
            "spec_path": str(spec_file),
            "worktree_full": str(tmp_path),
            "plan_path": str(spec_dir / "plan.md"),
            "tasks_target": str(spec_dir / "tasks.md"),
        }

        with chdir(tmp_path):
            _invoke_agent_phase("plan", contract, cwd=str(tmp_path))

        assert "file_structure_appendix" in contract, (
            "PLAN contract must include 'file_structure_appendix' key "
            "with the tree-sitter-extracted file structure"
        )

    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_prompt_contains_file_structure_appendix(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The final prompt sent to the agent contains the file structure appendix."""
        from deviate.cli.meso import _invoke_agent_phase

        mock_build.return_value = "test prompt base"
        mock_invoke.return_value = MagicMock(status="PASS")

        spec_dir = tmp_path / "specs" / "adhoc" / "008-ast-phase-prioritization"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "issues" / "008-ast-phase-prioritization.md"
        spec_file.parent.mkdir(parents=True)
        _write_spec_with_workstations(spec_file, ["src/deviate/core/treesitter.py"])

        _write_python_source(
            tmp_path,
            "src/deviate/core",
            {"treesitter.py": "def foo() -> str:\n    return 'bar'\n"},
        )

        contract: dict[str, str] = {
            "issue_id": "ISS-ADH-008",
            "spec_path": str(spec_file),
            "worktree_full": str(tmp_path),
            "plan_path": str(spec_dir / "plan.md"),
            "tasks_target": str(spec_dir / "tasks.md"),
        }

        with chdir(tmp_path):
            _invoke_agent_phase("plan", contract, cwd=str(tmp_path))

        captured_prompt = mock_invoke.call_args[0][0]
        assert "## Target File Structure" in captured_prompt, (
            "Final agent prompt must contain '## Target File Structure' section"
        )

    @patch("deviate.cli.meso.AgentBackend.invoke")
    @patch("deviate.cli.meso._build_slim_prompt")
    def test_appendix_empty_when_no_workstation_files(
        self,
        mock_build: MagicMock,
        mock_invoke: MagicMock,
        tmp_path: Path,
    ) -> None:
        """No workstation files → appendix is empty string (no injection)."""
        from deviate.cli.meso import _invoke_agent_phase

        mock_build.return_value = "test prompt base"
        mock_invoke.return_value = MagicMock(status="PASS")

        spec_dir = tmp_path / "specs" / "adhoc" / "008-ast-phase-prioritization"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "issues" / "008-ast-phase-prioritization.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Test Issue\nNo topology mapping here.\n")

        contract: dict[str, str] = {
            "issue_id": "ISS-ADH-008",
            "spec_path": str(spec_file),
            "worktree_full": str(tmp_path),
            "plan_path": str(spec_dir / "plan.md"),
            "tasks_target": str(spec_dir / "tasks.md"),
        }

        with chdir(tmp_path):
            _invoke_agent_phase("plan", contract, cwd=str(tmp_path))

        captured_prompt = mock_invoke.call_args[0][0]
        assert "## Target File Structure" not in captured_prompt, (
            "No appendix should be injected when spec has no workstation files"
        )


class TestPlanTemplateContent:
    """Verify the plan.md prompt template references file structure injection."""

    def test_plan_template_has_target_file_structure_section(self) -> None:
        """plan.md contains ## Target File Structure in the output format schema."""
        from deviate.prompts.assembly import load_template

        template = load_template("plan")
        assert "## Target File Structure" in template, (
            "plan.md template must reference '## Target File Structure' "
            "in its output format schema or execution sequence"
        )
