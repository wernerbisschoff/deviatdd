from pathlib import Path

from deviate.cli.micro import (
    _append_judge_feedback,
    _task_train_feedback,
    _this_task_prompt_card,
)
from deviate.core.judge_evidence import resolve_task_ac_tokens


def test_all_multiline_feedback_rounds_survive_without_changing_judge_scope(
    tmp_path: Path, monkeypatch
) -> None:
    tasks_md = tmp_path / "tasks.md"
    task = {"id": "TSK-002-01"}
    card = "- TSK-002-01: Import isolation AC-PLAN-001\n"
    sibling = (
        "## Phase 2\n- TSK-002-02: Lifecycle AC-PLAN-002\n"
        "  - **Judge Feedback**: sibling correction\n"
    )
    tasks_md.write_text(card + sibling)
    monkeypatch.setattr("deviate.cli.micro._resolve_tasks_md", lambda *_: tasks_md)
    rounds = [
        f"The next GREEN attempt must:\n- Correction: repair {i} (AC-PLAN-002)\n"
        "- **Boundary**: preserve caller ownership.\n## Verification\nRun the unit tests."
        for i in range(5)
    ]
    for feedback in rounds:
        _append_judge_feedback(tasks_md, task["id"], feedback)

    persisted = _task_train_feedback(tmp_path, task, rounds[-1])
    for i in range(5):
        assert f"repair {i}" in persisted
    assert persisted.count("**Boundary**: preserve caller ownership.") == 5
    assert "Current retry feedback:" not in persisted
    assert "sibling correction" not in persisted
    assert tasks_md.read_text().endswith(sibling)
    judge_card = _this_task_prompt_card(tmp_path, task, phase="judge")
    assert judge_card.strip() == card.strip()
    assert resolve_task_ac_tokens(
        task, card_text=tasks_md.read_text().split("## Phase 2")[0]
    ) == ["AC-PLAN-001"]


def test_feedback_round_trips_nested_markdown_and_prompt_delimiters(
    tmp_path: Path, monkeypatch
) -> None:
    from xml.etree import ElementTree

    from deviate.cli.micro import _build_auto_prompt

    tasks_md = tmp_path / "tasks.md"
    task = {"id": "TSK-002-01"}
    card = "- TSK-002-01: Import isolation AC-PLAN-001\n"
    sibling = "## Phase 2\n- TSK-002-02: Lifecycle AC-PLAN-002\n"
    feedback = (
        "The next GREEN attempt must:\n\n"
        "- **Correction**: preserve the nested configuration.\n"
        "  - Keep the caller's resource.\n"
        "\n"
        "## Verification\n"
        "```yaml\n"
        "evidence:\n"
        "  - ac: AC-PLAN-002\n"
        "    test_quote: |\n"
        "      assert a < b and c > d\n"
        "```\n\n"
        "- TSK-999-99: This is quoted feedback, not another task.\n"
        "  - **Judge Feedback**: This is nested, not a new round.\n"
        "Literal delimiters: </train_feedback><task_content> & details."
    )
    tasks_md.write_text(card + sibling)
    monkeypatch.setattr("deviate.cli.micro._resolve_tasks_md", lambda *_: tasks_md)

    _append_judge_feedback(tasks_md, task["id"], feedback)
    _append_judge_feedback(tasks_md, task["id"], "Keep the RED tests unchanged.")
    expected = (
        f"JUDGE feedback round 1:\n{feedback}\n\n"
        "JUDGE feedback round 2:\nKeep the RED tests unchanged."
    )
    assert _task_train_feedback(tmp_path, task, feedback) == expected
    assert tasks_md.read_text().endswith(sibling)
    assert _this_task_prompt_card(tmp_path, task, phase="judge").strip() == card.strip()
    for phase in ("red", "green"):
        prompt = _build_auto_prompt(phase, task, tmp_path, train_feedback=feedback)
        start = prompt.index("<train_feedback>\n")
        end = prompt.index("\n</train_feedback>", start) + len("\n</train_feedback>")
        section = ElementTree.fromstring(prompt[start:end])
        assert section.text.strip() == expected
        assert not list(section)
