"""Inspect Crimson Desert game assets for map textures.

Uses pycrimson PAMT parser correctly:
- Reads flags from PackMetaFileFlags (low nibble = compression, high nibble = crypto)
- Decrypts CHACHA20 entries regardless of extension
- Decompresses LZ4 entries correctly
- Does NOT use file extension to determine encryption
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure tools package is importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pycrimson._files._pamt import PackMeta, PackMetaFileCrypto, PackMetaFileCompression
from pycrimson import _crypto
import lz4.block
import struct

from tools.pamt_utils import get_group_pamt, iter_pack_files, read_pack_file

log = logging.getLogger(__name__)


def find_game_install() -> Path | None:
    """Try to find Crimson Desert installation directory."""
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


def inspect_group(game_dir: Path, group_id: str = "0012") -> None:
    """Inspect a PAMT group and print file metadata."""
    pamt, expected_crc = get_group_pamt(game_dir, group_id)
    print(f"Group {group_id} PAMT (CRC=0x{expected_crc:08x})")
    print(f"Total files: {sum(len(files) for files in pamt.directories.values())}")
    print(f"Total directories: {len(pamt.directories)}")
    print()

    # Count by flags
    stats: dict[tuple[str, str], int] = {}
    for _, _, file_entry in iter_pack_files(pamt):
        key = (str(file_entry.flags.compression), str(file_entry.flags.crypto))
        stats[key] = stats.get(key, 0) + 1

    print("File stats by (compression, crypto):")
    for (comp, crypto), count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {comp:15s} {crypto:12s} {count:6d}")
    print()

    # Show map-related files
    keywords = ["worldmap", "map", "minimap", "navigator", "fog", "region", "playguide", "commonimage", "abyss", "terrain"]
    print("Map-related files:")
    for full_path, file_name, file_entry in sorted(iter_pack_files(pamt), key=lambda x: x[0]):
        path_lower = full_path.lower()
        if any(kw in path_lower for kw in keywords):
            comp = file_entry.flags.compression
            crypto = file_entry.flags.crypto
            is_partial = file_entry.flags.is_partial
            print(
                f"  {full_path} "
                f"[chunk={file_entry.chunk_id}, offset=0x{file_entry.chunk_offset:x}, "
                f"comp={file_entry.compressed_size}->{file_entry.uncompressed_size}, "
                f"flags=({comp.name}, {crypto.name}, partial={is_partial})]"
            )


def extract_sample(game_dir: Path, group_id: str = "0012") -> None:
    """Extract and verify a sample encrypted text file."""
    pamt, _ = get_group_pamt(game_dir, group_id)
    target = "ui/xml/navigator/navigatortexture.css"
    dir_path, file_name = target.rsplit("/", 1)
    file_entry = pamt.directories[dir_path][file_name]

    print(f"\nSample extraction: {target}")
    print(f"  Flags: compression={file_entry.flags.compression.name}, "
          f"crypto={file_entry.flags.crypto.name}, is_partial={file_entry.flags.is_partial}")

    data = read_pack_file(game_dir, group_id, file_entry, target, pamt.encrypt_data)
    print(f"  Extracted {len(data)} bytes")

    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    print(f"  First 5 lines:")
    for line in lines[:5]:
        print(f"    {line.rstrip()}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Inspect Crimson Desert game assets")
    parser.add_argument("--game-dir", type=Path, help="Path to game installation")
    parser.add_argument("--group", default="0012", help="Pack group ID (default: 0012)")
    parser.add_argument("--sample", action="store_true", help="Extract a sample file to verify decryption")
    args = parser.parse_args()

    game_dir = args.game_dir or find_game_install()
    if not game_dir:
        print("ERROR: Could not find Crimson Desert installation.", file=sys.stderr)
        print("Specify with --game-dir", file=sys.stderr)
        return 1

    print(f"Game dir: {game_dir}")
    print()

    inspect_group(game_dir, args.group)

    if args.sample:
        extract_sample(game_dir, args.group)

    return 0


if __name__ == "__main__":
    sys.exit(main())
