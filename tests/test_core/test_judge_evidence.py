"""TSK-028-01: task-scoped JUDGE tokens via first-hit resolver.

Constitution §3 Testing Protocols: pytest under tests/; no agent; no git.
AC-PLAN-001 / AC-PLAN-002: required tokens come from the task resolver,
not the full plan contract. ISS-ADH-020 quote pins stay fail-closed on
this-task tokens.

GREEN scope is only ``src/deviate/core/judge_evidence.py``:
add optional ``required_tokens`` (default ``None``) and
``resolve_task_ac_tokens(task, *, card_text="")``.
Do not edit ``micro.py``, ``review.py``, or prompt templates.
When ``required_tokens`` is a list (including empty), use that list.
Do not read the plan contract for the required set.
"""

from __future__ import annotations

import inspect
import re
from typing import Any

from deviate.core.agent import EvidenceItem
from deviate.core.judge_evidence import evaluate_judge_evidence
from deviate.state.ledger import CriterionLink, TaskRecord

try:
    from deviate.core.judge_evidence import resolve_task_ac_tokens
except ImportError:  # RED: symbol lands in GREEN

    def resolve_task_ac_tokens(*_args: Any, **_kwargs: Any) -> list[str]:
        raise AssertionError("resolve_task_ac_tokens is not implemented")


# Spec example quotes (ISS-ADH-020 / AC-PLAN-003).
_TEST_QUOTE = "assert increment(2) == 3"
_IMPL_QUOTE = "return n + 1"

_MATCHING_DIFF = """\
diff --git a/tests/example.py b/tests/example.py
index 1111111..2222222 100644
--- a/tests/example.py
+++ b/tests/example.py
@@ -0,0 +1,3 @@
+def test_increment() -> None:
+    assert increment(2) == 3
+
diff --git a/src/example.py b/src/example.py
index 1111111..2222222 100644
--- a/src/example.py
+++ b/src/example.py
@@ -0,0 +1,2 @@
+def increment(n: int) -> int:
+    return n + 1
"""

_DIRTY_TEST_DIFF = """\
diff --git a/tests/example.py b/tests/example.py
index 1111111..2222222 100644
--- a/tests/example.py
+++ b/tests/example.py
@@ -0,0 +1,3 @@
+def test_increment() -> None:
+    assert increment(2) == 3
+
"""

_SHORT_LINE_DIFF = """\
diff --git a/tests/example.py b/tests/example.py
index 1111111..2222222 100644
--- a/tests/example.py
+++ b/tests/example.py
@@ -0,0 +1,2 @@
+def test_flag() -> None:
+    x = 1
diff --git a/src/example.py b/src/example.py
index 1111111..2222222 100644
--- a/src/example.py
+++ b/src/example.py
@@ -0,0 +1,1 @@
+x = 1
"""

_GENERIC_ASSERT_DIFF = """\
diff --git a/tests/example.py b/tests/example.py
index 1111111..2222222 100644
--- a/tests/example.py
+++ b/tests/example.py
@@ -0,0 +1,2 @@
+def test_placeholder() -> None:
+    assert True  # increment contract placeholder
diff --git a/src/example.py b/src/example.py
index 1111111..2222222 100644
--- a/src/example.py
+++ b/src/example.py
@@ -0,0 +1,2 @@
+def increment(n: int) -> int:
+    return n + 1
"""


def _plan_contract(*acs: str, extra_outside: str = "") -> str:
    body = "\n".join(f"**Scenario {ac}: example**" for ac in acs)
    return (
        f"{extra_outside}\n"
        '<authoritative_acceptance_contract source="plan.md">\n'
        f"{body}\n"
        "</authoritative_acceptance_contract>\n"
    )


def _item(**overrides: str) -> EvidenceItem:
    fields = {
        "ac": "AC-PLAN-001",
        "test_path": "tests/example.py",
        "test_quote": _TEST_QUOTE,
        "impl_path": "src/example.py",
        "impl_quote": _IMPL_QUOTE,
    }
    fields.update(overrides)
    return EvidenceItem(**fields)


_PLAN_BLOCK = re.compile(
    r'<authoritative_acceptance_contract\s+source="plan.md">(.*?)'
    r"</authoritative_acceptance_contract>",
    re.DOTALL,
)
_AC_TOKEN = re.compile(r"AC-PLAN-\d{3}")


def _tokens_in_plan(plan_contract: str) -> list[str]:
    match = _PLAN_BLOCK.search(plan_contract)
    if match is None:
        return []
    return list(dict.fromkeys(_AC_TOKEN.findall(match.group(1))))


def _evaluate(**kwargs: Any) -> str | None:
    """Call the gate. Drop ``required_tokens`` only while the kwarg is absent."""
    try:
        return evaluate_judge_evidence(**kwargs)
    except TypeError as exc:
        if "required_tokens" not in str(exc):
            raise
        kwargs.pop("required_tokens", None)
        return evaluate_judge_evidence(**kwargs)


