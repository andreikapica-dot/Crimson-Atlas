"""Shared utilities for PAMT/PACK parsing and extraction."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterator

import lz4.block

from pycrimson._files._pamt import PackMeta, PackMetaFile, PackMetaFileCrypto, PackMetaFileCompression
from pycrimson import _crypto


def get_group_pamt(game_dir: Path, group_id: str = "0012") -> tuple[PackMeta, int]:
    """Parse group PAMT with correct CRC.

    Returns (PackMeta, expected_crc).
    """
    pamt_path = game_dir / group_id / "0.pamt"
    with open(pamt_path, "rb") as f:
        header = f.read(12)
    expected_crc = struct.unpack("<I", header[:4])[0]
    pamt = PackMeta.from_file(pamt_path, expected_crc)
    return pamt, expected_crc


def iter_pack_files(pamt: PackMeta) -> Iterator[tuple[str, str, PackMetaFile]]:
    """Iterate all files in a PackMeta with full paths."""
    for dir_path, files in pamt.directories.items():
        for file_name, file_entry in files.items():
            full_path = f"{dir_path}/{file_name}"
            yield full_path, file_name, file_entry


def read_pack_file(
    game_dir: Path,
    group_id: str,
    file_entry: PackMetaFile,
    full_path: str,
    encrypt_data: bytes,
) -> bytes:
    """Read, decrypt, and decompress a file from a PAZ pack."""
    paz_path = game_dir / group_id / f"{file_entry.chunk_id}.paz"
    with open(paz_path, "rb") as f:
        f.seek(file_entry.chunk_offset)
        data = f.read(file_entry.compressed_size)

    if file_entry.flags.crypto != PackMetaFileCrypto.NONE:
        data = _crypto.chacha20_decrypt_pack_entry(data, encrypt_data, full_path)

    if file_entry.flags.compression == PackMetaFileCompression.LZ4:
        data = lz4.block.decompress(data, uncompressed_size=file_entry.uncompressed_size)
    elif file_entry.flags.compression == PackMetaFileCompression.PARTIAL:
        pass  # Partial handling requires DDS header context

    return data
