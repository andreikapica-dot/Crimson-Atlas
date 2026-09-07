import { describe, expect, it } from "vitest";
import { flattenCatalog, type CatalogData } from "../catalog";

const catalog: CatalogData = {
  markerCount: 2,
  teleportableCount: 1,
  source: { name: "Source", url: "https://example.com" },
  groups: [{ id: "travel", label: "Перемещение", color: "#fff", icon: "/group.webp" }],
  types: [{ id: "waypoint", name: "Точка пути", nameEn: "Waypoint", translations: { ko: "경유지" }, group: "travel", icon: "/point.webp" }],
  realms: {
    pywel: [{ type: 0, points: [[10, 20, 30], [40, null, 50]] }],
    abyss: [],
  },
};

describe("marker catalog", () => {
  it("flattens compact points without changing game coordinate order", () => {
    const markers = flattenCatalog(catalog, "pywel", {});
    expect(markers[0]).toMatchObject({ id: "catalog:pywel:0:0", x: 10, y: 20, z: 30 });
    expect(markers[1]).toMatchObject({ id: "catalog:pywel:0:1", x: 40, y: null, z: 50 });
  });

  it("applies editable local overrides, including a previously unknown Y", () => {
    const markers = flattenCatalog(catalog, "pywel", {
      "catalog:pywel:0:1": { name: "Проверенная точка", x: 41, y: 101, z: 51, note: "Проверено в игре" },
    });
    expect(markers[1]).toMatchObject({ name: "Проверенная точка", x: 41, y: 101, z: 51, note: "Проверено в игре" });
  });

  it("uses English catalog names, groups, and descriptions without changing coordinates", () => {
    const [marker] = flattenCatalog(catalog, "pywel", {}, "en");
    expect(marker).toMatchObject({
      name: "Waypoint",
      groupLabel: "Travel and locations",
      description: "A useful location or landmark for exploring the world.",
      x: 10,
      y: 20,
      z: 30,
    });
  });

  it("uses translated interface groups and safe English marker-name fallback for new languages", () => {
    const [marker] = flattenCatalog(catalog, "pywel", {}, "ko");
    expect(marker).toMatchObject({ name: "경유지", groupLabel: "여행 및 장소", x: 10, z: 30 });
  });
});
