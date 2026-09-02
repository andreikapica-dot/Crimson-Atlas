"""Build the local Abyss island overlay from read-only extracted level metadata."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from pathlib import Path


TILE_SIZE = 512.0
MAP_SCALE = 0.026307676497790568
MAP_ORIGIN_X = 431.0512794162984
MAP_ORIGIN_Y = 215.5651012228959


def game_to_lng_lat(x: float, z: float) -> list[float]:
    pixel_x = MAP_SCALE * x + MAP_ORIGIN_X
    pixel_y = -MAP_SCALE * z + MAP_ORIGIN_Y
    normalized_x = pixel_x / TILE_SIZE
    normalized_y = pixel_y / TILE_SIZE
    longitude = normalized_x * 360.0 - 180.0
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * normalized_y))))
    return [longitude, latitude]


def level_bounds(path: Path) -> tuple[float, float, float, float, float, float]:
    data = path.read_bytes()
    positions = []
    offset = 0
    while True:
        offset = data.find(b"PARC", offset)
        if offset < 0:
            break
        positions.append(offset)
        offset += 4
    if len(positions) < 3:
        raise ValueError("level has no SceneObject PARC section")
    values = struct.unpack_from("<6f", data, positions[2] - 26)
    if not (values[0] < values[3] and values[1] < values[4] and values[2] < values[5]):
        raise ValueError(f"invalid bounds: {values!r}")
    return values


def island_polygon(identifier: str, min_x: float, min_z: float, max_x: float, max_z: float) -> list[list[float]]:
    """Create a stable chart silhouette constrained by the exact level bounds."""
    center_x, center_z = (min_x + max_x) / 2.0, (min_z + max_z) / 2.0
    radius_x, radius_z = (max_x - min_x) / 2.0, (max_z - min_z) / 2.0
    seed = int(identifier)
    points = []
    point_count = 18
    for index in range(point_count):
        angle = 2.0 * math.pi * index / point_count
        variation = 0.84 + 0.12 * math.sin(seed * 0.37 + index * 2.17) + 0.04 * math.cos(index * 4.11)
        x = center_x + math.cos(angle) * radius_x * variation
        z = center_z + math.sin(angle) * radius_z * variation
        points.append(game_to_lng_lat(x, z))
    points.append(points[0])
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--geojson", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))["matches"]
    active_ids = {
        match.group(1)
        for entry in candidates
        if (match := re.search(r"abyssislandtransmitter_(\d{4})_phase00_00\.palevel$", entry["path"], re.I))
    }
    features = []
    records = []
    errors = []
    for path in sorted(args.levels.glob("abyssisland_[0-9][0-9][0-9][0-9]_phase00_00.palevel")):
        identifier = re.search(r"_(\d{4})_", path.name).group(1)
        if identifier not in active_ids:
            continue
        try:
            min_x, min_y, min_z, max_x, max_y, max_z = level_bounds(path)
            center_x, center_z = (min_x + max_x) / 2.0, (min_z + max_z) / 2.0
            record = {
                "id": identifier,
                "name": f"Остров Бездны {identifier}",
                "center": {"x": center_x, "y": (min_y + max_y) / 2.0, "z": center_z},
                "bounds": {"minX": min_x, "minY": min_y, "minZ": min_z, "maxX": max_x, "maxY": max_y, "maxZ": max_z},
                "source_level": path.name,
                "has_transmitter": True,
            }
            records.append(record)
            features.append(
                {
                    "type": "Feature",
                    "properties": {"id": identifier, "name": record["name"], "x": center_x, "z": center_z},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [island_polygon(identifier, min_x, min_z, max_x, max_z)],
                    },
                }
            )
        except Exception as exc:
            errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})

    collection = {"type": "FeatureCollection", "features": features}
    args.geojson.parent.mkdir(parents=True, exist_ok=True)
    args.geojson.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    diagnostic = {
        "source": "Crimson Desert group 0015 level bounds and transmitter levels",
        "game_install_access": "read_only",
        "active_island_count": len(records),
        "active_transmitter_ids": sorted(active_ids),
        "records": records,
        "errors": errors,
        "geometry_note": "Centers and bounds are exact game data; displayed silhouettes are bounded chart approximations.",
    }
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"active_island_count": len(records), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
