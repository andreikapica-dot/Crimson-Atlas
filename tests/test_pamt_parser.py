"""Tests for PAMT parser correctness.

Verifies:
- Flags byte parsing (low nibble = compression, high nibble = crypto)
- is_partial detection
- Extension does NOT determine encryption
- CHACHA20 is detected from flags, not extension
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from pycrimson._files._pamt import (
    PackMeta,
    PackMetaFile,
    PackMetaFileCompression,
    PackMetaFileCrypto,
    PackMetaFileFlags,
)
from pycrimson._crypto import chacha20_decrypt_pack_entry
import lz4.block

from tools.pamt_utils import get_group_pamt, iter_pack_files, read_pack_file


GAME_DIR = Path(r"G:\Steam\steamapps\common\Crimson Desert")
GROUP_ID = "0012"


class TestPackMetaFileFlags(unittest.TestCase):
    """Test PackMetaFileFlags parsing."""

    def test_low_nibble_compression_high_nibble_crypto(self):
        """Verify low nibble is compression, high nibble is crypto."""
        reader = _FakeReader([0x32])  # LZ4 (2) + CHACHA20 (3)
        flags = PackMetaFileFlags.read_from(reader)
        self.assertEqual(flags.compression, PackMetaFileCompression.LZ4)
        self.assertEqual(flags.crypto, PackMetaFileCrypto.CHACHA20)

    def test_none_compression_none_crypto(self):
        """Verify NONE+NONE parses correctly."""
        reader = _FakeReader([0x00])
        flags = PackMetaFileFlags.read_from(reader)
        self.assertEqual(flags.compression, PackMetaFileCompression.NONE)
        self.assertEqual(flags.crypto, PackMetaFileCrypto.NONE)
        self.assertFalse(flags.is_partial)

    def test_partial_compression_becomes_none(self):
        """Verify PARTIAL compression is mapped to NONE with is_partial=True."""
        reader = _FakeReader([0x01])  # PARTIAL (1) + NONE (0)
        flags = PackMetaFileFlags.read_from(reader)
        self.assertEqual(flags.compression, PackMetaFileCompression.NONE)
        self.assertTrue(flags.is_partial)

    def test_partial_with_chacha20(self):
        """Verify PARTIAL + CHACHA20 combination."""
        reader = _FakeReader([0x31])  # PARTIAL (1) + CHACHA20 (3)
        flags = PackMetaFileFlags.read_from(reader)
        self.assertEqual(flags.compression, PackMetaFileCompression.NONE)
        self.assertEqual(flags.crypto, PackMetaFileCrypto.CHACHA20)
        self.assertTrue(flags.is_partial)

    def test_all_compression_values(self):
        """Verify all compression values parse correctly."""
        for comp_val, comp_enum in [
            (0, PackMetaFileCompression.NONE),
            (1, PackMetaFileCompression.PARTIAL),
            (2, PackMetaFileCompression.LZ4),
            (3, PackMetaFileCompression.ZLIB),
            (4, PackMetaFileCompression.QUICKLZ),
        ]:
            reader = _FakeReader([comp_val])  # compression only, no crypto
            flags = PackMetaFileFlags.read_from(reader)
            if comp_val == 1:
                self.assertEqual(flags.compression, PackMetaFileCompression.NONE)
                self.assertTrue(flags.is_partial)
            else:
                self.assertEqual(flags.compression, comp_enum)
                self.assertFalse(flags.is_partial)

    def test_all_crypto_values(self):
        """Verify all crypto values parse correctly."""
        for crypto_val, crypto_enum in [
            (0, PackMetaFileCrypto.NONE),
            (1, PackMetaFileCrypto.ICE),
            (2, PackMetaFileCrypto.AES),
            (3, PackMetaFileCrypto.CHACHA20),
        ]:
            reader = _FakeReader([crypto_val << 4])  # crypto only
            flags = PackMetaFileFlags.read_from(reader)
            self.assertEqual(flags.compression, PackMetaFileCompression.NONE)
            self.assertEqual(flags.crypto, crypto_enum)


class TestExtensionDoesNotDetermineEncryption(unittest.TestCase):
    """Test that file extension does NOT determine encryption status."""

    def test_dds_can_be_unencrypted(self):
        """DDS files can have NONE crypto regardless of extension."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        dds_files = []
        for _, file_name, file_entry in iter_pack_files(pamt):
            if file_name.lower().endswith(".dds"):
                dds_files.append(file_entry)

        unencrypted_dds = [f for f in dds_files if f.flags.crypto == PackMetaFileCrypto.NONE]
        self.assertGreater(len(unencrypted_dds), 0, "Expected some DDS files to be unencrypted")

    def test_css_can_be_encrypted(self):
        """CSS files can be encrypted regardless of extension."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        encrypted_css = []
        for _, file_name, file_entry in iter_pack_files(pamt):
            if file_name.lower().endswith(".css") and file_entry.flags.crypto == PackMetaFileCrypto.CHACHA20:
                encrypted_css.append(file_name)

        self.assertGreater(len(encrypted_css), 0, "Expected some CSS files to be CHACHA20 encrypted")

    def test_xml_can_be_encrypted(self):
        """XML files can be encrypted regardless of extension."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        encrypted_xml = []
        for _, file_name, file_entry in iter_pack_files(pamt):
            if file_name.lower().endswith(".xml") and file_entry.flags.crypto == PackMetaFileCrypto.CHACHA20:
                encrypted_xml.append(file_name)

        self.assertGreater(len(encrypted_xml), 0, "Expected some XML files to be CHACHA20 encrypted")


