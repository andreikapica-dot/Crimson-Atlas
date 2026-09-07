# Coordinate System

## Purpose

The coordinate system handles:

1. Game coordinate representation (X, Y, Z)
2. World offset application
3. Map coordinate conversion (lng/lat or tile coordinates)
4. Calibration management
5. Realm detection (Pywel, Abyss, etc.)
6. Heading calculation

## Game Coordinates

### Format
- X: East-West axis (negative = west, positive = east)
- Y: Height axis (negative = below ground, positive = above)
- Z: North-South axis (negative = south, positive = north)

### Realms
The game world is divided into realms. Our system supports:

- `pywel`: Main continent
- `abyss`: High-altitude realm (Y > 1400)
- Future realms as discovered

Realm detection is based on Y coordinate threshold:
```python
realm = "abyss" if y > ABYSS_HEIGHT_THRESHOLD else "pywel"
```

### World Offset
Absolute position = local position + world offset

```python
abs_x = local_x + world_offset_x
abs_y = local_y  # Y typically not offset
abs_z = local_z + world_offset_z
```

The world offset is read from a static address in the game's memory.

## Map Coordinate System

### Our Own Projection
Unlike CD Companion (which uses MapGenie's lng/lat), we use our own coordinate system:

**Option A: Tile-based (Mercator)**
- Map divided into tiles at various zoom levels
- Each tile has a unique identifier (z/x/y)
- Player position projected to tile coordinates
- Standard for web mapping

**Option B: Normalized game coordinates**
- Direct mapping from game units to pixel coordinates
- Simple linear or affine transform
- No projection complexity

**Recommendation: Tile-based Mercator**
- Compatible with MapLibre GL JS
- Easy to generate offline tiles
- Standard zoom/pan/rotate behavior
- Well-understood math

### Coordinate Transforms

#### Game to Map
```python
def game_to_map(game_x: float, game_z: float, calibration: Calibration) -> tuple[float, float]:
    # Apply affine or linear transform
    # Returns (map_x, map_y) in tile coordinates or pixels
```

#### Map to Game
```python
def map_to_game(map_x: float, map_y: float, calibration: Calibration) -> tuple[float, float] | None:
    # Inverse transform
    # Returns (game_x, game_z) or None if invalid
```

## Calibration System

### Purpose
Convert between game coordinates and map coordinates using reference points.

### Methods

#### Linear (2 points)
```python
sx = (lng1 - lng0) / (gx1 - gx0)
ox = lng0 - gx0 * sx
sz = (lat1 - lat0) / (gz1 - gz0)
oz = lat0 - gz0 * sz

lng = gx * sx + ox
lat = gz * sz + oz
```

#### Affine (3+ points)
```python
# Solve 3x3 system for lng = ax*X + az*Z + ao
# Solve 3x3 system for lat = bx*X + bz*Z + bo

lng = ax * gx + az * gz + ao
lat = bx * gx + bz * gz + bo
```

### Default Calibrations
Built-in calibrations for each realm with minimum 2 reference points.

### User Calibration
1. User stands at recognizable location
2. Reads current game coordinates from debug panel
3. Clicks corresponding location on our map
4. Point is added to calibration set
5. With >= 3 points, affine calibration is computed
6. Saved to user data directory

### Validation
- Minimum 2 points for linear
- Minimum 3 points for affine
- Minimum span check (points too close = unreliable)
- Determinant check for affine (non-degenerate)

## Heading Calculation

### Player Heading
```python
def player_heading(fx: float, fz: float) -> float | None:
    # From forward vector (negated because entity+0x80/0x88 points backward)
    if fx * fx + fz * fz < 1e-6:
        return None
    return math.atan2(-fx, -fz) * 180.0 / math.pi
```

Range: 0-360 degrees

### Camera Heading
```python
def camera_heading(raw_degrees: float) -> float | None:
    # Signed degrees, -180 to 180
    if raw_degrees == 0.0:
        return None
    return raw_degrees
```

## Height Handling

### Default Teleport Y
When teleporting to a map click with no height data:
- Pywel: `DEFAULT_TELEPORT_Y = 1000.0`
- Abyss: `ABYSS_DEFAULT_Y = 2400.0`

### Height Boost
Applied to all teleports to prevent ground clipping:
```python
TELEPORT_Y = target_y + HEIGHT_BOOST  # HEIGHT_BOOST = 10.0
```

## Coordinate Precision

### Internal Storage
- Game coordinates: float32 (as read from memory)
- Map coordinates: float64 for precision

### Display
- Game XYZ: 2 decimal places
- Map coordinates: 8 decimal places (lng/lat precision)
- Heading: 1 decimal place

## Units

### Game Units
- 1 unit = 1 meter (approximate)
- Used for distance calculations
- Used for teleport coordinates

### Map Units
- Mercator projection meters at zoom level
- Or tile coordinates (integers)

## Distance Calculations

```python
def distance_2d(x1: float, z1: float, x2: float, z2: float) -> float:
    dx = x2 - x1
    dz = z2 - z1
    return math.sqrt(dx * dx + dz * dz)

def distance_3d(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    return math.sqrt(dx * dx + dy * dy + dz * dz)
```

## Edge Cases

### Zero Coordinates
- (0, 0, 0) typically indicates invalid/uninitialized position
- Should be filtered out

### Loading Screens
- Position may jump or reset during loading
- Use position change threshold to filter noise

### Realm Transitions
- Player may briefly have invalid Y during teleport
- Realm detection should use hysteresis

### Negative Coordinates
- Game uses signed coordinates throughout
- Map projection must handle negative values correctly
