import { describe, expect, it } from "vitest";
import {
  GAME_BOUNDS,
  alignToClickedPosition,
  detectRealm,
  gameToMap,
  getDefaultCenter,
  getDefaultZoom,
  isWithinGameBounds,
  mapToGame,
} from "../map/coordinates";

describe("coordinates", () => {
  it.each([
    { x: 0, y: 0, z: 0 },
    { x: 1234.5, y: 27, z: -678.9 },
    { x: GAME_BOUNDS.minX, y: 0, z: GAME_BOUNDS.minZ },
    { x: GAME_BOUNDS.maxX, y: 0, z: GAME_BOUNDS.maxZ },
  ])("round trips uncorrected game position $x/$z", (original) => {
    const back = mapToGame(gameToMap(original, "abyss"), "abyss");
    expect(back.x).toBeCloseTo(original.x, 5);
    expect(back.z).toBeCloseTo(original.z, 5);
  });

  it("round trips the screenshot-verified Pywel area", () => {
    const original = { x: -9065.5, y: 479.3, z: -4277.4 };
    const back = mapToGame(gameToMap(original, "pywel"), "pywel");
    expect(back.x).toBeCloseTo(original.x, 5);
    expect(back.z).toBeCloseTo(original.z, 5);
  });

  it("calculates a persistent alignment from the clicked true position", () => {
    const current = { x: 4, z: -7 };
    const actual = { x: -100, y: 600, z: 200 };
    const clicked = { x: -85, y: 0, z: 175 };
    const alignment = alignToClickedPosition(current, actual, clicked);
    expect(alignment).toEqual({ x: 19, z: -32 });
    expect(gameToMap(actual, "pywel", alignment)).toEqual(gameToMap(clicked, "pywel", current));
  });

  it("round trips Abyss positions independently from Pywel correction", () => {
    const original = { x: -10665.4, y: 1795.2, z: -3700.8 };
    const back = mapToGame(gameToMap(original, "abyss"), "abyss");
    expect(back.x).toBeCloseTo(original.x, 5);
    expect(back.z).toBeCloseTo(original.z, 5);
  });

  it("places opposite game bounds at opposite map corners", () => {
    const northWest = gameToMap({ x: GAME_BOUNDS.minX, y: 0, z: GAME_BOUNDS.maxZ }, "abyss");
    const southEast = gameToMap({ x: GAME_BOUNDS.maxX, y: 0, z: GAME_BOUNDS.minZ }, "abyss");
    expect(northWest.x).toBeLessThan(-179.9);
    expect(northWest.y).toBeGreaterThan(85.0);
    expect(southEast.x).toBeGreaterThan(179.9);
    expect(southEast.y).toBeLessThan(-85.0);
  });

  it("uses game origin as the default center", () => {
    expect(getDefaultCenter()).toEqual(gameToMap({ x: 0, y: 0, z: 0 }));
    expect(getDefaultZoom()).toBeGreaterThan(0);
  });

  it("validates the calibrated game bounds", () => {
    expect(isWithinGameBounds(0, 0)).toBe(true);
    expect(isWithinGameBounds(GAME_BOUNDS.minX - 1, 0)).toBe(false);
    expect(isWithinGameBounds(0, GAME_BOUNDS.maxZ + 1)).toBe(false);
  });

  it("detects realm with transition hysteresis", () => {
    expect(detectRealm(1600, "pywel")).toBe("abyss");
    expect(detectRealm(1400, "abyss")).toBe("abyss");
    expect(detectRealm(1200, "abyss")).toBe("pywel");
    expect(detectRealm(1400, "pywel")).toBe("pywel");
  });
});
