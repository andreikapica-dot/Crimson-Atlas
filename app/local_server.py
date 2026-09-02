"""WebSocket server for local frontend communication.

Runs in a dedicated background thread with its own asyncio event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from typing import Any

import websockets

log = logging.getLogger(__name__)

_HOST = "127.0.0.1"
_PORT = 7892


class LocalServer:
    """Thread-safe WebSocket server for broadcasting position updates."""

    def __init__(self) -> None:
        self._clients: set[websockets.WebSocketServerProtocol] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._packets_broadcast = 0
        self._commands: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=64)

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------
    @property
    def client_count(self) -> int:
        """Number of currently connected clients."""
        with self._lock:
            return len(self._clients)

    @property
    def packets_broadcast(self) -> int:
        """Total number of packets broadcast since start."""
        return self._packets_broadcast

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the server in a background thread."""
        if self._running:
            log.warning("LocalServer already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the server and disconnect all clients."""
        self._running = False
        if self._loop and not self._loop.is_closed() and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread:
            self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------
    def poll_command(self) -> dict[str, Any] | None:
        """Return one pending frontend command without blocking."""
        try:
            return self._commands.get_nowait()
        except queue.Empty:
            return None

    def broadcast(self, packet: dict[str, Any]) -> None:
        """Thread-safe: send a JSON packet to all connected clients.

        Silently drops the broadcast if the event loop is not yet ready
        or no clients are connected.
        """
        if not packet or not self._loop:
            return

        message = json.dumps(packet)

        def _send() -> None:
            if not self._clients:
                return
            dead: list[websockets.WebSocketServerProtocol] = []
            for ws in list(self._clients):
                try:
                    asyncio.ensure_future(ws.send(message))
                except Exception:
                    dead.append(ws)
            if dead:
                for ws in dead:
                    self._clients.discard(ws)
                log.info("Removed %d dead client(s), %d remaining", len(dead), len(self._clients))

            self._packets_broadcast += 1

        self._loop.call_soon_threadsafe(_send)

    def broadcast_position(self, packet: dict[str, Any]) -> None:
        """Broadcast a position packet (compatibility helper)."""
        self.broadcast(packet)

    # ------------------------------------------------------------------
    # Event loop & handler
    # ------------------------------------------------------------------
    def _run_event_loop(self) -> None:
        """Entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._serve_forever())
        except Exception as exc:
            log.error("LocalServer event loop error: %s", exc)
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    async def _serve_forever(self) -> None:
        """Run the WebSocket server until stopped."""
        async with websockets.serve(
            self._handle_client,
            _HOST,
            _PORT,
            ping_interval=20,
            ping_timeout=20,
        ):
            log.info("LocalServer listening on ws://%s:%d", _HOST, _PORT)
            assert self._stop_event is not None
            await self._stop_event.wait()

    async def _handle_client(
        self,
        websocket: websockets.WebSocketServerProtocol,
    ) -> None:
        """Handle a single client connection."""
        with self._lock:
            self._clients.add(websocket)
        log.info("Client connected; total=%d", self.client_count)

        try:
            async for message in websocket:
                try:
                    command = json.loads(message)
                    if not isinstance(command, dict) or not isinstance(command.get("cmd"), str):
                        raise ValueError("command must be a JSON object with cmd")
                    try:
                        self._commands.put_nowait(command)
                    except queue.Full:
                        await websocket.send(json.dumps({
                            "type": "command_result",
                            "requestId": command.get("requestId"),
                            "ok": False,
                            "error": "Command queue is full",
                        }))
                except (json.JSONDecodeError, ValueError) as exc:
                    await websocket.send(json.dumps({
                        "type": "command_result",
                        "ok": False,
                        "error": str(exc),
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as exc:
            log.debug("Client handler error: %s", exc)
        finally:
            with self._lock:
                self._clients.discard(websocket)
            log.info("Client disconnected; total=%d", self.client_count)
