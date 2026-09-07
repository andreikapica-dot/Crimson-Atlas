# CD Companion — Reference Analysis

## What CD Companion Currently Does

CD Companion is a real-time companion application for Crimson Desert that:

1. Attaches to `CrimsonDesert.exe` via memory reading
2. Installs AOB-based hooks and code caves to capture player position
3. Broadcasts position via WebSocket (`ws://127.0.0.1:7891`)
4. Displays the position on an interactive map by:
   - Injecting JavaScript into MapGenie or Greymane Codex
   - Using a PyQt5/QWebEngineView overlay window
5. Provides teleportation by writing to memory
6. Supports waypoints, calibration, nearby locations, and global hotkeys

## How the Memory Reader Works

### Process Attachment
- Uses `pymem` to attach to `CrimsonDesert.exe`
- Retrieves the main module base and image size
- Reads the entire module into memory for AOB scanning (chunked at 64KB)

### AOB Scanning
- Searches for byte patterns in the module:
  - `AOB_ENTITY`: Entity base pattern
  - `AOB_POS`: Position write pattern
  - `AOB_HEALTH`: Health/invulnerability pattern
  - `AOB_MAP`: In-game map marker destination pattern
  - `AOB_XYZ_PREFIX` + `AOB_XYZ_MID`: Static XYZ globals
  - `AOB_WORLD`: World offset pattern
  - `AOB_PHYS_DELTA_HOOK`: Physics delta hook point
  - `AOB_CAM`: Camera heading pattern
- Caches resolved RVAs in `cd_hook_offsets.json` with module size fingerprint
- Falls back to cache when AOB scan fails or is ambiguous

### Hook Installation
- Allocates a 4KB code cave block near hook addresses (or anywhere if far mode)
- Builds x64 assembly caves for each hook point
- Patches original instructions with 7-byte JMP rel32 (or 5/9 bytes for special cases)
- Handles predecessor hooks (e.g., Freedom Flyer, OpenFlight) via trampoline chaining

### Code Caves

| Cave | Purpose |
|------|---------|
| cave_a | Captures entity base into `td+0x18` |
| cave_b | Captures local XYZ into `td+0x20` |
| cave_c | Handles invulnerability flag |
| cave_d | Captures in-game map marker destination |
| cave_e | Physics delta hook — teleport and movement |
| cave_f | Camera heading capture |

## How XYZ is Captured

### Primary: Static XYZ Globals
- Found via `vmovsd [rip+disp32], xmm0` + `mov eax, [rsp+28]` + `mov [rip+disp32], eax`
- Returns absolute X, Y, Z addresses that can be read directly without hooks
- Most reliable method — no hook dependency

### Fallback: Physics Position Hook (hook_e)
- Hooks `movaps xmm0, xmm6` / `subss xmm9, xmm8` in the physics loop
- Captures `[r13]` (current physics position vector) into the allocated block
- Also saves RBX (entity pointer) at `tp+0x28` for heading calculation

### Fallback: Hook B (td+0x20)
- Older method — captures position when static XYZ is unavailable

## How Absolute Coordinates are Calculated

```
absolute = local + worldOffset
```

- `get_player_pos()` reads local XYZ from static addresses or physics hook
- `get_world_offsets()` reads 4 floats from the world offset address
- `get_player_abs()` adds world offset X and Z to local position
- Y is typically not offset (or offset Y is negligible)

## How Teleport Works

### Teleport Target Structure (`tp` block)
```
+0   float x    — target X (absolute or relative depending on mode)
+4   float y    — target Y
+8   float z    — target Z
+12  float 0.0  — padding
+16  uint32 flag — 1=teleport, 2=move, 0=none
+24  16 bytes   — save/restore area for xmm1 (teleport mode)
+40  16 bytes   — current physics position capture
```

### Teleport Flow (flag=1)
1. User or script writes target coords + flag=1 to `tp` block
2. Next physics frame, cave_e executes:
   - Saves xmm1 to `tp+24`
   - Computes `delta = target_static - current_physics`
   - Restores xmm1
   - Clears flag to 0
