"""Offline PE signature diagnostic tool for Crimson Desert.

Reads a CrimsonDesert.exe from disk (without running it) and checks
whether all Atlas-required AOB signatures are present.

Usage:
    python tools/check_game_signatures.py <path-to-CrimsonDesert.exe>

This tool is for developer diagnostics only. It does NOT launch the game
and does NOT access Steam/Epic authentication.
"""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from memory.aob import find_pattern, find_first_pattern
from memory.hooks import PHYSICS_HOOK_ORIGINAL, PHYSICS_HOOK_SIZE
from memory.scanner import AOBScanner
from memory.signatures import SIGNATURES, PHYSICS_DELTA_PATTERN


PHYSICS_CONFIRM = b"\x41\x0F\x58\x45\x00\x41\x0F\x11\x45\x00"

WORLD_OFFSET_PATTERN = b"\x0F\x5C\x1D"
WORLD_OFFSET_SUFFIX = b"\x0F\x11\x99\x90\x00\x00\x00"

XYZ_PREFIX = b"\xC5\xFB\x11\x05"
XYZ_MID = b"\x8B\x44\x24\x28\x89\x05"

CAMERA_HEADING = b"\xC4\xC1\x7A\x11\x97\xCC\x04\x00\x00\xC5\x78\x2F\xCE"


def read_pe_sections(exe_path: str) -> list[tuple[str, int, int, bytes]]:
    """Read PE sections from an executable file.

    Returns list of (section_name, virtual_address, virtual_size, raw_bytes).
    Only readable sections are included.
    """
    try:
        import pefile
    except ImportError:
        print("ERROR: pefile is required. Install with: pip install pefile")
        sys.exit(1)

    pe = pefile.PE(exe_path)
    sections = []
    image_base = pe.OPTIONAL_HEADER.ImageBase

    for section in pe.sections:
        name = section.Name.decode("ascii", errors="replace").rstrip("\x00")
        if not name:
            continue
        if not (section.Characteristics & 0x40000020):
            continue
        data = section.get_data()
        sections.append((name, section.VirtualAddress, section.Misc_VirtualSize, data))

    pe.close()
    return sections, image_base


def scan_section_data(data: bytes, base: int, pattern: bytes) -> list[int]:
    """Find all matches of pattern in data, returning RVAs."""
    matches = find_pattern(data, pattern)
    return [m for m in matches if 0 <= m < len(data)]


def format_result(found: bool, count: int, rvas: list[int]) -> str:
    if found:
        rva_strs = [f"RVA={rva:#010x}" for rva in rvas[:5]]
        return f"FOUND  count={count}  {', '.join(rva_strs)}"
    return "NOT FOUND"


