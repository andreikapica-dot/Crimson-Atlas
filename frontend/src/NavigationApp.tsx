import { useEffect, useMemo, useRef, useState } from "react";

import MapView, { type CrimsonRouteLine, type Realm } from "./components/MapView";
import { DEFAULT_DISPLAY_SETTINGS } from "./displaySettings";
import { isLanguage, translations, LANGUAGE_STORAGE_KEY, type Language } from "./i18n";
import { detectRealm, type MapAlignment } from "./map/coordinates";
import { loadNavigationState, NAVIGATION_STATE_KEY, saveNavigationState } from "./navigationState";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:7892";
const EMPTY_SET = new Set<string>();
const EMPTY_ALIGNMENT: MapAlignment = { x: 0, z: 0 };

interface PositionPacket {
  type: "position";
  x: number;
  y: number;
  z: number;
}

function loadLanguage(): Language {
  const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return isLanguage(saved) ? saved : "ru";
}

function loadAlignment(realm: Realm): MapAlignment {
  try {
    const parsed = JSON.parse(localStorage.getItem("crimson-atlas-map-alignment-v1") || "{}");
    if (Number.isFinite(parsed?.[realm]?.x) && Number.isFinite(parsed?.[realm]?.z)) {
      return { x: Number(parsed[realm].x), z: Number(parsed[realm].z) };
    }
  } catch { /* use the default alignment */ }
  return EMPTY_ALIGNMENT;
}

export default function NavigationApp() {
  const initial = loadNavigationState();
  const [language] = useState<Language>(loadLanguage);
  const [position, setPosition] = useState<PositionPacket | null>(null);
  const [routes, setRoutes] = useState<CrimsonRouteLine[]>(initial.routes);
  const [routeRealm, setRouteRealm] = useState<Realm | null>(initial.realm);
  const [routeTarget, setRouteTarget] = useState(initial.target);
  const detectedRealmRef = useRef<Realm | null>(initial.realm);
  const realm = routeRealm || detectedRealmRef.current || "pywel";
  const t = translations[language];

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "position") {
          const packet = data as PositionPacket;
          setPosition(packet);
          detectedRealmRef.current = detectRealm(packet.y, detectedRealmRef.current);
        }
        if (data.type === "crimson_route_result" && data.ok) {
          const nextRoutes = Array.isArray(data.routes) ? data.routes : [];
          const nextRealm = data.realm === "abyss" ? "abyss" : "pywel";
          setRoutes(nextRoutes);
          setRouteRealm(nextRealm);
          saveNavigationState(nextRoutes, nextRealm, loadNavigationState().target);
        }
      } catch { /* ignore malformed packets */ }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== NAVIGATION_STATE_KEY) return;
      const next = loadNavigationState();
      setRoutes(next.routes);
      setRouteRealm(next.realm);
      setRouteTarget(next.target);
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  const remaining = useMemo(() => {
    const primary = routes.find((route) => route.primary) || routes[0];
    const end = primary?.endPoint || (primary?.points.length ? primary.points[primary.points.length - 1] : null);
    if (!position || !end) return null;
    return Math.hypot(position.x - end.x, position.z - end.z);
  }, [position, routes]);

  return (
    <div className="navigation-app">
      <div className="navigation-dragbar">
        <strong>{t.navigation.toLocaleUpperCase(language)}</strong>
        <span>{remaining === null ? (routes.length ? "…" : t.noActiveRoute) : `${Math.round(remaining)} m`}</span>
        <button onClick={() => void fetch("/__navigation/hide", { method: "POST" })} aria-label={t.cancel}>×</button>
      </div>
      <MapView
        displaySettings={DEFAULT_DISPLAY_SETTINGS}
        realm={realm}
        position={position}
        followPlayer
        waypoints={[]}
        catalogMarkers={[]}
        visibleCatalogGroups={EMPTY_SET}
        visibleCatalogTypes={EMPTY_SET}
        selectedWaypointId={null}
        selectedCatalogMarkerId={null}
        foundCatalogMarkerIds={EMPTY_SET}
        language={language}
        alignment={loadAlignment(realm)}
        calibrationMode={false}
        crimsonRoutes={routes}
        crimsonRouteRealm={routeRealm}
        routeTarget={routeTarget}
        onMapClick={() => {}}
        onSelectWaypoint={() => {}}
        onSelectCatalogMarker={() => {}}
      />
    </div>
  );
}
