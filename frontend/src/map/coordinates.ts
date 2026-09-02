/** Coordinate projection used by the local TH.GL-derived tile pyramid.
 *
 * The game X/Z plane is first mapped into the 512px zoom-0 tile world and
 * then converted to MapLibre's Web Mercator longitude/latitude space.
 */

export interface GamePosition {
  x: number;
  y: number;
  z: number;
}

export interface MapPosition {
  x: number;
  y: number;
}

export type WorldRealm = "pywel" | "abyss";

export interface MapAlignment {
  x: number;
  z: number;
}

export function detectRealm(y: number, previous: WorldRealm | null = null): WorldRealm {
  if (previous === "abyss") return y < 1300 ? "pywel" : "abyss";
  if (previous === "pywel") return y > 1500 ? "abyss" : "pywel";
  return y > 1400 ? "abyss" : "pywel";
}

export const TILE_SIZE = 512;
export const MAP_SCALE = 0.026307676497790568;
export const MAP_ORIGIN_X = 431.0512794162984;
export const MAP_ORIGIN_Y = 215.5651012228959;

export const ZERO_ALIGNMENT: MapAlignment = { x: 0, z: 0 };

export const GAME_BOUNDS = {
  minX: -16384,
  maxX: 3076,
  minZ: -11267,
  maxZ: 8193,
} as const;

const MAX_LATITUDE = 85.0511287798066;

function pixelToLngLat(pixelX: number, pixelY: number): MapPosition {
  const x = pixelX / TILE_SIZE;
  const y = pixelY / TILE_SIZE;
  const lng = x * 360 - 180;
  const lat = (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI;
  return { x: lng, y: Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, lat)) };
}

function lngLatToPixel(map: MapPosition): { x: number; y: number } {
  const lat = Math.max(-MAX_LATITUDE, Math.min(MAX_LATITUDE, map.y));
  const latRadians = (lat * Math.PI) / 180;
  return {
    x: ((map.x + 180) / 360) * TILE_SIZE,
    y: ((1 - Math.asinh(Math.tan(latRadians)) / Math.PI) / 2) * TILE_SIZE,
  };
}

export function gameToMap(game: GamePosition, _realm: WorldRealm = "pywel", alignment: MapAlignment = ZERO_ALIGNMENT): MapPosition {
  return pixelToLngLat(
    MAP_SCALE * (game.x + alignment.x) + MAP_ORIGIN_X,
    -MAP_SCALE * (game.z + alignment.z) + MAP_ORIGIN_Y,
  );
}

export function mapToGame(map: MapPosition, _realm: WorldRealm = "pywel", alignment: MapAlignment = ZERO_ALIGNMENT): GamePosition {
  const pixel = lngLatToPixel(map);
  return {
    x: (pixel.x - MAP_ORIGIN_X) / MAP_SCALE - alignment.x,
    y: 0,
    z: (MAP_ORIGIN_Y - pixel.y) / MAP_SCALE - alignment.z,
  };
}

/** Calculate the saved offset after the user clicks the true player location. */
export function alignToClickedPosition(
  current: MapAlignment,
  actual: GamePosition,
  clicked: GamePosition,
): MapAlignment {
  return {
    x: current.x + clicked.x - actual.x,
    z: current.z + clicked.z - actual.z,
  };
}

export function getDefaultCenter(realm: WorldRealm = "pywel"): MapPosition {
  return gameToMap({ x: 0, y: 0, z: 0 }, realm);
}

export function getDefaultZoom(): number {
  return 1.35;
}

export function isWithinGameBounds(x: number, z: number): boolean {
  return x >= GAME_BOUNDS.minX && x <= GAME_BOUNDS.maxX
    && z >= GAME_BOUNDS.minZ && z <= GAME_BOUNDS.maxZ;
}
