"""Reusable AOB pattern scanner with diagnostics and caching support."""

from __future__ import annotations

import logging
import struct
import traceback
from typing import Optional

from memory.aob import (
    find_first_pattern,
    find_pattern,
    log_scan_diagnostics,
    validate_address,
    AOBParseError,
)
from memory.process import GameProcess
from memory.signatures import get_signatures
from memory.types import ScanResult

log = logging.getLogger(__name__)


class AOBScanner:
    """Scans game memory for AOB patterns."""

    def __init__(self, game_process: GameProcess) -> None:
        self.game_process = game_process
        self._module_data: bytes = b""
        self._module_base: int = 0
        self._module_size: int = 0
        self._executable_ranges: list[tuple[int, int]] = []

    def read_module(self) -> tuple[bytes, int, int]:
        """Read the entire game module into memory.

        Returns (module_data, module_base, module_size).
        Also populates _executable_ranges for section validation.
        """
        if not self.game_process.is_attached or not self.game_process.module:
            raise RuntimeError("Not attached to process")

        base = self.game_process.module.lpBaseOfDll
        size = self.game_process.module.SizeOfImage

        data = bytearray(size)
        chunk_size = 0x10000  # 64KB chunks

        for offset in range(0, size, chunk_size):
            chunk_len = min(chunk_size, size - offset)
            try:
                data[offset:offset + chunk_len] = self.game_process.read_bytes(
                    base + offset, chunk_len
                )
            except Exception:
                # Zero-fill failed chunks — log but continue
                log.debug("Failed to read module chunk at offset %#x", offset)

        self._module_data = bytes(data)
        self._module_base = base
        self._module_size = size
        # Keep the parser input identical in Python and in the Cython release.
        # Cython enforces the ``bytes`` annotation at runtime and rejects the
        # mutable bytearray used while the module is being assembled.
        self._executable_ranges = self._parse_executable_sections(
            self._module_data, base
        )

        return self._module_data, base, size

    def _parse_executable_sections(self, data: bytes, base: int) -> list[tuple[int, int]]:
        """Parse PE headers to find executable section ranges.

        Returns a list of (start VA, end VA) tuples for sections
        with the executable flag set.
        """
        IMAGE_FILE_EXECUTABLE_IMAGE = 0x0002
        IMAGE_SCN_MEM_EXECUTE = 0x20000000
        ranges: list[tuple[int, int]] = []

        try:
            if len(data) < 64:
                return ranges

            e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
            if e_lfanew + 24 > len(data):
                return ranges

            magic = data[e_lfanew:e_lfanew + 4]
            if magic != b"\x50\x45\x00\x00":
                return ranges

            number_of_sections = int.from_bytes(data[e_lfanew + 6:e_lfanew + 8], "little")
            size_of_optional_header = int.from_bytes(data[e_lfanew + 20:e_lfanew + 22], "little")
            optional_header_offset = e_lfanew + 24
            section_table_offset = optional_header_offset + size_of_optional_header

            for i in range(number_of_sections):
                sec_offset = section_table_offset + i * 40
                if sec_offset + 40 > len(data):
                    break

                characteristics = int.from_bytes(data[sec_offset + 36:sec_offset + 40], "little")
                if characteristics & IMAGE_SCN_MEM_EXECUTE:
                    virtual_address = int.from_bytes(data[sec_offset + 12:sec_offset + 16], "little")
                    virtual_size = int.from_bytes(data[sec_offset + 8:sec_offset + 12], "little")
                    if virtual_size == 0:
                        virtual_size = int.from_bytes(data[sec_offset + 16:sec_offset + 20], "little")
                    if virtual_address > 0 and virtual_size > 0:
                        ranges.append(
                            (base + virtual_address, base + virtual_address + virtual_size)
                        )
                        log.debug(
                            "Executable section: VA=%#x size=%#x",
                            base + virtual_address, virtual_size,
                        )

        except Exception as e:
            log.debug("Failed to parse executable sections: %s", e)

        return ranges

    def is_in_executable_section(self, address: int) -> bool:
        """Check if an address falls within an executable PE section."""
        for start, end in self._executable_ranges:
            if start <= address < end:
                return True
        return False

    def find_static_xyz(self, data: bytes, base: int) -> tuple[int, int, int]:
        """Find static XYZ addresses via vmovsd+mov pattern.

        Pattern:
          vmovsd [rip+disp32], xmm0   (C5 FB 11 05 + disp32)
          ... 8 bytes ...
          mov eax, [rsp+28]           (8B 44 24 28)
          mov [rip+disp32], eax       (89 05 + disp32)

        Returns (x_addr, y_addr, z_addr) or (0, 0, 0) if not found.
        X and Y share the same address (XY is a vec2 written together).
        """
        prefix = b"\xC5\xFB\x11\x05"  # vmovsd [rip+disp32], xmm0
        mid = b"\x8B\x44\x24\x28\x89\x05"  # mov eax,[rsp+28] ; mov [rip+disp32],eax

        pos = 0
        while pos < len(data) - 20:
            i = data.find(prefix, pos)
            if i == -1:
                break
            if data[i + 8:i + 14] == mid:
                disp_xy = struct.unpack_from("<i", data, i + 4)[0]
                xy_addr = base + i + 8 + disp_xy
                disp_z = struct.unpack_from("<i", data, i + 14)[0]
                z_addr = base + i + 18 + disp_z
                return xy_addr, xy_addr + 4, z_addr
            pos = i + 1

        return 0, 0, 0

    def find_world_offset(self, data: bytes, base: int) -> Optional[int]:
        """Find the world offset address.

        Tries VEX-encoded pattern first, then fallback.

        Returns absolute address or None.
        """
        # Try VEX-encoded pattern first
        pos = 0
        matches = []
        while pos < len(data) - 22:
            i = data.find(b"\xC5", pos)
            if i == -1:
                break
            if (
                data[i + 8] == 0xC5
                and data[i + 10] == 0x11
                and data[i + 12:i + 16] == b"\x90\x00\x00\x00"
                and data[i + 16] == 0xE8
                and data[i + 21] == 0xC5
            ):
                matches.append(i)
                if len(matches) > 1:
                    # Ambiguous — don't use
                    return None
            pos = i + 1

        if len(matches) == 1:
            i = matches[0]
            disp = struct.unpack_from("<i", data, i + 4)[0]
            return base + i + 8 + disp

        # Fallback: AOB_WORLD pattern
        suffix = b"\x0F\x11\x99\x90\x00\x00\x00"
        pos = 0
        while pos < len(data) - 14:
            i = data.find(b"\x0F\x5C\x1D", pos)
            if i == -1:
                break
            if data[i + 7:i + 14] == suffix:
                disp = struct.unpack_from("<i", data, i + 3)[0]
                return base + i + 7 + disp
            pos = i + 1

        return None

    def find_physics_delta_hook(self, data: bytes, base: int) -> Optional[int]:
        """Find the physics delta hook point.

        Pattern: movaps xmm0, xmm6 / subss xmm9, xmm8
        Confirmed by addps xmm0, [r13] + movups [r13], xmm0 in next 8 bytes.

        Also accepts stale JMP from previous unclean session:
          E9 xx xx xx xx 90 90 90 (8-byte JMP patch)

        Returns absolute address or None.
        Returns None if 0 or >1 candidates found (ambiguous).
        """
        hook = b"\x0F\x28\xC6\xF3\x45\x0F\x5C\xC8"
        confirm_patterns = [
            b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00",
        ]
        stale_jmp_prefix = b"\xE9"
        stale_jmp_size = 8

        candidates: list[int] = []

        for confirm in confirm_patterns:
            pos = 0
            while pos < len(data) - len(confirm) - 8:
                i = data.find(confirm, pos)
                if i == -1:
                    break

                hook_offset = i - 8
                if hook_offset >= 0:
                    before = data[hook_offset:i]

                    if before == hook:
                        candidates.append(hook_offset)
                        pos = i + 1
                        continue

                    if len(before) == stale_jmp_size and before[0:1] == stale_jmp_prefix:
                        if all(b == 0x90 for b in before[5:8]):
                            log.debug(
                                "Physics hook found with stale JMP at %#x (RVA=%#x)",
                                base + hook_offset, hook_offset,
                            )
                            candidates.append(hook_offset)
                            pos = i + 1
                            continue

                pos = i + 1

        if len(candidates) == 1:
            return base + candidates[0]
        elif len(candidates) > 1:
            log.warning(
                "Physics delta hook: %d candidates found — ambiguous, rejecting",
                len(candidates),
            )
            return None

        # Fallback: search for hook pattern directly without confirmation
        hook_matches = []
        pos = 0
        while pos < len(data) - 18:
            i = data.find(hook, pos)
            if i == -1:
                break
            if i + len(hook) + 10 <= len(data):
                after = data[i + len(hook):i + len(hook) + 10]
                if any(after.startswith(c) for c in confirm_patterns):
                    hook_matches.append(i)
            pos = i + 1

        if len(hook_matches) == 1:
            return base + hook_matches[0]
        elif len(hook_matches) > 1:
            log.warning(
                "Physics delta hook: %d match(es) without stale JMP — ambiguous, rejecting",
                len(hook_matches),
            )
            return None

        return None

    def find_camera_heading(self, data: bytes, base: int) -> Optional[int]:
        """Find camera heading pattern.

        Returns absolute address or None.
        """
        pattern = b"\xC4\xC1\x7A\x11\x97\xCC\x04\x00\x00\xC5\x78\x2F\xCE"
        idx = find_first_pattern(data, pattern)
        if idx is not None:
            addr = base + idx
            if validate_address(addr, self._module_base, self._module_size):
                return addr
            log.warning(
                "Camera heading address %#x (RVA=%#x) is outside module range — rejecting",
                addr, idx,
            )
        return None

    def scan(self, game_version: str = "generic") -> dict[str, ScanResult]:
        """Scan for all known patterns for a game version.

        Args:
            game_version: Game version string for signature lookup.
                Falls back to generic signatures if version-specific
                signatures are not found.

        Returns dict of pattern_name -> ScanResult.
        """
        try:
            data, base, size = self.read_module()
        except Exception as e:
            log.error("Failed to read module: %s\n%s", e, traceback.format_exc())
            raise

        signatures = get_signatures(game_version)
        results: dict[str, ScanResult] = {}

        log.info(
            "AOB scan started for version %s (module size=%#x, base=%#x)",
            game_version, size, base,
        )
        self._module_base = base
        self._module_size = size

        # Static XYZ (special handling — returns 3 addresses)
        x_addr, y_addr, z_addr = self.find_static_xyz(data, base)
        if any((x_addr, y_addr, z_addr)):
            results["xyz_x"] = ScanResult("xyz_x", x_addr, x_addr - base, size)
            results["xyz_y"] = ScanResult("xyz_y", y_addr, y_addr - base, size)
            results["xyz_z"] = ScanResult("xyz_z", z_addr, z_addr - base, size)
            log.info(
                "Static XYZ found: X=%#x Y=%#x Z=%#x",
                x_addr, y_addr, z_addr,
            )
        else:
            log.warning("Static XYZ AOB not found — position reading will use hook fallback")

        # World offset
        world_addr = self.find_world_offset(data, base)
        if world_addr:
            if validate_address(world_addr, base, size):
                results["world_offset"] = ScanResult(
                    "world_offset", world_addr, world_addr - base, size
                )
                log.info("World offset found: %#x (RVA=%#x)", world_addr, world_addr - base)
            else:
                log.warning("World offset address %#x is outside module range — rejecting", world_addr)
        else:
            log.warning("World offset AOB not found")

        # Physics delta hook
        phys_addr = self.find_physics_delta_hook(data, base)
        if phys_addr:
            if validate_address(phys_addr, base, size) and self.is_in_executable_section(phys_addr):
                results["physics_delta"] = ScanResult(
                    "physics_delta", phys_addr, phys_addr - base, size
                )
                log.info("Physics delta hook found: %#x (RVA=%#x)", phys_addr, phys_addr - base)
            elif validate_address(phys_addr, base, size):
                log.warning(
                    "Physics delta hook found at %#x but NOT in executable section — rejecting",
                    phys_addr,
                )
            else:
                log.warning("Physics delta address %#x is outside module range — rejecting", phys_addr)
        else:
            log.warning("Physics delta hook not found")

        # Camera heading
        cam_addr = self.find_camera_heading(data, base)
        if cam_addr:
            results["camera_heading"] = ScanResult(
                "camera_heading", cam_addr, cam_addr - base, size
            )
            log.info("Camera heading hook found: %#x (RVA=%#x)", cam_addr, cam_addr - base)
        else:
            log.warning("Camera heading AOB not found")

        # Generic patterns from signature set — use items_bytes() to get bytes, not strings
        for name, pattern in signatures.items_bytes():
            if name in ("xyz_prefix", "xyz_mid", "world_offset", "physics_delta", "camera_heading"):
                continue  # Already handled above

            try:
                matches = find_pattern(data, pattern)
            except AOBParseError as e:
                log.error("Failed to parse pattern '%s': %s", name, e)
                continue
            except Exception as e:
                log.error("Unexpected error scanning '%s': %s\n%s", name, e, traceback.format_exc())
                continue

            if len(matches) == 1:
                addr = base + matches[0]
                if validate_address(addr, base, size):
                    results[name] = ScanResult(name, addr, matches[0], size, matches=1)
                    log.debug("Found unique %s at %#x", name, addr)
                else:
                    log.warning(
                        "Pattern '%s' matched at %#x but outside module range — rejecting",
                        name, addr,
                    )
            elif len(matches) > 1:
                log_scan_diagnostics(name, pattern, matches, base, size)
            else:
                log.debug("AOB pattern '%s' not found", name)

        log.info("AOB scan complete: %d patterns resolved", len(results))
        return results
