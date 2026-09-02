"""Tests for physics hook installation and validation."""

from __future__ import annotations

import struct
import unittest
from unittest.mock import MagicMock, patch

from memory.hooks import (
    CAPTURE_MAGIC,
    CAPTURE_OFFSET_SEQUENCE,
    CAPTURE_OFFSET_XYZ,
    PHYSICS_HOOK_ORIGINAL,
    PHYSICS_HOOK_SIZE,
    HookEngine,
)
from memory.types import HookInfo, PositionSource
from memory.player_reader import PlayerPositionReader
from memory.process import GameProcess


def _make_mock_process() -> MagicMock:
    """Create a properly mocked game process that avoids ctypes recursion."""
    mock = MagicMock(spec=GameProcess)
    mock.pm = MagicMock()
    mock.pm.process_handle = 0x12345678
    mock.module = MagicMock()
    mock.module.lpBaseOfDll = 0x140000000
    mock.module.SizeOfImage = 0x1000000
    return mock


class TestPhysicsHookByteVerification(unittest.TestCase):
    """Test physics hook byte verification."""

    def test_rejects_wrong_bytes(self) -> None:
        """Hook installation must reject unexpected bytes."""
        engine = HookEngine(_make_mock_process())
        engine.game_process.read_bytes = MagicMock(return_value=b"\x90" * 8)

        with self.assertRaises(RuntimeError) as ctx:
            engine.install_physics_hook(0x140000000)
        self.assertIn("Unexpected bytes", str(ctx.exception))

    def test_cave_contains_one_shot_teleport_command(self) -> None:
        """Cave reads target, computes absolute delta, and clears the flag."""
        engine = HookEngine(_make_mock_process())
        cave = engine._build_physics_cave(0x140008000, 0x140001008)
        self.assertIn(b"\x0f\x10\x40\x10", cave)  # target vector
        self.assertIn(b"\x41\x0f\x5c\x45\x00", cave)  # target - current
        self.assertIn(b"\xc7\x40\x20\x00\x00\x00\x00", cave)  # clear command
        self.assertTrue(cave.endswith(b"\xff\x25\x00\x00\x00\x00" + struct.pack("<Q", 0x140001008)))

    def test_accepts_original_bytes(self) -> None:
        """Hook installation must accept correct original bytes."""
        engine = HookEngine(_make_mock_process())
        engine.game_process.read_bytes = MagicMock(return_value=PHYSICS_HOOK_ORIGINAL)
        engine.game_process.write_bytes = MagicMock()

        with patch("ctypes.windll.kernel32.VirtualAllocEx", return_value=0x140001000):
            hook = engine.install_physics_hook(0x140000000)
        self.assertEqual(hook.original_bytes, PHYSICS_HOOK_ORIGINAL)
        self.assertEqual(hook.original_size, PHYSICS_HOOK_SIZE)
        self.assertEqual(hook.capture_buffer_address, 0x140001800)

    def test_accepts_stale_jmp(self) -> None:
        """Hook installation must accept stale JMP from previous session."""
        engine = HookEngine(_make_mock_process())
        stale_jmp = b"\xE9" + b"\x00" * 4  # JMP rel32 placeholder
        engine.game_process.read_bytes = MagicMock(return_value=stale_jmp)
        engine.game_process.write_bytes = MagicMock()

        with patch("ctypes.windll.kernel32.VirtualAllocEx", return_value=0x140001000):
            hook = engine.install_physics_hook(0x140000000)
        self.assertEqual(hook.original_bytes, stale_jmp)
        self.assertEqual(hook.capture_buffer_address, 0x140001800)


