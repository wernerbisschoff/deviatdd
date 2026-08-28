from __future__ import annotations

from typing import Literal

ExecutionProfile = Literal["full", "fast", "judge"]

_PROFILE_DEFAULTS: dict[str, tuple[bool, bool]] = {
    "full": (False, False),
    "fast": (True, True),
    "judge": (False, True),
}

# Legacy names accepted on the CLI and in config, then rewritten.
_PROFILE_ALIASES: dict[str, str] = {
    "secure": "judge",
}

_VALID_PROFILE_CHOICES = ", ".join(sorted(_PROFILE_DEFAULTS))


def canonicalize_profile(profile: str) -> str:
    """Map a legacy profile name to the public vocabulary."""
    return _PROFILE_ALIASES.get(profile, profile)


def resolve_profile(
    profile: str,
    no_judge: bool | None = None,
    no_refactor: bool | None = None,
) -> tuple[bool, bool]:
    profile = canonicalize_profile(profile)
    if profile not in _PROFILE_DEFAULTS:
        raise ValueError(
            f"Invalid profile '{profile}'. Must be one of: {_VALID_PROFILE_CHOICES}"
        )

    no_j, no_r = _PROFILE_DEFAULTS[profile]

    if no_judge is not None:
        no_j = no_judge
    if no_refactor is not None:
        no_r = no_refactor

    return (no_j, no_r)
