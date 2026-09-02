"""Search service for POIs and waypoints."""

from __future__ import annotations

import logging
from typing import Any

from data.poi_database import POIDatabase

log = logging.getLogger(__name__)


class SearchService:
    """Provides search functionality for POIs and waypoints."""

    def __init__(self, poi_database: POIDatabase) -> None:
        self.poi_database = poi_database

    def search_pois(self, query: str, realm: str | None = None) -> list[Any]:
        """Search POIs by name.

        Args:
            query: Search query string
            realm: Optional realm filter

        Returns:
            List of matching POIs
        """
        query_lower = query.lower()
        pois = self.poi_database.get_pois(realm=realm)
        return [p for p in pois if query_lower in p.name.lower()]

    def search_waypoints(self, query: str, waypoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Search waypoints by name.

        Args:
            query: Search query string
            waypoints: List of waypoint dicts

        Returns:
            List of matching waypoints
        """
        query_lower = query.lower()
        return [w for w in waypoints if query_lower in w.get("name", "").lower()]
