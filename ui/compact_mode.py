"""Compact overlay mode."""

from __future__ import annotations

import logging
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout

log = logging.getLogger(__name__)


class CompactOverlay(QMainWindow):
    """Compact overlay mode showing only the map."""

    def __init__(self, config: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up compact overlay UI."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.resize(240, 240)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # TODO: Add webview for map only
        self.setCentralWidget(central)
