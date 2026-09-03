"""Mechanical TDD JUDGE evidence gate (path + exact substring)."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Literal

_AC_TOKEN = re.compile(r"AC-PLAN-\d{3}")
_LABELED_SECTION = re.compile(r"^\s*-\s+\*\*([^*]+)\*\*:")
_CARD_STRUCTURE_LINE = re.compile(
    r"^(?:- (?:\[(?:x| )\]\s+)?TSK-\d{3}-\d{2}:|  - |#{1,6}\s)"
)
_AC_SECTION_NAMES = frozenset({"acceptance criteria"})
_NON_AC_SECTION_NAMES = frozenset(
    {
        "rationale",
        "type",
        "mode",
        "files",
        "details",
        "test strategy",
        "verification",
        "estimated time",
        "dependency",
        "judge feedback",
        "goal",
        "flow references",
    }
)
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


def resolve_task_ac_tokens(task: Any, *, card_text: str = "") -> list[str]:
    """Return this task's required ``AC-PLAN-NNN`` tokens (first hit wins).

    Order: non-empty ``acceptance_criteria`` ``criterion_id``s, else tokens
    named in this task's ``tasks.md`` card, else no AC tokens. Card fallback
    prefers ``**Acceptance Criteria**`` lines; otherwise it scans remaining
    text after dropping ``**Rationale**``, ``**Judge Feedback**``, and
    similar non-AC sections. Never reads ``plan.md``.
    """
    ids = _criterion_ids(_attr(task, "acceptance_criteria") or [])
    if ids:
        return ids
    return _unique_ac_tokens(_card_ac_scope(card_text or ""))


def evaluate_judge_evidence(
    *,
    plan_contract: str,
    injected_diff: str,
    evidence: Sequence[Any],
    next_action: str | None = None,
    head_contents: Mapping[str, str] | None = None,
    declared_paths: Sequence[str] | None = None,
    required_tokens: Sequence[str] | None = None,
    use_head: bool | None = None,
) -> str | None:
    """Return runner-authored feedback when citations fail; None on pass.

    When ``required_tokens`` is a list (including empty), that list is the
    required set. Do not read the plan contract for the required set.
    ``required_tokens is None`` keeps the legacy plan-block extract for
    callers that have not yet passed an explicit list.
    Declared regression paths are checked even when the token set is empty.
    ``use_head`` overrides the already-exists HEAD source: ``None`` keeps
    ``next_action == skip_refactor`` as the only HEAD path (JUDGE gate).
    COMPLETED no longer rematches quotes against HEAD after a clean pass
    (GH-191); token coverage + ``test_path`` existence live in
    ``_require_tdd_completed_evidence``.
    """
    hunks = _map_diff_hunks(injected_diff)
    head = dict(head_contents or {})
    missing_path = _missing_declared_path(
        declared_paths=declared_paths,
        evidence=evidence,
        hunks=hunks,
        head=head,
    )
    if missing_path is not None:
        return missing_path

    tokens = _required_token_set(required_tokens, plan_contract)
    if not tokens:
        return None

    missing = _uncovered_tokens(tokens, evidence)
    if missing:
        return _MISSING_TOKENS.format(tokens=", ".join(missing))

    head_mode = (
        use_head if use_head is not None else next_action == _ALREADY_EXISTS_ACTION
    )
    impl_required = next_action != _EMPTY_GREEN_ACTION

    for item in evidence:
        if _field(item, "ac") not in tokens:
            continue
        failure = _check_citation(
            item,
            hunks=hunks,
            head=head,
            use_head=head_mode,
            impl_required=impl_required,
        )
        if failure is not None:
            return failure
    return None


def _normalized_paths(values: Sequence[Any] | None) -> list[str]:
    """Return stripped, de-duplicated path strings from *values*."""
    paths: list[str] = []
    for raw in values or []:
        text = str(raw).strip() if raw is not None else ""
        if text:
            paths.append(text)
    return list(dict.fromkeys(paths))


def _missing_declared_path(
    *,
    declared_paths: Sequence[str] | None,
    evidence: Sequence[Any],
    hunks: Mapping[str, str],
    head: Mapping[str, str],
) -> str | None:
    """Fail closed when a declared test path is absent from diff and HEAD."""
    evidence_tests = [_field(item, "test_path") for item in evidence]
    snapshot = set(hunks) | set(head)
    for path in _normalized_paths([*(declared_paths or []), *evidence_tests]):
        if path not in snapshot:
            return _UNKNOWN_PATH.format(kind="test", label=path)
    return None


def _required_token_set(
    required_tokens: Sequence[str] | None, plan_contract: str
) -> list[str]:
    """Use the explicit list when provided; else extract from the plan block."""
    if required_tokens is not None:
        return list(dict.fromkeys(required_tokens))
    return _extract_ac_plan_tokens(plan_contract)


def _extract_ac_plan_tokens(plan_contract: str) -> list[str]:
    match = _CONTRACT_BLOCK.search(plan_contract)
    if match is None:
        return []
    return _unique_ac_tokens(match.group(1))


def _unique_ac_tokens(text: str) -> list[str]:
    """Return first-seen ``AC-PLAN-NNN`` tokens from *text* via ``_AC_TOKEN``."""
    return list(dict.fromkeys(_AC_TOKEN.findall(text)))


def _strip_judge_feedback(text: str) -> str:
    """Drop ``**Judge Feedback**`` bullets and their continuation lines."""
    return _strip_labeled_sections(text, {"judge feedback"})


def _card_ac_scope(text: str) -> str:
    """Return the card slice that may name this-task ``AC-PLAN-NNN`` tokens.

    Prefer ``**Acceptance Criteria**`` blocks when present. Otherwise drop
    Rationale and similar non-AC labeled sections (GH-191) and scan what
    remains — unstructured cards with no section headings still contribute
    tokens. ``**Judge Feedback**`` is never a token source (GH-89).
    """
    ac_blocks = _extract_labeled_sections(text, _AC_SECTION_NAMES)
    if ac_blocks:
        return "\n".join(ac_blocks)
    return _strip_labeled_sections(text, _NON_AC_SECTION_NAMES)


def _section_name(line: str) -> str | None:
    match = _LABELED_SECTION.match(line)
    if match is None:
        return None
    return match.group(1).strip().lower()


def _extract_labeled_sections(text: str, names: frozenset[str] | set[str]) -> list[str]:
    """Return labeled section blocks whose heading is in *names*."""
    blocks: list[str] = []
    current: list[str] = []
    capturing = False
    for line in text.splitlines():
        heading = _section_name(line)
        if heading is not None:
            if current:
                blocks.append("\n".join(current))
                current = []
            capturing = heading in names
            if capturing:
                current.append(line)
            continue
        if capturing and not _CARD_STRUCTURE_LINE.match(line):
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
        capturing = False
    if current:
        blocks.append("\n".join(current))
    return blocks


def _strip_labeled_sections(text: str, names: frozenset[str] | set[str]) -> str:
    """Drop labeled sections in *names* and their continuation lines."""
    kept: list[str] = []
    skipping = False
    for line in text.splitlines():
        heading = _section_name(line)
        if heading is not None and heading in names:
            skipping = True
            continue
        if skipping and not _CARD_STRUCTURE_LINE.match(line):
            continue
        skipping = False
        kept.append(line)
    return "\n".join(kept)


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _criterion_ids(criteria: Sequence[Any]) -> list[str]:
    ids: list[str] = []
    for item in criteria:
        text = _field(item, "criterion_id").strip()
        if text:
            ids.append(text)
    return list(dict.fromkeys(ids))


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
    value = _attr(item, name, "")
    if value is None:
        return ""
    return str(value)
