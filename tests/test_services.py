"""Service tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from services.nearby import NearbyService
from services.search import SearchService
from data.poi_database import POIDatabase, POI


class TestNearbyService(unittest.TestCase):
    """Test nearby service."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self._temp_dir = tempfile.mkdtemp()
        data_dir = Path(self._temp_dir)
        self.poi_db = POIDatabase(data_dir)
        self.nearby = NearbyService(self.poi_db)

        # Add test POIs
        self.poi_db.add_poi(POI(
            id="test1", name="Test POI 1", category="landmark",
            game_x=0.0, game_y=0.0, game_z=0.0, realm="pywel"
        ))
        self.poi_db.add_poi(POI(
            id="test2", name="Test POI 2", category="landmark",
            game_x=100.0, game_y=0.0, game_z=0.0, realm="pywel"
        ))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_find_nearby(self) -> None:
        """Test nearby search."""
        results = self.nearby.find_nearby(0.0, 0.0, "pywel", radius=200.0)
        self.assertEqual(len(results), 2)

    def test_find_nearby_out_of_range(self) -> None:
        """Test nearby search with out-of-range result."""
        results = self.nearby.find_nearby(0.0, 0.0, "pywel", radius=50.0)
        self.assertEqual(len(results), 1)


class TestSearchService(unittest.TestCase):
    """Test search service."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self._temp_dir = tempfile.mkdtemp()
        data_dir = Path(self._temp_dir)
        self.poi_db = POIDatabase(data_dir)
        self.search = SearchService(self.poi_db)

        self.poi_db.add_poi(POI(
            id="search1", name="Dragon Tower", category="landmark",
            game_x=0.0, game_y=0.0, game_z=0.0, realm="pywel"
        ))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def test_search_by_name(self) -> None:
        """Test POI search by name."""
        results = self.search.search_pois("dragon", realm="pywel")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Dragon Tower")

    def test_search_no_match(self) -> None:
        """Test POI search with no match."""
        results = self.search.search_pois("nonexistent", realm="pywel")
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
