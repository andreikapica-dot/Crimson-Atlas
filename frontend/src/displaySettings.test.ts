import { describe, expect, it } from "vitest";
import { DEFAULT_DISPLAY_SETTINGS, normalizeDisplaySettings } from "./displaySettings";

describe("display settings", () => {
  it("uses safe defaults for invalid data", () => {
    expect(normalizeDisplaySettings(null)).toEqual(DEFAULT_DISPLAY_SETTINGS);
    expect(normalizeDisplaySettings({ markerSize: "huge", autoReroute: "yes" })).toEqual(DEFAULT_DISPLAY_SETTINGS);
  });

  it("keeps supported user choices", () => {
    expect(normalizeDisplaySettings({ markerSize: "large", showFoundMarkers: false, showHoverDetails: false, focusSelectedMarker: false, clusterMarkers: false, markerLabelMode: "selected", foundMarkerOpacity: 0.65 }))
      .toEqual({ markerSize: "large", showFoundMarkers: false, showHoverDetails: false, focusSelectedMarker: false, clusterMarkers: false, markerLabelMode: "selected", foundMarkerOpacity: 0.65 });
  });

  it("clamps found-marker opacity and rejects unknown label modes", () => {
    expect(normalizeDisplaySettings({ foundMarkerOpacity: 4, markerLabelMode: "nearby" }).foundMarkerOpacity).toBe(1);
    expect(normalizeDisplaySettings({ foundMarkerOpacity: 0 }).foundMarkerOpacity).toBe(0.1);
    expect(normalizeDisplaySettings({ markerLabelMode: "nearby" }).markerLabelMode).toBe("hover");
    expect(normalizeDisplaySettings({ markerLabelMode: "always" }).markerLabelMode).toBe("selected");
  });
});
