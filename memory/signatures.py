"""AOB signature definitions organized by game version/build.

All game-version-specific AOB patterns are defined here.
DO NOT scatter AOB patterns throughout the codebase.

Signatures are sourced from the verified working CD Companion implementation.

The "generic" signature set is used for AOB patterns that are known to be
stable across multiple game builds. The version-specific sets extend or
override these patterns where game patches change instruction layout.
"""

from __future__ import annotations

import logging

from memory.types import SignatureSet

# AOB patterns for Crimson Desert, sourced from CD Companion.
# Each version key should match the game's build/version string.
# Patterns are verified against the current game binary.

# Physics delta hook — confirmed identical across builds 1.0.0.2079 and 1.0.0.2692.
PHYSICS_DELTA_PATTERN = b"\x0F\x28\xC6\xF3\x45\x0F\x5C\xC8"

SIGNATURES: dict[str, SignatureSet] = {
    "generic": SignatureSet(
        world_offset=b"\x0F\x5C\x1D",
        physics_delta=PHYSICS_DELTA_PATTERN,
        xyz_prefix=b"\xC5\xFB\x11\x05",
        xyz_mid=b"\x8B\x44\x24\x28\x89\x05",
    ),
    "2.00.00": SignatureSet(
        entity_base=b"\x48\x83\xEC\x50\x48\x8B\xF9\x48\x8B\x91\x30\x11\x00\x00",
        position_write=b"\x0F\x11\x99\x90\x00\x00\x00",
        health=b"\x48\x8B\x46\x08\x48\x89\xF1",
        map_marker=b"\xC5\xFB\x10\x07\xC5\xFB\x11\x02\x8B\x47\x08\x89\x42\x08",
        world_offset=b"\x0F\x5C\x1D",
        physics_delta=PHYSICS_DELTA_PATTERN,
        camera_heading=b"\xC4\xC1\x7A\x11\x97\xCC\x04\x00\x00\xC5\x78\x2F\xCE",
        xyz_prefix=b"\xC5\xFB\x11\x05",
        xyz_mid=b"\x8B\x44\x24\x28\x89\x05",
    ),
}


def get_signatures(version: str) -> SignatureSet:
    """Get signatures for a specific game version.

    Falls back to the "generic" signature set for patterns that are
    build-independent (physics_delta, xyz_prefix, xyz_mid, world_offset).

    Args:
        version: Game version string (e.g. "2.00.00", "1.0.0.2079").

    Returns:
        SignatureSet — version-specific if known, otherwise the generic set.
    """
    if version in SIGNATURES:
        return SIGNATURES[version]

    # Unknown version: use generic signatures as a fallback.
    # The generic set covers AOB patterns that are stable across builds.
    logging.info(
        "Unknown game version '%s' — using generic signature set",
        version,
    )
    return SIGNATURES["generic"]


def list_versions() -> list[str]:
    """List all known game versions (excludes 'generic')."""
    return [v for v in SIGNATURES if v != "generic"]
