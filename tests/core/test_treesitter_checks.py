from __future__ import annotations

from deviate.cli.micro import (
    _build_structured_diff_summary,
    _check_return_type_mismatch,
    _ts_check_cyclomatic_complexity,
    _ts_check_dead_code,
    _ts_check_duplication,
    _ts_check_return_type,
)


class TestBuildStructuredDiffSummary:
    def test_single_changed_function(self) -> None:
        symbols = [
            {
                "type": "function",
                "file": "src/example.py",
                "old_signature": "def hello(name: str) -> str",
            }
        ]
        result = _build_structured_diff_summary(symbols)
        assert "Structured Diff Summary" in result
        assert "function" in result
        assert "src/example.py" in result

    def test_symbol_with_new_and_old_signatures(self) -> None:
        symbols = [
            {
                "type": "function",
                "file": "src/example.py",
                "old_signature": "def hello(name: str) -> str",
                "new_signature": "def hello(name: str, greeting: str) -> str",
            }
        ]
        result = _build_structured_diff_summary(symbols)
        assert "Old:" in result
        assert "New:" in result

    def test_multiple_symbols_separate_files(self) -> None:
        symbols = [
            {"type": "function", "file": "a.py", "new_signature": "def foo()"},
            {"type": "class", "file": "b.py", "new_signature": "class Bar"},
        ]
        result = _build_structured_diff_summary(symbols)
        assert "foo" in result
        assert "Bar" in result
        assert "a.py" in result
        assert "b.py" in result

    def test_empty_symbols_returns_empty_string(self) -> None:
        result = _build_structured_diff_summary([])
        assert result == ""

    def test_symbol_without_signatures_still_appears(self) -> None:
        symbols = [{"type": "function", "file": "a.py"}]
        result = _build_structured_diff_summary(symbols)
        assert "function" in result
        assert "a.py" in result


class TestCheckReturnType:
    def test_correct_string_return_passes(self) -> None:
        src = b"def greet(name: str) -> str:\n    return f'Hello'\n"
        issues = _ts_check_return_type("test.py", src)
        assert issues == []

    def test_int_literal_where_str_expected_fails(self) -> None:
        src = b"def add(a: int, b: int) -> str:\n    return 42\n"
        issues = _ts_check_return_type("test.py", src)
        assert any("str" in i and "integer" in i for i in issues)

    def test_function_without_return_annotation_skipped(self) -> None:
        src = b"def greet(name):\n    return 42\n"
        issues = _ts_check_return_type("test.py", src)
        assert issues == []

    def test_multiple_functions_one_wrong(self) -> None:
        src = b"def good() -> str:\n    return 'ok'\ndef bad() -> str:\n    return 1\n"
        issues = _ts_check_return_type("test.py", src)
        assert any("bad" in i for i in issues)
        assert not any("good" in i for i in issues)

    def test_empty_source_returns_no_issues(self) -> None:
        issues = _ts_check_return_type("test.py", b"")
        assert issues == []

    def test_none_return_on_typed_function(self) -> None:
        src = b"def get_val() -> str | None:\n    return None\n"
        issues = _ts_check_return_type("test.py", src)
        assert issues == []


class TestCheckDeadCode:
    def test_private_function_with_no_call_sites_flagged(self) -> None:
        src = b"def _helper():\n    pass\ndef public():\n    return 1\n"
        issues = _ts_check_dead_code("test.py", src)
        assert any("dead code" in i and "_helper" in i for i in issues)

    def test_private_function_called_not_flagged(self) -> None:
        src = b"def _helper():\n    return 42\ndef use():\n    return _helper()\n"
        issues = _ts_check_dead_code("test.py", src)
        assert issues == []

    def test_public_unused_not_flagged(self) -> None:
        src = b"def helper():\n    return 1\ndef other():\n    return 2\n"
        issues = _ts_check_dead_code("test.py", src)
        assert issues == []

    def test_mixed_private_usage(self) -> None:
        src = (
            b"def _unused():\n    pass\n"
            b"def _used():\n    return 1\n"
            b"def caller():\n    return _used()\n"
        )
        issues = _ts_check_dead_code("test.py", src)
        assert any("_unused" in i for i in issues)
        assert not any("_used" in i for i in issues)

    def test_empty_returns_no_issues(self) -> None:
        issues = _ts_check_dead_code("test.py", b"")
        assert issues == []


