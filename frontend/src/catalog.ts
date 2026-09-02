import type { Realm } from "./components/MapView";
import { catalogGroupLabels, englishGroupDescriptions, type Language } from "./i18n";

export interface CatalogGroup {
  id: string;
  label: string;
  color: string;
  icon: string;
}

export interface CatalogType {
  id: string;
  name: string;
  nameEn: string;
  description?: string;
  group: string;
  icon: string;
}

export interface CatalogData {
  markerCount: number;
  teleportableCount: number;
  source: { name: string; url: string };
  groups: CatalogGroup[];
  types: CatalogType[];
  realms: Record<Realm, Array<{ type: number; points: Array<[number, number | null, number]> }>>;
}

export interface CatalogOverride {
  name?: string;
  x?: number;
  y?: number | null;
  z?: number;
  note?: string;
}

export interface CatalogMarker {
  id: string;
  type: string;
  name: string;
  nameEn: string;
  description: string;
  group: string;
  groupLabel: string;
  groupColor: string;
  icon: string;
  x: number;
  y: number | null;
  z: number;
  realm: Realm;
  note: string;
  sourceName: string;
  sourceUrl: string;
}

export function flattenCatalog(
  catalog: CatalogData,
  realm: Realm,
  overrides: Record<string, CatalogOverride>,
  language: Language = "ru",
): CatalogMarker[] {
  const groups = new Map(catalog.groups.map((group) => [group.id, group]));
  const markers: CatalogMarker[] = [];
  for (const typeGroup of catalog.realms[realm] || []) {
    const type = catalog.types[typeGroup.type];
    const group = groups.get(type.group)!;
    typeGroup.points.forEach((point, pointIndex) => {
      const id = `catalog:${realm}:${typeGroup.type}:${pointIndex}`;
      const override = overrides[id] || {};
      markers.push({
        id,
        type: type.id,
        name: override.name || (language === "en" ? type.nameEn : type.name),
        nameEn: type.nameEn,
        description: language === "en" ? (englishGroupDescriptions[type.group] || "") : (type.description || ""),
        group: type.group,
        groupLabel: catalogGroupLabels[language][group.id] || group.label,
        groupColor: group.color,
        icon: type.icon,
        x: override.x ?? point[0],
        y: override.y === undefined ? point[1] : override.y,
        z: override.z ?? point[2],
        realm,
        note: override.note || "",
        sourceName: catalog.source.name,
        sourceUrl: catalog.source.url,
      });
    });
  }
  return markers;
}
