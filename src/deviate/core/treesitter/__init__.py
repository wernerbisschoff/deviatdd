from __future__ import annotations

import importlib
import logging
import os
import pathlib

from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_QUERIES_DIR: pathlib.Path = pathlib.Path(__file__).parent / "queries"

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
    ".ex": "elixir",
    ".exs": "elixir",
    ".cs": "c_sharp",
    ".md": "markdown",
    ".mdx": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".less": "css",
    ".sql": "sql",
    "Dockerfile": "dockerfile",
    ".dockerfile": "dockerfile",
    ".tf": "hcl",
    ".tfvars": "hcl",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
}

_GRAMMAR_PACKAGES: dict[str, str] = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "tsx": "tree_sitter_typescript",
    "rust": "tree_sitter_rust",
    "go": "tree_sitter_go",
    "cpp": "tree_sitter_cpp",
    "elixir": "tree_sitter_elixir",
    "c_sharp": "tree_sitter_c_sharp",
    "markdown": "tree_sitter_markdown",
    "bash": "tree_sitter_bash",
    "json": "tree_sitter_json",
    "toml": "tree_sitter_toml",
    "yaml": "tree_sitter_yaml",
    "html": "tree_sitter_html",
    "css": "tree_sitter_css",
    "sql": "tree_sitter_sql",
    "dockerfile": "tree_sitter_dockerfile",
    "hcl": "tree_sitter_hcl",
    "kotlin": "tree_sitter_kotlin",
    "swift": "tree_sitter_swift",
}

_LANGUAGE_ATTRS: dict[str, str] = {
    "typescript": "language_typescript",
    "tsx": "language_tsx",
}

_CAP_KIND: dict[str, str] = {
    "function": "function",
    "method": "function",
    "class": "class",
    "struct": "class",
    "interface": "interface",
    "entry": "entry",
}

_tree_sitter_available = True
_parser_cache: dict[str, Any] = {}
_query_cache: dict[str, Any] = {}
_grammar_cache: dict[str, Any] = {}

try:
    from tree_sitter import Language, Parser, Query, QueryCursor, Tree
except ImportError:
    _tree_sitter_available = False
    Language = None
    Parser = None
    Query = None
    QueryCursor = None
    Tree = None


@dataclass
class SymbolChange:
    language: str
    kind: str
    name: str
    change: str
    old_name: str = ""


@dataclass
class DuplicateBlock:
    lines: int
    locations: list[str]
    similarity: float


@dataclass
class FileStructure:
    filepath: str
    language: str
    symbols: list[dict[str, str]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def get_language_id(filepath: str) -> str | None:
    ext = _get_extension(filepath)
    return EXTENSION_MAP.get(ext)


def get_parser(filepath: str) -> Any | None:
    if not _tree_sitter_available or Parser is None:
        return None
    lang_id = get_language_id(filepath)
    if lang_id is None:
        return None
    if lang_id in _parser_cache:
        return _parser_cache[lang_id]
    lang_obj = _load_language(lang_id)
    if lang_obj is None:
        return None
    try:
        parser = Parser(lang_obj)
        _parser_cache[lang_id] = parser
        return parser
    except Exception:
        logger.warning("Failed to create parser for %s", lang_id)
        return None


def _load_language(grammar_id: str) -> Any | None:
    if not _tree_sitter_available or Language is None:
        return None
    if grammar_id in _grammar_cache:
        return _grammar_cache[grammar_id]
    pkg_name = _GRAMMAR_PACKAGES.get(grammar_id)
    if pkg_name is None:
        return None
    try:
        pkg = importlib.import_module(pkg_name)
        lang_attr = _LANGUAGE_ATTRS.get(grammar_id, "language")
        cap_fn = getattr(pkg, lang_attr, None) or pkg.language
        capsule = cap_fn()
        lang_obj = Language(capsule)
        _grammar_cache[grammar_id] = lang_obj
        return lang_obj
    except Exception:
        logger.warning("Failed to load language %s", grammar_id)
        return None


def _get_extension(filepath: str) -> str:
    name = os.path.basename(filepath)
    if name == "Dockerfile":
        return "Dockerfile"
    _, ext = os.path.splitext(name)
    return ext.lower() if ext else ""


def _load_queries(grammar_id: str) -> Any | None:
    if not _tree_sitter_available or Query is None:
        return None
    if grammar_id in _query_cache:
        return _query_cache[grammar_id]
    qfile = _QUERIES_DIR / f"{grammar_id}.scm"
    if not qfile.exists():
        _query_cache[grammar_id] = None
        return None
    lang_obj = _load_language(grammar_id)
    if lang_obj is None:
        return None
    try:
        qtext = qfile.read_text()
        query = Query(lang_obj, qtext)
        _query_cache[grammar_id] = query
        return query
    except Exception:
        logger.warning("Failed to compile query for %s", grammar_id)
        return None


def _extract_symbols_from_parsed(
    tree: Any, grammar_id: str
) -> tuple[list[dict[str, str]], list[str]]:
    symbols: list[dict[str, str]] = []
    imports: list[str] = []

    query = _load_queries(grammar_id)
    if query is None:
        return symbols, imports
    if QueryCursor is None:
        return symbols, imports

    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)

    for cap_name, nodes in captures.items():
        for node in nodes:
            text = node.text.decode("utf-8", errors="replace")
            if cap_name == "import":
                imports.append(text)
            elif cap_name in _CAP_KIND:
                symbols.append({"kind": _CAP_KIND[cap_name], "name": text})

    return symbols, imports


