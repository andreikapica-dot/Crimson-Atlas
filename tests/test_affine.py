"""Affine transform tests."""

from __future__ import annotations

import unittest

from coordinates.affine import fit_affine, fit_affine_exact, compute_residuals, AffineTransform
import numpy as np


class TestExactAffine(unittest.TestCase):
    def test_identity(self) -> None:
        pts = [(0, 0, 0, 0), (1, 0, 1, 0), (0, 1, 0, 1)]
        t = fit_affine_exact(pts)
        self.assertAlmostEqual(t.apply(0, 0)[0], 0)
        self.assertAlmostEqual(t.apply(0, 0)[1], 0)
        self.assertAlmostEqual(t.apply(1, 0)[0], 1)
        self.assertAlmostEqual(t.apply(0, 1)[1], 1)

    def test_scale(self) -> None:
        pts = [(0, 0, 0, 0), (10, 0, 20, 0), (0, 10, 0, 40)]
        t = fit_affine_exact(pts)
        x, y = t.apply(5, 5)
        self.assertAlmostEqual(x, 10)
        self.assertAlmostEqual(y, 20)

    def test_rotation(self) -> None:
        pts = [(0, 0, 0, 0), (1, 0, 0, 1), (0, 1, -1, 0)]
        t = fit_affine_exact(pts)
        x, y = t.apply(1, 1)
        self.assertAlmostEqual(x, -1)
        self.assertAlmostEqual(y, 1)

    def test_collinear_raises(self) -> None:
        pts = [(0, 0, 0, 0), (1, 1, 1, 1), (2, 2, 2, 2)]
        with self.assertRaises(ValueError):
            fit_affine_exact(pts)


class TestLeastSquaresAffine(unittest.TestCase):
    def test_overdetermined(self) -> None:
        pts = [
            (0, 0, 0, 0),
            (1, 0, 1, 0),
            (0, 1, 0, 1),
            (1, 1, 1, 1),
            (2, 0, 2, 0),
        ]
        t = fit_affine(pts)
        residuals = compute_residuals(pts, t)
        for r in residuals:
            self.assertLess(r, 1e-10)

    def test_residuals_nonzero_for_noisy(self) -> None:
        pts = [
            (0, 0, 0, 0),
            (1, 0, 1.1, 0),
            (0, 1, 0, 1.1),
        ]
        t = fit_affine_exact(pts)
        residuals = compute_residuals(pts, t)
        self.assertAlmostEqual(residuals[0], 0)
        self.assertAlmostEqual(residuals[1], 0)
        self.assertAlmostEqual(residuals[2], 0)


class TestAffineRoundTrip(unittest.TestCase):
    def test_round_trip(self) -> None:
        pts = [
            (0, 0, 100, 200),
            (1000, 0, 300, 500),
            (0, 1000, 500, 200),
            (500, 500, 250, 350),
        ]
        t = fit_affine(pts)
        inv = t.inverse()
        self.assertIsNotNone(inv)
        for gx, gz, _, _ in pts:
            mx, my = t.apply(gx, gz)
            gx2, gz2 = inv.apply(mx, my)
            self.assertAlmostEqual(gx, gx2, places=5)
            self.assertAlmostEqual(gz, gz2, places=5)


class TestCalibrationSerialization(unittest.TestCase):
    def test_round_trip(self) -> None:
        a = np.array([[2, 0], [0, 3]])
        b = np.array([10, 20])
        t = AffineTransform(a, b)
        data = t.to_dict()
        t2 = AffineTransform.from_dict(data)
        self.assertTrue(np.allclose(t.a, t2.a))
        self.assertTrue(np.allclose(t.b, t2.b))
