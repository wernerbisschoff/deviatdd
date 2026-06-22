from __future__ import annotations

import importlib
import logging
import os
import pathlib

from typing import Any

logger = logging.getLogger(__name__)

_QUERIES_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent / "queries"

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
