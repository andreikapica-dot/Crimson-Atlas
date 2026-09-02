"""Persistence service for waypoints, calibration, and settings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class PersistenceService:
    """Manages saving and loading of user data."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_waypoints(self) -> list[dict[str, Any]]:
        """Load saved waypoints."""
        wp_file = self.data_dir / "waypoints.json"
        if not wp_file.exists():
            return []
        try:
            with open(wp_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to load waypoints: %s", e)
            return []

    def save_waypoints(self, waypoints: list[dict[str, Any]]) -> None:
        """Save waypoints to file."""
        wp_file = self.data_dir / "waypoints.json"
        try:
            with open(wp_file, "w", encoding="utf-8") as f:
                json.dump(waypoints, f, indent=2)
        except Exception as e:
            log.warning("Failed to save waypoints: %s", e)

    def load_calibration(self, realm: str) -> list[dict[str, Any]]:
        """Load calibration points for a realm."""
        cal_file = self.data_dir / f"calibration_{realm}.json"
        if not cal_file.exists():
            return []
        try:
            with open(cal_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to load calibration for %s: %s", realm, e)
            return []

    def save_calibration(self, realm: str, calibration: list[dict[str, Any]]) -> None:
        """Save calibration points for a realm."""
        cal_file = self.data_dir / f"calibration_{realm}.json"
        try:
            with open(cal_file, "w", encoding="utf-8") as f:
                json.dump(calibration, f, indent=2)
        except Exception as e:
            log.warning("Failed to save calibration for %s: %s", realm, e)

    def load_settings(self) -> dict[str, Any]:
        """Load application settings."""
        settings_file = self.data_dir / "settings.json"
        if not settings_file.exists():
            return {}
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to load settings: %s", e)
            return {}

    def save_settings(self, settings: dict[str, Any]) -> None:
        """Save application settings."""
        settings_file = self.data_dir / "settings.json"
        try:
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            log.warning("Failed to save settings: %s", e)
