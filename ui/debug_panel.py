"""Debug panel for raw coordinate display."""

from __future__ import annotations

import logging
from typing import Any

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QGroupBox, QFormLayout
from PyQt5.QtCore import Qt

log = logging.getLogger(__name__)


class DebugPanel(QDialog):
    """Debug panel showing raw game coordinates."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Debug — Raw Coordinates")
        self.setFixedSize(300, 200)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Position group
        pos_group = QGroupBox("Player Position")
        pos_layout = QFormLayout()

        self.x_label = QLabel("—")
        self.y_label = QLabel("—")
        self.z_label = QLabel("—")
        self.realm_label = QLabel("—")
        self.heading_label = QLabel("—")

        pos_layout.addRow("X:", self.x_label)
        pos_layout.addRow("Y:", self.y_label)
        pos_layout.addRow("Z:", self.z_label)
        pos_layout.addRow("Realm:", self.realm_label)
        pos_layout.addRow("Heading:", self.heading_label)

        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QFormLayout()

        self.status_label = QLabel("disconnected")
        self.teleport_label = QLabel("—")

        status_layout.addRow("Engine:", self.status_label)
        status_layout.addRow("Teleport:", self.teleport_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()

    def update_position(self, x: float, y: float, z: float, realm: str, heading: float | None) -> None:
        """Update position display."""
        self.x_label.setText(f"{x:.2f}")
        self.y_label.setText(f"{y:.2f}")
        self.z_label.setText(f"{z:.2f}")
        self.realm_label.setText(realm)
        self.heading_label.setText(f"{heading:.1f}°" if heading is not None else "—")

    def update_status(self, status: str, teleport_available: bool) -> None:
        """Update status display."""
        self.status_label.setText(status)
        self.teleport_label.setText("Available" if teleport_available else "Unavailable")
