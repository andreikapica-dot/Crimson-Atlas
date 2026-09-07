import { useEffect, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, type MapLayerMouseEvent, type Marker, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import type { CatalogMarker } from "../catalog";
import type { DisplaySettings } from "../displaySettings";
import { translations, type Language } from "../i18n";
import type { NavigationTarget } from "../navigationState";

import {
  GAME_BOUNDS,
  gameToMap,
  getDefaultCenter,
  getDefaultZoom,
  mapToGame,
  type MapAlignment,
} from "../map/coordinates";

export type CrimsonRoutePoint = {
  x: number;
  y: number;
  z: number;
};

export type CrimsonRouteLine = {
  index: number;
  primary: boolean;
  points: CrimsonRoutePoint[];
  pointCount: number;
  polylineDistance: number;
  roadDistance: number;
  endPoint?: { x: number; y: number; z: number } | null;
};

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
  displaySettings: DisplaySettings;
  language: Language;
  alignment: MapAlignment;
  calibrationMode: boolean;
  onMapClick: (position: { x: number; y: number; z: number }) => void;
  onSelectWaypoint: (id: string) => void;
  onSelectCatalogMarker: (id: string) => void;
  crimsonRoutes: CrimsonRouteLine[];
  crimsonRouteRealm: Realm | null;
  routeTarget?: NavigationTarget | null;
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
const catalogSelectionLayerId = (groupId: string) => `catalog-${groupId}-selection`;
const markerImageId = (filename: string) => `marker:${filename}`;

function createStyle(realm: Realm, clusterMarkers: boolean): StyleSpecification {
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
      cluster: clusterMarkers,
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
  sources["crimson-route"] = {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
  };
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
  layers.push(
    {
      id: "crimson-route-primary",
      type: "line",
      source: "crimson-route",
      filter: ["==", ["get", "primary"], true],
      paint: {
        "line-width": 5,
        "line-color": "#efc05c",
        "line-opacity": 0.95,
      },
    },
    {
      id: "crimson-route-alt",
      type: "line",
      source: "crimson-route",
      filter: ["==", ["get", "primary"], false],
      paint: {
        "line-width": 3,
        "line-color": "#62b4e8",
        "line-opacity": 0.55,
      },
    },
  );
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
        id: catalogSelectionLayerId(group.id),
        type: "circle",
        source,
        filter: ["all", ["!", ["has", "point_count"]], ["==", ["get", "selected"], true]],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 2, 10, 6.5, 17],
          "circle-color": "rgba(239, 192, 92, 0.16)",
          "circle-stroke-color": "#efc05c",
          "circle-stroke-width": 2.5,
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
          // At the highest zoom every catalog point must remain visible and
          // clickable. Collision hiding here made markers disappear exactly
          // when clusters expanded into their individual points.
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
          "icon-padding": 2,
        },
        paint: {
          "icon-opacity": ["case", ["boolean", ["get", "selected"], false], 1, ["boolean", ["get", "muted"], false], 0.22, ["boolean", ["get", "found"], false], 0.32, 1],
        },
      },
    );
  }
  return { version: 8, sources, layers };
}

function makeWaypointElement(waypoint: Waypoint, selected: boolean, muted: boolean): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `waypoint-marker${selected ? " selected" : ""}${waypoint.found ? " found" : ""}${muted ? " muted" : ""}`;
  element.style.setProperty("--marker-color", waypoint.color);
  element.title = `${waypoint.name}\nX ${waypoint.x.toFixed(1)} · Y ${waypoint.y.toFixed(1)} · Z ${waypoint.z.toFixed(1)}`;
  element.setAttribute("aria-label", waypoint.name);
  element.innerHTML = '<span class="waypoint-dot"></span>';
  return element;
}

