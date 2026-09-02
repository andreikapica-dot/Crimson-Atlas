"""Affine transform fitting and application for map calibration."""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


class AffineTransform:
    """2D affine transform: map = A * game + b
    Maps (game_x, game_z) -> (map_x, map_y)
    """

    def __init__(self, a: np.ndarray, b: np.ndarray) -> None:
        self.a = a  # 2x2 matrix
        self.b = b  # 2x1 vector

    def apply(self, game_x: float, game_z: float) -> tuple[float, float]:
        g = np.array([game_x, game_z])
        result = self.a @ g + self.b
        return float(result[0]), float(result[1])

    def inverse(self) -> Optional["AffineTransform"]:
        det = float(np.linalg.det(self.a))
        if abs(det) < 1e-12:
            return None
        inv_a = np.linalg.inv(self.a)
        inv_b = -inv_a @ self.b
        return AffineTransform(inv_a, inv_b)

    def to_dict(self) -> dict:
        return {
            "a": self.a.tolist(),
            "b": self.b.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AffineTransform":
        return cls(np.array(data["a"]), np.array(data["b"]))


def fit_affine(points: list[tuple[float, float, float, float]]) -> AffineTransform:
    """Fit affine transform using least squares.

    Args:
        points: List of (game_x, game_z, map_x, map_y)

    Returns:
        AffineTransform minimizing squared error.
    """
    if len(points) < 3:
        raise ValueError("Need at least 3 points for affine fit")

    g = np.array([[p[0], p[1], 1.0] for p in points])
    mx = np.array([p[2] for p in points])
    my = np.array([p[3] for p in points])

    coeffs_x, _, _, _ = np.linalg.lstsq(g, mx, rcond=None)
    coeffs_y, _, _, _ = np.linalg.lstsq(g, my, rcond=None)

    a = np.array([[coeffs_x[0], coeffs_x[1]],
                  [coeffs_y[0], coeffs_y[1]]])
    b = np.array([coeffs_x[2], coeffs_y[2]])

    return AffineTransform(a, b)


def fit_affine_exact(points: list[tuple[float, float, float, float]]) -> AffineTransform:
    """Fit affine transform from exactly 3 points (exact solution).

    Args:
        points: Exactly 3 points as (game_x, game_z, map_x, map_y)

    Returns:
        AffineTransform passing through all 3 points exactly.
    """
    if len(points) != 3:
        raise ValueError("Exact fit requires exactly 3 points")

    gx0, gz0, mx0, my0 = points[0]
    gx1, gz1, mx1, my1 = points[1]
    gx2, gz2, mx2, my2 = points[2]

    rows = np.array([
        [gx0, gz0, 1.0],
        [gx1, gz1, 1.0],
        [gx2, gz2, 1.0],
    ])
    mx = np.array([mx0, mx1, mx2])
    my = np.array([my0, my1, my2])

    try:
        coeffs_x = np.linalg.solve(rows, mx)
        coeffs_y = np.linalg.solve(rows, my)
    except np.linalg.LinAlgError:
        raise ValueError("Points are collinear or singular")

    a = np.array([[coeffs_x[0], coeffs_x[1]],
                  [coeffs_y[0], coeffs_y[1]]])
    b = np.array([coeffs_x[2], coeffs_y[2]])

    return AffineTransform(a, b)


def compute_residuals(points: list[tuple[float, float, float, float]],
                       transform: AffineTransform) -> list[float]:
    """Compute per-point residual errors after transform.

    Args:
        points: List of (game_x, game_z, map_x, map_y)
        transform: Fitted transform

    Returns:
        List of Euclidean distances (map units) between predicted and actual map positions.
    """
    residuals = []
    for gx, gz, mx, my in points:
        pred_x, pred_y = transform.apply(gx, gz)
        error = math.sqrt((pred_x - mx) ** 2 + (pred_y - my) ** 2)
        residuals.append(error)
    return residuals
