"""Shared type definitions for memory engine."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from typing import Iterator, Optional


class PositionSource(Enum):
    """Source of player position data."""

    STATIC_XYZ = "static_xyz"
    PHYSICS_HOOK = "physics_hook"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SignatureSet:
    """Container for AOB signatures for a specific game version."""

    entity_base: bytes = b""
    position_write: bytes = b""
    health: bytes = b""
    map_marker: bytes = b""
    world_offset: bytes = b""
    physics_delta: bytes = b""
    camera_heading: bytes = b""
    xyz_prefix: bytes = b""
    xyz_mid: bytes = b""

    def to_dict(self) -> dict[str, str]:
        """Convert to dict for JSON serialization."""
        return {k: v.hex() for k, v in self.__dict__.items() if v}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> SignatureSet:
        """Create from dict with hex strings."""
        kwargs = {k: bytes.fromhex(v) for k, v in data.items()}
        return cls(**kwargs)

    def items_bytes(self) -> Iterator[tuple[str, bytes]]:
        """Iterate over (name, bytes_pattern) pairs for scanning."""
        for f in fields(self):
            value = getattr(self, f.name)
            if value:
                yield f.name, value


@dataclass(frozen=True)
class HookInfo:
    """Information about an installed hook."""

    address: int
    original_size: int
    original_bytes: bytes
    cave_address: int
    cave_size: int
    capture_buffer_address: int = 0


@dataclass(frozen=True)
class ScanResult:
    """Result of an AOB scan."""

    name: str
    address: int
    rva: int
    module_size: int
    matches: int = 1

    def is_unique(self) -> bool:
        """Whether this is a unique match."""
        return self.matches == 1


@dataclass(frozen=True)
class PlayerPosition:
    """Current player position."""

    x: float
    y: float
    z: float
    timestamp: float
    source: PositionSource = PositionSource.UNAVAILABLE
    valid: bool = True

    def __str__(self) -> str:
        if not self.valid:
            return "Position: invalid"
        return f"Position: X={self.x:.2f} Y={self.y:.2f} Z={self.z:.2f}"
