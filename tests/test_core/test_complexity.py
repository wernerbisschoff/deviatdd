from __future__ import annotations

import pytest

from deviate.core.complexity import ComplexityGate


class TestComplexityGateClassify:
    def test_classify_low(self):
        result = ComplexityGate.classify("Fix typo", _stub="LOW")
        assert result.level == "LOW"
        assert result.execution_mode == "DIRECT"

    def test_classify_medium(self):
        result = ComplexityGate.classify(
            "Add form validation with 3 fields",
            _stub="MEDIUM",
        )
        assert result.level == "MEDIUM"
        assert result.execution_mode == "DIRECT"

    def test_classify_high(self):
        result = ComplexityGate.classify(
            "Build authentication system with OAuth, JWT, RBAC",
            _stub="HIGH",
        )
        assert result.level == "HIGH"
        assert result.execution_mode == "TDD"

    def test_classify_unknown_stub_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown stub value"):
            ComplexityGate.classify("Some description", _stub="INVALID")
