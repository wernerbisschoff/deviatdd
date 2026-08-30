"""Manual honeycomb test thinning for ``/deviate-prune``.

Deterministic keep/drop list: pytest marks and name tags first, then
body heuristics for untagged tests. Spec files and JSONL ledgers are
never unlinked.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from deviate.core.issues import resolve_issue, resolve_issue_artifact_path
from deviate.state.config import SessionState

DROP_TEST_TAGS = frozenset({"spy", "impl"})
KEEP_TEST_TAGS = frozenset({"behavioral", "ac"})
PROTECTED_BASENAMES = frozenset(
    {"explore.md", "prd.md", "constitution.md", "plan.md", "tasks.md"}
)
LEDGER_REWRITE_RE = re.compile(r"\b(compact|squash|rewrite)\b", re.IGNORECASE)
AC_TOKEN_RE = re.compile(r"\bAC-(?:PLAN-\d{3}|[A-Z]+-\d{3}-\d{2})\b")
TAG_SEGMENT_RE = re.compile(
    r"(?:^|[_-])(spy|impl|behavioral|ac)(?:$|[_-])", re.IGNORECASE
)
ISSUE_ID_RE = re.compile(r"\bISS-(?:ADH-)?\d{3}(?:-\d{3})?\b")
SPY_ASSERT_RE = re.compile(
    r"\b(?:assert_called|assert_called_once|assert_called_with|"
    r"assert_called_once_with|assert_not_called|assert_has_calls|"
    r"assert_any_call|call_count|mock_calls|mocker\.spy)\b"
)
PRIVATE_ATTR_RE = re.compile(r"(?:\b(?!self|cls)\w+)\._[A-Za-z]\w*\s*(?!\()")
EXTERNAL_BOUNDARY_MOCK_RE = re.compile(
    r"\b(?:subprocess\.run|subprocess\.Popen|\bPopen\b|_run_pytest|"
    r"run_safe_command|invoke_agent|_invoke_agent|\bcodex exec\b|spawn|"
    r"run_pytest)"
)

PATCH_PRIVATE_RE = re.compile(r"patch(?:\.object)?\([^)]*['\"]_[A-Za-z]")

PUBLIC_IO_RE = re.compile(
    r"\b(?:assert|raises|t\.Fail|t\.Errorf|t\.Fatal|t\.Fatalf|"
    r"expect\(|toBe\(|toEqual\(|should\.|\.should|require\.|"
    r"assertEqual|assertTrue|assertFalse|assertThat)\b"
)

PruneStatus = Literal[
    "READY",
    "IN_FLIGHT",
    "LEDGER_REWRITE_REJECTED",
    "NO_ISSUE",
    "ONE_ISSUE_ONLY",
    "FAILURE",
]
TestKind = Literal["keep", "drop"]


@dataclass(frozen=True)
class TestItem:
    """One discovered test function scoped to the targeted issue."""

    path: Path
    name: str
    kind: TestKind
    source: str

    @property
    def qualname(self) -> str:
        return f"{self.path.as_posix()}::{self.name}"


@dataclass
class PrunePlan:
    """Inventory + gate result for one prune invocation."""

    status: PruneStatus
    issue_id: str | None = None
    issue_status: str | None = None
    spec_deletes: list[Path] = field(default_factory=list)
    spec_keeps: list[Path] = field(default_factory=list)
    test_drop: list[TestItem] = field(default_factory=list)
    test_keep: list[TestItem] = field(default_factory=list)
    unmatched_acs: list[str] = field(default_factory=list)
    reason: str = ""
    issue_dir: Path | None = None

    @property
    def ledger_untouched(self) -> bool:
        return True


def is_ledger_rewrite_request(text: str) -> bool:
    """Return True when *text* asks to compact, squash, or rewrite a ledger."""
    return bool(LEDGER_REWRITE_RE.search(text or ""))


def extract_plan_ac_tokens(plan_text: str) -> list[str]:
    """Return first-seen plan AC tokens (``AC-PLAN-NNN`` or ``AC-EPIC-NNN-NN``)."""
    return list(dict.fromkeys(AC_TOKEN_RE.findall(plan_text or "")))


def classify_test(
    name: str,
    markers: set[str] | None = None,
    body: str | None = None,
) -> TestKind:
    """Keep ``behavioral`` / ``ac``; drop ``spy`` / ``impl``.

    Untagged tests are classified from *body* (honeycomb). Absence of
    marks or name tags is not an auto-keep.
    """
    tags = {tag.lower() for tag in (markers or set())} | _name_tags(name)
    if tags & KEEP_TEST_TAGS:
        return "keep"
    if tags & DROP_TEST_TAGS:
        return "drop"
    return _classify_body(body or "")


def resolve_prune_issue_id(root: Path, issue_id: str | None) -> str | None:
    """Resolve one issue id from ``--issue`` or ``session.active_issue_id``."""
    if issue_id and issue_id.strip():
        return issue_id.strip()
    session = SessionState.load(root / ".deviate" / "session.json")
    if session.active_issue_id:
        return session.active_issue_id
    return None


def extra_issue_ids(intent: str, issue_id: str | None) -> list[str]:
    """Return extra ISS-* ids in *intent* that are not the targeted issue."""
    found = list(dict.fromkeys(ISSUE_ID_RE.findall(intent or "")))
    if issue_id:
        found = [item for item in found if item != issue_id]
    return found


def build_prune_plan(
    root: Path,
    issue_id: str | None = None,
    *,
    intent: str = "",
) -> PrunePlan:
    """Inventory one issue's tests. Never schedules spec deletes."""
    if is_ledger_rewrite_request(intent):
        return PrunePlan(
            status="LEDGER_REWRITE_REJECTED",
            issue_id=issue_id,
            reason=(
                "LEDGER_REWRITE_REJECTED: prune never compacts, squashes, "
                "or rewrites JSONL ledgers"
            ),
        )

    resolved = resolve_prune_issue_id(root, issue_id)
    extras = extra_issue_ids(intent, resolved)
    if extras:
        return PrunePlan(
            status="ONE_ISSUE_ONLY",
            issue_id=resolved,
            reason=(
                "ONE_ISSUE_ONLY: prune accepts one issue per invocation; "
                f"extra ids: {', '.join(extras)}"
            ),
        )
    if resolved is None:
        return PrunePlan(
            status="NO_ISSUE",
            reason="NO_ISSUE: pass --issue or set session.active_issue_id",
        )

    record = resolve_issue(resolved, root / "specs" / "issues.jsonl")
    if record is None or not record.source_file:
        return PrunePlan(
            status="FAILURE",
            issue_id=resolved,
            reason=f"ISSUE_NOT_FOUND: {resolved} is absent from specs/issues.jsonl",
        )

    issue_dir = resolve_issue_artifact_path(root, record.source_file, "plan.md").parent
    keeps = _protected_keeps(root, record.source_file)
    tests = discover_issue_tests(root, resolved, record.source_file)
    drop_tests = [item for item in tests if item.kind == "drop"]
    keep_tests = [item for item in tests if item.kind == "keep"]
    plan_path = issue_dir / "plan.md"
    plan_tokens = (
        extract_plan_ac_tokens(plan_path.read_text(encoding="utf-8"))
        if plan_path.is_file()
        else []
    )
    unmatched = _unmatched_acs(plan_tokens, keep_tests)

    if record.status != "COMPLETED":
        return PrunePlan(
            status="IN_FLIGHT",
            issue_id=resolved,
            issue_status=record.status,
            spec_deletes=[],
            spec_keeps=keeps,
            test_drop=drop_tests,
            test_keep=keep_tests,
            unmatched_acs=unmatched,
            reason=(
                f"IN_FLIGHT: {resolved} is {record.status}; "
                "prune still thins tests and never deletes spec files"
            ),
            issue_dir=issue_dir,
        )

    return PrunePlan(
        status="READY",
        issue_id=resolved,
        issue_status=record.status,
        spec_deletes=[],
        spec_keeps=keeps,
        test_drop=drop_tests,
        test_keep=keep_tests,
        unmatched_acs=unmatched,
        issue_dir=issue_dir,
    )


