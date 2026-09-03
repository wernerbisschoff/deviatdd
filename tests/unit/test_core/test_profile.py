from __future__ import annotations

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.core.profile import canonicalize_profile, resolve_profile

runner = CliRunner()


class TestResolveProfile:
    def test_fast_skips_judge_and_refactor(self):
        result = resolve_profile("fast")
        assert result == (True, True)

    def test_full_profile_runs_all_phases(self):
        result = resolve_profile("full")
        assert result == (False, False)

    def test_legacy_secure_skips_refactor_only(self):
        assert canonicalize_profile("secure") == "secure"
        assert resolve_profile("secure") == (False, True)

    def test_legacy_secure_with_explicit_no_refactor_false(self):
        result = resolve_profile("secure", no_refactor=False)
        assert result == (False, False)

    def test_legacy_default_coerces_to_full(self):
        assert canonicalize_profile("default") == "full"
        assert resolve_profile("default") == resolve_profile("full")

    def test_invalid_profile_raises_value_error(self):
        with pytest.raises(ValueError) as exc:
            resolve_profile("invalid")
        msg = str(exc.value).lower()
        assert "full" in msg
        assert "fast" in msg
        assert "secure" not in msg
        assert "judge" not in msg

    def test_judge_is_not_a_public_profile(self):
        with pytest.raises(ValueError) as exc:
            resolve_profile("judge")
        assert "full" in str(exc.value).lower()
        assert "fast" in str(exc.value).lower()

    def test_explicit_flag_overrides_profile_default(self):
        result = resolve_profile("fast", no_judge=False)
        assert result == (False, True)

    def test_none_params_do_not_override_profile(self):
        result = resolve_profile("fast", no_judge=None, no_refactor=None)
        assert result == (True, True)

    def test_help_lists_only_full_and_fast(self):
        result = runner.invoke(cli, ["micro", "run", "--help"])
        assert result.exit_code == 0, result.output
        assert "Execution profile: full, fast" in result.output
        assert "full, fast, secure" not in result.output
        assert "full, fast, judge" not in result.output
        profile_lines = [
            line
            for line in result.output.splitlines()
            if "Execution profile" in line or "--profile" in line
        ]
        joined = "\n".join(profile_lines).lower()
        assert "secure" not in joined