def _feedback(
    *,
    evidence: list[EvidenceItem],
    plan_contract: str | None = None,
    injected_diff: str = _MATCHING_DIFF,
    next_action: str | None = "continue_refactor",
    head_contents: dict[str, str] | None = None,
    required_tokens: list[str] | None = None,
) -> str | None:
    plan = plan_contract or _plan_contract("AC-PLAN-001")
    kwargs: dict[str, Any] = {}
    accepts_tokens = (
        "required_tokens" in inspect.signature(evaluate_judge_evidence).parameters
    )
    if required_tokens is not None:
        kwargs["required_tokens"] = required_tokens
    elif accepts_tokens:
        kwargs["required_tokens"] = _tokens_in_plan(plan)
    return _evaluate(
        plan_contract=plan,
        injected_diff=injected_diff,
        evidence=evidence,
        next_action=next_action,
        head_contents=head_contents,
        **kwargs,
    )


class TestRejectUnmatchedCitations:
    """AC-PLAN-002: missing, partial, hallucinated, empty, short, or wrong-hunk."""

    def test_empty_evidence_fails_when_ac_plan_tokens_exist(self):
        result = _feedback(evidence=[])
        assert result is not None
        assert "AC-PLAN-001" in result

    def test_partial_coverage_passes_when_omitted_token_is_not_required(self):
        """AC-PLAN-001: later-shard AC-PLAN-002 is legal at JUDGE."""
        result = _feedback(
            evidence=[_item(ac="AC-PLAN-001")],
            plan_contract=_plan_contract("AC-PLAN-001", "AC-PLAN-002"),
            required_tokens=["AC-PLAN-001"],
        )
        assert result is None

    def test_missing_this_task_token_still_fails(self):
        """ISS-ADH-020 / AC-PLAN-001: omitted required token stays fail-closed."""
        result = _feedback(
            evidence=[],
            plan_contract=_plan_contract("AC-PLAN-001", "AC-PLAN-002"),
            required_tokens=["AC-PLAN-001"],
        )
        assert result is not None
        assert "AC-PLAN-001" in result
        assert "AC-PLAN-002" not in result

    def test_hallucinated_test_path_fails(self):
        result = _feedback(
            evidence=[_item(test_path="tests/hallucinated.py")],
        )
        assert result is not None
        assert "tests/hallucinated.py" in result

    def test_hallucinated_impl_path_fails(self):
        result = _feedback(
            evidence=[_item(impl_path="src/hallucinated.py")],
        )
        assert result is not None
        assert "src/hallucinated.py" in result

    def test_empty_test_quote_fails(self):
        result = _feedback(evidence=[_item(test_quote="")])
        assert result is not None
        assert result.strip() != ""

    def test_empty_impl_quote_fails_when_impl_required(self):
        result = _feedback(evidence=[_item(impl_quote="")])
        assert result is not None
        assert result.strip() != ""

    def test_quote_below_uniqueness_floor_fails(self):
        """Generic ``assert True`` is too short and is not the full added line."""
        result = _feedback(
            evidence=[_item(test_quote="assert True")],
            injected_diff=_GENERIC_ASSERT_DIFF,
        )
        assert result is not None
        assert result.strip() != ""

    def test_quote_not_substring_of_named_hunk_fails(self):
        result = _feedback(
            evidence=[_item(test_quote="assert increment(99) == 100")],
        )
        assert result is not None
        assert result.strip() != ""

    def test_quote_from_different_file_hunk_fails(self):
        result = _feedback(
            evidence=[_item(test_quote=_IMPL_QUOTE)],
        )
        assert result is not None
        assert result.strip() != ""


class TestAcceptMatchingQuotes:
    """AC-PLAN-003: every injected AC-PLAN-NNN has matching test and impl quotes."""

    def test_matching_quotes_covering_every_token_pass(self):
        result = _feedback(
            evidence=[
                _item(ac="AC-PLAN-001"),
                _item(ac="AC-PLAN-002"),
            ],
            plan_contract=_plan_contract("AC-PLAN-001", "AC-PLAN-002"),
        )
        assert result is None

    def test_spec_example_impl_quote_passes_as_full_added_line(self):
        """``return n + 1`` is under 12 non-ws chars but is the full added line."""
        result = _feedback(evidence=[_item()])
        assert result is None

    def test_short_full_added_line_passes_uniqueness_floor(self):
        result = _feedback(
            evidence=[
                _item(test_quote="x = 1", impl_quote="x = 1"),
            ],
            injected_diff=_SHORT_LINE_DIFF,
        )
        assert result is None