def discover_issue_tests(root: Path, issue_id: str, source_file: str) -> list[TestItem]:
    """Classify tests in files that mention *issue_id* or the issue slug."""
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return []
    slug = PurePosixPath(source_file).stem
    needles = {issue_id, slug}
    items: list[TestItem] = []
    patterns = ("test_*", "*_test", "*.spec.*", "*_test.*")
    for pattern in patterns:
        for path in sorted(tests_root.rglob(pattern)):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            rel = path.relative_to(root)
            haystack = f"{rel.as_posix()}\n{text}"
            if not any(needle and needle in haystack for needle in needles):
                continue
            items.extend(_parse_test_items(rel, text))
    return items


def apply_prune(root: Path, plan: PrunePlan) -> None:
    """Apply honeycomb test thinning. Never unlinks spec files or ledgers."""
    if plan.status in {"LEDGER_REWRITE_REJECTED", "NO_ISSUE", "ONE_ISSUE_ONLY"}:
        return
    _thin_tests(root, plan.test_drop)


def is_protected_spec(path: Path, root: Path) -> bool:
    """Return True for ledgers, cycle markdown, epic explore/prd, and issue md."""
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return True
    if rel == "specs/issues.jsonl" or rel.endswith("/tasks.jsonl"):
        return True
    if rel == "specs/_product/flows.jsonl" or rel.startswith("specs/_product/"):
        return True
    if path.name in PROTECTED_BASENAMES:
        return True
    if "/issues/" in rel and rel.endswith(".md"):
        return True
    return True


