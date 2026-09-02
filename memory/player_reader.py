"""Player position and heading reader for Crimson Atlas.

This module provides a clean API for reading player state from game memory.
It does NOT expose raw pymem objects to the rest of the application.
"""

from __future__ import annotations

import logging
import math
import struct
import time
from typing import Optional

from memory.process import GameProcess
from memory.scanner import AOBScanner
from memory.types import PlayerPosition, PositionSource, ScanResult

log = logging.getLogger(__name__)

# Capture buffer layout constants
CAPTURE_MAGIC = 0x50415054
CAPTURE_OFFSET_SEQUENCE = 0x04
CAPTURE_OFFSET_XYZ = 0x40


class PlayerPositionReader:
    """Reads player position and heading from game memory.

    This class provides a clean API for the rest of the application.
    It handles:
    - Static XYZ global reads (preferred, read-only)
    - Physics position hook fallback
    - World offset application
    - Heading calculation
    - Position validation
    """

    def __init__(self, game_process: GameProcess, scanner: AOBScanner) -> None:
        self.game_process = game_process
        self.scanner = scanner
        self._xyz_addresses: tuple[int, int, int] = (0, 0, 0)
        self._world_offset_addr: int = 0
        self._capture_buf_addr: int = 0
        self._last_sequence: int = 0
        self._source: PositionSource = PositionSource.UNAVAILABLE
        self._last_position: Optional[PlayerPosition] = None
        self._read_count: int = 0
        self._error_count: int = 0

    @property
    def last_position(self) -> Optional[PlayerPosition]:
        """Last successfully read position."""
        return self._last_position

    @property
    def read_count(self) -> int:
        """Total number of position reads."""
        return self._read_count

    @property
    def error_count(self) -> int:
        """Total number of read errors."""
        return self._error_count

    @property
    def position_source(self) -> PositionSource:
        """Current position data source."""
        return self._source

    def set_physics_hook(self, capture_buf_addr: int) -> None:
        """Activate physics hook as position source.

        Args:
            capture_buf_addr: Address of the capture buffer in game memory.
        """
        self._capture_buf_addr = capture_buf_addr
        self._last_sequence = 0
        self._source = PositionSource.PHYSICS_HOOK
        log.info("PlayerReader: source set to PHYSICS_HOOK (capture_buf=%#x)", capture_buf_addr)

    def update_addresses(self, scan_results: dict[str, ScanResult]) -> None:
        """Update internal addresses from scan results."""
        self._xyz_addresses = (
            scan_results.get("xyz_x", ScanResult("", 0, 0, 0)).address,
            scan_results.get("xyz_y", ScanResult("", 0, 0, 0)).address,
            scan_results.get("xyz_z", ScanResult("", 0, 0, 0)).address,
        )
        self._world_offset_addr = scan_results.get("world_offset", ScanResult("", 0, 0, 0)).address

        x_addr, y_addr, z_addr = self._xyz_addresses
        if any((x_addr, y_addr, z_addr)):
            self._source = PositionSource.STATIC_XYZ
            log.info(
                "PlayerReader: static XYZ addresses updated X=%#x Y=%#x Z=%#x",
                x_addr, y_addr, z_addr,
            )
        elif self._source != PositionSource.PHYSICS_HOOK:
            self._source = PositionSource.UNAVAILABLE

        if self._world_offset_addr:
            log.info("PlayerReader: world offset at %#x", self._world_offset_addr)

    def read_position(self) -> PlayerPosition:
        """Read current player position.

        Returns:
            PlayerPosition with current coordinates and validity flag.
        """
        self._read_count += 1
        timestamp = time.time()

        # Strategy 1: Static XYZ globals (preferred, read-only)
        if self._source == PositionSource.STATIC_XYZ:
            pos = self._read_static_xyz()
            if pos:
                self._last_position = PlayerPosition(
                    x=pos[0], y=pos[1], z=pos[2],
                    timestamp=timestamp, source=PositionSource.STATIC_XYZ, valid=True
                )
                return self._last_position

        # Strategy 2: Physics position hook (fallback)
        if self._source == PositionSource.PHYSICS_HOOK:
            pos = self._read_physics_capture()
            if pos:
                self._last_position = PlayerPosition(
                    x=pos[0], y=pos[1], z=pos[2],
                    timestamp=timestamp, source=PositionSource.PHYSICS_HOOK, valid=True
                )
                return self._last_position

        # No valid position
        self._error_count += 1
        log.debug("No valid position available (source=%s)", self._source.value)
        return PlayerPosition(
            x=0.0, y=0.0, z=0.0,
            timestamp=timestamp, source=self._source, valid=False
        )

    def _read_static_xyz(self) -> Optional[tuple[float, float, float]]:
        """Read position from static XYZ globals.

        Returns:
            (x, y, z) tuple or None if unavailable.
        """
        x_addr, y_addr, z_addr = self._xyz_addresses
        if not any((x_addr, y_addr, z_addr)):
            return None

        try:
            x = self.game_process.read_float(x_addr)
            y = self.game_process.read_float(y_addr)
            z = self.game_process.read_float(z_addr)

            # Check for zero position (loading screen / invalid)
            if x == 0.0 and y == 0.0 and z == 0.0:
                return None

            # Validate
            if not all(math.isfinite(v) for v in (x, y, z)):
                return None
            if abs(x) > 1e6 or abs(y) > 1e6 or abs(z) > 1e6:
                return None

            return x, y, z
        except Exception as e:
            log.debug("Static XYZ read failed: %s", e)
            return None

    def _read_physics_capture(self) -> Optional[tuple[float, float, float]]:
        """Read position from physics hook capture buffer.

        Returns:
            (x, y, z) tuple or None if unavailable or invalid.
        """
        if not self._capture_buf_addr:
            return None

        try:
            # Check magic to verify buffer is initialized
            magic = struct.unpack("<I", self.game_process.read_bytes(self._capture_buf_addr, 4))[0]
            if magic != CAPTURE_MAGIC:
                log.debug("Physics capture buffer magic mismatch: %#x", magic)
                return None

            # Read sequence counter
            seq = struct.unpack("<I", self.game_process.read_bytes(
                self._capture_buf_addr + CAPTURE_OFFSET_SEQUENCE, 4
            ))[0]

            # If sequence hasn't changed, no new data
            if seq == 0 or seq == self._last_sequence:
                return None

            self._last_sequence = seq

            # Read XYZ from capture buffer
            raw = self.game_process.read_bytes(
                self._capture_buf_addr + CAPTURE_OFFSET_XYZ, 12
            )
            x, y, z = struct.unpack("<fff", raw)

            # Validate
            if not all(math.isfinite(v) for v in (x, y, z)):
                log.debug("Physics capture contains non-finite values: (%s, %s, %s)", x, y, z)
                return None

            if abs(x) > 1e6 or abs(y) > 1e6 or abs(z) > 1e6:
                log.debug("Physics capture contains absurd values: (%s, %s, %s)", x, y, z)
                return None

            return x, y, z

        except Exception as e:
            log.debug("Physics capture read failed: %s", e)
            return None

    def get_world_offset(self) -> Optional[tuple[float, float, float, float]]:
        """Get world offset (4 floats).

        The world offset is added to local position to get absolute position.

        Returns:
            (offset_x, offset_y, offset_z, offset_w) or None if unavailable.
        """
        if not self._world_offset_addr:
            return None
        try:
            raw = self.game_process.read_bytes(self._world_offset_addr, 16)
            return struct.unpack("<ffff", raw)
        except Exception as e:
            log.debug("World offset read failed: %s", e)
            return None

    def get_absolute_position(
        self,
        local_pos: Optional[PlayerPosition] = None,
    ) -> Optional[tuple[float, float, float]]:
        """Get absolute world position.

        Absolute = local + world offset (X and Z only; Y typically not offset).

        Args:
            local_pos: Optional pre-read local position.  If provided, the
                method will not call read_position() again, avoiding a
                second memory read for the same frame.

        Returns:
            (abs_x, abs_y, abs_z) or None if unavailable.
        """
        if local_pos is None:
            local_pos = self.read_position()
        if not local_pos.valid:
            return None

        x, y, z = local_pos.x, local_pos.y, local_pos.z
        offset = self.get_world_offset()
        if offset:
            ox, oy, oz, _ = offset
            return x + ox, y, z + oz

        return (x, y, z)

    def get_player_heading(self) -> Optional[float]:
        """Get player heading in degrees (0-360).

        Returns:
            Heading in degrees or None if unavailable.
        """
        # TODO: Implement when physics entity hook is available
        return None

    def get_camera_heading(self) -> Optional[float]:
        """Get camera heading in degrees (-180 to 180).

        Returns:
            Heading in degrees or None if unavailable.
        """
        # TODO: Implement when camera hook is available
        return None

    def is_position_valid(self, position: PlayerPosition) -> bool:
        """Check if a position is valid (not loading screen, etc.)."""
        if not position.valid:
            return False
        if not all(math.isfinite(v) for v in (position.x, position.y, position.z)):
            return False
        return not (position.x == 0.0 and position.y == 0.0 and position.z == 0.0)
