"""GH-230: successive JUDGE requirements can be mutually incompatible.

Detector only — no agent, no git. Wallet-service TSK-001-06 oscillated
between strict orderViewId matching and preserving submitted-state
fixtures that returned a different orderViewId.
"""

from __future__ import annotations

import pytest

from deviate.core.judge_contradiction import (
    detect_judge_requirement_contradiction,
    extract_repair_fields,
    requirement_focus,
)

STRICT_IDENTITY = """\
The next GREEN attempt must:
- Requirement: AC-PLAN-001 requires strict orderViewId matching for mismatched evidence.
- Evidence: Returned orderViewId did not match the requested provider identity.
- Correction: Reject when the returned orderViewId does not match the requested identity.
- Verification: Run the retained regression; mismatched evidence must fail the identity assertion.
- Boundary: Preserve the RED tests and public interface. Do not expand the acceptance contract.
"""

PRESERVE_FIXTURE = """\
The next GREEN attempt must:
- Requirement: Preserve existing submitted-state tests that use a different returned orderViewId.
- Evidence: Submitted-state fixtures return a different orderViewId than the request.
- Correction: Keep the submitted-state fixture that returns a different orderViewId.
- Verification: Existing submitted-state tests must keep passing unchanged.
- Boundary: Do not change existing submitted-state tests. Do not expand the acceptance contract.
"""

INCREMENT = """\
The next GREEN attempt must:
- Requirement: AC-PLAN-001 requires incrementing the input by one.
- Correction: Implement increment in src/example.py using the supplied input.
- Boundary: Preserve the RED tests and public interface. Do not expand the acceptance contract.
"""

ERROR_PATH = """\
The next GREEN attempt must:
- Requirement: AC-PLAN-001 also requires the error path to raise ValueError.
- Correction: Raise ValueError for negative inputs in src/example.py.
- Boundary: Preserve the RED tests and public interface. Do not expand the acceptance contract.
"""

REQUESTED_ID = """\
The next GREEN attempt must:
- Requirement: Return the requested orderViewId on submit.
- Correction: Map the request identity through the provider adapter.
"""

PROVIDER_ID = """\
The next GREEN attempt must:
- Requirement: Return the provider catalog orderViewId on submit.
- Correction: Persist the catalog identifier from the provider payload.
"""


def test_extracts_repair_contract_fields() -> None:
    fields = extract_repair_fields(STRICT_IDENTITY)
    assert "strict orderViewId matching" in fields["requirement"]
    assert "does not match the requested identity" in fields["correction"]


def test_requirement_focus_drops_stock_preserve_boundary() -> None:
    focus = requirement_focus(INCREMENT)
    assert "incrementing" in focus
    assert "public interface" not in focus.lower()


def test_wallet_style_polar_flip_is_a_contradiction() -> None:
    found = detect_judge_requirement_contradiction([STRICT_IDENTITY], PRESERVE_FIXTURE)
    assert found is not None
    assert found.kind == "polar_flip"
    assert "identity" in found.summary.lower() or "fixture" in found.summary.lower()


def test_reverse_wallet_polar_flip_is_a_contradiction() -> None:
    found = detect_judge_requirement_contradiction([PRESERVE_FIXTURE], STRICT_IDENTITY)
    assert found is not None
    assert found.kind == "polar_flip"


def test_compatible_refinements_are_not_a_contradiction() -> None:
    assert detect_judge_requirement_contradiction([INCREMENT], ERROR_PATH) is None


def test_identical_restated_requirement_is_not_a_contradiction() -> None:
    assert (
        detect_judge_requirement_contradiction([STRICT_IDENTITY], STRICT_IDENTITY)
        is None
    )


def test_first_rejection_has_no_contradiction() -> None:
    assert detect_judge_requirement_contradiction([], STRICT_IDENTITY) is None
    assert detect_judge_requirement_contradiction([STRICT_IDENTITY], "") is None


def test_aba_oscillation_is_a_contradiction() -> None:
    found = detect_judge_requirement_contradiction(
        [REQUESTED_ID, PROVIDER_ID], REQUESTED_ID
    )
    assert found is not None
    assert found.kind == "oscillation"


def test_explicit_incompatible_fixture_language() -> None:
    current = (
        "The next GREEN attempt must: these requirements are mutually "
        "incompatible with the submitted-state fixture that returns a "
        "different orderViewId."
    )
    found = detect_judge_requirement_contradiction([PRESERVE_FIXTURE], current)
    assert found is not None
    assert found.kind == "explicit"


def test_explicit_without_shared_subject_is_not_a_contradiction() -> None:
    current = (
        "The next GREEN attempt must: these requirements are mutually "
        "incompatible with the submitted-state fixture."
    )
    assert detect_judge_requirement_contradiction([INCREMENT], current) is None


def test_generic_matching_without_shared_identity_is_not_a_contradiction() -> None:
    generic_match = (
        "The next GREEN attempt must: Requirement: output values must match "
        "the snapshot. Correction: update formatting in src/example.py."
    )
    keep_tests = (
        "The next GREEN attempt must: Requirement: preserve existing "
        "submitted-state tests. Correction: keep the tests passing unchanged."
    )
    assert detect_judge_requirement_contradiction([generic_match], keep_tests) is None
    assert detect_judge_requirement_contradiction([keep_tests], generic_match) is None


def test_non_adjacent_history_does_not_halt() -> None:
    assert (
        detect_judge_requirement_contradiction(
            [STRICT_IDENTITY, INCREMENT], PRESERVE_FIXTURE
        )
        is None
    )


@pytest.mark.behavioral
def test_same_requirement_with_opposite_polarity_is_a_contradiction() -> None:
    prior = (
        "The next GREEN attempt must require the returned orderViewId to "
        "match the requested identity."
    )
    current = (
        "The next GREEN attempt must reject matching the requested "
        "orderViewId and preserve the provider identity instead."
    )

    found = detect_judge_requirement_contradiction([prior], current)

    assert found is not None
    assert found.kind == "polar_flip"


@pytest.mark.behavioral
def test_repeated_aba_detection_returns_one_stable_result() -> None:
    first = detect_judge_requirement_contradiction(
        [REQUESTED_ID, PROVIDER_ID], REQUESTED_ID
    )
    second = detect_judge_requirement_contradiction(
        [REQUESTED_ID, PROVIDER_ID], REQUESTED_ID
    )

    assert first is not None
    assert second == first
    assert first.kind == "oscillation"
