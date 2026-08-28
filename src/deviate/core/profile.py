from __future__ import annotations

from typing import Literal

ExecutionProfile = Literal["full", "fast"]

_PROFILE_DEFAULTS: dict[str, tuple[bool, bool]] = {
    "full": (False, False),
    "fast": (True, True),
}

# Legacy names accepted on the CLI and in config. Not public choices.
# ``secure`` keeps JUDGE and skips REFACTOR; it is not a third profile.
_PROFILE_ALIAS_FLAGS: dict[str, tuple[bool, bool]] = {
    "secure": (False, True),
}

_PROFILE_NAME_ALIASES: dict[str, str] = {
    "default": "full",
}

_VALID_PROFILE_CHOICES = ", ".join(sorted(_PROFILE_DEFAULTS))


def canonicalize_profile(profile: str) -> str:
    """Map a legacy profile name. ``secure`` stays ``secure`` (internal alias)."""
    return _PROFILE_NAME_ALIASES.get(profile, profile)


def resolve_profile(
    profile: str,
    no_judge: bool | None = None,
    no_refactor: bool | None = None,
) -> tuple[bool, bool]:
    profile = canonicalize_profile(profile)
    if profile in _PROFILE_DEFAULTS:
        no_j, no_r = _PROFILE_DEFAULTS[profile]
    elif profile in _PROFILE_ALIAS_FLAGS:
        no_j, no_r = _PROFILE_ALIAS_FLAGS[profile]
    else:
        raise ValueError(
            f"Invalid profile '{profile}'. Must be one of: {_VALID_PROFILE_CHOICES}"
        )

    if no_judge is not None:
        no_j = no_judge
    if no_refactor is not None:
        no_r = no_refactor

    return (no_j, no_r)
