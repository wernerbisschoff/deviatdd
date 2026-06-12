from __future__ import annotations

from unittest.mock import patch

import pytest

from deviate.core.agent import HandoverManifest


@pytest.fixture(autouse=True)
def mock_agent_invocation():
    """Prevent any test from actually invoking an agent backend.

    The micro phase now calls ``_invoke_agent`` when ``--agent`` is
    passed.  This fixture ensures those calls are short-circuited so
    that tests never fire a real prompt against opencode, droid, etc.

    Returns a successful HandoverManifest so phase gating passes.
    """
    with patch("deviate.cli.micro._invoke_agent") as mock:
        mock.return_value = HandoverManifest(
            phase="RED",
            status="TEST_WRITTEN_FAILING",
        )
        yield
