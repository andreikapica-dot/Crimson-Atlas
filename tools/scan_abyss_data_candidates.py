"""Scan every Crimson Desert PAMT index for Abyss/world-map data candidates.

The game installation is opened read-only. Only the JSON report in the project
directory is written.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from collections import Counter
from pathlib import Path

KEYWORDS = re.compile(
    r"abyss|worldmap|world_map|stageinfo|stage_info|regioninfo|region_info|"
    r"uimaptexture|bitmapposition|"
    r"abyssgate|hyper.?space|triangle.?ring|dry.?valley|sleet.?isles|"
    r"wanderer|providence",
    re.IGNORECASE,
)


def read_trie_string(data: bytes, offset: int) -> str:
    segments: list[str] = []
    while offset != -1:
        next_offset = struct.unpack_from("<i", data, offset)[0]
        length = data[offset + 4]
        segments.append(data[offset + 5 : offset + 5 + length].decode("utf-8", errors="replace"))
        offset = next_offset
    return "".join(reversed(segments))


def parse_pamt(path: Path) -> tuple[int, list[dict[str, object]]]:
    data = path.read_bytes()
    chunk_count = struct.unpack_from("<H", data, 4)[0]
    offset = 12 + chunk_count * 12

    directory_buffer_size = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    directory_buffer = data[offset : offset + directory_buffer_size]
    offset += directory_buffer_size

    file_buffer_size = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    file_buffer = data[offset : offset + file_buffer_size]
    offset += file_buffer_size

    directory_count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    directories = []
    for _ in range(directory_count):
        _, name_offset, file_start, file_count = struct.unpack_from("<IIII", data, offset)
        directories.append(
            (read_trie_string(directory_buffer, name_offset), file_start, file_count)
        )
        offset += 16

    file_count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    files = []
    directory_index = 0
    for index in range(file_count):
        while (
            directory_index + 1 < len(directories)
            and index >= directories[directory_index][1] + directories[directory_index][2]
        ):
            directory_index += 1
        name_offset, chunk_offset, compressed_size, uncompressed_size, chunk_id, flags, _ = struct.unpack_from(
            "<IIIIHBB", data, offset
        )
        offset += 20
        directory = directories[directory_index][0] if directories else ""
        name = read_trie_string(file_buffer, name_offset)
        files.append(
            {
                "path": f"{directory}/{name}" if directory else name,
                "chunk_offset": chunk_offset,
                "compressed_size": compressed_size,
                "uncompressed_size": uncompressed_size,
                "chunk_id": chunk_id,
                "flags": flags,
            }
        )
    return directory_count, files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    matches: list[dict[str, object]] = []
    groups: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    for pamt_path in sorted(args.game_dir.glob("[0-9][0-9][0-9][0-9]/0.pamt")):
        group_id = pamt_path.parent.name
        try:
            directory_count, files = parse_pamt(pamt_path)
            group_matches = 0
            extension_counts: Counter[str] = Counter()
            for entry in files:
                internal_path = str(entry["path"])
                if not KEYWORDS.search(internal_path):
                    continue
                extension = Path(internal_path).suffix.lower()
                extension_counts[extension or "<none>"] += 1
                group_matches += 1
                matches.append(
                    {
                        "group": group_id,
                        "path": internal_path,
                        "extension": extension,
                        "uncompressed_size": entry["uncompressed_size"],
                        "compressed_size": entry["compressed_size"],
                        "chunk_id": entry["chunk_id"],
                        "chunk_offset": entry["chunk_offset"],
                        "flags": entry["flags"],
                    }
                )
            groups.append(
                {
                    "group": group_id,
                    "directories": directory_count,
                    "matches": group_matches,
                    "extensions": dict(extension_counts.most_common()),
                }
            )
        except Exception as exc:
            errors.append({"group": group_id, "error": f"{type(exc).__name__}: {exc}"})

    report = {
        "game_install": str(args.game_dir),
        "game_install_access": "read_only",
        "keywords": KEYWORDS.pattern,
        "groups": groups,
        "match_count": len(matches),
        "matches": matches,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"match_count": len(matches), "groups": groups, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
