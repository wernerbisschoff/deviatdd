from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_agent_invocation():
    """Prevent any test from actually invoking an agent backend.

    The micro phase now calls ``_invoke_agent`` when ``--agent`` is
    passed.  This fixture ensures those calls are short-circuited so
    that tests never fire a real prompt against opencode, droid, etc.
    """
    with patch("deviate.cli.micro._invoke_agent") as mock:
        mock.return_value = True
        yield