def extract_file_structure(filepath: str) -> FileStructure:
    result = FileStructure(filepath=filepath, language="", symbols=[], imports=[])
    if not os.path.isfile(filepath):
        return result
    lang_id = get_language_id(filepath)
    if lang_id is None:
        logger.warning("Unknown extension for file: %s", filepath)
        return result
    result.language = lang_id
    parser = get_parser(filepath)
    if parser is None:
        return result
    try:
        with open(filepath, "rb") as f:
            src = f.read()
        tree = parser.parse(src)
        symbols, imports = _extract_symbols_from_parsed(tree, lang_id)
        result.symbols = symbols
        result.imports = imports
    except Exception:
        logger.warning("Failed to parse file: %s", filepath)
    return result


def incremental_parse(filepath: str, old_tree: Any = None) -> Any | None:
    if not _tree_sitter_available or Parser is None:
        return None
    parser = get_parser(filepath)
    if parser is None:
        return None
    try:
        with open(filepath, "rb") as f:
            src = f.read()
        if old_tree is not None:
            return parser.parse(src, old_tree)
        return parser.parse(src)
    except Exception as exc:
        logger.warning("Failed to parse: %s (%s)", filepath, exc)
        return None


def _reconstruct_sources_from_diff(
    diff_text: str, target_filepath: str
) -> tuple[bytes | None, bytes | None]:
    if not diff_text.strip():
        return None, None

    lines = diff_text.splitlines()
    old_lines: list[bytes] = []
    new_lines: list[bytes] = []
    in_target = False

    for line in lines:
        if line.startswith("diff --git"):
            parts = line.split()
            b_path = parts[-1] if len(parts) >= 4 else ""
            b_path = b_path.lstrip("b/")
            in_target = b_path == target_filepath
            if in_target:
                old_lines = []
                new_lines = []
            continue

        if not in_target:
            continue

        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if (
            line.startswith("index ")
            or line.startswith("new file")
            or line.startswith("deleted file")
        ):
            continue
        if line.startswith("@@"):
            continue

        if len(line) > 0:
            prefix = line[0]
            content = line[1:] if len(line) > 1 else ""
            content_bytes = content.encode("utf-8")
            if prefix == " ":
                old_lines.append(content_bytes)
                new_lines.append(content_bytes)
            elif prefix == "-":
                old_lines.append(content_bytes)
            elif prefix == "+":
                new_lines.append(content_bytes)

    old_src = b"\n".join(old_lines) if old_lines else None
    new_src = b"\n".join(new_lines) if new_lines else None
    return old_src, new_src


def _extract_fn_names(tree: Any, query: Any) -> set[str]:
    names: set[str] = set()
    if QueryCursor is None:
        return names
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    for cap_name, nodes in captures.items():
        if cap_name in ("function", "method", "class", "struct", "interface"):
            for node in nodes:
                names.add(node.text.decode("utf-8", errors="replace"))
    return names


