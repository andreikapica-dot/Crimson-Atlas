"""World coordinate types and realm detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LocalPosition:
    """Local position in game coordinates (before world offset)."""

    x: float
    y: float
    z: float

    def to_tuple(self) -> tuple[float, float, float]:
        """Convert to tuple."""
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class WorldPosition:
    """Absolute world position (after world offset applied)."""

    x: float
    y: float
    z: float
    realm: str = "pywel"
    timestamp: float = 0.0
    valid: bool = True

    def distance_2d(self, other: WorldPosition) -> float:
        """Calculate 2D (XZ) distance to another position."""
        dx = other.x - self.x
        dz = other.z - self.z
        return math.sqrt(dx * dx + dz * dz)

    def distance_3d(self, other: WorldPosition) -> float:
        """Calculate 3D distance to another position."""
        dx = other.x - self.x
        dy = other.y - self.y
        dz = other.z - self.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def __str__(self) -> str:
        if not self.valid:
            return "WorldPosition(invalid)"
        return (
            f"WorldPosition(x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f}, "
            f"realm={self.realm})"
        )


@dataclass(frozen=True)
class WorldOffset:
    """World offset applied to local coordinates."""

    x: float
    y: float
    z: float
    w: float  # padding/unknown

    def apply(self, local: LocalPosition) -> WorldPosition:
        """Apply offset to local position."""
        return WorldPosition(
            x=local.x + self.x,
            y=local.y + self.y,
            z=local.z + self.z,
        )


def detect_realm(y: float, threshold: float = 1400.0) -> str:
    """Detect realm from Y coordinate.

    Args:
        y: Y coordinate.
        threshold: Height threshold for Abyss realm.

    Returns:
        Realm name.
    """
    return "abyss" if y > threshold else "pywel"


# Default Y values for teleport when no height data is available
DEFAULT_TELEPORT_Y: dict[str, float] = {
    "pywel": 1000.0,
    "abyss": 2400.0,
}

# Height boost applied to teleports to prevent ground clipping
HEIGHT_BOOST: float = 10.0

# Invulnerability duration after teleport (seconds)
INVULNERABILITY_SECONDS: int = 10


import math  # noqa: E402 - needed for sqrt in distance methods