3. Original `subss xmm9, xmm8` runs with modified xmm0
4. `addps xmm0, [r13]` updates physics position to target
5. Game applies the new position

### Direct Write Fallback
- If physics hook is unavailable, writes directly to `phys_pos_addr` ([r13] vector)
- Bypasses the delta calculation entirely

### Teleport Abort
- Stores `_pre_teleport_pos` before each teleport
- `abort` command teleports back to stored coordinates

### Invulnerability
- Writes `0x01` to `inv` address for 10 seconds after teleport
- Prevents damage from falling or teleport-related issues

## How Calibration Works

### Purpose
Converts game coordinates (X, Z) to map coordinates (lng, lat) used by MapGenie/Greymane.

### Method
- Uses affine transformation with 3+ calibration points
- Falls back to linear transformation with 2 points
- Equation: `lng = ax*X + az*Z + ao`, `lat = bx*X + bz*Z + bo`
- Inverse transformation for map-click-to-game teleport

### Default Calibrations
Built-in for `pywel` and `abyss` realms with 2 reference points each.

### User Calibration
1. User goes to a recognizable in-game location
2. Clicks "Calibrate marker" on the map
3. Clicks the exact location on MapGenie
4. Point is saved to `%LOCALAPPDATA%\CD_Teleport\cd_calibration_{realm}.json`
5. With >= 3 points, affine calibration replaces the default linear one

## Which Concepts We Should Retain

1. **AOB scanning with cache** — robust pattern matching with RVA cache and module size fingerprinting
2. **Code cave architecture** — clean separation of scanning, allocation, cave building, and hook installation
3. **Physics delta hook for teleport** — elegant solution that works with the game's physics loop
4. **Static XYZ as primary source** — most reliable position reading method
5. **World offset addition** — simple but essential for absolute coordinates
6. **Hook predecessor detection** — compatibility with other mods (Freedom Flyer, OpenFlight)
7. **Calibration system** — affine/linear transform approach is sound
8. **Separation of concerns** — reader, scanner, cave builder, teleport as mixins

## Which Parts Should Be Redesigned

1. **Complete UI replacement** — no PyQt5/QWebEngineView with external map injection
2. **No WebSocket server** — local IPC between Python backend and frontend
3. **No browser extension** — all functionality in the standalone app
4. **New coordinate system** — our own map projection, not tied to MapGenie lng/lat
5. **New POI database** — our own categories, markers, and progress tracking
6. **New rendering pipeline** — our own map tiles and markers using MapLibre GL JS
7. **No dependency on pymem internals** — wrap memory operations in our own clean API
8. **Modular architecture** — replace monolithic mixin-based engine with clear module boundaries

## Parts Coupled to Old MapGenie Integration (DO NOT REUSE)

1. **JavaScript injection** (`inject.js`, `inject_parts/`) — entirely MapGenie-specific DOM manipulation
2. **WebSocket protocol** — designed for MapGenie browser extension communication
3. **MapGenie patch** (`mapgenie_patch.py`) — intercepts MapGenie network requests
4. **Greymane adapter** (`greymane_adapter.js`) — Greymane-specific JS bridge
5. **Location sync protocol** — propagates `location_toggle` across MapGenie clients
6. **Browser extension integration** — `cdcompanion://` URL scheme handling
7. **Overlay window positioning relative to browser** — game window detection for overlay placement
8. **MapGenie-specific coordinate conversion** — lng/lat tied to MapGenie's projection

## Architecture Decisions for New Application

### Backend (Python)
- Own memory engine with clean public API
- Own coordinate system with pluggable transforms
- Own persistence layer (JSON/SQLite)
- Local HTTP/WebSocket server for frontend communication

### Frontend (TypeScript + React + Vite + MapLibre GL JS)
- Bundled local application
- Loaded from `http://127.0.0.1:<local-port>` or bundled assets
- No external map website dependencies
- Own tile server or vector tile source

### Communication
- Local WebSocket or HTTP between Python and frontend
- JSON messages for position, commands, and state
- No browser extension needed

### Data
- Own POI database (JSON or SQLite)
- Own waypoint storage
- Own calibration data
- Own user preferences
