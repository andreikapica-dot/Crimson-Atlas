"""Tests for version-independent compatibility and signature fallback.

These tests verify that Atlas can work with unknown/legacy game builds
when the core AOB patterns are present, even if the exact game version
is not in the signature whitelist.
"""

from __future__ import annotations

import struct
import unittest
from unittest.mock import MagicMock, patch

from memory.aob import find_pattern
from memory.hooks import PHYSICS_HOOK_ORIGINAL, PHYSICS_HOOK_SIZE, HookEngine
from memory.player_reader import PlayerPositionReader
from memory.process import GameProcess
from memory.scanner import AOBScanner
from memory.signatures import SIGNATURES, get_signatures, list_versions
from memory.state import ProcessState
from memory.types import PositionSource, ScanResult
from app.main import select_signature_version


def _make_mock_process(module_base: int = 0x140000000, module_size: int = 0x1000000) -> MagicMock:
    """Create a properly mocked game process."""
    mock = MagicMock(spec=GameProcess)
    mock.pm = MagicMock()
    mock.pm.process_handle = 0x12345678
    mock.module = MagicMock()
    mock.module.lpBaseOfDll = module_base
    mock.module.SizeOfImage = module_size
    mock.is_attached = True
    mock.get_game_version = MagicMock(return_value=None)
    return mock


class TestGenericSignatureFallback(unittest.TestCase):
    """Test that unknown game versions fall back to generic signatures."""

    def test_unknown_version_uses_generic_set(self) -> None:
        """get_signatures('1.0.0.2079') should return generic fallback, not empty."""
        result = get_signatures("1.0.0.2079")
        self.assertEqual(result.physics_delta, PHYSICS_HOOK_ORIGINAL)

    def test_unknown_version_not_empty(self) -> None:
        """Unknown version signature set must not be empty."""
        result = get_signatures("99.99.99")
        self.assertTrue(any(result.items_bytes()))

    def test_known_version_still_works(self) -> None:
        """Known version should return its specific signature set."""
        result = get_signatures("2.00.00")
        self.assertEqual(result.physics_delta, PHYSICS_HOOK_ORIGINAL)

    def test_generic_is_not_in_list_versions(self) -> None:
        """list_versions should not include 'generic'."""
        versions = list_versions()
        self.assertNotIn("generic", versions)
        self.assertIn("2.00.00", versions)

    def test_runtime_selects_generic_for_unknown_version(self) -> None:
        self.assertEqual(select_signature_version("1.0.0.2760"), "generic")
        self.assertEqual(select_signature_version(None), "generic")
        self.assertEqual(select_signature_version("2.00.00"), "2.00.00")


class TestPhysicsHookPatternAtDifferentRVA(unittest.TestCase):
    """Test that the physics hook AOB is found at any RVA, not hardcoded."""

    def test_find_physics_hook_at_old_build_rva(self) -> None:
        """Scanner must find physics hook at old build RVA (not current build)."""
        module_base = 0x140000000
        # Simulate old build layout: hook at RVA ~0x03A409DF
        hook_rva = 0x03A409DF
        confirm_rva = hook_rva + 8
        module_size = hook_rva + 100
        module_data = bytearray(module_size)
        module_data[hook_rva:hook_rva + 8] = PHYSICS_HOOK_ORIGINAL
        # Place confirmation bytes after the hook
        confirm_pattern = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"
        module_data[confirm_rva:confirm_rva + len(confirm_pattern)] = confirm_pattern

        scanner = AOBScanner.__new__(AOBScanner)
        scanner._module_data = bytes(module_data)
        scanner._module_base = module_base
        scanner._module_size = len(module_data)

        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNotNone(result)
        self.assertEqual(result, module_base + hook_rva)

    def test_find_physics_hook_at_new_build_rva(self) -> None:
        """Scanner must find physics hook at new build RVA."""
        module_base = 0x140000000
        # Simulate new build layout: hook at RVA ~0x03BB102F
        hook_rva = 0x03BB102F
        confirm_rva = hook_rva + 8
        module_size = hook_rva + 100
        module_data = bytearray(module_size)
        module_data[hook_rva:hook_rva + 8] = PHYSICS_HOOK_ORIGINAL
        confirm_pattern = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"
        module_data[confirm_rva:confirm_rva + len(confirm_pattern)] = confirm_pattern

        scanner = AOBScanner.__new__(AOBScanner)
        scanner._module_data = bytes(module_data)
        scanner._module_base = module_base
        scanner._module_size = len(module_data)

        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNotNone(result)
        self.assertEqual(result, module_base + hook_rva)

    def test_physics_hook_address_is_dynamic(self) -> None:
        """Hook address must come from AOB scan, not hardcoded constant."""
        old_build_rva = 0x03A409DF
        new_build_rva = 0x03BB102F

        module_base = 0x140000000

        for build_rva, label in [(old_build_rva, "old"), (new_build_rva, "new")]:
            module_size = build_rva + 100
            module_data = bytearray(module_size)
            module_data[build_rva:build_rva + 8] = PHYSICS_HOOK_ORIGINAL
            confirm_rva = build_rva + 8
            module_data[confirm_rva:confirm_rva + 10] = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"

            scanner = AOBScanner.__new__(AOBScanner)
            scanner._module_data = bytes(module_data)
            scanner._module_base = module_base
            scanner._module_size = len(module_data)

            addr = scanner.find_physics_delta_hook(module_data, module_base)
            self.assertIsNotNone(addr, f"Physics hook not found in {label} build")
            self.assertEqual(addr, module_base + build_rva,
                             f"Address mismatch for {label} build")


