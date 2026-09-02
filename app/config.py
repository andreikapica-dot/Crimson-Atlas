"""Configuration management."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Config:
    """Application configuration."""

    # Window settings
    width: int = 1280
    height: int = 820
    x: int = 0
    y: int = 0
    transparency: int = 0
    always_on_top: bool = False

    # Map settings
    follow_player: bool = True
    rotate_map: bool = False
    show_pois: bool = True
    show_waypoints: bool = True
    show_nearby: bool = True

    # Teleport settings
    teleport_enabled: bool = True
    height_boost: float = 0.0
    invulnerability_seconds: int = 10

    # Memory settings
    memory_read_rate: int = 60  # Hz
    reconnect_delay: float = 5.0  # seconds

    # Data paths
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("LOCALAPPDATA", "")) / "CD_Companion")
    poi_database: str = "pois.json"
    waypoints_file: str = "waypoints.json"
    calibration_file: str = "calibration.json"
    settings_file: str = "settings.json"
    hook_cache_file: str = "hook_cache.json"

    # Realm thresholds
    abyss_height_threshold: float = 1400.0
    abyss_default_y: float = 2400.0
    default_teleport_y: float = 1000.0

    @classmethod
    def load(cls) -> Config:
        """Load configuration from file, falling back to defaults."""
        config = cls()
        config_path = config._get_config_path()
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except Exception:
                pass
        return config

    def save(self) -> None:
        """Save configuration to file."""
        self._get_config_path().parent.mkdir(parents=True, exist_ok=True)
        data = {
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
            "transparency": self.transparency,
            "always_on_top": self.always_on_top,
            "follow_player": self.follow_player,
            "rotate_map": self.rotate_map,
            "show_pois": self.show_pois,
            "show_waypoints": self.show_waypoints,
            "show_nearby": self.show_nearby,
            "teleport_enabled": self.teleport_enabled,
            "height_boost": self.height_boost,
            "invulnerability_seconds": self.invulnerability_seconds,
        }
        with open(self._get_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _get_config_path(self) -> Path:
        return self.data_dir / self.settings_file
