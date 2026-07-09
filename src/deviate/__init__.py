from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("deviatdd")
except PackageNotFoundError:
    # Source checkouts without an editable install (e.g. running the module
    # directly from a git clone) have no dist-info. Fall back to a sentinel
    # so the CLI still imports; downstream code can detect it via the
    # "+unknown" suffix.
    __version__ = "0.0.0+unknown"
