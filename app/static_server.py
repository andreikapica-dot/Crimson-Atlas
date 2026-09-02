"""Small loopback-only server for the bundled Crimson Atlas frontend."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class StaticFrontendServer:
    def __init__(self, root: Path, host: str = "127.0.0.1", port: int = 7891) -> None:
        if not (root / "index.html").is_file():
            raise FileNotFoundError(f"Built frontend not found: {root}")
        handler = partial(_QuietHandler, directory=str(root))
        self._server = ThreadingHTTPServer((host, port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="atlas-frontend", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=3)