def ledger_paths(root: Path) -> list[Path]:
    """Return existing append-only JSONL ledgers. Missing flows.jsonl is skipped."""
    found: list[Path] = []
    issues = root / "specs" / "issues.jsonl"
    if issues.is_file():
        found.append(issues)
    found.extend(sorted(root.glob("specs/**/tasks.jsonl")))
    flows = root / "specs" / "_product" / "flows.jsonl"
    if flows.is_file():
        found.append(flows)
    return found


def snapshot_ledgers(root: Path) -> dict[str, bytes]:
    """Byte-snapshot existing ledgers so callers can assert they stayed put."""
    return {str(path): path.read_bytes() for path in ledger_paths(root)}


def plan_to_contract(root: Path, plan: PrunePlan) -> dict[str, object]:
    """JSON contract consumed by ``/deviate-prune`` after ``deviate prune pre``."""

    def rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    return {
        "status": plan.status,
        "issue_id": plan.issue_id,
        "issue_status": plan.issue_status,
        "spec_deletes": [rel(path) for path in plan.spec_deletes],
        "spec_keeps": [rel(path) for path in plan.spec_keeps],
        "test_drop": [item.qualname for item in plan.test_drop],
        "test_keep": [item.qualname for item in plan.test_keep],
        "unmatched_acs": list(plan.unmatched_acs),
        "ledger_untouched": True,
        "reason": plan.reason,
        "repo_root": str(root),
    }


