"""Nearby location search service."""

from __future__ import annotations

import logging
from typing import Any

from data.poi_database import POIDatabase

log = logging.getLogger(__name__)


class NearbyService:
    """Searches for nearby POIs and waypoints."""

    def __init__(self, poi_database: POIDatabase) -> None:
        self.poi_database = poi_database

    def find_nearby(
        self,
        position_x: float,
        position_z: float,
        realm: str,
        radius: float = 500.0,
        categories: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find POIs near the given position.

        Args:
            position_x: Player X coordinate
            position_z: Player Z coordinate
            realm: Current realm
            radius: Search radius in game units
            categories: Optional category filter

        Returns:
            List of nearby POIs with distance info
        """
        pois = self.poi_database.get_pois(realm=realm)
        if categories:
            pois = [p for p in pois if p.category in categories]

        results = []
        for poi in pois:
            dx = poi.game_x - position_x
            dz = poi.game_z - position_z
            dist = (dx * dx + dz * dz) ** 0.5
            if dist <= radius:
                results.append({
                    "poi": poi,
                    "distance": dist,
                })

        results.sort(key=lambda r: r["distance"])
        return results

    def find_nearest(
        self,
        position_x: float,
        position_z: float,
        realm: str,
        categories: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Find the nearest POI."""
        nearby = self.find_nearby(position_x, position_z, realm, categories=categories)
        return nearby[0] if nearby else None
