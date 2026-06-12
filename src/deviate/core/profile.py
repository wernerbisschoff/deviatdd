from __future__ import annotations

from typing import Literal

ExecutionProfile = Literal["full", "fast", "secure"]

_PROFILE_DEFAULTS: dict[ExecutionProfile, tuple[bool, bool]] = {
    "full": (False, False),
    "fast": (True, True),
    "secure": (False, True),
}


def resolve_profile(
    profile: str,
    no_judge: bool | None = None,
    no_refactor: bool | None = None,
) -> tuple[bool, bool]:
    if profile not in _PROFILE_DEFAULTS:
        valid = ", ".join(sorted(_PROFILE_DEFAULTS))
        raise ValueError(f"Invalid profile '{profile}'. Must be one of: {valid}")

    no_j, no_r = _PROFILE_DEFAULTS[profile]  # type: ignore[assignment]

    if no_judge is not None:
        no_j = no_judge
    if no_refactor is not None:
        no_r = no_refactor

    return (no_j, no_r)