def _protected_keeps(root: Path, source_file: str) -> list[Path]:
    keeps: list[Path] = []
    issue_md = root / source_file
    if issue_md.is_file():
        keeps.append(issue_md)
    epic = PurePosixPath(source_file).parent.parent.name
    for name in ("explore.md", "prd.md", "plan.md", "tasks.md"):
        candidate = root / "specs" / epic / name
        if candidate.is_file() and candidate not in keeps:
            keeps.append(candidate)
    issue_dir = resolve_issue_artifact_path(root, source_file, "plan.md").parent
    for name in ("plan.md", "tasks.md", "design.md", "data-model.md"):
        candidate = issue_dir / name
        if candidate.is_file() and candidate not in keeps:
            keeps.append(candidate)
    shared_prd = root / "specs" / "adhoc" / "prd.md"
    if shared_prd.is_file() and shared_prd not in keeps:
        keeps.append(shared_prd)
    return keeps


def _unmatched_acs(tokens: list[str], keep_tests: list[TestItem]) -> list[str]:
    corpus = "\n".join(f"{item.name}\n{item.source}" for item in keep_tests)
    return [token for token in tokens if token not in corpus]


def _name_tags(name: str) -> set[str]:
    tags = {match.group(1).lower() for match in TAG_SEGMENT_RE.finditer(name)}
    # Go/Rust camelCase: TestBehavioralFoo (capitalized segment, exact case)
    for token in ("behavioral", "spy", "impl", "ac"):
        camel = token[0].upper() + token[1:]
        if camel in name:
            tags.add(token)
    return tags


def _classify_body(body: str) -> TestKind:
    if not body.strip():
        return "drop"
    if PATCH_PRIVATE_RE.search(body):
        return "drop"
    is_external_boundary_mock = bool(EXTERNAL_BOUNDARY_MOCK_RE.search(body))
    if SPY_ASSERT_RE.search(body) and not is_external_boundary_mock:
        return "drop"
    if PRIVATE_ATTR_RE.search(body):
        return "drop"
    if AC_TOKEN_RE.search(body) or PUBLIC_IO_RE.search(body):
        return "keep"
    return "drop"


