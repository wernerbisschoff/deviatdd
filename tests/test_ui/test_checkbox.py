from __future__ import annotations

from deviate.core.commands import OPTIONAL_PACK_NAMES
from deviate.ui.checkbox import CheckboxSession, checkbox_select


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

    def test_space_untoggles(self) -> None:
        session = CheckboxSession(options=OPTIONAL_PACK_NAMES)
        session.apply("space")
        session.apply("space")
        assert session.picked() == []


class TestCheckboxSelectLoop:
    def test_read_key_drives_product_and_pr(self) -> None:
        keys = iter(["space", "down", "down", "space", "enter"])
        picked = checkbox_select(
            OPTIONAL_PACK_NAMES,
            title="Optional command packs",
            read_key=lambda: next(keys),
        )
        assert picked == ["product", "pr"]
