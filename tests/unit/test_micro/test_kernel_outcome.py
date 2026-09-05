"""AC-PLAN-001/002: KernelOutcome token and KernelError mapping (RED)."""

import pytest

pytestmark = pytest.mark.behavioral


def test_manual_prints_fixed_token_verbatim_exit_zero(capsys):
    from deviate.cli.micro import KernelOutcome, print_kernel_outcome

    outcome = KernelOutcome(token="RED_POST_OK")
    rc = print_kernel_outcome(outcome)
    out = capsys.readouterr().out
    assert out.strip() == "RED_POST_OK"
    assert rc == 0


def test_kernel_error_manual_exits_1_auto_catches_per_step(capsys):
    from deviate.cli.micro import KernelError, handle_kernel_error

    err = KernelError(token="RED_POST_OK", detail="boom")
    rc = handle_kernel_error(err, surface="manual")
    out = capsys.readouterr().out
    assert "RED_POST_OK" in out
    assert rc == 1
    caught = handle_kernel_error(err, surface="auto")
    assert caught == "RED_POST_OK"


def test_missing_task_id_fails_with_token_empty_detail_no_stack_leak(capsys):
    from deviate.cli.micro import KernelError, handle_kernel_error

    err = KernelError(token="RED_POST_OK", detail="")
    rc = handle_kernel_error(err, surface="manual")
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "RED_POST_OK" in out
    assert rc == 1
    assert "Traceback" not in out
