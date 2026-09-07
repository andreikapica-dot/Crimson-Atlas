"""Lifecycle tests for the local WebSocket server."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.local_server import LocalServer


class TestLocalServerStartup(unittest.TestCase):
    def test_start_propagates_bind_failure(self) -> None:
        server = LocalServer()
        failure = OSError("address already in use")
        with patch.object(server, "_serve_forever", AsyncMock(side_effect=failure)):
            with self.assertRaisesRegex(RuntimeError, "could not bind"):
                server.start(timeout=1.0)


if __name__ == "__main__":
    unittest.main()
