"""Build a compact offline save-key to marker lookup from installed game data.

The game archives are opened read-only. The generated file contains only
knowledge keys and public Atlas marker identifiers, never save contents.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any

from pamt_utils import get_group_pamt, iter_pack_files, read_pack_file


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "frontend" / "public" / "data" / "marker-catalog.json"
OUTPUT_PATH = ROOT / "frontend" / "public" / "data" / "save-completion-map.json"

# Strict differential rules confirmed from two adjacent local save snapshots.
# Both MissionInfo records belong to the same Challenge_AbyssRuins_Dem_0019
# activity. The older snapshot has neither mission completed and neither marker;
# the next snapshot has both missions completed and exactly these two markers.
# Requiring the whole mission group avoids guessing which internal sub-mission
# owns which individual pin.
VERIFIED_MISSION_SOURCE_RULES = [
    {
        "missionKeys": [1001278, 1002692],
        "sourceIds": [
            "faction_quest@-3819.38:-4728.83:160",
            "faction_quest@-3628.00:-4761.05:1911",
        ],
    },
]


def _u8(data: bytes, offset: int) -> tuple[int, int]:
    return data[offset], offset + 1


def _u16(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<H", data, offset)[0], offset + 2


def _u32(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def _cstring(data: bytes, offset: int) -> tuple[str, int]:
    length, offset = _u32(data, offset)
    if length > 100_000 or offset + length > len(data):
        raise ValueError("invalid string length")
    return data[offset:offset + length].decode("utf-8", errors="replace"), offset + length


def _header_offsets(data: bytes) -> dict[int, int]:
    count16 = struct.unpack_from("<H", data, 0)[0]
    if 2 + count16 * 8 == len(data):
        count, offset = count16, 2
    else:
        count, offset = struct.unpack_from("<I", data, 0)[0], 4
    return {
        struct.unpack_from("<I", data, offset + index * 8)[0]:
        struct.unpack_from("<I", data, offset + index * 8 + 4)[0]
        for index in range(count)
    }


def _faction_node_prefix(data: bytes, offset: int, end: int) -> tuple[int, float, float] | None:
    """Read only the stable prefix through knowledge key and world position."""
    try:
        _, offset = _u32(data, offset)
        _, offset = _cstring(data, offset)
        _, offset = _u8(data, offset)
        knowledge_key, offset = _u32(data, offset)
        _, offset = _u32(data, offset)
        _, offset = _u32(data, offset)
        _, offset = _u16(data, offset)
        _, offset = _u16(data, offset)
        _, offset = _cstring(data, offset)
        child_count, offset = _u32(data, offset)
        offset += child_count * 4
        node_line_count, offset = _u32(data, offset)
        offset += node_line_count * 4
        x, y, z = struct.unpack_from("<fff", data, offset)
        if offset + 12 > end or not all(math.isfinite(value) for value in (x, y, z)):
            return None
        return knowledge_key, x, z
    except (IndexError, struct.error, UnicodeError, ValueError):
        return None


def _extract_faction_nodes(game_dir: Path) -> list[tuple[int, float, float]]:
    pack, _ = get_group_pamt(game_dir, "0008")
    wanted: dict[str, bytes] = {}
    names = {"factionnode.staticinfobody", "factionnode.staticinfoheader"}
    for full_path, filename, entry in iter_pack_files(pack):
        lower = filename.lower()
        if lower in names:
            wanted[lower] = read_pack_file(game_dir, "0008", entry, full_path, pack.encrypt_data)
    body = wanted.get("factionnode.staticinfobody")
    header = wanted.get("factionnode.staticinfoheader")
    if body is None or header is None:
        raise RuntimeError("FactionNode game tables were not found")

    index = _header_offsets(header)
    sorted_offsets = sorted(set(index.values()))
    position_by_offset = {value: index for index, value in enumerate(sorted_offsets)}
    result: list[tuple[int, float, float]] = []
    for entry_offset in index.values():
        position = position_by_offset[entry_offset]
        entry_end = sorted_offsets[position + 1] if position + 1 < len(sorted_offsets) else len(body)
        parsed = _faction_node_prefix(body, entry_offset, entry_end)
        if parsed is not None:
            result.append(parsed)
    return result


def _faction_markers(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    type_index = next(
        index for index, marker_type in enumerate(catalog["types"])
        if marker_type["id"] == "faction_node"
    )
    markers: list[dict[str, Any]] = []
    for realm, groups in catalog["realms"].items():
        for group in groups:
            if group["type"] != type_index:
                continue
            source_ids = group.get("sourceIds") or [[] for _ in group["points"]]
            for point, ids in zip(group["points"], source_ids, strict=True):
                markers.append({"realm": realm, "x": point[0], "z": point[2], "sourceIds": ids})
    return markers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    markers = _faction_markers(catalog)
    knowledge_sources: dict[int, set[str]] = defaultdict(set)
    for knowledge_key, x, z in _extract_faction_nodes(args.game_dir):
        best = min(
            markers,
            key=lambda marker: (marker["x"] - x) ** 2 + (marker["z"] - z) ** 2,
            default=None,
        )
        if best is None or (best["x"] - x) ** 2 + (best["z"] - z) ** 2 > 1.0:
            continue
        knowledge_sources[knowledge_key].update(str(value) for value in best["sourceIds"])

    payload = {
        "version": 2,
        "knowledgeSourceIds": {
            str(key): sorted(values)
            for key, values in sorted(knowledge_sources.items())
            if values
        },
        "missionSourceRules": VERIFIED_MISSION_SOURCE_RULES,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Built {len(payload['knowledgeSourceIds'])} knowledge-to-marker links")


if __name__ == "__main__":
    main()
