"""Tests for the top-level `deviate` package.

Mirrors `src/deviate/__init__.py` — the module-level version lookup that
fires on every `import deviate`. The CLI smoke suite (`test_cli/test_init.py`)
exercises the same lookup via `deviate --version`; these tests guard the
import-time contract directly so a regression fails at collection rather
than at first invocation.
"""


def test_module_version_resolves():
    """Import-time guard: deviate.__version__ must not raise PackageNotFoundError.

    Regression: src/deviate/__init__.py previously called
    version("deviate") (the import name) instead of "deviatdd" (the
    distribution name in pyproject.toml), so importing the package failed
    with PackageNotFoundError and the entire CLI was unreachable.
    """
    import importlib

    import deviate

    importlib.reload(deviate)  # force re-evaluation of the module-level call
    assert deviate.__version__, "deviate.__version__ must be a non-empty string"
    assert "+unknown" not in deviate.__version__, (
        f"deviate.__version__ is the missing-metadata fallback: {deviate.__version__!r}. "
        "Check that the deviatdd distribution is installed (e.g. "
        "`uv tool install --force .`)."
    )
