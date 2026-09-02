"""AOB signature definitions organized by game version/build.

All game-version-specific AOB patterns are defined here.
DO NOT scatter AOB patterns throughout the codebase.

Signatures are sourced from the verified working CD Companion implementation.
"""

from __future__ import annotations

from memory.types import SignatureSet

# AOB patterns for Crimson Desert, sourced from CD Companion.
# Each version key should match the game's build/version string.
# Patterns are verified against the current game binary.

SIGNATURES: dict[str, SignatureSet] = {
    "2.00.00": SignatureSet(
        # Entity base pattern: sub rsp,50; mov rdi,rcx
        entity_base=b"\x48\x83\xEC\x50\x48\x8B\xF9\x48\x8B\x91\x30\x11\x00\x00",
        # Position write: vmovsd [rip+disp], xmm0
        position_write=b"\x0F\x11\x99\x90\x00\x00\x00",
        # Health/invulnerability: mov [rcx+08], rbx
        health=b"\x48\x8B\x46\x08\x48\x89\xF1",
        # Map marker destination: vmovsd [rdx], xmm0
        map_marker=b"\xC5\xFB\x10\x07\xC5\xFB\x11\x02\x8B\x47\x08\x89\x42\x08",
        # World offset: vsubps pattern
        world_offset=b"\x0F\x5C\x1D",
        # Physics delta hook: movaps xmm0, xmm6
        physics_delta=b"\x0F\x28\xC6\xF3\x45\x0F\x5C\xC8",
        # Camera heading: vmovss [r15+0x4CC], xmm2
        camera_heading=b"\xC4\xC1\x7A\x11\x97\xCC\x04\x00\x00\xC5\x78\x2F\xCE",
        # Static XYZ prefix: vmovsd [rip+disp32], xmm0
        xyz_prefix=b"\xC5\xFB\x11\x05",
        # Static XYZ mid: mov eax,[rsp+28] ; mov [rip+disp32],eax
        xyz_mid=b"\x8B\x44\x24\x28\x89\x05",
    ),
    # Future versions should be added here
}


def get_signatures(version: str) -> SignatureSet:
    """Get signatures for a specific game version.

    Args:
        version: Game version string (e.g. "2.00.00").

    Returns:
        Signature set for the version, or empty SignatureSet if unknown.
    """
    return SIGNATURES.get(version, SignatureSet())


def list_versions() -> list[str]:
    """List all known game versions."""
    return list(SIGNATURES.keys())
