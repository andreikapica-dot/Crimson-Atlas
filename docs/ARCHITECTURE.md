# Architecture

## Overview

A standalone Crimson Desert companion application built from scratch with no dependency on CD Companion or any external map service.

```
CrimsonDesert.exe
        ↓
Memory Engine (Python)
        ↓
Player World Position
        ↓
Coordinate Engine (Python)
        ↓
Local HTTP/WebSocket Server
        ↓
Frontend (TypeScript/React/MapLibre)
        ↓
User Interaction (Teleport, Waypoints, Nearby, POIs)
```

## System Components

### 1. Memory Engine (`memory/`)
- **process.py**: Process attachment/detachment, module enumeration
- **scanner.py**: AOB pattern scanning with caching
- **signatures.py**: All game-version-specific AOB patterns in one place
- **hooks.py**: Code cave builder, JMP patching, hook installation/removal
- **player_reader.py**: Position, heading, and camera data extraction
- **teleport.py**: Teleportation via physics delta injection and direct write

### 2. Coordinate Engine (`coordinates/`)
- **world.py**: World coordinate representation, realms, offsets
- **calibration.py**: Affine/linear transform calibration
- **transforms.py**: Game-to-map and map-to-game coordinate transforms

### 3. Map System (`map/`)
- **renderer**: MapLibre GL JS based renderer
- **player_layer**: Player arrow and position tracking
- **poi_layer**: POI markers with categories and filters
- **waypoint_layer**: User waypoints with save/delete/teleport
- **teleport_layer**: Teleport destination visualization

### 4. Data Layer (`data/`)
- **poi_database**: POI storage (JSON or SQLite)
- **categories**: POI category definitions
- **user_progress**: Found locations tracking

### 5. Services (`services/`)
- **nearby**: Nearby location search and display
- **search**: POI and waypoint search
- **persistence**: Save/load waypoints, calibration, settings

### 6. UI (`ui/`)
- **main_window**: Main application window
- **settings**: Settings panel
- **compact_mode**: Compact overlay mode
- **debug_panel**: Raw coordinate display for debugging

### 7. Application Shell (`app/`)
- **main.py**: Entry point, process lifecycle
- **config**: Configuration management
- **local_server**: HTTP/WebSocket server for frontend

## Technology Stack

### Backend
- Python 3.11+
- pymem for memory reading
- ctypes for Windows API calls
- websockets for local communication
- SQLite/JSON for persistence

### Frontend
- TypeScript
- React
- Vite
- MapLibre GL JS
- Custom CSS (no external UI framework dependency)

### Desktop Integration
- Python desktop shell with embedded browser (CEF/WebView2) OR
- Separate frontend dev server + Python backend communication via localhost

## Communication Protocol

### Backend → Frontend
```json
{
  "type": "position",
  "x": -8432.1,
  "y": 12.4,
  "z": 3201.7,
  "realm": "pywel",
  "heading": 45.2
}
```

```json
{
  "type": "status",
  "status": "attached|scanning|disconnected",
  "teleportAvailable": true
}
```

### Frontend → Backend
```json
{
  "cmd": "teleport",
  "x": -8432.1,
  "y": 12.4,
  "z": 3201.7
}
```

```json
{
  "cmd": "save_waypoint",
  "name": "My Spot"
}
```

## Data Flow

1. **Memory Read Loop** (60 Hz)
   - Reads position from game memory
   - Applies world offset
   - Publishes to position queue

2. **Coordinate Transform** (on position update)
   - Converts game XYZ to map coordinates
   - Applies calibration if available

3. **Frontend Update** (requestAnimationFrame)
   - Receives position updates via WebSocket
   - Interpolates player marker
   - Renders map layers

4. **Expensive Operations** (throttled)
   - Nearby search: 2-5 Hz
   - UI statistics: 2-10 Hz
   - POI filtering: on filter change only

## File Structure

```
cd_companion/
├── app/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   └── local_server.py      # HTTP/WebSocket server
├── memory/
│   ├── __init__.py
│   ├── process.py           # Process attachment
│   ├── scanner.py           # AOB scanning
│   ├── signatures.py        # AOB patterns per version
│   ├── hooks.py             # Code cave builder
│   ├── player_reader.py     # Position/heading reader
│   └── teleport.py          # Teleport implementation
├── coordinates/
│   ├── __init__.py
│   ├── world.py             # World coordinate types
│   ├── calibration.py       # Calibration management
│   └── transforms.py        # Coordinate transforms
├── map/
│   ├── __init__.py
│   ├── renderer/            # MapLibre renderer setup
│   ├── layers/              # Map layer implementations
│   └── tiles/               # Tile generation tools
├── data/
│   ├── __init__.py
│   ├── poi_database.py      # POI storage
│   ├── categories.py        # Category definitions
│   └── user_progress.py     # Found locations
├── services/
│   ├── __init__.py
│   ├── nearby.py            # Nearby search
│   ├── search.py            # Search functionality
│   └── persistence.py       # Save/load managers
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # Main window
│   ├── settings.py          # Settings panel
│   ├── compact_mode.py      # Compact overlay
│   └── debug_panel.py       # Debug coordinates
├── frontend/                # TypeScript/React/Vite app
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── styles/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── tools/
│   ├── data_collection.py   # POI data collection
│   ├── tile_generation.py   # Tile generation
│   └── validation.py        # Data validation
├── tests/
│   ├── __init__.py
│   ├── test_memory.py
│   ├── test_coordinates.py
│   ├── test_teleport.py
│   └── test_services.py
├── docs/
│   ├── REFERENCE_ANALYSIS.md
│   ├── ARCHITECTURE.md
│   ├── MEMORY_ENGINE.md
│   └── COORDINATES.md
├── pyproject.toml
├── requirements.txt
├── README.md
└── LICENSE
```

## Design Principles

1. **No external dependencies** — Everything runs locally
2. **Modular architecture** — Clear boundaries between components
3. **Version-tolerant signatures** — Easy to update for game patches
4. **Clean public APIs** — Internal implementation can change without breaking consumers
5. **Separation of rates** — Memory read, map render, and UI calc run at different frequencies
6. **Graceful degradation** — Feature detection, not version detection
7. **Testability** — Pure functions for coordinate math, mockable memory interface
