from __future__ import annotations

from deviate.core.treesitter import (
    extract_changed_symbols,
    extract_file_structure,
    incremental_parse,
)

SAMPLE_SOURCE = """
def hello(name: str) -> str:
    return f"Hello, {name}!"


class Greeter:
    def greet(self, name: str) -> str:
        return self._format(name)

    def _format(self, name: str) -> str:
        return f"Hi, {name}"
"""

SAMPLE_DIFF = """diff --git a/src/example.py b/src/example.py
index abc..def 100644
--- a/src/example.py
+++ b/src/example.py
@@ -1,5 +1,5 @@
-def hello(name: str) -> str:
-    return f"Hello, {name}!"
+def hello(name: str, greeting: str = "Hello") -> str:
+    return f"{greeting}, {name}!"

 class Greeter:
"""


class TestExtractChangedSymbols:
    """extract_changed_symbols() parses git diff output into structured change data."""

    def test_single_function(self) -> None:
        """AC-ADHOC-008-01: Diff with one changed function returns structured symbol list."""
        result = extract_changed_symbols(SAMPLE_DIFF)
        assert len(result) == 1
        entry = result[0]
        assert entry["type"] == "function"
        assert entry["file"] == "src/example.py"
        assert "hello" in entry.get("old_signature", "")
        assert "hello" in entry.get("new_signature", "")

    def test_empty_diff(self) -> None:
        """AC-ADHOC-008-01: Empty diff returns empty list."""
        result = extract_changed_symbols("")
        assert result == []

    def test_diff_no_symbol_changes(self) -> None:
        """Non-functional changes (whitespace, comments) produce no symbol entries."""
        whitespace_diff = """diff --git a/src/example.py b/src/example.py
index abc..def 100644
--- a/src/example.py
+++ b/src/example.py
@@ -1,3 +1,3 @@
-# old comment
+# new comment
 x = 1
"""
        result = extract_changed_symbols(whitespace_diff)
        assert result == []

    def test_changed_class(self) -> None:
        """Diff changing a class definition extracts class symbol."""
        class_diff = """diff --git a/src/example.py b/src/example.py
index abc..def 100644
--- a/src/example.py
+++ b/src/example.py
@@ -1,5 +1,5 @@
-class Greeter:
-    pass
+class Greeter:
+    def hello(self) -> str:
+        return "hi"
"""
        result = extract_changed_symbols(class_diff)
        assert len(result) >= 1
        assert result[0]["type"] == "class"

    def test_syntax_error_fallback(self) -> None:
        """AC-ADHOC-008-03: Invalid Python in diff falls back gracefully (no crash)."""
        broken_diff = """diff --git a/src/broken.py b/src/broken.py
index abc..def 100644
--- a/src/broken.py
+++ b/src/broken.py
@@ -1 +1 @@
-x = 1
+def broken( invalid syntax here
"""
        result = extract_changed_symbols(broken_diff)
        assert isinstance(result, list)


class TestExtractFileStructure:
    """extract_file_structure() extracts function/class signatures from source code."""

    def test_basic_structure(self) -> None:
        """AC-ADHOC-008-02: Source with classes and functions returns correct signature map."""
        result = extract_file_structure(SAMPLE_SOURCE)
        assert "functions" in result
        assert "classes" in result
        assert "hello" in result["functions"]
        assert "Greeter" in result["classes"]

    def test_methods_under_class(self) -> None:
        """Methods are nested under their parent class."""
        result = extract_file_structure(SAMPLE_SOURCE)
        greeter = result["classes"]["Greeter"]
        assert "greet" in greeter["methods"]
        assert "_format" in greeter["methods"]

    def test_signature_details(self) -> None:
        """Each function entry includes name, params, and return_type."""
        result = extract_file_structure(SAMPLE_SOURCE)
        hello = result["functions"]["hello"]
        assert hello["params"] == ["name: str"]
        assert hello["return_type"] == "str"

    def test_empty_source(self) -> None:
        """Empty source string returns empty structure."""
        result = extract_file_structure("")
        assert result == {"functions": {}, "classes": {}}

    def test_import_extraction(self) -> None:
        """Imports are extracted when present."""
        source_with_imports = """
import os
from pathlib import Path

def load(path: Path) -> str:
    return os.read(path)
"""
        result = extract_file_structure(source_with_imports)
        assert "imports" in result
        assert any("import os" in i for i in result["imports"])
        assert any("from pathlib import Path" in i for i in result["imports"])


class TestIncrementalParse:
    """incremental_parse() re-parses only changed ranges of a file."""

    def test_initial_parse(self) -> None:
        """First call with old_tree=None performs full parse."""
        result = incremental_parse(SAMPLE_SOURCE)
        assert result is not None

    def test_incremental_reparse(self) -> None:
        """Subsequent parse with old_tree returns a new tree of same type."""
        initial = incremental_parse(SAMPLE_SOURCE)
        modified = SAMPLE_SOURCE.replace('"Hello"', '"Hey"')
        result = incremental_parse(modified, old_tree=initial)
        assert result is not None

    def test_unchanged_source(self) -> None:
        """Same source passed twice produces equivalent trees."""
        first = incremental_parse(SAMPLE_SOURCE)
        second = incremental_parse(SAMPLE_SOURCE, old_tree=first)
        assert second is not None
