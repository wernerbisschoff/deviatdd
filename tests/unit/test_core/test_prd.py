from __future__ import annotations

from pathlib import Path

from deviate.core.prd import extract_prd_requirements


class TestExtractPrdRequirements:
    def test_extract_prd_requirements_returns_fr_list(self, tmp_path: Path):
        prd_path = tmp_path / "prd.md"
        prd_path.write_text(
            "# PRD\n"
            "- **FR-001**: First requirement\n"
            "- **FR-002**: Second requirement\n"
            "- Some non-FR text\n"
            "- **FR-003**: Third requirement\n"
        )
        result = extract_prd_requirements(prd_path)
        assert result == ["FR-001", "FR-002", "FR-003"]

    def test_extract_prd_requirements_empty_when_no_fr(self, tmp_path: Path):
        prd_path = tmp_path / "prd.md"
        prd_path.write_text("# PRD\nNo requirements here.\n")
        result = extract_prd_requirements(prd_path)
        assert result == []