class TestHookInfoLifecycle(unittest.TestCase):
    """Test HookInfo structure and lifecycle."""

    def test_hook_info_creation(self) -> None:
        """HookInfo can be created with all fields."""
        hook = HookInfo(
            address=0x140000000,
            original_size=8,
            original_bytes=b"\x0F" * 8,
            cave_address=0x140002000,
            cave_size=64,
            capture_buffer_address=0x140003000,
        )
        self.assertEqual(hook.address, 0x140000000)
        self.assertEqual(hook.original_size, 8)
        self.assertEqual(hook.cave_size, 64)
        self.assertEqual(hook.capture_buffer_address, 0x140003000)

    def test_hook_info_defaults(self) -> None:
        """HookInfo defaults are correct."""
        hook = HookInfo(
            address=0x140000000,
            original_size=8,
            original_bytes=b"\x0F" * 8,
            cave_address=0x140002000,
            cave_size=64,
        )
        self.assertEqual(hook.capture_buffer_address, 0)


class TestCaptureBufferValidation(unittest.TestCase):
    """Test capture buffer validation in player reader."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.game_process = _make_mock_process()
        self.scanner = MagicMock()
        self.reader = PlayerPositionReader(self.game_process, self.scanner)

    def test_rejects_uninitialized_buffer(self) -> None:
        """Reader must reject buffer with wrong magic."""
        self.reader.set_physics_hook(0x140003000)
        self.game_process.read_bytes = MagicMock(
            return_value=struct.pack("<I", 0xDEADBEEF)
        )
        pos = self.reader.read_position()
        self.assertFalse(pos.valid)

    def test_rejects_zero_sequence(self) -> None:
        """Reader must reject buffer with zero sequence."""
        self.reader.set_physics_hook(0x140003000)
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),  # magic OK
                struct.pack("<I", 0),              # seq = 0
            ]
        )
        pos = self.reader.read_position()
        self.assertFalse(pos.valid)

    def test_accepts_valid_capture(self) -> None:
        """Reader must accept valid captured position."""
        self.reader.set_physics_hook(0x140003000)
        x, y, z = 1234.5, 678.9, -2345.6
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),      # magic OK
                struct.pack("<I", 1),                  # seq = 1
                struct.pack("<fff", x, y, z),          # XYZ
            ]
        )
        pos = self.reader.read_position()
        self.assertTrue(pos.valid)
        self.assertAlmostEqual(pos.x, x, places=2)
        self.assertAlmostEqual(pos.y, y, places=2)
        self.assertAlmostEqual(pos.z, z, places=2)
        self.assertEqual(pos.source, PositionSource.PHYSICS_HOOK)

    def test_sequence_change_detection(self) -> None:
        """Reader must detect sequence changes."""
        self.reader.set_physics_hook(0x140003000)
        x1, y1, z1 = 100.0, 200.0, 300.0
        x2, y2, z2 = 101.0, 201.0, 301.0

        # First read — seq=1
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),
                struct.pack("<fff", x1, y1, z1),
            ]
        )
        pos1 = self.reader.read_position()
        self.assertTrue(pos1.valid)
        self.assertEqual(self.reader._last_sequence, 1)

        # Second read with same seq — should reject
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),  # same seq
                struct.pack("<fff", x1, y1, z1),
            ]
        )
        pos2 = self.reader.read_position()
        self.assertFalse(pos2.valid)  # rejected because seq unchanged

        # Third read with new seq — should accept
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 2),  # new seq
                struct.pack("<fff", x2, y2, z2),
            ]
        )
        pos3 = self.reader.read_position()
        self.assertTrue(pos3.valid)
        self.assertEqual(self.reader._last_sequence, 2)


class TestNaNInfFiltering(unittest.TestCase):
    """Test NaN and infinity filtering."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.game_process = _make_mock_process()
        self.scanner = MagicMock()
        self.reader = PlayerPositionReader(self.game_process, self.scanner)

    def test_rejects_nan(self) -> None:
        """Reader must reject NaN values."""
        self.reader.set_physics_hook(0x140003000)
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),
                struct.pack("<fff", float("nan"), 100.0, 200.0),
            ]
        )
        pos = self.reader.read_position()
        self.assertFalse(pos.valid)

    def test_rejects_inf(self) -> None:
        """Reader must reject infinity values."""
        self.reader.set_physics_hook(0x140003000)
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),
                struct.pack("<fff", 100.0, float("inf"), 200.0),
            ]
        )
        pos = self.reader.read_position()
        self.assertFalse(pos.valid)

    def test_rejects_negative_inf(self) -> None:
        """Reader must reject negative infinity values."""
        self.reader.set_physics_hook(0x140003000)
        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),
                struct.pack("<fff", 100.0, -float("inf"), 200.0),
            ]
        )
        pos = self.reader.read_position()
        self.assertFalse(pos.valid)


