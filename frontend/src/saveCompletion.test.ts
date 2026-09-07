import { describe, expect, it } from "vitest";
import type { CatalogMarker } from "./catalog";
import {
  matchSaveCompletion,
  type SaveCompletionMap,
  type SaveCompletionPacket,
} from "./saveCompletion";

const marker = (values: Partial<CatalogMarker>): CatalogMarker => ({
  id: "marker",
  type: "chest",
  name: "Chest",
  nameEn: "Chest",
  description: "",
  group: "treasures",
  groupLabel: "Treasures",
  groupColor: "#fff",
  icon: "chest.png",
  x: 0,
  y: 0,
  z: 0,
  realm: "pywel",
  note: "",
  sourceName: "test",
  sourceUrl: "test",
  sourceIds: [],
  ...values,
});

const packet = (values: Partial<SaveCompletionPacket>): SaveCompletionPacket => ({
  type: "save_completion",
  status: "ready",
  ...values,
});

describe("matchSaveCompletion", () => {
  it("matches completed main quests by their exact source key", () => {
    const markers = [
      marker({ id: "done", type: "main_quest", sourceIds: ["main_quest@-1.00:-2.00:1000027"] }),
      marker({ id: "open", type: "main_quest", sourceIds: ["main_quest@-1.00:-2.00:1000725"] }),
    ];
    expect([...matchSaveCompletion(markers, packet({ completedQuestKeys: [1000027] }))]).toEqual(["done"]);
  });

  it("marks only the terminal objective when a quest key has several map pins", () => {
    const markers = [
      marker({ id: "objective-1", type: "main_quest", sourceIds: ["main_quest@-1.00:-2.00:1000027"] }),
      marker({ id: "objective-2", type: "main_quest", sourceIds: ["main_quest@-3.00:-4.00:1000027"] }),
      marker({ id: "objective-final", type: "main_quest", sourceIds: ["main_quest@-5.00:-6.00:1000027"] }),
    ];
    expect([...matchSaveCompletion(markers, packet({ completedQuestKeys: [1000027] }))]).toEqual([
      "objective-final",
    ]);
  });

  it("matches a completed positioned object only within its realm, type, and radius", () => {
    const markers = [
      marker({ id: "near", x: 10, z: 10 }),
      marker({ id: "wrong-type", type: "bonfire", x: 10, z: 10 }),
      marker({ id: "wrong-realm", realm: "abyss", x: 10, z: 10 }),
      marker({ id: "far", x: 100, z: 100 }),
    ];
    const result = matchSaveCompletion(markers, packet({
      completedLocations: [{ x: 11, y: 500, z: 11, realm: "pywel", markerTypes: ["chest"] }],
    }));
    expect([...result]).toEqual(["near"]);
  });

  it("honours the stricter radius carried by exact gimmick evidence", () => {
    const markers = [marker({ id: "almost", type: "sealed_artifact", x: 1.1, z: 0 })];
    const result = matchSaveCompletion(markers, packet({
      completedLocations: [{
        x: 0,
        y: 500,
        z: 0,
        realm: "pywel",
        markerTypes: ["sealed_artifact"],
        maxDistance: 1,
      }],
    }));
    expect([...result]).toEqual([]);
  });

  it("never substitutes a nearby marker for exact object evidence", () => {
    const markers = [
      marker({ id: "exact", type: "weapon_display", x: -10.125, z: -20.25 }),
      marker({ id: "nearby", type: "weapon_display", x: -10.124, z: -20.25 }),
    ];
    const result = matchSaveCompletion(markers, packet({
      completedLocations: [{
        x: -10.125,
        y: 500,
        z: -20.25,
        realm: "pywel",
        markerTypes: ["weapon_display"],
        matchMode: "exact",
      }],
    }));
    expect([...result]).toEqual(["exact"]);
  });

  it("matches a discovered facility from its absolute save position", () => {
    const markers = [
      marker({ id: "anvil", type: "crafting_anvil", x: -10139.864, z: -4705.406 }),
      marker({ id: "nearby", type: "bonfire", x: -10139.864, z: -4705.406 }),
    ];
    const result = matchSaveCompletion(markers, packet({
      discoveredLocations: [{
        x: -10139.864,
        y: 615.942,
        z: -4705.406,
        realm: "pywel",
        markerTypes: ["crafting_anvil"],
        maxDistance: 3,
      }],
    }));
    expect([...result]).toEqual(["anvil"]);
  });

  it("maps learned knowledge through the offline lookup", () => {
    const markers = [
      marker({ id: "learned-node", type: "faction_node", sourceIds: ["faction_node_11"] }),
      marker({ id: "unknown-node", type: "faction_node", sourceIds: ["faction_node_12"] }),
    ];
    const completionMap: SaveCompletionMap = {
      version: 1,
      knowledgeSourceIds: { "1001674": ["faction_node_11"] },
    };
    const result = matchSaveCompletion(
      markers,
      packet({ completedKnowledgeKeys: [1001674] }),
      completionMap,
    );

    expect([...result]).toEqual(["learned-node"]);
  });

  it("marks a verified faction activity only when its whole mission group is completed", () => {
    const markers = [
      marker({ id: "faction-a", type: "faction_quest", sourceIds: ["faction_quest@a:b:1"] }),
      marker({ id: "faction-b", type: "faction_quest", sourceIds: ["faction_quest@c:d:2"] }),
    ];
    const completionMap: SaveCompletionMap = {
      version: 2,
      knowledgeSourceIds: {},
      missionSourceRules: [{
        missionKeys: [1001278, 1002692],
        sourceIds: ["faction_quest@a:b:1", "faction_quest@c:d:2"],
      }],
    };

    expect([...matchSaveCompletion(
      markers,
      packet({ completedMissionKeys: [1001278] }),
      completionMap,
    )]).toEqual([]);
    expect([...matchSaveCompletion(
      markers,
      packet({ completedMissionKeys: [1001278, 1002692] }),
      completionMap,
    )]).toEqual(["faction-a", "faction-b"]);
  });
});
