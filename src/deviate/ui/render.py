from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_jsonl(event: str, **fields: Any) -> None:
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
