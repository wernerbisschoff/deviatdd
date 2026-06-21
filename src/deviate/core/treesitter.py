from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Tree

from deviate.core._shared import git_env as _git_env

_PARSER: Parser | None = None


def _get_parser() -> Parser:
    global _PARSER
    if _PARSER is None:
        py_lang = Language(tree_sitter_python.language())
        _PARSER = Parser(py_lang)
    return _PARSER


def _node_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode()


_BOOL_OPS = frozenset({"and", "or"})
_CONTROL_KEYWORDS = frozenset({"if", "elif", "for", "while", "except"})

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


def get_file_at_revision(repo: Path, revision: str, filepath: str) -> str | None:
    """Fetch file content at a given git revision. Returns None if file didn't exist."""
    try:
        result = subprocess.run(
            ["git", "show", f"{revision}:{filepath}"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _count_function_lines(fn_node: Node) -> int:
    """Count lines in a function body (end_row - start_row + 1)."""
    return fn_node.end_point[0] - fn_node.start_point[0] + 1


def _compute_cyclomatic_complexity(fn_node: Node, source_bytes: bytes) -> int:
    """Compute McCabe cyclomatic complexity for a function via tree-sitter walk."""
    base = 1
    branches = 0
    stack = [fn_node]
    while stack:
        node = stack.pop()
        if node.type == "if_statement":
            branches += 1
            for child in node.children:
                if child.type == "elif_clause":
                    branches += 1
        elif node.type in ("for_statement", "while_statement"):
            branches += 1
        elif node.type == "try_statement":
            for child in node.children:
                if child.type == "except_clause":
                    branches += 1
        elif node.type == "boolean_operator":
            op_text = _node_text(node, source_bytes)
            if op_text.strip() in _BOOL_OPS:
                branches += 1
        for child in node.children:
            stack.append(child)
    return base + branches


def _find_function_calls(source_bytes: bytes, fn_name: str) -> int:
    """Count call sites of a function within source (excluding its own definition)."""
    pattern = re.compile(rf"(?<!def )\b{re.escape(fn_name)}\s*\(")
    # Count all call patterns, then subtract 1 for the definition line
    matches = pattern.findall(source_bytes.decode())
    return max(0, len(matches))


def _walk_imports(root: Node, source_bytes: bytes) -> list[str]:
    """Extract import statements from the root node."""
    imports: list[str] = []
    for child in root.children:
        if child.type in ("import_statement", "import_from_statement"):
            imports.append(_node_text(child, source_bytes))
    return imports


def _signature_str(name: str, info: dict[str, Any]) -> str:
    """Build a compact signature string from function info."""
    params = ", ".join(info.get("params", []))
    sig = f"def {name}({params})"
    ret = info.get("return_type")
    if ret:
        sig += f" -> {ret}"
    return sig


def ast_diff_files(
    old_source: str,
    new_source: str,
    filepath: str = "",
) -> dict[str, Any]:
    """Compare two source versions and return a structured structural diff.

    Returns a dict with keys: change_type, functions_added, functions_removed,
    functions_modified, classes_added, classes_removed, classes_modified,
    imports_added, imports_removed, complexity_warnings, dead_functions.
    """
    old_clean = old_source.strip() if old_source else ""
    new_clean = new_source.strip() if new_source else ""
    old_empty = not old_clean
    new_empty = not new_clean

    if old_empty and new_empty:
        return {"change_type": "unchanged"}

    if old_empty and not new_empty:
        change_type = "added"
    elif not old_empty and new_empty:
        change_type = "deleted"
    else:
        change_type = "modified"

    result: dict[str, Any] = {
        "change_type": change_type,
        "file": filepath,
    }

    old_data = (
        extract_file_structure(old_source)
        if old_source
        else {"functions": {}, "classes": {}, "imports": []}
    )
    new_data = (
        extract_file_structure(new_source)
        if new_source
        else {"functions": {}, "classes": {}, "imports": []}
    )

    old_funcs: dict = old_data.get("functions", {})
    new_funcs: dict = new_data.get("functions", {})
    old_classes: dict = old_data.get("classes", {})
    new_classes: dict = new_data.get("classes", {})

    old_func_names = set(old_funcs)
    new_func_names = set(new_funcs)
    common_funcs = old_func_names & new_func_names
    added_func_names = new_func_names - old_func_names
    removed_func_names = old_func_names - new_func_names

    # Added functions
    added: list[dict[str, Any]] = []
    for name in sorted(added_func_names):
        info = new_funcs[name]
        added.append(
            {
                "name": name,
                "signature": _signature_str(name, info),
                "params": info.get("params", []),
                "return_type": info.get("return_type"),
            }
        )

    # Removed functions
    removed: list[dict[str, Any]] = []
    for name in sorted(removed_func_names):
        info = old_funcs[name]
        removed.append(
            {
                "name": name,
                "signature": _signature_str(name, info),
            }
        )

    # Modified functions
    modified: list[dict[str, Any]] = []
    modified_func_names: set[str] = set()
    for name in sorted(common_funcs):
        old_info = old_funcs[name]
        new_info = new_funcs[name]
        old_params = old_info.get("params", [])
        new_params = new_info.get("params", [])
        old_ret = old_info.get("return_type")
        new_ret = new_info.get("return_type")
        if old_params != new_params or old_ret != new_ret:
            modified.append(
                {
                    "name": name,
                    "old_signature": _signature_str(name, old_info),
                    "new_signature": _signature_str(name, new_info),
                    "old_params": old_params,
                    "new_params": new_params,
                    "return_type_changed": old_ret != new_ret,
                }
            )
            modified_func_names.add(name)

    result["functions_added"] = added
    result["functions_removed"] = removed
    result["functions_modified"] = modified

    # Class diff
    old_cls_names = set(old_classes)
    new_cls_names = set(new_classes)
    common_classes = old_cls_names & new_cls_names

    added_classes: list[dict[str, Any]] = []
    for name in sorted(new_cls_names - old_cls_names):
        cls_info = new_classes[name]
        added_classes.append(
            {
                "name": name,
                "methods": sorted(cls_info.get("methods", {})),
            }
        )

    removed_classes: list[dict[str, Any]] = []
    for name in sorted(old_cls_names - new_cls_names):
        removed_classes.append({"name": name})

    modified_classes: list[dict[str, Any]] = []
    for name in sorted(common_classes):
        old_methods = set(old_classes[name].get("methods", {}))
        new_methods = set(new_classes[name].get("methods", {}))
        methods_added = sorted(new_methods - old_methods)
        methods_removed = sorted(old_methods - new_methods)
        if methods_added or methods_removed:
            modified_classes.append(
                {
                    "name": name,
                    "methods_added": methods_added,
                    "methods_removed": methods_removed,
                }
            )

    result["classes_added"] = added_classes
    result["classes_removed"] = removed_classes
    result["classes_modified"] = modified_classes

    # Import diff
    old_imports = set(old_data.get("imports", []))
    new_imports = set(new_data.get("imports", []))
    result["imports_added"] = sorted(new_imports - old_imports) if not new_empty else []
    result["imports_removed"] = (
        sorted(old_imports - new_imports) if not old_empty else []
    )

    # Complexity and dead code analysis (only on new/modified functions)
    complexity_warnings: list[dict[str, Any]] = []
    dead_functions: list[str] = []
    if new_source and not new_empty:
        parser = _get_parser()
        new_bytes = new_source.encode()
        tree = parser.parse(new_bytes)
        root = tree.root_node
        all_new_funcs = extract_file_structure(new_source).get("functions", {})

        names_to_check = added_func_names | modified_func_names
        modified_class_method_names: set[str] = set()
        for cm in modified_classes:
            for m in cm.get("methods_added", []):
                modified_class_method_names.add(f"{cm['name']}.{m}")

        for child in root.children:
            if child.type == "function_definition":
                name = _node_text(child.child_by_field_name("name"), new_bytes)
                if name in names_to_check:
                    cc = _compute_cyclomatic_complexity(child, new_bytes)
                    lines = _count_function_lines(child)
                    entry: dict[str, Any] = {
                        "function": name,
                        "complexity": cc,
                        "lines": lines,
                    }
                    if cc >= 10:
                        entry["reason"] = "high_complexity"
                        complexity_warnings.append(entry)
                    elif lines > 30:
                        entry["reason"] = "long_function"
                        complexity_warnings.append(entry)
            elif child.type == "class_definition":
                class_name = _node_text(child.child_by_field_name("name"), new_bytes)
                body = child.child_by_field_name("body")
                if body is not None:
                    for item in body.children:
                        if item.type == "function_definition":
                            mname = _node_text(
                                item.child_by_field_name("name"), new_bytes
                            )
                            full_name = f"{class_name}.{mname}"
                            if (
                                full_name in modified_class_method_names
                                or mname in added_func_names
                            ):
                                cc = _compute_cyclomatic_complexity(item, new_bytes)
                                lines = _count_function_lines(item)
                                entry = {
                                    "function": full_name,
                                    "complexity": cc,
                                    "lines": lines,
                                }
                                if cc >= 10:
                                    entry["reason"] = "high_complexity"
                                    complexity_warnings.append(entry)
                                elif lines > 30:
                                    entry["reason"] = "long_function"
                                    complexity_warnings.append(entry)

        # Dead function detection: functions in new version with no internal call sites
        for name, info in all_new_funcs.items():
            if name in names_to_check:
                calls = _find_function_calls(new_bytes, name)
                if calls == 0:
                    dead_functions.append(name)

    result["complexity_warnings"] = complexity_warnings
    result["dead_functions"] = dead_functions

    return result
