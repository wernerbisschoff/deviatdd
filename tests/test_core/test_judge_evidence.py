"""TSK-020-02: path, quote, and AC coverage in the JUDGE evidence helper.

Constitution §3 Testing Protocols: pytest under tests/; no agent; no git.
"""

from __future__ import annotations

from deviate.core.agent import EvidenceItem
from deviate.core.judge_evidence import evaluate_judge_evidence

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


def _feedback(
    *,
    evidence: list[EvidenceItem],
    plan_contract: str | None = None,
    injected_diff: str = _MATCHING_DIFF,
    next_action: str | None = "continue_refactor",
    head_contents: dict[str, str] | None = None,
) -> str | None:
    return evaluate_judge_evidence(
        plan_contract=plan_contract or _plan_contract("AC-PLAN-001"),
        injected_diff=injected_diff,
        evidence=evidence,
        next_action=next_action,
        head_contents=head_contents,
    )


class TestRejectUnmatchedCitations:
    """AC-PLAN-002: missing, partial, hallucinated, empty, short, or wrong-hunk."""

    def test_empty_evidence_fails_when_ac_plan_tokens_exist(self):
        result = _feedback(evidence=[])
        assert result is not None
        assert "AC-PLAN-001" in result

    def test_partial_coverage_fails_for_omitted_token(self):
        result = _feedback(
            evidence=[_item()],
            plan_contract=_plan_contract("AC-PLAN-001", "AC-PLAN-002"),
        )
        assert result is not None
        assert "AC-PLAN-002" in result

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
