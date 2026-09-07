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

from logging_config import configure_console_encoding
configure_console_encoding()

from memory.hooks import HookEngine, PHYSICS_HOOK_ORIGINAL, PHYSICS_HOOK_SIZE
from memory.process import GameProcess, ProcessState, PROCESS_NAME
from memory.scanner import AOBScanner
from memory.player_reader import PlayerPositionReader, PositionSource
from memory.teleport import TeleportEngine
from memory.signatures import get_signatures, list_versions
from app.local_server import LocalServer
from app.protocol import build_position_packet, validate_position_packet
from services.crimson_route import CrimsonRouteClient, CrimsonRouteError
from services.save_completion import SaveCompletionMonitor

logger = logging.getLogger(__name__)


def self_test() -> int:
    """Validate packaged imports without attaching to the game process."""
    import struct
    from types import SimpleNamespace

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
    if struct.unpack("<ffffI", capture.payload) != (100.0, 220.0, 300.0, 0.0, 1):
        raise RuntimeError("Teleport serialization produced an invalid payload")

    # Exercise AOBScanner.read_module through the packaged Cython extension.
    # A source-only test does not catch Cython's runtime type enforcement.
    module_image = bytearray(0x400)
    module_image[0:2] = b"MZ"
    module_image[0x3C:0x40] = (0x80).to_bytes(4, "little")
    module_image[0x80:0x84] = b"PE\0\0"
    module_image[0x86:0x88] = (1).to_bytes(2, "little")
    module_image[0x94:0x96] = (0xF0).to_bytes(2, "little")
    section_offset = 0x80 + 24 + 0xF0
    module_image[section_offset + 8:section_offset + 12] = (0x200).to_bytes(4, "little")
    module_image[section_offset + 12:section_offset + 16] = (0x1000).to_bytes(4, "little")
    module_image[section_offset + 36:section_offset + 40] = (0x20000000).to_bytes(4, "little")

    class ScannerProcess:
        is_attached = True
        module = SimpleNamespace(lpBaseOfDll=0x140000000, SizeOfImage=len(module_image))

        def read_bytes(self, address: int, size: int) -> bytes:
            offset = address - self.module.lpBaseOfDll
            return bytes(module_image[offset:offset + size])

    scanner = AOBScanner(ScannerProcess())  # type: ignore[arg-type]
    _, scanner_base, scanner_size = scanner.read_module()
    expected_range = (scanner_base + 0x1000, scanner_base + 0x1200)
    if scanner_size != len(module_image) or scanner._executable_ranges != [expected_range]:
        raise RuntimeError("Packaged scanner module-read validation failed")
    print(f"Crimson Atlas service self-test passed ({len(versions)} signature set(s))")
    return 0


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def select_signature_version(game_version: str | None) -> str:
    """Select a known signature profile or the generic compatibility set."""
    return game_version if game_version in list_versions() else "generic"


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
    crimson_route = CrimsonRouteClient()
    crimson_route_lock = threading.Lock()

    server = LocalServer()
    server.start()
    save_completion = SaveCompletionMonitor(server.broadcast)
    save_completion.start()

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
    last_completion_broadcast_time = 0.0
    def calculate_crimson_route(command: dict) -> None:
        """Calculate a Crimson Route path without blocking the main game loop."""
        request_id = command.get("requestId")
        start = command.get("start")

        if not crimson_route_lock.acquire(blocking=False):
            server.broadcast({
                "type": "crimson_route_result",
                "requestId": request_id,
                "ok": False,
                "error": "Crimson Route is already calculating a route",
            })
            return

        try:
            x = float(command["x"])
            z = float(command["z"])

            if not all(math.isfinite(value) for value in (x, z)):
                raise ValueError("Coordinates must be finite")

            if not (-16384.0 <= x <= 3076.0 and -11267.0 <= z <= 8193.0):
                raise ValueError("Coordinates are outside the calibrated map")

            if start:
                logger.info(
                    "Crimson Route request start: X=%.2f Y=%.2f Z=%.2f",
                    float(start["x"]),
                    float(start["y"]),
                    float(start["z"]),
                )
            logger.info(
                "Crimson Route destination: X=%.2f Z=%.2f",
                x, z,
            )

            # Do not send marker Y for now.
            # Crimson Route will determine the appropriate navigation height.
            response = crimson_route.calculate_route(
                x,
                z,
                start=start,
                alternatives=bool(command.get("alternatives", True)),
                apply_to_overlay=bool(command.get("applyToOverlay", True)),
            )

            frontend_routes = []

            for index, route in enumerate(response.get("routes") or []):
                if not route.get("found"):
                    continue

                points = []

                for point in route.get("points") or []:
                    try:
                        px = float(point["x"])
                        py = float(point["y"])
                        pz = float(point["z"])
                    except (KeyError, TypeError, ValueError):
                        continue

                    if not all(math.isfinite(value) for value in (px, py, pz)):
                        continue

                    points.append({
                        "x": px,
                        "y": py,
                        "z": pz,
                    })

                if len(points) < 2:
                    continue

                frontend_routes.append({
                    "index": index,
                    "primary": index == 0,
                    "points": points,
                    "pointCount": len(points),
                    "polylineDistance": route.get("polyline_distance", 0),
                    "roadDistance": route.get("road_distance", 0),
                    "endPoint": route.get("end_point"),
                })

            if not frontend_routes:
                raise CrimsonRouteError(
                    response.get("error") or "Crimson Route did not return a usable route"
                )

            server.broadcast({
                "type": "crimson_route_result",
                "requestId": request_id,
                "ok": True,
                "realm": command.get("realm"),
                "routes": frontend_routes,
            })

            logger.info(
                "Crimson Route calculated %d route(s) to X=%.2f Z=%.2f",
                len(frontend_routes),
                x,
                z,
            )

        except (CrimsonRouteError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Crimson Route calculation failed: %s", exc)

            server.broadcast({
                "type": "crimson_route_result",
                "requestId": request_id,
                "ok": False,
                "error": str(exc),
            })

        except Exception as exc:
            logger.exception("Unexpected Crimson Route error")

            server.broadcast({
                "type": "crimson_route_result",
                "requestId": request_id,
                "ok": False,
                "error": str(exc),
            })

        finally:
            crimson_route_lock.release()

    def clear_crimson_route_display() -> None:
        """Clear the route displayed by Crimson Route, after any active calculation."""
        try:
            with crimson_route_lock:
                crimson_route.clear_display_route()
            logger.info("Crimson Route in-game display cleared")
        except CrimsonRouteError as exc:
            logger.warning("Could not clear Crimson Route display: %s", exc)
        except Exception:
            logger.exception("Unexpected Crimson Route clear error")

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
            if now - last_completion_broadcast_time >= 5.0:
                server.broadcast(save_completion.latest_packet)
                last_completion_broadcast_time = now

            command = server.poll_command()
            while command is not None:
                request_id = command.get("requestId")
                cmd = command.get("cmd")

                if cmd == "crimson_route.calculate":
                    route_start = absolute_pos
                    command_copy = dict(command)
                    if route_start:
                        command_copy["start"] = {
                            "x": route_start[0],
                            "y": route_start[1],
                            "z": route_start[2],
                            "height_reliable": True,
                        }
                    threading.Thread(
                        target=calculate_crimson_route,
                        args=(command_copy,),
                        name="crimson-route-calculation",
                        daemon=True,
                    ).start()

                    command = server.poll_command()
                    continue

                if cmd == "crimson_route.clear":
                    threading.Thread(
                        target=clear_crimson_route_display,
                        name="crimson-route-clear",
                        daemon=True,
                    ).start()

                    command = server.poll_command()
                    continue

                if cmd != "teleport":
                    result = {
                        "type": "command_result",
                        "requestId": request_id,
                        "ok": False,
                        "error": "Unknown command",
                    }
                else:
                    try:
                        x, y, z = (
                            float(command[key])
                            for key in ("x", "y", "z")
                        )

                        if not all(math.isfinite(value) for value in (x, y, z)):
                            raise ValueError("Coordinates must be finite")

                        if not (-16384.0 <= x <= 3076.0 and -11267.0 <= z <= 8193.0):
                            raise ValueError(
                                "Coordinates are outside the calibrated map"
                            )

                        if absolute_pos:
                            teleport_engine.save_pre_teleport_position(
                                *absolute_pos
                            )

                        offset = (
                            world_offset[:3]
                            if world_offset
                            else (0.0, 0.0, 0.0)
                        )

                        ok, error = teleport_engine.teleport_to(
                            x,
                            y,
                            z,
                            offset,
                        )

                        result = {
                            "type": "command_result",
                            "requestId": request_id,
                            "ok": ok,
                            "error": error,
                        }

                    except (KeyError, TypeError, ValueError) as exc:
                        result = {
                            "type": "command_result",
                            "requestId": request_id,
                            "ok": False,
                            "error": str(exc),
                        }

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
                    game_version = game_process.get_game_version()
                    if game_version:
                        logger.info("Detected game version: %s", game_version)
                    else:
                        logger.info("Detected game version: unknown")

                    current_version = select_signature_version(game_version)
                    if current_version == "generic":
                        logger.info("Unknown build, using generic signatures")

                    scan_results = scanner.scan(current_version)
                    reader.update_addresses(scan_results)

                    has_static = any((
                        scan_results.get("xyz_x"),
                        scan_results.get("xyz_y"),
                        scan_results.get("xyz_z"),
                    ))
                    has_physics = scan_results.get("physics_delta") is not None
                    has_world = scan_results.get("world_offset") is not None

                    logger.info(
                        "Static XYZ candidate: %s",
                        "FOUND" if has_static else "NOT FOUND",
                    )
                    logger.info(
                        "Physics hook candidate: %s",
                        "FOUND" if has_physics else "NOT FOUND",
                    )
                    logger.info(
                        "World offset candidate: %s",
                        "FOUND" if has_world else "NOT FOUND",
                    )

                    # ---- New policy: always try Physics Hook first ----
                    if has_physics:
                        phys_addr = scan_results["physics_delta"].address
                        try:
                            hook_info = hook_engine.install_physics_hook(phys_addr)
                            reader.set_physics_hook(hook_info.capture_buffer_address)
                            teleport_engine.set_physics_hook(hook_info.capture_buffer_address)
                            physics_hook_installed = True
                            logger.info("Physics hook installed successfully")
                            if has_static:
                                logger.info(
                                    "Static XYZ retained as fallback"
                                )
                        except Exception as e:
                            logger.error("Physics hook installation failed: %s", e)
                            if has_static:
                                logger.info(
                                    "Falling back to STATIC_XYZ"
                                )
                            else:
                                logger.error(
                                    "No fallback available — position source unavailable"
                                )
                    else:
                        logger.info("No physics hook candidate — skipping hook installation")

                    # Deterministic source selection
                    source = reader.select_position_source()
                    logger.info("Selected position source: %s", source.value.upper())
                    logger.info(
                        "Teleport: %s",
                        "available" if teleport_engine.available else "unavailable",
                    )

                    if source == PositionSource.UNAVAILABLE:
                        logger.error(
                            "UNSUPPORTED_BUILD — no position source found. "
                            "Signatures may have changed in this game build."
                        )
                        game_process._state = ProcessState.UNSUPPORTED_BUILD
                        time.sleep(5)
                        continue

                    logger.info(
                        "Scan complete, starting position reads (source=%s)",
                        source.value.upper(),
                    )
                    if game_version:
                        logger.info("Game version: %s", game_version)
                    else:
                        logger.info("Game version: unknown (AOB-based scanning)")
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
        save_completion.stop()
        server.stop()
        logger.info("Cleanup complete")

    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