def extract_changed_symbols(diff_text: str, filepath: str) -> list[SymbolChange]:
    if not _tree_sitter_available or Parser is None:
        return []

    lang_id = get_language_id(filepath)
    if lang_id is None:
        return []

    parser = get_parser(filepath)
    if parser is None:
        return []

    old_src, new_src = _reconstruct_sources_from_diff(diff_text, filepath)
    if old_src is None and new_src is None:
        return []

    query = _load_queries(lang_id)
    if query is None or QueryCursor is None:
        return []

    changes: list[SymbolChange] = []

    try:
        old_tree = parser.parse(old_src) if old_src is not None else None
        new_tree = parser.parse(new_src) if new_src is not None else None
        src = new_src or old_src

        old_names = _extract_fn_names(old_tree, query) if old_tree else set()
        new_names = _extract_fn_names(new_tree, query) if new_tree else set()

        kind_map: dict[str, str] = {}
        if src:
            kind_tree = new_tree or old_tree
            if kind_tree:
                kind_map = _build_kind_map(kind_tree, query)

        all_names = old_names | new_names

        for name in all_names:
            if name in old_names and name not in new_names:
                ch = "removed"
            elif name not in old_names and name in new_names:
                ch = "added"
            else:
                ch = "modified"
            kind = kind_map.get(name, "function")
            changes.append(
                SymbolChange(language=lang_id, kind=kind, name=name, change=ch)
            )
    except Exception:
        pass

    return changes


def _build_kind_map(tree: Any, query: Any) -> dict[str, str]:
    kind_map: dict[str, str] = {}
    if QueryCursor is None:
        return kind_map
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    for cap_name, nodes in captures.items():
        mapped = _CAP_KIND.get(cap_name)
        if mapped:
            for node in nodes:
                name = node.text.decode("utf-8", errors="replace")
                kind_map[name] = mapped
    return kind_map


def extract_dead_code(filepath: str) -> list[str]:
    if not _tree_sitter_available or QueryCursor is None:
        return []

    lang_id = get_language_id(filepath)
    if lang_id is None:
        return []

    parser = get_parser(filepath)
    if parser is None:
        return []

    query = _load_queries(lang_id)
    if query is None:
        return []

    try:
        with open(filepath, "rb") as f:
            src = f.read()
        tree = parser.parse(src)

        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        defined_functions: list[str] = []
        called_functions: list[str] = []

        for cap_name, nodes in captures.items():
            for node in nodes:
                text = node.text.decode("utf-8", errors="replace")
                if cap_name in ("function", "method"):
                    defined_functions.append(text)
                elif cap_name == "call":
                    called_functions.append(text)

        defined_set = set(defined_functions)
        called_set = set(called_functions)
        dead = defined_set - called_set

        return list(dead)
    except Exception:
        logger.warning("Failed to detect dead code in: %s", filepath)
        return []


def detect_duplicate_blocks(filepath: str, min_lines: int = 5) -> list[DuplicateBlock]:
    if not _tree_sitter_available or Parser is None:
        return []

    lang_id = get_language_id(filepath)
    if lang_id is None:
        return []

    parser = get_parser(filepath)
    if parser is None:
        return []

    try:
        with open(filepath, "rb") as f:
            src = f.read()
        tree = parser.parse(src)

        blocks: list[tuple[int, int, int, str]] = []
        stack = [tree.root_node]

        while stack:
            node = stack.pop()
            line_count = node.end_point.row - node.start_point.row
            if node.child_count > 1 and line_count >= min_lines:
                children_types = tuple(c.type for c in node.children)
                if children_types:
                    blocks.append(
                        (
                            node.start_point.row,
                            node.end_point.row,
                            line_count,
                            str(children_types),
                        )
                    )
            for child in node.children:
                stack.append(child)

        duplicates: list[DuplicateBlock] = []
        seen: dict[str, int] = {}

        for row_start, row_end, lines, sig in blocks:
            if sig in seen and abs(lines - seen[sig]) <= 1:
                duplicates.append(
                    DuplicateBlock(
                        lines=lines,
                        locations=[
                            f"{os.path.basename(filepath)}:{row_start}-{row_end}"
                        ],
                        similarity=0.85,
                    )
                )
            else:
                seen[sig] = lines

        return duplicates
    except Exception:
        logger.warning("Failed to detect duplicate blocks in: %s", filepath)
        return []


def estimate_cyclomatic_complexity(filepath: str, func_node: Any | None) -> int:
    if not _tree_sitter_available or QueryCursor is None:
        return 1

    lang_id = get_language_id(filepath)
    if lang_id is None:
        return 1

    parser = get_parser(filepath)
    if parser is None:
        return 1

    try:
        if func_node is not None:
            target_node = func_node
        else:
            with open(filepath, "rb") as f:
                src = f.read()
            if not src.strip():
                return 1
            tree = parser.parse(src)
            target_node = tree.root_node

        query = _load_queries(lang_id)
        if query is None:
            return 1
        cursor = QueryCursor(query)
        captures = cursor.captures(target_node)
        decision_count = 0
        for cap_name, nodes in captures.items():
            if cap_name in ("conditional", "loop"):
                decision_count += len(nodes)

        return decision_count + 1
    except Exception:
        return 1
