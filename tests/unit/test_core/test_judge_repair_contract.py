from pathlib import Path

import pytest

from deviate.core.commands import install_command
from deviate.prompts.assembly import load_template


@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_judge_repair_contract_reaches_both_prompt_modes(
    mode: str, tmp_path: Path
) -> None:
    if mode == "auto":
        prompt = load_template("judge")
    else:
        install_command("deviate-judge", tmp_path)
        prompt = (tmp_path / "deviate-judge.md").read_text(encoding="utf-8")

    contract = prompt.split("**Repair contract", 1)[1].split("```yaml", 1)[0]
    for field in ("Requirement", "Evidence", "Correction", "Verification", "Boundary"):
        assert f"**{field}**" in contract
    assert "GREEN must not edit tests" in contract
    assert "RED must not edit production code" in contract
    assert "Do not expand the acceptance contract" in contract
    assert "not a new rejection gate" in contract
    assert "then add an assertion" not in contract
