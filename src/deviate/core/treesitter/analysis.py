from __future__ import annotations

import logging
import os

from typing import Any

from deviate.core.treesitter.models import DuplicateBlock, FileStructure, SymbolChange
from deviate.core.treesitter.parser import (
    _CAP_KIND,
    _load_queries,
    _tree_sitter_available,
    get_language_id,
    get_parser,
    Parser,
    Query,
    QueryCursor,
)

logger = logging.getLogger(__name__)


__all__ = [
    "extract_file_structure",
    "incremental_parse",
    "extract_changed_symbols",
    "extract_dead_code",
    "detect_duplicate_blocks",
    "estimate_cyclomatic_complexity",
]


def _extract_symbols_from_parsed(
    tree: Any, grammar_id: str
) -> tuple[list[dict[str, str | int]], list[str]]:
    symbols: list[dict[str, str | int]] = []
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
                fn = _fn_node(node)
                srow = fn.start_point.row
                erow = fn.end_point.row
                signature = _extract_fn_signature(fn)
                entry: dict[str, str | int] = {
                    "kind": _CAP_KIND[cap_name],
                    "name": text,
                    "start_line": srow,
                    "end_line": erow,
                    "line_count": max(0, erow - srow + 1),
                }
                if signature:
                    entry["signature"] = signature
                symbols.append(entry)

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


def _fn_node(node: Any) -> Any:
    if Query is None:
        return node
    parent = getattr(node, "parent", None)
    if parent is None:
        return node
    ptype = getattr(parent, "type", "")
    if (
        "function" in ptype
        or "class" in ptype
        or "struct" in ptype
        or "interface" in ptype
        or ptype in ("trait_item", "impl_item")
    ):
        return parent
    grand = getattr(parent, "parent", None)
    if grand is not None:
        gtype = getattr(grand, "type", "")
        if (
            "function" in gtype
            or "class" in gtype
            or "struct" in gtype
            or "interface" in gtype
            or gtype in ("trait_item", "impl_item")
        ):
            return grand
    return node


def _extract_fn_signature(node: Any) -> str:
    if not _tree_sitter_available:
        return ""
    try:
        text = node.text.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if lines:
            return lines[0].strip()[:80]
        return text[:80].strip()
    except Exception:
        return ""


def _extract_fn_metadata(tree: Any, query: Any) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    if QueryCursor is None:
        return meta
    cursor = QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    for cap_name, nodes in captures.items():
        if cap_name not in _CAP_KIND:
            continue
        for node in nodes:
            text = node.text.decode("utf-8", errors="replace")
            fn = _fn_node(node)
            srow = fn.start_point.row
            erow = fn.end_point.row
            line_count = max(0, erow - srow + 1)
            signature = _extract_fn_signature(fn)
            meta[text] = {
                "kind": _CAP_KIND.get(cap_name, "function"),
                "start_line": srow,
                "end_line": erow,
                "signature": signature,
                "line_count": line_count,
            }
    return meta


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

        old_meta = _extract_fn_metadata(old_tree, query) if old_tree else {}
        new_meta = _extract_fn_metadata(new_tree, query) if new_tree else {}

        old_names = set(old_meta)
        new_names = set(new_meta)

        all_names = old_names | new_names

        for name in all_names:
            if name in old_names and name not in new_names:
                ch = "removed"
            elif name not in old_names and name in new_names:
                ch = "added"
            else:
                ch = "modified"

            o = old_meta.get(name, {})
            n = new_meta.get(name, {})
            kind = n.get("kind") or o.get("kind", "function")

            changes.append(
                SymbolChange(
                    language=lang_id,
                    kind=kind,
                    name=name,
                    change=ch,
                    old_name=o.get("signature", ""),
                    start_line=n.get("start_line", 0),
                    end_line=n.get("end_line", 0),
                    old_start_line=o.get("start_line", 0),
                    old_end_line=o.get("end_line", 0),
                    old_signature=o.get("signature", ""),
                    new_signature=n.get("signature", ""),
                    old_line_count=o.get("line_count", 0),
                    new_line_count=n.get("line_count", 0),
                )
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
            line_count = node.end_point.row - node.start_point.row + 1
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
        seen: dict[str, tuple[int, str]] = {}

        for row_start, row_end, lines, sig in blocks:
            loc = f"{os.path.basename(filepath)}:{row_start}-{row_end}"
            if sig in seen and abs(lines - seen[sig][0]) <= 1:
                duplicates.append(
                    DuplicateBlock(
                        lines=lines,
                        locations=[seen[sig][1], loc],
                        similarity=0.85,
                    )
                )
            else:
                seen[sig] = (lines, loc)

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
