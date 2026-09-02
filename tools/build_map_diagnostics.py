"""Build map asset diagnostics for Crimson Desert group 0012.

Scans all files, extracts encrypted text/config files, searches for
texture/reference patterns, and builds diagnostics/ui_map_references.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure tools package is importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pycrimson._files._pamt import PackMeta, PackMetaFileCrypto, PackMetaFileCompression
import lz4.block

from tools.pamt_utils import get_group_pamt, iter_pack_files, read_pack_file

log = logging.getLogger(__name__)

GAME_DIR = Path(r"G:\Steam\steamapps\common\Crimson Desert")
GROUP_ID = "0012"

TEXT_EXTENSIONS = {".xml", ".css", ".html", ".js", ".json"}

REFERENCE_KEYWORDS = [
    ".dds",
    "textureid(",
    "world",
    "map",
    "minimap",
    "abyss",
    "navigator",
    "terrain",
    "tile",
    "region",
    "background",
]

# Ranking rules for map texture candidates
RANK_RULES = [
    # (pattern, rank, reason_prefix)
    (r"worldmap.*hex", 95, "worldmap hex tile"),
    (r"abyss_worldmap_bg", 90, "worldmap background"),
    (r"worldmap.*fog", 85, "worldmap fog/overlay"),
    (r"worldmapregiontitle", 80, "worldmap region image"),
    (r"minimap", 75, "minimap"),
    (r"worldmapimage", 70, "worldmapimage"),
    (r"playguideimage.*minimap", 70, "playguideimage minimap"),
    (r"navigator.*texture", 10, "navigator texture reference"),
]

# Penalty patterns
PENALTY_PATTERNS = [
    (r"icon", -50, "icon"),
    (r"object", -50, "object"),
    (r"character", -50, "character"),
    (r"npc", -50, "npc"),
]


def rank_file(path: str, file_entry: PackMetaFile) -> tuple[int, str]:
    """Rank a file as a map texture candidate."""
    path_lower = path.lower()
    rank = 0
    reasons = []

    for pattern, value, reason in RANK_RULES:
        if re.search(pattern, path_lower):
            if value > rank:
                rank = value
            reasons.append(reason)

    for pattern, penalty, reason in PENALTY_PATTERNS:
        if re.search(pattern, path_lower):
            rank += penalty
            reasons.append(f"penalty:{reason}")

    return rank, "; ".join(reasons) if reasons else "unknown"


def extract_text_content(
    game_dir: Path,
    group_id: str,
    file_entry: PackMetaFile,
    full_path: str,
    encrypt_data: bytes,
) -> str | None:
    """Extract and decode text content from an encrypted file."""
    try:
        data = read_pack_file(game_dir, group_id, file_entry, full_path, encrypt_data)
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        log.debug("Failed to extract text from %s: %s", full_path, e)
        return None


def build_references(pamt: PackMeta, game_dir: Path, group_id: str) -> list[dict[str, Any]]:
    """Build reference list from encrypted text files."""
    references = []

    for full_path, file_name, file_entry in iter_pack_files(pamt):
        if file_entry.flags.crypto == PackMetaFileCrypto.NONE:
            continue

        ext = Path(file_name).suffix.lower()
        if ext not in TEXT_EXTENSIONS:
            continue

        text = extract_text_content(game_dir, group_id, file_entry, full_path, pamt.encrypt_data)
        if not text:
            continue

        lines = text.split("\n")
        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()
            matched_keywords = [kw for kw in REFERENCE_KEYWORDS if kw in line_lower]
            if not matched_keywords:
                continue

            ref_type = "content_reference"
            if ".dds" in line_lower:
                ref_type = "dds_reference"
            if "textureid(" in line_lower:
                ref_type = "textureid_reference"

            # Extract candidate DDS if referenced
            candidate_dds = None
            if "textureid(" in line_lower:
                m = re.search(r"textureid\(([^)]+)\)", line_lower)
                if m:
                    candidate_dds = m.group(1)

            references.append({
                "source_file": full_path,
                "type": ref_type,
                "texture_name": candidate_dds,
                "line": line_num,
                "content": line.strip()[:500],
                "candidate_dds": candidate_dds,
                "rank": 10 if "navigator" in full_path.lower() else 0,
            })

    return references


def build_map_texture_candidates(pamt: PackMeta, game_dir: Path, group_id: str) -> list[dict[str, Any]]:
    """Build ranked list of map texture candidates."""
    candidates = []

    for full_path, file_name, file_entry in iter_pack_files(pamt):
        path_lower = full_path.lower()

        # Only consider files in map-related directories or with map-related names
        if not any(kw in path_lower for kw in [
            "worldmap", "minimap", "navigator", "fog", "region", "playguide",
            "commonimage", "abyss", "terrain", "map", "tile"
        ]):
            continue

        rank, reason = rank_file(full_path, file_entry)

        # Only include files with positive rank
        if rank <= 0:
            continue

        comp_name = file_entry.flags.compression.name
        crypto_name = file_entry.flags.crypto.name

        candidates.append({
            "path": full_path,
            "chunk_id": file_entry.chunk_id,
            "offset": f"0x{file_entry.chunk_offset:x}",
            "compressed_size": file_entry.compressed_size,
            "uncompressed_size": file_entry.uncompressed_size,
            "flags": f"0x{file_entry.flags.compression.value | (file_entry.flags.crypto.value << 4):02x}",
            "compression": comp_name,
            "crypto": crypto_name,
            "is_partial": file_entry.flags.is_partial,
            "rank": rank,
            "reason": reason,
        })

    candidates.sort(key=lambda x: x["rank"], reverse=True)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Build map asset diagnostics")
    parser.add_argument("--game-dir", type=Path, default=GAME_DIR, help="Path to game installation")
    parser.add_argument("--group", default=GROUP_ID, help="Pack group ID")
    parser.add_argument("--output", type=Path, default=Path("diagnostics/ui_map_references.json"), help="Output JSON path")
    args = parser.parse_args()

    game_dir = args.game_dir
    if not game_dir.exists():
        print(f"ERROR: Game directory not found: {game_dir}", file=sys.stderr)
        return 1

    print(f"Parsing group {args.group} PAMT...")
    pamt, expected_crc = get_group_pamt(game_dir, args.group)

    total_files = sum(len(files) for files in pamt.directories.values())
    print(f"Total files: {total_files}")

    print("Building references from encrypted text files...")
    references = build_references(pamt, game_dir, args.group)
    print(f"Found {len(references)} references")

    print("Ranking map texture candidates...")
    candidates = build_map_texture_candidates(pamt, game_dir, args.group)
    print(f"Found {len(candidates)} ranked candidates")

    diagnostics = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "game_version": "2.00.00",
        "group": args.group,
        "total_files": total_files,
        "references": references,
        "map_texture_candidates": candidates[:200],  # Top 200
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, indent=2, ensure_ascii=False)

    print(f"\nDiagnostics written to {args.output}")

    # Print top 20 candidates
    print("\nTop 20 map texture candidates:")
    for i, c in enumerate(candidates[:20], 1):
        print(f"{i:3d}. [rank={c['rank']:3d}] {c['path']}")
        print(f"      {c['reason']}")
        print(f"      chunk={c['chunk_id']}, offset={c['offset']}, "
              f"comp={c['compressed_size']}->{c['uncompressed_size']}, "
              f"flags={c['flags']} ({c['compression']}, {c['crypto']}, partial={c['is_partial']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
