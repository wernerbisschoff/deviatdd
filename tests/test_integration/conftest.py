from __future__ import annotations

from contextlib import chdir
from pathlib import Path

import pytest

from deviate.state.config import SessionState


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    dot_dir = tmp_path / ".deviate"
    dot_dir.mkdir(parents=True)
    session = SessionState(current_phase="IDLE")
    session.save(dot_dir / "session.json")
    spec_dir = tmp_path / "specs" / "001-deviate-cli-python"
    spec_dir.mkdir(parents=True)
    with chdir(tmp_path):
        yield tmp_path
