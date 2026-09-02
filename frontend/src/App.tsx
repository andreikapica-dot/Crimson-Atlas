import { useEffect, useMemo, useRef, useState } from "react";
import MapView, { type Realm, type Waypoint } from "./components/MapView";
import { flattenCatalog, type CatalogData, type CatalogMarker, type CatalogOverride } from "./catalog";
import { setGroupTypesVisible, toggleTypeVisibility } from "./catalogVisibility";
import { catalogGroupLabels, LANGUAGE_STORAGE_KEY, translations, type Language } from "./i18n";
import { GAME_BOUNDS, alignToClickedPosition, detectRealm, isWithinGameBounds, type MapAlignment } from "./map/coordinates";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:7892";
const STORAGE_KEY = "crimson-atlas-waypoints-v1";
const CATALOG_OVERRIDE_KEY = "crimson-atlas-catalog-overrides-v1";
const FOUND_MARKERS_KEY = "crimson-atlas-found-markers-v1";
const MAP_ALIGNMENT_KEY = "crimson-atlas-map-alignment-v1";

const CATEGORIES = [
  { id: "favorite", symbol: "★", color: "#efc05c" },
  { id: "resource", symbol: "◆", color: "#75c99a" },
  { id: "quest", symbol: "!", color: "#7db7e8" },
  { id: "danger", symbol: "▲", color: "#e46f64" },
  { id: "custom", symbol: "●", color: "#bd91df" },
] as const;

const COLOR_PALETTE = ["#efc05c", "#75c99a", "#7db7e8", "#e46f64", "#bd91df", "#e58bc4", "#df9d65", "#a8adb5"];

interface PositionPacket {
  type: "position";
  x: number;
  y: number;
  z: number;
  reader?: string;
  realm?: Realm;
}

interface BackendStatus {
  gameAttached: boolean;
  teleportAvailable: boolean;
  message?: string;
}

interface Draft {
  id?: string;
  catalogId?: string;
  name: string;
  category: string;
  color: string;
  x: string;
  y: string;
  z: string;
  realm: Realm;
  note: string;
}

interface TeleportTarget {
  name: string;
  x: number;
  y: number;
  z: number;
}

