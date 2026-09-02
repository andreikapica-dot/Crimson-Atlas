"""Development launcher for Crimson Atlas.

Starts the frontend Vite dev server, waits for it to be ready, then
runs the backend main loop.  Shuts down the frontend cleanly on exit.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time

logger = logging.getLogger(__name__)


def main() -> int:
    """Launch frontend + backend for local development."""
    # Start frontend dev server
    logger.info("Starting frontend dev server...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd="frontend",
        shell=True,
    )

    try:
        logger.info("Waiting 3 seconds for frontend to start...")
        time.sleep(3)

        # Run backend main loop (blocks until Ctrl+C)
        from app.main import main as backend_main
        return backend_main()

    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down...")
        return 0
    finally:
        logger.info("Stopping frontend dev server...")
        frontend.send_signal(signal.CTRL_C_EVENT if sys.platform == "win32" else signal.SIGINT)
        try:
            frontend.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Frontend did not stop gracefully — terminating")
            frontend.kill()
        logger.info("Frontend stopped.")


if __name__ == "__main__":
    sys.exit(main())
