"""Teleportation implementation."""

from __future__ import annotations

import logging
import math
import struct
from typing import Optional

from memory.process import GameProcess

log = logging.getLogger(__name__)

HEIGHT_BOOST = 0.0
INVULNERABILITY_SECONDS = 10


class TeleportEngine:
    """Handles teleportation and movement injection."""

    def __init__(self, game_process: GameProcess) -> None:
        self.game_process = game_process
        self._tp_address: int = 0  # Teleport target block
        self._inv_address: int = 0  # Invulnerability flag
        self._pre_teleport_pos: Optional[tuple[float, float, float]] = None
        self._enabled: bool = True

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable teleportation."""
        self._enabled = enabled

    @property
    def available(self) -> bool:
        """Whether the live physics hook can accept a teleport command."""
        return self._enabled and self._tp_address != 0

    def set_physics_hook(self, capture_buffer_address: int) -> None:
        """Connect teleport commands to the shared physics capture buffer."""
        self._tp_address = capture_buffer_address + 0x10 if capture_buffer_address else 0

    def clear_physics_hook(self) -> None:
        """Disconnect the capture buffer after process exit or cleanup."""
        self._tp_address = 0

    def teleport_to(
        self,
        x: float,
        y: float,
        z: float,
        world_offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> tuple[bool, str]:
        """Teleport to absolute coordinates.

        Returns (success, error_message).
        """
        if not self._enabled:
            return False, "Teleport is disabled"

        if not self._tp_address:
            return False, "Teleport hook not installed"

        try:
            x = float(x)
            y = float(y)
            z = float(z)
            ox, oy, oz = (float(value) for value in world_offset)
        except (TypeError, ValueError):
            return False, "Coordinates must be real numbers"

        if not all(math.isfinite(value) for value in (x, y, z, ox, oy, oz)):
            return False, "Coordinates must be finite numbers"

        try:
            local_x = x - ox
            local_y = y - oy + HEIGHT_BOOST
            local_z = z - oz

            # +0x10 target vector followed by +0x20 command flag.
            # The injected cave atomically consumes and clears the flag.
            data = struct.pack("<ffffI", local_x, local_y, local_z, 0.0, 1)
            self.game_process.write_bytes(self._tp_address, data)

            log.info("Teleport queued to absolute (%.1f, %.1f, %.1f)", x, y, z)
            return True, ""
        except Exception as e:
            log.error("Teleport failed: %s", e)
            return False, str(e)

    def teleport_to_current_plus(self, dx: float, dy: float, dz: float) -> tuple[bool, str]:
        """Teleport to current position plus offset.

        Returns (success, error_message).
        """
        # TODO: Read current position and add offset
        return False, "Not implemented"

    def move_by(self, dx: float, dy: float, dz: float) -> tuple[bool, str]:
        """Inject a movement delta via physics hook.

        Returns (success, error_message).
        """
        if not self._tp_address:
            return False, "Teleport hook not installed"

        try:
            # flag=2 = move mode
            data = struct.pack("<ffffI", dx, dy, dz, 0.0, 2)
            self.game_process.write_bytes(self._tp_address, data)
            log.info("Move delta injected: (%.1f, %.1f, %.1f)", dx, dy, dz)
            return True, ""
        except Exception as e:
            log.error("Move failed: %s", e)
            return False, str(e)

    def abort_teleport(self) -> tuple[bool, str]:
        """Return to position before last teleport.

        Returns (success, error_message).
        """
        if not self._pre_teleport_pos:
            return False, "No previous teleport position"

        x, y, z = self._pre_teleport_pos
        result = self.teleport_to(x, y, z)
        self._pre_teleport_pos = None
        return result

    def set_invulnerability(self, enabled: bool) -> None:
        """Set invulnerability flag."""
        if not self._inv_address:
            return
        try:
            self.game_process.write_bytes(
                self._inv_address,
                b"\x01" if enabled else b"\x00",
                1,
            )
        except Exception as e:
            log.debug("Failed to set invulnerability: %s", e)

    def save_pre_teleport_position(self, x: float, y: float, z: float) -> None:
        """Save position before teleport for abort functionality."""
        self._pre_teleport_pos = (x, y, z)
