"""Main application entry point for Crimson Atlas.

This is a development/debug application that:
1. Attaches to CrimsonDesert.exe
2. Reads player position from memory
3. Displays live X/Y/Z coordinates (local and absolute)

This is NOT the final UI. It's a CLI-based debug tool for Phase 1/2B.
"""

from __future__ import annotations

import logging
import math
import os
import sys
import threading
import time
from typing import Optional

from memory.hooks import HookEngine, PHYSICS_HOOK_ORIGINAL, PHYSICS_HOOK_SIZE
from memory.process import GameProcess, ProcessState, PROCESS_NAME
from memory.scanner import AOBScanner
from memory.player_reader import PlayerPositionReader, PositionSource
from memory.teleport import TeleportEngine
from memory.signatures import get_signatures, list_versions
from app.local_server import LocalServer
from app.protocol import build_position_packet, validate_position_packet

logger = logging.getLogger(__name__)


def self_test() -> int:
    """Validate packaged imports without attaching to the game process."""
    import struct

    versions = list_versions()
    if not versions:
        raise RuntimeError("No Crimson Desert signature sets are available")
    if not callable(build_position_packet) or not callable(validate_position_packet):
        raise RuntimeError("Protocol helpers are unavailable")

    class CaptureProcess:
        payload: bytes | None = None

        def write_bytes(self, _address: int, payload: bytes) -> None:
            self.payload = payload

    capture = CaptureProcess()
    teleport = TeleportEngine(capture)  # type: ignore[arg-type]
    teleport.set_physics_hook(0x1000)
    ok, error = teleport.teleport_to(110.0, 220.0, 330.0, (10.0, 20.0, 30.0))
    if not ok or capture.payload is None:
        raise RuntimeError(f"Teleport serialization failed: {error}")
    if struct.unpack("<ffffI", capture.payload) != (100.0, 200.0, 300.0, 0.0, 1):
        raise RuntimeError("Teleport serialization produced an invalid payload")
    print(f"Crimson Atlas service self-test passed ({len(versions)} signature set(s))")
    return 0


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def format_position(pos: Optional[PlayerPosition], label: str = "") -> str:
    """Format position for display."""
    if pos is None or not pos.valid:
        return f"{label}X: —     Y: —     Z: —"
    return (
        f"{label}X: {pos.x:>10.2f}     "
        f"Y: {pos.y:>10.2f}     "
        f"Z: {pos.z:>10.2f}"
    )


def print_header() -> None:
    """Print application header."""
    print("=" * 60)
    print("  CRIMSON ATLAS — Memory Reading Debug Tool")
    print("=" * 60)
    print()


def print_status(
    process_state: ProcessState,
    game_version: str,
    reader_source: PositionSource,
    local_pos: Optional[PlayerPosition],
    world_offset: Optional[tuple[float, float, float, float]],
    absolute_pos: Optional[tuple[float, float, float]],
    update_rate: float,
    last_update_age: float,
    read_count: int,
    error_count: int,
) -> None:
    """Print current status with local/absolute coordinates."""
    # State
    state_str = process_state.value.replace("_", " ").title()
    print(f"Game:        {state_str}")

    # Version
    if game_version:
        print(f"Version:     {game_version}")
    else:
        print("Version:     Unknown")

    # Reader source
    source_str = reader_source.value.replace("_", " ").title()
    print(f"Reader:      {source_str}")
    print()

    # Local position
    print("LOCAL POSITION")
    if local_pos and local_pos.valid:
        print(f"  X: {local_pos.x:>10.2f}")
        print(f"  Y: {local_pos.y:>10.2f}")
        print(f"  Z: {local_pos.z:>10.2f}")
    else:
        print("  X: —")
        print("  Y: —")
        print("  Z: —")
    print()

    # World offset
    print("WORLD OFFSET")
    if world_offset:
        ox, oy, oz, ow = world_offset
        print(f"  X: {ox:>10.2f}")
        print(f"  Y: {oy:>10.2f}")
        print(f"  Z: {oz:>10.2f}")
        print(f"  W: {ow:>10.2f}")
    else:
        print("  X: —")
        print("  Y: —")
        print("  Z: —")
        print("  W: —")
    print()

    # Absolute world position
    print("ABSOLUTE WORLD POSITION")
    if absolute_pos:
        ax, ay, az = absolute_pos
        print(f"  X: {ax:>10.2f}")
        print(f"  Y: {ay:>10.2f}")
        print(f"  Z: {az:>10.2f}")
    else:
        print("  X: —")
        print("  Y: —")
        print("  Z: —")
    print()

    # Stats
    print(f"Update rate: {update_rate:>6.1f} Hz")
    print(f"Last update: {last_update_age:>6.1f}s ago")
    print(f"Reads: {read_count:>8} (errors: {error_count})")
    print()
    print("Press Ctrl+C to exit")


