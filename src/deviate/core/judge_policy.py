"""Pure policy helpers for JUDGE feedback and route selection."""

from __future__ import annotations

import re
from collections.abc import Callable

from deviate.core.agent import HandoverManifest
from deviate.state.config import JUDGE_REVERT_ACTION_ALIASES

JUDGE_ACTIONS = frozenset(
    {
        "revert_red",
        "revert_green",
        "continue_refactor",
        "skip_refactor",
        "proceed_to_refactor_no_diff",
    }
)
REVERT_JUDGE_ACTIONS = frozenset({"revert_red", "revert_green"})

_REFACTOR_NOTE_RE = re.compile(r"(REFACTOR NOTE:.*)", re.DOTALL | re.IGNORECASE)
_REFACTOR_ONLY_BODY_RE = re.compile(
    r"(?is)^\s*(?:COMPLIANCE_PASS\b[^\n]*\s*)*REFACTOR NOTE:"
)
_RETRY_INSTRUCTION_RE = re.compile(
    r"the next (?:green|red) attempt must\s*:",
    re.IGNORECASE,
)
_BLOCKING_VIOLATION_RE = re.compile(
    r"spec non-compliance|no-shortcut|test integrity|security|"
    r"gate bypass|governance|scope violation|constitution",
    re.IGNORECASE,
)
_FILE_LINE_CITATION_RE = re.compile(
    r"((?:[\w.-]+/)*[\w.-]+\.[A-Za-z][A-Za-z0-9]{0,7}):\d+(?::\d+)?\b"
)
_BARE_AND_LINE_RE = re.compile(r"\s+and\s+:\d+\b")