class TestLocalWorldOffsetCalculation(unittest.TestCase):
    """Test local + world offset to absolute calculation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.game_process = _make_mock_process()
        self.scanner = MagicMock()
        self.reader = PlayerPositionReader(self.game_process, self.scanner)

    def test_absolute_with_world_offset(self) -> None:
        """Absolute = local + world offset (X and Z)."""
        scan_results = {
            "world_offset": MagicMock(address=0x140020000),
        }
        self.reader.update_addresses(scan_results)
        self.reader.set_physics_hook(0x140003000)

        local_x, local_y, local_z = 100.0, 50.0, 200.0
        offset_x, offset_y, offset_z = -5000.0, 0.0, 3000.0

        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),
                struct.pack("<fff", local_x, local_y, local_z),
                struct.pack("<ffff", offset_x, offset_y, offset_z, 0.0),
            ]
        )

        abs_pos = self.reader.get_absolute_position()
        self.assertIsNotNone(abs_pos)
        self.assertAlmostEqual(abs_pos[0], local_x + offset_x)
        self.assertAlmostEqual(abs_pos[1], local_y + offset_y)
        self.assertAlmostEqual(abs_pos[2], local_z + offset_z)

    def test_absolute_without_world_offset(self) -> None:
        """Absolute falls back to local when no world offset."""
        scan_results = {
            "world_offset": MagicMock(address=0x140020000),
        }
        self.reader.update_addresses(scan_results)
        self.reader.set_physics_hook(0x140003000)

        local_x, local_y, local_z = 100.0, 50.0, 200.0

        self.game_process.read_bytes = MagicMock(
            side_effect=[
                struct.pack("<I", CAPTURE_MAGIC),
                struct.pack("<I", 1),
                struct.pack("<fff", local_x, local_y, local_z),
                struct.pack("<ffff", 0.0, 0.0, 0.0, 0.0),  # world offset = zeros
            ]
        )

        abs_pos = self.reader.get_absolute_position()
        self.assertIsNotNone(abs_pos)
        self.assertAlmostEqual(abs_pos[0], local_x)
        self.assertAlmostEqual(abs_pos[1], local_y)
        self.assertAlmostEqual(abs_pos[2], local_z)


class TestSourceSelection(unittest.TestCase):
    """Test position source selection logic."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.game_process = _make_mock_process()
        self.scanner = MagicMock()
        self.reader = PlayerPositionReader(self.game_process, self.scanner)

    def test_static_xyz_preferred(self) -> None:
        """Static XYZ is preferred when available."""
        scan_results = {
            "xyz_x": MagicMock(address=0x140010000),
            "xyz_y": MagicMock(address=0x140010004),
            "xyz_z": MagicMock(address=0x140010008),
            "world_offset": MagicMock(address=0x140020000),
        }
        self.reader.update_addresses(scan_results)
        self.assertEqual(self.reader.position_source, PositionSource.STATIC_XYZ)

    def test_physics_fallback_when_static_missing(self) -> None:
        """Physics hook is fallback when static XYZ missing."""
        scan_results = {
            "world_offset": MagicMock(address=0x140020000),
            "physics_delta": MagicMock(address=0x140030000),
        }
        self.reader.update_addresses(scan_results)
        self.reader.set_physics_hook(0x140003000)
        self.assertEqual(self.reader.position_source, PositionSource.PHYSICS_HOOK)

    def test_unavailable_when_no_source(self) -> None:
        """Source is UNAVAILABLE when no position source found."""
        scan_results = {
            "world_offset": MagicMock(address=0x140020000),
        }
        self.reader.update_addresses(scan_results)
        self.assertEqual(self.reader.position_source, PositionSource.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
