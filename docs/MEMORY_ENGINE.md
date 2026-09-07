# Memory Engine

## Purpose

The memory engine is responsible for:

1. Finding and attaching to `CrimsonDesert.exe`
2. Identifying the supported game build
3. Performing AOB scans
4. Installing required hooks
5. Capturing player coordinates and heading
6. Exposing current absolute world position
7. Supporting teleportation
8. Cleanly detaching
9. Detecting when the game closes
10. Reconnecting after game restart
11. Reporting unsupported game versions clearly

## Design Goals

- **No dependency on CD Companion** — Clean reimplementation from scratch
- **Version-tolerant** — Easy to add new game versions
- **Robust** — Handles hook failures, process death, and game updates gracefully
- **Compatible** — Works alongside other mods (Freedom Flyer, OpenFlight)
- **Safe** — Proper cleanup on detach, no memory leaks

## Module Structure

### `memory/signatures.py`

All AOB patterns organized by game version:

```python
SIGNATURES = {
    "2.00.00": {
        "player_position": b"...",
        "teleport": b"...",
        "health": b"...",
        "map_marker": b"...",
        "world_offset": b"...",
        "physics_delta": b"...",
        "camera_heading": b"...",
        "xyz_static_prefix": b"...",
        "xyz_static_mid": b"...",
    },
    "2.01.00": {
        # Next version...
    }
}
```

Rules:
- Never scatter AOB patterns throughout the codebase
- Keep all version-specific data in this file
- Use descriptive keys for each signature
- Include build hashes or module sizes for validation

### `memory/process.py`

Process management:

```python
class GameProcess:
    def attach(self) -> None
    def detach(self) -> None
    def is_alive(self) -> bool
    def get_module_base(self) -> int
    def get_module_size(self) -> int
    def read_bytes(self, address: int, size: int) -> bytes
    def read_float(self, address: int) -> float
    def read_ulonglong(self, address: int) -> int
    def write_bytes(self, address: int, data: bytes) -> None
    def allocate_memory(self, size: int, address: int = 0) -> int
    def free_memory(self, address: int) -> None
```

### `memory/scanner.py`

AOB scanning with caching:

```python
class AOBScanner:
    def scan_module(self, module_base: int, module_size: int) -> bytes
    def find_pattern(self, data: bytes, pattern: bytes) -> list[int]
    def find_first(self, data: bytes, pattern: bytes) -> int | None
    def validate_cache(self, cached_rva: int, expected_bytes: bytes, data: bytes, base: int) -> int | None
```

Features:
- Chunked module reading (64KB chunks to handle read failures)
- Pattern validation against cached RVAs
- Module size fingerprinting
- Automatic cache invalidation on game update

### `memory/hooks.py`

Code cave builder and hook installer:

```python
class HookEngine:
    def allocate_block(self, size: int, near: int = 0) -> int
    def build_cave(self, cave_type: str, **kwargs) -> bytes
    def install_hook(self, hook_address: int, cave_address: int, original_bytes: bytes) -> None
    def remove_hook(self, hook_address: int, original_bytes: bytes) -> None
    def cleanup(self) -> None
```

Supported cave types:
- `entity_capture` — Captures entity base
- `position_capture` — Captures local XYZ
- `invulnerability` — Handles invuln flag
- `map_destination` — Captures map marker
- `physics_delta` — Teleport via physics loop
- `camera_heading` — Captures camera yaw

### `memory/player_reader.py`

Position and heading extraction:

```python
class PlayerReader:
    def get_local_position(self) -> tuple[float, float, float] | None
    def get_world_offset(self) -> tuple[float, float, float, float] | None
    def get_absolute_position(self) -> tuple[float, float, float] | None
    def get_player_heading(self) -> float | None
    def get_camera_heading(self) -> float | None
    def get_map_destination(self) -> tuple[float, float, float] | None
```

Read priority:
1. Static XYZ globals (no hook required)
2. Physics position hook (hook_e)
3. Entity capture hook (hook_b / td+0x20)

### `memory/teleport.py`

Teleportation implementation:

```python
class TeleportEngine:
    def teleport_to(self, x: float, y: float, z: float) -> tuple[bool, str]
    def move_by(self, dx: float, dy: float, dz: float) -> tuple[bool, str]
    def abort_teleport(self) -> tuple[bool, str]
    def set_invulnerability(self, enabled: bool) -> None
```

Methods:
- `teleport_to`: Absolute coordinate teleport
- `move_by`: Relative movement via physics delta
- `abort_teleport`: Return to pre-teleport position
- `set_invulnerability`: Toggle invuln flag

## Position Update Architecture

### Memory Read Rate
- Target: 60 Hz (every ~16ms)
- Reads position from game memory
- Applies world offset
- Publishes to internal queue

### Map Render Rate
- Driven by frontend `requestAnimationFrame`
- Receives position updates via WebSocket
- Interpolates between updates for smooth movement

### Expensive UI Calculations
- Nearby search: 2-5 Hz
- UI statistics: 2-10 Hz
- POI filtering: on filter change only

### Threading Model
```
Main Thread:
  - Process attach/detach
  - Hook installation/removal
  - Configuration

Memory Read Thread:
  - AOB scanning (on attach)
  - Position reading (60 Hz)
  - Teleport execution

WebSocket Thread:
  - Client communication
  - Command processing

Frontend Thread:
  - Map rendering
  - UI updates
  - User interaction
```

## Hook Architecture

### Code Cave Layout

Each allocated block (4KB) contains:

```
Offset 0x000: Teleport data (td)
Offset 0x040: Invulnerability flag (inv)
Offset 0x050: Map destination (md)
Offset 0x060: Teleport target (tp)
Offset 0x090: Camera yaw
Offset 0x094: Player heading
Offset 0x0A0: Physics position
Offset 0x0C0: Physics pointer
Offset 0x100: Cave A (entity capture)
Offset 0x180: Cave B (position capture)
Offset 0x200: Cave C (invulnerability)
Offset 0x280: Cave D (map destination)
Offset 0x300: Cave E (physics delta)
Offset 0x380: Cave F (camera heading)
```

### JMP Patch Sizes

| Hook | Patch Size | Notes |
|------|-----------|-------|
| hook_a | 7 bytes | Standard rel32 JMP + 2 NOPs |
| hook_b | 7 bytes | Standard rel32 JMP + 2 NOPs |
| hook_c | 7 bytes | Standard rel32 JMP + 2 NOPs |
| hook_d | 7 bytes | Standard rel32 JMP + 2 NOPs |
| hook_e | 7 bytes | Standard, or 5 bytes with safetyhook predecessor |
| hook_cam | 9 bytes | VEX instruction, needs full 9-byte patch |

### Predecessor Hook Handling

When another mod (Freedom Flyer, OpenFlight) has already hooked the same point:

1. Detect JMP at hook address
2. Read trampoline to determine patch size (5 vs 7 bytes)
3. Chain our cave through their trampoline
4. For safetyhook (5-byte patch): skip original bytes on flag=0
5. For OpenFlight (7-byte patch): execute all original bytes

## Fallback Strategy

When a signature or hook fails:

1. **Static XYZ unavailable** → Use physics position hook
2. **Physics hook unavailable** → Use hook_b (td+0x20)
3. **All position sources fail** → Report "no position" to frontend
4. **Hook installation fails** → Detach and retry on next cycle
5. **Process dies** → Auto-detach, wait for re-attach
6. **Game updates** → Clear cache, re-scan, report unsupported if no patterns match

## Error Handling

### Process Not Found
- Log warning
- Wait 5 seconds
- Retry attach

### Hook Installation Failure
- Log error with details
- Detach cleanly
- Retry on next cycle

### Read Failure
- Log warning
- Attempt detach
- Re-attach on next cycle

### Unsupported Version
- No matching signatures
- Clear error message to user
- Suggest checking for updates

## Security Considerations

- Require Administrator privileges for memory access
- Validate all read addresses before dereferencing
- Never write to arbitrary memory addresses
- Clean up all allocated memory on detach
- Restore all original bytes on hook removal
- No persistent memory modifications after detach

## Performance Considerations

- Read module in chunks to handle read failures
- Cache resolved RVAs to avoid re-scanning
- Throttle broadcasts when position unchanged
- Use memory-mapped reads where possible
- Minimize allocations in hot path
