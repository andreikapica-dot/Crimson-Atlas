"""Extract selected PAMT entries without modifying the game installation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import lz4.block
from pycrimson._context import PackageContext
from pycrimson._files import PackTextureHeaderCollection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    pattern = re.compile(args.pattern, re.IGNORECASE)
    report = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = [entry for entry in report["matches"] if pattern.search(entry["path"])]
    results = []
    errors = []
    partial_context = object.__new__(PackageContext)
    partial_context._pthc = PackTextureHeaderCollection.from_file(args.game_dir / "meta" / "0.pathc")

    for entry in selected:
        group = entry["group"]
        internal_path = entry["path"]
        try:
            flags = int(entry["flags"])
            compression, crypto = flags & 0xF, flags >> 4
            if crypto:
                raise ValueError(f"encrypted entry is not supported by this focused extractor (crypto={crypto})")
            paz_path = args.game_dir / group / f"{entry['chunk_id']}.paz"
            with paz_path.open("rb") as handle:
                handle.seek(int(entry["chunk_offset"]))
                data = handle.read(int(entry["compressed_size"]))
            if compression == 1 and internal_path.lower().endswith(".dds"):
                data = partial_context._handle_partial_texture(
                    data,
                    partial_context._pthc.get_file_header(internal_path),
                )
            elif compression == 2:
                data = lz4.block.decompress(data, uncompressed_size=int(entry["uncompressed_size"]))
            elif compression != 0:
                raise ValueError(f"unsupported compression={compression}")
            target = args.output_dir / group / internal_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            results.append({"group": group, "path": internal_path, "output": str(target), "size": len(data)})
        except Exception as exc:
            errors.append({"group": group, "path": internal_path, "error": f"{type(exc).__name__}: {exc}"})

    summary = {"pattern": args.pattern, "count": len(results), "results": results, "errors": errors}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "extraction_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"count": len(results), "errors": errors}, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
