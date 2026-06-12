from __future__ import annotations

import subprocess
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPytestReportConfig:
    def test_default_values(self):
        from deviate.state.config import PytestReportConfig

        config = PytestReportConfig()
        assert config.json_report is False

    def test_extra_fields_forbidden(self):
        from pydantic import ValidationError
        from deviate.state.config import PytestReportConfig

        with pytest.raises(ValidationError):
            PytestReportConfig(json_report=True, unknown_field="value")


class TestRunPytestJsonReport:
    @patch("deviate.cli.micro._is_pytest_json_report_available", return_value=True)
    @patch("deviate.cli.micro.subprocess.run")
    def test_report_enabled_appends_json_report_flag(self, mock_run, mock_available):
        from deviate.state.config import PytestReportConfig
        from deviate.cli.micro import _run_pytest

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        config = PytestReportConfig(json_report=True)
        _run_pytest(root=Path("."), report_config=config)
        args = mock_run.call_args[0][0]
        assert "--json-report" in args

    @patch("deviate.cli.micro.subprocess.run")
    def test_report_disabled_no_json_report_flag(self, mock_run):
        from deviate.state.config import PytestReportConfig
        from deviate.cli.micro import _run_pytest

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        config = PytestReportConfig(json_report=False)
        _run_pytest(root=Path("."), report_config=config)
        args = mock_run.call_args[0][0]
        assert "--json-report" not in args

    @patch("deviate.cli.micro.subprocess.run")
    def test_fallback_when_plugin_missing(self, mock_run):
        from deviate.state.config import PytestReportConfig
        from deviate.cli.micro import _run_pytest, _classify_pytest_outcome

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="AssertionError: assert False", stderr=""
        )
        config = PytestReportConfig(json_report=True)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _run_pytest(root=Path("."), report_config=config)
        outcome = _classify_pytest_outcome(
            result.stdout, result.stderr, result.returncode
        )
        assert outcome is not None
        plugin_warnings = [
            x for x in w if "pytest-json-report" in str(x.message).lower()
        ]
        assert len(plugin_warnings) > 0