def coerce_feedback_text(value: object) -> str:
    """Return a readable feedback string for a scalar or collection."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [coerce_feedback_text(v) for v in value.values() if v is not None]
        return "\n".join(p for p in parts if p) if parts else str(value)
    if isinstance(value, (list, tuple)):
        return "\n".join(coerce_feedback_text(v) for v in value)
    return str(value)


def format_violations_as_feedback(violations: list[object] | None) -> str:
    """Render supported structured violation schemas as feedback text."""
    if not violations:
        return ""
    lines: list[str] = []
    for i, violation in enumerate(violations, start=1):
        if not isinstance(violation, dict):
            body = coerce_feedback_text(violation)
            if body:
                lines.append(f"- violation {i}: {body}".rstrip())
            continue
        category = violation.get("category", "")
        file = violation.get("file", "")
        detail = violation.get("detail", "")
        severity = violation.get("severity", "")
        requirement = violation.get("requirement", "")
        recommendation = violation.get("recommendation", "")
        parts: list[str] = []
        if category:
            parts.append(f"[{category}]")
        if severity:
            parts.append(f"({severity})")
        if file:
            parts.append(f"file: {file}")
        if requirement:
            parts.append(f"req: {requirement}")
        head = " ".join(parts) if parts else f"violation {i}"
        body = detail or ""
        if recommendation:
            body = (body + " " if body else "") + f"Recommendation: {recommendation}"
        lines.append(f"- {head}: {body}".rstrip())
    return "\n".join(lines)


def _manifest_extra(manifest: HandoverManifest) -> dict[str, object]:
    extra = getattr(manifest, "model_extra", None)
    return extra if isinstance(extra, dict) else {}


def _manifest_field(manifest: HandoverManifest, name: str) -> object:
    extra = _manifest_extra(manifest)
    if name in extra:
        return extra[name]
    return getattr(manifest, name, None)


def _category_is_test_integrity(category: object) -> bool:
    return "test integrity" in str(category or "").strip().lower()


def _evaluation_test_integrity_fail(evaluation: object) -> bool:
    if evaluation is None:
        return False
    if isinstance(evaluation, dict):
        value = evaluation.get("test_integrity")
    else:
        value = getattr(evaluation, "test_integrity", None)
    return str(value or "").strip().upper() == "FAIL"


def manifest_signals_test_integrity(manifest: HandoverManifest) -> bool:
    """Return true when the manifest declares failed test integrity."""
    if _evaluation_test_integrity_fail(_manifest_field(manifest, "evaluation")):
        return True
    if str(_manifest_field(manifest, "test_integrity") or "").strip().upper() == "FAIL":
        return True
    violations = _manifest_field(manifest, "violations")
    if not isinstance(violations, list):
        return False
    for item in violations:
        category = (
            item.get("category")
            if isinstance(item, dict)
            else getattr(item, "category", None)
        )
        if _category_is_test_integrity(category):
            return True
    return False


def verdict_is_fail(verdict: str) -> bool:
    """Return true for compliance violation or failure tokens."""
    token = str(verdict or "").strip().upper()
    return "COMPLIANCE_VIOLATION" in token or "COMPLIANCE_FAIL" in token


def _manifest_train_feedback(manifest: HandoverManifest) -> str:
    return coerce_feedback_text(
        getattr(manifest, "train_feedback", None)
        or (_manifest_extra(manifest).get("train_feedback", "") if manifest else "")
    )


def feedback_is_refactor_only(feedback: str) -> bool:
    """Return true when feedback contains only a refactor note."""
    text = coerce_feedback_text(feedback).strip()
    if not text:
        return False
    upper = text.upper()
    if upper.startswith("COMPLIANCE_VIOLATION") or upper.startswith("COMPLIANCE_FAIL"):
        return False
    if _RETRY_INSTRUCTION_RE.search(text):
        return False
    return bool(_REFACTOR_ONLY_BODY_RE.match(text))


def violation_categories(manifest: HandoverManifest) -> list[str]:
    """Return category strings from the manifest violations."""
    violations = _manifest_field(manifest, "violations")
    if not isinstance(violations, list):
        return []
    categories: list[str] = []
    for item in violations:
        if isinstance(item, str) and item.strip():
            categories.append(item)
            continue
        category = (
            item.get("category")
            if isinstance(item, dict)
            else getattr(item, "category", None)
        )
        if category:
            categories.append(str(category))
    return categories


def _manifest_has_blocking_violations(manifest: HandoverManifest) -> bool:
    return any(
        _BLOCKING_VIOLATION_RE.search(category)
        for category in violation_categories(manifest)
    )


def verdict_is_clean_pass(verdict: str, manifest: HandoverManifest) -> bool:
    """Return true when the payload is a pass without a blocking failure."""
    if manifest_signals_test_integrity(manifest):
        return False
    if _manifest_has_blocking_violations(manifest):
        return False
    feedback = _manifest_train_feedback(manifest)
    if feedback_is_refactor_only(feedback):
        return True
    if verdict_is_fail(verdict):
        return False
    token = str(verdict or "").strip().upper()
    if "COMPLIANCE_PASS" in token:
        return True
    if token:
        return False
    return feedback.strip().upper().startswith("COMPLIANCE_PASS")


def extract_refactor_note(feedback: str) -> str:
    """Return the refactor-note portion of pass feedback."""
    text = coerce_feedback_text(feedback).strip()
    if not text:
        return ""
    upper = text.upper()
    match = _REFACTOR_NOTE_RE.search(text)
    if "COMPLIANCE_VIOLATION" in upper or "COMPLIANCE_FAIL" in upper:
        return match.group(1).strip() if match else ""
    if match:
        return match.group(1).strip()
    if upper.startswith("COMPLIANCE_PASS"):
        return ""
    return text


def coerce_judge_action(
    manifest: HandoverManifest,
    verdict: str,
    *,
    failure_kind: str = "",
    log: Callable[[str], None] | None = None,
) -> str | None:
    """Normalize the declared JUDGE action and apply fallback policy."""
    if failure_kind in {"test_defect", "no_failing_test"} and verdict_is_fail(verdict):
        return "revert_red"
    if (
        verdict_is_fail(verdict)
        and failure_kind not in {"mechanical", "test_defect", "no_failing_test"}
        and manifest_signals_test_integrity(manifest)
    ):
        return "revert_red"
    next_action = getattr(manifest, "next_action", None)
    if next_action is not None:
        next_action = JUDGE_REVERT_ACTION_ALIASES.get(next_action, next_action)
    if verdict_is_clean_pass(verdict, manifest):
        if next_action in JUDGE_ACTIONS and next_action not in REVERT_JUDGE_ACTIONS:
            return next_action
        if (
            next_action is not None
            and next_action != ""
            and next_action not in JUDGE_ACTIONS
        ):
            if log:
                log(
                    f"JUDGE_UNKNOWN_ACTION ignored: {next_action!r}; "
                    f"defaulting verdict={verdict!r}"
                )
        return None
    if next_action in JUDGE_ACTIONS:
        return next_action
    if next_action is not None and next_action != "":
        if log:
            log(
                f"JUDGE_UNKNOWN_ACTION ignored: {next_action!r}; "
                f"defaulting verdict={verdict!r}"
            )
    if verdict_is_fail(verdict):
        return "revert_green"
    return None


def strip_revert_line_citations(feedback: str) -> str:
    """Remove discarded-commit line numbers from revert feedback."""
    if not feedback:
        return feedback
    stripped = _FILE_LINE_CITATION_RE.sub(r"\1", feedback)
    return _BARE_AND_LINE_RE.sub("", stripped)


def judge_feedback_from_manifest(manifest: HandoverManifest) -> tuple[str, str]:
    """Resolve feedback text and its source from a judge manifest."""
    extra = _manifest_extra(manifest)
    train_feedback = coerce_feedback_text(
        getattr(manifest, "train_feedback", None) or extra.get("train_feedback", "")
    )
    rationale = coerce_feedback_text(
        getattr(manifest, "rationale", None) or extra.get("rationale", "")
    )
    summary = coerce_feedback_text(
        getattr(manifest, "summary", None) or extra.get("summary", "")
    )
    violations = format_violations_as_feedback(
        getattr(manifest, "violations", None) or extra.get("violations", []) or []
    )
    for text, source in (
        (train_feedback, "train_feedback"),
        (violations, "violations"),
        (rationale, "rationale"),
        (summary, "summary"),
    ):
        if text:
            return strip_revert_line_citations(text), source
    return "", ""


def blast_for_action(action: str | None) -> str:
    """Map a routed JUDGE action to its rollback scope."""
    if action == "revert_red":
        return "red"
    if action == "revert_green":
        return "green"
    return "none"


def declared_next_action_raw(manifest: HandoverManifest) -> str:
    """Return the agent-declared action before normalization."""
    raw = getattr(manifest, "next_action", None)
    if raw is None:
        raw = _manifest_extra(manifest).get("next_action")
    if raw is None or raw == "":
        return ""
    return str(raw)


def evaluation_test_integrity_value(manifest: HandoverManifest) -> object:
    """Return evaluation.test_integrity when present."""
    evaluation = _manifest_field(manifest, "evaluation")
    if evaluation is None:
        return None
    if isinstance(evaluation, dict):
        return evaluation.get("test_integrity")
    return getattr(evaluation, "test_integrity", None)
