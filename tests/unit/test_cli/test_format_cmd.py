"""``_run_format_cmd`` must not require ``mise`` on PATH.

Format is optional polish. Unit tests and mise-less CI (GitHub Actions
pytest) must get a ``CompletedProcess`` instead of ``FileNotFoundError``.
Real ``mise run format`` is unchanged when mise exists and
``[tasks.format]`` is defined.

Lives under ``tests/unit/test_cli/`` so the ``test_micro`` autouse
subprocess mock does not swallow the missing-binary ``FileNotFoundError``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from deviate.cli.micro import _run_format_cmd


def _write_format_task(root: Path) -> None:
    (root / "mise.toml").write_text(
        '[tasks.format]\nrun = "true"\n',
        encoding="utf-8",
    )


class TestRunFormatCmdOptionalMise:
    def test_missing_format_task_is_noop(self, tmp_path: Path) -> None:
        with patch("deviate.cli.micro.subprocess.run") as mock_run:
            result = _run_format_cmd(tmp_path)
        mock_run.assert_not_called()
        assert result.returncode == 0
        assert result.args == ["mise", "run", "format"]

    def test_missing_mise_binary_returns_127(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_format_task(tmp_path)
        monkeypatch.setenv("PATH", "/nonexistent-mise-bin")
        result = _run_format_cmd(tmp_path)
        assert result.returncode == 127
        assert result.args == ["mise", "run", "format"]
        assert "mise" in (result.stderr or "").lower()

    def test_file_not_found_is_caught(self, tmp_path: Path) -> None:
        _write_format_task(tmp_path)
        with patch(
            "deviate.cli.micro.subprocess.run",
            side_effect=FileNotFoundError(2, "No such file or directory", "mise"),
        ):
            result = _run_format_cmd(tmp_path)
        assert result.returncode == 127
        assert result.args == ["mise", "run", "format"]
        assert "mise" in (result.stderr or "").lower()

    def test_defined_format_runs_mise_when_present(self, tmp_path: Path) -> None:
        _write_format_task(tmp_path)
        fake = subprocess.CompletedProcess(
            ["mise", "run", "format"], 0, "formatted\n", ""
        )
        with patch("deviate.cli.micro.subprocess.run", return_value=fake) as mock_run:
            result = _run_format_cmd(tmp_path)
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == ["mise", "run", "format"]
        assert mock_run.call_args.kwargs["cwd"] == tmp_path
        assert result.returncode == 0
        assert result.stdout == "formatted\n"