class TestEmptyGreenTestQuoteOnly:
    """AC-PLAN-004: proceed_to_refactor_no_diff requires test_quote only."""

    def test_dirty_diff_test_quote_without_impl_quote_passes(self):
        result = _feedback(
            evidence=[
                _item(impl_path="", impl_quote=""),
            ],
            injected_diff=_DIRTY_TEST_DIFF,
            next_action="proceed_to_refactor_no_diff",
        )
        assert result is None

    def test_empty_green_without_test_quote_fails(self):
        result = _feedback(
            evidence=[_item(test_quote="", impl_path="", impl_quote="")],
            injected_diff=_DIRTY_TEST_DIFF,
            next_action="proceed_to_refactor_no_diff",
        )
        assert result is not None
        assert result.strip() != ""


class TestAlreadyExistsHeadFallback:
    """AC-PLAN-005: skip_refactor quotes HEAD; missing test file fails closed."""

    def test_matching_head_test_and_impl_quotes_pass(self):
        result = _feedback(
            evidence=[_item()],
            injected_diff="",
            next_action="skip_refactor",
            head_contents={
                "tests/example.py": (
                    "def test_increment() -> None:\n    assert increment(2) == 3\n"
                ),
                "src/example.py": ("def increment(n: int) -> int:\n    return n + 1\n"),
            },
        )
        assert result is None

    def test_named_test_file_absent_from_head_fails(self):
        result = _feedback(
            evidence=[_item()],
            injected_diff="",
            next_action="skip_refactor",
            head_contents={
                "src/example.py": "def increment(n: int) -> int:\n    return n + 1\n",
            },
        )
        assert result is not None
        assert "tests/example.py" in result


class TestNoAcPlanEmptyEvidence:
    """AC-PLAN-006: empty evidence is legal when the plan block has no tokens."""

    def test_empty_evidence_passes_when_contract_has_no_ac_plan_tokens(self):
        result = _feedback(
            evidence=[],
            plan_contract=_plan_contract(),
        )
        assert result is None

    def test_ac_plan_text_outside_contract_block_is_not_required(self):
        outside = (
            "<macro_issue_intent>\n"
            "**Scenario AC-PLAN-099: prompt template only**\n"
            "</macro_issue_intent>\n"
            "judge.md mentions AC-PLAN-001 must be cited\n"
        )
        result = _feedback(
            evidence=[],
            plan_contract=_plan_contract(extra_outside=outside),
        )
        assert result is None


class TestAlreadySatisfiedDeclaredPathMembership:
    """AC-PLAN-005: membership even when the contract has no AC-PLAN-* tokens."""

    def test_already_satisfied_declared_path_missing_without_ac_tokens(self):
        result = evaluate_judge_evidence(
            plan_contract=_plan_contract(),
            injected_diff="",
            evidence=[],
            next_action="skip_refactor",
            head_contents={},
            declared_paths=["tests/ghost_regression.py"],
        )
        assert result is not None
        assert result.strip() != ""
        assert "tests/ghost_regression.py" in result

    def test_already_exists_evidence_test_path_missing_without_ac_tokens(self):
        result = _feedback(
            evidence=[_item(test_path="tests/ghost_regression.py")],
            plan_contract=_plan_contract(),
            injected_diff="",
            next_action="skip_refactor",
            head_contents={},
        )
        assert result is not None
        assert result.strip() != ""
        assert "tests/ghost_regression.py" in result

    def test_empty_required_tokens_still_checks_declared_paths(self):
        """AC-PLAN-002: empty required set still runs declared_paths checks."""
        result = _evaluate(
            plan_contract=_plan_contract("AC-PLAN-001", "AC-PLAN-002"),
            injected_diff="",
            evidence=[],
            next_action="skip_refactor",
            head_contents={},
            declared_paths=["tests/ghost_regression.py"],
            required_tokens=[],
        )
        assert result is not None
        assert "tests/ghost_regression.py" in result

    def test_empty_required_tokens_does_not_fall_back_to_plan(self):
        """AC-PLAN-001: never require every token in plan.md."""
        result = _evaluate(
            plan_contract=_plan_contract("AC-PLAN-001", "AC-PLAN-002"),
            injected_diff=_MATCHING_DIFF,
            evidence=[],
            required_tokens=[],
        )
        assert result is None


def _criteria(
    *ids: str,
) -> list[dict[str, str]]:
    return [
        {
            "criterion_id": token,
            "verification_mode": "automated",
            "test_ref": "tests/example.py",
        }
        for token in ids
    ]


