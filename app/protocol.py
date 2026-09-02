"""Crimson Atlas WebSocket protocol definitions.

Defines the packet schemas and helper functions for frontend/backend
communication.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Position packet schema
# ---------------------------------------------------------------------------
# Required fields for a position packet:
#   type      - str    - packet discriminator ("position")
#   x, y, z   - float  - absolute world coordinates
#   realm      - str    - detected realm ("pywel" / "abyss")
#   localX, localY, localZ - float - local (cell-relative) coordinates
#   offsetX, offsetZ      - float - world offset applied to compute absolute
#   reader    - str    - PositionSource string ("static_xyz" / "physics_hook")
#   timestamp - float  - unix timestamp of the read

POSITION_PACKET_FIELDS: tuple[str, ...] = (
    "type",
    "x",
    "y",
    "z",
    "realm",
    "localX",
    "localY",
    "localZ",
    "offsetX",
    "offsetZ",
    "reader",
    "timestamp",
)

POSITION_TYPE = "position"


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
def build_position_packet(
    *,
    x: float,
    y: float,
    z: float,
    local_x: float,
    local_y: float,
    local_z: float,
    offset_x: float,
    offset_z: float,
    reader: str,
    timestamp: float,
) -> dict[str, Any]:
    """Create a validated position packet dict.

    All keyword arguments map 1:1 to the protocol schema.
    """
    packet: dict[str, Any] = {
        "type": POSITION_TYPE,
        "x": x,
        "y": y,
        "z": z,
        "realm": "abyss" if y > 1400.0 else "pywel",
        "localX": local_x,
        "localY": local_y,
        "localZ": local_z,
        "offsetX": offset_x,
        "offsetZ": offset_z,
        "reader": reader,
        "timestamp": timestamp,
    }
    return packet


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
def validate_position_packet(packet: dict[str, Any]) -> bool:
    """Validate a dict against the position packet schema.

    Returns True if the packet is structurally valid and all field types
    are correct.  Does NOT check value ranges — that is the caller's
    responsibility.
    """
    if not isinstance(packet, dict):
        log.debug("validate_position_packet: packet is not a dict")
        return False

    if packet.get("type") != POSITION_TYPE:
        log.debug("validate_position_packet: wrong type field: %r", packet.get("type"))
        return False

    # Check all required fields are present
    for field in POSITION_PACKET_FIELDS:
        if field == "type":
            continue
        if field not in packet:
            log.debug("validate_position_packet: missing field %r", field)
            return False

    # Type checks
    numeric_fields = (
        "x", "y", "z",
        "localX", "localY", "localZ",
        "offsetX", "offsetZ",
        "timestamp",
    )
    for field in numeric_fields:
        value = packet[field]
        if not isinstance(value, (int, float)):
            log.debug("validate_position_packet: %r is not numeric: %r", field, value)
            return False

    if not isinstance(packet["reader"], str):
        log.debug("validate_position_packet: reader is not a str: %r", packet["reader"])
        return False

    if packet["realm"] not in ("pywel", "abyss"):
        log.debug("validate_position_packet: invalid realm: %r", packet["realm"])
        return False

    return True
