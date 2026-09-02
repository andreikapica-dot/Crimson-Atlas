"""Extract top candidate map assets from Crimson Desert group 0012.

Read-only extraction. Does not modify game files.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

# Ensure tools package is importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pycrimson._files._pamt import PackMeta, PackMetaFile

from tools.pamt_utils import get_group_pamt, read_pack_file

log = logging.getLogger(__name__)


def find_game_install() -> Path | None:
    candidates = [
        Path(r"G:\Steam\steamapps\common\Crimson Desert"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Crimson Desert"),
        Path(r"C:\Program Files\Steam\steamapps\common\Crimson Desert"),
        Path(r"C:\Games\Crimson Desert"),
        Path(r"D:\Games\Crimson Desert"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# Top candidate map assets to extract
MAP_ASSET_CANDIDATES: List[str] = [
    # Backgrounds and fog
    "ui/texture/image/commonimage/cd_image_abyss_worldmap_bg_hex_00.dds",
    "ui/texture/image/commonimage/cd_image_worldmap_crime_fog_00.dds",
    # Minimaps
    "ui/texture/image/playguideimage/cd_playguideimage_advice_minimap.dds",
    "ui/texture/image/playguideimage/cd_playguideimage_wanted_minimap_target.dds",
    # Fog overlays
    "ui/texture/image/worldmapfog/bitmap_region.dds",
    "ui/texture/image/worldmapfog/bitmap_region_worldmap_ui.dds",
    "ui/texture/image/worldmapfog/v_bitmap_region.dds",
    "ui/texture/image/worldmapfog/v_bitmap_region_nature.dds",
    # Region title
    "ui/texture/image/worldmapregiontitle/cd_worldmap_image_crimsondesert_crime_sdf_4096x4096.dds",
    # Text/config files
    "ui/xml/navigator/navigatortexture.css",
    "ui/xml/navigator/icon_navi.xml",
    "ui/xml/navigator/navigatoreditormetadata.xml",
    "ui/inputmap.xml",
    "ui/inputmap_common.xml",
]


def extract_candidates(game_dir: Path, output_dir: Path, group_id: str = "0012") -> None:
    pamt, _ = get_group_pamt(game_dir, group_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    missing = []

    for target in MAP_ASSET_CANDIDATES:
        dir_path, file_name = target.rsplit("/", 1)
        if dir_path not in pamt.directories:
            missing.append(target)
            continue
        if file_name not in pamt.directories[dir_path]:
            missing.append(target)
            continue

        file_entry = pamt.directories[dir_path][file_name]
        try:
            data = read_pack_file(game_dir, group_id, file_entry, target, pamt.encrypt_data)
        except Exception as e:
            log.error("Failed to extract %s: %s", target, e)
            missing.append(target)
            continue

        out_path = output_dir / target
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        extracted += 1
        print(f"  Extracted: {target} ({len(data)} bytes)")

    print(f"\nExtracted {extracted} files to {output_dir}")
    if missing:
        print(f"Missing ({len(missing)}):")
        for m in missing:
            print(f"  {m}")


def extract_hex_tile_sample(game_dir: Path, output_dir: Path, group_id: str = "0012", count: int = 10) -> None:
    """Extract first N worldmap hex tiles as a sample."""
    pamt, _ = get_group_pamt(game_dir, group_id)
    wm_dir = pamt.directories.get("ui/texture/image/worldmap", {})
    items = sorted(wm_dir.items(), key=lambda x: x[0])[:count]

    out_base = output_dir / "worldmap_sample"
    out_base.mkdir(parents=True, exist_ok=True)

    for file_name, file_entry in items:
        target = f"ui/texture/image/worldmap/{file_name}"
        try:
            data = read_pack_file(game_dir, group_id, file_entry, target, pamt.encrypt_data)
            out_path = out_base / file_name
            out_path.write_bytes(data)
            print(f"  Extracted hex tile: {file_name} ({len(data)} bytes)")
        except Exception as e:
            log.error("Failed to extract %s: %s", target, e)


def extract_worldmapimage_sample(game_dir: Path, output_dir: Path, group_id: str = "0012", count: int = 5) -> None:
    """Extract first N worldmapimage files as a sample."""
    pamt, _ = get_group_pamt(game_dir, group_id)
    wm_dir = pamt.directories.get("ui/texture/image/worldmapimage", {})
    items = sorted(wm_dir.items(), key=lambda x: x[0])[:count]

    out_base = output_dir / "worldmapimage_sample"
    out_base.mkdir(parents=True, exist_ok=True)

    for file_name, file_entry in items:
        target = f"ui/texture/image/worldmapimage/{file_name}"
        try:
            data = read_pack_file(game_dir, group_id, file_entry, target, pamt.encrypt_data)
            out_path = out_base / file_name
            out_path.write_bytes(data)
            print(f"  Extracted worldmapimage: {file_name} ({len(data)} bytes)")
        except Exception as e:
            log.error("Failed to extract %s: %s", target, e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract map assets from Crimson Desert")
    parser.add_argument("--game-dir", type=Path, help="Path to game installation")
    parser.add_argument("--output-dir", type=Path, default=Path("output/map_assets"), help="Output directory")
    parser.add_argument("--group", default="0012", help="Pack group ID (default: 0012)")
    parser.add_argument("--hex-count", type=int, default=10, help="Number of hex tiles to sample")
    parser.add_argument("--image-count", type=int, default=5, help="Number of worldmapimages to sample")
    args = parser.parse_args()

    game_dir = args.game_dir or find_game_install()
    if not game_dir:
        print("ERROR: Could not find Crimson Desert installation.", file=sys.stderr)
        print("Specify with --game-dir", file=sys.stderr)
        return 1

    print(f"Game dir: {game_dir}")
    print(f"Output dir: {args.output_dir}")
    print()

    print("Extracting top candidate map assets...")
    extract_candidates(game_dir, args.output_dir, args.group)

    print("\nExtracting hex tile sample...")
    extract_hex_tile_sample(game_dir, args.output_dir, args.group, args.hex_count)

    print("\nExtracting worldmapimage sample...")
    extract_worldmapimage_sample(game_dir, args.output_dir, args.group, args.image_count)

    return 0


if __name__ == "__main__":
    sys.exit(main())
