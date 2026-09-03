"""GH-185: a clean COMPLIANCE_PASS must not be rewritten to revert_green.

MeepleInn TSK-002-01: verdict COMPLIANCE_PASS, next_action_raw
continue_refactor, violations=[], test_integrity=PASS, feedback is a
REFACTOR NOTE, then the evidence-quote substring gate coerced the
action to revert_green and looped GREEN to TRAIN_EXHAUSTED.

A clean pass keeps the agent's forward route. Unmatched quotes
(indentation / #178) are ignored on pass. REFACTOR NOTE is advice, not
a revert. COMPLIANCE_VIOLATION + revert_green still discards GREEN.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from deviate.cli.micro import _rewrite_unmatched_tdd_pass
from deviate.core.agent import HandoverManifest
from tests.helpers.cycle_driver import load_verdicts
from tests.unit.test_micro.test_judge import (
    _GATE_IMPL_PATH,
    _GATE_IMPL_QUOTE,
    _GATE_ISSUE_ID,
    _GATE_TASK_ID,
    _GATE_TEST_QUOTE,
    _assert_forward,
    _assert_reverted_to_red,
    _gate_evidence,
    _gate_git,
    _gate_manifest,
    _run_tdd_judge,
    _seed_red_green,
)

_GH185_NOTE = (
    "REFACTOR NOTE: consider replacing the plain <a href> nav links with "
    "Phoenix.Component <.link navigate={...}> for LiveView-native navigation; "
    "not blocking."
)


def _indented_quote(quote: str) -> str:
    """Return a quote that fails the exact-substring evidence gate (#178)."""
    return f"    {quote}"


def _gh185_manifest(
    *,
    verdict: str = "COMPLIANCE_PASS",
    next_action: str | None = "continue_refactor",
    train_feedback: str = _GH185_NOTE,
    evidence: list[dict[str, str]] | None = None,
) -> HandoverManifest:
    if evidence is None:
        evidence = [
            _gate_evidence(
                test_quote=_indented_quote(_GATE_TEST_QUOTE),
                impl_quote=_indented_quote(_GATE_IMPL_QUOTE),
            )
        ]
    manifest = _gate_manifest(
        verdict=verdict,
        next_action=next_action,
        evidence=evidence,
        train_feedback=train_feedback,
    )
    extra = manifest.model_extra if isinstance(manifest.model_extra, dict) else {}
    extra["evaluation"] = {"test_integrity": "PASS"}
    extra["violations"] = []
    extra["test_integrity"] = "PASS"
    return manifest


def _phase_decisions(logged: list[tuple[str, dict[str, object]]]) -> list[str]:
    return [
        str(kwargs.get("action") or "")
        for event, kwargs in logged
        if event == "PHASE_DECISION"
    ]


class TestRewriteUnmatchedTddPassKeepsCleanPass:
    """``_rewrite_unmatched_tdd_pass`` must return the action unchanged
    on a clean COMPLIANCE_PASS (GH-185)."""

    def test_pass_returns_continue_refactor_unchanged(self, tmp_git_repo: Path) -> None:
        _seed_red_green(tmp_git_repo)
        task = {
            "id": _GATE_TASK_ID,
            "issue_id": _GATE_ISSUE_ID,
            "description": "GH-185 ignore unmatched quotes on pass",
            "status": "GREEN",
            "execution_mode": "TDD",
        }
        manifest = _gh185_manifest()
        logged: list[tuple[str, dict[str, object]]] = []

        def _capture(event: str, **kwargs: object) -> None:
            logged.append((event, kwargs))

        with patch("deviate.cli.micro._log_run", side_effect=_capture):
            result = _rewrite_unmatched_tdd_pass(
                root=tmp_git_repo,
                task=task,
                manifest=manifest,
                action="continue_refactor",
                injected_diff="",
            )
        assert result == "continue_refactor", (
            f"GH-185: clean COMPLIANCE_PASS must keep continue_refactor; got {result!r}"
        )
        rejected = [
            event for event, _kwargs in logged if event == "JUDGE_EVIDENCE_REJECTED"
        ]
        assert rejected == [], (
            "GH-185: must not log JUDGE_EVIDENCE_REJECTED on a clean pass; "
            f"got {logged!r}"
        )


class TestGh185PassUnmatchedQuotesKeepGreen:
    """Pin the MeepleInn TSK-002-01 verdicts.jsonl shape."""

    def test_pass_continue_refactor_note_unmatched_quotes_forwards(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        green_sha = _gate_git(tmp_git_repo, "rev-parse", "HEAD").stdout.strip()
        logged: list[tuple[str, dict[str, object]]] = []

        def _capture(event: str, **kwargs: object) -> None:
            logged.append((event, kwargs))

        with patch("deviate.cli.micro._log_run", side_effect=_capture):
            session, output, ledger = _run_tdd_judge(
                tmp_git_repo,
                _gh185_manifest(),
                red_sha,
            )
        assert "JUDGE_REJECTED" not in output, output
        assert "JUDGE_EVIDENCE_REJECTED" not in {event for event, _ in logged}, logged
        assert session.judge_rejected is False
        assert session.pending_judge_action == "continue_refactor"
        _assert_forward(
            session,
            ledger,
            action="continue_refactor",
            completed=False,
        )
        assert _GH185_NOTE in session.train_feedback, (
            "GH-185: REFACTOR NOTE stays advice for REFACTOR; "
            f"got {session.train_feedback!r}"
        )
        head = _gate_git(tmp_git_repo, "rev-parse", "HEAD").stdout.strip()
        assert head == green_sha, (
            f"GH-185: GREEN commit must stay; before={green_sha} after={head}"
        )
        assert (tmp_git_repo / _GATE_IMPL_PATH).exists(), (
            "GH-185: GREEN implementation must not be discarded"
        )
        decisions = _phase_decisions(logged)
        assert "continue_refactor" in decisions, (
            f"GH-185: PHASE_DECISION must stay continue_refactor; got {decisions!r}"
        )
        assert "revert_green" not in decisions, (
            f"GH-185: PHASE_DECISION must not become revert_green; got {decisions!r}"
        )
        rows = [
            row
            for row in load_verdicts(tmp_git_repo, _GATE_ISSUE_ID, _GATE_TASK_ID)
            if row.get("event") != "cycle_end"
        ]
        assert rows, "expected a verdicts.jsonl row for the JUDGE application"
        row = rows[-1]
        assert row["verdict"] == "COMPLIANCE_PASS"
        assert row["next_action"] == "continue_refactor"
        assert row["next_action_raw"] == "continue_refactor"
        assert row["coerced"] is False, (
            f"GH-185: coerced must stay false on a clean pass; got {row!r}"
        )
        assert row["blast"] == "none"
        assert row["violations"] == []
        assert str(row["test_integrity"]).upper() == "PASS"
        assert "REFACTOR NOTE" in str(row["feedback"])
        assert row["next_action"] != "revert_green"

    def test_refactor_only_violation_unmatched_quotes_keeps_green(
        self, tmp_git_repo: Path
    ) -> None:
        """#183 + #185: REFACTOR NOTE is polish; evidence quotes cannot revert."""
        red_sha = _seed_red_green(tmp_git_repo)
        green_sha = _gate_git(tmp_git_repo, "rev-parse", "HEAD").stdout.strip()
        logged: list[tuple[str, dict[str, object]]] = []

        def _capture(event: str, **kwargs: object) -> None:
            logged.append((event, kwargs))

        with patch("deviate.cli.micro._log_run", side_effect=_capture):
            session, output, ledger = _run_tdd_judge(
                tmp_git_repo,
                _gh185_manifest(
                    verdict="COMPLIANCE_VIOLATION",
                    next_action="revert_green",
                    train_feedback=_GH185_NOTE,
                ),
                red_sha,
            )
        assert "JUDGE_REJECTED" not in output, output
        assert "JUDGE_EVIDENCE_REJECTED" not in {event for event, _ in logged}, logged
        assert session.judge_rejected is False
        _assert_forward(
            session,
            ledger,
            action="continue_refactor",
            completed=False,
        )
        assert _GH185_NOTE in session.train_feedback
        head = _gate_git(tmp_git_repo, "rev-parse", "HEAD").stdout.strip()
        assert head == green_sha, (
            f"#183+#185: GREEN must stay; before={green_sha} after={head}"
        )
        assert "revert_green" not in _phase_decisions(logged)

    def test_gh158_pass_plus_refactor_note_still_continues(
        self, tmp_git_repo: Path
    ) -> None:
        """Existing GH-158 pass+REFACTOR NOTE still continues (matching quotes)."""
        red_sha = _seed_red_green(tmp_git_repo)
        session, output, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                verdict="COMPLIANCE_PASS",
                next_action="continue_refactor",
                evidence=[_gate_evidence()],
                train_feedback=(
                    "COMPLIANCE_PASS: No correctness issues.\n\n" + _GH185_NOTE
                ),
            ),
            red_sha,
        )
        assert "JUDGE_REJECTED" not in output, output
        _assert_forward(
            session,
            ledger,
            action="continue_refactor",
            completed=False,
        )
        assert session.judge_rejected is False
        assert _GH185_NOTE in session.train_feedback

    def test_compliance_violation_revert_green_still_discards_green(
        self, tmp_git_repo: Path
    ) -> None:
        red_sha = _seed_red_green(tmp_git_repo)
        session, output, ledger = _run_tdd_judge(
            tmp_git_repo,
            _gate_manifest(
                verdict="COMPLIANCE_VIOLATION",
                next_action="revert_green",
                evidence=None,
                train_feedback=(
                    "COMPLIANCE_VIOLATION: The GREEN diff omitted the brand "
                    "asset. The next GREEN attempt must: copy the image."
                ),
                violations=[
                    {
                        "category": "Spec Non-Compliance",
                        "detail": "brand asset missing",
                    }
                ],
            ),
            red_sha,
        )
        assert "JUDGE_REJECTED" in output, output
        _assert_reverted_to_red(session, ledger)
        assert session.pending_judge_action == "revert_green"
        assert session.current_phase == "GREEN"
        assert not (tmp_git_repo / _GATE_IMPL_PATH).exists(), (
            "COMPLIANCE_VIOLATION + revert_green must still discard GREEN"
        )
