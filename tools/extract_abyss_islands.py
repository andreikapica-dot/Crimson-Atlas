"""Extract every Abyss island/stage texture and related UI metadata read-only."""

from __future__ import annotations

import argparse
import io
import json
import math
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pycrimson import _crypto
from pycrimson._context import PackageContext
from pycrimson._files._pamt import PackMeta, PackMetaFileCompression, PackMetaFileCrypto
import lz4.block

GROUP_ID = "0012"
ISLAND_DIR = "ui/texture/image/worldmapimage_abyssgate"
TEXT_PATHS = [
    "ui/xml/gamemain/play/worldmapview.css",
    "ui/xml/gamemain/play/worldmapview.html",
    "ui/xml/texture/cd_worldmap_illust_image.xml",
    "ui/xml/texture/cd_worldmap_regiontitleimage.xml",
    "ui/xml/texture/cd_worldmap_regiontitleimage_eng.xml",
]


def read_entry(context: PackageContext, pack: PackMeta, path: str, entry: object) -> bytes:
    paz_path = context._base_path / GROUP_ID / f"{entry.chunk_id}.paz"
    with paz_path.open("rb") as handle:
        handle.seek(entry.chunk_offset)
        size = entry.compressed_size if (entry.flags.is_partial or entry.flags.compression != PackMetaFileCompression.NONE) else entry.uncompressed_size
        data = handle.read(size)
    if entry.flags.crypto != PackMetaFileCrypto.NONE:
        data = _crypto.chacha20_decrypt_pack_entry(data, pack.encrypt_data, path)
    if entry.flags.compression == PackMetaFileCompression.LZ4:
        data = lz4.block.decompress(data, uncompressed_size=entry.uncompressed_size)
    if entry.flags.is_partial and path.lower().endswith(".dds") and entry.compressed_size != entry.uncompressed_size:
        data = context._handle_partial_texture(data, context._pthc.get_file_header(path))
    return data


def contact_sheet(records: list[dict[str, object]], output: Path) -> None:
    columns, cell, image_box, label = 5, 220, 180, 42
    rows = math.ceil(len(records) / columns)
    sheet = Image.new("RGB", (columns * cell, 42 + rows * (image_box + label)), "#e6e8e8")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((14, 14), f"All Abyss island/stage assets ({len(records)})", fill="black", font=font)
    for index, record in enumerate(records):
        row, col = divmod(index, columns)
        x, y = col * cell + 20, 42 + row * (image_box + label)
        with Image.open(str(record["png_path"])) as source:
            preview = source.convert("RGBA")
            background = Image.new("RGBA", preview.size, "#bcc3c6")
            background.alpha_composite(preview)
            visible = background.convert("RGB")
            visible.thumbnail((image_box, image_box), Image.Resampling.LANCZOS)
        sheet.paste(visible, (x + (image_box - visible.width) // 2, y + (image_box - visible.height) // 2))
        draw.rectangle((x, y, x + image_box, y + image_box), outline="#687074")
        draw.text((x, y + image_box + 6), str(record["name"])[:31], fill="black", font=font)
        draw.text((x, y + image_box + 22), f"{record['width']}x{record['height']} alpha={record['alpha_present']}", fill="#333", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    args = parser.parse_args()

    pamt_path = args.game_dir / GROUP_ID / "0.pamt"
    expected_crc = struct.unpack("<I", pamt_path.read_bytes()[:4])[0]
    pack = PackMeta.from_file(pamt_path, expected_crc)
    context = object.__new__(PackageContext)
    context._base_path = args.game_dir
    context._packs = {GROUP_ID: pack}
    context._paz_handle_cache = {}
    context._pack_group_whitelist = [GROUP_ID]
    context._parse_texture_header_collection()

    root = args.project_dir / "work" / "abyss_islands"
    dds_dir, png_dir, text_dir = root / "dds", root / "png", root / "ui"
    records: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    entries = sorted(pack.directories.get(ISLAND_DIR, {}).items())
    for name, entry in entries:
        internal_path = f"{ISLAND_DIR}/{name}"
        try:
            data = read_entry(context, pack, internal_path, entry)
            dds_path, png_path = dds_dir / name, png_dir / f"{Path(name).stem}.png"
            dds_path.parent.mkdir(parents=True, exist_ok=True)
            png_path.parent.mkdir(parents=True, exist_ok=True)
            dds_path.write_bytes(data)
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                width, height = image.size
                rgba = image.convert("RGBA")
                alpha_min, alpha_max = rgba.getchannel("A").getextrema()
                rgba.save(png_path, optimize=True)
            records.append({
                "name": name,
                "internal_path": internal_path,
                "width": width,
                "height": height,
                "alpha_present": alpha_min < 255,
                "alpha_min": alpha_min,
                "alpha_max": alpha_max,
                "dds_path": str(dds_path),
                "png_path": str(png_path),
            })
        except Exception as exc:
            errors.append({"path": internal_path, "error": f"{type(exc).__name__}: {exc}"})

    for internal_path in TEXT_PATHS:
        directory, name = internal_path.rsplit("/", 1)
        entry = pack.directories.get(directory, {}).get(name)
        if entry is None:
            errors.append({"path": internal_path, "error": "not found"})
            continue
        try:
            data = read_entry(context, pack, internal_path, entry)
            target = text_dir / internal_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except Exception as exc:
            errors.append({"path": internal_path, "error": f"{type(exc).__name__}: {exc}"})

    sheet = root / "abyss_islands_contact_sheet.png"
    contact_sheet(records, sheet)
    manifest = {
        "game_install": str(args.game_dir),
        "game_install_access": "read_only",
        "directory": ISLAND_DIR,
        "count": len(records),
        "records": records,
        "errors": errors,
        "contact_sheet": str(sheet),
    }
    manifest_path = args.project_dir / "diagnostics" / "abyss_island_assets.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"count": len(records), "errors": errors, "contact_sheet": str(sheet), "manifest": str(manifest_path)}, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
