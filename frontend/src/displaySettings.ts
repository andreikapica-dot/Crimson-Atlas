export type MarkerSize = "compact" | "normal" | "large";
export type MarkerLabelMode = "off" | "hover" | "selected";

export interface DisplaySettings {
  markerSize: MarkerSize;
  showFoundMarkers: boolean;
  showHoverDetails: boolean;
  focusSelectedMarker: boolean;
  clusterMarkers: boolean;
  markerLabelMode: MarkerLabelMode;
  foundMarkerOpacity: number;
}

export const DISPLAY_SETTINGS_STORAGE_KEY = "crimson-atlas-display-settings-v1";

export const DEFAULT_DISPLAY_SETTINGS: DisplaySettings = {
  markerSize: "normal",
  showFoundMarkers: true,
  showHoverDetails: true,
  focusSelectedMarker: true,
  clusterMarkers: true,
  markerLabelMode: "hover",
  foundMarkerOpacity: 0.32,
};

export function normalizeDisplaySettings(value: unknown): DisplaySettings {
  if (!value || typeof value !== "object") return { ...DEFAULT_DISPLAY_SETTINGS };
  const source = value as Partial<Record<keyof DisplaySettings, unknown>>;
  const markerSize = source.markerSize === "compact" || source.markerSize === "large" ? source.markerSize : "normal";
  const bool = (key: "showFoundMarkers" | "showHoverDetails" | "focusSelectedMarker" | "clusterMarkers") =>
    typeof source[key] === "boolean" ? source[key] as boolean : DEFAULT_DISPLAY_SETTINGS[key];
  const markerLabelMode = source.markerLabelMode === "off" || source.markerLabelMode === "selected"
    ? source.markerLabelMode
    : source.markerLabelMode === "always" ? "selected"
    : "hover";
  const foundMarkerOpacity = typeof source.foundMarkerOpacity === "number" && Number.isFinite(source.foundMarkerOpacity)
    ? Math.min(1, Math.max(0.1, source.foundMarkerOpacity))
    : DEFAULT_DISPLAY_SETTINGS.foundMarkerOpacity;
  return {
    markerSize,
    showFoundMarkers: bool("showFoundMarkers"),
    showHoverDetails: bool("showHoverDetails"),
    focusSelectedMarker: bool("focusSelectedMarker"),
    clusterMarkers: bool("clusterMarkers"),
    markerLabelMode,
    foundMarkerOpacity,
  };
}

export function loadDisplaySettings(storage: Pick<Storage, "getItem"> = localStorage): DisplaySettings {
  try {
    return normalizeDisplaySettings(JSON.parse(storage.getItem(DISPLAY_SETTINGS_STORAGE_KEY) || "null"));
  } catch {
    return { ...DEFAULT_DISPLAY_SETTINGS };
  }
}
