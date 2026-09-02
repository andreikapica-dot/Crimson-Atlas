import { describe, expect, it } from "vitest";
import { setGroupTypesVisible, toggleTypeVisibility } from "../catalogVisibility";

const groupTypes = [{ id: "wolf" }, { id: "bear" }, { id: "fox" }];

describe("catalog visibility", () => {
  it("clears and restores every subtype with the parent category", () => {
    const hidden = setGroupTypesVisible(new Set(["wolf", "bear", "fox", "ore"]), groupTypes, false);
    expect([...hidden]).toEqual(["ore"]);
    expect([...setGroupTypesVisible(hidden, groupTypes, true)].sort()).toEqual(["bear", "fox", "ore", "wolf"]);
  });

  it("enables only the clicked subtype when its category is off", () => {
    const next = toggleTypeVisibility(new Set(["wolf", "bear", "fox", "ore"]), groupTypes, "bear", false);
    expect([...next].sort()).toEqual(["bear", "ore"]);
  });

  it("toggles one subtype without changing its siblings when the category is on", () => {
    const next = toggleTypeVisibility(new Set(["wolf", "bear", "fox"]), groupTypes, "bear", true);
    expect([...next].sort()).toEqual(["fox", "wolf"]);
  });
});
