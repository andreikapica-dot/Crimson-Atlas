"""Player reader tests."""

from __future__ import annotations

import unittest
import time

from memory.types import PlayerPosition, ScanResult
from memory.player_reader import PlayerPositionReader


class TestPlayerPositionReader(unittest.TestCase):
    """Test player position reader."""

    def test_position_validation(self) -> None:
        """Test position validation."""
        # Valid position
        valid = PlayerPosition(x=100.0, y=50.0, z=-200.0, timestamp=time.time(), valid=True)
        self.assertTrue(valid.x != 0.0 or valid.y != 0.0 or valid.z != 0.0)

        # Invalid position (all zeros)
        invalid = PlayerPosition(x=0.0, y=0.0, z=0.0, timestamp=time.time(), valid=False)
        self.assertFalse(invalid.valid)


class TestScanResult(unittest.TestCase):
    """Test scan result types."""

    def test_unique_match(self) -> None:
        """Test unique match detection."""
        result = ScanResult("test", 0x1000, 0x1000, 0x100000, matches=1)
        self.assertTrue(result.is_unique())

    def test_ambiguous_match(self) -> None:
        """Test ambiguous match detection."""
        result = ScanResult("test", 0x1000, 0x1000, 0x100000, matches=3)
        self.assertFalse(result.is_unique())


if __name__ == "__main__":
    unittest.main()
