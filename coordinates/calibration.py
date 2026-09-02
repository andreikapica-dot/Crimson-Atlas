"""Coordinate calibration management."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class CalibrationPoint:
    """A single calibration point mapping game coords to map coords."""

    def __init__(self, game_x: float, game_z: float, map_x: float, map_y: float, label: str = "") -> None:
        self.game_x = game_x
        self.game_z = game_z
        self.map_x = map_x
        self.map_y = map_y
        self.label = label

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "game": [self.game_x, self.game_z],
            "map": [self.map_x, self.map_y],
        }
        if self.label:
            d["label"] = self.label
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationPoint:
        gx, gz = data["game"]
        mx, my = data["map"]
        label = data.get("label", "")
        return cls(gx, gz, mx, my, label=label)


class Calibration:
    """Coordinate calibration for a realm."""

    def __init__(self, realm: str) -> None:
        self.realm = realm
        self.points: list[CalibrationPoint] = []

    def add_point(self, point: CalibrationPoint) -> None:
        """Add a calibration point."""
        self.points.append(point)

    def compute_transform(self) -> Optional["AffineTransform"]:
        """Compute affine transform from calibration points."""
        from coordinates.affine import fit_affine, fit_affine_exact

        if len(self.points) < 2:
            return None
        if len(self.points) == 2:
            return None
        if len(self.points) == 3:
            pts = [(p.game_x, p.game_z, p.map_x, p.map_y) for p in self.points]
            return fit_affine_exact(pts)
        pts = [(p.game_x, p.game_z, p.map_x, p.map_y) for p in self.points]
        return fit_affine(pts)

    def compute_residuals(self) -> tuple[list[float], float, float]:
        """Compute residual errors for current transform.

        Returns:
            (residuals_list, mean_error, max_error)
        """
        from coordinates.affine import compute_residuals

        transform = self.compute_transform()
        if not transform or len(self.points) < 2:
            return [], 0.0, 0.0
        pts = [(p.game_x, p.game_z, p.map_x, p.map_y) for p in self.points]
        residuals = compute_residuals(pts, transform)
        if not residuals:
            return [], 0.0, 0.0
        return residuals, sum(residuals) / len(residuals), max(residuals)

    def is_usable(self) -> bool:
        """Check if calibration has enough points for a usable transform."""
        return len(self.points) >= 3

    def to_dict(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.points]

    @classmethod
    def from_dict(cls, realm: str, data: list[dict[str, Any]]) -> Calibration:
        cal = cls(realm)
        for point_data in data:
            cal.add_point(CalibrationPoint.from_dict(point_data))
        return cal


class CalibrationManager:
    """Manages calibration data for all realms."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._calibrations: dict[str, Calibration] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default calibration points."""
        # Default calibrations for known realms
        defaults = {
            "pywel": [
                {"game": [-12127.14, 7.69], "map": [-0.9052, 0.7787]},
                {"game": [-3690.79, -6117.51], "map": [-0.5555, 0.5249]},
            ],
            "abyss": [
                {"game": [-10679.20, -3686.57], "map": [-1.3022, 0.6476]},
                {"game": [-12273.09, -4988.26], "map": [-1.3517, 0.6072]},
            ],
        }
        for realm, points in defaults.items():
            cal = Calibration(realm)
            for p in points:
                cal.add_point(CalibrationPoint.from_dict(p))
            self._calibrations[realm] = cal

    def get_calibration(self, realm: str) -> Calibration:
        """Get calibration for a realm, creating default if needed."""
        if realm not in self._calibrations:
            self._calibrations[realm] = Calibration(realm)
        return self._calibrations[realm]

    def add_point(self, realm: str, game_x: float, game_z: float, map_x: float, map_y: float) -> None:
        """Add a calibration point for a realm."""
        cal = self.get_calibration(realm)
        cal.add_point(CalibrationPoint(game_x, game_z, map_x, map_y))
        self._save(realm)

    def reset(self, realm: str) -> None:
        """Reset calibration for a realm to defaults."""
        if realm in self._calibrations:
            del self._calibrations[realm]
        cal_file = self.data_dir / f"calibration_{realm}.json"
        if cal_file.exists():
            cal_file.unlink()
        self._load_defaults()

    def _save(self, realm: str) -> None:
        """Save calibration to file."""
        cal = self._calibrations.get(realm)
        if not cal:
            return
        cal_file = self.data_dir / f"calibration_{realm}.json"
        cal_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cal_file, "w", encoding="utf-8") as f:
            json.dump(cal.to_dict(), f, indent=2)

    def load(self, realm: str) -> None:
        """Load calibration from file."""
        cal_file = self.data_dir / f"calibration_{realm}.json"
        if not cal_file.exists():
            return
        try:
            with open(cal_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._calibrations[realm] = Calibration.from_dict(realm, data)
        except Exception as e:
            log.warning("Failed to load calibration for %s: %s", realm, e)

    def is_usable(self, realm: str) -> bool:
        """Check if calibration has enough points to be usable."""
        cal = self._calibrations.get(realm)
        if not cal:
            return False
        return cal.is_usable()
