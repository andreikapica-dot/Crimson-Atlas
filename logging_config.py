"""Logging configuration for Crimson Atlas."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional


def configure_console_encoding() -> None:
    """Configure stdout/stderr for UTF-8 output on Windows.

    On legacy Windows locales (e.g. Korean CP949, Japanese CP932), the default
    console encoding cannot encode characters such as em-dash (\\u2014). Without
    reconfiguration, Unicode output causes ``UnicodeEncodeError`` and crashes
    the backend at startup. This function is defensive: it never raises.
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def setup_logging(
    log_dir: Optional[Path] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Set up logging for the application.

    Args:
        log_dir: Directory for log files. Defaults to logs/ in project root.
        console_level: Minimum level for console output.
        file_level: Minimum level for file output.

    Returns:
        Root logger for the application.
    """
    if log_dir is None:
        configured_log_dir = os.environ.get("CRIMSON_ATLAS_LOG_DIR")
        log_dir = (
            Path(configured_log_dir)
            if configured_log_dir
            else Path(__file__).resolve().parent.parent.parent / "logs"
        )
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "crimson_atlas.log"

    # Clear any existing handlers from root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="w")
    file_handler.setLevel(file_level)
    file_formatter = logging.Formatter(
        "%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("PyQt5").setLevel(logging.WARNING)

    return root_logger
