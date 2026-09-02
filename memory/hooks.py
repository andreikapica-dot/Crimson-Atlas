"""Code cave builder and hook installer for Crimson Atlas."""

from __future__ import annotations

import ctypes
import logging
import struct
from typing import Optional

from memory.process import GameProcess
from memory.types import HookInfo, PositionSource

log = logging.getLogger(__name__)

# Windows API constants
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_EXECUTE_READWRITE = 0x40

# Standard JMP patch sizes
STANDARD_PATCH_SIZE = 7
PHYSICS_HOOK_PATCH_SIZE = 8

# Physics delta hook constants
PHYSICS_HOOK_ORIGINAL = b"\x0F\x28\xC6\xF3\x45\x0F\x5C\xC8"
PHYSICS_HOOK_SIZE = 8
CAPTURE_MAGIC = 0x50415054  # "CAPT"
CAPTURE_OFFSET_MAGIC = 0x00
CAPTURE_OFFSET_SEQUENCE = 0x04
CAPTURE_OFFSET_TELEPORT = 0x10
CAPTURE_OFFSET_TELEPORT_FLAG = 0x20
CAPTURE_OFFSET_XYZ = 0x40
CAPTURE_BUFFER_SIZE = 0x100

# Set up VirtualAllocEx argtypes for 64-bit address support
_kernel32 = ctypes.windll.kernel32
_kernel32.VirtualAllocEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_ulong,
    ctypes.c_ulong,
]
_kernel32.VirtualAllocEx.restype = ctypes.c_void_p


