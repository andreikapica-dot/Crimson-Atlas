"""Process attachment and management for Crimson Atlas.

This module handles:
- Locating CrimsonDesert.exe
- Attaching via pymem
- Exposing process handle and module info
- Detecting process exit
- Safe detach and reconnect
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import sys
import time
from typing import Optional

import pymem
import pymem.process

from memory.state import ProcessState

log = logging.getLogger(__name__)

PROCESS_NAME = "CrimsonDesert.exe"


class GameProcess:
    """Manages attachment to CrimsonDesert.exe."""

    def __init__(self) -> None:
        self.pm: Optional[pymem.Pymem] = None
        self.module: Optional[Any] = None
        self._state: ProcessState = ProcessState.GAME_NOT_RUNNING
        self._last_error: Optional[str] = None

    @property
    def state(self) -> ProcessState:
        """Current process state."""
        return self._state

    @property
    def last_error(self) -> Optional[str]:
        """Last error message."""
        return self._last_error

    @property
    def is_attached(self) -> bool:
        """Whether we are currently attached."""
        return self._state == ProcessState.ATTACHED

    def attach(self) -> bool:
        """Attach to the game process.

        Returns:
            True if attachment succeeded.
        """
        if self._state == ProcessState.ATTACHED:
            self.detach()

        self._state = ProcessState.ATTACHING
        self._last_error = None

        try:
            log.info("Attempting to attach to %s...", PROCESS_NAME)
            self.pm = pymem.Pymem(PROCESS_NAME)
            self.module = pymem.process.module_from_name(
                self.pm.process_handle, PROCESS_NAME
            )
            self._state = ProcessState.ATTACHED
            log.info(
                "Attached to %s — base=%#x size=%#x",
                PROCESS_NAME,
                self.module.lpBaseOfDll,
                self.module.SizeOfImage,
            )
            return True
        except pymem.exception.ProcessNotFound:
            self._last_error = "Process not found"
            self._state = ProcessState.GAME_NOT_RUNNING
            log.warning("%s is not running", PROCESS_NAME)
            return False
        except Exception as e:
            self._last_error = str(e)
            self._state = ProcessState.ERROR
            log.error("Failed to attach: %s", e)
            return False

    def detach(self) -> None:
        """Detach from the game process."""
        if self.pm:
            try:
                self.pm.close_process()
            except Exception:
                pass
        self.pm = None
        self.module = None
        old_state = self._state
        self._state = ProcessState.GAME_NOT_RUNNING
        if old_state == ProcessState.ATTACHED:
            log.info("Detached from %s", PROCESS_NAME)

    def is_alive(self) -> bool:
        """Check if the game process is still running."""
        if not self.pm:
            return False
        try:
            kernel32 = ctypes.windll.kernel32
            WAIT_OBJECT_0 = 0x0
            return (
                kernel32.WaitForSingleObject(self.pm.process_handle, 0)
                != WAIT_OBJECT_0
            )
        except Exception:
            return False

    def wait_for_process(self, poll_interval: float = 2.0) -> bool:
        """Wait for the game process to appear.

        Args:
            poll_interval: Seconds between checks.

        Returns:
            True if process appeared and was attached.
        """
        log.info("Waiting for %s to start...", PROCESS_NAME)
        while True:
            if self.attach():
                return True
            time.sleep(poll_interval)

    def read_bytes(self, address: int, size: int) -> bytes:
        """Read bytes from process memory."""
        if not self.pm:
            raise RuntimeError("Not attached to process")
        return self.pm.read_bytes(address, size)

    def read_float(self, address: int) -> float:
        """Read a float from process memory."""
        if not self.pm:
            raise RuntimeError("Not attached to process")
        return self.pm.read_float(address)

    def read_ulonglong(self, address: int) -> int:
        """Read a 64-bit unsigned integer from process memory."""
        if not self.pm:
            raise RuntimeError("Not attached to process")
        return self.pm.read_ulonglong(address)

    def write_bytes(self, address: int, data: bytes) -> None:
        """Write bytes to process memory."""
        if not self.pm:
            raise RuntimeError("Not attached to process")
        self.pm.write_bytes(address, data, len(data))

    def write_float(self, address: int, value: float) -> None:
        """Write a float to process memory."""
        import struct
        self.write_bytes(address, struct.pack("<f", value))

    def write_ulonglong(self, address: int, value: int) -> None:
        """Write a 64-bit unsigned integer to process memory."""
        import struct
        self.write_bytes(address, struct.pack("<Q", value))

    def allocate_memory(self, size: int, address: int = 0) -> int:
        """Allocate memory in the process."""
        if not self.pm:
            raise RuntimeError("Not attached to process")
        kernel32 = ctypes.windll.kernel32
        MEM_COMMIT = 0x1000
        MEM_RESERVE = 0x2000
        PAGE_EXECUTE_READWRITE = 0x40
        result = kernel32.VirtualAllocEx(
            self.pm.process_handle,
            address,
            size,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE,
        )
        if not result:
            raise RuntimeError("Failed to allocate memory")
        return result

    def free_memory(self, address: int) -> None:
        """Free allocated memory."""
        if not self.pm:
            return
        kernel32 = ctypes.windll.kernel32
        MEM_RELEASE = 0x8000
        kernel32.VirtualFreeEx(self.pm.process_handle, address, 0, MEM_RELEASE)

    def get_module_base(self) -> int:
        """Get the base address of the game module."""
        if not self.module:
            raise RuntimeError("Not attached or module not loaded")
        return self.module.lpBaseOfDll

    def get_module_size(self) -> int:
        """Get the size of the game module."""
        if not self.module:
            raise RuntimeError("Not attached or module not loaded")
        return self.module.SizeOfImage