def _decorator_tail(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


def _marker_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        tail = _decorator_tail(decorator)
        if tail:
            names.add(tail)
    return names


def _node_span(node: ast.AST) -> tuple[int, int]:
    start = getattr(node, "lineno", 1)
    for decorator in getattr(node, "decorator_list", []):
        start = min(start, decorator.lineno)
    end = getattr(node, "end_lineno", None) or start
    return start, end


def _parse_test_items(rel: Path, text: str) -> list[TestItem]:
    """Classify tests in *text*. Uses AST for Python; regex fallback for other languages."""
    if rel.suffix == ".py":
        return _parse_python_test_items(rel, text)
    return _parse_other_test_items(rel, text)


def _parse_python_test_items(rel: Path, text: str) -> list[TestItem]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    file_drop = bool(_name_tags(rel.stem) & DROP_TEST_TAGS)
    items: list[TestItem] = []
    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        markers = _marker_names(node)
        start, end = _node_span(node)
        source = "\n".join(lines[start - 1 : end])
        kind = classify_test(node.name, markers, source)
        if (
            kind == "keep"
            and file_drop
            and not (_name_tags(node.name) & KEEP_TEST_TAGS or markers & KEEP_TEST_TAGS)
        ):
            kind = "drop"
        items.append(TestItem(path=rel, name=node.name, kind=kind, source=source))
    return items


def _parse_other_test_items(rel: Path, text: str) -> list[TestItem]:
    """Regex-based test discovery for non-Python files (Go, Rust, JS, Elixir, ...)."""
    file_drop = bool(_name_tags(rel.stem) & DROP_TEST_TAGS)
    items: list[TestItem] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        name = _test_name_from_line(line)
        if not name:
            continue
        start = index
        end = _body_end(lines, index)
        source = "\n".join(lines[start - 1 : end])
        markers = _markers_before(lines, index - 1)
        kind = classify_test(name, markers, source)
        if (
            kind == "keep"
            and file_drop
            and not (_name_tags(name) & KEEP_TEST_TAGS or markers & KEEP_TEST_TAGS)
        ):
            kind = "drop"
        items.append(TestItem(path=rel, name=name, kind=kind, source=source))
    return items


def _test_name_from_line(line: str) -> str | None:
    """Return a test name from a declaration line, or None."""
    s = line.strip()
    if not s:
        return None
    for pattern in (
        r"^\s*test_[A-Za-z0-9_]+\s*\(?\s*:",
        r"^\s*(?:pub\s+)?fn\s+test_[A-Za-z0-9_]+\s*\(",
        r"^\s*(?:pub\s+)?fn\s+Test[A-Za-z0-9_]+\s*\(",
        r"^\s*func\s+Test[A-Za-z0-9_]+\s*\(",
        r"^\s*(?:it|test)\(['\"][^'\"]+['\"]",
        r"^\s*describe\(['\"]",
    ):
        if re.match(pattern, s):
            m = re.search(
                r"(?:test_[A-Za-z0-9_]+|Test[A-Za-z0-9_]+|func\s+Test[A-Za-z0-9_]+|[\w/\- ]+?)\s*\(",
                s,
            )
            if m:
                return (
                    m.group(0)
                    .replace("func ", "")
                    .replace("fn ", "")
                    .rstrip(" (")
                    .strip()
                )
    return None


def _body_end(lines: list[str], start_index: int) -> int:
    """Approximate the end line of a test body by brace/indent balance."""
    depth = 0
    for index in range(start_index - 1, len(lines)):
        line = lines[index]
        depth += line.count("{") - line.count("}")
        stripped = line.strip()
        if depth <= 0 and (stripped.endswith(")") or not stripped):
            return index + 1
    return len(lines)


def _markers_before(lines: list[str], line_index: int) -> set[str]:
    """Collect tag/marker tokens on the lines immediately before *line_index*."""
    markers: set[str] = set()
    for index in range(max(0, line_index - 2), line_index):
        line = lines[index].strip()
        if line.startswith("#[") or line.startswith("@") or "@tag" in line:
            for token in ("behavioral", "spy", "impl", "ac"):
                if token in line:
                    markers.add(token)
    return markers


def _thin_tests(root: Path, drop_items: list[TestItem]) -> None:
    by_path: dict[Path, list[TestItem]] = {}
    for item in drop_items:
        by_path.setdefault(item.path, []).append(item)
    for rel, items in by_path.items():
        path = rel if rel.is_absolute() else root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        remaining = [
            item
            for item in _parse_test_items(rel, text)
            if item.name not in {drop.name for drop in items}
        ]
        if not remaining:
            path.unlink()
            continue
        drop_names = {item.name for item in items}
        if rel.suffix == ".py":
            rewritten = _strip_functions(text, drop_names)
        else:
            rewritten = _strip_other_functions(text, drop_names)
        if rewritten is None or not rewritten.strip():
            path.unlink()
        else:
            path.write_text(rewritten, encoding="utf-8")


def _strip_functions(text: str, drop_names: set[str]) -> str | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in drop_names:
            ranges.append(_node_span(node))
    if not ranges:
        return text
    skip = {line for start, end in ranges for line in range(start, end + 1)}
    kept = [
        line
        for index, line in enumerate(text.splitlines(keepends=True), start=1)
        if index not in skip
    ]
    return "".join(kept)


def _strip_other_functions(text: str, drop_names: set[str]) -> str | None:
    """Line-based removal of test blocks for non-Python files."""
    lines = text.splitlines()
    skip: set[int] = set()
    for index, line in enumerate(lines, start=1):
        name = _test_name_from_line(line)
        if name in drop_names:
            end = _body_end(lines, index)
            skip.update(range(index, end + 1))
    if not skip:
        return text
    kept = [line for index, line in enumerate(lines, start=1) if index not in skip]
    return "\n".join(kept)


def dumps_contract(contract: dict[str, object]) -> str:
    """Pretty-print a prune contract for stdout."""
    return json.dumps(contract, indent=2)
