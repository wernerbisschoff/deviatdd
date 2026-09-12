"""Micro phase package: names served from submodules, patch-compatible."""

import sys as _sys
import types as _types

from . import pending as _pending
from . import suites as _suites
from . import surface as _surface

_HOME_MODULES = (_surface, _pending, _suites)

_LIVE_ONLY = frozenset(
    {
        "_review_mode",
        "_review_json_mode",
        "_review_task_id",
        "_cli_model_override",
        "_verbose",
        # Replaced wholesale on the home module by the test-suite fixture,
        # so the package must never hold a copy.
        "subprocess",
    }
)


def _home_module(name):
    for _mod in _HOME_MODULES:
        if name in _mod.__dict__:
            return _mod
    return None


for _mod in _HOME_MODULES:
    for _key, _value in _mod.__dict__.items():
        if _key.startswith("__") or _key in _LIVE_ONLY:
            continue
        globals().setdefault(_key, _value)
del _mod, _key, _value


def __getattr__(name: str):
    mod = _home_module(name)
    if mod is not None:
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    names = set(globals().keys())
    for _mod in _HOME_MODULES:
        names.update(_mod.__dict__.keys())
    return sorted(names)


class _MicroPackageModule(_types.ModuleType):
    """Forward rebinding into the owning submodule.

    Tests and callers patch names on this package and expect running code
    to see the replacement. The code lives in the submodules now, so sets
    and deletes land there too (plus the local copy, which keeps mock's
    save/restore pointed at the right originals).
    """

    def __setattr__(self, name, value):
        if name in _LIVE_ONLY:
            mod = _home_module(name)
            if mod is not None:
                mod.__dict__[name] = value
                return
        for _mod in _HOME_MODULES:
            if name in _mod.__dict__:
                _mod.__dict__[name] = value
        super().__setattr__(name, value)

    def __delattr__(self, name):
        for _mod in _HOME_MODULES:
            if name in _mod.__dict__:
                del _mod.__dict__[name]
        try:
            super().__delattr__(name)
        except AttributeError:
            pass


_sys.modules[__name__].__class__ = _MicroPackageModule
