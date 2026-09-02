/** Player marker component for Crimson Atlas.
 *
 * Uses a MapLibre Marker with a simple SVG circle (neutral, no heading).
 * Projection logic is delegated to coordinates.ts.
 */

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { gameToMap } from "../map/coordinates";

interface PlayerMarkerProps {
  map: maplibregl.Map | null;
  position: { x: number; y: number; z: number } | null;
}

export default function PlayerMarker({ map, position }: PlayerMarkerProps) {
  const markerRef = useRef<maplibregl.Marker | null>(null);

  useEffect(() => {
    if (!map) return;

    const el = document.createElement("div");
    el.innerHTML = `
      <svg width="32" height="32" viewBox="0 0 32 32" style="display:block">
        <circle cx="16" cy="16" r="7" fill="#ffd060" stroke="#000000" stroke-width="2"/>
        <circle cx="16" cy="16" r="3" fill="#000000"/>
      </svg>
    `;

    const marker = new maplibregl.Marker({ element: el, anchor: "center" })
      .setLngLat([0, 0])
      .addTo(map);

    markerRef.current = marker;

    return () => {
      marker.remove();
      markerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    if (!position || !markerRef.current) return;
    const mapPos = gameToMap(position);
    markerRef.current.setLngLat([mapPos.x, mapPos.y]);
  }, [position]);

  return null;
}
