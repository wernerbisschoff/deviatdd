"""Detect mutually incompatible successive JUDGE rejection requirements.

MVP for GH-230: compare JUDGE verdict / repair-contract text across
rounds. A polar flip (strict identity matching vs preserve conflicting
fixtures) or an A-B-A oscillation is a specification decision, not more
implementation training.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Sequence

_REPAIR_FIELD_RE = re.compile(
    r"^(?:[-*]\s+)?(?:\*\*)?(Requirement|Evidence|Correction|Verification|Boundary)"
    r"(?:\*\*)?\s*:\s*(.*)$",
    re.IGNORECASE,
)
_BOILERPLATE_RE = re.compile(
    r"preserve the red tests(?: and public interface)?"
    r"|do not expand the acceptance contract"
    r"|do not edit production code"
    r"|green must not edit tests"
    r"|red must not edit production code"
    r"|change tests only"
    r"|the next (?:green|red) attempt must\s*:"
    r"|compliance_(?:violation|fail|pass)\b",
    re.IGNORECASE,
)
_STRICT_MATCH_RE = re.compile(
    r"\bstrict\b[^\n.]{0,80}\bmatch|\bidentity\s+match|\bmatch[^\n.]{0,40}\bidentit\w*"
    r"|\b(?:must|require[sd]?)\b[^\n.]{0,40}\bmatch[^\n.]{0,40}\b(?:id(?:entity|s)?|identit\w*)\b",
    re.IGNORECASE | re.DOTALL,
)
_PRESERVE_RE = re.compile(
    r"\b(?:preserve|keep|retain|do\s+not\s+(?:change|modify|edit|alter|touch)"
    r"|leave\s+(?:the\s+)?existing)\b",
    re.IGNORECASE,
)
_MISMATCH_RE = re.compile(
    r"\b(?:different|mismatch(?:ed)?|another\s+(?:returned|id)"
    r"|do\s+not\s+match|not\s+(?:the\s+)?same)\b",
    re.IGNORECASE,
)
_TEST_FIXTURE_RE = re.compile(r"\b(?:tests?|fixtures?|existing)\b", re.IGNORECASE)
_EXPLICIT_RE = re.compile(
    r"\b(?:contradict(?:s|ion|ory)?\s+between"
    r"|mutually\s+(?:incompatible|exclusive)"
    r"|incompatible\s+(?:with|fixture|test|requirement)"
    r"|conflicting\s+(?:test|fixture|requirement)"
    r"|cannot\s+(?:both|simultaneously)\s+"
    r"(?:preserve|satisfy|require|match))\b",
    re.IGNORECASE,
)
_CAMEL_RE = re.compile(r"([a-z])([A-Z])")
_TOKEN_RE = re.compile(r"[a-z0-9_]{4,}")
_IDENTITY_STOP = frozenset(
    {
        "valid",
        "invalid",
        "said",
        "did",
        "mid",
        "avoided",
        "decided",
        "rapid",
        "solid",
        "provided",
        "avoid",
    }
)
_STOPWORDS = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "when",
        "must",
        "next",
        "attempt",
        "green",
        "judge",
        "requirement",
        "correction",
        "evidence",
        "boundary",
        "verification",
        "should",
        "using",
        "into",
        "have",
        "been",
        "also",
        "does",
        "then",
        "than",
        "them",
        "they",
        "their",
        "plan",
        "public",
        "interface",
        "acceptance",
        "contract",
        "returned",
        "return",
        "existing",
        "tests",
        "test",
        "fixture",
        "fixtures",
    }
)
_OSCILLATION_SAME = 0.55
_OSCILLATION_DIFF = 0.35


@dataclass(frozen=True, slots=True)
class JudgeContradiction:
    """One detected conflict between successive JUDGE rejection rounds."""

    kind: str
    prior: str
    current: str
    shared_tokens: tuple[str, ...]
    summary: str


def normalize_feedback(text: str) -> str:
    """Collapse whitespace so the same round is recognized across sources."""
    return " ".join((text or "").split()).strip().lower()


def extract_repair_fields(feedback: str) -> dict[str, str]:
    """Return repair-contract fields when the JUDGE payload used them."""
    fields: dict[str, str] = {}
    current = ""
    chunks: list[str] = []
    for raw in (feedback or "").splitlines():
        line = raw.strip()
        match = _REPAIR_FIELD_RE.match(line)
        if match:
            if current:
                fields[current] = " ".join(chunks).strip()
            current = match.group(1).lower()
            chunks = [match.group(2).strip()]
            continue
        if current and line:
            chunks.append(line)
    if current:
        fields[current] = " ".join(chunks).strip()
    return fields


def _strip_boilerplate(text: str) -> str:
    return _BOILERPLATE_RE.sub(" ", text or "")


def requirement_focus(feedback: str) -> str:
    """Requirement + Correction (fallback: full text) without stock phrases."""
    fields = extract_repair_fields(feedback)
    focus = " ".join(
        part for key in ("requirement", "correction") if (part := fields.get(key, ""))
    )
    if not focus.strip():
        focus = feedback or ""
    return _strip_boilerplate(focus)


def _tokens(text: str) -> frozenset[str]:
    split = _CAMEL_RE.sub(r"\1 \2", text or "")
    split = split.replace("_", " ").replace("-", " ")
    return frozenset(
        token
        for token in _TOKEN_RE.findall(split.lower())
        if token not in _STOPWORDS and token not in _IDENTITY_STOP
    )


_ID_TOKEN_RE = re.compile(r"[A-Za-z_]*[Ii][Dd]\b")


def _identity_tokens(text: str) -> frozenset[str]:
    tokens = set()
    for match in _ID_TOKEN_RE.findall(text or ""):
        norm = match.lower().replace("_", "").replace("-", "")
        if norm and norm not in _IDENTITY_STOP:
            tokens.add(norm)
    lowered = (text or "").lower()
    for word in ("identity", "provider"):
        if re.search(r"\b" + word + r"\b", lowered):
            tokens.add(word)
    return frozenset(tokens)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _has_strict_match(text: str) -> bool:
    return bool(_STRICT_MATCH_RE.search(text))


def _has_preserve_mismatch(text: str) -> bool:
    if not _PRESERVE_RE.search(text):
        return False
    if not _TEST_FIXTURE_RE.search(text):
        return False
    return bool(_MISMATCH_RE.search(text))


def _has_preserve_tests(text: str) -> bool:
    return bool(_PRESERVE_RE.search(text) and _TEST_FIXTURE_RE.search(text))


def _has_preserve_identity(text: str) -> bool:
    return bool(_PRESERVE_RE.search(text) and _identity_tokens(text))


def _polar_flip(prior: str, current: str) -> JudgeContradiction | None:
    prior_focus = requirement_focus(prior)
    current_focus = requirement_focus(current)
    prior_strict = _has_strict_match(prior_focus)
    current_strict = _has_strict_match(current_focus)
    prior_preserve = _has_preserve_mismatch(prior_focus) or (
        _has_preserve_tests(prior_focus) and bool(_identity_tokens(prior_focus))
    ) or _has_preserve_identity(prior_focus)
    current_preserve = _has_preserve_mismatch(current_focus) or (
        _has_preserve_tests(current_focus) and bool(_identity_tokens(current_focus))
    ) or _has_preserve_identity(current_focus)
    flipped = (prior_strict and current_preserve) or (current_strict and prior_preserve)
    if not flipped:
        return None
    shared_identity = sorted(
        _identity_tokens(prior_focus) & _identity_tokens(current_focus)
    )
    if not shared_identity:
        return None
    shared = tuple(
        sorted(
            (_tokens(prior_focus) | _identity_tokens(prior_focus))
            & (_tokens(current_focus) | _identity_tokens(current_focus))
        )
    )
    return JudgeContradiction(
        kind="polar_flip",
        prior=prior.strip(),
        current=current.strip(),
        shared_tokens=shared,
        summary=(
            "Successive JUDGE requirements conflict: one requires strict "
            "identity matching and the other requires preserving existing "
            "tests or fixtures that use a different identity."
        ),
    )


def _explicit(prior: str, current: str) -> JudgeContradiction | None:
    if not _EXPLICIT_RE.search(current):
        return None
    shared = _tokens(requirement_focus(prior)) & _tokens(requirement_focus(current))
    shared_identity = _identity_tokens(prior) & _identity_tokens(current)
    if not shared and not shared_identity:
        return None
    return JudgeContradiction(
        kind="explicit",
        prior=prior.strip(),
        current=current.strip(),
        shared_tokens=tuple(sorted(shared | shared_identity)),
        summary=(
            "JUDGE named a mutually incompatible fixture or requirement "
            "conflict. This is a specification decision, not more training."
        ),
    )


def _oscillation(
    prior_rounds: Sequence[str], current: str
) -> JudgeContradiction | None:
    if len(prior_rounds) < 2:
        return None
    older = prior_rounds[-2]
    previous = prior_rounds[-1]
    current_tokens = _tokens(requirement_focus(current))
    older_tokens = _tokens(requirement_focus(older))
    previous_tokens = _tokens(requirement_focus(previous))
    if (
        _jaccard(current_tokens, older_tokens) >= _OSCILLATION_SAME
        and _jaccard(current_tokens, previous_tokens) <= _OSCILLATION_DIFF
    ):
        return JudgeContradiction(
            kind="oscillation",
            prior=previous.strip(),
            current=current.strip(),
            shared_tokens=tuple(sorted(current_tokens & older_tokens)),
            summary=(
                "JUDGE requirements oscillated between two incompatible "
                "interpretations (A → B → A). Stop training and choose one spec."
            ),
        )
    return None


def detect_judge_requirement_contradiction(
    prior_rounds: Sequence[str], current: str
) -> JudgeContradiction | None:
    """Return a contradiction when *current* fights a prior JUDGE requirement.

    Empty history or empty current is not a contradiction. Identical
    restated requirements (same-blast training) are not a contradiction.
    """
    current_text = (current or "").strip()
    if not current_text:
        return None
    history = [round_text for round_text in prior_rounds if (round_text or "").strip()]
    if not history:
        return None
    current_norm = normalize_feedback(current_text)
    distinct = [
        round_text
        for round_text in history
        if normalize_feedback(round_text) != current_norm
    ]
    if not distinct:
        return None
    latest = distinct[-1]
    found = _explicit(latest, current_text) or _polar_flip(latest, current_text)
    if found:
        return found
    return _oscillation(history, current_text)
