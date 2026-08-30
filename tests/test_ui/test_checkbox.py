from __future__ import annotations

from deviate.core.commands import OPTIONAL_PACK_NAMES
from deviate.ui.checkbox import CheckboxSession, _arrow_from_sequence, checkbox_select


class TestCheckboxSession:
    def test_default_is_empty(self) -> None:
        session = CheckboxSession(options=OPTIONAL_PACK_NAMES)
        assert session.picked() == []
        assert session.apply("enter") == "confirm"
        assert session.picked() == []

    def test_space_toggles_product_and_pr(self) -> None:
        session = CheckboxSession(options=OPTIONAL_PACK_NAMES)
        assert session.options[0] == "product"
        session.apply("space")
        session.apply("down")  # merge
        session.apply("down")  # pr
        session.apply("space")
        assert session.apply("enter") == "confirm"
        assert session.picked() == ["product", "pr"]

    def test_esc_is_not_confirm(self) -> None:
        session = CheckboxSession(options=OPTIONAL_PACK_NAMES)
        session.apply("space")
        assert session.apply("esc") == "continue"
        assert session.picked() == ["product"]

    def test_up_and_down_keep_continue(self) -> None:
        session = CheckboxSession(options=OPTIONAL_PACK_NAMES)
        assert session.apply("down") == "continue"
        assert session.cursor == 1
        assert session.apply("up") == "continue"
        assert session.cursor == 0
        assert session.picked() == []

    def test_space_untoggles(self) -> None:
        session = CheckboxSession(options=OPTIONAL_PACK_NAMES)
        session.apply("space")
        session.apply("space")
        assert session.picked() == []


class TestArrowSequence:
    def test_csi_and_ss3_and_three_byte_leftover(self) -> None:
        assert _arrow_from_sequence("[A") == "up"
        assert _arrow_from_sequence("[B") == "down"
        assert _arrow_from_sequence("OA") == "up"
        assert _arrow_from_sequence("OB") == "down"
        assert _arrow_from_sequence("\x1b[A") == "up"
        assert _arrow_from_sequence("\x1b[B") == "down"
        assert _arrow_from_sequence("\x1bOA") == "up"
        assert _arrow_from_sequence("\x1bOB") == "down"
        assert _arrow_from_sequence("") is None
        assert _arrow_from_sequence("\x1b") is None


class TestCheckboxSelectLoop:
    def test_read_key_drives_product_and_pr(self) -> None:
        keys = iter(["space", "down", "down", "space", "enter"])
        picked = checkbox_select(
            OPTIONAL_PACK_NAMES,
            title="Optional command packs",
            read_key=lambda: next(keys),
        )
        assert picked == ["product", "pr"]
