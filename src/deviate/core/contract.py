from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def emit_contract(data: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"contract_{timestamp}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def load_contract(path: Path) -> dict:
    return json.loads(path.read_text())
