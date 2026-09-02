"""Settings panel."""

from __future__ import annotations

import logging
from typing import Any

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QSlider, QSpinBox, QGroupBox, QFormLayout,
)

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings configuration dialog."""

    def __init__(self, config: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # General settings
        general_group = QGroupBox("General")
        general_layout = QFormLayout()

        self.follow_cb = QCheckBox()
        self.follow_cb.setChecked(self.config.follow_player)
        general_layout.addRow("Follow Player:", self.follow_cb)

        self.rotate_cb = QCheckBox()
        self.rotate_cb.setChecked(self.config.rotate_map)
        general_layout.addRow("Rotate Map:", self.rotate_cb)

        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # Teleport settings
        teleport_group = QGroupBox("Teleport")
        teleport_layout = QFormLayout()

        self.teleport_cb = QCheckBox()
        self.teleport_cb.setChecked(self.config.teleport_enabled)
        teleport_layout.addRow("Enable Teleport:", self.teleport_cb)

        self.height_slider = QSlider(Qt.Orientation.Horizontal)
        self.height_slider.setRange(0, 2000)
        self.height_slider.setValue(int(self.config.height_boost))
        teleport_layout.addRow("Height Boost:", self.height_slider)

        teleport_group.setLayout(teleport_layout)
        layout.addWidget(teleport_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_settings(self) -> dict[str, Any]:
        """Get settings from dialog."""
        return {
            "follow_player": self.follow_cb.isChecked(),
            "rotate_map": self.rotate_cb.isChecked(),
            "teleport_enabled": self.teleport_cb.isChecked(),
            "height_boost": self.height_slider.value(),
        }