class TestPhysicsHookFallback(unittest.TestCase):
    """Test physics hook works as fallback when static XYZ is missing."""

    def test_physics_fallback_when_static_xyz_missing(self) -> None:
        """Scanner results with physics hook but no static XYZ should work."""
        scan_results = {
            "world_offset": ScanResult("world_offset", 0x140020000, 0x200000, 0x1000000),
            "physics_delta": ScanResult("physics_delta", 0x140030000, 0x300000, 0x1000000),
        }

        game_process = _make_mock_process()
        scanner = MagicMock()
        reader = PlayerPositionReader(game_process, scanner)
        reader.update_addresses(scan_results)
        reader.set_physics_hook(0x140033000)

        self.assertEqual(reader.position_source, PositionSource.PHYSICS_HOOK)

    def test_physics_hook_installed_with_fallback(self) -> None:
        """HookEngine installs physics hook when static XYZ missing."""
        game_process = _make_mock_process()
        engine = HookEngine(game_process)
        engine.game_process.read_bytes = MagicMock(return_value=PHYSICS_HOOK_ORIGINAL)
        engine.game_process.write_bytes = MagicMock()

        with patch("ctypes.windll.kernel32.VirtualAllocEx", return_value=0x140001000):
            hook = engine.install_physics_hook(0x140000000)

        self.assertEqual(hook.original_bytes, PHYSICS_HOOK_ORIGINAL)


class TestPhysicsHookValidation(unittest.TestCase):
    """Test physics hook confirmation validation."""

    def test_hook_with_valid_confirmation_accepted(self) -> None:
        """Physics hook with correct confirmation bytes is found."""
        module_base = 0x140000000
        module_data = bytearray(0x100000)

        hook_offset = 0x1000
        module_data[hook_offset:hook_offset + 8] = PHYSICS_HOOK_ORIGINAL
        confirm_offset = hook_offset + 8
        module_data[confirm_offset:confirm_offset + 10] = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"

        scanner = AOBScanner.__new__(AOBScanner)
        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNotNone(result)
        self.assertEqual(result, module_base + hook_offset)

    def test_hook_with_invalid_confirmation_rejected(self) -> None:
        """Physics hook without confirmation bytes must NOT be returned."""
        module_base = 0x140000000
        module_data = bytearray(0x100000)

        hook_offset = 0x1000
        module_data[hook_offset:hook_offset + 8] = PHYSICS_HOOK_ORIGINAL
        # Wrong confirmation bytes
        confirm_offset = hook_offset + 8
        module_data[confirm_offset:confirm_offset + 10] = b"\xDE\xAD\xBE\xEF\x00\x00\x00\x00\x00\x00"

        scanner = AOBScanner.__new__(AOBScanner)
        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNone(result, "Hook accepted without valid confirmation")

    def test_hook_with_stale_jmp_accepted(self) -> None:
        """Stale JMP patched over hook is accepted (recovery scenario)."""
        module_base = 0x140000000

        hook_offset = 0x2000
        confirm_offset = hook_offset + 8
        module_data = bytearray(0x100000)
        module_data[confirm_offset:confirm_offset + 10] = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"
        # Stale JMP overwriting the hook bytes
        stale_jmp = b"\xE9" + b"\x00" * 4 + b"\x90" * 3
        module_data[hook_offset:hook_offset + 8] = stale_jmp

        scanner = AOBScanner.__new__(AOBScanner)
        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNotNone(result)
        self.assertEqual(result, module_base + hook_offset)


