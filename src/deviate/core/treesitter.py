from __future__ import annotations

import re
from typing import Any

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Tree

_PARSER: Parser | None = None


def _get_parser() -> Parser:
    global _PARSER
    if _PARSER is None:
        py_lang = Language(tree_sitter_python.language())
        _PARSER = Parser(py_lang)
    return _PARSER


def _node_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode()


_FUNC_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)")
_CLASS_RE = re.compile(r"^\s*class\s+(\w+)")

_PARAM_NODE_TYPES = frozenset(
    {
        "identifier",
        "typed_parameter",
        "default_parameter",
        "typed_default_parameter",
        "list_splat_pattern",
        "dictionary_splat_pattern",
        "keyword_separator",
    }
)


def _parse_diff_hunks(diff_text: str) -> list[dict[str, Any]]:
    if not diff_text.strip():
        return []

    hunks: list[dict[str, Any]] = []
    current_hunk: dict[str, Any] | None = None
    current_file: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("@@"):
            if current_hunk is not None:
                hunks.append(current_hunk)
            current_hunk = {"file": current_file, "old_lines": [], "new_lines": []}
        elif current_hunk is not None:
            if line.startswith("-") and not line.startswith("---"):
                current_hunk["old_lines"].append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                current_hunk["new_lines"].append(line[1:])

    if current_hunk is not None:
        hunks.append(current_hunk)

    return hunks


def _build_symbol_map(lines: list[str]) -> dict[str, dict[str, str]]:
    symbols: dict[str, dict[str, str]] = {}
    for line in lines:
        m = _FUNC_RE.match(line)
        if m:
            symbols[m.group(1)] = {"type": "function", "signature": line.strip()}
            continue
        m = _CLASS_RE.match(line)
        if m:
            symbols[m.group(1)] = {"type": "class", "signature": line.strip()}
    return symbols


def extract_changed_symbols(diff_text: str) -> list[dict[str, Any]]:
    if not diff_text.strip():
        return []

    hunks = _parse_diff_hunks(diff_text)
    result: list[dict[str, Any]] = []

    for hunk in hunks:
        old_symbols = _build_symbol_map(hunk["old_lines"])
        new_symbols = _build_symbol_map(hunk["new_lines"])
        all_names = set(old_symbols) | set(new_symbols)
        file_path = hunk.get("file")

        for name in sorted(all_names):
            old_info = old_symbols.get(name)
            new_info = new_symbols.get(name)
            info = old_info or new_info
            entry: dict[str, Any] = {
                "type": info["type"],
                "file": file_path,
            }
            if old_info:
                entry["old_signature"] = old_info["signature"]
            if new_info:
                entry["new_signature"] = new_info["signature"]
            result.append(entry)

    return result


def _extract_params(fn_node: Node, source_bytes: bytes) -> list[str]:
    params_node = fn_node.child_by_field_name("parameters")
    if params_node is None:
        return []
    params: list[str] = []
    for child in params_node.children:
        if child.type in _PARAM_NODE_TYPES:
            params.append(_node_text(child, source_bytes))
    return params


def _extract_return_type(fn_node: Node, source_bytes: bytes) -> str | None:
    ret = fn_node.child_by_field_name("return_type")
    if ret is not None:
        return _node_text(ret, source_bytes)
    return None


def _extract_function(fn_node: Node, source_bytes: bytes) -> tuple[str, dict[str, Any]]:
    name = _node_text(fn_node.child_by_field_name("name"), source_bytes)
    return name, {
        "params": _extract_params(fn_node, source_bytes),
        "return_type": _extract_return_type(fn_node, source_bytes),
    }


def _extract_methods(body: Node, source_bytes: bytes) -> dict[str, dict[str, Any]]:
    methods: dict[str, dict[str, Any]] = {}
    for item in body.children:
        if item.type == "function_definition":
            mname, minfo = _extract_function(item, source_bytes)
            methods[mname] = minfo
    return methods


def extract_file_structure(source: str) -> dict[str, Any]:
    if not source.strip():
        return {"functions": {}, "classes": {}}

    parser = _get_parser()
    source_bytes = source.encode()
    tree = parser.parse(source_bytes)
    root = tree.root_node

    functions: dict[str, dict[str, Any]] = {}
    classes: dict[str, dict[str, Any]] = {}
    imports: list[str] = []

    for child in root.children:
        if child.type == "function_definition":
            name, info = _extract_function(child, source_bytes)
            functions[name] = info
        elif child.type == "class_definition":
            class_name = _node_text(child.child_by_field_name("name"), source_bytes)
            body = child.child_by_field_name("body")
            methods = _extract_methods(body, source_bytes) if body is not None else {}
            classes[class_name] = {"methods": methods}
        elif child.type in ("import_statement", "import_from_statement"):
            imports.append(_node_text(child, source_bytes))

    result: dict[str, Any] = {
        "functions": functions,
        "classes": classes,
    }
    if imports:
        result["imports"] = imports

    return result


def incremental_parse(source: str, old_tree: Tree | None = None) -> Tree | None:
    parser = _get_parser()
    source_bytes = source.encode()

    if old_tree is not None:
        result = parser.parse(source_bytes, old_tree)
    else:
        result = parser.parse(source_bytes)

    return result
