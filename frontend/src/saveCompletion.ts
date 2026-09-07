import type { CatalogMarker } from "./catalog";

export interface SaveCompletedLocation {
  x: number;
  y: number;
  z: number;
  realm: "pywel" | "abyss";
  markerTypes: string[];
  maxDistance?: number;
  matchMode?: "exact";
}

export interface SaveCompletionPacket {
  type: "save_completion";
  status: "waiting" | "not_found" | "error" | "ready";
  completedQuestKeys?: number[];
  completedMissionKeys?: number[];
  completedKnowledgeKeys?: number[];
  completedSceneObjectUuids?: number[][];
  completedLocations?: SaveCompletedLocation[];
  discoveredLocations?: SaveCompletedLocation[];
  completedQuestCount?: number;
  completedMissionCount?: number;
  completedSceneObjectCount?: number;
  matchedLocationCount?: number;
  discoveredLocationCount?: number;
  learnedKnowledgeCount?: number;
  saveSlot?: string;
  error?: string;
}

export interface SaveCompletionMap {
  version: number;
  knowledgeSourceIds: Record<string, string[]>;
  missionSourceRules?: Array<{
    missionKeys: number[];
    sourceIds: string[];
  }>;
}

function questKeyFromSourceId(sourceId: string): number | null {
  const match = sourceId.match(/^main_quest@[^:]+:[^:]+:(\d+)$/);
  return match ? Number(match[1]) : null;
}

export function matchSaveCompletion(
  markers: CatalogMarker[],
  packet: SaveCompletionPacket | null,
  completionMap: SaveCompletionMap | null = null,
  maxDistance = 30,
): Set<string> {
  const matched = new Set<string>();
  if (!packet || packet.status !== "ready") return matched;

  const completedQuests = new Set(packet.completedQuestKeys || []);
  const terminalQuestMarkers = new Map<number, string>();
  for (const marker of markers) {
    if (marker.type !== "main_quest") continue;
    marker.sourceIds.forEach((sourceId) => {
      const questKey = questKeyFromSourceId(sourceId);
      if (questKey !== null && completedQuests.has(questKey)) {
        // A quest can publish several objective pins with the same quest key.
        // The final pin in source order is the completed destination; marking
        // every objective makes one completed quest look like 5-10 finds.
        terminalQuestMarkers.set(questKey, marker.id);
      }
    });
  }
  terminalQuestMarkers.forEach((markerId) => matched.add(markerId));

  if (completionMap) {
    const markerIdBySource = new Map<string, string>();
    markers.forEach((marker) => {
      marker.sourceIds.forEach((sourceId) => markerIdBySource.set(sourceId, marker.id));
    });
    (packet.completedKnowledgeKeys || []).forEach((knowledgeKey) => {
      (completionMap.knowledgeSourceIds[String(knowledgeKey)] || []).forEach((sourceId) => {
        const markerId = markerIdBySource.get(sourceId);
        if (markerId) matched.add(markerId);
      });
    });
    const completedMissions = new Set(packet.completedMissionKeys || []);
    (completionMap.missionSourceRules || []).forEach((rule) => {
      if (!rule.missionKeys.length || !rule.missionKeys.every((key) => completedMissions.has(key))) return;
      rule.sourceIds.forEach((sourceId) => {
        const markerId = markerIdBySource.get(sourceId);
        if (markerId) matched.add(markerId);
      });
    });
  }

  const positionedLocations = [
    ...(packet.completedLocations || []),
    ...(packet.discoveredLocations || []),
  ];
  for (const location of positionedLocations) {
    if (!Number.isFinite(location.x) || !Number.isFinite(location.z)) continue;
    const allowedTypes = new Set(location.markerTypes || []);
    if (location.matchMode === "exact") {
      for (const marker of markers) {
        if (marker.realm !== location.realm || !allowedTypes.has(marker.type)) continue;
        if (Math.round(marker.x * 1000) === Math.round(location.x * 1000)
          && Math.round(marker.z * 1000) === Math.round(location.z * 1000)) {
          matched.add(marker.id);
        }
      }
      continue;
    }
    let best: CatalogMarker | null = null;
    let bestDistanceSquared = Number.POSITIVE_INFINITY;
    for (const marker of markers) {
      if (marker.realm !== location.realm || !allowedTypes.has(marker.type)) continue;
      const dx = marker.x - location.x;
      const dz = marker.z - location.z;
      const distanceSquared = dx * dx + dz * dz;
      if (distanceSquared < bestDistanceSquared) {
        best = marker;
        bestDistanceSquared = distanceSquared;
      }
    }
    const locationDistance = Number.isFinite(location.maxDistance)
      ? Math.max(0, Number(location.maxDistance))
      : maxDistance;
    if (best && bestDistanceSquared <= locationDistance * locationDistance) matched.add(best.id);
  }

  return matched;
}
