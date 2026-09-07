"""Build a transparent raster tile pyramid for the Abyss island artwork.

The source images and their exact map bounds stay in the public manifest.  A
separate tile pyramid avoids MapLibre style reload races while preserving the
original PNG files for future calibration.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image


TILE_SIZE = 512
MAX_ZOOM = 4
ROOT = Path(__file__).resolve().parents[1]
ISLAND_DIR = ROOT / "frontend" / "public" / "maps" / "abyss" / "islands"
MANIFEST_PATH = ISLAND_DIR / "manifest.json"
OUTPUT_DIR = ROOT / "frontend" / "public" / "maps" / "abyss-islands"
MAP_SCALE = 0.026307676497790568
# The extracted knowledge images are detail overlays, not full 2048-unit
# map panels. At the old 1.0 scale they covered roughly twice the footprint
# shown by the in-game/MapGenie Abyss overview. Keep their verified anchors
# but render the artwork at half the old width and height.
ISLAND_DISPLAY_SCALE = 0.5

# Per-image placement corrections derived from live game screenshots. These
# cannot be one global offset because the UI textures use different anchors.
VERIFIED_WORLD_OFFSETS = {
    "abyssone_0002": {"x": 103.9, "z": -98.9},
    "abyssone_0009": {"x": 204.0, "z": -176.5},
}


def lng_lat_to_pixel(lng: float, lat: float, zoom: int) -> tuple[float, float]:
    world_size = TILE_SIZE * (2**zoom)
    lat_radians = math.radians(max(-85.0511287798066, min(85.0511287798066, lat)))
    return (
        ((lng + 180.0) / 360.0) * world_size,
        ((1.0 - math.asinh(math.tan(lat_radians)) / math.pi) / 2.0) * world_size,
    )


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for zoom in range(MAX_ZOOM + 1):
        tile_count = 2**zoom
        canvas_size = TILE_SIZE * tile_count
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

        for item in manifest["images"]:
            source = Image.open(ROOT / "frontend" / "public" / item["url"].lstrip("/")).convert("RGBA")
            top_left = item["coordinates"][0]
            bottom_right = item["coordinates"][2]
            left, top = lng_lat_to_pixel(top_left[0], top_left[1], zoom)
            right, bottom = lng_lat_to_pixel(bottom_right[0], bottom_right[1], zoom)
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0
            half_width = abs(right - left) * ISLAND_DISPLAY_SCALE / 2.0
            half_height = abs(bottom - top) * ISLAND_DISPLAY_SCALE / 2.0
            left, right = center_x - half_width, center_x + half_width
            top, bottom = center_y - half_height, center_y + half_height
            correction = VERIFIED_WORLD_OFFSETS.get(item["id"], {"x": 0.0, "z": 0.0})
            pixel_dx = MAP_SCALE * correction["x"] * (2**zoom)
            pixel_dy = -MAP_SCALE * correction["z"] * (2**zoom)
            left += pixel_dx
            right += pixel_dx
            top += pixel_dy
            bottom += pixel_dy
            box = (
                round(min(left, right)),
                round(min(top, bottom)),
                round(max(left, right)),
                round(max(top, bottom)),
            )
            width = max(1, box[2] - box[0])
            height = max(1, box[3] - box[1])
            resized = source.resize((width, height), Image.Resampling.LANCZOS)
            canvas.alpha_composite(resized, (box[0], box[1]))

        zoom_dir = OUTPUT_DIR / str(zoom)
        zoom_dir.mkdir(parents=True, exist_ok=True)
        for tile_y in range(tile_count):
            row_dir = zoom_dir / str(tile_y)
            row_dir.mkdir(parents=True, exist_ok=True)
            for tile_x in range(tile_count):
                tile = canvas.crop((
                    tile_x * TILE_SIZE,
                    tile_y * TILE_SIZE,
                    (tile_x + 1) * TILE_SIZE,
                    (tile_y + 1) * TILE_SIZE,
                ))
                tile.save(row_dir / f"{tile_x}.webp", "WEBP", lossless=True, method=6)

        canvas.close()

    metadata = {
        "sourceManifest": "/maps/abyss/islands/manifest.json",
        "islandGroupCount": len(manifest["images"]),
        "tileSize": TILE_SIZE,
        "minZoom": 0,
        "maxZoom": MAX_ZOOM,
        "displayScale": ISLAND_DISPLAY_SCALE,
        "verifiedWorldOffsets": VERIFIED_WORLD_OFFSETS,
    }
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Built {sum(4**z for z in range(MAX_ZOOM + 1))} tiles for {len(manifest['images'])} island groups")


if __name__ == "__main__":
    main()
