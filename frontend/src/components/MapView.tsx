import { useEffect, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, type MapLayerMouseEvent, type Marker, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import type { CatalogMarker } from "../catalog";
import { translations, type Language } from "../i18n";

import {
  GAME_BOUNDS,
  gameToMap,
  getDefaultCenter,
  getDefaultZoom,
  mapToGame,
  type MapAlignment,
} from "../map/coordinates";

export type Realm = "pywel" | "abyss";

export interface Waypoint {
  id: string;
  name: string;
  category: string;
  color: string;
  x: number;
  y: number;
  z: number;
  realm: Realm;
  note: string;
  createdAt: number;
  found?: boolean;
}

interface Props {
  realm: Realm;
  position: { x: number; y: number; z: number } | null;
  followPlayer: boolean;
  waypoints: Waypoint[];
  catalogMarkers: CatalogMarker[];
  visibleCatalogGroups: Set<string>;
  visibleCatalogTypes: Set<string>;
  selectedWaypointId: string | null;
  selectedCatalogMarkerId: string | null;
  foundCatalogMarkerIds: Set<string>;
  language: Language;
  alignment: MapAlignment;
  calibrationMode: boolean;
  onMapClick: (position: { x: number; y: number; z: number }) => void;
  onSelectWaypoint: (id: string) => void;
  onSelectCatalogMarker: (id: string) => void;
}

const CATALOG_GROUP_STYLES = [
  { id: "travel", color: "#62b4e8", icon: "point-of-interest.png" },
  { id: "quests", color: "#f0c45d", icon: "main-quest.png" },
  { id: "treasures", color: "#dca85b", icon: "treasure-chest.png" },
  { id: "abyss", color: "#b989e6", icon: "abyss-cresset.png" },
  { id: "ores", color: "#9fa8b2", icon: "pickaxe.png" },
  { id: "plants", color: "#72c98d", icon: "plants.png" },
  { id: "animals", color: "#8fc47b", icon: "animals.png" },
  { id: "shops", color: "#df9d65", icon: "money.png" },
  { id: "crafting", color: "#76b7aa", icon: "crafting-tools.png" },
  { id: "combat", color: "#e16e68", icon: "enemy.png" },
  { id: "activities", color: "#e58bc4", icon: "card-game.png" },
  { id: "other", color: "#a8adb5", icon: "point-of-interest.png" },
] as const;

const catalogSourceId = (groupId: string) => `catalog-${groupId}`;
const catalogClusterLayerId = (groupId: string) => `catalog-${groupId}-clusters`;
const catalogClusterIconLayerId = (groupId: string) => `catalog-${groupId}-cluster-icons`;
const catalogPointLayerId = (groupId: string) => `catalog-${groupId}-points`;
const markerImageId = (filename: string) => `marker:${filename}`;

function createStyle(realm: Realm): StyleSpecification {
  const sources: StyleSpecification["sources"] = {
    atlas: {
      type: "raster",
      tiles: [`/maps/${realm}/{z}/{y}/{x}.webp`],
      tileSize: 512,
      minzoom: 0,
      maxzoom: 6,
      attribution: "Local Crimson Atlas map",
    },
  };
  for (const group of CATALOG_GROUP_STYLES) {
    sources[catalogSourceId(group.id)] = {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
      cluster: true,
      clusterMaxZoom: 5,
      clusterRadius: 56,
    };
  }
  if (realm === "abyss") {
    sources["abyss-islands"] = {
      type: "raster",
      tiles: ["/maps/abyss-islands/{z}/{y}/{x}.webp"],
      tileSize: 512,
      minzoom: 0,
      maxzoom: 4,
    };
  }
  const layers: StyleSpecification["layers"] = [
    { id: "background", type: "background", paint: { "background-color": "#101316" } },
    {
      id: "atlas-map",
      type: "raster",
      source: "atlas",
      paint: { "raster-fade-duration": 0, "raster-resampling": "linear" },
    },
  ];
  if (realm === "abyss") {
    layers.push({
      id: "abyss-islands",
      type: "raster",
      source: "abyss-islands",
      paint: { "raster-fade-duration": 0, "raster-opacity": 1, "raster-resampling": "linear" },
    });
  }
  for (const group of CATALOG_GROUP_STYLES) {
    const source = catalogSourceId(group.id);
    layers.push(
      {
        id: catalogClusterLayerId(group.id),
        type: "circle",
        source,
        filter: ["has", "point_count"],
        paint: {
          "circle-radius": ["step", ["get", "point_count"], 12, 25, 14, 100, 16, 500, 18],
          "circle-color": group.color,
          "circle-stroke-color": "#f7f1e7",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.92,
        },
      },
      {
        id: catalogClusterIconLayerId(group.id),
        type: "symbol",
        source,
        filter: ["has", "point_count"],
        layout: {
          "icon-image": markerImageId(group.icon),
          "icon-size": 0.55,
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      },
      {
        id: catalogPointLayerId(group.id),
        type: "symbol",
        source,
        filter: ["!", ["has", "point_count"]],
        layout: {
          "icon-image": ["get", "iconId"],
          "icon-size": ["interpolate", ["linear"], ["zoom"], 2, 0.42, 5, 0.62, 6.5, 0.74],
          "icon-allow-overlap": false,
          "icon-padding": 2,
        },
        paint: {
          "icon-opacity": ["case", ["boolean", ["get", "found"], false], 0.32, 1],
        },
      },
    );
  }
  return { version: 8, sources, layers };
}

function makeWaypointElement(waypoint: Waypoint, selected: boolean): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `waypoint-marker${selected ? " selected" : ""}${waypoint.found ? " found" : ""}`;
  element.style.setProperty("--marker-color", waypoint.color);
  element.title = `${waypoint.name}\nX ${waypoint.x.toFixed(1)} · Y ${waypoint.y.toFixed(1)} · Z ${waypoint.z.toFixed(1)}`;
  element.setAttribute("aria-label", waypoint.name);
  element.innerHTML = '<span class="waypoint-dot"></span>';
  return element;
}

export default function MapView({
  realm,
  position,
  followPlayer,
  waypoints,
  catalogMarkers,
  visibleCatalogGroups,
  visibleCatalogTypes,
  selectedWaypointId,
  selectedCatalogMarkerId,
  foundCatalogMarkerIds,
  language,
  alignment,
  calibrationMode,
  onMapClick,
  onSelectWaypoint,
  onSelectCatalogMarker,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const styledRealmRef = useRef<Realm>(realm);
  const alignmentRef = useRef<MapAlignment>(alignment);
  const calibrationModeRef = useRef(calibrationMode);
  const playerMarkerRef = useRef<Marker | null>(null);
  const waypointMarkersRef = useRef<Marker[]>([]);
  const callbacksRef = useRef({ onMapClick, onSelectWaypoint, onSelectCatalogMarker });
  const [cursor, setCursor] = useState<{ x: number; z: number } | null>(null);

  callbacksRef.current = { onMapClick, onSelectWaypoint, onSelectCatalogMarker };
  alignmentRef.current = alignment;
  calibrationModeRef.current = calibrationMode;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const center = getDefaultCenter(realm);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: createStyle(realm),
      center: [center.x, center.y],
      zoom: getDefaultZoom(),
      minZoom: 0,
      maxZoom: 6.5,
      renderWorldCopies: false,
      maxBounds: [[-179.9, -85], [179.9, 85]],
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.scrollZoom.setWheelZoomRate(1 / 220);
    map.scrollZoom.setZoomRate(1 / 70);
    const pendingImages = new Set<string>();
    map.on("styleimagemissing", async (event) => {
      if (!event.id.startsWith("marker:") || pendingImages.has(event.id)) return;
      const filename = event.id.slice("marker:".length);
      if (!/^[a-z0-9-]+\.png$/.test(filename)) return;
      pendingImages.add(event.id);
      try {
        const image = await map.loadImage(`/marker-icons/${filename}`);
        if (!map.hasImage(event.id)) {
          const pixelRatio = Math.max(1, Math.min(8, image.data.width / 48));
          map.addImage(event.id, image.data, { pixelRatio });
        }
      } finally {
        pendingImages.delete(event.id);
      }
    });
    map.on("click", (event) => {
      if (event.defaultPrevented) return;
      const interactiveLayers = CATALOG_GROUP_STYLES
        .flatMap((group) => [
          catalogPointLayerId(group.id),
          catalogClusterLayerId(group.id),
          catalogClusterIconLayerId(group.id),
        ])
        .filter((layer) => map.getLayer(layer));
      if (
        !calibrationModeRef.current
        &&
        interactiveLayers.length > 0
        && map.queryRenderedFeatures(event.point, { layers: interactiveLayers }).length > 0
      ) return;
      const game = mapToGame({ x: event.lngLat.lng, y: event.lngLat.lat }, styledRealmRef.current, alignmentRef.current);
      if (
        game.x >= GAME_BOUNDS.minX && game.x <= GAME_BOUNDS.maxX
        && game.z >= GAME_BOUNDS.minZ && game.z <= GAME_BOUNDS.maxZ
      ) callbacksRef.current.onMapClick(game);
    });
    for (const group of CATALOG_GROUP_STYLES) {
      const pointLayer = catalogPointLayerId(group.id);
      const clusterLayer = catalogClusterLayerId(group.id);
      const clusterIconLayer = catalogClusterIconLayerId(group.id);
      map.on("click", pointLayer, (event) => {
        if (calibrationModeRef.current) return;
        event.preventDefault();
        const markerId = event.features?.[0]?.properties?.markerId;
        if (typeof markerId === "string") callbacksRef.current.onSelectCatalogMarker(markerId);
      });
      const expandCluster = async (event: MapLayerMouseEvent) => {
        if (calibrationModeRef.current) return;
        event.preventDefault();
        const feature = event.features?.[0];
        const clusterId = feature?.properties?.cluster_id;
        if (typeof clusterId !== "number" || feature?.geometry.type !== "Point") return;
        const source = map.getSource(catalogSourceId(group.id)) as GeoJSONSource | undefined;
        if (!source) return;
        const zoom = await source.getClusterExpansionZoom(clusterId);
        map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom, duration: 180 });
      };
      map.on("click", clusterLayer, expandCluster);
      map.on("click", clusterIconLayer, expandCluster);
      for (const layer of [pointLayer, clusterLayer, clusterIconLayer]) {
        map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
      }
    }
    map.on("mousemove", (event) => {
      const game = mapToGame({ x: event.lngLat.lng, y: event.lngLat.lat }, styledRealmRef.current, alignmentRef.current);
      setCursor({ x: game.x, z: game.z });
    });
    map.on("mouseout", () => setCursor(null));
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || styledRealmRef.current === realm) return;
    styledRealmRef.current = realm;
    mapRef.current.setStyle(createStyle(realm));
  }, [realm]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;
    const update = () => {
      if (cancelled) return;
      for (const group of CATALOG_GROUP_STYLES) {
        const source = map.getSource(catalogSourceId(group.id)) as GeoJSONSource | undefined;
        if (!source) continue;
        const features = visibleCatalogGroups.has(group.id)
          ? catalogMarkers
            .filter((marker) => marker.group === group.id && visibleCatalogTypes.has(marker.type))
            .map((marker) => {
              const position = gameToMap({ x: marker.x, y: marker.y || 0, z: marker.z }, realm, alignment);
              return {
                type: "Feature" as const,
                geometry: { type: "Point" as const, coordinates: [position.x, position.y] },
                properties: { markerId: marker.id, iconId: markerImageId(marker.icon), found: foundCatalogMarkerIds.has(marker.id) },
              };
            })
          : [];
        source.setData({ type: "FeatureCollection", features });
      }
    };
    map.on("style.load", update);
    update();
    return () => {
      cancelled = true;
      map.off("style.load", update);
    };
  }, [catalogMarkers, visibleCatalogGroups, visibleCatalogTypes, foundCatalogMarkerIds, realm, alignment]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!position) {
      playerMarkerRef.current?.remove();
      playerMarkerRef.current = null;
      return;
    }
    const target = gameToMap(position, realm, alignment);
    if (!playerMarkerRef.current) {
      const element = document.createElement("div");
      element.className = "player-marker";
      element.title = translations[language].currentPosition;
      element.innerHTML = '<span class="player-pulse"></span><span class="player-core"></span>';
      playerMarkerRef.current = new maplibregl.Marker({ element, anchor: "center" })
        .setLngLat([target.x, target.y])
        .addTo(map);
    } else {
      playerMarkerRef.current.getElement().title = translations[language].currentPosition;
      playerMarkerRef.current.setLngLat([target.x, target.y]);
    }
    if (followPlayer) map.easeTo({ center: [target.x, target.y], duration: 350 });
  }, [position, followPlayer, language, realm, alignment]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    waypointMarkersRef.current.forEach((marker) => marker.remove());
    waypointMarkersRef.current = waypoints
      .filter((waypoint) => waypoint.realm === realm)
      .map((waypoint) => {
        const element = makeWaypointElement(waypoint, waypoint.id === selectedWaypointId);
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          callbacksRef.current.onSelectWaypoint(waypoint.id);
        });
        const mapPosition = gameToMap(waypoint, realm, alignment);
        return new maplibregl.Marker({ element, anchor: "bottom" })
          .setLngLat([mapPosition.x, mapPosition.y])
          .addTo(map);
      });
    return () => {
      waypointMarkersRef.current.forEach((marker) => marker.remove());
      waypointMarkersRef.current = [];
    };
  }, [waypoints, realm, selectedWaypointId, alignment]);

  useEffect(() => {
    if (!selectedWaypointId) return;
    const waypoint = waypoints.find((item) => item.id === selectedWaypointId);
    if (!waypoint || waypoint.realm !== realm) return;
    const target = gameToMap(waypoint, realm, alignment);
    mapRef.current?.easeTo({ center: [target.x, target.y], zoom: Math.max(mapRef.current.getZoom(), 3), duration: 500 });
  }, [selectedWaypointId, waypoints, realm, alignment]);

  useEffect(() => {
    if (!selectedCatalogMarkerId) return;
    const marker = catalogMarkers.find((item) => item.id === selectedCatalogMarkerId);
    if (!marker) return;
    const target = gameToMap({ x: marker.x, y: marker.y || 0, z: marker.z }, realm, alignment);
    mapRef.current?.easeTo({ center: [target.x, target.y], zoom: Math.max(mapRef.current.getZoom(), 5.5), duration: 450 });
  }, [selectedCatalogMarkerId, catalogMarkers, realm, alignment]);

  return (
    <main className={`map-shell${calibrationMode ? " calibrating" : ""}`}>
      <div ref={containerRef} className="map-canvas" />
      <div className="map-realm-label">{realm === "pywel" ? translations[language].pywelMap : translations[language].abyss}</div>
      {cursor && (
        <div className="cursor-readout">
          X {cursor.x.toFixed(1)} <span /> Z {cursor.z.toFixed(1)}
        </div>
      )}
    </main>
  );
}