function loadWaypoints(): Waypoint[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function loadCatalogOverrides(): Record<string, CatalogOverride> {
  try {
    const parsed = JSON.parse(localStorage.getItem(CATALOG_OVERRIDE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function loadLanguage(): Language {
  return localStorage.getItem(LANGUAGE_STORAGE_KEY) === "en" ? "en" : "ru";
}

function loadFoundMarkers(): Set<string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(FOUND_MARKERS_KEY) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : []);
  } catch {
    return new Set();
  }
}

function loadMapAlignments(): Record<Realm, MapAlignment> {
  const fallback = { pywel: { x: 0, z: 0 }, abyss: { x: 0, z: 0 } };
  try {
    const parsed = JSON.parse(localStorage.getItem(MAP_ALIGNMENT_KEY) || "{}");
    for (const realm of ["pywel", "abyss"] as const) {
      if (Number.isFinite(parsed?.[realm]?.x) && Number.isFinite(parsed?.[realm]?.z)) {
        fallback[realm] = { x: Number(parsed[realm].x), z: Number(parsed[realm].z) };
      }
    }
  } catch { /* use zero alignment */ }
  return fallback;
}

function createDraft(position: { x: number; y: number; z: number }, realm: Realm, language: Language): Draft {
  return {
    name: translations[language].newMarker,
    category: "custom",
    color: "#bd91df",
    x: position.x.toFixed(2),
    y: position.y.toFixed(2),
    z: position.z.toFixed(2),
    realm,
    note: "",
  };
}

export default function App() {
  const [language, setLanguage] = useState<Language>(loadLanguage);
  const [realm, setRealm] = useState<Realm>("pywel");
  const [connected, setConnected] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ gameAttached: false, teleportAvailable: false });
  const [position, setPosition] = useState<PositionPacket | null>(null);
  const [followPlayer, setFollowPlayer] = useState(true);
  const [waypoints, setWaypoints] = useState<Waypoint[]>(loadWaypoints);
  const [catalog, setCatalog] = useState<CatalogData | null>(null);
  const [catalogOverrides, setCatalogOverrides] = useState<Record<string, CatalogOverride>>(loadCatalogOverrides);
  const [foundMarkers, setFoundMarkers] = useState<Set<string>>(loadFoundMarkers);
  const [visibleCatalogGroups, setVisibleCatalogGroups] = useState<Set<string>>(new Set());
  const [visibleCatalogTypes, setVisibleCatalogTypes] = useState<Set<string>>(new Set());
  const [waypointsVisible, setWaypointsVisible] = useState(true);
  const [mapAlignments, setMapAlignments] = useState<Record<Realm, MapAlignment>>(loadMapAlignments);
  const [calibrationMode, setCalibrationMode] = useState(false);
  const [expandedCatalogGroups, setExpandedCatalogGroups] = useState<Set<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [teleportTarget, setTeleportTarget] = useState<TeleportTarget | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number>();
  const detectedRealmRef = useRef<Realm | null>(null);
  const t = translations[language];

  useEffect(() => localStorage.setItem(STORAGE_KEY, JSON.stringify(waypoints)), [waypoints]);
  useEffect(() => localStorage.setItem(CATALOG_OVERRIDE_KEY, JSON.stringify(catalogOverrides)), [catalogOverrides]);
  useEffect(() => localStorage.setItem(FOUND_MARKERS_KEY, JSON.stringify([...foundMarkers])), [foundMarkers]);
  useEffect(() => localStorage.setItem(MAP_ALIGNMENT_KEY, JSON.stringify(mapAlignments)), [mapAlignments]);
  useEffect(() => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    document.documentElement.lang = language;
  }, [language]);

  useEffect(() => {
    let cancelled = false;
    fetch("/data/marker-catalog.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<CatalogData>;
      })
      .then((data) => {
        if (cancelled) return;
        setCatalog(data);
        setVisibleCatalogGroups(new Set(data.groups.map((group) => group.id)));
        setVisibleCatalogTypes(new Set(data.types.map((type) => type.id)));
      })
      .catch(() => setToast(translations[loadLanguage()].catalogLoadError));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let disposed = false;
    function connect() {
      if (disposed) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "position") {
            const packet = data as PositionPacket;
            setPosition(packet);
            const detected = detectRealm(packet.y, detectedRealmRef.current);
            if (detected !== detectedRealmRef.current) {
              detectedRealmRef.current = detected;
              setRealm(detected);
              setSelectedId(null);
              setSelectedCatalogId(null);
              setCalibrationMode(false);
            }
          }
          if (data.type === "status") setBackendStatus(data as BackendStatus);
          if (data.type === "command_result") {
            const message = translations[loadLanguage()];
            setToast(data.ok ? message.teleportDone : `${message.teleportUnavailable}: ${data.error || message.error}`);
            window.setTimeout(() => setToast(null), 4000);
          }
        } catch { /* malformed packets are ignored */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!disposed) reconnectRef.current = window.setTimeout(connect, 1800);
      };
      ws.onerror = () => ws.close();
    }
    connect();
    return () => {
      disposed = true;
      window.clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, []);

  const filteredWaypoints = useMemo(() => {
    if (!waypointsVisible) return [];
    const normalized = query.trim().toLocaleLowerCase(language);
    return waypoints.filter((waypoint) => waypoint.realm === realm)
      .filter((waypoint) => category === "all" || waypoint.category === category)
      .filter((waypoint) => !normalized || `${waypoint.name} ${waypoint.note} ${waypoint.x} ${waypoint.z}`.toLocaleLowerCase(language).includes(normalized));
  }, [waypoints, waypointsVisible, realm, category, query, language]);

  const catalogMarkers = useMemo(
    () => catalog ? flattenCatalog(catalog, realm, catalogOverrides, language) : [],
    [catalog, realm, catalogOverrides, language],
  );
  const normalizedQuery = query.trim().toLocaleLowerCase(language);
  const catalogSearchResults = useMemo(() => {
    if (normalizedQuery.length < 2) return [];
    return catalogMarkers
      .filter((marker) => visibleCatalogGroups.has(marker.group))
      .filter((marker) => visibleCatalogTypes.has(marker.type))
      .filter((marker) => `${marker.name} ${marker.nameEn} ${marker.type} ${marker.x} ${marker.z}`.toLocaleLowerCase(language).includes(normalizedQuery))
      .slice(0, 120);
  }, [catalogMarkers, normalizedQuery, visibleCatalogGroups, visibleCatalogTypes]);
  const groupCounts = useMemo(() => {
    const counts = new Map<string, number>();
    catalogMarkers.forEach((marker) => counts.set(marker.group, (counts.get(marker.group) || 0) + 1));
    return counts;
  }, [catalogMarkers]);
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    catalogMarkers.forEach((marker) => counts.set(marker.type, (counts.get(marker.type) || 0) + 1));
    return counts;
  }, [catalogMarkers]);
  const typesByGroup = useMemo(() => {
    const result = new Map<string, CatalogData["types"]>();
    catalog?.types.forEach((type) => {
      if ((typeCounts.get(type.id) || 0) === 0) return;
      result.set(type.group, [...(result.get(type.group) || []), type]);
    });
    result.forEach((types, group) => result.set(group, types.sort((a, b) => {
      const left = language === "en" ? a.nameEn : a.name;
      const right = language === "en" ? b.nameEn : b.name;
      return left.localeCompare(right, language);
    })));
    return result;
  }, [catalog, typeCounts, language]);

  const selected = waypoints.find((waypoint) => waypoint.id === selectedId) || null;
  const selectedCatalog = catalogMarkers.find((marker) => marker.id === selectedCatalogId) || null;

  function saveDraft() {
    if (!draft) return;
    const x = Number(draft.x);
    const y = draft.y.trim() === "" ? null : Number(draft.y);
    const z = Number(draft.z);
    if (![x, z].every(Number.isFinite) || (y !== null && !Number.isFinite(y)) || !isWithinGameBounds(x, z)) {
      setToast(`${t.coordinatesOutside}: X ${GAME_BOUNDS.minX}…${GAME_BOUNDS.maxX}, Z ${GAME_BOUNDS.minZ}…${GAME_BOUNDS.maxZ}`);
      return;
    }
    if (draft.catalogId) {
      setCatalogOverrides((items) => ({
        ...items,
        [draft.catalogId!]: { name: draft.name.trim(), x, y, z, note: draft.note.trim() },
      }));
      setDraft(null);
      return;
    }
    if (y === null) {
      setToast(t.heightRequired);
      return;
    }
    const color = /^#[0-9a-f]{6}$/i.test(draft.color) ? draft.color : "#bd91df";
    const waypoint: Waypoint = {
      id: draft.id || crypto.randomUUID(),
      name: draft.name.trim() || t.unnamedMarker,
      category: draft.category,
      color,
      x, y, z,
      realm: draft.realm,
      note: draft.note.trim(),
      createdAt: draft.id ? waypoints.find((item) => item.id === draft.id)?.createdAt || Date.now() : Date.now(),
    };
    setWaypoints((items) => draft.id ? items.map((item) => item.id === draft.id ? waypoint : item) : [...items, waypoint]);
    setSelectedId(waypoint.id);
    setDraft(null);
  }

  function editWaypoint(waypoint: Waypoint) {
    setDraft({
      id: waypoint.id,
      name: waypoint.name,
      category: waypoint.category,
      color: waypoint.color,
      x: String(waypoint.x), y: String(waypoint.y), z: String(waypoint.z),
      realm: waypoint.realm,
      note: waypoint.note,
    });
  }

  function editCatalogMarker(marker: CatalogMarker) {
    setDraft({
      catalogId: marker.id,
      name: marker.name,
      category: "custom",
      color: marker.groupColor,
      x: String(marker.x), y: marker.y === null ? "" : String(marker.y), z: String(marker.z),
      realm: marker.realm,
      note: marker.note,
    });
  }

  function teleport(target: TeleportTarget) {
    const socket = wsRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setToast(t.localServiceStopped);
      return;
    }
    socket.send(JSON.stringify({
      cmd: "teleport",
      requestId: crypto.randomUUID(),
      x: target.x, y: target.y + 1, z: target.z,
    }));
    setTeleportTarget(null);
    setToast(t.teleportSent);
  }

  function toggleFound(markerId: string) {
    setFoundMarkers((current) => {
      const next = new Set(current);
      if (next.has(markerId)) next.delete(markerId); else next.add(markerId);
      return next;
    });
  }

  function toggleWaypointFound(waypointId: string) {
    setWaypoints((items) => items.map((item) => item.id === waypointId ? { ...item, found: !item.found } : item));
  }

  return (
    <div className={`atlas-app${sidebarOpen ? "" : " sidebar-collapsed"}`}>
      <aside className="sidebar">
        <header className="brand-row">
          <div className="brand-mark">CA</div>
          <div className="brand-copy"><strong>CRIMSON ATLAS</strong><small>{t.tagline}</small></div>
          <div className="language-switch" aria-label="Language">
            <button className={language === "ru" ? "active" : ""} onClick={() => setLanguage("ru")}>RU</button>
            <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button>
          </div>
          <button className="icon-button close-sidebar" onClick={() => setSidebarOpen(false)} aria-label={t.hideSidebar}>‹</button>
        </header>

        <div className="realm-switch" role="tablist">
          <button className={realm === "pywel" ? "active" : ""} onClick={() => { setRealm("pywel"); setSelectedId(null); setSelectedCatalogId(null); }}>{t.pywel}</button>
          <button className={realm === "abyss" ? "active" : ""} onClick={() => { setRealm("abyss"); setSelectedId(null); setSelectedCatalogId(null); }}>{t.abyss}</button>
        </div>

        <label className="search-box">
          <span>⌕</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t.searchPlaceholder} />
        </label>

        <section className="category-list">
          <div className="visibility-actions">
            <button onClick={() => {
              if (!catalog) return;
              setVisibleCatalogGroups(new Set(catalog.groups.map((group) => group.id)));
              setVisibleCatalogTypes(new Set(catalog.types.map((type) => type.id)));
              setWaypointsVisible(true);
            }}>{t.showAll}</button>
            <button onClick={() => { setVisibleCatalogGroups(new Set()); setWaypointsVisible(false); }}>{t.hideAll}</button>
          </div>
          {catalog?.groups.filter((item) => (groupCounts.get(item.id) || 0) > 0).map((item) => {
            const visible = visibleCatalogGroups.has(item.id);
            const groupTypes = typesByGroup.get(item.id) || [];
            const expanded = expandedCatalogGroups.has(item.id);
            const visibleTypeCount = groupTypes.filter((type) => visibleCatalogTypes.has(type.id)).length;
            return (
              <div className="category-group" key={item.id}>
                <div className={`category-group-row${visible ? " active" : ""}`}>
                  <button className={`category-toggle${visible ? " active" : ""}`} onClick={() => {
                    setVisibleCatalogGroups((current) => {
                      const next = new Set(current);
                      if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                      return next;
                    });
                    setVisibleCatalogTypes((current) => setGroupTypesVisible(current, groupTypes, !visible));
                  }}>
                    <img className="category-icon" src={`/marker-icons/${item.icon}`} alt="" />
                    <span>{catalogGroupLabels[language][item.id] || item.label}</span><b>{groupCounts.get(item.id) || 0}</b>
                    <em>{visible ? "●" : "○"}</em>
                  </button>
                  <button className={`subcategory-expand${expanded ? " open" : ""}`} aria-label={`${t.subcategories}: ${catalogGroupLabels[language][item.id] || item.label}`} onClick={() => setExpandedCatalogGroups((current) => {
                    const next = new Set(current);
                    if (next.has(item.id)) next.delete(item.id); else next.add(item.id);
                    return next;
                  })}>⌄</button>
                </div>
                {expanded && <div className="subcategory-list">
                  <div className="subcategory-summary"><span>{t.markerTypes}</span><b>{visibleTypeCount}/{groupTypes.length}</b></div>
                  {groupTypes.map((type) => {
                    const typeVisible = visible && visibleCatalogTypes.has(type.id);
                    return <button key={type.id} className={typeVisible ? "active" : ""} onClick={() => {
                      setVisibleCatalogTypes((current) => toggleTypeVisibility(current, groupTypes, type.id, visible));
                      if (!visible) setVisibleCatalogGroups((current) => new Set(current).add(item.id));
                    }}>
                      <img src={`/marker-icons/${type.icon}`} alt="" /><span>{language === "en" ? type.nameEn : type.name}</span><b>{typeCounts.get(type.id) || 0}</b><em>{typeVisible ? "●" : "○"}</em>
                    </button>;
                  })}
                </div>}
              </div>
            );
          })}
          <button className={waypointsVisible ? "active" : ""} onClick={() => {
            setWaypointsVisible((value) => !value);
            setCategory("all");
          }}>
            <span className="category-symbol" style={{ color: "#bd91df" }}>●</span><span>{t.myMarkers}</span>
            <b>{waypoints.filter((item) => item.realm === realm).length}</b><em>{waypointsVisible ? "●" : "○"}</em>
          </button>
        </section>

        <section className="waypoint-list">
          <div className="section-heading"><span>{normalizedQuery.length >= 2 ? t.searchResults : t.myMarkers}</span><small>{normalizedQuery.length >= 2 ? catalogSearchResults.length + filteredWaypoints.length : filteredWaypoints.length}</small></div>
          {normalizedQuery.length < 2 && filteredWaypoints.length === 0 && <div className="empty-state">{t.emptyMarkers}</div>}
          {filteredWaypoints.map((waypoint) => (
            <button key={waypoint.id} className={`waypoint-card${selectedId === waypoint.id ? " active" : ""}${waypoint.found ? " found" : ""}`} onClick={() => { setSelectedId(waypoint.id); setSelectedCatalogId(null); }}>
              <i style={{ background: waypoint.color }} />
              <span><strong>{waypoint.name}</strong><small>X {waypoint.x.toFixed(1)} · Y {waypoint.y.toFixed(1)} · Z {waypoint.z.toFixed(1)}</small></span>
            </button>
          ))}
          {catalogSearchResults.map((marker) => (
            <button key={marker.id} className={`waypoint-card catalog-card${selectedCatalogId === marker.id ? " active" : ""}${foundMarkers.has(marker.id) ? " found" : ""}`} onClick={() => { setSelectedCatalogId(marker.id); setSelectedId(null); }}>
              <img src={`/marker-icons/${marker.icon}`} alt="" />
              <span><strong>{marker.name}</strong><small>{marker.groupLabel} · X {marker.x.toFixed(1)} · Z {marker.z.toFixed(1)}</small></span>
            </button>
          ))}
          {normalizedQuery.length >= 2 && catalogSearchResults.length === 120 && <small className="search-limit">{t.searchLimit}</small>}
        </section>

        <a className="kofi-link" href="https://ko-fi.com/andrei33721" target="_blank" rel="noreferrer">☕ {t.support}</a>

        <footer className="connection-card">
          <span className={`connection-dot ${backendStatus.gameAttached ? "online" : connected ? "waiting" : "offline"}`} />
          <div><strong>{backendStatus.gameAttached ? t.gameConnected : connected ? t.waitingForGame : t.serviceStopped}</strong>
            <small>{position ? `X ${position.x.toFixed(1)} · Y ${position.y.toFixed(1)} · Z ${position.z.toFixed(1)}` : t.startGame}</small></div>
        </footer>
      </aside>

      {!sidebarOpen && <button className="open-sidebar" onClick={() => setSidebarOpen(true)}>☰</button>}

      <MapView
        realm={realm}
        position={position}
        followPlayer={followPlayer}
        waypoints={waypointsVisible ? waypoints : []}
        catalogMarkers={catalogMarkers}
        visibleCatalogGroups={visibleCatalogGroups}
        visibleCatalogTypes={visibleCatalogTypes}
        selectedWaypointId={selectedId}
        selectedCatalogMarkerId={selectedCatalogId}
        foundCatalogMarkerIds={foundMarkers}
        language={language}
        alignment={mapAlignments[realm]}
        calibrationMode={calibrationMode}
        onMapClick={(point) => {
          if (calibrationMode && position) {
            const next = alignToClickedPosition(mapAlignments[realm], position, point);
            setMapAlignments((items) => ({ ...items, [realm]: next }));
            setCalibrationMode(false);
            setFollowPlayer(true);
            setToast(t.alignmentSaved);
            window.setTimeout(() => setToast(null), 3500);
            return;
          }
          setDraft(createDraft({ ...point, y: position?.y || 0 }, realm, language));
        }}
        onSelectWaypoint={setSelectedId}
        onSelectCatalogMarker={(id) => { setSelectedCatalogId(id); setSelectedId(null); }}
      />

      <div className="map-actions">
        <button className={followPlayer ? "active" : ""} onClick={() => setFollowPlayer((value) => !value)} title={t.followPlayer}>◎</button>
        <button className={calibrationMode ? "active" : ""} onClick={() => {
          setCalibrationMode((value) => !value);
          setFollowPlayer(false);
        }} disabled={!position} title={t.calibrateMap}>⌖</button>
        <button onClick={() => position && setDraft(createDraft(position, realm, language))} disabled={!position} title={t.markerAtPlayer}>＋</button>
      </div>

      {calibrationMode && <div className="calibration-hint"><strong>{t.calibrationTitle}</strong><span>{t.calibrationInstruction}</span><div><button onClick={() => setCalibrationMode(false)}>{t.cancel}</button><button onClick={() => {
        setMapAlignments((items) => ({ ...items, [realm]: { x: 0, z: 0 } }));
        setCalibrationMode(false);
        setToast(t.alignmentReset);
      }}>{t.resetAlignment}</button></div></div>}

      {selected && !draft && (
        <article className="waypoint-detail">
          <button className="detail-close" onClick={() => setSelectedId(null)}>×</button>
          <span className="detail-category" style={{ color: selected.color }}>{t.categories[selected.category as keyof typeof t.categories] || t.marker}</span>
          <h2>{selected.name}</h2>
          <div className="coordinate-grid"><span>X<strong>{selected.x.toFixed(2)}</strong></span><span>Y<strong>{selected.y.toFixed(2)}</strong></span><span>Z<strong>{selected.z.toFixed(2)}</strong></span></div>
          {selected.note && <p>{selected.note}</p>}
          <button className={`found-button${selected.found ? " active" : ""}`} onClick={() => toggleWaypointFound(selected.id)}>
            <span>{selected.found ? "✓" : "○"}</span>
            {selected.found ? t.unmarkFound : t.markFound}
          </button>
          <div className="detail-actions">
            <button onClick={() => editWaypoint(selected)}>{t.edit}</button>
            <button className="teleport-button" onClick={() => setTeleportTarget(selected)} disabled={!backendStatus.teleportAvailable}>{t.teleport}</button>
            <button className="delete-button" onClick={() => { setWaypoints((items) => items.filter((item) => item.id !== selected.id)); setSelectedId(null); }}>{t.delete}</button>
          </div>
          {!backendStatus.teleportAvailable && <small className="teleport-hint">{t.teleportNeedsGame}</small>}
        </article>
      )}

      {selectedCatalog && !draft && (
        <article className="waypoint-detail catalog-detail">
          <button className="detail-close" onClick={() => setSelectedCatalogId(null)}>×</button>
          <div className="catalog-title-row"><img src={`/marker-icons/${selectedCatalog.icon}`} alt="" /><div><span className="detail-category" style={{ color: selectedCatalog.groupColor }}>{selectedCatalog.groupLabel}</span><h2>{selectedCatalog.name}</h2></div></div>
          <div className="coordinate-grid"><span>X<strong>{selectedCatalog.x.toFixed(2)}</strong></span><span>Y<strong>{selectedCatalog.y === null ? "—" : selectedCatalog.y.toFixed(2)}</strong></span><span>Z<strong>{selectedCatalog.z.toFixed(2)}</strong></span></div>
          <p>{selectedCatalog.note || selectedCatalog.description}</p>
          <button className={`found-button${foundMarkers.has(selectedCatalog.id) ? " active" : ""}`} onClick={() => toggleFound(selectedCatalog.id)}>
            <span>{foundMarkers.has(selectedCatalog.id) ? "✓" : "○"}</span>
            {foundMarkers.has(selectedCatalog.id) ? t.unmarkFound : t.markFound}
          </button>
          <div className="detail-actions">
            <button onClick={() => editCatalogMarker(selectedCatalog)}>{t.edit}</button>
            <button className="teleport-button" onClick={() => selectedCatalog.y !== null && setTeleportTarget({ name: selectedCatalog.name, x: selectedCatalog.x, y: selectedCatalog.y, z: selectedCatalog.z })} disabled={!backendStatus.teleportAvailable || selectedCatalog.y === null}>{t.teleport}</button>
          </div>
          {selectedCatalog.y === null && <small className="teleport-hint">{t.teleportNeedsHeight}</small>}
        </article>
      )}

      {draft && (
        <div className="modal-backdrop">
          <form className="editor-modal" onSubmit={(event) => { event.preventDefault(); saveDraft(); }}>
            <h2>{draft.id || draft.catalogId ? t.editMarker : t.newMarker}</h2>
            <label>{t.name}<input autoFocus value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
            {!draft.catalogId && <div className="editor-choices">
              <span className="field-caption">{t.category}</span>
              <div className="category-choice-grid">
                {CATEGORIES.map((item) => <button type="button" key={item.id} className={draft.category === item.id ? "active" : ""} onClick={() => setDraft({ ...draft, category: item.id, color: item.color })}>
                  <i style={{ color: item.color }}>{item.symbol}</i><span>{t.categories[item.id]}</span>
                </button>)}
              </div>
              <span className="field-caption">{t.color}</span>
              <div className="color-choice-row">
                {COLOR_PALETTE.map((color) => <button type="button" key={color} className={draft.color.toLowerCase() === color ? "active" : ""} style={{ background: color }} aria-label={`${t.color} ${color}`} onClick={() => setDraft({ ...draft, color })} />)}
                <input aria-label={t.colorCode} value={draft.color} maxLength={7} onChange={(event) => setDraft({ ...draft, color: event.target.value })} />
              </div>
            </div>}
            <div className="field-row coordinates"><label>X<input type="number" step="any" value={draft.x} onChange={(event) => setDraft({ ...draft, x: event.target.value })} /></label><label>Y<input type="number" step="any" value={draft.y} onChange={(event) => setDraft({ ...draft, y: event.target.value })} /></label><label>Z<input type="number" step="any" value={draft.z} onChange={(event) => setDraft({ ...draft, z: event.target.value })} /></label></div>
            <label>{t.note}<textarea rows={3} value={draft.note} onChange={(event) => setDraft({ ...draft, note: event.target.value })} placeholder={t.notePlaceholder} /></label>
            <div className="modal-actions"><button type="button" onClick={() => setDraft(null)}>{t.cancel}</button><button className="primary" type="submit">{t.save}</button></div>
          </form>
        </div>
      )}

      {teleportTarget && (
        <div className="modal-backdrop">
          <div className="confirm-modal"><span className="warning-icon">!</span><h2>{t.teleportQuestion}</h2><p>{t.teleportPrompt} “{teleportTarget.name}”?</p><code>X {teleportTarget.x.toFixed(2)} · Y {(teleportTarget.y + 1).toFixed(2)} · Z {teleportTarget.z.toFixed(2)}</code><div className="modal-actions"><button onClick={() => setTeleportTarget(null)}>{t.cancel}</button><button className="danger" onClick={() => teleport(teleportTarget)}>{t.teleport}</button></div></div>
        </div>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