def main() -> int:
    """Main entry point."""
    # Set up logging
    from logging_config import setup_logging
    setup_logging()

    logger.info("Crimson Atlas starting...")

    print_header()

    # Check for known versions
    print(f"Known game versions: {', '.join(list_versions())}")
    print()

    # Initialize components
    game_process = GameProcess()
    scanner = AOBScanner(game_process)
    reader = PlayerPositionReader(game_process, scanner)
    hook_engine = HookEngine(game_process)
    teleport_engine = TeleportEngine(game_process)
    server = LocalServer()
    server.start()

    # Desktop hosts use this private stdin channel for a graceful shutdown.
    # Closing the window must reach ``finally`` so installed hooks are restored.
    shutdown_requested = threading.Event()
    if not sys.stdin.isatty():
        def watch_stdin() -> None:
            try:
                for line in sys.stdin:
                    if line.strip().lower() == "shutdown":
                        break
            finally:
                shutdown_requested.set()

        threading.Thread(target=watch_stdin, name="atlas-shutdown", daemon=True).start()

    # State tracking
    current_version: str = ""
    scan_results: dict = {}
    physics_hook_installed: bool = False
    last_position_time = time.time()
    frame_count = 0
    last_fps_time = time.time()
    update_rate = 0.0
    absolute_pos: Optional[tuple[float, float, float]] = None
    world_offset: Optional[tuple[float, float, float, float]] = None
    last_status_time = 0.0

    try:
        while not shutdown_requested.is_set():
            now = time.time()
            if now - last_status_time >= 1.0:
                server.broadcast({
                    "type": "status",
                    "gameAttached": game_process.is_attached,
                    "teleportAvailable": teleport_engine.available,
                    "message": game_process.state.value,
                })
                last_status_time = now

            command = server.poll_command()
            while command is not None:
                request_id = command.get("requestId")
                if command.get("cmd") != "teleport":
                    result = {"type": "command_result", "requestId": request_id, "ok": False, "error": "Unknown command"}
                else:
                    try:
                        x, y, z = (float(command[key]) for key in ("x", "y", "z"))
                        if not all(math.isfinite(value) for value in (x, y, z)):
                            raise ValueError("Coordinates must be finite")
                        if not (-16384.0 <= x <= 3076.0 and -11267.0 <= z <= 8193.0):
                            raise ValueError("Coordinates are outside the calibrated map")
                        if absolute_pos:
                            teleport_engine.save_pre_teleport_position(*absolute_pos)
                        offset = world_offset[:3] if world_offset else (0.0, 0.0, 0.0)
                        ok, error = teleport_engine.teleport_to(x, y, z, offset)
                        result = {"type": "command_result", "requestId": request_id, "ok": ok, "error": error}
                    except (KeyError, TypeError, ValueError) as exc:
                        result = {"type": "command_result", "requestId": request_id, "ok": False, "error": str(exc)}
                server.broadcast(result)
                command = server.poll_command()

            # Handle process state changes
            if not game_process.is_attached:
                physics_hook_installed = False
                teleport_engine.clear_physics_hook()
                if game_process.attach():
                    logger.info("Process attached successfully")
                    clear_screen()
                    print_header()
                else:
                    time.sleep(0.5)
                    continue

            # Process is attached — try to scan if not done
            if not scan_results:
                try:
                    # Try to detect version from module
                    versions = list_versions()
                    if versions:
                        current_version = versions[0]
                        logger.info("Using signature set for version %s", current_version)

                    scan_results = scanner.scan(current_version)
                    reader.update_addresses(scan_results)

                    # Install physics hook if static XYZ not available
                    if not scan_results.get("xyz_x") and scan_results.get("physics_delta"):
                        phys_addr = scan_results["physics_delta"].address
                        try:
                            hook_info = hook_engine.install_physics_hook(phys_addr)
                            reader.set_physics_hook(hook_info.capture_buffer_address)
                            teleport_engine.set_physics_hook(hook_info.capture_buffer_address)
                            physics_hook_installed = True
                            logger.info(
                                "Physics hook installed — using PHYSICS_HOOK fallback"
                            )
                        except Exception as e:
                            logger.error("Failed to install physics hook: %s", e)

                    if not scan_results.get("xyz_x") and not scan_results.get("physics_delta"):
                        logger.error(
                            "No position source found — check signatures or game version"
                        )
                        game_process._state = ProcessState.UNSUPPORTED_BUILD
                        time.sleep(5)
                        continue

                    logger.info("Scan complete, starting position reads")
                except Exception as e:
                    logger.error("Scan failed: %s\n%s", e, logging.getLogger().handlers[0].format(traceback.format_exc()) if False else "")
                    import traceback
                    logger.error("Traceback:\n%s", traceback.format_exc())
                    game_process.detach()
                    time.sleep(2)
                    continue

            # Check if process is still alive
            if not game_process.is_alive():
                logger.info("Game process exited")
                if physics_hook_installed:
                    logger.info("Restoring hooks and freeing memory")
                hook_engine.cleanup()
                physics_hook_installed = False
                teleport_engine.clear_physics_hook()
                game_process.detach()
                scan_results = {}
                reader._capture_buf_addr = 0
                reader._source = PositionSource.UNAVAILABLE
                continue

            # Read position
            try:
                position = reader.read_position()
                last_position_time = time.time()
                frame_count += 1
            except Exception as e:
                logger.error("Position read error: %s", e)
                reader._error_count += 1
                time.sleep(0.1)
                continue

            # Broadcast valid position over WebSocket
            if position and position.valid:
                absolute_pos = reader.get_absolute_position(local_pos=position)
                world_offset = reader.get_world_offset()
                packet = build_position_packet(
                    x=absolute_pos[0] if absolute_pos else position.x,
                    y=absolute_pos[1] if absolute_pos else position.y,
                    z=absolute_pos[2] if absolute_pos else position.z,
                    local_x=position.x,
                    local_y=position.y,
                    local_z=position.z,
                    offset_x=world_offset[0] if world_offset else 0.0,
                    offset_z=world_offset[2] if world_offset else 0.0,
                    reader=position.source.value,
                    timestamp=position.timestamp,
                )
                if validate_position_packet(packet):
                    server.broadcast_position(packet)

            # Calculate update rate
            now = time.time()
            elapsed = now - last_fps_time
            if elapsed >= 1.0:
                update_rate = frame_count / elapsed
                frame_count = 0
                last_fps_time = now

            # Display
            last_update_age = now - last_position_time
            print_status(
                game_process.state, current_version,
                reader.position_source,
                position,
                world_offset,
                absolute_pos,
                update_rate, last_update_age,
                reader.read_count, reader.error_count,
            )

            # Sleep to target ~15 display updates per second
            time.sleep(0.066)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        logger.info("Crimson Atlas shutting down")
        if physics_hook_installed:
            logger.info("Cleaning up physics hook")
            hook_engine.cleanup()
        if game_process.is_attached:
            game_process.detach()
        logger.info("Stopping local server...")
        server.stop()
        logger.info("Cleanup complete")

    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
