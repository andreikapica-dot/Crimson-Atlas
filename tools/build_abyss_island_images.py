"""Build the real Abyss island-image overlay from game UI assets and table positions."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from PIL import Image


TILE_SIZE = 512.0
MAP_SCALE = 0.026307676497790568
MAP_ORIGIN_X = 431.0512794162984
MAP_ORIGIN_Y = 215.5651012228959
# Game UI declares these icons at 512 map pixels. The world map uses four
# world units per UI pixel (32768 world units across an 8192-pixel chart).
ISLAND_IMAGE_WORLD_SIZE = 2048.0


def game_to_lng_lat(x: float, z: float) -> list[float]:
    pixel_x = MAP_SCALE * x + MAP_ORIGIN_X
    pixel_y = -MAP_SCALE * z + MAP_ORIGIN_Y
    normalized_x = pixel_x / TILE_SIZE
    normalized_y = pixel_y / TILE_SIZE
    longitude = normalized_x * 360.0 - 180.0
    latitude = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * normalized_y))))
    return [longitude, latitude]


def read_table_entries(blob_path: Path) -> list[tuple[int, bytes]]:
    header_path = blob_path.with_suffix(".pabgh")
    header = header_path.read_bytes()
    blob = blob_path.read_bytes()
    count = int.from_bytes(header[:2], "little")
    key_size = (len(header) - 2) // count - 4
    rows = []
    offset = 2
    for _ in range(count):
        key = int.from_bytes(header[offset:offset + key_size], "little")
        value_offset = int.from_bytes(header[offset + key_size:offset + key_size + 4], "little")
        rows.append((key, value_offset))
        offset += key_size + 4
    return [
        (key, blob[value_offset:(rows[index + 1][1] if index + 1 < len(rows) else len(blob))])
        for index, (key, value_offset) in enumerate(rows)
    ]


def decode_entry(entry: bytes) -> tuple[str, float, float, float]:
    name_size = int.from_bytes(entry[4:8], "little")
    name = entry[8:8 + name_size].decode("utf-8")
    position_offset = 8 + name_size + 1
    import struct
    x, y, z = struct.unpack_from("<3f", entry, position_offset)
    return name, x, y, z


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--textures", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    texture_files = {path.name.lower(): path for path in args.textures.rglob("*complete.dds")}
    records = []
    missing = []
    pattern = re.compile(
        r"^Knowledge_Node_(Abyssone_(?:\d{4}|End_0001)|"
        r"Abyss_(?:SteelSail|SkyPillars|StreamSky|RecordFleet|MechHeart))_ui_map_texture_3_0$",
        re.IGNORECASE,
    )
    half_size = ISLAND_IMAGE_WORLD_SIZE / 2.0
    for table_key, entry in read_table_entries(args.table):
        name, x, y, z = decode_entry(entry)
        match = pattern.match(name)
        if not match:
            continue
        node_name = match.group(1).lower()
        texture_name = f"cd_knowledgeimage_icon_knowledge_node_{node_name}_complete.dds"
        source = texture_files.get(texture_name)
        if source is None:
            missing.append({"tableKey": table_key, "name": name, "texture": texture_name})
            continue
        output_name = f"{node_name}.png"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.convert("RGBA").save(args.output_dir / output_name, optimize=True)
        west, north = game_to_lng_lat(x - half_size, z + half_size)
        east, south = game_to_lng_lat(x + half_size, z - half_size)
        records.append({
            "id": node_name,
            "url": f"/maps/abyss/islands/{output_name}",
            "worldPosition": {"x": x, "y": y, "z": z},
            "coordinates": [[west, north], [east, north], [east, south], [west, south]],
            "tableKey": table_key,
            "source": source.name,
        })

    result = {
        "source": "Crimson Desert UIMapTextureInfo plus complete Knowledge Node map textures",
        "islandGroupCount": len(records),
        "worldSizePerImage": ISLAND_IMAGE_WORLD_SIZE,
        "images": records,
        "missing": missing,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"islandGroupCount": len(records), "missing": missing}, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
