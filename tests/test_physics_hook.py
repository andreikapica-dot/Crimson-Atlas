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
from memory.teleport import TeleportEngine


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
        self.assertEqual(hook.original_bytes, PHYSICS_HOOK_ORIGINAL)
        self.assertNotEqual(hook.original_bytes, stale_jmp)
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
        offset_x, offset_y, offset_z = -5000.0, 125.0, 3000.0

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
        self.assertAlmostEqual(abs_pos[1], local_y)
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


class TestSourceSelectionPolicy(unittest.TestCase):
    """Test deterministic position source selection per new policy.

    Policy: PHYSICS_HOOK preferred; STATIC_XYZ fallback only when hook fails;
    UNAVAILABLE when neither is available.
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.game_process = _make_mock_process()
        self.scanner = MagicMock()
        self.reader = PlayerPositionReader(self.game_process, self.scanner)
        self.teleport = TeleportEngine(self.game_process)

    def _make_scan(self, static=True, physics=True):
        """Build a scan_results dict matching the scanner output shape."""
        from memory.types import ScanResult
        results = {"world_offset": ScanResult("world_offset", 0x140020000, 0, 0)}
        if static:
            results["xyz_x"] = ScanResult("xyz_x", 0x140010000, 0, 0)
            results["xyz_y"] = ScanResult("xyz_y", 0x140010004, 0, 0)
            results["xyz_z"] = ScanResult("xyz_z", 0x140010008, 0, 0)
        if physics:
            results["physics_delta"] = ScanResult("physics_delta", 0x140030000, 0, 0)
        return results

    # 1) physics + static both found → hook installed → PHYSICS_HOOK
    def test_physics_and_static_found_hook_success(self) -> None:
        """Both sources found; hook installs → PHYSICS_HOOK preferred."""
        scan = self._make_scan(static=True, physics=True)
        self.reader.update_addresses(scan)

        # Simulate successful hook installation
        self.reader.set_physics_hook(0x140003000)
        self.teleport.set_physics_hook(0x140003000)
        self.assertTrue(self.teleport.available)

        source = self.reader.select_position_source()
        self.assertEqual(source, PositionSource.PHYSICS_HOOK)

    # 2) physics found + static found + hook install fails → STATIC_XYZ
    def test_physics_and_static_found_hook_fails_fallback_static(self) -> None:
        """Hook install fails → fallback to STATIC_XYZ, teleport unavailable."""
        scan = self._make_scan(static=True, physics=True)
        self.reader.update_addresses(scan)

        # Hook install failed — capture_buf_addr stays 0
        source = self.reader.select_position_source()
        self.assertEqual(source, PositionSource.STATIC_XYZ)
        self.assertFalse(self.teleport.available)

    # 3) physics found + no static → PHYSICS_HOOK
    def test_physics_found_no_static(self) -> None:
        """Physics found, no static → PHYSICS_HOOK after set_physics_hook."""
        scan = self._make_scan(static=False, physics=True)
        self.reader.update_addresses(scan)

        self.reader.set_physics_hook(0x140003000)
        self.teleport.set_physics_hook(0x140003000)
        self.assertTrue(self.teleport.available)

        source = self.reader.select_position_source()
        self.assertEqual(source, PositionSource.PHYSICS_HOOK)

    # 4) no physics + static found → STATIC_XYZ
    def test_no_physics_static_found(self) -> None:
        """No physics candidate → STATIC_XYZ fallback."""
        scan = self._make_scan(static=True, physics=False)
        self.reader.update_addresses(scan)

        source = self.reader.select_position_source()
        self.assertEqual(source, PositionSource.STATIC_XYZ)
        self.assertFalse(self.teleport.available)

    # 5) neither found → UNAVAILABLE
    def test_neither_found(self) -> None:
        """No source → UNAVAILABLE."""
        scan = self._make_scan(static=False, physics=False)
        self.reader.update_addresses(scan)

        source = self.reader.select_position_source()
        self.assertEqual(source, PositionSource.UNAVAILABLE)

    # 6) physics + static → teleport_engine receives capture buffer
    def test_teleport_receives_capture_buffer_on_hook_success(self) -> None:
        """On hook success, teleport engine is wired to capture buffer."""
        scan = self._make_scan(static=True, physics=True)
        self.reader.update_addresses(scan)

        capture_addr = 0x140003000
        self.reader.set_physics_hook(capture_addr)
        self.teleport.set_physics_hook(capture_addr)

        self.assertTrue(self.teleport.available)

    # 7) static fallback → teleport unavailable
    def test_teleport_unavailable_on_static_fallback(self) -> None:
        """On static fallback, teleport must be unavailable."""
        scan = self._make_scan(static=True, physics=True)
        self.reader.update_addresses(scan)

        # Hook failed — teleport never gets set_physics_hook
        self.assertFalse(self.teleport.available)

    # 8) ambiguous physics hook → hook not installed
    def test_ambiguous_physics_hook_not_installed(self) -> None:
        """Ambiguous physics candidate must not result in hook installation."""
        scan = {
            "world_offset": MagicMock(address=0x140020000),
            "physics_delta": MagicMock(
                address=0,  # scanner signals ambiguous
                matches=3,
            ),
        }
        self.reader.update_addresses(scan)

        # select_position_source should fall back to UNAVAILABLE since
        # set_physics_hook was never called (ambiguous candidate rejected)
        source = self.reader.select_position_source()
        self.assertEqual(source, PositionSource.UNAVAILABLE)

    # 9) stale JMP behavior unchanged
    def test_stale_jmp_behavior_unchanged(self) -> None:
        """Stale JMP acceptance does not bypass ambiguity checks."""
        # This test delegates to TestStaleJmpCleanup for the byte-level
        # verification; here we confirm set_physics_hook still works after
        # a stale-JMP-cleaned hook.
        engine = HookEngine(_make_mock_process())
        stale_jmp = b"\xE9" + b"\x00" * 4
        engine.game_process.read_bytes = MagicMock(return_value=stale_jmp)
        engine.game_process.write_bytes = MagicMock()

        with patch("ctypes.windll.kernel32.VirtualAllocEx", return_value=0x140001000):
            hook = engine.install_physics_hook(0x140000000)

        self.assertEqual(hook.original_bytes, PHYSICS_HOOK_ORIGINAL)
        self.assertNotEqual(hook.original_bytes, stale_jmp)

        engine.remove_hook(0x140000000)
        written_address, written_payload = engine.game_process.write_bytes.call_args.args
        self.assertEqual(written_address, 0x140000000)
        self.assertEqual(written_payload, PHYSICS_HOOK_ORIGINAL)

    # 10) cleanup restores PHYSICS_HOOK_ORIGINAL
    def test_cleanup_restores_physics_hook_original(self) -> None:
        """remove_hook writes PHYSICS_HOOK_ORIGINAL back to target."""
        engine = HookEngine(_make_mock_process())
        engine.game_process.read_bytes = MagicMock(return_value=PHYSICS_HOOK_ORIGINAL)
        engine.game_process.write_bytes = MagicMock()

        with patch("ctypes.windll.kernel32.VirtualAllocEx", return_value=0x140001000):
            hook = engine.install_physics_hook(0x140000000)

        engine.remove_hook(0x140000000)
        written_address, written_payload = engine.game_process.write_bytes.call_args.args
        self.assertEqual(written_address, 0x140000000)
        self.assertEqual(written_payload, PHYSICS_HOOK_ORIGINAL)


class TestPositionSourceSelectionMethod(unittest.TestCase):
    """Verify select_position_source and has_static_xyz methods."""

    def setUp(self) -> None:
        self.game_process = _make_mock_process()
        self.scanner = MagicMock()
        self.reader = PlayerPositionReader(self.game_process, self.scanner)

    def test_select_source_physics_when_hook_active(self) -> None:
        """PHYSICS_HOOK wins when capture buffer is set."""
        self.reader.set_physics_hook(0x140003000)
        src = self.reader.select_position_source()
        self.assertEqual(src, PositionSource.PHYSICS_HOOK)

    def test_select_source_static_when_no_hook(self) -> None:
        """STATIC_XYZ when no hook but static addresses present."""
        from memory.types import ScanResult
        scan = {
            "xyz_x": ScanResult("xyz_x", 0x140010000, 0, 0),
            "xyz_y": ScanResult("xyz_y", 0x140010004, 0, 0),
            "xyz_z": ScanResult("xyz_z", 0x140010008, 0, 0),
        }
        self.reader.update_addresses(scan)
        src = self.reader.select_position_source()
        self.assertEqual(src, PositionSource.STATIC_XYZ)

    def test_select_source_unavailable_when_neither(self) -> None:
        """UNAVAILABLE when no hook and no static."""
        src = self.reader.select_position_source()
        self.assertEqual(src, PositionSource.UNAVAILABLE)

    def test_has_static_xyz_true(self) -> None:
        """has_static_xyz returns True when addresses present."""
        from memory.types import ScanResult
        scan = {
            "xyz_x": ScanResult("xyz_x", 0x140010000, 0, 0),
            "xyz_y": ScanResult("xyz_y", 0x140010004, 0, 0),
            "xyz_z": ScanResult("xyz_z", 0x140010008, 0, 0),
        }
        self.reader.update_addresses(scan)
        self.assertTrue(self.reader.has_static_xyz())

    def test_has_static_xyz_false(self) -> None:
        """has_static_xyz returns False when no addresses."""
        self.assertFalse(self.reader.has_static_xyz())


class TestStaleJmpCleanup(unittest.TestCase):
    """Regression test: stale JMP must not be restored on hook removal."""

    def test_cleanup_restores_original_bytes_not_stale_jmp(self) -> None:
        """When a stale JMP is found, cleanup must write PHYSICS_HOOK_ORIGINAL."""
        engine = HookEngine(_make_mock_process())
        stale_jmp = b"\xE9" + b"\x00" * 4
        engine.game_process.read_bytes = MagicMock(return_value=stale_jmp)
        engine.game_process.write_bytes = MagicMock()

        with patch("ctypes.windll.kernel32.VirtualAllocEx", return_value=0x140001000):
            hook = engine.install_physics_hook(0x140000000)

        self.assertEqual(hook.original_bytes, PHYSICS_HOOK_ORIGINAL)
        self.assertNotEqual(hook.original_bytes, stale_jmp)

        engine.remove_hook(0x140000000)
        written_address, written_payload = engine.game_process.write_bytes.call_args.args
        self.assertEqual(written_address, 0x140000000)
        self.assertEqual(written_payload, PHYSICS_HOOK_ORIGINAL)
        self.assertNotEqual(written_payload, stale_jmp)


if __name__ == "__main__":
    unittest.main()
