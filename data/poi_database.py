"""POI database management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class POI:
    """Point of Interest."""

    id: str
    name: str
    category: str
    game_x: float
    game_y: float
    game_z: float
    realm: str = "pywel"
    description: str = ""
    found: bool = False


@dataclass
class POICategory:
    """POI category definition."""

    id: str
    name: str
    icon: str
    color: str
    visible: bool = True


class POIDatabase:
    """Manages POI data."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._pois: dict[str, POI] = {}
        self._categories: dict[str, POICategory] = {}
        self._load_default_categories()
        self._load_pois()

    def _load_default_categories(self) -> None:
        """Load default POI categories."""
        defaults = [
            POICategory("landmark", "Landmarks", "🏛️", "#ffd060"),
            POICategory("resource", "Resources", "🪨", "#60b4ff"),
            POICategory("quest", "Quests", "📜", "#ff6060"),
            POICategory("dungeon", "Dungeons", "⚔️", "#b460ff"),
            POICategory("camp", "Camps", "⛺", "#60ff90"),
            POICategory("npc", "NPCs", "👤", "#ffb460"),
        ]
        for cat in defaults:
            self._categories[cat.id] = cat

    def _load_pois(self) -> None:
        """Load POIs from file."""
        poi_file = self.data_dir / "pois.json"
        if not poi_file.exists():
            return
        try:
            with open(poi_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for poi_data in data:
                poi = POI(**poi_data)
                self._pois[poi.id] = poi
        except Exception as e:
            log.warning("Failed to load POIs: %s", e)

    def get_pois(self, category: str | None = None, realm: str | None = None) -> list[POI]:
        """Get POIs, optionally filtered by category and realm."""
        results = list(self._pois.values())
        if category:
            results = [p for p in results if p.category == category]
        if realm:
            results = [p for p in results if p.realm == realm]
        return results

    def get_poi(self, poi_id: str) -> POI | None:
        """Get a specific POI by ID."""
        return self._pois.get(poi_id)

    def get_categories(self) -> list[POICategory]:
        """Get all POI categories."""
        return list(self._categories.values())

    def get_category(self, category_id: str) -> POICategory | None:
        """Get a specific category."""
        return self._categories.get(category_id)

    def add_poi(self, poi: POI) -> None:
        """Add a new POI."""
        self._pois[poi.id] = poi
        self._save_pois()

    def update_poi(self, poi_id: str, **kwargs: Any) -> None:
        """Update POI properties."""
        if poi_id not in self._pois:
            return
        poi = self._pois[poi_id]
        for key, value in kwargs.items():
            if hasattr(poi, key):
                setattr(poi, key, value)
        self._save_pois()

    def _save_pois(self) -> None:
        """Save POIs to file."""
        poi_file = self.data_dir / "pois.json"
        poi_file.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "game_x": p.game_x,
                "game_y": p.game_y,
                "game_z": p.game_z,
                "realm": p.realm,
                "description": p.description,
                "found": p.found,
            }
            for p in self._pois.values()
        ]
        with open(poi_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
