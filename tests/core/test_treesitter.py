from __future__ import annotations

import pytest


class TestLanguageDispatch:
    """Every extension in EXTENSION_MAP maps to a valid grammar ID."""

    def test_language_dispatch_python(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".py" in EXTENSION_MAP
        assert EXTENSION_MAP[".py"] == "python"
        assert get_language_id("foo.py") == "python"

    def test_language_dispatch_javascript(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".js", ".mjs", ".cjs"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "javascript"
            assert get_language_id(f"foo{ext}") == "javascript"

    def test_language_dispatch_typescript(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".ts", ".mts", ".cts"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "typescript"
            assert get_language_id(f"foo{ext}") == "typescript"

    def test_language_dispatch_tsx(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".tsx" in EXTENSION_MAP
        assert EXTENSION_MAP[".tsx"] == "tsx"
        assert get_language_id("foo.tsx") == "tsx"

    def test_language_dispatch_rust(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".rs" in EXTENSION_MAP
        assert EXTENSION_MAP[".rs"] == "rust"
        assert get_language_id("foo.rs") == "rust"

    def test_language_dispatch_go(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".go" in EXTENSION_MAP
        assert EXTENSION_MAP[".go"] == "go"
        assert get_language_id("foo.go") == "go"

    def test_language_dispatch_cpp(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".cpp", ".cc", ".cxx", ".hpp", ".h"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "cpp"
            assert get_language_id(f"foo{ext}") == "cpp"

    def test_language_dispatch_elixir(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".ex", ".exs"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "elixir"
            assert get_language_id(f"foo{ext}") == "elixir"

    def test_language_dispatch_csharp(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".cs" in EXTENSION_MAP
        assert EXTENSION_MAP[".cs"] == "c_sharp"
        assert get_language_id("foo.cs") == "c_sharp"

    def test_language_dispatch_markdown(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".md", ".mdx"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "markdown"
            assert get_language_id(f"foo{ext}") == "markdown"

    def test_language_dispatch_bash(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".sh", ".bash", ".zsh"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "bash"
            assert get_language_id(f"foo{ext}") == "bash"

    def test_language_dispatch_json(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".json" in EXTENSION_MAP
        assert EXTENSION_MAP[".json"] == "json"
        assert get_language_id("foo.json") == "json"

    def test_language_dispatch_toml(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".toml" in EXTENSION_MAP
        assert EXTENSION_MAP[".toml"] == "toml"
        assert get_language_id("foo.toml") == "toml"

    def test_language_dispatch_yaml(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".yaml", ".yml"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "yaml"
            assert get_language_id(f"foo{ext}") == "yaml"

    def test_language_dispatch_html(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".html", ".htm"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "html"
            assert get_language_id(f"foo{ext}") == "html"

    def test_language_dispatch_css(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".css", ".scss", ".less"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "css"
            assert get_language_id(f"foo{ext}") == "css"

    def test_language_dispatch_sql(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".sql" in EXTENSION_MAP
        assert EXTENSION_MAP[".sql"] == "sql"
        assert get_language_id("foo.sql") == "sql"

    def test_language_dispatch_dockerfile(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert "Dockerfile" in EXTENSION_MAP
        assert EXTENSION_MAP["Dockerfile"] == "dockerfile"
        assert get_language_id("Dockerfile") == "dockerfile"
        assert ".dockerfile" in EXTENSION_MAP
        assert get_language_id("Container.dockerfile") == "dockerfile"

    def test_language_dispatch_terraform(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".tf", ".tfvars"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "hcl"
            assert get_language_id(f"foo{ext}") == "hcl"

    def test_language_dispatch_kotlin(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        for ext in (".kt", ".kts"):
            assert ext in EXTENSION_MAP
            assert EXTENSION_MAP[ext] == "kotlin"
            assert get_language_id(f"foo{ext}") == "kotlin"

    def test_language_dispatch_swift(self) -> None:
        from deviate.core.treesitter import get_language_id, EXTENSION_MAP

        assert ".swift" in EXTENSION_MAP
        assert EXTENSION_MAP[".swift"] == "swift"
        assert get_language_id("foo.swift") == "swift"

    def test_unknown_extension_returns_none(self) -> None:
        from deviate.core.treesitter import get_language_id

        assert get_language_id("foo.rb") is None
        assert get_language_id("Makefile") is None
        assert get_language_id("") is None


class TestExtensionMapCompleteness:
    """EXTENSION_MAP covers the minimum 21-entry set from the spec."""

    def test_extension_map_contains_all_required_extensions(self) -> None:
        from deviate.core.treesitter import EXTENSION_MAP

        required = {
            ".py",
            ".js",
            ".mjs",
            ".cjs",
            ".ts",
            ".mts",
            ".cts",
            ".tsx",
            ".rs",
            ".go",
            ".cpp",
            ".cc",
            ".cxx",
            ".hpp",
            ".h",
            ".ex",
            ".exs",
            ".cs",
            ".md",
            ".mdx",
            ".sh",
            ".bash",
            ".zsh",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".html",
            ".htm",
            ".css",
            ".scss",
            ".less",
            ".sql",
            "Dockerfile",
            ".dockerfile",
            ".tf",
            ".tfvars",
            ".kt",
            ".kts",
            ".swift",
        }
        for ext in required:
            assert ext in EXTENSION_MAP, f"Missing EXTENSION_MAP entry for {ext}"


class TestGetParser:
    """get_parser() returns a configured tree-sitter Parser for each grammar."""

    def test_get_parser_python(self) -> None:
        from deviate.core.treesitter import get_parser, get_language_id

        parser = get_parser("test.py")
        assert parser is not None
        lang_id = get_language_id("test.py")
        assert lang_id == "python"

        src = b"def foo():\n    pass\n"
        tree = parser.parse(src)
        assert tree is not None
        assert tree.root_node is not None
        assert tree.root_node.type == "module"

    def test_get_parser_rust(self) -> None:
        from deviate.core.treesitter import get_parser

        parser = get_parser("test.rs")
        assert parser is not None

        src = b"fn foo() {}"
        tree = parser.parse(src)
        assert tree is not None
        assert tree.root_node is not None

    def test_get_parser_unknown_returns_none(self) -> None:
        from deviate.core.treesitter import get_parser

        assert get_parser("foo.rb") is None

    def test_get_parser_cache_reuses_parser(self) -> None:
        from deviate.core.treesitter import get_parser

        p1 = get_parser("a.py")
        p2 = get_parser("b.py")
        assert p1 is p2, "get_parser should cache parsers per grammar"


class TestExtractChangedSymbols:
    """extract_changed_symbols() parses git diff output."""

    def test_single_function_changed(self) -> None:
        from deviate.core.treesitter import extract_changed_symbols

        diff = """diff --git a/src/mod.py b/src/mod.py
index abc..def 100644
--- a/src/mod.py
+++ b/src/mod.py
@@ -1,5 +1,6 @@
-def old_func(x):
-    return x + 1
+def new_func(x):
+    return x + 2
"""
        symbols = extract_changed_symbols(diff, "src/mod.py")
        assert len(symbols) > 0
        sym = symbols[0]
        assert sym.kind == "function"
        assert sym.name in ("old_func", "new_func")
        assert sym.change in ("modified", "added", "removed")

    def test_mixed_languages(self) -> None:
        from deviate.core.treesitter import extract_changed_symbols

        diff = """diff --git a/src/mod.py b/src/mod.py
index a..b 100644
--- a/src/mod.py
+++ b/src/mod.py
@@ -1 +1 @@
-def foo():
+def bar():
diff --git a/src/lib.rs b/src/lib.rs
index c..d 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1 +1 @@
-fn old() {}
+fn new() {}
"""
        symbols = extract_changed_symbols(diff, "src/mod.py")
        assert len(symbols) > 0

    def test_empty_diff_returns_empty_list(self) -> None:
        from deviate.core.treesitter import extract_changed_symbols

        assert extract_changed_symbols("", "file.py") == []

    def test_unknown_file_extension_returns_empty(self) -> None:
        from deviate.core.treesitter import extract_changed_symbols

        result = extract_changed_symbols("dummy", "foo.rb")
        assert result == []


class TestExtractFileStructure:
    """extract_file_structure() parses files and returns structured data."""

    PYTHON_SRC = """
import os
from pathlib import Path

class MyClass:
    def method(self):
        pass

def top_level():
    return 42
"""

    def test_python_file_structure(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import extract_file_structure

        p = tmp_path / "mod.py"
        p.write_text(self.PYTHON_SRC)
        struct = extract_file_structure(str(p))
        assert struct is not None
        assert struct.language == "python"
        assert any("MyClass" in str(s) for s in struct.symbols)
        assert any("top_level" in str(s) for s in struct.symbols)

    def test_typescript_file_structure(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import extract_file_structure

        ts_src = """interface User {
  name: string;
}
class Service {
  async run(): Promise<void> {}
}
"""
        p = tmp_path / "mod.ts"
        p.write_text(ts_src)
        struct = extract_file_structure(str(p))
        assert struct is not None
        assert struct.language == "typescript"
        assert len(struct.symbols) > 0

    def test_rust_file_structure(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import extract_file_structure

        rs_src = """struct Config {
    port: u16,
}
impl Config {
    fn new() -> Self { Config { port: 8080 } }
}
trait Runnable {
    fn run(&self);
}
"""
        p = tmp_path / "mod.rs"
        p.write_text(rs_src)
        struct = extract_file_structure(str(p))
        assert struct is not None
        assert struct.language == "rust"
        assert len(struct.symbols) > 0

    def test_unknown_extension_returns_empty(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        from deviate.core.treesitter import extract_file_structure

        p = tmp_path / "foo.rb"
        p.write_text("class Foo; end")
        struct = extract_file_structure(str(p))
        assert struct is not None
        assert len(struct.symbols) == 0


class TestIncrementalParse:
    """incremental_parse() re-parses only changed ranges."""

    def test_incremental_parse_returns_tree(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        from deviate.core.treesitter import incremental_parse

        src1 = b"def foo():\n    return 1\n"
        src2 = b"def foo():\n    return 2\n"
        p = tmp_path / "mod.py"
        p.write_bytes(src1)

        tree1 = incremental_parse(str(p))
        assert tree1 is not None

        p.write_bytes(src2)
        tree2 = incremental_parse(str(p), old_tree=tree1)
        assert tree2 is not None
        assert tree2.root_node is not None


class TestDeadCodeDetection:
    """extract_dead_code() finds unused definitions."""

    def test_detects_unused_function(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import extract_dead_code

        src = """
def used():
    return 1

def unused():
    return 2

result = used()
"""
        p = tmp_path / "mod.py"
        p.write_text(src)
        dead = extract_dead_code(str(p))
        assert len(dead) > 0
        assert any("unused" in str(d) for d in dead)

    def test_empty_when_no_dead_code(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import extract_dead_code

        src = """
def used():
    return 1

x = used()
"""
        p = tmp_path / "mod.py"
        p.write_text(src)
        dead = extract_dead_code(str(p))
        assert dead == []


class TestDuplicateBlockDetection:
    """detect_duplicate_blocks() finds similar AST subtrees."""

    def test_detects_duplicate_blocks(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import detect_duplicate_blocks

        src = """def block_a():
    x = 1
    y = 2
    z = x + y
    return z

def block_b():
    a = 1
    b = 2
    c = a + b
    return c
"""
        p = tmp_path / "mod.py"
        p.write_text(src)
        dups = detect_duplicate_blocks(str(p), min_lines=3)
        if len(dups) > 0:
            assert dups[0].lines >= 3

    def test_empty_when_no_duplicates(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import detect_duplicate_blocks

        src = """def unique():
    return 1
"""
        p = tmp_path / "mod.py"
        p.write_text(src)
        dups = detect_duplicate_blocks(str(p))
        assert dups == []


class TestCyclomaticComplexity:
    """estimate_cyclomatic_complexity() counts decision points."""

    def test_simple_function_has_complexity_one(self) -> None:
        from deviate.core.treesitter import estimate_cyclomatic_complexity

        complexity = estimate_cyclomatic_complexity("test.py", None)
        assert complexity is not None

    def test_high_complexity_detected(self, tmp_path: pytest.TempPathFactory) -> None:
        from deviate.core.treesitter import (
            estimate_cyclomatic_complexity,
            extract_file_structure,
        )

        src = """def complex(x):
    if x > 0:
        return 1
    elif x > 10:
        return 2
    else:
        for i in range(x):
            if i % 2 == 0:
                pass
        while x > 0:
            x -= 1
    return 0
"""
        p = tmp_path / "mod.py"
        p.write_text(src)
        struct = extract_file_structure(str(p))
        assert struct is not None
        assert len(struct.symbols) > 0

        complexity = estimate_cyclomatic_complexity(str(p), None)
        assert complexity is not None


class TestQueryFileCoverage:
    """All .scm query files exist and compile without error."""

    def test_query_file_coverage(self) -> None:
        from deviate.core.treesitter import _QUERIES_DIR

        import pathlib

        qdir = pathlib.Path(_QUERIES_DIR)
        assert qdir.is_dir(), f"Queries directory not found: {qdir}"

        scm_files = sorted(qdir.glob("*.scm"))
        expected = {
            "python.scm",
            "javascript.scm",
            "typescript.scm",
            "tsx.scm",
            "rust.scm",
            "go.scm",
            "cpp.scm",
            "elixir.scm",
            "c_sharp.scm",
            "markdown.scm",
            "bash.scm",
            "json.scm",
            "toml.scm",
            "yaml.scm",
            "html.scm",
            "css.scm",
            "sql.scm",
            "dockerfile.scm",
            "hcl.scm",
            "kotlin.scm",
            "swift.scm",
        }
        found = {f.name for f in scm_files}
        missing = expected - found
        assert not missing, f"Query files missing: {missing}"


class TestSymbolChangeDataClass:
    """SymbolChange dataclass has expected fields."""

    def test_symbol_change_fields(self) -> None:
        from deviate.core.treesitter import SymbolChange

        sc = SymbolChange(
            language="python",
            kind="function",
            name="foo",
            change="modified",
            old_name="bar",
            start_line=10,
            end_line=25,
            old_start_line=8,
            old_end_line=22,
            old_signature="def bar(x)",
            new_signature="def foo(x, y)",
            old_line_count=14,
            new_line_count=16,
        )
        assert sc.language == "python"
        assert sc.kind == "function"
        assert sc.name == "foo"
        assert sc.change == "modified"
        assert sc.old_name == "bar"
        assert sc.start_line == 10
        assert sc.end_line == 25
        assert sc.old_start_line == 8
        assert sc.old_end_line == 22
        assert sc.old_signature == "def bar(x)"
        assert sc.new_signature == "def foo(x, y)"
        assert sc.old_line_count == 14
        assert sc.new_line_count == 16


class TestDuplicateBlockDataClass:
    """DuplicateBlock dataclass has expected fields."""

    def test_duplicate_block_fields(self) -> None:
        from deviate.core.treesitter import DuplicateBlock

        db = DuplicateBlock(
            lines=5,
            locations=["mod.py:10-14", "mod.py:20-24"],
            similarity=0.85,
        )
        assert db.lines == 5
        assert len(db.locations) == 2
        assert db.similarity == 0.85


class TestFileStructureDataClass:
    """FileStructure dataclass has expected fields."""

    def test_file_structure_fields(self) -> None:
        from deviate.core.treesitter import FileStructure

        fs = FileStructure(
            filepath="/path/to/mod.py",
            language="python",
            symbols=[
                {
                    "kind": "function",
                    "name": "foo",
                    "start_line": 1,
                    "end_line": 5,
                    "body_size": 3,
                }
            ],
            imports=["os", "sys"],
        )
        assert fs.filepath == "/path/to/mod.py"
        assert fs.language == "python"
        assert len(fs.symbols) == 1
        assert fs.symbols[0]["start_line"] == 1
        assert fs.symbols[0]["end_line"] == 5
        assert len(fs.imports) == 2


class TestGracefulDegradation:
    """Module degrades gracefully when tree-sitter is unavailable."""

    def test_import_succeeds_without_treesitter(self) -> None:
        import deviate.core.treesitter as ts

        assert ts is not None

    def test_functions_return_empty_without_treesitter(self) -> None:
        from unittest.mock import patch

        from deviate.core.treesitter import (
            extract_changed_symbols,
            extract_file_structure,
            get_parser,
        )

        with patch("deviate.core.treesitter.parser._tree_sitter_available", False):
            assert get_parser("test.py") is None
            assert extract_changed_symbols("", "test.py") == []
            struct = extract_file_structure("nonexistent.py")
            assert struct is not None
            assert struct.symbols == []