class TestCheckCyclomaticComplexity:
    def test_trivial_function_no_warning(self) -> None:
        src = b"def greet():\n    return 'hello'\n"
        issues = _ts_check_cyclomatic_complexity("test.py", src)
        assert issues == []

    def test_low_complexity_no_warning(self) -> None:
        src = (
            b"def check(x):\n"
            b"    if x > 0:\n"
            b"        return 1\n"
            b"    if x < 0:\n"
            b"        return -1\n"
            b"    return 0\n"
        )
        issues = _ts_check_cyclomatic_complexity("test.py", src)
        assert issues == []

    def test_high_complexity_triggers_warning(self) -> None:
        lines = ["def complex(x):"]
        for i in range(11):
            lines.append(f"    if x == {i}:")
            lines.append("        pass")
        src = "\n".join(lines).encode()
        issues = _ts_check_cyclomatic_complexity("test.py", src)
        assert any("complex" in i for i in issues)

    def test_boolean_operator_counts_toward_complexity(self) -> None:
        src = (
            b"def check(x):\n    if x > 0 and x < 10:\n        return 1\n    return 0\n"
        )
        issues = _ts_check_cyclomatic_complexity("test.py", src)
        assert issues == []

    def test_empty_returns_no_issues(self) -> None:
        issues = _ts_check_cyclomatic_complexity("test.py", b"")
        assert issues == []


class TestCheckDuplication:
    def test_identical_function_bodies_detected(self) -> None:
        src = (
            b"def foo():\n"
            b"    x = 1\n"
            b"    y = 2\n"
            b"    z = 3\n"
            b"    a = 4\n"
            b"    b = 5\n"
            b"    return x\n"
            b"def bar():\n"
            b"    x = 1\n"
            b"    y = 2\n"
            b"    z = 3\n"
            b"    a = 4\n"
            b"    b = 5\n"
            b"    return x\n"
        )
        issues = _ts_check_duplication("test.py", src)
        assert any("duplicate" in i and "foo" in i and "bar" in i for i in issues)

    def test_different_bodies_not_flagged(self) -> None:
        src = (
            b"def foo():\n"
            b"    x = 1\n"
            b"    y = 2\n"
            b"    z = 3\n"
            b"    a = 4\n"
            b"    b = 5\n"
            b"    return x\n"
            b"def bar():\n"
            b"    return 'different'\n"
        )
        issues = _ts_check_duplication("test.py", src)
        assert issues == []

    def test_short_bodies_under_five_lines_skipped(self) -> None:
        src = b"def foo():\n    return 1\ndef bar():\n    return 1\n"
        issues = _ts_check_duplication("test.py", src)
        assert issues == []

    def test_empty_returns_no_issues(self) -> None:
        issues = _ts_check_duplication("test.py", b"")
        assert issues == []


class TestCheckReturnTypeMismatchIntegration:
    def test_orchestrates_all_checks(self, tmp_path) -> None:
        filepath = tmp_path / "test_checks.py"
        filepath.write_text(
            "def _unused_helper():\n"
            "    pass\n"
            "def greet() -> str:\n"
            "    return 'hello'\n"
            "def duplicate():\n"
            "    x = 1\n"
            "    y = 2\n"
            "    z = 3\n"
            "    a = 4\n"
            "    b = 5\n"
            "    return x\n"
            "def other_duplicate():\n"
            "    x = 1\n"
            "    y = 2\n"
            "    z = 3\n"
            "    a = 4\n"
            "    b = 5\n"
            "    return x\n"
        )
        issues = _check_return_type_mismatch(str(filepath))
        assert any("dead code" in i for i in issues)
        assert any("duplicate" in i for i in issues)

    def test_no_issues_returns_empty(self, tmp_path) -> None:
        filepath = tmp_path / "clean.py"
        filepath.write_text("def public() -> str:\n    return 'ok'\n")
        issues = _check_return_type_mismatch(str(filepath))
        assert issues == []

    def test_nonexistent_file_does_not_crash(self) -> None:
        issues = _check_return_type_mismatch("/nonexistent/path.py")
        assert issues == []

    def test_syntax_error_does_not_crash(self, tmp_path) -> None:
        filepath = tmp_path / "broken.py"
        filepath.write_text("def broken( invalid syntax\n")
        issues = _check_return_type_mismatch(str(filepath))
        assert isinstance(issues, list)
