"""Coordinate transformation tests."""

from __future__ import annotations

import unittest
import math

from coordinates.calibration import Calibration, CalibrationPoint
from coordinates.transforms import (
    build_affine_transform,
    build_linear_transform,
    game_to_map,
    map_to_game,
    calibration_span,
)
from coordinates.world import WorldPosition, LocalPosition, detect_realm


class TestCoordinateTransforms(unittest.TestCase):
    """Test coordinate transformation functions."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.calibration = Calibration("test")
        self.calibration.add_point(CalibrationPoint(0.0, 0.0, 0.0, 0.0))
        self.calibration.add_point(CalibrationPoint(100.0, 0.0, 1.0, 0.0))
        self.calibration.add_point(CalibrationPoint(0.0, 100.0, 0.0, 1.0))

    def test_linear_transform(self) -> None:
        """Test linear transform with 2 points."""
        cal = Calibration("test")
        cal.add_point(CalibrationPoint(0.0, 0.0, 0.0, 0.0))
        cal.add_point(CalibrationPoint(100.0, 100.0, 1.0, 1.0))

        transform = build_linear_transform(cal)
        self.assertIsNotNone(transform)

        map_x, map_y = game_to_map(50.0, 50.0, transform)
        self.assertAlmostEqual(map_x, 0.5, places=5)
        self.assertAlmostEqual(map_y, 0.5, places=5)

    def test_affine_transform(self) -> None:
        """Test affine transform with 3 points."""
        transform = build_affine_transform(self.calibration)
        self.assertIsNotNone(transform)

        map_x, map_y = game_to_map(50.0, 50.0, transform)
        self.assertAlmostEqual(map_x, 0.5, places=5)
        self.assertAlmostEqual(map_y, 0.5, places=5)

    def test_affine_transform_collinear_returns_none(self) -> None:
        """Test affine transform with collinear points returns None."""
        cal = Calibration("test")
        cal.add_point(CalibrationPoint(0.0, 0.0, 0.0, 0.0))
        cal.add_point(CalibrationPoint(1.0, 1.0, 1.0, 1.0))
        cal.add_point(CalibrationPoint(2.0, 2.0, 2.0, 2.0))
        transform = build_affine_transform(cal)
        self.assertIsNone(transform)

    def test_game_to_map_with_affine(self) -> None:
        """Test game_to_map with affine transform."""
        transform = build_affine_transform(self.calibration)
        self.assertIsNotNone(transform)

        map_x, map_y = game_to_map(50.0, 50.0, transform)
        self.assertAlmostEqual(map_x, 0.5, places=5)
        self.assertAlmostEqual(map_y, 0.5, places=5)

    def test_map_to_game_with_affine(self) -> None:
        """Test map_to_game with affine transform."""
        transform = build_affine_transform(self.calibration)
        self.assertIsNotNone(transform)

        game_x, game_z = map_to_game(0.5, 0.5, transform)
        self.assertAlmostEqual(game_x, 50.0, places=5)
        self.assertAlmostEqual(game_z, 50.0, places=5)

    def test_round_trip_with_affine(self) -> None:
        """Test round-trip conversion with affine transform."""
        transform = build_affine_transform(self.calibration)
        self.assertIsNotNone(transform)

        original_x, original_z = 75.0, 25.0
        map_x, map_y = game_to_map(original_x, original_z, transform)
        game_x, game_z = map_to_game(map_x, map_y, transform)

        self.assertAlmostEqual(game_x, original_x, places=5)
        self.assertAlmostEqual(game_z, original_z, places=5)

    def test_calibration_compute_transform_3_points(self) -> None:
        """Test Calibration.compute_transform with 3 points."""
        cal = Calibration("test")
        cal.add_point(CalibrationPoint(0.0, 0.0, 0.0, 0.0))
        cal.add_point(CalibrationPoint(100.0, 0.0, 1.0, 0.0))
        cal.add_point(CalibrationPoint(0.0, 100.0, 0.0, 1.0))

        transform = cal.compute_transform()
        self.assertIsNotNone(transform)

        map_x, map_y = transform.apply(50.0, 50.0)
        self.assertAlmostEqual(map_x, 0.5, places=5)
        self.assertAlmostEqual(map_y, 0.5, places=5)

    def test_calibration_compute_residuals(self) -> None:
        """Test Calibration.compute_residuals."""
        residuals, mean_err, max_err = self.calibration.compute_residuals()
        self.assertEqual(len(residuals), 3)
        self.assertAlmostEqual(mean_err, 0.0, places=5)
        self.assertAlmostEqual(max_err, 0.0, places=5)

    def test_calibration_is_usable_with_insufficient_points(self) -> None:
        """Test Calibration.is_usable with <3 points."""
        cal = Calibration("test")
        self.assertFalse(cal.is_usable())
        cal.add_point(CalibrationPoint(0.0, 0.0, 0.0, 0.0))
        self.assertFalse(cal.is_usable())
        cal.add_point(CalibrationPoint(100.0, 0.0, 1.0, 0.0))
        self.assertFalse(cal.is_usable())

    def test_realm_detection(self) -> None:
        """Test realm detection from Y coordinate."""
        self.assertEqual(detect_realm(100.0), "pywel")
        self.assertEqual(detect_realm(1399.9), "pywel")
        self.assertEqual(detect_realm(1400.1), "abyss")
        self.assertEqual(detect_realm(0.0), "pywel")
        self.assertEqual(detect_realm(2000.0), "abyss")


class TestWorldPosition(unittest.TestCase):
    """Test world position types."""

    def test_distance_2d(self) -> None:
        """Test 2D distance calculation."""
        p1 = WorldPosition(0.0, 0.0, 0.0)
        p2 = WorldPosition(3.0, 0.0, 4.0)
        self.assertAlmostEqual(p1.distance_2d(p2), 5.0, places=5)

    def test_distance_3d(self) -> None:
        """Test 3D distance calculation."""
        p1 = WorldPosition(0.0, 0.0, 0.0)
        p2 = WorldPosition(1.0, 2.0, 2.0)
        self.assertAlmostEqual(p1.distance_3d(p2), 3.0, places=5)


if __name__ == "__main__":
    unittest.main()