def check_signatures(exe_path: str) -> None:
    """Check all Atlas signatures against a game EXE."""
    from pathlib import Path

    exe_file = Path(exe_path)
    if not exe_file.is_file():
        print(f"ERROR: File not found: {exe_path}")
        sys.exit(1)

    # Get file version info
    try:
        import ctypes
        version = ctypes.windll.version

        class VS_FIXEDFILEINFO(ctypes.Structure):
            _fields_ = [
                ("dwSignature", ctypes.c_uint32),
                ("dwStrucVersion", ctypes.c_uint32),
                ("dwFileVersionMS", ctypes.c_uint32),
                ("dwFileVersionLS", ctypes.c_uint32),
                ("dwProductVersionMS", ctypes.c_uint32),
                ("dwProductVersionLS", ctypes.c_uint32),
                ("dwFileFlagsMask", ctypes.c_uint32),
                ("dwFileFlags", ctypes.c_uint32),
                ("dwFileOS", ctypes.c_uint32),
                ("dwFileType", ctypes.c_uint32),
                ("dwFileSubtype", ctypes.c_uint32),
                ("dwFileDateMS", ctypes.c_uint32),
                ("dwFileDateLS", ctypes.c_uint32),
            ]

        version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
        version.GetFileVersionInfoSizeW.restype = ctypes.c_uint32
        version.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        version.GetFileVersionInfoW.restype = ctypes.c_int
        version.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)]
        version.VerQueryValueW.restype = ctypes.c_int

        handle = ctypes.c_uint32()
        size = version.GetFileVersionInfoSizeW(str(exe_file), ctypes.byref(handle))
        if size:
            data = (ctypes.c_ubyte * size)()
            if not version.GetFileVersionInfoW(str(exe_file), 0, size, data):
                raise OSError("GetFileVersionInfoW failed")
            ffi = ctypes.c_void_p()
            ffi_len = ctypes.c_uint32()
            if not version.VerQueryValueW(data, "\\", ctypes.byref(ffi), ctypes.byref(ffi_len)):
                raise OSError("VerQueryValueW failed")
            fixed = ctypes.cast(ffi, ctypes.POINTER(VS_FIXEDFILEINFO)).contents

            def format_version(ms: int, ls: int) -> str:
                return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"

            file_version = format_version(fixed.dwFileVersionMS, fixed.dwFileVersionLS)
            product_version = format_version(fixed.dwProductVersionMS, fixed.dwProductVersionLS)
        else:
            file_version = None
    except Exception:
        file_version = None
        product_version = None

    # Read PE sections
    try:
        sections, image_base = read_pe_sections(str(exe_file))
    except Exception as e:
        print(f"ERROR: Could not parse PE: {e}")
        sys.exit(1)

    print(f"File: {exe_file.name}")
    print(f"Path: {exe_file}")
    print(f"Size: {exe_file.stat().st_size:,} bytes")
    print(f"File version: {file_version or 'unknown'}")
    print(f"Product version: {product_version or 'unknown'}")
    print(f"PE image base: {image_base:#x}")
    print(f"Readable sections: {len(sections)}")
    for name, va, vsize, _ in sections:
        print(f"  {name}: VA={va:#x} size={vsize:#x}")
    print()

    # Scan for each signature across all readable sections
    # Combine all section data into one buffer for scanning
    # (patterns don't cross section boundaries in practice)
    combined = b""
    section_map = []
    for name, va, vsize, data in sections:
        offset = len(combined)
        combined += data
        section_map.append((name, va, vsize, offset, len(data)))

    # Recreate the image layout used by AOBScanner.read_module so the final
    # verdict comes from the production resolvers, including their contextual
    # validation and the primary VEX world-offset path.
    image_size = max((va + max(vsize, len(data)) for _, va, vsize, data in sections), default=0)
    module_image = bytearray(image_size)
    for _, va, _, data in sections:
        module_image[va:va + len(data)] = data
    module_data = bytes(module_image)
    runtime_scanner = AOBScanner.__new__(AOBScanner)
    runtime_world_addr = runtime_scanner.find_world_offset(module_data, image_base)
    runtime_static = runtime_scanner.find_static_xyz(module_data, image_base)
    runtime_physics_addr = runtime_scanner.find_physics_delta_hook(module_data, image_base)

    def scan_full(pattern: bytes) -> tuple[int, list[int]]:
        matches = find_pattern(combined, pattern)
        # Convert offsets to RVAs
        rv_list = []
        for m in matches:
            for sec_name, sec_va, sec_vsize, sec_offset, sec_dlen in section_map:
                if sec_offset <= m < sec_offset + sec_dlen:
                    rva = sec_va + (m - sec_offset)
                    rv_list.append(rva)
                    break
        return len(matches), rv_list

    print("=== Signature Scan Results ===")
    print()

    # 1. Physics Hook (required)
    physics_count, physics_rvas = scan_full(PHYSICS_DELTA_PATTERN)
    print(f"PHYSICS_HOOK (required):")
    print(f"  Pattern: {PHYSICS_DELTA_PATTERN.hex()}")
    print(f"  {format_result(physics_count > 0, physics_count, physics_rvas)}")
    print()

    # 2. Physics Confirmation (required for validation)
    confirm_count, confirm_rvas = scan_full(PHYSICS_CONFIRM)
    print(f"PHYSICS_CONFIRM (validation):")
    print(f"  Pattern: {PHYSICS_CONFIRM.hex()}")
    print(f"  {format_result(confirm_count > 0, confirm_count, confirm_rvas)}")
    print()

    # 3. World Offset (required for absolute position)
    world_count, world_rvas = scan_full(WORLD_OFFSET_PATTERN)
    print(f"WORLD_OFFSET (required for absolute position):")
    print(f"  Pattern: {WORLD_OFFSET_PATTERN.hex()}")
    # Also check with suffix
    full_matches = 0
    full_rvas = []
    pos = 0
    while pos < len(combined) - len(WORLD_OFFSET_PATTERN):
        idx = combined.find(WORLD_OFFSET_PATTERN, pos)
        if idx == -1:
            break
        if combined[idx + 7:idx + 14] == WORLD_OFFSET_SUFFIX:
            for sec_name, sec_va, sec_vsize, sec_offset, sec_dlen in section_map:
                if sec_offset <= idx < sec_offset + sec_dlen:
                    rva = sec_va + (idx - sec_offset)
                    full_rvas.append(rva)
                    break
            full_matches += 1
        pos = idx + 1
    print(f"  Raw fallback prefix: {format_result(world_count > 0, world_count, world_rvas)}")
    print(f"  Legacy fallback with suffix: {format_result(full_matches > 0, full_matches, full_rvas)}")
    print()

    # 4. Static XYZ (optional, fallback)
    xyz_count, xyz_rvas = scan_full(XYZ_PREFIX)
    xyz_mid_count, _ = scan_full(XYZ_MID)
    static_valid_count = 0
    pos = 0
    while pos < len(combined) - 14:
        idx = combined.find(XYZ_PREFIX, pos)
        if idx == -1:
            break
        if combined[idx + 8:idx + 14] == XYZ_MID:
            static_valid_count += 1
        pos = idx + 1
    print(f"STATIC_XYZ (optional, fallback):")
    print(f"  Prefix pattern: {XYZ_PREFIX.hex()} — {format_result(xyz_count > 0, xyz_count, xyz_rvas)}")
    print(f"  Mid pattern:    {XYZ_MID.hex()} — {format_result(xyz_mid_count > 0, xyz_mid_count, [])}")
    print()

    # 5. Camera Heading (optional)
    cam_count, cam_rvas = scan_full(CAMERA_HEADING)
    print(f"CAMERA_HEADING (optional):")
    print(f"  Pattern: {CAMERA_HEADING.hex()}")
    print(f"  {format_result(cam_count > 0, cam_count, cam_rvas)}")
    print()

    # 6. Additional signatures from version-specific sets
    print("=== Additional Signatures (version 2.00.00) ===")
    version_sigs = SIGNATURES.get("2.00.00")
    if version_sigs:
        for name, pattern in version_sigs.items_bytes():
            if name in ("physics_delta", "world_offset", "xyz_prefix", "xyz_mid"):
                continue  # Already reported above
            count, rv_list = scan_full(pattern)
            print(f"  {name}: {format_result(count > 0, count, rv_list)}")
    else:
        print("  No version-specific signatures defined.")
    print()

    # Summary
    print("=== Summary ===")
    physics_valid = runtime_physics_addr is not None
    world_valid = runtime_world_addr is not None
    static_valid = all(runtime_static)
    print(
        f"Physics Hook: {'OK at RVA ' + hex(runtime_physics_addr - image_base) if physics_valid else 'MISSING OR UNCONFIRMED'}"
    )
    print(
        f"World Offset: {'OK at RVA ' + hex(runtime_world_addr - image_base) if world_valid else 'MISSING OR UNCONFIRMED'}"
    )
    print(f"Static XYZ:   {'OK (fallback)' if static_valid else 'MISSING OR UNCONFIRMED'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/check_game_signatures.py <path-to-CrimsonDesert.exe>")
        sys.exit(1)
    check_signatures(sys.argv[1])
