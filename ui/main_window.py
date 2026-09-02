"""Main application window."""

from __future__ import annotations

import logging
import sys
from typing import Any

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with embedded map frontend."""

    def __init__(self, config: Any, server: Any) -> None:
        super().__init__()
        self.config = config
        self.server = server

        self._setup_window()
        self._setup_webview()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle("Crimson Atlas")
        self.resize(self.config.width, self.config.height)
        self.move(self.config.x, self.config.y)

        flags = Qt.WindowType.WindowStaysOnTopHint
        if not self.config.always_on_top:
            flags = Qt.WindowType.Widget
        self.setWindowFlags(flags)

    def _setup_webview(self) -> None:
        """Set up the embedded web view."""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        self.setCentralWidget(central)

        url = QUrl("http://127.0.0.1:7891")
        self.webview.load(url)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Handle window close."""
        self.config.width = self.width()
        self.config.height = self.height()
        self.config.x = self.x()
        self.config.y = self.y()
        self.config.save()
        super().closeEvent(event)
