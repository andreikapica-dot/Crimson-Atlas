"""Map projection tests."""

from __future__ import annotations

import unittest


class TestDebugProjection(unittest.TestCase):
    """Test identity projection (debug map phase)."""

    def game_to_map(self, game_x: float, game_z: float) -> tuple[float, float]:
        """Debug projection: direct mapping."""
        return game_x, game_z

    def map_to_game(self, map_x: float, map_y: float) -> tuple[float, float]:
        """Debug inverse: direct mapping."""
        return map_x, map_y

    def test_origin_maps_to_origin(self) -> None:
        map_x, map_y = self.game_to_map(0.0, 0.0)
        self.assertEqual(map_x, 0.0)
        self.assertEqual(map_y, 0.0)
        game_x, game_z = self.map_to_game(map_x, map_y)
        self.assertEqual(game_x, 0.0)
        self.assertEqual(game_z, 0.0)

    def test_positive_coords(self) -> None:
        map_x, map_y = self.game_to_map(100.0, 200.0)
        self.assertEqual(map_x, 100.0)
        self.assertEqual(map_y, 200.0)
        game_x, game_z = self.map_to_game(map_x, map_y)
        self.assertEqual(game_x, 100.0)
        self.assertEqual(game_z, 200.0)

    def test_negative_coords(self) -> None:
        map_x, map_y = self.game_to_map(-500.0, -300.0)
        self.assertEqual(map_x, -500.0)
        self.assertEqual(map_y, -300.0)
        game_x, game_z = self.map_to_game(map_x, map_y)
        self.assertEqual(game_x, -500.0)
        self.assertEqual(game_z, -300.0)

    def test_round_trip(self) -> None:
        cases = [
            (0.0, 0.0),
            (100.0, 200.0),
            (-500.0, -300.0),
            (1234.5, -678.9),
            (-9668.29, 220.84),
        ]
        for gx, gz in cases:
            map_x, map_y = self.game_to_map(gx, gz)
            game_x, game_z = self.map_to_game(map_x, map_y)
            self.assertAlmostEqual(game_x, gx, places=5)
            self.assertAlmostEqual(game_z, gz, places=5)


if __name__ == "__main__":
    unittest.main()
