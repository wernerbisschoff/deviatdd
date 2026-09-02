"""JUDGE revert-route rename: ``revert_to_red`` → ``revert_green`` and
``revert_before`` → ``revert_red``.

The old names described a destination (``revert_to_red``) or a point in
history (``revert_before``); JUDGE agents kept misreading ``revert_to_red``
as "revert the RED phase as well". The new names state the blast radius:
``revert_green`` discards GREEN and keeps RED; ``revert_red`` discards RED
and GREEN.

Contract:
- The canonical enum is ``revert_green`` / ``revert_red`` (plus the three
  unchanged forward routes).
- Legacy names are accepted as aliases and normalized at the two trust
  boundaries: ``_coerce_judge_action`` (JUDGE manifests) and
  ``SessionState.load`` (persisted ``pending_judge_action`` on resume).
- Prompts advertise only the new names.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deviate.state.config import SessionState


class TestCanonicalNamesInEnum:
    """The shared alias map in ``state/config.py`` carries the contract."""

    def test_new_names_are_canonical(self):
        from deviate.state.config import JUDGE_REVERT_ACTION_ALIASES

        assert JUDGE_REVERT_ACTION_ALIASES == {
            "revert_to_red": "revert_green",
            "revert_before": "revert_red",
        }


class TestSessionLoadNormalizesLegacyPendingAction:
    """Persisted ``pending_judge_action`` from a pre-rename session file
    must route identically after an upgrade."""

    @pytest.mark.parametrize(
        "legacy,canonical",
        [
            ("revert_to_red", "revert_green"),
            ("revert_before", "revert_red"),
        ],
    )
    def test_legacy_value_normalizes_on_load(self, tmp_path: Path, legacy, canonical):
        path = tmp_path / "session.json"
        path.write_text(
            json.dumps(
                SessionState(pending_judge_action=legacy).model_dump(mode="json")
            ),
            encoding="utf-8",
        )
        session = SessionState.load(path)
        assert session.pending_judge_action == canonical

    @pytest.mark.parametrize(
        "value",
        ["revert_green", "revert_red", "skip_refactor", "", "continue_refactor"],
    )
    def test_canonical_and_forward_values_pass_through(self, tmp_path: Path, value):
        path = tmp_path / "session.json"
        path.write_text(
            json.dumps(
                SessionState(pending_judge_action=value).model_dump(mode="json")
            ),
            encoding="utf-8",
        )
        session = SessionState.load(path)
        assert session.pending_judge_action == value

    def test_saving_canonical_name_round_trips(self, tmp_path: Path):
        path = tmp_path / "session.json"
        SessionState(pending_judge_action="revert_green").save(path)
        assert SessionState.load(path).pending_judge_action == "revert_green"


class TestCoerceJudgeActionAcceptsNewNamesAndAliases:
    """``_coerce_judge_action`` must accept the canonical names and
    normalize the legacy aliases; forward routes and defaults are
    unchanged."""

    @pytest.mark.parametrize(
        "declared,expected",
        [
            ("revert_green", "revert_green"),
            ("revert_red", "revert_red"),
            ("revert_to_red", "revert_green"),
            ("revert_before", "revert_red"),
        ],
    )
    def test_revert_routes_resolve(
        self,
        declared: str,
        expected: str,
    ) -> None:
        from deviate.cli.micro import _coerce_judge_action
        from deviate.core.agent import HandoverManifest

        extra: dict[str, object] = {}
        if declared in {"revert_red", "revert_before"}:
            extra["evaluation"] = {"test_integrity": "FAIL"}
        manifest = HandoverManifest.model_construct(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-RENAME-01",
            next_action=declared,
            **extra,
        )
        result = _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION")
        assert result == expected, (
            f"declared {declared!r}: expected {expected!r}, got {result!r}"
        )

    def test_spec_only_violation_defaults_to_revert_green(self) -> None:
        from deviate.cli.micro import _coerce_judge_action
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest.model_construct(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-RENAME-02",
        )
        assert _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION") == "revert_green"

    def test_test_defect_forces_revert_red(self) -> None:
        from deviate.cli.micro import _coerce_judge_action
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest.model_construct(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-RENAME-03",
        )
        result = _coerce_judge_action(
            manifest, "COMPLIANCE_VIOLATION", failure_kind="test_defect"
        )
        assert result == "revert_red"

    def test_unknown_action_still_falls_back_to_default(self) -> None:
        from deviate.cli.micro import _coerce_judge_action
        from deviate.core.agent import HandoverManifest

        manifest = HandoverManifest.model_construct(
            phase="JUDGE",
            status="SUCCESS",
            verdict="COMPLIANCE_VIOLATION",
            task_id="TSK-RENAME-04",
            next_action="revert_everything",
        )
        result = _coerce_judge_action(manifest, "COMPLIANCE_VIOLATION")
        assert result == "revert_green"


class TestJudgePromptAdvertisesOnlyNewNames:
    """The JUDGE prompt is the JUDGE agent's contract. It must advertise the
    canonical names and must not mention the legacy aliases (mentioning them
    invites the model to emit them)."""

    def test_prompt_names_revert_green_and_revert_red(self) -> None:
        from importlib import resources

        text = resources.files("deviate.prompts.auto").joinpath("judge.md").read_text()
        assert "revert_green" in text
        assert "revert_red" in text

    def test_prompt_does_not_mention_legacy_aliases(self) -> None:
        from importlib import resources

        text = resources.files("deviate.prompts.auto").joinpath("judge.md").read_text()
        assert "revert_to_red" not in text
        assert "revert_before" not in text
