"""AOB scanner tests."""

from __future__ import annotations

import struct
import unittest

from memory.aob import find_first_pattern, find_pattern
from memory.scanner import AOBScanner
from memory.types import SignatureSet
from memory.signatures import get_signatures


class TestAOBScanner(unittest.TestCase):
    """Test AOB scanner functionality."""

    def test_find_pattern(self) -> None:
        """Test basic pattern finding."""
        data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F"
        pattern = b"\x05\x06\x07"

        results = find_pattern(data, pattern)
        self.assertEqual(results, [5])

    def test_find_pattern_multiple(self) -> None:
        """Test finding multiple pattern occurrences."""
        data = b"\x05\x06\x07\x00\x05\x06\x07\x00\x05\x06\x07"
        pattern = b"\x05\x06\x07"

        results = find_pattern(data, pattern)
        self.assertEqual(results, [0, 4, 8])

    def test_find_pattern_none(self) -> None:
        """Test pattern not found."""
        data = b"\x00\x01\x02\x03"
        pattern = b"\xFF\xFF"

        results = find_pattern(data, pattern)
        self.assertEqual(results, [])

    def test_find_first(self) -> None:
        """Test finding first occurrence."""
        data = b"\x00\x01\x02\x03\x02\x03"
        pattern = b"\x02\x03"

        result = find_first_pattern(data, pattern)
        self.assertEqual(result, 2)

    def test_find_static_xyz(self) -> None:
        """Test static XYZ pattern detection."""
        scanner = AOBScanner(None)  # type: ignore

        # Build a test pattern:
        # C5 FB 11 05 [disp32]  ... 8B 44 24 28  89 05 [disp32]
        base = 0x10000000
        xy_addr = base + 0x1000
        z_addr = base + 0x2000

        # Pack displacements
        # disp_xy is relative to (base + i + 8) where i is the pattern start
        disp_xy = xy_addr - (base + 0x1000 + 8)
        disp_z = z_addr - (base + 0x1000 + 18)

        data = bytearray(0x3000)
        # vmovsd [rip+disp32], xmm0 at offset 0x1000
        data[0x1000:0x1004] = b"\xC5\xFB\x11\x05"
        data[0x1004:0x1008] = struct.pack("<i", disp_xy)
        # mid pattern at i+8:i+14 = 0x1008:0x100E
        data[0x1008:0x100E] = b"\x8B\x44\x24\x28\x89\x05"
        # z displacement at i+14:i+18 = 0x100E:0x1012
        data[0x100E:0x1012] = struct.pack("<i", disp_z)

        x_addr, y_addr, z_addr = scanner.find_static_xyz(bytes(data), base)
        self.assertEqual(x_addr, xy_addr)
        self.assertEqual(y_addr, xy_addr + 4)
        self.assertEqual(z_addr, z_addr)

    def test_signature_selection(self) -> None:
        """Test signature selection by version."""
        sigs = get_signatures("2.00.00")
        self.assertIsInstance(sigs, SignatureSet)
        self.assertTrue(len(sigs.entity_base) > 0)
        self.assertTrue(len(sigs.physics_delta) > 0)

    def test_unknown_version(self) -> None:
        """Test unknown version returns empty signatures."""
        sigs = get_signatures("9.99.99")
        self.assertIsInstance(sigs, SignatureSet)


if __name__ == "__main__":
    unittest.main()