class HookEngine:
    """Manages code cave allocation and hook installation."""

    def __init__(self, game_process: GameProcess) -> None:
        self.game_process = game_process
        self._block_address: int = 0
        self._block_size: int = 0x1000  # 4KB
        self._hooks: dict[int, HookInfo] = {}
        self._next_cave_offset: int = 0x100

    @property
    def block_address(self) -> int:
        """Address of allocated code cave block."""
        return self._block_address

    @property
    def hooks_installed(self) -> bool:
        """Whether any hooks are installed."""
        return len(self._hooks) > 0

    def allocate_block(self, near_address: int = 0) -> int:
        """Allocate a code cave block near an address.

        Args:
            near_address: Preferred address near which to allocate.

        Returns:
            Allocated block address.

        Raises:
            RuntimeError: If allocation fails.
        """
        handle = self.game_process.pm.process_handle

        # If we have a near address, try to allocate close to it first
        if near_address:
            for offset in range(0x10000, 0x7FFF0000, 0x10000):
                for addr in (near_address + offset, near_address - offset):
                    if addr <= 0:
                        continue
                    result = _kernel32.VirtualAllocEx(
                        handle, addr, self._block_size,
                        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
                    )
                    if result:
                        self._block_address = result
                        log.info("Allocated code cave at %#x (near %#x)", result, near_address)
                        return result

        # Fallback: allocate anywhere
        result = _kernel32.VirtualAllocEx(
            handle, 0, self._block_size,
            MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE
        )
        if not result:
            raise RuntimeError("Failed to allocate code cave block")
        self._block_address = result
        log.info("Allocated code cave at %#x (fallback)", result)
        return result

    def free_block(self) -> None:
        """Free the allocated code cave block."""
        if self._block_address:
            try:
                self.game_process.free_memory(self._block_address)
            except Exception as e:
                log.debug("Error freeing block: %s", e)
            self._block_address = 0
            self._next_cave_offset = 0x100

    def install_hook(
        self,
        hook_address: int,
        cave_code: bytes,
        original_size: int = STANDARD_PATCH_SIZE,
    ) -> HookInfo:
        """Install a hook by patching the original code with a JMP to the cave.

        Args:
            hook_address: Address of the instruction to hook.
            cave_code: Machine code for the code cave.
            original_size: Number of original bytes to preserve.

        Returns:
            HookInfo for the installed hook.

        Raises:
            RuntimeError: If hook is already installed or write fails.
        """
        if hook_address in self._hooks:
            raise RuntimeError(f"Hook already installed at {hook_address:#x}")

        # Read original bytes before patching
        original_bytes = self.game_process.read_bytes(hook_address, original_size)

        # Write cave to allocated block
        cave_offset = self._next_cave_offset
        self._next_cave_offset += len(cave_code)
        cave_address = self._block_address + cave_offset
        self.game_process.write_bytes(cave_address, cave_code)

        # Build and write JMP patch
        jmp_patch = self._build_jmp_patch(hook_address, cave_address, original_size)
        self.game_process.write_bytes(hook_address, jmp_patch)

        hook_info = HookInfo(
            address=hook_address,
            original_size=original_size,
            original_bytes=original_bytes,
            cave_address=cave_address,
            cave_size=len(cave_code),
        )
        self._hooks[hook_address] = hook_info

        log.info(
            "Installed hook at %#x → cave %#x (%d bytes)",
            hook_address, cave_address, len(cave_code),
        )
        return hook_info

    def install_physics_hook(self, hook_address: int) -> HookInfo:
        """Install the physics delta hook for position capture.

        This hook captures the live player position vector from [r13]
        into an allocated capture buffer.

        Args:
            hook_address: Address of the physics delta instruction.

        Returns:
            HookInfo including capture_buffer_address.

        Raises:
            RuntimeError: If hook cannot be installed.
        """
        if hook_address in self._hooks:
            raise RuntimeError(f"Hook already installed at {hook_address:#x}")

        # Verify expected original bytes
        actual = self.game_process.read_bytes(hook_address, PHYSICS_HOOK_SIZE)
        if actual != PHYSICS_HOOK_ORIGINAL:
            # Check for stale JMP from previous unclean session
            if actual[:1] == b"\xE9":
                log.warning(
                    "Stale JMP found at physics hook %#x — overwriting with fresh hook",
                    hook_address,
                )
            else:
                raise RuntimeError(
                    f"Unexpected bytes at physics hook {hook_address:#x}: {actual.hex()}"
                )

        # Allocate block if not already allocated
        if not self._block_address:
            self.allocate_block(near_address=hook_address)

        # Capture buffer inside the allocated block
        # Keep shared data well away from code caves, which start at +0x100.
        capture_buf = self._block_address + 0x800

        # Initialize capture buffer
        self.game_process.write_bytes(capture_buf, struct.pack("<I", CAPTURE_MAGIC))
        self.game_process.write_bytes(
            capture_buf + CAPTURE_OFFSET_SEQUENCE,
            b"\x00" * (CAPTURE_BUFFER_SIZE - CAPTURE_OFFSET_SEQUENCE),
        )

        log.info(
            "Physics capture buffer allocated at %#x (magic=%#x)",
            capture_buf, CAPTURE_MAGIC,
        )

        # Build cave
        return_addr = hook_address + PHYSICS_HOOK_SIZE
        cave_code = self._build_physics_cave(capture_buf, return_addr)

        # Write cave to block
        cave_offset = self._next_cave_offset
        cave_address = self._block_address + cave_offset
        self.game_process.write_bytes(cave_address, cave_code)
        self._next_cave_offset += len(cave_code)

        # Build and write 8-byte JMP patch
        jmp_patch = self._build_jmp_patch(hook_address, cave_address, PHYSICS_HOOK_PATCH_SIZE)
        self.game_process.write_bytes(hook_address, jmp_patch)

        hook_info = HookInfo(
            address=hook_address,
            original_size=PHYSICS_HOOK_SIZE,
            original_bytes=actual,
            cave_address=cave_address,
            cave_size=len(cave_code),
            capture_buffer_address=capture_buf,
        )
        self._hooks[hook_address] = hook_info

        log.info(
            "Physics hook installed: %#x -> cave %#x (capture_buf=%#x)",
            hook_address, cave_address, capture_buf,
        )
        return hook_info

    def remove_hook(self, hook_address: int) -> None:
        """Remove a hook by restoring original bytes."""
        if hook_address not in self._hooks:
            return
        hook_info = self._hooks[hook_address]
        try:
            self.game_process.write_bytes(
                hook_address,
                hook_info.original_bytes[:hook_info.original_size],
            )
            log.info("Removed hook at %#x", hook_address)
        except Exception as e:
            log.error("Failed to remove hook at %#x: %s", hook_address, e)
        del self._hooks[hook_address]

    def cleanup(self) -> None:
        """Remove all hooks and free allocated memory."""
        log.info("Cleaning up %d hooks", len(self._hooks))
        for addr in list(self._hooks.keys()):
            self.remove_hook(addr)
        self.free_block()

    def _build_physics_cave(self, capture_buf: int, return_addr: int) -> bytes:
        """Build code cave for physics delta hook.

        The cave captures the live player position from [r13]. A pending
        teleport request replaces the movement delta in xmm0 before the
        original code resumes and applies it to [r13].

        Capture buffer layout:
          +0x00: magic (uint32) = 0x50415054
          +0x04: sequence (uint32) — incremented each physics frame
          +0x10: teleport target/delta xyz[0..3] (16 bytes)
          +0x20: command (uint32): 0=none, 1=absolute local, 2=delta
          +0x40: xyz[0..3] (16 bytes) — [r13] position vector
        """
        cave = bytearray()

        # Preserve flags and rax while we inspect the shared capture buffer.
        cave += b"\x9C\x50"  # pushfq; push rax
        # mov rax, capture_buf
        cave += b"\x48\xB8" + struct.pack("<Q", capture_buf)

        # Save R13 at capture_buf + 0x60 (for future heading use)
        cave += b"\x4C\x89\x68\x60"  # mov [rax+0x60], r13

        # Read [r13] into xmm0, save to capture_buf + 0x40
        cave += b"\x41\x0F\x10\x45\x00"  # movups xmm0, [r13]
        cave += b"\x0F\x11\x40\x40"      # movups [rax+0x40], xmm0

        # Increment sequence counter.
        cave += b"\xFF\x40\x04"  # inc dword [rax+0x04]

        # Original instructions (8 bytes)
        cave += b"\x0F\x28\xC6"          # movaps xmm0, xmm6
        cave += b"\xF3\x45\x0F\x5C\xC8"  # subss xmm9, xmm8

        # If no command is pending, retain the normal physics delta in xmm0.
        cave += b"\x83\x78\x20\x00"  # cmp dword [rax+0x20], 0
        jump_done = len(cave) + 1
        cave += b"\x74\x00"  # je done

        # Command 1 is an absolute local target: target - current = delta.
        cave += b"\x83\x78\x20\x01"  # cmp dword [rax+0x20], 1
        jump_delta = len(cave) + 1
        cave += b"\x75\x00"  # jne delta_mode
        cave += b"\x0F\x10\x40\x10"      # movups xmm0, [rax+0x10]
        cave += b"\x41\x0F\x5C\x45\x00"  # subps xmm0, [r13]
        jump_clear = len(cave) + 1
        cave += b"\xEB\x00"  # jmp clear

        delta_mode = len(cave)
        cave += b"\x0F\x10\x40\x10"  # movups xmm0, [rax+0x10]
        clear_command = len(cave)
        cave += b"\xC7\x40\x20\x00\x00\x00\x00"  # mov dword [rax+0x20], 0
        done = len(cave)
        cave[jump_done] = (done - (jump_done + 1)) & 0xFF
        cave[jump_delta] = (delta_mode - (jump_delta + 1)) & 0xFF
        cave[jump_clear] = (clear_command - (jump_clear + 1)) & 0xFF

        cave += b"\x58\x9D"  # pop rax; popfq

        # jmp [rip+8] to return_addr
        cave += b"\xFF\x25\x00\x00\x00\x00" + struct.pack("<Q", return_addr)

        return bytes(cave)

    def _build_jmp_patch(self, from_addr: int, to_addr: int, patch_size: int = STANDARD_PATCH_SIZE) -> bytes:
        """Build a JMP patch.

        For 5-byte patch: E9 + rel32.
        For 7-byte patch: E9 + rel32 + 2 NOPs.
        For 8-byte patch: E9 + rel32 + 3 NOPs.

        Args:
            from_addr: Address of the instruction being patched.
            to_addr: Destination address (code cave).
            patch_size: Total patch size (5, 7, or 8).

        Returns:
            Patch bytes.
        """
        rel = to_addr - (from_addr + 5)
        if not (-0x80000000 <= rel <= 0x7FFFFFFF):
            raise RuntimeError(
                f"Cave too far for rel32 jump: {from_addr:#x} → {to_addr:#x}"
            )

        if patch_size == 5:
            return b"\xE9" + struct.pack("<i", rel)
        elif patch_size == 8:
            return b"\xE9" + struct.pack("<i", rel) + b"\x90" * 3
        else:
            # 7-byte patch: E9 + rel32 + 2 NOPs
            return b"\xE9" + struct.pack("<i", rel) + b"\x90" * 2
