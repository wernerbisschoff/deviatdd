from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Single module-level lock that serializes ALL process-level writes to the
# interactive Console / raw sys.stdout fd. Background reader threads spawned
# by `core.agent._invoke_streaming` invoke user-supplied output callbacks
# (notably `cli.micro._make_output_handler`'s closure, which calls `c.print`)
# concurrently with main-thread `c.print` writes. Without serialization, the
# `sys.stdout.flush()` call inside the handler's tool-call branch (and
# `emit_jsonl` below) bypass Rich's internal RLock and race with main-thread
# writes at the OS fd level — historically manifesting as a SIGSEGV during
# `run --all` JUDGE phase on macOS. Sharing one lock across all stdout-
# emitting call sites guarantees a consistent writer/flush ordering and
# closes both the active (handler) and latent (`--json`) crash paths.
_stdout_lock = threading.Lock()

# Public alias so other modules (e.g. `cli.micro._make_output_handler`)
# import the same instance.
stdout_lock = _stdout_lock


def emit_jsonl(event: str, **fields: Any) -> None:
    with _stdout_lock:
        data = {"event": event, "timestamp": _now_iso(), **fields}
        sys.stdout.write(json.dumps(data) + "\n")
        sys.stdout.flush()


def is_interactive() -> bool:
    if os.environ.get("CI"):
        return False
    try:
        return os.isatty(sys.stdout.fileno())
    except (OSError, AttributeError):
        return False
