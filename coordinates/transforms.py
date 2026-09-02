"""Coordinate transformations between game and map spaces."""

from __future__ import annotations

import logging
from typing import Optional

from coordinates.calibration import Calibration

log = logging.getLogger(__name__)


def _det3(rows: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]) -> float:
    """Calculate 3x3 matrix determinant."""
    (a, b, c), (d, e, f), (g, h, i) = rows
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _solve_3x3(
    rows: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    values: tuple[float, float, float],
) -> Optional[tuple[float, float, float]]:
    """Solve 3x3 linear system."""
    det = _det3(rows)
    if abs(det) < 1e-12:
        return None

    mx = ((values[0], rows[0][1], rows[0][2]),
          (values[1], rows[1][1], rows[1][2]),
          (values[2], rows[2][1], rows[2][2]))
    my = ((rows[0][0], values[0], rows[0][2]),
          (rows[1][0], values[1], rows[1][2]),
          (rows[2][0], values[2], rows[2][2]))
    mz = ((rows[0][0], rows[0][1], values[0]),
          (rows[1][0], rows[1][1], values[1]),
          (rows[2][0], rows[2][1], values[2]))

    return _det3(mx) / det, _det3(my) / det, _det3(mz) / det


def build_affine_transform(cal: Calibration) -> Optional[dict[str, Any]]:
    """Build affine transform from calibration points.

    Requires >= 3 points.
    Returns transform dict or None if not possible.
    """
    if len(cal.points) < 3:
        return None

    pts = cal.points[:3]
    rows = []
    lng_vals = []
    lat_vals = []

    for pt in pts:
        rows.append((pt.game_x, pt.game_z, 1.0))
        lng_vals.append(pt.map_x)
        lat_vals.append(pt.map_y)

    lng_coeffs = _solve_3x3(tuple(rows), tuple(lng_vals))
    lat_coeffs = _solve_3x3(tuple(rows), tuple(lat_vals))

    if not lng_coeffs or not lat_coeffs:
        return None

    ax, az, ao = lng_coeffs
    bx, bz, bo = lat_coeffs

    if abs(ax * bz - az * bx) < 1e-12:
        return None

    return {
        "mode": "affine",
        "lng": lng_coeffs,
        "lat": lat_coeffs,
    }


def build_linear_transform(cal: Calibration) -> Optional[dict[str, float]]:
    """Build linear transform from 2 calibration points.

    Returns transform dict or None if not possible.
    """
    if len(cal.points) < 2:
        return None

    p0 = cal.points[0]
    p1 = cal.points[1]

    dx = p1.game_x - p0.game_x
    dz = p1.game_z - p0.game_z

    if abs(dx) < 1e-6 or abs(dz) < 1e-6:
        return {"mode": "linear", "sx": 1.0, "ox": 0.0, "sz": 1.0, "oz": 0.0}

    sx = (p1.map_x - p0.map_x) / dx
    ox = p0.map_x - p0.game_x * sx
    sz = (p1.map_y - p0.map_y) / dz
    oz = p0.map_y - p0.game_z * sz

    return {"mode": "linear", "sx": sx, "ox": ox, "sz": sz, "oz": oz}


def build_transform(cal: Calibration) -> Optional[dict[str, Any]]:
    """Build the best available transform for a calibration."""
    affine = build_affine_transform(cal)
    if affine:
        return affine
    return build_linear_transform(cal)


def game_to_map(game_x: float, game_z: float, transform: dict[str, Any]) -> Optional[tuple[float, float]]:
    """Convert game coordinates to map coordinates."""
    tx = transform
    if tx["mode"] == "affine":
        ax, az, ao = tx["lng"]
        bx, bz, bo = tx["lat"]
        map_x = game_x * ax + game_z * az + ao
        map_y = game_x * bx + game_z * bz + bo
        return map_x, map_y
    else:
        map_x = game_x * tx["sx"] + tx["ox"]
        map_y = game_z * tx["sz"] + tx["oz"]
        return map_x, map_y


def map_to_game(map_x: float, map_y: float, transform: dict[str, Any]) -> Optional[tuple[float, float]]:
    """Convert map coordinates to game coordinates (inverse transform)."""
    tx = transform
    if tx["mode"] == "affine":
        ax, az, ao = tx["lng"]
        bx, bz, bo = tx["lat"]
        det = ax * bz - az * bx
        if abs(det) < 1e-12:
            return None
        dmx = map_x - ao
        dmy = map_y - bo
        game_x = (dmx * bz - az * dmy) / det
        game_z = (ax * dmy - dmx * bx) / det
        return game_x, game_z
    else:
        sx, sz = tx["sx"], tx["sz"]
        if abs(sx) < 1e-12 or abs(sz) < 1e-12:
            return None
        game_x = (map_x - tx["ox"]) / sx
        game_z = (map_y - tx["oz"]) / sz
        return game_x, game_z


def calibration_span(cal: Calibration) -> float:
    """Calculate the maximum distance between calibration points."""
    if len(cal.points) < 2:
        return 0.0

    best = 0.0
    for i in range(len(cal.points)):
        gx0, gz0 = cal.points[i].game_x, cal.points[i].game_z
        for j in range(i + 1, len(cal.points)):
            gx1, gz1 = cal.points[j].game_x, cal.points[j].game_z
            dist = ((gx1 - gx0) ** 2 + (gz1 - gz0) ** 2) ** 0.5
            best = max(best, dist)
    return best
