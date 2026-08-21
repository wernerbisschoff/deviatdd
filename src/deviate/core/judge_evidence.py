"""Mechanical TDD JUDGE evidence gate (path + exact substring)."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Literal

_AC_TOKEN = re.compile(r"AC-PLAN-\d{3}")
_CONTRACT_BLOCK = re.compile(
    r'<authoritative_acceptance_contract\s+source="plan.md">(.*?)'
    r"</authoritative_acceptance_contract>",
    re.DOTALL,
)
_DIFF_CHUNK = re.compile(r"(?=^diff --git )", re.MULTILINE)
_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_PLUS_HEADER = re.compile(r"^\+\+\+ b/(.+)$")
_UNIQUENESS_FLOOR = 12
_EMPTY_GREEN_ACTION = "proceed_to_refactor_no_diff"
_ALREADY_EXISTS_ACTION = "skip_refactor"

# Runner-authored feedback — same abort family as JUDGE_AGENT_NO_FEEDBACK.
_MISSING_TOKENS = (
    "JUDGE evidence is missing, empty, or partial for injected "
    "acceptance tokens: {tokens}"
)
_EMPTY_QUOTE = "JUDGE evidence {kind}_quote is empty"
_UNKNOWN_PATH = (
    "JUDGE evidence {kind}_path is not in the injected diff or HEAD: {label}"
)
_QUOTE_NOT_IN_SOURCE = "JUDGE evidence {kind}_quote is not an exact substring of {path}"
_QUOTE_TOO_GENERIC = (
    "JUDGE evidence {kind}_quote is below the uniqueness floor for {path}"
)

_SourceKind = Literal["diff", "head"]


def evaluate_judge_evidence(
    *,
    plan_contract: str,
    injected_diff: str,
    evidence: Sequence[Any],
    next_action: str | None = None,
    head_contents: Mapping[str, str] | None = None,
) -> str | None:
    """Return runner-authored feedback when citations fail; None on pass.

    Tokens come only from ``<authoritative_acceptance_contract source="plan.md">``.
    """
    tokens = _extract_ac_plan_tokens(plan_contract)
    if not tokens:
        return None

    missing = _uncovered_tokens(tokens, evidence)
    if missing:
        return _MISSING_TOKENS.format(tokens=", ".join(missing))

    hunks = _map_diff_hunks(injected_diff)
    head = dict(head_contents or {})
    use_head = next_action == _ALREADY_EXISTS_ACTION
    impl_required = next_action != _EMPTY_GREEN_ACTION

    for item in evidence:
        if _field(item, "ac") not in tokens:
            continue
        failure = _check_citation(
            item,
            hunks=hunks,
            head=head,
            use_head=use_head,
            impl_required=impl_required,
        )
        if failure is not None:
            return failure
    return None


def _extract_ac_plan_tokens(plan_contract: str) -> list[str]:
    match = _CONTRACT_BLOCK.search(plan_contract)
    if match is None:
        return []
    return list(dict.fromkeys(_AC_TOKEN.findall(match.group(1))))


def _uncovered_tokens(tokens: Sequence[str], evidence: Sequence[Any]) -> list[str]:
    cited = {_field(item, "ac") for item in evidence}
    return [token for token in tokens if token not in cited]


def _map_diff_hunks(injected_diff: str) -> dict[str, str]:
    hunks: dict[str, str] = {}
    for chunk in _iter_diff_chunks(injected_diff):
        for path in _chunk_paths(chunk):
            hunks[path] = chunk
    return hunks


def _iter_diff_chunks(injected_diff: str) -> Iterator[str]:
    if not injected_diff:
        return
    yield from (chunk for chunk in _DIFF_CHUNK.split(injected_diff) if chunk.strip())


def _chunk_paths(chunk: str) -> list[str]:
    lines = chunk.splitlines()
    if not lines:
        return []
    header = _DIFF_HEADER.match(lines[0])
    if header is None:
        return []
    paths = [header.group(1), header.group(2)]
    for line in lines:
        plus = _PLUS_HEADER.match(line)
        if plus is not None:
            paths.append(plus.group(1))
    return paths


def _check_citation(
    item: Any,
    *,
    hunks: Mapping[str, str],
    head: Mapping[str, str],
    use_head: bool,
    impl_required: bool,
) -> str | None:
    test_failure = _check_quote(
        path=_field(item, "test_path"),
        quote=_field(item, "test_quote"),
        kind="test",
        hunks=hunks,
        head=head,
        use_head=use_head,
    )
    if test_failure is not None or not impl_required:
        return test_failure
    return _check_quote(
        path=_field(item, "impl_path"),
        quote=_field(item, "impl_quote"),
        kind="impl",
        hunks=hunks,
        head=head,
        use_head=use_head,
    )


def _check_quote(
    *,
    path: str,
    quote: str,
    kind: str,
    hunks: Mapping[str, str],
    head: Mapping[str, str],
    use_head: bool,
) -> str | None:
    if not quote.strip():
        return _EMPTY_QUOTE.format(kind=kind)
    source, source_kind = _resolve_source(
        path, hunks=hunks, head=head, use_head=use_head
    )
    if source is None:
        label = path or f"(empty {kind}_path)"
        return _UNKNOWN_PATH.format(kind=kind, label=label)
    if quote not in source:
        return _QUOTE_NOT_IN_SOURCE.format(kind=kind, path=path)
    if not _meets_uniqueness_floor(quote, source, added_only=source_kind == "diff"):
        return _QUOTE_TOO_GENERIC.format(kind=kind, path=path)
    return None


def _resolve_source(
    path: str,
    *,
    hunks: Mapping[str, str],
    head: Mapping[str, str],
    use_head: bool,
) -> tuple[str | None, _SourceKind | None]:
    if not path:
        return None, None
    if use_head:
        if path in head:
            return head[path], "head"
        return None, None
    if path in hunks:
        return hunks[path], "diff"
    return None, None


def _meets_uniqueness_floor(quote: str, source: str, *, added_only: bool) -> bool:
    if _non_ws_len(quote) >= _UNIQUENESS_FLOOR:
        return True
    candidates = (
        _added_line_bodies(source) if added_only else _stripped_source_lines(source)
    )
    return quote in candidates


def _added_line_bodies(source: str) -> list[str]:
    bodies: list[str] = []
    for line in source.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            bodies.append(line[1:].strip())
    return bodies


def _stripped_source_lines(source: str) -> list[str]:
    return [line.strip() for line in source.splitlines() if line.strip()]


def _non_ws_len(value: str) -> int:
    return sum(1 for char in value if not char.isspace())


def _field(item: Any, name: str) -> str:
    if isinstance(item, Mapping):
        value = item.get(name, "")
    else:
        value = getattr(item, name, "")
    if value is None:
        return ""
    return str(value)