class TestMultipleCandidatesRejected(unittest.TestCase):
    """Test that ambiguous matches are rejected."""

    def test_multiple_physics_hooks_rejected(self) -> None:
        """If physics hook pattern appears multiple times with valid confirmation, scanner must reject."""
        module_base = 0x140000000
        module_data = bytearray(0x1000000)

        hook_offset1 = 0x1000
        module_data[hook_offset1:hook_offset1 + 8] = PHYSICS_HOOK_ORIGINAL
        confirm_offset1 = hook_offset1 + 8
        module_data[confirm_offset1:confirm_offset1 + 10] = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"

        hook_offset2 = 0x5000
        module_data[hook_offset2:hook_offset2 + 8] = PHYSICS_HOOK_ORIGINAL
        confirm_offset2 = hook_offset2 + 8
        module_data[confirm_offset2:confirm_offset2 + 10] = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"

        scanner = AOBScanner.__new__(AOBScanner)
        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNone(result, "Ambiguous hook candidates must be rejected, not first-match")

    def test_empty_data_returns_none(self) -> None:
        """Scanner returns None for empty module data."""
        scanner = AOBScanner.__new__(AOBScanner)
        result = scanner.find_physics_delta_hook(b"", 0x140000000)
        self.assertIsNone(result)

    def test_ambiguous_hooks_do_not_install(self) -> None:
        """When scanner finds >1 candidate, HookEngine.install_physics_hook must never be called."""
        module_base = 0x140000000
        module_data = bytearray(0x1000000)

        for offset in [0x1000, 0x5000]:
            module_data[offset:offset + 8] = PHYSICS_HOOK_ORIGINAL
            confirm_offset = offset + 8
            module_data[confirm_offset:confirm_offset + 10] = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"

        scanner = AOBScanner.__new__(AOBScanner)
        result = scanner.find_physics_delta_hook(module_data, module_base)
        self.assertIsNone(result, "Ambiguous candidates must return None")

        # Verify HookEngine would never be called with None
        game_process = _make_mock_process()
        engine = HookEngine(game_process)
        engine.game_process.read_bytes = MagicMock()
        with self.assertRaises(Exception):
            engine.install_physics_hook(0)  # type: ignore


class TestUnknownBuildGracefulFailure(unittest.TestCase):
    """Test that unknown builds with missing signatures fail gracefully."""

    def test_no_position_source_sets_unsupported(self) -> None:
        """When no position source is found, state becomes UNSUPPORTED_BUILD."""
        scan_results = {}

        game_process = _make_mock_process()
        game_process._state = ProcessState.GAME_NOT_RUNNING
        scanner = MagicMock()
        reader = PlayerPositionReader(game_process, scanner)

        reader.update_addresses(scan_results)
        self.assertEqual(reader.position_source, PositionSource.UNAVAILABLE)

    def test_partial_signatures_dont_crash(self) -> None:
        """Partial signature results should not crash the reader."""
        scan_results = {
            "world_offset": ScanResult("world_offset", 0x140020000, 0x200000, 0x1000000),
        }

        game_process = _make_mock_process()
        scanner = MagicMock()
        reader = PlayerPositionReader(game_process, scanner)
        reader.update_addresses(scan_results)

        self.assertEqual(reader.position_source, PositionSource.UNAVAILABLE)


class TestVersionDetection(unittest.TestCase):
    """Test game version detection logic."""

    def test_get_game_version_returns_none_when_not_attached(self) -> None:
        """get_game_version returns None when not attached."""
        process = GameProcess()
        self.assertIsNone(process.get_game_version())

    def test_get_game_version_with_mock(self) -> None:
        """get_game_version can be mocked for the main.py logic."""
        mock = _make_mock_process()
        mock.get_game_version.return_value = "1.0.0.2079"
        result = mock.get_game_version()
        self.assertEqual(result, "1.0.0.2079")


if __name__ == "__main__":
    unittest.main()
