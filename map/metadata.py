"""Map metadata management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class MapMetadata:
    """Metadata for a realm map."""

    id: str
    name: str
    projection: str = "crimson-atlas-world-v1"
    game_bounds: Optional[dict[str, float]] = None
    image: Optional[dict[str, Any]] = None
    calibration: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "projection": self.projection,
            "gameBounds": self.game_bounds,
            "image": self.image,
            "calibration": self.calibration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapMetadata:
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            projection=data.get("projection", "crimson-atlas-world-v1"),
            game_bounds=data.get("gameBounds"),
            image=data.get("image"),
            calibration=data.get("calibration"),
        )


def load_map_metadata(data_dir: Path, realm: str) -> Optional[MapMetadata]:
    """Load map metadata from data/maps/{realm}/metadata.json"""
    path = data_dir / "maps" / realm / "metadata.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return MapMetadata.from_dict(data)
    except Exception as e:
        log.warning("Failed to load map metadata for %s: %s", realm, e)
        return None


def save_map_metadata(data_dir: Path, metadata: MapMetadata) -> None:
    """Save map metadata to data/maps/{realm}/metadata.json"""
    path = data_dir / "maps" / metadata.id / "metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, indent=2)
