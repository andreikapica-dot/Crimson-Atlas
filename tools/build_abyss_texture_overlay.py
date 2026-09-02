"""Build transparent, georeferenced Abyss island overlays from extracted game SDFs."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


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


def make_transparent_sdf(source: Path, target: Path) -> None:
    with Image.open(source) as image:
        luminance = ImageEnhance.Contrast(image.convert("L")).enhance(1.25)
        luminance = luminance.point(lambda value: 0 if value < 7 else value)
        glow = luminance.filter(ImageFilter.GaussianBlur(0.45))
        colored = Image.new("RGBA", luminance.size, (225, 240, 234, 0))
        colored.putalpha(glow)
        target.parent.mkdir(parents=True, exist_ok=True)
        colored.save(target, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--placement", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    placement = json.loads(args.placement.read_text(encoding="utf-8"))
    textures = json.loads(args.textures.read_text(encoding="utf-8"))
    active = {record["id"]: record for record in placement["records"]}
    texture_by_id = {}
    for record in textures["records"]:
        match = re.search(r"abyss_(\d{4})_sdf", record["name"], re.I)
        if match and match.group(1) in active:
            texture_by_id[match.group(1)] = record

    images = []
    for identifier in sorted(texture_by_id):
        record = active[identifier]
        texture = texture_by_id[identifier]
        filename = f"abyss_island_{identifier}.png"
        make_transparent_sdf(Path(texture["png_path"]), args.output_dir / filename)
        bounds = record["bounds"]
        west, north = game_to_lng_lat(bounds["minX"], bounds["maxZ"])
        east, south = game_to_lng_lat(bounds["maxX"], bounds["minZ"])
        images.append({
            "id": identifier,
            "url": f"/maps/abyss/island-images/{filename}",
            "coordinates": [
                [west, north],
                [east, north],
                [east, south],
                [west, south],
            ],
            "source": texture["internal_path"],
        })

    result = {
        "activeIslandCount": len(active),
        "gameTextureCount": len(images),
        "fallbackIslandCount": len(active) - len(images),
        "images": images,
        "note": "Game SDF artwork is used when present; every other active island remains visible via exact-bounds fallback geometry.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("activeIslandCount", "gameTextureCount", "fallbackIslandCount")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