function makeCatalogTooltip(marker: CatalogMarker, detailed = true): HTMLDivElement {
  const root = document.createElement("div");
  root.className = "catalog-tooltip";
  const icon = document.createElement("img");
  icon.src = `/marker-icons/${marker.icon}`;
  icon.alt = "";
  const copy = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = marker.name;
  const category = document.createElement("span");
  category.textContent = marker.groupLabel;
  const coordinates = document.createElement("small");
  coordinates.textContent = `X ${marker.x.toFixed(1)} · ${marker.y === null ? "Y —" : `Y ${marker.y.toFixed(1)}`} · Z ${marker.z.toFixed(1)}`;
  copy.append(name);
  if (detailed) copy.append(category, coordinates);
  root.append(icon, copy);
  return root;
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
  displaySettings,
  language,
  alignment,
  calibrationMode,
  onMapClick,
  onSelectWaypoint,
  onSelectCatalogMarker,
  crimsonRoutes,
  crimsonRouteRealm,
  routeTarget = null,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const styledRealmRef = useRef<Realm>(realm);
  const alignmentRef = useRef<MapAlignment>(alignment);
  const calibrationModeRef = useRef(calibrationMode);
  const hoverDetailsRef = useRef(displaySettings.showHoverDetails);
  const labelModeRef = useRef(displaySettings.markerLabelMode);
  const clusteringRef = useRef(displaySettings.clusterMarkers);
  const playerMarkerRef = useRef<Marker | null>(null);
  const routeEndMarkerRef = useRef<Marker | null>(null);
  const waypointMarkersRef = useRef<Marker[]>([]);
  const catalogLabelMarkersRef = useRef<Marker[]>([]);
  const callbacksRef = useRef({ onMapClick, onSelectWaypoint, onSelectCatalogMarker });
  const catalogMarkersRef = useRef(catalogMarkers);
  const tooltipRef = useRef<maplibregl.Popup | null>(null);
  const [cursor, setCursor] = useState<{ x: number; z: number } | null>(null);

  callbacksRef.current = { onMapClick, onSelectWaypoint, onSelectCatalogMarker };
  catalogMarkersRef.current = catalogMarkers;
  alignmentRef.current = alignment;
  calibrationModeRef.current = calibrationMode;
  hoverDetailsRef.current = displaySettings.showHoverDetails;
  labelModeRef.current = displaySettings.markerLabelMode;

  useEffect(() => {
    if (!displaySettings.showHoverDetails) {
      tooltipRef.current?.remove();
      tooltipRef.current = null;
    }
  }, [displaySettings.showHoverDetails]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const center = getDefaultCenter(realm);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: createStyle(realm, displaySettings.clusterMarkers),
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
      map.on("mouseenter", pointLayer, (event) => {
        if (calibrationModeRef.current || (!hoverDetailsRef.current && labelModeRef.current !== "hover")) return;
        const feature = event.features?.[0];
        const markerId = feature?.properties?.markerId;
        if (typeof markerId !== "string" || feature?.geometry.type !== "Point") return;
        const marker = catalogMarkersRef.current.find((item) => item.id === markerId);
        if (!marker) return;
        tooltipRef.current?.remove();
        tooltipRef.current = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 16,
          className: "catalog-hover-popup",
        })
          .setLngLat(feature.geometry.coordinates as [number, number])
          .setDOMContent(makeCatalogTooltip(marker, hoverDetailsRef.current))
          .addTo(map);
      });
      map.on("mouseleave", pointLayer, () => {
        tooltipRef.current?.remove();
        tooltipRef.current = null;
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
      tooltipRef.current?.remove();
      tooltipRef.current = null;
      catalogLabelMarkersRef.current.forEach((marker) => marker.remove());
      catalogLabelMarkersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || (styledRealmRef.current === realm && clusteringRef.current === displaySettings.clusterMarkers)) return;
    styledRealmRef.current = realm;
    clusteringRef.current = displaySettings.clusterMarkers;
    mapRef.current.setStyle(createStyle(realm, displaySettings.clusterMarkers));
  }, [realm, displaySettings.clusterMarkers]);

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
            .filter((marker) => displaySettings.showFoundMarkers || !foundCatalogMarkerIds.has(marker.id) || marker.id === selectedCatalogMarkerId)
            .map((marker) => {
              const position = gameToMap({ x: marker.x, y: marker.y || 0, z: marker.z }, realm, alignment);
              return {
                type: "Feature" as const,
                geometry: { type: "Point" as const, coordinates: [position.x, position.y] },
                properties: {
                  markerId: marker.id,
                  iconId: markerImageId(marker.icon),
                  found: foundCatalogMarkerIds.has(marker.id),
                  selected: marker.id === selectedCatalogMarkerId,
                  muted: displaySettings.focusSelectedMarker && (
                    selectedWaypointId !== null
                    || (selectedCatalogMarkerId !== null && marker.id !== selectedCatalogMarkerId)
                  ),
                },
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
  }, [catalogMarkers, visibleCatalogGroups, visibleCatalogTypes, foundCatalogMarkerIds, selectedCatalogMarkerId, selectedWaypointId, displaySettings.showFoundMarkers, displaySettings.focusSelectedMarker, realm, alignment]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const clustersMuted = displaySettings.focusSelectedMarker && (selectedCatalogMarkerId !== null || selectedWaypointId !== null);
    const apply = () => {
      for (const group of CATALOG_GROUP_STYLES) {
        const circleLayer = catalogClusterLayerId(group.id);
        const iconLayer = catalogClusterIconLayerId(group.id);
        if (map.getLayer(circleLayer)) map.setPaintProperty(circleLayer, "circle-opacity", clustersMuted ? 0.2 : 0.92);
        if (map.getLayer(iconLayer)) map.setPaintProperty(iconLayer, "icon-opacity", clustersMuted ? 0.2 : 1);
      }
    };
    map.on("style.load", apply);
    apply();
    return () => { map.off("style.load", apply); };
  }, [displaySettings.focusSelectedMarker, displaySettings.clusterMarkers, selectedCatalogMarkerId, selectedWaypointId, realm]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const scale = displaySettings.markerSize === "compact" ? 0.82 : displaySettings.markerSize === "large" ? 1.22 : 1;
    const apply = () => {
      for (const group of CATALOG_GROUP_STYLES) {
        const layer = catalogPointLayerId(group.id);
        if (map.getLayer(layer)) {
          map.setLayoutProperty(layer, "icon-size", ["interpolate", ["linear"], ["zoom"], 2, 0.42 * scale, 5, 0.62 * scale, 6.5, 0.74 * scale]);
        }
      }
    };
    map.on("style.load", apply);
    apply();
    return () => { map.off("style.load", apply); };
  }, [displaySettings.markerSize, realm]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      for (const group of CATALOG_GROUP_STYLES) {
        const layer = catalogPointLayerId(group.id);
        if (!map.getLayer(layer)) continue;
        map.setPaintProperty(layer, "icon-opacity", [
          "case",
          ["boolean", ["get", "selected"], false], 1,
          ["boolean", ["get", "muted"], false], 0.22,
          ["boolean", ["get", "found"], false], displaySettings.foundMarkerOpacity,
          1,
        ]);
      }
    };
    map.on("style.load", apply);
    apply();
    return () => { map.off("style.load", apply); };
  }, [displaySettings.foundMarkerOpacity, realm, displaySettings.clusterMarkers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const clearLabels = () => {
      catalogLabelMarkersRef.current.forEach((marker) => marker.remove());
      catalogLabelMarkersRef.current = [];
    };
    const syncLabels = () => {
      clearLabels();
      if (displaySettings.markerLabelMode === "off" || displaySettings.markerLabelMode === "hover") return;

      const selected = selectedCatalogMarkerId
        ? catalogMarkers.find((marker) => marker.id === selectedCatalogMarkerId) || null
        : null;
      const candidates: CatalogMarker[] = [];
      if (selected) candidates.push(selected);

      catalogLabelMarkersRef.current = candidates.map((marker) => {
        const element = document.createElement("div");
        element.className = `catalog-map-label${marker.id === selectedCatalogMarkerId ? " selected" : ""}`;
        element.textContent = marker.name;
        const target = gameToMap({ x: marker.x, y: marker.y || 0, z: marker.z }, realm, alignment);
        return new maplibregl.Marker({ element, anchor: "left", offset: [14, 0] })
          .setLngLat([target.x, target.y])
          .addTo(map);
      });
    };
    map.on("moveend", syncLabels);
    map.on("zoomend", syncLabels);
    map.on("style.load", syncLabels);
    syncLabels();
    return () => {
      map.off("moveend", syncLabels);
      map.off("zoomend", syncLabels);
      map.off("style.load", syncLabels);
      clearLabels();
    };
  }, [catalogMarkers, selectedCatalogMarkerId, displaySettings.markerLabelMode, displaySettings.clusterMarkers, realm, alignment]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;
    const update = () => {
      if (cancelled) return;
      const source = map.getSource("crimson-route") as GeoJSONSource | undefined;
      if (!source) return;
      if (crimsonRouteRealm !== realm || !crimsonRoutes.length) {
        source.setData({ type: "FeatureCollection", features: [] });
        return;
      }

      const primary = crimsonRoutes.find((route) => route.primary);
      const trimmedPrimaryPoints = (() => {
        if (!primary || !position) return primary?.points;
        let closestIndex = 0;
        let closestDist = Infinity;
        for (let i = 0; i < primary.points.length; i++) {
          const dx = primary.points[i].x - position.x;
          const dz = primary.points[i].z - position.z;
          const dist = Math.sqrt(dx * dx + dz * dz);
          if (dist < closestDist) {
            closestDist = dist;
            closestIndex = i;
          }
        }
        if (closestDist > 15) return primary.points;
        const startIndex = Math.max(0, closestIndex - 1);
        return primary.points.slice(startIndex);
      })();

      const features = crimsonRoutes.map((route) => {
        const points = route.primary && trimmedPrimaryPoints ? trimmedPrimaryPoints : route.points;
        return {
          type: "Feature" as const,
          geometry: {
            type: "LineString" as const,
            coordinates: points.map((point) => {
              const pos = gameToMap(point, realm, alignment);
              return [pos.x, pos.y];
            }),
          },
          properties: {
            index: route.index,
            primary: route.primary,
            pointCount: route.pointCount,
            polylineDistance: route.polylineDistance,
            roadDistance: route.roadDistance,
          },
        };
      });
      source.setData({ type: "FeatureCollection", features });
    };
    map.on("style.load", update);
    update();
    return () => {
      cancelled = true;
      map.off("style.load", update);
    };
  }, [crimsonRoutes, crimsonRouteRealm, realm, alignment, position]);

  useEffect(() => {
    const map = mapRef.current;
    routeEndMarkerRef.current?.remove();
    routeEndMarkerRef.current = null;
    if (!map || crimsonRouteRealm !== realm || !crimsonRoutes.length) return;

    const primary = crimsonRoutes.find((route) => route.primary) || crimsonRoutes[0];
    const fallback = primary.endPoint || (primary.points.length ? primary.points[primary.points.length - 1] : null);
    const destination = routeTarget?.realm === realm ? routeTarget : fallback ? { ...fallback, realm } : null;
    if (!destination) return;

    const element = document.createElement("div");
    element.className = "route-end-marker";
    element.title = routeTarget?.name || translations[language].navigation;
    if (routeTarget?.icon && /^[a-z0-9-]+\.png$/.test(routeTarget.icon)) {
      const image = document.createElement("img");
      image.src = `/marker-icons/${routeTarget.icon}`;
      image.alt = "";
      element.append(image);
    } else {
      element.style.setProperty("--route-target-color", routeTarget?.color || "#efc05c");
      element.innerHTML = '<span class="route-end-dot"></span>';
    }
    const target = gameToMap({ x: destination.x, y: 0, z: destination.z }, realm, alignment);
    routeEndMarkerRef.current = new maplibregl.Marker({ element, anchor: "bottom" })
      .setLngLat([target.x, target.y])
      .addTo(map);
    return () => {
      routeEndMarkerRef.current?.remove();
      routeEndMarkerRef.current = null;
    };
  }, [crimsonRoutes, crimsonRouteRealm, routeTarget, realm, alignment, language]);

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
        const selected = waypoint.id === selectedWaypointId;
        const muted = displaySettings.focusSelectedMarker && !selected && (selectedWaypointId !== null || selectedCatalogMarkerId !== null);
        const element = makeWaypointElement(waypoint, selected, muted);
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
  }, [waypoints, realm, selectedWaypointId, selectedCatalogMarkerId, displaySettings.focusSelectedMarker, alignment]);

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