class TestResolveTaskAcTokens:
    """AC-PLAN-002: first-hit order is criteria, then card, then none."""

    def test_resolve_task_ac_tokens_criteria_then_card_then_none(self):
        card_with_extra = (
            "- TSK-028-01: Scope JUDGE tokens\n"
            "  - **Rationale**: names AC-PLAN-001 and AC-PLAN-002.\n"
            "  - **Details**: also names AC-PLAN-005.\n"
        )
        criteria_task: dict[str, Any] = {
            "id": "TSK-028-01",
            "acceptance_criteria": _criteria("AC-PLAN-001"),
        }
        assert resolve_task_ac_tokens(criteria_task, card_text=card_with_extra) == [
            "AC-PLAN-001"
        ]

        empty_criteria_task: dict[str, Any] = {
            "id": "TSK-028-01",
            "acceptance_criteria": [],
        }
        card_named = "Rationale owns AC-PLAN-001. Details also name AC-PLAN-003.\n"
        assert resolve_task_ac_tokens(empty_criteria_task, card_text=card_named) == [
            "AC-PLAN-001",
            "AC-PLAN-003",
        ]

        pending_without_field: dict[str, Any] = {
            "id": "TSK-028-01",
            "status": "PENDING",
        }
        assert resolve_task_ac_tokens(
            pending_without_field, card_text="Card names AC-PLAN-001 only.\n"
        ) == ["AC-PLAN-001"]

        infra_card = "Enabling / infra task with no plan tokens.\n"
        assert resolve_task_ac_tokens({"id": "TSK-028-01"}, card_text=infra_card) == []

    def test_none_acceptance_criteria_uses_card_tokens(self):
        task = {"id": "TSK-028-01", "acceptance_criteria": None}
        assert resolve_task_ac_tokens(
            task, card_text="Acceptance names AC-PLAN-002.\n"
        ) == ["AC-PLAN-002"]

    def test_task_record_criterion_ids_win_over_card(self):
        record = TaskRecord(
            id="TSK-028-01",
            issue_id="ISS-ADH-028",
            description="Scope JUDGE tokens to this task via first-hit resolver",
            acceptance_criteria=[
                CriterionLink(
                    criterion_id="AC-PLAN-001",
                    verification_mode="automated",
                    test_ref="tests/test_core/test_judge_evidence.py",
                )
            ],
        )
        card = "Card also names AC-PLAN-002 and AC-PLAN-007.\n"
        assert resolve_task_ac_tokens(record, card_text=card) == ["AC-PLAN-001"]

    def test_judge_feedback_quote_does_not_add_token(self):
        """GH-89: runner feedback quoting AC-PLAN-001 is not a required token."""
        task = {"id": "TSK-003-02"}
        card = (
            "- TSK-003-02: Booking harness\n"
            "  - **Rationale**: Enable the sandbox without naming a plan token.\n"
            "  - **Judge Feedback**: JUDGE evidence is missing... AC-PLAN-001\n"
            "for injected acceptance tokens: AC-PLAN-001\n"
            "  - **Files**: tests/test_booking.py\n"
        )
        assert resolve_task_ac_tokens(task, card_text=card) == []

    def test_rationale_forward_ref_is_not_a_required_token(self):
        """GH-191: TSK-002-01 Rationale naming AC-PLAN-002 is not this-task scope."""
        task = {"id": "TSK-002-01", "acceptance_criteria": []}
        card = (
            "- TSK-002-01: Root layout chrome\n"
            "  - **Type**: Feature_Batch\n"
            "  - **Acceptance Criteria**: AC-PLAN-001, AC-PLAN-003\n"
            "  - **Rationale**: the shell must exist before AC-PLAN-002 "
            "binds the layout option\n"
            "  - **Details**: implement the chrome; AC-PLAN-002 is next.\n"
            "  - **Files**: lib/meepleinn_web/layouts/root.html.heex\n"
        )
        assert resolve_task_ac_tokens(task, card_text=card) == [
            "AC-PLAN-001",
            "AC-PLAN-003",
        ]

    def test_rationale_only_card_yields_no_tokens(self):
        """A card that only names later-task ACs in Rationale requires none."""
        task = {"id": "TSK-002-01"}
        card = (
            "- TSK-002-01: Root layout chrome\n"
            "  - **Rationale**: must exist before AC-PLAN-002 binds "
            "the layout option\n"
            "  - **Details**: AC-PLAN-002 is owned by the next task.\n"
        )
        assert resolve_task_ac_tokens(task, card_text=card) == []

    def test_structured_card_without_criteria_skips_rationale(self):
        """Empty criterion_ids + labeled card: scrape AC section, not Rationale."""
        task = {"id": "TSK-028-01", "acceptance_criteria": []}
        card = (
            "- TSK-028-01: Scope JUDGE tokens\n"
            "  - **Rationale**: names AC-PLAN-001 and AC-PLAN-002.\n"
            "  - **Details**: also names AC-PLAN-005.\n"
        )
        assert resolve_task_ac_tokens(task, card_text=card) == []
