"""Post-COMPLETED spec+test cleanup for ``/deviate-prune``.

Deterministic keep/drop list: honeycomb tags on tests, drop-safe cycle
markdown under one issue folder, and a hard refusal to touch JSONL ledgers.
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

DROP_CYCLE_FILES = frozenset({"plan.md", "tasks.md", "design.md", "data-model.md"})
DROP_TEST_TAGS = frozenset({"spy", "impl"})
KEEP_TEST_TAGS = frozenset({"behavioral", "ac"})
PROTECTED_BASENAMES = frozenset({"explore.md", "prd.md", "constitution.md"})
LEDGER_REWRITE_RE = re.compile(r"\b(compact|squash|rewrite)\b", re.IGNORECASE)
AC_TOKEN_RE = re.compile(r"\bAC-(?:PLAN-\d{3}|[A-Z]+-\d{3}-\d{2})\b")
TAG_SEGMENT_RE = re.compile(
    r"(?:^|[_-])(spy|impl|behavioral|ac)(?:$|[_-])", re.IGNORECASE
)
ISSUE_ID_RE = re.compile(r"\bISS-(?:ADH-)?\d{3}(?:-\d{3})?\b")

PruneStatus = Literal[
    "READY",
    "IN_FLIGHT",
    "ACS_NOT_ENCODED",
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


def classify_test(name: str, markers: set[str] | None = None) -> TestKind:
    """Keep ``behavioral`` / ``ac``; drop ``spy`` / ``impl``; else keep."""
    tags = {tag.lower() for tag in (markers or set())} | _name_tags(name)
    if tags & KEEP_TEST_TAGS:
        return "keep"
    if tags & DROP_TEST_TAGS:
        return "drop"
    return "keep"


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
    """Inventory one issue and decide whether spec deletes may land."""
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
    deletes = inventory_cycle_markdown(issue_dir)

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
                "spec deletion is a no-op until COMPLETED"
            ),
            issue_dir=issue_dir,
        )

    if unmatched:
        return PrunePlan(
            status="ACS_NOT_ENCODED",
            issue_id=resolved,
            issue_status=record.status,
            spec_deletes=[],
            spec_keeps=keeps,
            test_drop=drop_tests,
            test_keep=keep_tests,
            unmatched_acs=unmatched,
            reason=(
                "ACS_NOT_ENCODED: plan ACs are not yet behavioral / ac tests: "
                + ", ".join(unmatched)
            ),
            issue_dir=issue_dir,
        )

    return PrunePlan(
        status="READY",
        issue_id=resolved,
        issue_status=record.status,
        spec_deletes=deletes,
        spec_keeps=keeps,
        test_drop=drop_tests,
        test_keep=keep_tests,
        unmatched_acs=[],
        issue_dir=issue_dir,
    )


def inventory_cycle_markdown(issue_dir: Path) -> list[Path]:
    """Return drop-safe cycle markdown under one per-issue folder."""
    if not issue_dir.is_dir():
        return []
    found: list[Path] = []
    for name in sorted(DROP_CYCLE_FILES):
        path = issue_dir / name
        if path.is_file():
            found.append(path)
    return found


def discover_issue_tests(root: Path, issue_id: str, source_file: str) -> list[TestItem]:
    """Classify tests in files that mention *issue_id* or the issue slug."""
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return []
    slug = PurePosixPath(source_file).stem
    needles = {issue_id, slug}
    items: list[TestItem] = []
    for path in sorted(tests_root.rglob("test_*.py")):
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
    """Apply honeycomb test thinning and, when READY, cycle-markdown deletes.

    Never creates, rewrites, or deletes JSONL ledgers. In-flight and
    unmatched-AC plans skip spec deletes. A ledger-rewrite request is a
    no-op for every mutation.
    """
    if plan.status in {"LEDGER_REWRITE_REJECTED", "NO_ISSUE", "ONE_ISSUE_ONLY"}:
        return
    _thin_tests(root, plan.test_drop)
    if plan.status != "READY":
        return
    for path in plan.spec_deletes:
        if not path.is_file():
            continue
        if is_protected_spec(path, root):
            continue
        path.unlink()
    if plan.issue_dir is not None and plan.issue_dir.is_dir():
        try:
            next(plan.issue_dir.iterdir())
        except StopIteration:
            plan.issue_dir.rmdir()


def is_protected_spec(path: Path, root: Path) -> bool:
    """Return True for ledgers, epic explore/prd, issue md, and Product/flows."""
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
    return False


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
    for name in ("explore.md", "prd.md"):
        candidate = root / "specs" / epic / name
        if candidate.is_file():
            keeps.append(candidate)
    shared_prd = root / "specs" / "adhoc" / "prd.md"
    if shared_prd.is_file() and shared_prd not in keeps:
        keeps.append(shared_prd)
    return keeps


def _unmatched_acs(tokens: list[str], keep_tests: list[TestItem]) -> list[str]:
    corpus = "\n".join(f"{item.name}\n{item.source}" for item in keep_tests)
    return [token for token in tokens if token not in corpus]


def _name_tags(name: str) -> set[str]:
    return {match.group(1).lower() for match in TAG_SEGMENT_RE.finditer(name)}


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
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    file_kind = classify_test(rel.stem)
    items: list[TestItem] = []
    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        markers = _marker_names(node)
        kind = classify_test(node.name, markers)
        if (
            kind == "keep"
            and file_kind == "drop"
            and not (_name_tags(node.name) & KEEP_TEST_TAGS or markers & KEEP_TEST_TAGS)
        ):
            kind = "drop"
        start, end = _node_span(node)
        source = "\n".join(lines[start - 1 : end])
        items.append(TestItem(path=rel, name=node.name, kind=kind, source=source))
    return items


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
        rewritten = _strip_functions(text, drop_names)
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


def dumps_contract(contract: dict[str, object]) -> str:
    """Pretty-print a prune contract for stdout."""
    return json.dumps(contract, indent=2)
