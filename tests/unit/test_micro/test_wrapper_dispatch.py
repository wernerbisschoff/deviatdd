"""AC-PLAN-013/014: eight thin wrappers dispatch exactly one kernel (US-007-01, FR-007-07)."""

from __future__ import annotations

import inspect

import pytest

import deviate.cli.micro as micro

WRAPPERS = [
    ("red_pre", "_red_pre_kernel"),
    ("red_post", "_red_post_kernel"),
    ("green_pre", "_green_pre_kernel"),
    ("green_post", "_green_post_kernel"),
    ("judge_pre", "_judge_pre_kernel"),
    ("judge_post", "_judge_post_kernel"),
    ("refactor_pre", "_refactor_pre_kernel"),
    ("refactor_post", "_refactor_post_kernel"),
]


@pytest.mark.behavioral
@pytest.mark.parametrize("wrapper,kernel", WRAPPERS)
def test_wrapper_kernel_exists(wrapper, kernel):
    assert hasattr(micro, wrapper), f"missing wrapper {wrapper}"
    assert callable(getattr(micro, wrapper)), f"wrapper not callable {wrapper}"
    assert hasattr(micro, kernel), f"missing kernel {kernel}"
    assert callable(getattr(micro, kernel)), f"kernel not callable {kernel}"


@pytest.mark.spy
@pytest.mark.parametrize("wrapper,kernel", WRAPPERS)
def test_wrapper_calls_exactly_one_kernel(wrapper, kernel):
    fn = getattr(micro, wrapper)
    src = inspect.getsource(fn)
    hits = src.count("_kernel(")
    assert hits == 1, f"{wrapper} calls {hits} kernels, expected exactly 1 ({kernel})"


@pytest.mark.behavioral
@pytest.mark.parametrize("kernel", [k for _, k in WRAPPERS])
def test_unknown_task_id_raises_kernel_error_token(kernel):
    from pathlib import Path

    fn = getattr(micro, kernel)
    with pytest.raises(micro.KernelError) as exc:
        if "root" in inspect.signature(fn).parameters:
            try:
                fn(task_id="NOPE-404", root=Path("/nonexistent-root-xyz"))
            except TypeError:
                fn("NOPE-404", Path("/nonexistent-root-xyz"))
        else:
            fn(task_id="NOPE-404")
    assert exc.value.token, "KernelError must carry a token"


@pytest.mark.behavioral
def test_green_pre_and_judge_pre_emit_no_contract():
    green_src = inspect.getsource(micro.green_pre)
    judge_src = inspect.getsource(micro.judge_pre)
    assert green_src.count("_kernel(") == 1, "green_pre must wrap exactly one kernel"
    assert judge_src.count("_kernel(") == 1, "judge_pre must wrap exactly one kernel"
    assert "five-key" not in green_src + judge_src
    assert "eight-field" not in green_src + judge_src


@pytest.mark.spy
def test_double_kernel_call_is_rejected():
    fn = getattr(micro, "red_post")
    src = inspect.getsource(fn)
    assert src.count("_kernel(") == 1, "double kernel call must fail this test"
    assert src.count("_invoke_agent") == 0, "wrappers must never reach _invoke_agent"