class TestChaCha20DetectedFromFlags(unittest.TestCase):
    """Test that CHACHA20 is detected from flags, not extension."""

    def test_navigatortexture_css_is_chacha20(self):
        """navigatortexture.css should be detected as CHACHA20 from flags."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        nav_css = pamt.directories.get("ui/xml/navigator", {}).get("navigatortexture.css")
        self.assertIsNotNone(nav_css)
        self.assertEqual(nav_css.flags.crypto, PackMetaFileCrypto.CHACHA20)
        self.assertEqual(nav_css.flags.compression, PackMetaFileCompression.LZ4)

    def test_worldmap_hex_is_unencrypted(self):
        """Worldmap hex tiles should be detected as NONE from flags."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        wm_dir = pamt.directories.get("ui/texture/image/worldmap", {})
        hex_tiles = [f for _, f in wm_dir.items()]
        self.assertGreater(len(hex_tiles), 0)
        for tile in hex_tiles[:5]:
            self.assertEqual(tile.flags.crypto, PackMetaFileCrypto.NONE)
            self.assertEqual(tile.flags.compression, PackMetaFileCompression.NONE)
            self.assertTrue(tile.flags.is_partial)

    def test_decrypt_chacha20_css(self):
        """Verify we can decrypt and decompress a CHACHA20+LZ4 CSS file."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        target = "ui/xml/navigator/navigatortexture.css"
        dir_path, file_name = target.rsplit("/", 1)
        file_entry = pamt.directories[dir_path][file_name]

        data = read_pack_file(GAME_DIR, GROUP_ID, file_entry, target, pamt.encrypt_data)
        text = data.decode("utf-8", errors="replace")

        self.assertIn("textureid", text.lower())
        self.assertGreater(len(text), 100)


class TestPamtIntegration(unittest.TestCase):
    """Integration tests for PAMT parsing."""

    def test_group_0012_has_expected_structure(self):
        """Verify group 0012 has expected directories and file count."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)
        total = sum(len(files) for files in pamt.directories.values())
        self.assertGreater(total, 1000, f"Expected many files, got {total}")

        expected_dirs = [
            "ui",
            "ui/texture",
            "ui/texture/image",
            "ui/texture/image/worldmap",
            "ui/xml/navigator",
        ]
        for d in expected_dirs:
            self.assertIn(d, pamt.directories, f"Missing directory: {d}")

    def test_flags_match_known_files(self):
        """Verify known files have expected flags."""
        pamt, _ = get_group_pamt(GAME_DIR, GROUP_ID)

        known = {
            "ui/xml/navigator/navigatortexture.css": (PackMetaFileCompression.LZ4, PackMetaFileCrypto.CHACHA20),
            "ui/texture/image/worldmap/cd_worldmap_abyss_hex_sdf_32768x32768_0_0.dds": (PackMetaFileCompression.NONE, PackMetaFileCrypto.NONE),
            "ui/texture/image/commonimage/cd_image_abyss_worldmap_bg_hex_00.dds": (PackMetaFileCompression.NONE, PackMetaFileCrypto.NONE),
        }

        for target, (expected_comp, expected_crypto) in known.items():
            dir_path, file_name = target.rsplit("/", 1)
            entry = pamt.directories.get(dir_path, {}).get(file_name)
            self.assertIsNotNone(entry, f"Missing file: {target}")
            self.assertEqual(entry.flags.compression, expected_comp, f"Wrong compression for {target}")
            self.assertEqual(entry.flags.crypto, expected_crypto, f"Wrong crypto for {target}")


class _FakeReader:
    """Minimal fake reader for PackMetaFileFlags tests."""

    def __init__(self, bytes_data):
        self._data = bytes_data
        self._pos = 0

    def read_u8(self):
        val = self._data[self._pos]
        self._pos += 1
        return val


if __name__ == "__main__":
    unittest.main()
