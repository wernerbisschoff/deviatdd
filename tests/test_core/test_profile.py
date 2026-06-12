from __future__ import annotations

import pytest

from deviate.core.profile import resolve_profile


class TestResolveProfile:
    def test_fast_skips_judge_and_refactor(self):
        result = resolve_profile("fast")
        assert result == (True, True)

    def test_secure_with_explicit_no_refactor_false(self):
        result = resolve_profile("secure", no_refactor=False)
        assert result == (False, False)

    def test_invalid_profile_raises_value_error(self):
        with pytest.raises(ValueError) as exc:
            resolve_profile("invalid")
        msg = str(exc.value).lower()
        assert "full" in msg
        assert "fast" in msg
        assert "secure" in msg

    def test_explicit_flag_overrides_profile_default(self):
        result = resolve_profile("fast", no_judge=False)
        assert result == (False, True)

    def test_full_profile_runs_all_phases(self):
        result = resolve_profile("full")
        assert result == (False, False)

    def test_none_params_do_not_override_profile(self):
        result = resolve_profile("fast", no_judge=None, no_refactor=None)
        assert result == (True, True)
