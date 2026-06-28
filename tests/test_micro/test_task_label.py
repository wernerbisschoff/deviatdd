from __future__ import annotations


class TestTaskLabel:
    def test_bare_id(self) -> None:
        from deviate.cli.micro import _task_label

        assert _task_label({"id": "TSK-013-01"}) == "TSK-013-01"

    def test_empty_description_falls_back_to_id(self) -> None:
        from deviate.cli.micro import _task_label

        assert _task_label({"id": "TSK-013-01", "description": ""}) == "TSK-013-01"

    def test_whitespace_description_falls_back_to_id(self) -> None:
        from deviate.cli.micro import _task_label

        assert _task_label({"id": "TSK-013-01", "description": "   "}) == "TSK-013-01"

    def test_short_description_included_verbatim(self) -> None:
        from deviate.cli.micro import _task_label

        task = {
            "id": "TSK-012-01",
            "description": "FLOW-11 capture helper + path/persistence/idempotency tests",
        }
        assert _task_label(task) == (
            "TSK-012-01: FLOW-11 capture helper + path/persistence/idempotency tests"
        )

    def test_long_description_truncated_with_ellipsis(self) -> None:
        from deviate.cli.micro import _TASK_DESC_MAX, _task_label

        long_desc = "x" * (_TASK_DESC_MAX + 25)
        label = _task_label({"id": "TSK-013-01", "description": long_desc})
        assert label.startswith("TSK-013-01: ")
        # Truncated at _TASK_DESC_MAX + ellipsis, plus the "TSK-013-01: " prefix.
        assert label.endswith("…")
        assert len(label) == len("TSK-013-01: ") + _TASK_DESC_MAX + 1

    def test_missing_id_defaults_to_question_mark(self) -> None:
        from deviate.cli.micro import _task_label

        # A task dict without an id still surfaces its description so the
        # log line stays informative; the bare id falls back to "?".
        assert _task_label({"description": "no id here"}) == "?: no id here"

    def test_surrounding_whitespace_stripped(self) -> None:
        from deviate.cli.micro import _task_label

        task = {"id": "TSK-013-01", "description": "  padded name  "}
        assert _task_label(task) == "TSK-013-01: padded name"
