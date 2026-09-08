"""RED: named missing-infrastructure signal plus non-error RED status.

Covers AC-PLAN-004 (named signal with setup command, non-error RED status)
and AC-PLAN-005 (partial infra resolves to exactly one outcome).
Constitution: Micro-layer RED verification boundary; pytest unit suite.
"""

from __future__ import annotations

import pytest

from deviate.cli import micro


@pytest.mark.behavioral
def test_named_signal_carries_setup_command() -> None:
    signal = micro.build_precondition_signal(
        setup_command="mise run setup:e2e", detail="probe db:5432 timed out after 5s"
    )
    text = str(signal)
    assert micro.PRECONDITION_SIGNAL_NAME in text
    assert "mise run setup:e2e" in text


@pytest.mark.behavioral
def test_named_signal_carries_probe_detail() -> None:
    signal = micro.build_precondition_signal(
        setup_command="mise run setup:e2e", detail="probe db:5432 timed out after 5s"
    )
    assert "db:5432" in str(signal)


@pytest.mark.behavioral
def test_env_not_ready_preserved_as_alias() -> None:
    assert micro.is_precondition_signal("ENV_NOT_READY") is True
    assert micro.is_precondition_signal(micro.PRECONDITION_SIGNAL_NAME) is True
    assert micro.is_precondition_signal(micro.EnvNotReadyError("x")) is True


@pytest.mark.behavioral
def test_precondition_maps_to_non_error_red_status() -> None:
    assert micro.RED_PRECONDITION_STATUS != "ERROR"
    signal = micro.build_precondition_signal(
        setup_command="mise run setup:e2e", detail="probe down"
    )
    assert micro.red_status_for_signal(signal) == micro.RED_PRECONDITION_STATUS


@pytest.mark.behavioral
def test_partial_infra_resolves_to_exactly_one_outcome() -> None:
    proof = micro.coerce_partial_infra_result(
        has_red_proof=True,
        signal=micro.build_precondition_signal(
            setup_command="mise run setup:e2e", detail="cache up, db down"
        ),
    )
    blocked = micro.coerce_partial_infra_result(
        has_red_proof=False,
        signal=micro.build_precondition_signal(
            setup_command="mise run setup:e2e", detail="cache up, db down"
        ),
    )
    assert (proof is None) != (blocked is None)
    assert "mise run setup:e2e" in str(blocked or proof)


@pytest.mark.behavioral
def test_malformed_env_file_names_file_and_parse_failure() -> None:
    signal = micro.build_precondition_signal_for_env_file(
        path=".env.instance", error="line 3: unterminated quote"
    )
    text = str(signal)
    assert ".env.instance" in text
    assert "unterminated quote" in text
    assert "mise run setup:e2e" in text or micro.PRECONDITION_SIGNAL_NAME in text


@pytest.mark.spy
def test_unknown_signal_leaves_retry_handling_unchanged() -> None:
    assert micro.is_precondition_signal("SOME_UNKNOWN_SIGNAL") is False
    assert micro.is_precondition_signal(ValueError("boom")) is False
